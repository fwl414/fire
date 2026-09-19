from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict

from services.record_persistence_service import list_inspection_records, list_workorders
from services.hardware_event_service import list_hardware_events, get_hardware_dashboard
from services.workorder_alert_service import build_todo_alerts, summarize_orders

RISK_COLORS = {"低风险": "#22c55e", "中风险": "#f59e0b", "高风险": "#ef4444", "严重风险": "#7f1d1d", "未评估": "#94a3b8"}


def get_command_center() -> Dict[str, Any]:
    records = list_inspection_records(500)
    orders = list_workorders("", 500)
    hardware = get_hardware_dashboard()
    hw_events = list_hardware_events(limit=6)
    summary = summarize_orders(orders)
    high = len([r for r in records if r.get("risk_level") in ["高风险", "严重风险"]])
    cards = [
        {"label": "巡检档案", "value": len(records), "unit": "条", "desc": "已保存巡检记录", "level": "primary"},
        {"label": "高风险隐患", "value": high, "unit": "项", "desc": "高风险及严重风险", "level": "danger" if high else "success"},
        {"label": "待整改工单", "value": len([o for o in orders if o.get("status") != "已闭环"]), "unit": "条", "desc": "待派单/整改/复查", "level": "warning"},
        {"label": "闭环率", "value": summary.get("closed_loop_rate", 0), "unit": "%", "desc": "整改闭环完成率", "level": "success"},
        {"label": "即将逾期", "value": summary.get("due_soon_count", 0), "unit": "条", "desc": "24小时内到期", "level": "warning"},
        {"label": "已逾期", "value": summary.get("overdue_count", 0), "unit": "条", "desc": "超过整改时限", "level": "danger"},
        {"label": "待复查", "value": summary.get("review_count", 0), "unit": "条", "desc": "整改完成待复核", "level": "warning"},
        {"label": "硬件事件", "value": hardware.get("total", 0), "unit": "条", "desc": "接入事件总数", "level": "primary"},
    ]
    risk_counter = Counter([r.get("risk_level") or "未评估" for r in records])
    risk_distribution = [{"name": k, "value": risk_counter.get(k, 0), "color": RISK_COLORS.get(k, "#94a3b8")} for k in ["低风险", "中风险", "高风险", "严重风险"]]
    status_counts = summary.get("status_counts", {})
    status_distribution = [{"name": k, "value": status_counts.get(k, 0)} for k in ["待派单", "整改中", "待复查", "已闭环"]]
    today = datetime.now().date()
    trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        ds = day.strftime("%Y-%m-%d")
        trend.append({"date": ds, "count": len([r for r in records if str(r.get("created_at", "")).startswith(ds)])})
    hazard_counter = Counter()
    for r in records:
        hazard_counter.update(r.get("hazards", []))
    return {
        "summary_cards": cards,
        "alerts": summary.get("alerts", []),
        "risk_distribution": risk_distribution,
        "status_distribution": status_distribution,
        "trend": trend,
        "top_hazards": [{"name": k, "count": v} for k, v in hazard_counter.most_common(8)],
        "hardware": hardware,
        "latest_hardware_events": hw_events,
    }
