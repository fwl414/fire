"""跨实例互斥锁与实例标识（数据库实现）

多实例部署时，各实例都会启动，"只应有一个实例执行"的动作必须互斥，否则会出现
重复播种、重复备份。这里用一张带唯一约束的小表实现，不引入 Redis：

- `acquire`：尝试占用；被他人持有时按 `expires_at` 判断是否已过期（持有者崩溃后可被接管）
- `release`：仅持有者能释放
- `run_exclusive`：拿不到锁就直接跳过，适合启动期种子、定时任务

`instance_id()` 同时用于 worker 标识与健康检查，便于在负载均衡下确认请求落到了哪个实例。
"""
from __future__ import annotations

import logging
import os
import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable, Optional, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import RuntimeLock, SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_TTL_SECONDS = 300

_instance_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def instance_id() -> str:
    """本实例的唯一标识，进程生命周期内不变。"""
    return _instance_id


def acquire(db: Session, name: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, owner: Optional[str] = None) -> bool:
    """尝试获取锁；成功返回 True。"""
    owner = owner or _instance_id
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=max(1, ttl_seconds))

    existing = db.query(RuntimeLock).filter(RuntimeLock.name == name).first()
    if existing:
        held_by_other = (
            existing.owner != owner
            and existing.expires_at is not None
            and existing.expires_at > now
        )
        if held_by_other:
            return False
        existing.owner = owner
        existing.acquired_at = now
        existing.expires_at = expires_at
        db.commit()
        return True

    db.add(RuntimeLock(name=name, owner=owner, acquired_at=now, expires_at=expires_at))
    try:
        db.commit()
    except IntegrityError:
        # 其他实例抢先插入，说明锁已被占用
        db.rollback()
        return False
    return True


def release(db: Session, name: str, *, owner: Optional[str] = None) -> None:
    owner = owner or _instance_id
    existing = db.query(RuntimeLock).filter(RuntimeLock.name == name).first()
    if not existing or existing.owner != owner:
        return
    db.delete(existing)
    db.commit()


def snapshot(db: Session) -> list:
    """当前所有锁的状态，供运维查看。"""
    now = datetime.utcnow()
    return [
        {
            "name": row.name,
            "owner": row.owner or "",
            "acquired_at": row.acquired_at.isoformat() if row.acquired_at else "",
            "expires_at": row.expires_at.isoformat() if row.expires_at else "",
            "expired": bool(row.expires_at and row.expires_at <= now),
            "held_by_me": row.owner == _instance_id,
        }
        for row in db.query(RuntimeLock).order_by(RuntimeLock.name.asc()).all()
    ]


def run_exclusive(
    name: str,
    action: Callable[[], T],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db: Optional[Session] = None,
) -> Optional[T]:
    """拿不到锁就跳过（返回 None）；拿到锁则执行并在结束后释放。"""
    owns_session = db is None
    session = db or SessionLocal()
    try:
        if not acquire(session, name, ttl_seconds=ttl_seconds):
            logger.info(f"动作「{name}」已由其他实例执行，本实例跳过")
            return None
        try:
            return action()
        finally:
            release(session, name)
    except Exception as exc:  # noqa: BLE001 - 启动期动作失败不应阻断应用启动
        logger.warning(f"执行互斥动作「{name}」失败: {exc}")
        return None
    finally:
        if owns_session:
            session.close()


@contextmanager
def exclusive(name: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS):
    """上下文管理器形式；未获得锁时 `yield False`。"""
    db = SessionLocal()
    try:
        acquired = acquire(db, name, ttl_seconds=ttl_seconds)
        try:
            yield acquired
        finally:
            if acquired:
                release(db, name)
    finally:
        db.close()
