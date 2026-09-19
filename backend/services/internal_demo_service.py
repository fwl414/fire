from __future__ import annotations
from datetime import datetime
from typing import Any, Dict
from services.hardware_event_service import create_hardware_event, convert_event_to_inspection, convert_event_to_workorder
from services.record_persistence_service import update_workorder_status, get_inspection_record
HIDDEN_DEMO_SECRET = "fire-v12-demo"

def run_hidden_closed_loop_demo(secret: str = "") -> Dict[str, Any]:
    if secret != HIDDEN_DEMO_SECRET:
        return {"ok": False, "message": "隐藏演示口令不正确"}
    event = create_hardware_event({"event_type":"electrical_alarm","location":"实验室A区配电箱旁","device_id":"ELE-DEMO-001","device_name":"演示电气火灾探测器","risk_level":"高风险","risk_score":86,"description":"探测到插排过载、线路温升异常，现场附近堆放纸箱，可燃物距离配电箱过近。","status":"待处理"})
    inspection = convert_event_to_inspection(event["id"])
    workorder_result = convert_event_to_workorder(event["id"])
    orders = workorder_result.get("orders") or inspection.get("workorders") or []
    progressed=[]
    for idx, order in enumerate(orders):
        if idx == 0:
            progressed.append(update_workorder_status(order["id"], "整改中", "演示系统", "演示流程：责任人已接单并开始整改。"))
            progressed.append(update_workorder_status(order["id"], "待复查", "演示系统", "演示流程：整改完成，等待安全管理员复查。"))
        elif idx == 1:
            progressed.append(update_workorder_status(order["id"], "整改中", "演示系统", "演示流程：责任人已接单。"))
            progressed.append(update_workorder_status(order["id"], "待复查", "演示系统", "演示流程：提交复查。"))
            progressed.append(update_workorder_status(order["id"], "已闭环", "演示系统", "演示流程：复查通过，完成闭环归档。"))
    record = get_inspection_record(inspection.get("record_id") or inspection.get("id", ""))
    return {"ok": True, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "event": event, "inspection": record or inspection, "workorders": progressed or orders, "message": "已生成一条隐藏演示闭环：硬件报警 → Agent分析 → 巡检档案 → 整改工单 → 复查提醒/闭环。", "hidden_path": "/internal/closed-loop-demo"}
