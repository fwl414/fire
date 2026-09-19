"""
通用工具与全局配置
- 统一响应格式
- 全局异常处理
- 结构化日志
"""
from __future__ import annotations

import time
import json
import logging
import traceback
import os
import uuid
from typing import Any, Collection, Dict, Optional, Tuple
from datetime import date, datetime, timedelta

from fastapi import Request, status, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.exceptions import HTTPException as StarletteHTTPException

_IS_PRODUCTION = os.environ.get("ENV", "development").lower() in ("production", "prod")
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


class JsonFormatter(logging.Formatter):
    """JSON格式日志，便于日志采集系统"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration"):
            log_entry["duration"] = record.duration
        return json.dumps(log_entry, ensure_ascii=False)


_handler = logging.StreamHandler()
if _IS_PRODUCTION:
    _handler.setFormatter(JsonFormatter())
else:
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

logging.basicConfig(level=_LOG_LEVEL, handlers=[_handler])
logger = logging.getLogger("fire_ai_agent")


def _utc_offset() -> timedelta:
    """本地时区相对 UTC 的偏移（取整到秒）。

    `datetime.now() - datetime.utcnow()` 是两次独立取时相减，会带几微秒的抖动；
    直接用它算「本地零点」会得到一个带微秒的随机边界，恰好在零点（或跨天那一刻）
    产生的记录就可能被算进前一天/后一天。时区偏移本身是整分钟的，取整到秒没有误差。
    """
    offset = datetime.now() - datetime.utcnow()
    return timedelta(seconds=round(offset.total_seconds()))


def local_day_bounds_utc(target: date) -> Tuple[datetime, datetime]:
    """任意**本地日期**对应的 UTC 区间 `[零点, 次日零点)`。

    用于「按用户选的某一天统计」这类场景（例如安全简报可以选日期）。
    库里的时间列是无时区的 UTC，所以本地零点要减去时区偏移。
    """
    start = datetime.combine(target, datetime.min.time()) - _utc_offset()
    return start, start + timedelta(days=1)


def local_day_start_utc(days_ago: int = 0) -> datetime:
    """本地「今天零点」对应的 UTC 时刻（`days_ago` 往前推若干天）。

    数据库里的 `created_at` / `login_at` 等落库的是无时区的 `datetime.utcnow()`，
    而业务上的「今日」是**用户本地时区**的今天，两者相差一个时区偏移。
    直接拿本地零点去和 UTC 值比较会把边界算错：UTC+8 下「今日」会从本地 08:00 才开始，
    本地 00:00-08:00 产生的记录会被漏掉。

    偏移取整到秒（见 `_utc_offset`），避免微秒抖动让边界漂移；
    跨夏令时切换那一天会有偏差，本项目部署时区无夏令时。
    """
    target = datetime.now().date() - timedelta(days=days_ago)
    return local_day_bounds_utc(target)[0]


def local_day_end_utc(days_ago: int = 0) -> datetime:
    """本地「今天 23:59:59.999999」对应的 UTC 时刻，与 `local_day_start_utc` 配对使用。"""
    return local_day_start_utc(days_ago) + timedelta(days=1) - timedelta(microseconds=1)


def parse_date(raw: Any) -> Optional[date]:
    """解析 `YYYY-MM-DD`（也接受 ISO 时间串，取日期部分）；解析不出来返回 None。

    各处的日期入参都走这一个实现，避免「同一个参数在 A 接口被忽略、在 B 接口报错」。
    """
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def paginate(query, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    统一分页查询助手。
    用法:
        result = paginate(db.query(User).filter(...), page=1, page_size=20)
    返回:
        {"list": [...], "total": 100, "page": 1, "page_size": 20, "total_pages": 5}
    """
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size
    return {
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def success_response(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """统一成功响应格式"""
    return {
        "ok": True,
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def error_response(message: str = "error", code: int = 1, http_status: int = 400,
                   data: Any = None) -> JSONResponse:
    """统一错误响应格式"""
    return JSONResponse(
        status_code=http_status,
        content={
            "ok": False,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = round(time.time() - start_time, 4)
            response.headers["X-Process-Time"] = str(process_time)
            if response.status_code >= 500:
                logger.error(f"{request.method} {request.url.path} {response.status_code}")
            elif response.status_code >= 400:
                logger.warning(f"{request.method} {request.url.path} {response.status_code}")
            else:
                logger.info(f"{request.method} {request.url.path} {response.status_code} ({process_time}s)")
            return response
        except Exception as e:
            process_time = round(time.time() - start_time, 4)
            tb = traceback.format_exc()
            logger.error(f"UNHANDLED EXCEPTION {request.method} {request.url.path}\n{tb}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "ok": False,
                    "code": 500,
                    "message": f"服务器内部错误: {str(e)}",
                    "data": None,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "process_time": process_time
                }
            )


# ---------------- 上传文件安全校验 ----------------

UPLOAD_MAX_BYTES = int(os.environ.get("MAX_FILE_SIZE", "52428800"))

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"})
CAD_EXTENSIONS = frozenset({".dxf", ".dwg"})
BIM_EXTENSIONS = frozenset({".ifc", ".glb", ".gltf", ".rvt"})
TEXT_EXTENSIONS = frozenset({".txt", ".csv", ".json", ".md"})

# 内容特征前缀，用于防止仅伪造扩展名的上传
_PREFIX_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".bmp": (b"BM",),
    ".dwg": (b"AC10",),
    ".ifc": (b"ISO-10303-21",),
    ".glb": (b"glTF",),
    ".rvt": (b"\xd0\xcf\x11\xe0",),
}


def _looks_like_text(content: bytes) -> bool:
    sample = content[:8192]
    if b"\x00" in sample:
        return False
    for encoding in ("utf-8", "gbk"):
        try:
            sample.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def _content_matches_extension(ext: str, content: bytes) -> bool:
    if ext == ".webp":
        return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if ext == ".dxf":
        return b"SECTION" in content[:8192] or content.startswith(b"AutoCAD Binary DXF")
    prefixes = _PREFIX_SIGNATURES.get(ext)
    if prefixes:
        return any(content.startswith(prefix) for prefix in prefixes)
    return _looks_like_text(content)


def random_upload_name(prefix: str, ext: str) -> str:
    """生成随机上传文件名，避免使用用户可控的名称。"""
    return f"{prefix}_{uuid.uuid4().hex}{ext}"


async def read_validated_upload(
    upload: Optional[UploadFile],
    allowed_extensions: Collection[str],
    *,
    max_bytes: Optional[int] = None,
    label: str = "文件",
) -> Tuple[bytes, str]:
    """读取并校验上传文件：扩展名白名单 + 大小限制 + 内容特征校验。

    返回 (文件内容, 规范化小写扩展名)，校验不通过时抛出 HTTPException。
    """
    filename = (getattr(upload, "filename", "") or "").strip()
    if not upload or not filename:
        raise HTTPException(status_code=400, detail=f"{label}文件名无效")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        allowed = "、".join(sorted(allowed_extensions))
        raise HTTPException(status_code=400, detail=f"{label}格式不支持，仅允许：{allowed}")

    limit = max_bytes if max_bytes is not None else UPLOAD_MAX_BYTES
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{label}内容为空")
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"{label}超过大小限制 {round(limit / 1024 / 1024, 1)}MB",
        )
    if not _content_matches_extension(ext, content):
        raise HTTPException(status_code=400, detail=f"{label}内容与扩展名不符，请上传真实文件")

    return content, ext


def register_exception_handlers(app):
    """注册全局异常处理器"""
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"ValueError at {request.url.path}: {exc}")
        return error_response(str(exc), code=400, http_status=400)

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        logger.warning(f"PermissionError at {request.url.path}: {exc}")
        return error_response(str(exc), code=403, http_status=403)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTP {exc.status_code} at {request.url.path}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "code": exc.status_code,
                "message": exc.detail if isinstance(exc.detail, str) else "请求错误",
                "data": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception at {request.url.path}\n{traceback.format_exc()}")
        debug = os.environ.get("DEBUG", "false").lower() == "true"
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "code": 500,
                "message": "服务器内部错误",
                "data": {"error": str(exc)} if debug else None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    return app
