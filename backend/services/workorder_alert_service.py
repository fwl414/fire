from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List


def parse_deadline(value: str):
    if not value:
        return None
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"]:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    return None


def decorate_workorder(order: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    deadline_dt = parse_deadline(order.get("deadline", ""))
    status = order.get("status", "")
    closed = status == "已闭环"
    remaining_hours = None
    level = "info"
    badge = "正常"
    msg = "请按计划推进整改闭环。"
    if deadline_dt and not closed:
        remaining_hours = round((deadline_dt - now).total_seconds() / 3600, 1)
        if remaining_hours < 0:
            level = "danger"; badge = "已逾期"; msg = f"工单已逾期 {abs(remaining_hours):.1f} 小时，请立即处理并记录原因。"
        elif remaining_hours <= 24:
            level = "warning"; badge = "即将逾期"; msg = f"距离整改时限不足 {remaining_hours:.1f} 小时，请优先推进。"
    if status == "待复查":
        level = "warning"; badge = "待复查"; msg = "整改已提交，需安全管理员复查确认后闭环。"
    if ("高" in str(order.get("risk_level", "")) or "严重" in str(order.get("risk_level", ""))) and not closed:
        if level == "info": level = "danger"; badge = "高风险优先"; msg = "高风险工单应优先处理，避免风险持续暴露。"
    decorated = dict(order)
    decorated.update({
        "remaining_hours": remaining_hours,
        "is_overdue": bool(remaining_hours is not None and remaining_hours < 0 and not closed),
        "is_due_soon": bool(remaining_hours is not None and 0 <= remaining_hours <= 24 and not closed),
        "is_high_priority": bool(("高" in str(order.get("risk_level", "")) or "严重" in str(order.get("risk_level", ""))) and not closed),
        "review_reminder": status == "待复查",
        "reminder_level": level,
        "reminder_badge": badge,
        "reminder_message": msg,
    })
    return decorated


def build_todo_alerts(orders: List[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    alerts = []
    for o in orders:
        d = decorate_workorder(o)
        if d.get("reminder_level") in ["danger", "warning"]:
            alerts.append({
                "id": d.get("id"),
                "type": "workorder",
                "title": d.get("title") or d.get("hazard") or "整改工单",
                "badge": d.get("reminder_badge"),
                "level": d.get("reminder_level"),
                "message": d.get("reminder_message"),
                "location": d.get("location"),
                "deadline": d.get("deadline"),
                "risk_level": d.get("risk_level"),
                "status": d.get("status"),
            })
    score = {"danger": 0, "warning": 1, "info": 2}
    return sorted(alerts, key=lambda x: (score.get(x.get("level"), 9), x.get("deadline") or ""))[:limit]


def summarize_orders(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    enriched = [decorate_workorder(o) for o in orders]
    counter = Counter([o.get("status", "未知") for o in enriched])
    closed = counter.get("已闭环", 0)
    total = len(enriched)
    return {
        "status_counts": dict(counter),
        "closed_loop_rate": round(closed / total * 100, 1) if total else 0,
        "overdue_count": len([o for o in enriched if o.get("is_overdue")]),
        "due_soon_count": len([o for o in enriched if o.get("is_due_soon")]),
        "high_priority_count": len([o for o in enriched if o.get("is_high_priority")]),
        "review_count": len([o for o in enriched if o.get("review_reminder")]),
        "alerts": build_todo_alerts(enriched),
    }
