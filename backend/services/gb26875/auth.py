"""GB 26875 接入设备身份校验

国标数据包里没有账号口令字段，设备身份来自「源地址」（6 字节 BCD = 12 位十进制）。
平台侧用 `GB26875Device` 台账登记允许接入的地址与设备系统类型：

- 地址未登记 → 拒绝（否认回答），不落任何数据
- 台账里配置了口令 → 报文需携带匹配的用户名/口令才放行
- 未配置口令 → 仅按地址放行（多数消防主机只做地址白名单）

口令为厂商私有扩展：注册阶段传输装置在「用户信息传输装置配置情况」（类型 26）
信息体里以 `USER=xxx;PWD=yyy` 明文携带。口令用 `video_credential_cipher` 对称加密落库，
任何接口都不回传明文。
"""
from __future__ import annotations

import re
import secrets
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from database import GB26875Device
from services import video_credential_cipher

CREDENTIAL_PATTERN = re.compile(r"(?:^|[;,\s])(?:USER|USERNAME)\s*=\s*([^;,]+)", re.IGNORECASE)
PASSWORD_PATTERN = re.compile(r"(?:^|[;,\s])(?:PWD|PASSWORD|PASS)\s*=\s*([^;,]+)", re.IGNORECASE)


class GB26875AuthError(RuntimeError):
    """设备身份校验失败。"""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_address(address: str) -> str:
    """归一化为 12 位十进制地址字符串。"""
    digits = "".join(ch for ch in str(address or "") if ch.isdigit())
    if not digits or len(digits) > 12:
        raise GB26875AuthError(f"设备地址非法：{address}", status_code=400)
    return digits.rjust(12, "0")


def resolve(db: Session, address: str) -> Optional[GB26875Device]:
    """按国标地址查台账；未登记返回 None。"""
    try:
        normalized = normalize_address(address)
    except GB26875AuthError:
        return None
    return db.query(GB26875Device).filter(GB26875Device.gb_address == normalized).first()


def parse_credentials(text: str) -> Optional[Tuple[str, str]]:
    """从信息体文本中解析 `USER=xxx;PWD=yyy`；解析不出返回 None。"""
    raw = _decode_text(text)
    if not raw:
        return None
    user = CREDENTIAL_PATTERN.search(raw)
    password = PASSWORD_PATTERN.search(raw)
    if not user or not password:
        return None
    return user.group(1).strip(), password.group(1).strip()


def _decode_text(raw) -> str:
    if isinstance(raw, bytes):
        for encoding in ("gb18030", "utf-8"):
            try:
                return raw.decode(encoding).strip("\x00").strip()
            except UnicodeDecodeError:
                continue
        return ""
    return str(raw or "").strip()


def verify_credentials(device: GB26875Device, credentials: Optional[Tuple[str, str]]) -> None:
    """校验用户名/口令；台账未配置口令时只做地址校验。"""
    stored = device.password_cipher or ""
    if not stored:
        return
    if not credentials:
        raise GB26875AuthError("该设备已启用口令校验，但报文未携带凭证")
    username, password = credentials
    if username != (device.username or ""):
        raise GB26875AuthError("设备用户名不匹配")
    try:
        expected = video_credential_cipher.decrypt_secret(stored)
    except video_credential_cipher.CredentialCipherError as exc:
        raise GB26875AuthError(f"设备口令无法解密，请重新签发：{exc}") from exc
    if not secrets.compare_digest(expected, password):
        raise GB26875AuthError("设备口令不匹配")


def authenticate(db: Session, address: str, credentials: Optional[Tuple[str, str]] = None) -> GB26875Device:
    """校验设备身份，通过返回台账记录，否则抛 GB26875AuthError。"""
    device = resolve(db, address)
    if not device:
        raise GB26875AuthError(f"设备地址未登记：{address}", status_code=403)
    if not device.enabled:
        raise GB26875AuthError(f"设备已停用：{device.gb_address}", status_code=403)
    verify_credentials(device, credentials)
    return device


def issue_credentials(db: Session, device: GB26875Device) -> Tuple[str, str]:
    """签发（或轮换）设备用户名与口令，返回明文（仅本次调用方可拿到）。"""
    username = f"gb{device.gb_address[-8:]}"
    password = secrets.token_urlsafe(12)
    device.username = username
    device.password_cipher = video_credential_cipher.encrypt_secret(password)
    db.commit()
    db.refresh(device)
    return username, password


def revoke_credentials(db: Session, device: GB26875Device) -> None:
    """撤销口令校验，回到仅地址白名单模式。"""
    device.username = ""
    device.password_cipher = ""
    db.commit()
    db.refresh(device)


def device_view(device: GB26875Device) -> dict:
    """台账脱敏视图，供接口返回。"""
    return {
        "id": device.id,
        "gb_address": device.gb_address,
        "device_code": device.device_code,
        "device_system_type": device.device_system_type,
        "username": device.username or "",
        "credential_configured": bool(device.password_cipher),
        "enabled": bool(device.enabled),
        "registered": bool(device.registered),
        "last_heartbeat_at": device.last_heartbeat_at.isoformat() if device.last_heartbeat_at else None,
        "remote_ip": device.remote_ip or "",
        "remote_port": device.remote_port,
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "updated_at": device.updated_at.isoformat() if device.updated_at else None,
    }
