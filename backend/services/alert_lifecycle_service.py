"""
告警生命周期服务

负责告警的：
1. 去重：同一租户下同一设备/类型/楼栋的重复告警归并到同一条记录，累加重复次数
2. 合并：把多条同类告警人工合并为一条主告警
3. 升级：重复次数超阈值或持续未闭环超时后，自动提升严重度
4. 工单落库：把 Agent 生成的处置工单落到 fault_tickets 并回写 alert.workorder_id
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database import AlertRecord, FaultTicket
from services.alert_notify_service import enqueue_alert_notifications
from services.metrics_service import incr
from services.websocket_service import send_alert_notification

SEVERITY_ORDER = ["low", "medium", "high", "critical"]
OPEN_STATUSES = ("pending", "processing")
MERGED_STATUS = "merged"
RESOLVED_STATUS = "resolved"

# 告警状态 → 界面文案（全系统同一份，避免各页面各写一套）
ALERT_STATUS_LABELS = {
    "pending": "待处置",
    "processing": "处置中",
    "resolved": "已处置",
    "merged": "已合并",
}

# 告警级别 → 界面文案（与状态文案同样全系统统一）
ALERT_SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高",
    "medium": "中",
    "low": "低",
}

# 重复告警归并窗口（分钟）
DEDUP_WINDOW_MINUTES = int(os.environ.get("ALERT_DEDUP_WINDOW_MINUTES", "30"))
# 重复次数达到该值后升级
ESCALATE_REPEAT_THRESHOLD = int(os.environ.get("ALERT_ESCALATE_REPEAT_THRESHOLD", "3"))
# 未闭环超过该时长后升级
ESCALATE_SLA_MINUTES = int(os.environ.get("ALERT_ESCALATE_SLA_MINUTES", "120"))

_PRIORITY_MAP = {
    "紧急": "urgent",
    "高": "high",
    "中": "medium",
    "低": "low",
    "urgent": "urgent",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def severity_index(severity: Optional[str]) -> int:
    try:
        return SEVERITY_ORDER.index((severity or "medium").lower())
    except ValueError:
        return SEVERITY_ORDER.index("medium")


def build_dedup_key(
    tenant_id: Optional[int],
    device_key: Optional[Any],
    alert_type: str,
    building_id: Optional[int] = None,
) -> str:
    """构造告警去重指纹：同一租户 + 同一设备 + 同一告警类型 + 同一楼栋视为同类告警。"""
    parts = [
        "" if tenant_id is None else str(tenant_id),
        str(device_key or ""),
        str(alert_type or ""),
        "" if building_id is None else str(building_id),
    ]
    return ":".join(parts)[:160]


def find_open_alert(db: Session, tenant_id: Optional[int], dedup_key: str) -> Optional[AlertRecord]:
    """查找同类且尚未闭环的告警（含超过归并窗口的老告警，用于识别反复未闭环）。"""
    if not dedup_key:
        return None
    return (
        db.query(AlertRecord)
        .filter(
            AlertRecord.tenant_id == tenant_id,
            AlertRecord.dedup_key == dedup_key,
            AlertRecord.status.in_(OPEN_STATUSES),
        )
        .order_by(AlertRecord.created_at.desc())
        .first()
    )


def escalate_alert(db: Session, alert: AlertRecord, reason: str, levels: int = 1, commit: bool = True) -> AlertRecord:
    """升级告警：提升严重度（封顶 critical）并记录升级原因。"""
    before = alert.severity or "medium"
    target = min(len(SEVERITY_ORDER) - 1, severity_index(before) + max(1, levels))
    alert.severity = SEVERITY_ORDER[target]
    alert.escalated = True
    alert.escalated_at = datetime.utcnow()
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {before} → {alert.severity}：{reason}"
    alert.escalation_reason = f"{alert.escalation_reason}\n{line}".strip() if alert.escalation_reason else line
    alert.updated_at = datetime.utcnow()
    incr("alert_escalated")
    if commit:
        db.commit()
        db.refresh(alert)
    return alert


def _alert_push_payload(alert: AlertRecord) -> Dict[str, Any]:
    """推送用的告警摘要：只带前端展示需要的字段，不整条记录外抛。"""
    return {
        "id": alert.id,
        "alert_code": alert.alert_code,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "status": alert.status,
        "building_name": alert.building_name,
        "location": alert.location,
        "description": alert.description,
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
    }


def ingest_alert(
    db: Session,
    *,
    tenant_id: Optional[int],
    alert_type: str,
    severity: str,
    description: str,
    alert_value: Optional[float] = None,
    alert_unit: str = "",
    device_id: Optional[int] = None,
    device_code: str = "",
    device_name: str = "",
    building_id: Optional[int] = None,
    building_name: str = "",
    location: str = "",
    agent_analysis: str = "",
    device_info: Optional[Dict[str, Any]] = None,
    telemetry_history: Optional[List[Dict[str, Any]]] = None,
    window_minutes: Optional[int] = None,
    repeat_threshold: Optional[int] = None,
) -> Dict[str, Any]:
    """告警入库入口：自动去重与升级。

    返回 {"alert", "action", "escalated", "repeat_count", "merged": bool}
    action 取值 "created"（新建）或 "merged"（归并到已有告警）。
    """
    now = datetime.utcnow()
    window = DEDUP_WINDOW_MINUTES if window_minutes is None else window_minutes
    threshold = ESCALATE_REPEAT_THRESHOLD if repeat_threshold is None else repeat_threshold
    dedup_key = build_dedup_key(tenant_id, device_id or device_code, alert_type, building_id)

    existing = find_open_alert(db, tenant_id, dedup_key)
    if existing:
        existing.repeat_count = (existing.repeat_count or 1) + 1
        existing.last_seen_at = now
        existing.updated_at = now
        if alert_value is not None:
            existing.alert_value = alert_value
        if alert_unit:
            existing.alert_unit = alert_unit
        if agent_analysis:
            existing.agent_analysis = agent_analysis
        if device_info:
            existing.device_info = device_info
        if telemetry_history:
            existing.telemetry_history = telemetry_history

        reasons: List[str] = []
        if existing.repeat_count >= threshold:
            reasons.append(f"同类告警重复 {existing.repeat_count} 次")
        created_at = existing.created_at or now
        if now - created_at > timedelta(minutes=window):
            overdue_minutes = int((now - created_at).total_seconds() // 60)
            reasons.append(f"同类告警持续未闭环 {overdue_minutes} 分钟")

        escalated = False
        if reasons:
            levels = 1 if existing.repeat_count < threshold * 2 else 2
            escalate_alert(db, existing, "；".join(reasons), levels=levels, commit=False)
            escalated = True

        db.commit()
        db.refresh(existing)
        incr("alert_merged")
        # 只在升级时推送：同一告警在归并窗口内可能被高频重复上报，每次归并都推会把大屏刷爆
        if escalated:
            send_alert_notification(tenant_id, _alert_push_payload(existing))
            # 外部通道同理只在升级时补发（升级通常是「一直没处置」，需要真正叫到人）
            enqueue_alert_notifications(db, existing, reason="escalated")
        return {
            "alert": existing,
            "action": "merged",
            "merged": True,
            "escalated": escalated,
            "repeat_count": existing.repeat_count,
        }

    alert = AlertRecord(
        tenant_id=tenant_id,
        alert_code=f"AL-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
        dedup_key=dedup_key,
        device_id=device_id,
        device_code=device_code,
        device_name=device_name or (str(device_id) if device_id else ""),
        building_id=building_id,
        building_name=building_name,
        location=location or building_name,
        alert_type=alert_type,
        alert_value=alert_value or 0.0,
        alert_unit=alert_unit,
        severity=severity,
        status="pending",
        description=description,
        agent_analysis=agent_analysis,
        device_info=device_info or {},
        telemetry_history=telemetry_history or [],
        first_seen_at=now,
        last_seen_at=now,
        repeat_count=1,
        escalated=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    incr("alert_created")
    # 新告警立即推给该租户（大屏收到就刷新，另有 30 秒轮询兜底）
    send_alert_notification(tenant_id, _alert_push_payload(alert))
    # 同一条告警同时投递到已配置的外部通道（邮件 / 群机器人 / Webhook），失败只记日志不影响入库
    enqueue_alert_notifications(db, alert, reason="created")
    return {
        "alert": alert,
        "action": "created",
        "merged": False,
        "escalated": False,
        "repeat_count": 1,
    }


def merge_alerts(
    db: Session,
    tenant_id: Optional[int],
    primary_id: int,
    duplicate_ids: List[int],
) -> Dict[str, Any]:
    """把多条同类告警合并到主告警，被合并记录标记为 merged 并保留回溯指针。"""
    primary = db.query(AlertRecord).filter(
        AlertRecord.id == primary_id,
        AlertRecord.tenant_id == tenant_id,
    ).first()
    if not primary:
        raise ValueError("主告警不存在")

    absorbed: List[int] = []
    now = datetime.utcnow()
    for duplicate_id in duplicate_ids or []:
        if duplicate_id == primary_id:
            continue
        duplicate = db.query(AlertRecord).filter(
            AlertRecord.id == duplicate_id,
            AlertRecord.tenant_id == tenant_id,
        ).first()
        if not duplicate or duplicate.status == MERGED_STATUS:
            continue

        primary.repeat_count = (primary.repeat_count or 1) + (duplicate.repeat_count or 1)
        last_seen = duplicate.last_seen_at or duplicate.created_at
        if last_seen and (primary.last_seen_at is None or last_seen > primary.last_seen_at):
            primary.last_seen_at = last_seen
        if severity_index(duplicate.severity) > severity_index(primary.severity):
            primary.severity = duplicate.severity

        duplicate.status = MERGED_STATUS
        duplicate.merged_into_id = primary.id
        duplicate.updated_at = now
        absorbed.append(duplicate.id)

    primary.updated_at = now
    db.commit()
    db.refresh(primary)
    return {
        "primary_id": primary.id,
        "repeat_count": primary.repeat_count,
        "severity": primary.severity,
        "merged_ids": absorbed,
        "merged_count": len(absorbed),
    }


def escalate_overdue_alerts(
    db: Session,
    tenant_id: Optional[int],
    sla_minutes: Optional[int] = None,
) -> Dict[str, Any]:
    """把持续未闭环且未升级过的告警批量升级。"""
    sla = ESCALATE_SLA_MINUTES if sla_minutes is None else sla_minutes
    cutoff = datetime.utcnow() - timedelta(minutes=sla)
    rows = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.status.in_(OPEN_STATUSES),
        AlertRecord.created_at < cutoff,
        AlertRecord.escalated == False,  # noqa: E712 - SQLAlchemy 需要显式比较
    ).all()

    escalated = []
    for alert in rows:
        escalate_alert(db, alert, f"超过 {sla} 分钟未闭环", levels=1, commit=False)
        escalated.append({
            "id": alert.id,
            "alert_code": alert.alert_code,
            "severity": alert.severity,
            "repeat_count": alert.repeat_count,
        })
    db.commit()
    return {"sla_minutes": sla, "escalated_count": len(escalated), "items": escalated}


def alert_priority(workorder: Optional[Dict[str, Any]], fallback: str = "medium") -> str:
    """把告警档案里的中文优先级映射为工单优先级枚举。"""
    raw = (workorder or {}).get("priority") or fallback
    return _PRIORITY_MAP.get(str(raw), str(raw) or fallback)


def _parse_deadline(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def persist_alert_workorder(
    db: Session,
    *,
    tenant_id: Optional[int],
    alert: AlertRecord,
    workorder: Optional[Dict[str, Any]],
    reporter_id: Optional[int] = None,
    reporter_name: str = "",
) -> Optional[FaultTicket]:
    """把 Agent 生成的处置工单落到工件表，并回写 alert.workorder_id。

    同一告警的重复发生不重复建单，而是同步最新严重度/优先级并累加备注。
    """
    if not workorder:
        return None

    now = datetime.utcnow()
    existing = None
    if alert.workorder_id:
        existing = db.query(FaultTicket).filter(
            FaultTicket.id == alert.workorder_id,
            FaultTicket.tenant_id == tenant_id,
        ).first()

    if existing:
        existing.risk_level = workorder.get("risk_level") or existing.risk_level
        existing.priority = alert_priority(workorder, existing.priority or "medium")
        existing.updated_at = now
        note = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 同类告警重复至 {alert.repeat_count or 1} 次，当前严重度 {alert.severity}"
        existing.remark = f"{existing.remark}\n{note}".strip() if existing.remark else note
        db.commit()
        db.refresh(existing)
        return existing

    ticket = FaultTicket(
        tenant_id=tenant_id,
        device_id=alert.device_id,
        building_id=alert.building_id,
        building_name=alert.building_name or "",
        title=workorder.get("title") or f"{alert.location or alert.building_name}-{alert.description}处置工单",
        description=workorder.get("recommended_action") or alert.description or "",
        risk_level=workorder.get("risk_level") or "",
        priority=alert_priority(workorder),
        ticket_type="设备告警",
        status="待受理",
        reporter_id=reporter_id,
        reporter_name=reporter_name,
        location=alert.location or "",
        deadline=_parse_deadline(workorder.get("deadline")) or (now + timedelta(hours=24)),
        source="设备告警",
        remark=(
            f"来源告警 {alert.alert_code}（{alert.alert_type} / 严重度 {alert.severity}）\n"
            f"责任角色：{workorder.get('responsible_role', '区域安全责任人')}"
        ),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    incr("workorder_created")

    alert.workorder_id = ticket.id
    alert.updated_at = now
    db.commit()
    db.refresh(alert)
    return ticket


def alert_state_payload(alert: AlertRecord) -> Dict[str, Any]:
    """告警生命周期状态，供 API 响应复用。"""
    return {
        "dedup_key": alert.dedup_key or "",
        "first_seen_at": alert.first_seen_at.isoformat() if alert.first_seen_at else "",
        "last_seen_at": alert.last_seen_at.isoformat() if alert.last_seen_at else "",
        "repeat_count": alert.repeat_count or 1,
        "merged_into_id": alert.merged_into_id,
        "escalated": bool(alert.escalated),
        "escalated_at": alert.escalated_at.isoformat() if alert.escalated_at else "",
        "escalation_reason": alert.escalation_reason or "",
        "workorder_id": alert.workorder_id,
    }
