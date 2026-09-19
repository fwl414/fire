"""AI 结果人工复核

背景：AI 巡检链路此前会把模型结论直接落库并自动生成整改工单。云端模型未生效时
`image_analyzer` 会走本地兜底甚至返回硬编码隐患，这类低可信结果同样会触发工单。

本服务在「AI 结论 → 自动下发工单」之间加一道人工闸门：
- 置信度低（云端模型未生效或调用失败）时，必须人工确认
- 置信度中（仅单一模态由云端模型产出）时，需人工确认
- 高风险/严重风险结论，即使置信度高也要人工确认后再下发

巡检记录本身仍照常落库（作为证据与追溯），仅暂缓工单下发。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import AiReviewTask, FaultTicket
from services import metrics_service

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

CONFIDENCE_LABELS = {
    CONFIDENCE_HIGH: "高",
    CONFIDENCE_MEDIUM: "中",
    CONFIDENCE_LOW: "低",
}

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

HIGH_RISK_LEVELS = frozenset({"高风险", "严重风险"})

EVENT_CREATED = "ai_review_created"
EVENT_APPROVED = "ai_review_approved"
EVENT_REJECTED = "ai_review_rejected"


def assess_confidence(
    *,
    used_vision_api: bool = False,
    used_text_model_api: bool = False,
    vision_error: str = "",
    text_model_error: str = "",
    requested_modalities: int = 2,
) -> str:
    """按云端模型是否真正生效判定 AI 结论可信度。

    `requested_modalities` 表示该链路本来期望有几个模态走云端：
    巡检链路同时有文本与视觉（默认 2），视频抓拍识别只有视觉（传 1）。
    """
    if vision_error or text_model_error:
        return CONFIDENCE_LOW
    signals = int(bool(used_vision_api)) + int(bool(used_text_model_api))
    if signals == 0:
        return CONFIDENCE_LOW
    if signals < max(1, requested_modalities):
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_HIGH


def needs_manual_review(*, risk_level: str, confidence: str) -> Tuple[bool, str]:
    """返回 (是否需要人工复核, 原因)。"""
    if confidence == CONFIDENCE_LOW:
        return True, "AI 结果置信度低：云端模型未生效或调用失败"
    if confidence == CONFIDENCE_MEDIUM:
        return True, "AI 结果仅单一模态由云端模型产出，需人工确认"
    if risk_level in HIGH_RISK_LEVELS:
        return True, f"{risk_level}结论需人工确认后再下发工单"
    return False, ""


def _load_hazards(raw: str) -> List[str]:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(item) for item in data] if isinstance(data, list) else []


def create_review_task(
    db: Session,
    *,
    tenant_id: Optional[int],
    source: str,
    record_id: Optional[int],
    risk_level: str,
    risk_score: int,
    hazards: List[str],
    confidence: str,
    reason: str,
    ai_summary: str = "",
    location: str = "",
) -> AiReviewTask:
    """落一条待复核任务。"""
    task = AiReviewTask(
        tenant_id=tenant_id,
        source=source,
        record_id=record_id,
        risk_level=risk_level or "",
        risk_score=int(risk_score or 0),
        hazards=json.dumps(list(hazards or []), ensure_ascii=False),
        confidence=confidence,
        reason=reason[:255],
        ai_summary=ai_summary or "",
        location=location or "",
        status=STATUS_PENDING,
    )
    db.add(task)
    db.flush()
    metrics_service.incr(EVENT_CREATED)
    return task


def serialize_task(task: AiReviewTask) -> Dict[str, Any]:
    return {
        "id": task.id,
        "source": task.source,
        "record_id": task.record_id,
        "risk_level": task.risk_level,
        "risk_score": task.risk_score or 0,
        "hazards": _load_hazards(task.hazards),
        "confidence": task.confidence,
        "confidence_label": CONFIDENCE_LABELS.get(task.confidence, task.confidence),
        "reason": task.reason or "",
        "ai_summary": task.ai_summary or "",
        "location": task.location or "",
        "status": task.status,
        "ticket_id": task.ticket_id,
        "reviewer_name": task.reviewer_name or "",
        "review_note": task.review_note or "",
        "reviewed_at": task.reviewed_at.isoformat() if task.reviewed_at else "",
        "created_at": task.created_at.isoformat() if task.created_at else "",
    }


def list_review_tasks(
    db: Session,
    tenant_id: Optional[int],
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    query = db.query(AiReviewTask).filter(AiReviewTask.tenant_id == tenant_id)
    if status:
        query = query.filter(AiReviewTask.status == status)
    rows = (
        query.order_by(AiReviewTask.created_at.desc(), AiReviewTask.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [serialize_task(row) for row in rows]


def review_summary(db: Session, tenant_id: Optional[int]) -> Dict[str, Any]:
    rows = (
        db.query(AiReviewTask.status, func.count(AiReviewTask.id))
        .filter(AiReviewTask.tenant_id == tenant_id)
        .group_by(AiReviewTask.status)
        .all()
    )
    counts = {row[0] or "unknown": int(row[1]) for row in rows}
    return {
        "pending": counts.get(STATUS_PENDING, 0),
        "approved": counts.get(STATUS_APPROVED, 0),
        "rejected": counts.get(STATUS_REJECTED, 0),
        "total": sum(counts.values()),
        "by_status": counts,
    }


def pending_count(tenant_id: Optional[int] = None) -> int:
    """供 /metrics 使用；失败降级为 0。"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        query = db.query(func.count(AiReviewTask.id)).filter(
            AiReviewTask.status == STATUS_PENDING
        )
        if tenant_id is not None:
            query = query.filter(AiReviewTask.tenant_id == tenant_id)
        return int(query.scalar() or 0)
    except Exception:
        return 0
    finally:
        db.close()


