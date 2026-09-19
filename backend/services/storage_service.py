"""文件存储抽象：本地磁盘 + S3 兼容对象存储

背景：上传文件此前只落在本地磁盘，多实例部署时 A 实例写入的文件在 B 实例上读不到。

策略（**本地优先 + 对象存储镜像**）：
- 写入：始终写本地（保证依赖本地路径的分析链路——如视觉识别读图片——继续可用），
  同时镜像到 S3
- 读取：本地命中直接返回；本地缺失（例如请求落到另一个实例）则从 S3 拉回本地再返回
- 未配置 S3 时行为与原来完全一致（纯本地）

S3 使用标准 SigV4 签名，只依赖 httpx 与标准库，不引入 boto3。
兼容 MinIO / 阿里云 OSS / 腾讯云 COS 等支持 S3 协议的端点。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower()

S3_ENDPOINT = (os.environ.get("S3_ENDPOINT") or "").rstrip("/")
S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_REGION = os.environ.get("S3_REGION", "us-east-1").strip() or "us-east-1"
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "").strip()
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "").strip()
S3_PREFIX = os.environ.get("S3_PREFIX", "").strip().strip("/")
S3_PATH_STYLE = os.environ.get("S3_PATH_STYLE", "true").lower() == "true"
S3_VERIFY_TLS = os.environ.get("S3_VERIFY_TLS", "true").lower() == "true"
S3_TIMEOUT_SECONDS = float(os.environ.get("S3_TIMEOUT_SECONDS", "20"))

SERVICE = "s3"
EMPTY_PAYLOAD_HASH = hashlib.sha256(b"").hexdigest()

# 路径中不需要转义的字符（'/' 保留以维持目录层级）
_SAFE_CHARS = "/-_.~"


class StorageError(RuntimeError):
    """对象存储操作失败。"""


def s3_enabled() -> bool:
    """是否启用对象存储镜像。"""
    if STORAGE_BACKEND != "s3":
        return False
    missing = [
        name for name, value in (
            ("S3_ENDPOINT", S3_ENDPOINT),
            ("S3_BUCKET", S3_BUCKET),
            ("S3_ACCESS_KEY", S3_ACCESS_KEY),
            ("S3_SECRET_KEY", S3_SECRET_KEY),
        ) if not value
    ]
    if missing:
        logger.warning(f"STORAGE_BACKEND=s3 但缺少配置 {missing}，将退化为本地存储")
        return False
    return True


def describe() -> Dict[str, Any]:
    return {
        "backend": STORAGE_BACKEND,
        "object_storage_enabled": s3_enabled(),
        "bucket": S3_BUCKET if s3_enabled() else "",
        "prefix": S3_PREFIX,
        "region": S3_REGION if s3_enabled() else "",
        "path_style": S3_PATH_STYLE,
        "missing_config": [
            name for name, value in (
                ("S3_ENDPOINT", S3_ENDPOINT), ("S3_BUCKET", S3_BUCKET),
                ("S3_ACCESS_KEY", S3_ACCESS_KEY), ("S3_SECRET_KEY", S3_SECRET_KEY),
            ) if not value
        ] if STORAGE_BACKEND == "s3" else [],
    }


# ---------------- SigV4 签名 ----------------


def _uri_encode(value: str, *, encode_slash: bool = True) -> str:
    safe = "" if encode_slash else _SAFE_CHARS
    return urllib.parse.quote(value, safe=safe)


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def derive_signing_key(secret_key: str, date_stamp: str, region: str, service: str = SERVICE) -> bytes:
    """AWS4 派生签名密钥（AWS 官方示例中的四步 HMAC）。"""
    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def canonical_request(
    method: str,
    canonical_uri: str,
    query: Dict[str, str],
    headers: Dict[str, str],
    payload_hash: str,
) -> Tuple[str, str]:
    """返回 (规范化请求字符串, signedHeaders)。"""
    lower_headers = {key.lower().strip(): str(value).strip() for key, value in headers.items()}
    signed_headers = ";".join(sorted(lower_headers))
    header_block = "\n".join(f"{key}:{lower_headers[key]}" for key in sorted(lower_headers))
    canonical_query = "&".join(
        f"{_uri_encode(str(key))}={_uri_encode(str(value))}" for key, value in sorted(query.items())
    )
    parts = [
        method.upper(),
        canonical_uri,
        canonical_query,
        header_block,
        "",
        signed_headers,
        payload_hash,
    ]
    return "\n".join(parts), signed_headers


def sign_headers(
    *,
    method: str,
    canonical_uri: str,
    query: Dict[str, str],
    host: str,
    payload: bytes,
    access_key: str,
    secret_key: str,
    region: str,
    now: Optional[datetime] = None,
) -> Dict[str, str]:
    """生成带 SigV4 签名的请求头（含 Authorization / x-amz-date / x-amz-content-sha256）。"""
    moment = now or datetime.now(timezone.utc)
    amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = moment.strftime("%Y%m%d")
    payload_hash = _sha256_hex(payload)

    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    request, signed_headers = canonical_request(method, canonical_uri, query, headers, payload_hash)
    scope = f"{date_stamp}/{region}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        _sha256_hex(request.encode("utf-8")),
    ])
    signature = hmac.new(
        derive_signing_key(secret_key, date_stamp, region), string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return headers


# ---------------- S3 客户端 ----------------


def _object_url(key: str) -> Tuple[str, str]:
    """返回 (完整 URL, Host 头)。"""
    object_key = f"{S3_PREFIX}/{key}".strip("/")
    if S3_PATH_STYLE:
        url = f"{S3_ENDPOINT}/{S3_BUCKET}/{_uri_encode(object_key, encode_slash=False)}"
        host = urllib.parse.urlparse(S3_ENDPOINT).netloc
    else:
        parsed = urllib.parse.urlparse(S3_ENDPOINT)
        url = f"{parsed.scheme}://{S3_BUCKET}.{parsed.netloc}/{_uri_encode(object_key, encode_slash=False)}"
        host = f"{S3_BUCKET}.{parsed.netloc}"
    return url, host


def _request(method: str, key: str, payload: bytes = b"") -> httpx.Response:
    url, host = _object_url(key)
    parsed = urllib.parse.urlparse(url)
    canonical_uri = parsed.path or "/"
    headers = sign_headers(
        method=method,
        canonical_uri=canonical_uri,
        query={},
        host=host,
        payload=payload,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        region=S3_REGION,
    )
    try:
        with httpx.Client(timeout=S3_TIMEOUT_SECONDS, verify=S3_VERIFY_TLS) as client:
            return client.request(method, url, headers=headers, content=payload if payload else None)
    except httpx.HTTPError as exc:
        raise StorageError(f"对象存储请求失败：{type(exc).__name__}: {exc}") from exc


def s3_put(key: str, content: bytes) -> None:
    response = _request("PUT", key, content)
    if response.status_code not in (200, 201, 204):
        raise StorageError(f"对象存储写入失败：HTTP {response.status_code} {response.text[:200]}")


def s3_get(key: str) -> Optional[bytes]:
    response = _request("GET", key)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise StorageError(f"对象存储读取失败：HTTP {response.status_code} {response.text[:200]}")
    return response.content


def s3_delete(key: str) -> None:
    response = _request("DELETE", key)
    if response.status_code not in (200, 202, 204, 404):
        logger.warning(f"对象存储删除失败：HTTP {response.status_code}")


# ---------------- 对上层暴露的门面 ----------------


def _local_root() -> Path:
    from services.upload_archive_service import UPLOAD_ROOT

    return UPLOAD_ROOT


def local_path(key: str) -> Path:
    return _local_root() / Path(key).as_posix().lstrip("/")


def write_local(key: str, content: bytes) -> Path:
    target = local_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def put(key: str, content: bytes) -> Path:
    """写入文件：本地必写，启用对象存储时同步镜像。"""
    target = write_local(key, content)
    if s3_enabled():
        s3_put(key, content)
    return target


def materialize(key: str) -> Optional[Path]:
    """确保文件在本地可用，返回路径；本地与对象存储都没有则返回 None。"""
    target = local_path(key)
    if target.is_file():
        return target
    if not s3_enabled():
        return None
    try:
        content = s3_get(key)
    except StorageError as exc:
        logger.warning(f"从对象存储取回文件失败（{key}）：{exc}")
        return None
    if content is None:
        return None
    return write_local(key, content)


def read_bytes(key: str) -> Optional[bytes]:
    target = local_path(key)
    if target.is_file():
        return target.read_bytes()
    if not s3_enabled():
        return None
    try:
        content = s3_get(key)
    except StorageError as exc:
        logger.warning(f"从对象存储读取文件失败（{key}）：{exc}")
        return None
    if content is not None:
        write_local(key, content)
    return content


def delete(key: str) -> None:
    target = local_path(key)
    if target.is_file():
        try:
            target.unlink()
        except OSError as exc:
            logger.warning(f"删除本地文件失败（{key}）：{exc}")
    if s3_enabled():
        s3_delete(key)
