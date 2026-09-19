from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from services.hardware_event_service import create_hardware_event, update_hardware_event_status
from services.workorder_service import generate_workorders_from_inspection, build_inspection_report
from services.record_persistence_service import save_inspection_record
from services.runtime_db import connect_runtime_db

DEMO_SECRET = "fire-v12-demo"


def _check(secret: str):
    if secret != DEMO_SECRET:
        return {"ok": False, "message": "隐藏口令不正确"}
    return {"ok": True}


def generate_closed_loop_demo(secret: str) -> Dict[str, Any]:
    check = _check(secret)
    if not check["ok"]:
        return check
    now = datetime.now()
    event = create_hardware_event({
        "id": f"DEMO-EVT-{now.strftime('%Y%m%d%H%M%S')}",
        "event_type": "smoke_alarm",
        "location": "演示楼机房B区",
        "device_id": "DEMO-SMK-001",
        "device_name": "演示烟感传感器",
        "description": "烟感报警并伴随机房通道堆物，疑似影响应急处置。",
        "risk_level": "高风险",
        "risk_score": 86,
        "status": "处理中",
    })
    hazards = ["烟雾", "消防通道堵塞", "可燃物堆积"]
    work = generate_workorders_from_inspection({
        "inspection_id": f"DEMO-REC-{now.strftime('%Y%m%d%H%M%S')}",
        "location": "演示楼机房B区",
        "hazards": hazards,
        "risk_level": "高风险",
        "risk_score": 86,
    })
    orders = work.get("orders", [])
    if orders:
        orders[0]["deadline"] = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        orders[0]["status"] = "整改中"
    if len(orders) > 1:
        orders[1]["deadline"] = (now + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        orders[1]["status"] = "待复查"
    if len(orders) > 2:
        orders[2]["status"] = "已闭环"
    report = build_inspection_report({"location": "演示楼机房B区", "hazards": hazards, "risk_level": "高风险", "risk_score": 86, "workorders": orders})
    record = save_inspection_record({
        "id": work.get("inspection_id"),
        "location": "演示楼机房B区",
        "description": "隐藏演示闭环：硬件烟感报警触发 Agent 分析，生成巡检档案和整改工单。",
        "hazards": hazards,
        "risk_level": "高风险",
        "risk_score": 86,
        "result": {
            "demo": True,
            "source_hardware_event_id": event.get("id"),
            "rag_reference_cards": [
                {"title": "初期火灾处置", "category": "应急处置", "similarity": 92, "summary": "烟感报警应先现场核查并按预案处置。"},
                {"title": "消防通道管理", "category": "疏散通道", "similarity": 89, "summary": "疏散通道应保持畅通，不得堆放杂物。"},
            ],
            "image_evidence_cards": [{"id": "DEMO-IMG-001", "title": "演示图片证据", "hazard_tags": hazards, "risk_description": "模拟现场图片证据：机房通道堆物并伴随烟感报警。", "confidence": 0.86, "review_required": True, "include_in_report": True}],
        },
        "workorders": orders,
        "report": report,
        "tags_json": ["DEMO"],
    })
    update_hardware_event_status(event.get("id"), "处理中")
    return {"ok": True, "message": "隐藏演示闭环已生成", "hardware_event": event, "inspection_record": record, "workorders": orders}


def clear_demo_data(secret: str) -> Dict[str, Any]:
    check = _check(secret)
    if not check["ok"]:
        return check
    deleted = {}
    with connect_runtime_db() as conn:
        queries = {
            "work_orders": "DELETE FROM work_orders WHERE id LIKE 'DEMO-%' OR inspection_id LIKE 'DEMO-%' OR raw_json LIKE '%DEMO%'",
            "inspection_reports": "DELETE FROM inspection_reports WHERE id LIKE 'DEMO-%' OR inspection_id LIKE 'DEMO-%' OR report_json LIKE '%DEMO%'",
            "inspection_records": "DELETE FROM inspection_records WHERE id LIKE 'DEMO-%' OR result_json LIKE '%DEMO%' OR description LIKE '%隐藏演示闭环%'",
            "hardware_events": "DELETE FROM hardware_events WHERE id LIKE 'DEMO-%' OR description LIKE '%隐藏演示闭环%' OR device_id LIKE 'DEMO-%'",
        }
        for table, sql in queries.items():
            try:
                cur = conn.execute(sql)
                deleted[table] = cur.rowcount
            except Exception:
                deleted[table] = 0
        conn.commit()
    return {"ok": True, "message": "DEMO 演示数据已清理", "deleted": deleted}
