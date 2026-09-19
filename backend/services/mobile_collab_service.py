"""移动端协同服务

移动端不新增业务语义，只是把一线人员在现场最常做的几件事**聚合**出来：

- 概览：待处理告警、待受理工单、我的在办工单、今日巡检数（全部按租户与当前用户真实统计）
- 我的待办：指派给我的工单 + 待处理告警，统一成一种任务项，移动端只渲染一个列表
- 领取工单：把「待受理」的工单指派给自己并推进到「处理中」
- 现场上报：复用巡检 Agent（图片 + 描述 → 隐患识别 → 风险分 → 落巡检记录），见 `routers/mobile.py`

没有数据就返回 0 / 空列表，页面给空态；统计数字不编造。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import AlertRecord, Device, FaultTicket, InspectionRecord, User
from services.alert_lifecycle_service import OPEN_STATUSES
from services.common_utils import local_day_start_utc

# 工单闭环状态（与 routers/workorder.py 的状态机一致）
CLOSED_TICKET_STATUSES = ("已完成", "已关闭", "已闭环")
# 可领取的工单状态：只有「待受理」能被领取；「处理中」说明已经有人在做。
# 「待处理」是历史遗留取值（早期自动建单写的就是它，与「待受理」等价），一并视为可领取，
# 否则老库里的这批工单会既领不了、也不在任何 Tab 里流转。新写入一律用「待受理」。
CLAIMABLE_TICKET_STATUSES = ("待受理", "待处理")
# 高风险等级（用于移动端列表的醒目程度）
HIGH_RISK_LEVELS = ("高风险", "严重风险")

ALERT_STATUS_LABELS = {
    "pending": "待处置",
    "processing": "处置中",
    "resolved": "已处置",
    "merged": "已合并",
}

SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高",
    "medium": "中",
    "low": "低",
    "info": "提示",
}


def _alert_open_clause():
    return AlertRecord.status.in_(OPEN_STATUSES)


def _ticket_open_clause():
    return FaultTicket.status.notin_(CLOSED_TICKET_STATUSES)


def _alert_item(alert: AlertRecord) -> Dict[str, Any]:
    return {
        "type": "alert",
        "id": alert.id,
        "code": alert.alert_code,
        "title": alert.description or alert.alert_type,
        "alertType": alert.alert_type,
        "severity": alert.severity,
        "severityLabel": SEVERITY_LABELS.get(alert.severity, alert.severity or ""),
        "status": alert.status,
        "statusLabel": ALERT_STATUS_LABELS.get(alert.status, alert.status or ""),
        "location": alert.location or alert.building_name or "",
        "buildingName": alert.building_name or "",
        "repeatCount": alert.repeat_count or 1,
        "escalated": bool(alert.escalated),
        "createdAt": alert.created_at.isoformat() if alert.created_at else None,
    }


def _ticket_item(ticket: FaultTicket, current_user_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "type": "workorder",
        "id": ticket.id,
        "code": f"WO-{ticket.id}",
        "title": ticket.title or f"工单#{ticket.id}",
        "status": ticket.status,
        "riskLevel": ticket.risk_level or "",
        "priority": ticket.priority or "",
        "location": ticket.location or ticket.building_name or "",
        "buildingName": ticket.building_name or "",
        "assigneeId": ticket.assignee_id,
        "assigneeName": ticket.assignee_name or "",
        "deadline": ticket.deadline.isoformat() if ticket.deadline else None,
        "createdAt": ticket.created_at.isoformat() if ticket.created_at else None,
        # 只有「待受理」且没人认领时才能领取
        "claimable": (
            ticket.status in CLAIMABLE_TICKET_STATUSES
            and not ticket.assignee_id
        ),
        "mine": bool(current_user_id and ticket.assignee_id == current_user_id),
    }


def home_overview(db: Session, tenant_id: int, current_user: User) -> Dict[str, Any]:
    """移动端首页：真实待办统计 + 最近两屏列表。"""
    today_start = local_day_start_utc(0)

    pending_alerts = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        _alert_open_clause(),
        AlertRecord.merged_into_id.is_(None),
    )
    pending_ticket_query = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == tenant_id,
        FaultTicket.status.in_(CLAIMABLE_TICKET_STATUSES),
    )
    my_ticket_query = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == tenant_id,
        FaultTicket.assignee_id == current_user.id,
        _ticket_open_clause(),
    )

    today_inspections = db.query(InspectionRecord).filter(
        InspectionRecord.tenant_id == tenant_id,
        InspectionRecord.created_at >= today_start,
    ).count()
    today_alerts = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.created_at >= today_start,
    ).count()
    today_devices = db.query(Device).filter(Device.tenant_id == tenant_id).count()

    recent_alerts = pending_alerts.order_by(AlertRecord.created_at.desc()).limit(5).all()
    recent_mine = my_ticket_query.order_by(FaultTicket.created_at.desc()).limit(5).all()
    claimable = pending_ticket_query.order_by(FaultTicket.created_at.desc()).limit(5).all()

    return {
        "user": {
            "id": current_user.id,
            "name": current_user.real_name or current_user.username,
            "role": current_user.role.role_name if current_user.role else "",
        },
        "stats": {
            "pendingAlerts": pending_alerts.count(),
            "claimableWorkorders": pending_ticket_query.count(),
            "myWorkorders": my_ticket_query.count(),
            "todayInspections": today_inspections,
            "todayAlerts": today_alerts,
            "deviceCount": today_devices,
        },
        "pendingAlerts": [_alert_item(alert) for alert in recent_alerts],
        "myWorkorders": [_ticket_item(ticket, current_user.id) for ticket in recent_mine],
        "claimableWorkorders": [_ticket_item(ticket, current_user.id) for ticket in claimable],
        "generatedAt": datetime.utcnow().isoformat(),
    }


def my_tasks(db: Session, tenant_id: int, current_user: User, limit: int = 50) -> Dict[str, Any]:
    """我的待办：指派给我的工单 + 我参与处理的告警，按时间倒序合成一个列表。"""
    tickets = (
        db.query(FaultTicket)
        .filter(
            FaultTicket.tenant_id == tenant_id,
            FaultTicket.assignee_id == current_user.id,
            _ticket_open_clause(),
        )
        .order_by(FaultTicket.created_at.desc())
        .limit(limit)
        .all()
    )
    alerts = (
        db.query(AlertRecord)
        .filter(
            AlertRecord.tenant_id == tenant_id,
            _alert_open_clause(),
            AlertRecord.merged_into_id.is_(None),
        )
        .order_by(AlertRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    items: List[Dict[str, Any]] = [_ticket_item(ticket, current_user.id) for ticket in tickets]
    items += [_alert_item(alert) for alert in alerts]
    items.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return {
        "total": len(items),
        "workorderCount": len(tickets),
        "alertCount": len(alerts),
        "items": items[:limit],
    }


def claim_workorder(
    db: Session, tenant_id: int, current_user: User, order_id: int
) -> Dict[str, Any]:
    """领取工单：指派给自己并推进到「处理中」。

    已经被别人领走的工单不能再领（返回原因，而不是静默覆盖指派）。
    """
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == order_id,
        FaultTicket.tenant_id == tenant_id,
    ).first()
    if not ticket:
        return {"ok": False, "not_found": True, "message": "工单不存在"}

    if ticket.status not in CLAIMABLE_TICKET_STATUSES:
        return {
            "ok": False,
            "message": f"当前状态为「{ticket.status}」，只有"
                       f"{'、'.join(CLAIMABLE_TICKET_STATUSES)}的工单可以领取",
        }
    if ticket.assignee_id and ticket.assignee_id != current_user.id:
        return {
            "ok": False,
            "message": f"该工单已由「{ticket.assignee_name or ticket.assignee_id}」领取",
        }

    ticket.assignee_id = current_user.id
    ticket.assignee_name = current_user.real_name or current_user.username
    ticket.status = "处理中"
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return {
        "ok": True,
        "message": "已领取，工单已进入处理中",
        "workorder": _ticket_item(ticket, current_user.id),
    }