def get_task(db: Session, task_id: int, tenant_id: Optional[int]) -> Optional[AiReviewTask]:
    return db.query(AiReviewTask).filter(
        AiReviewTask.id == task_id,
        AiReviewTask.tenant_id == tenant_id,
    ).first()


def _stamp(task: AiReviewTask, reviewer, note: str) -> None:
    task.reviewer_id = getattr(reviewer, "id", None)
    task.reviewer_name = getattr(reviewer, "username", "") or ""
    task.review_note = note or ""
    task.reviewed_at = datetime.utcnow()


def approve_task(db: Session, task: AiReviewTask, reviewer, note: str = "") -> Dict[str, Any]:
    """复核通过：此时才生成整改工单。"""
    if task.status != STATUS_PENDING:
        raise ValueError(f"该复核任务已处理（当前状态：{task.status}）")

    hazards = _load_hazards(task.hazards)
    now = datetime.utcnow()
    ticket = FaultTicket(
        tenant_id=task.tenant_id,
        record_id=task.record_id,
        title=f"{task.risk_level or '消防隐患'}整改工单",
        description=(
            f"隐患：{'、'.join(hazards) or '未提取到明确隐患'}\n\n"
            f"AI 结论（置信度 {CONFIDENCE_LABELS.get(task.confidence, task.confidence)}）："
            f"{task.ai_summary or '无'}\n\n人工复核意见：{note or '无'}"
        ),
        risk_level=task.risk_level or "",
        status="待受理",
        source="AI复核",
        location=task.location or "",
        reporter_id=getattr(reviewer, "id", None),
        reporter_name=getattr(reviewer, "username", "") or "",
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.flush()

    task.status = STATUS_APPROVED
    task.ticket_id = ticket.id
    _stamp(task, reviewer, note)
    db.commit()
    db.refresh(task)
    metrics_service.incr(EVENT_APPROVED)
    return {"task": serialize_task(task), "ticket_id": ticket.id}


def reject_task(db: Session, task: AiReviewTask, reviewer, note: str = "") -> Dict[str, Any]:
    """复核驳回：不生成工单，仅留痕。"""
    if task.status != STATUS_PENDING:
        raise ValueError(f"该复核任务已处理（当前状态：{task.status}）")

    task.status = STATUS_REJECTED
    _stamp(task, reviewer, note)
    db.commit()
    db.refresh(task)
    metrics_service.incr(EVENT_REJECTED)
    return {"task": serialize_task(task), "ticket_id": None}
