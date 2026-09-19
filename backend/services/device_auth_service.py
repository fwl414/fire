"""设备身份认证服务

设备接入采用「设备密钥 + HMAC-SHA256 签名 + 时间戳窗口 + nonce 去重」三步校验，
不依赖用户 JWT，使真实硬件可以独立接入。

签名串定义（HTTP 与 MQTT 一致）：
    base = f"{device_code}\\n{timestamp}\\n{nonce}\\n{sha256(payload_bytes)}"
    signature = HMAC_SHA256(device_secret, base).hexdigest()

其中 payload_bytes：
    - HTTP：请求体原始字节
    - MQTT：data 字段的规范 JSON（sort_keys=True，separators=(",", ":")）
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Device, DeviceRequestNonce

# 允许的客户端与服务端时间偏移（秒），用于抵御重放
MAX_SIGN_SKEW_SECONDS = int(os.environ.get("DEVICE_SIGN_MAX_SKEW_SECONDS", "300"))
# nonce 记录保留时长（分钟），超过该时长的记录会被清理
NONCE_RETENTION_MINUTES = int(os.environ.get("DEVICE_NONCE_RETENTION_MINUTES", "15"))


class DeviceAuthError(Exception):
    """设备身份校验失败。"""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def generate_device_secret() -> str:
    """生成 32 字节随机设备密钥（64 位十六进制）。"""
    return secrets.token_hex(32)


def mask_secret(secret: Optional[str]) -> str:
    """密钥脱敏展示，只保留前 4 位。"""
    if not secret:
        return ""
    return f"{secret[:4]}{'*' * 8}"


def issue_device_credentials(db: Session, device: Device) -> str:
    """签发（或轮换）设备密钥，明文仅在此处返回一次。"""
    secret = generate_device_secret()
    device.device_secret = secret
    device.secret_issued_at = datetime.utcnow()
    device.ingest_enabled = True
    db.commit()
    db.refresh(device)
    return secret


def revoke_device_credentials(db: Session, device: Device) -> None:
    """吊销设备密钥并关闭接入。"""
    device.device_secret = ""
    device.secret_issued_at = None
    device.ingest_enabled = False
    db.commit()
    db.refresh(device)


def build_signature_base(device_code: str, timestamp: str, nonce: str, payload_bytes: bytes) -> bytes:
    payload_hash = hashlib.sha256(payload_bytes or b"").hexdigest()
    return f"{device_code}\n{timestamp}\n{nonce}\n{payload_hash}".encode("utf-8")


def compute_signature(
    secret: str,
    device_code: str,
    timestamp: str,
    nonce: str,
    payload_bytes: bytes,
) -> str:
    base = build_signature_base(device_code, timestamp, nonce, payload_bytes)
    return hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()


def canonical_payload_bytes(data: Any) -> bytes:
    """MQTT 消息体的规范 JSON 序列化，保证设备与服务端计算一致。"""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _consume_nonce(db: Session, device_id: int, nonce: str) -> None:
    """记录并校验 nonce；重复即判定为重放。"""
    if not nonce:
        raise DeviceAuthError("缺少 nonce")

    cutoff = datetime.utcnow() - timedelta(minutes=NONCE_RETENTION_MINUTES)
    db.query(DeviceRequestNonce).filter(DeviceRequestNonce.created_at < cutoff).delete(
        synchronize_session=False
    )
    db.commit()

    if db.query(DeviceRequestNonce).filter(
        DeviceRequestNonce.device_id == device_id,
        DeviceRequestNonce.nonce == nonce,
    ).first():
        raise DeviceAuthError("请求已被处理（nonce 重复）")

    db.add(DeviceRequestNonce(device_id=device_id, nonce=nonce))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DeviceAuthError("请求已被处理（nonce 重复）")


def verify_device_request(
    db: Session,
    *,
    device_code: str,
    timestamp: str,
    nonce: str,
    signature: str,
    payload_bytes: bytes,
    tenant_id: Optional[int] = None,
) -> Device:
    """校验设备请求身份，通过后返回设备并刷新 last_seen_at。"""
    if not device_code:
        raise DeviceAuthError("缺少设备标识")
    if not signature:
        raise DeviceAuthError("缺少签名")

    device = db.query(Device).filter(Device.device_code == device_code).first()
    if not device:
        raise DeviceAuthError("设备未注册")
    if not device.device_secret:
        raise DeviceAuthError("设备尚未签发接入凭证")
    if not device.ingest_enabled:
        raise DeviceAuthError("设备接入已被禁用", status_code=403)
    if tenant_id is not None and device.tenant_id != tenant_id:
        raise DeviceAuthError("设备不属于该租户", status_code=403)

    try:
        ts_value = int(str(timestamp))
    except (TypeError, ValueError):
        raise DeviceAuthError("时间戳格式错误")

    skew = abs(int(time.time()) - ts_value)
    if skew > MAX_SIGN_SKEW_SECONDS:
        raise DeviceAuthError(f"时间戳超出允许范围（±{MAX_SIGN_SKEW_SECONDS} 秒）")

    expected = compute_signature(device.device_secret, device_code, str(timestamp), nonce, payload_bytes)
    if not hmac.compare_digest(expected, str(signature)):
        raise DeviceAuthError("签名校验失败")

    _consume_nonce(db, device.id, nonce)

    device.last_seen_at = datetime.utcnow()
    if device.status in ("离线", "offline"):
        device.status = "正常"
    db.commit()
    db.refresh(device)
    return device


def device_credentials_status(device: Device) -> Dict[str, Any]:
    """设备接入凭证状态（不含明文密钥）。"""
    return {
        "id": device.id,
        "device_code": device.device_code,
        "device_name": device.device_name,
        "tenant_id": device.tenant_id,
        "credential_issued": bool(device.device_secret),
        "secret_masked": mask_secret(device.device_secret),
        "secret_issued_at": device.secret_issued_at.isoformat() if device.secret_issued_at else "",
        "ingest_enabled": bool(device.ingest_enabled),
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else "",
    }
