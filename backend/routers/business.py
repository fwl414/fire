from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db


from services.business_crud_service import (add_telemetry, create_alert, create_device as crud_create_device, create_inspection_record, create_workorder, delete_device as crud_delete_device, delete_workorder, get_alert as crud_get_alert, get_alert_statistics as crud_get_alert_statistics, get_device as crud_get_device, get_device_telemetry, get_inspection_record as crud_get_inspection, get_workorder as crud_get_workorder, list_alerts as crud_list_alerts, list_devices as crud_list_devices, list_inspection_records as crud_list_inspections, list_workorders as crud_list_workorders, update_alert, update_device as crud_update_device, update_inspection_record, update_workorder_status as crud_update_workorder_status)

from services.auth_service import get_current_tenant_id, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/api/business/devices")
def api_business_devices(
    keyword: str = "",
    device_type: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return crud_list_devices(db, tenant_id, keyword=keyword, device_type=device_type, status=status, page=page, page_size=page_size)


@router.get("/api/business/devices/{device_id}")
def api_business_device_detail(device_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    device = crud_get_device(db, tenant_id, device_id)
    if not device:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})
    return {"device": device}


@router.post("/api/business/devices")
def api_business_device_create(
    device_code: str = Form(...),
    device_name: str = Form(...),
    device_type: str = Form("灭火器"),
    location: str = Form(""),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = crud_create_device(db, tenant_id, device_code=device_code, device_name=device_name, device_type=device_type, location=location)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/business/devices/{device_id}")
def api_business_device_update(
    device_id: int,
    device_name: str = Form(None),
    device_type: str = Form(None),
    location: str = Form(None),
    status: str = Form(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = crud_update_device(db, tenant_id, device_id, device_name=device_name, device_type=device_type, location=location, status=status)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/api/business/devices/{device_id}")
def api_business_device_delete(device_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = crud_delete_device(db, tenant_id, device_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/api/business/devices/{device_id}/telemetry")
def api_business_device_telemetry(
    device_id: int,
    temperature: float = Form(None),
    smoke: float = Form(None),
    co: float = Form(None),
    battery: float = Form(None),
    online: bool = Form(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = add_telemetry(db, tenant_id, device_id, temperature=temperature, smoke=smoke, co=co, battery=battery, online=online)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/api/business/devices/{device_id}/telemetry")
def api_business_device_telemetry_history(device_id: int, limit: int = 100, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    return get_device_telemetry(db, tenant_id, device_id, limit=limit)


# ===== 巡检记录 =====

@router.get("/api/business/inspections")
def api_business_inspections(
    keyword: str = "",
    device_id: int = None,
    risk_level: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return crud_list_inspections(db, tenant_id, keyword=keyword, device_id=device_id, risk_level=risk_level, page=page, page_size=page_size)


@router.get("/api/business/inspections/{record_id}")
def api_business_inspection_detail(record_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    record = crud_get_inspection(db, tenant_id, record_id)
    if not record:
        return JSONResponse(status_code=404, content={"message": "巡检记录不存在"})
    return {"record": record}


@router.post("/api/business/inspections")
def api_business_inspection_create(payload: Dict[str, Any], db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = create_inspection_record(db, tenant_id, payload)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/business/inspections/{record_id}")
def api_business_inspection_update(record_id: int, payload: Dict[str, Any], db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = update_inspection_record(db, tenant_id, record_id, payload)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


# ===== 工单管理 =====

@router.get("/api/business/workorders")
def api_business_workorders(
    keyword: str = "",
    status: str = "",
    risk_level: str = "",
    device_id: int = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return crud_list_workorders(db, tenant_id, keyword=keyword, status=status, risk_level=risk_level, device_id=device_id, page=page, page_size=page_size)


@router.get("/api/business/workorders/{ticket_id}")
def api_business_workorder_detail(ticket_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    ticket = crud_get_workorder(db, tenant_id, ticket_id)
    if not ticket:
        return JSONResponse(status_code=404, content={"message": "工单不存在"})
    return {"ticket": ticket}


@router.post("/api/business/workorders")
def api_business_workorder_create(payload: Dict[str, Any], db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = create_workorder(db, tenant_id, payload)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/business/workorders/{ticket_id}/status")
def api_business_workorder_update_status(
    ticket_id: int,
    status: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = crud_update_workorder_status(db, tenant_id, ticket_id, status, description=description)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/api/business/workorders/{ticket_id}")
def api_business_workorder_delete(ticket_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = delete_workorder(db, tenant_id, ticket_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


# ===== 告警管理 =====

@router.get("/api/business/alerts")
def api_business_alerts(
    keyword: str = "",
    alert_type: str = "",
    severity: str = "",
    status: str = "",
    device_id: int = None,
    building_id: int = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return crud_list_alerts(db, tenant_id, keyword=keyword, alert_type=alert_type, severity=severity, status=status, device_id=device_id, building_id=building_id, page=page, page_size=page_size)


@router.get("/api/business/alerts/statistics")
def api_business_alert_statistics(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    return crud_get_alert_statistics(db, tenant_id)


@router.get("/api/business/alerts/{alert_id}")
def api_business_alert_detail(alert_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    alert = crud_get_alert(db, tenant_id, alert_id)
    if not alert:
        return JSONResponse(status_code=404, content={"message": "告警记录不存在"})
    return {"alert": alert}


@router.post("/api/business/alerts")
def api_business_alert_create(payload: Dict[str, Any], db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = create_alert(db, tenant_id, payload)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/business/alerts/{alert_id}")
def api_business_alert_update(alert_id: int, payload: Dict[str, Any], db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    result = update_alert(db, tenant_id, alert_id, payload)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


# ===== 建筑管理 =====

@router.post("/api/business/alerts/{alert_id}/notify")
def api_business_alert_notify(alert_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    alert = crud_get_alert(db, tenant_id, alert_id)
    if not alert:
        return JSONResponse(status_code=404, content={"message": "告警不存在"})
    from services.websocket_service import send_alert_notification
    send_alert_notification(tenant_id, alert)
    return {"ok": True, "message": "告警通知已推送"}


@router.post("/api/business/workorders/{ticket_id}/notify")
def api_business_workorder_notify(ticket_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    ticket = crud_get_workorder(db, tenant_id, ticket_id)
    if not ticket:
        return JSONResponse(status_code=404, content={"message": "工单不存在"})
    from services.websocket_service import send_workorder_notification
    send_workorder_notification(tenant_id, ticket)
    return {"ok": True, "message": "工单通知已推送"}
