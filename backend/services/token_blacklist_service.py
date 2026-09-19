"""
Token撤销服务
用于登出和禁用Token的场景
基于数据库持久化，支持重启与多实例共享，仅存储令牌指纹
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime
from typing import Dict

from database import SessionLocal, RevokedToken, ensure_auth_state_tables

_lock = threading.Lock()
_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    with _lock:
        if not _tables_ready:
            ensure_auth_state_tables()
            _tables_ready = True


def _fingerprint(token: str) -> str:
    """计算令牌指纹，避免明文令牌落库。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean_expired(db) -> None:
    """清理已过期的撤销记录。"""
    db.query(RevokedToken).filter(RevokedToken.expires_at <= datetime.utcnow()).delete(
        synchronize_session=False
    )


def add_to_blacklist(token: str, expires_at: float) -> None:
    """将Token加入撤销列表"""
    if not token:
        return
    _ensure_tables()
    fingerprint = _fingerprint(token)
    with _lock:
        db = SessionLocal()
        try:
            _clean_expired(db)
            record = db.query(RevokedToken).filter(RevokedToken.token_hash == fingerprint).first()
            if record:
                record.expires_at = datetime.utcfromtimestamp(expires_at)
                record.revoked_at = datetime.utcnow()
            else:
                db.add(
                    RevokedToken(
                        token_hash=fingerprint,
                        expires_at=datetime.utcfromtimestamp(expires_at),
                    )
                )
            db.commit()
        finally:
            db.close()


def is_blacklisted(token: str) -> bool:
    """检查Token是否已被撤销"""
    if not token:
        return False
    _ensure_tables()
    db = SessionLocal()
    try:
        record = db.query(RevokedToken).filter(
            RevokedToken.token_hash == _fingerprint(token),
            RevokedToken.expires_at > datetime.utcnow(),
        ).first()
        return record is not None
    finally:
        db.close()


def remove_from_blacklist(token: str) -> None:
    """从撤销列表移除Token"""
    if not token:
        return
    _ensure_tables()
    with _lock:
        db = SessionLocal()
        try:
            db.query(RevokedToken).filter(
                RevokedToken.token_hash == _fingerprint(token)
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def get_blacklist_stats() -> Dict[str, int]:
    """获取撤销列表统计信息"""
    _ensure_tables()
    db = SessionLocal()
    try:
        _clean_expired(db)
        db.commit()
        count = db.query(RevokedToken).filter(
            RevokedToken.expires_at > datetime.utcnow()
        ).count()
        return {"count": count}
    finally:
        db.close()


def clear_blacklist() -> None:
    """清空撤销列表"""
    _ensure_tables()
    with _lock:
        db = SessionLocal()
        try:
            db.query(RevokedToken).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def add_token_from_payload(token: str, payload: Dict) -> None:
    """从JWT payload中提取过期时间并加入撤销列表"""
    expires_at = payload.get("exp")
    if expires_at:
        add_to_blacklist(token, float(expires_at))
