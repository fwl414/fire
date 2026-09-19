"""设备上报消息收件箱

职责：
- 生成端到端幂等键，同一台设备同一条消息重复投递时只处理一次
- 记录消息生命周期（pending → processing → processed / failed / dead），可追溯、可重放
- 与后台任务队列配合，实现削峰、重试与死信

注意分工：**验签仍在收到消息时同步完成**（不能让未验签的数据落库），
只有业务处理（阈值判定、生成告警与工单）被移到队列里异步执行。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import DeviceMessage

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_PROCESSED = "processed"
STATUS_FAILED = "failed"
STATUS_DEAD = "dead"

ACTIVE_STATUSES = (STATUS_PENDING, STATUS_PROCESSING)
ABNORMAL_STATUSES = (STATUS_FAILED, STATUS_DEAD)

MAX_ERROR_LENGTH = 1000


def build_message_id(device_code: str, envelope: Dict[str, Any]) -> str:
    """幂等键：优先用设备提供的 message_id，否则用 `{device_code}:{nonce}`。

    nonce 是设备签名的一部分，天然一消息一个；没有 nonce 时退化为内容哈希。
    """
    provided = str(envelope.get("message_id") or envelope.get("msg_id") or "").strip()
    if provided:
        return provided[:128]

    nonce = str(envelope.get("nonce") or "").strip()
    if nonce:
        return f"{device_code}:{nonce}"[:128]

    digest = hashlib.sha256(
        f"{device_code}|{envelope.get('timestamp', '')}|{envelope.get('data', {})}".encode("utf-8")
    ).hexdigest()
    return f"{device_code}:{digest}"[:128]


def begin_message(
    db: Session,
    *,
    tenant_id: Optional[int],
    device_code: str,
    kind: str,
    envelope: Dict[str, Any],
    source: str = "mqtt",
    topic: str = "",
    device_id: Optional[int] = None,
) -> Tuple[Optional[DeviceMessage], bool]:
    """登记一条消息。返回 (记录, 是否重复投递)。

    重复判定靠 `(tenant_id, message_id)` 唯一约束，并发投递时由数据库兜底。
    """
    message_id = build_message_id(device_code, envelope)
    row = DeviceMessage(
        tenant_id=tenant_id,
        message_id=message_id,
        device_id=device_id,
        device_code=device_code or "",
        kind=kind or "",
        source=source,
        topic=(topic or "")[:255],
        payload=envelope.get("data") if isinstance(envelope.get("data"), dict) else {},
        envelope=envelope,
        status=STATUS_PENDING,
        attempts=0,
        received_at=datetime.utcnow(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = find_message(db, tenant_id, message_id)
        if existing is None:
            # 不是幂等冲突（例如字段约束不满足），照常抛出，不要伪装成"重复投递"
            raise
        logger.info(f"设备消息重复投递已忽略：{device_code} / {message_id}")
        return existing, True
    db.refresh(row)
    return row, False


def find_message(db: Session, tenant_id: Optional[int], message_id: str) -> Optional[DeviceMessage]:
    return db.query(DeviceMessage).filter(
        DeviceMessage.tenant_id == tenant_id,
        DeviceMessage.message_id == message_id,
    ).first()


def get_message(db: Session, tenant_id: Optional[int], row_id: int) -> Optional[DeviceMessage]:
    query = db.query(DeviceMessage).filter(DeviceMessage.id == row_id)
    if tenant_id is not None:
        query = query.filter(
            (DeviceMessage.tenant_id == tenant_id) | (DeviceMessage.tenant_id.is_(None))
        )
    return query.first()


def get_by_message_id(db: Session, message_id: str) -> Optional[DeviceMessage]:
    return db.query(DeviceMessage).filter(DeviceMessage.message_id == message_id).first()


def mark_processing(db: Session, row_id: int) -> None:
    row = db.query(DeviceMessage).filter(DeviceMessage.id == row_id).first()
    if not row:
        return
    row.status = STATUS_PROCESSING
    row.attempts = (row.attempts or 0) + 1
    row.error = ""
    db.commit()


def mark_processed(db: Session, row_id: int, *, alert_id: Optional[int] = None) -> None:
    row = db.query(DeviceMessage).filter(DeviceMessage.id == row_id).first()
    if not row:
        return
    row.status = STATUS_PROCESSED
    row.alert_id = alert_id
    row.error = ""
    row.processed_at = datetime.utcnow()
    db.commit()


def mark_failed(db: Session, row_id: int, error: str, *, dead: bool = False) -> None:
    row = db.query(DeviceMessage).filter(DeviceMessage.id == row_id).first()
    if not row:
        return
    row.status = STATUS_DEAD if dead else STATUS_FAILED
    row.error = (error or "")[:MAX_ERROR_LENGTH]
    if dead:
        row.processed_at = datetime.utcnow()
    db.commit()


def requeue(db: Session, row: DeviceMessage) -> bool:
    """把失败/死信消息重新置为待处理，供人工重放。"""
    if row.status == STATUS_PROCESSED:
        return False
    row.status = STATUS_PENDING
    row.error = ""
    db.commit()
    return True


def list_messages(
    db: Session,
    tenant_id: Optional[int],
    *,
    status: str = "",
    device_code: str = "",
    kind: str = "",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    query = db.query(DeviceMessage)
    if tenant_id is not None:
        query = query.filter(
            (DeviceMessage.tenant_id == tenant_id) | (DeviceMessage.tenant_id.is_(None))
        )
    if status:
        query = query.filter(DeviceMessage.status == status)
    if device_code:
        query = query.filter(DeviceMessage.device_code == device_code)
    if kind:
        query = query.filter(DeviceMessage.kind == kind)
    rows = (
        query.order_by(DeviceMessage.received_at.desc(), DeviceMessage.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [serialize(row) for row in rows]


def stats(db: Session, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    query = db.query(DeviceMessage)
    if tenant_id is not None:
        query = query.filter(
            (DeviceMessage.tenant_id == tenant_id) | (DeviceMessage.tenant_id.is_(None))
        )
    counts: Dict[str, int] = {}
    for status, total in (
        query.with_entities(DeviceMessage.status, func.count(DeviceMessage.id))
        .group_by(DeviceMessage.status)
        .all()
    ):
        counts[status or STATUS_PENDING] = int(total)
    return {"by_status": counts, "total": sum(counts.values())}


def serialize(row: DeviceMessage) -> Dict[str, Any]:
    return {
        "id": row.id,
        "message_id": row.message_id,
        "tenant_id": row.tenant_id,
        "device_id": row.device_id,
        "device_code": row.device_code or "",
        "kind": row.kind or "",
        "source": row.source or "",
        "topic": row.topic or "",
        "status": row.status,
        "attempts": row.attempts or 0,
        "error": row.error or "",
        "alert_id": row.alert_id,
        "payload": row.payload or {},
        "received_at": row.received_at.isoformat() if row.received_at else "",
        "processed_at": row.processed_at.isoformat() if row.processed_at else "",
    }
