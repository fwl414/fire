"""视频平台凭证的对称加密（仅用标准库）

摄像头 / NVR 的账号密码需要原样取回才能对接设备，因此不能做单向哈希，又不应该明文落库。
这里用 HKDF-SHA256 派生密钥 + HMAC-SHA256 计数器流加密，并附加 encrypt-then-MAC 完整性标签，
全部基于 hashlib/hmac，不引入第三方依赖（当前环境没有 cryptography）。

密钥来源（按优先级）：
1. `VIDEO_CREDENTIAL_KEY` 环境变量（生产环境必须显式配置）
2. `JWT_SECRET_KEY` 环境变量（做域分离派生）
3. 非生产环境下自动生成并持久化到 `VIDEO_CREDENTIAL_KEY_FILE`（默认 backend/.video_credential_key），
   保证本地重启后仍能解密；生产环境缺少密钥时直接报错，不做降级

存储格式：`v1:<b64 nonce>:<b64 密文>:<b64 标签>`
更换密钥后旧密文无法解密，需要重新录入摄像头凭证。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import warnings
from pathlib import Path
from typing import Tuple

VERSION = "v1"
NONCE_BYTES = 16
KEY_BYTES = 32
LABEL = b"fire-ai/video-credential"

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_KEY_FILE = BACKEND_DIR / ".video_credential_key"

IS_PRODUCTION = os.environ.get("ENV", "development").lower() in ("production", "prod")


class CredentialCipherError(RuntimeError):
    """凭证加解密失败。"""


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), validate=True)


def _key_file() -> Path:
    return Path(os.environ.get("VIDEO_CREDENTIAL_KEY_FILE") or DEFAULT_KEY_FILE)


def _load_or_create_dev_key() -> str:
    path = _key_file()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(48)
    path.write_text(generated, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    warnings.warn(
        f"未配置 VIDEO_CREDENTIAL_KEY，已生成本地开发密钥 {path}；生产环境请显式配置该环境变量。"
    )
    return generated


def get_key_source() -> str:
    """返回当前生效的密钥来源标识，供运维排查。"""
    if os.environ.get("VIDEO_CREDENTIAL_KEY", "").strip():
        return "VIDEO_CREDENTIAL_KEY"
    if os.environ.get("JWT_SECRET_KEY", "").strip():
        return "JWT_SECRET_KEY"
    if IS_PRODUCTION:
        return "none"
    return "dev_key_file"


def _root_secret() -> bytes:
    explicit = os.environ.get("VIDEO_CREDENTIAL_KEY", "").strip()
    if explicit:
        return explicit.encode("utf-8")

    jwt_secret = os.environ.get("JWT_SECRET_KEY", "").strip()
    if jwt_secret:
        return jwt_secret.encode("utf-8")

    if IS_PRODUCTION:
        raise CredentialCipherError(
            "生产环境必须配置 VIDEO_CREDENTIAL_KEY 或 JWT_SECRET_KEY，无法保存摄像头凭证"
        )
    return _load_or_create_dev_key().encode("utf-8")


def _hkdf(ikm: bytes, *, info: bytes, length: int = KEY_BYTES * 2) -> bytes:
    """RFC 5869 HKDF（空盐固定为 hashlen 个 0 字节）。"""
    prk = hmac.new(b"\x00" * hashlib.sha256().digest_size, ikm, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def _keys() -> Tuple[bytes, bytes]:
    material = _hkdf(_root_secret(), info=LABEL)
    return material[:KEY_BYTES], material[KEY_BYTES:]


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return out[:length]


def encrypt_secret(plaintext: str) -> str:
    """加密凭证；空字符串原样返回（表示未配置密码）。"""
    if not plaintext:
        return ""
    enc_key, mac_key = _keys()
    nonce = secrets.token_bytes(NONCE_BYTES)
    data = plaintext.encode("utf-8")
    stream = _keystream(enc_key, nonce, len(data))
    ciphertext = bytes(a ^ b for a, b in zip(data, stream))
    tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    return f"{VERSION}:{_b64e(nonce)}:{_b64e(ciphertext)}:{_b64e(tag)}"


def decrypt_secret(stored: str) -> str:
    """解密凭证；密文格式错误或校验失败时抛 CredentialCipherError。"""
    if not stored:
        return ""

    parts = stored.split(":")
    if len(parts) != 4 or parts[0] != VERSION:
        raise CredentialCipherError("凭证密文格式不正确，请重新录入摄像头密码")

    try:
        nonce = _b64d(parts[1])
        ciphertext = _b64d(parts[2])
        tag = _b64d(parts[3])
    except (ValueError, TypeError) as exc:
        raise CredentialCipherError(f"凭证密文解析失败：{exc}") from exc

    enc_key, mac_key = _keys()
    expected = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise CredentialCipherError("凭证密文校验失败，VIDEO_CREDENTIAL_KEY 可能已更换")

    stream = _keystream(enc_key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream)).decode("utf-8")


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(f"{VERSION}:") and len(value.split(":")) == 4
