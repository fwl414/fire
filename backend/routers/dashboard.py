from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db, Device, InspectionRecord, FaultTicket, ModelConfig

from services.health_service import get_system_health
from services.model_registry import serialize_config, get_active_config



from services.business_crud_service import (
    list_inspection_records as crud_list_inspections,
    list_workorders as crud_list_workorders,
)
from services.hardware_event_service import list_hardware_events
from services.auth_service import get_current_user, get_current_tenant_id

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["仪表盘"])

@router.get("/api/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    total_devices = db.query(Device).filter(Device.tenant_id == tenant_id).count()
    total_records = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id).count()
    high_risk = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id, InspectionRecord.risk_level == "高风险").count()
    severe_risk = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id, InspectionRecord.risk_level == "严重风险").count()
    pending_faults = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id, FaultTicket.status != "已完成").count()

    risk_levels = ["低风险", "中风险", "高风险", "严重风险"]
    risk_stats = {level: db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id, InspectionRecord.risk_level == level).count() for level in risk_levels}

    recent = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id).order_by(InspectionRecord.created_at.desc()).limit(5).all()
    active_text = get_active_config(db, "text")
    active_vision = get_active_config(db, "vision")

    return {
        "total_devices": total_devices,
        "total_records": total_records,
        "high_risk": high_risk,
        "severe_risk": severe_risk,
        "pending_faults": pending_faults,
        "risk_stats": risk_stats,
        "active_text_model": serialize_config(active_text) if active_text else None,
        "active_vision_model": serialize_config(active_vision) if active_vision else None,
        "recent_records": [
            {
                "id": r.id,
                "device_name": r.device_name,
                "location": r.location,
                "risk_score": r.risk_score,
                "risk_level": r.risk_level,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in recent
        ],
    }


@router.get("/api/dashboard/trends")
def dashboard_trends(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    rows = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id).order_by(InspectionRecord.created_at.asc()).all()
    by_date = {}
    hazard_counter = {}
    for r in rows:
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
        by_date.setdefault(day, {"date": day, "count": 0, "max_score": 0, "high_count": 0})
        by_date[day]["count"] += 1
        by_date[day]["max_score"] = max(by_date[day]["max_score"], r.risk_score or 0)
        if r.risk_level in ["高风险", "严重风险"]:
            by_date[day]["high_count"] += 1
        try:
            hazards = json.loads(r.hazards or "[]")
        except Exception:
            hazards = []
        for h in hazards:
            hazard_counter[h] = hazard_counter.get(h, 0) + 1

    top_hazards = [
        {"name": name, "count": count}
        for name, count in sorted(hazard_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    return {
        "trend": list(by_date.values()),
        "top_hazards": top_hazards,
    }


@router.get("/api/system/check")
def system_check(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    device_count = db.query(Device).filter(Device.tenant_id == tenant_id).count()
    record_count = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id).count()
    ticket_count = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id).count()
    text_cfg = db.query(ModelConfig).filter(ModelConfig.enabled == True, ModelConfig.text_model != "").first()
    vision_cfg = db.query(ModelConfig).filter(ModelConfig.enabled == True, ModelConfig.vision_model != "").first()

    checks = [
        {"name": "Backend API", "status": "ok", "message": "FastAPI is running."},
        {"name": "Database", "status": "ok", "message": f"Devices: {device_count}, Records: {record_count}, Tickets: {ticket_count}."},
        {"name": "Text LLM", "status": "ok" if text_cfg else "warning", "message": "Text model is enabled." if text_cfg else "Text model is not enabled."},
        {"name": "Vision LLM", "status": "ok" if vision_cfg else "warning", "message": "Vision model is enabled." if vision_cfg else "Vision model is not enabled. Image recognition will be downgraded."},
    ]
    return {
        "status": "ok",
        "version": "v1.0.0",
        "checks": checks,
        "suggestion": "Run /api/demo/seed if dashboard has no demo records."
    }


@router.get("/api/system/health")
def api_system_health(tenant_id: int = Depends(get_current_tenant_id)):
    return get_system_health(tenant_id=tenant_id)


@router.get("/api/system/core-check")
def api_system_core_check(request: Request, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    """V1.0.0 演示和运行验收的轻量级自检。"""
    route_paths = {getattr(route, "path", "") for route in request.app.routes}
    expected = [
        ("首页总览", "GET", "/api/product/dashboard-metrics"),
        ("智能巡检", "POST", "/api/inspection/analyze"),
        ("巡检任务", "POST", "/api/inspection/tasks"),
        ("Agent步骤", "GET", "/api/inspection/agent-steps"),
        ("巡检记录", "GET", "/api/inspection-records"),
        ("记录统计", "GET", "/api/inspection-records-dashboard"),
        ("整改工单", "GET", "/api/workorders"),
        ("设备档案", "GET", "/api/devices"),
        ("设备遥测", "GET", "/api/device-telemetry"),
        ("消防问答", "POST", "/api/qa/fire"),
        ("RAG知识库", "GET", "/api/rag/admin/stats"),
        ("知识库管理", "GET", "/api/knowledge"),
        ("知识分类", "GET", "/api/rag/categories"),
        ("学习题库", "GET", "/api/learning/quiz"),
        ("硬件事件", "GET", "/api/hardware/events"),
        ("系统健康", "GET", "/api/system/health"),
        ("演示数据", "POST", "/api/demo/seed-all"),
        ("巡检档案", "GET", "/api/inspection-archives"),
        ("档案统计", "GET", "/api/inspection-archives/dashboard"),
        ("报告模板", "GET", "/api/reports/templates"),
    ]
    interfaces = [
        {"module": module, "method": method, "path": path, "status": "可访问" if path in route_paths else "不可访问"}
        for module, method, path in expected
    ]
    try:
        records = crud_list_inspections(db, tenant_id, page_size=500).get("items", [])
        orders = crud_list_workorders(db, tenant_id, page_size=500).get("items", [])
        hw_events = list_hardware_events(limit=500, db=db, tenant_id=tenant_id)
    except Exception:
        records, orders, hw_events = [], [], []
    page_routes = [
        "/dashboard", "/inspection", "/records", "/faults", "/workorders", "/devices", "/device-data",
        "/qa", "/learning", "/learning-app", "/knowledge", "/evaluation", "/agent-lab", "/settings", "/hardware", "/system-health"
    ]
    closed = len([o for o in orders if o.get("status") == "已闭环"])
    return {
        "version": "V1.0.0",
        "interfaces": interfaces,
        "summary": {
            "api_routes": len([p for p in route_paths if p.startswith("/api")]),
            "page_routes": len(page_routes),
            "records": len(records),
            "workorders": len(orders),
            "hardware_events": len(hw_events),
            "closed_workorders": closed,
            "closed_loop": "巡检 → 巡检档案 → 报告 → 整改工单 → 复查 → Dashboard统计。" if records and orders else "暂无数据，可点击生成演示数据。",
        },
    }

