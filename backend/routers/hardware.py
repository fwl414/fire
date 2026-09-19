from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db


from services.hardware_event_service import (create_hardware_event, get_event_types, get_hardware_dashboard, get_hardware_event, list_hardware_events, update_hardware_event_status)
from services.hardware_gateway import (accept_hardware_event, accept_heartbeat, accept_sensor_report, get_hardware_overview, get_mock_hardware_latest, get_supported_hardware_types, sensor_report_payload_example)

from services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["硬件管理"])

@router.get("/api/hardware/overview")
def api_hardware_overview():
    return get_hardware_overview()


@router.get("/api/hardware/types")
def api_hardware_types():
    return get_supported_hardware_types()


@router.get("/api/hardware/mock/latest")
def api_hardware_mock_latest():
    return get_mock_hardware_latest()


@router.get("/api/hardware/payload-example")
def api_hardware_payload_example():
    return sensor_report_payload_example()


@router.post("/api/hardware/sensor-report")
def api_hardware_sensor_report(payload: Dict[str, Any]):
    return accept_sensor_report(payload)


@router.post("/api/hardware/event-report")
def api_hardware_event_report(payload: Dict[str, Any]):
    return accept_hardware_event(payload)


@router.post("/api/hardware/heartbeat")
def api_hardware_heartbeat(payload: Dict[str, Any]):
    return accept_heartbeat(payload)



@router.get("/api/hardware/event-types")
def api_hardware_event_types():
    return get_event_types()


@router.get("/api/hardware/events")
def api_hardware_events(status: str = "", event_type: str = "", limit: int = 200):
    return list_hardware_events(status=status, event_type=event_type, limit=limit)


@router.post("/api/hardware/events")
def api_hardware_event_create(payload: Dict[str, Any]):
    return create_hardware_event(payload)


@router.get("/api/hardware/events/{event_id}")
def api_hardware_event_get(event_id: str):
    return get_hardware_event(event_id)


@router.post("/api/hardware/events/{event_id}/status")
def api_hardware_event_status(event_id: str, payload: Dict[str, Any]):
    return update_hardware_event_status(event_id, payload.get("status", "处理中"))


@router.get("/api/hardware/events-dashboard")
def api_hardware_event_dashboard():
    return get_hardware_dashboard()


# ---------------- V1.0.0 stable route aliases and core self-check ----------------


