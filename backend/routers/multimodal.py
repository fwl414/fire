from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.multimodal_agent import MultiModalAgent
from services.telemetry_analyzer import interpret_device_alert



from services.risk_update_service import update_risk_score

from services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["多模态分析"])

@router.post("/api/multimodal/analyze")
async def api_multimodal_analyze(
    description: str = Form(""),
    image_paths: str = Form(""),
    telemetry_data: str = Form("[]"),
    building_info: str = Form("{}"),
    db: Session = Depends(get_db),
):
    agent = MultiModalAgent()
    img_paths = [p.strip() for p in image_paths.split(",") if p.strip()] if image_paths else None
    
    try:
        telemetry = json.loads(telemetry_data) if telemetry_data else []
    except Exception:
        telemetry = []
    
    try:
        building = json.loads(building_info) if building_info else {}
    except Exception:
        building = {}
    
    result = await agent.analyze(
        description=description,
        image_paths=img_paths,
        telemetry_data=telemetry,
        db=db,
        building_info=building
    )
    return result


@router.post("/api/multimodal/interpret-alert")
def api_interpret_device_alert(
    device_id: str = Form(...),
    alert_type: str = Form(...),
    telemetry_history: str = Form("[]"),
):
    try:
        history = json.loads(telemetry_history) if telemetry_history else []
    except Exception:
        history = []
    
    result = interpret_device_alert(device_id, alert_type, history)
    return result


@router.post("/api/multimodal/update-risk")
def api_update_risk_score(
    current_score: int = Form(...),
    improvement_items: str = Form("[]"),
):
    agent = MultiModalAgent()
    try:
        items = json.loads(improvement_items) if improvement_items else []
    except Exception:
        items = []
    
    result = agent.update_risk_score(current_score, items)
    return result


# ---------------- 设备遥测分析 API ----------------


