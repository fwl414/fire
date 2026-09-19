"""
操作日志自动记录中间件
自动记录POST/PUT/DELETE/PATCH等写操作的审计日志，持久化到主数据库
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from database import SessionLocal
from services.common_utils import logger
from services.operation_log_service import SOURCE_HTTP, append_operation_log

LOG_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

SKIP_PATHS = [
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/health",
    "/api/demo",
]

ACTION_MAP = {
    "POST": "创建",
    "PUT": "更新",
    "DELETE": "删除",
    "PATCH": "修改",
}

MODULE_MAP = {
    "/api/system/users": "用户管理",
    "/api/system/roles": "角色管理",
    "/api/devices": "设备管理",
    "/api/inspection": "巡检管理",
    "/api/workorders": "工单管理",
    "/api/records": "巡检档案",
    "/api/multimodal": "多模态分析",
    "/api/alerts": "告警管理",
    "/api/risk": "风险评分",
    "/api/buildings": "建筑管理",
    "/api/batch-inspection": "批量巡检",
    "/api/reports": "报表中心",
    "/api/knowledge": "知识库",
    "/api/system/operation-logs": "操作日志",
}


def _extract_module(path: str) -> str:
    """从路径提取模块名"""
    for prefix, name in MODULE_MAP.items():
        if path.startswith(prefix):
            return name
    return "系统操作"


def _extract_action(path: str, method: str) -> str:
    """从路径和方法提取操作描述"""
    base = ACTION_MAP.get(method, method)
    if "/users" in path:
        if "/reset-password" in path:
            return "重置密码"
        if "/toggle-status" in path:
            return "切换状态"
        return f"{base}用户"
    if "/roles" in path:
        return f"{base}角色"
    if "/devices" in path:
        return f"{base}设备"
    if "/workorders" in path:
        return f"{base}工单"
    if "/inspection" in path:
        return f"{base}巡检"
    if "/alerts" in path:
        return f"{base}告警"
    return base


def _should_log(path: str, method: str) -> bool:
    """判断是否需要记录日志"""
    if method not in LOG_METHODS:
        return False
    for skip in SKIP_PATHS:
        if path.startswith(skip):
            return False
    return True


class OperationLogMiddleware(BaseHTTPMiddleware):
    """操作日志自动记录中间件"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        if not _should_log(path, method):
            return await call_next(request)

        start_time = time.time()
        module = _extract_module(path)
        action = _extract_action(path, method)

        username = "匿名用户"
        user_id = None
        tenant_id = None
        ip_address = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "")[:250]

        try:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                from services.auth_service import decode_token
                payload = decode_token(token)
                if payload:
                    username = payload.get("username", "匿名用户")
                    user_id = int(payload.get("sub", 0)) or None
                    tenant_id = int(payload.get("tenant_id", 0)) or None
        except Exception:
            pass

        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Process-Time"] = str(duration_ms)

        status_code = response.status_code
        log_status = "success"
        if status_code >= 500:
            log_status = "error"
        elif status_code >= 400:
            log_status = "warning"

        # 写入主数据库并接入哈希链（失败不影响业务响应）
        try:
            db = SessionLocal()
            try:
                append_operation_log(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    username=username,
                    module=module,
                    action=action,
                    title=action,
                    description=f"{method} {path}",
                    level="warning" if log_status == "warning" else ("danger" if log_status == "error" else "info"),
                    status=log_status,
                    source=SOURCE_HTTP,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_data={"method": method, "path": path},
                    response_data={"status_code": status_code},
                    duration_ms=duration_ms,
                )
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"记录操作日志到数据库失败: {e}")

        return response
