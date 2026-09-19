from __future__ import annotations

import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy import or_, and_

from database import get_db, Building, Device, DeviceTelemetry, User
from schemas import DeviceCreate, DeviceUpdate, TelemetryCreate
from services.auth_service import get_current_tenant_id, get_current_user, require_permission
from services.telemetry_analyzer import (
    analyze_telemetry_single,
    analyze_telemetry_history,
    analyze_multiple_telemetry,
    get_latest_telemetry_by_device_type,
    parse_timestamp_utc,
)

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["消防设备"])


@router.get("/api/devices")
def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    device_type: Optional[str] = None,
    building_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(Device).filter(Device.tenant_id == tenant_id)
    
    if keyword:
        keyword_lower = f"%{keyword.lower()}%"
        query = query.filter(
            or_(
                Device.device_name.ilike(keyword_lower),
                Device.device_code.ilike(keyword_lower),
                Device.location.ilike(keyword_lower),
            )
        )
    
    if device_type:
        query = query.filter(Device.device_type == device_type)
    
    if building_id:
        try:
            building_id_int = int(building_id)
        except (TypeError, ValueError):
            building_id_int = None
        if building_id_int is not None:
            query = query.filter(Device.building_id == building_id_int)
    
    if status:
        query = query.filter(Device.status == status)
    
    total = query.count()
    
    rows = query.order_by(Device.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    items = [
        {
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "location": d.location,
            "status": d.status,
            "building_id": d.building_id,
            "floor_id": d.floor_id,
            "floor_x": d.floor_x,
            "floor_y": d.floor_y,
            "install_date": d.install_date.isoformat() if hasattr(d, 'install_date') and d.install_date else "",
            "last_maintenance": d.last_maintenance.isoformat() if hasattr(d, 'last_maintenance') and d.last_maintenance else "",
            "next_maintenance": d.next_maintenance.isoformat() if hasattr(d, 'next_maintenance') and d.next_maintenance else "",
            "description": d.description if hasattr(d, 'description') else "",
            "last_inspection_time": d.last_inspection_time.isoformat() if d.last_inspection_time else "",
            "created_at": d.created_at.isoformat() if d.created_at else "",
        }
        for d in rows
    ]
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/api/devices")
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    count = db.query(Device).filter(Device.tenant_id == tenant_id).count() + 1
    type_prefix_map = {
        "烟感探测器": "SMK",
        "温感探测器": "HEAT",
        "手动报警按钮": "MAB",
        "消火栓": "HYD",
        "喷淋头": "SPR",
        "防火门": "FDM",
        "灭火器": "EXT",
        "应急照明": "EL",
        "疏散指示": "EI",
        "消防水泵": "FWP",
        "稳压泵": "BST",
        "水流指示器": "WFI",
        "信号蝶阀": "SVD",
        "排烟风机": "EF",
        "防火卷帘": "FSD",
    }
    prefix = type_prefix_map.get(payload.device_type, "DEV")
    code = f"{prefix}-{count:06d}"

    if payload.building_id is not None:
        building = db.query(Building).filter(
            Building.id == payload.building_id,
            Building.tenant_id == tenant_id,
        ).first()
        if not building:
            return JSONResponse(status_code=404, content={"message": "建筑不存在"})
    
    d = Device(
        tenant_id=tenant_id,
        device_code=code,
        device_name=payload.device_name,
        device_type=payload.device_type,
        location=payload.location,
        status=payload.status,
        building_id=payload.building_id,
        floor_id=payload.floor_id,
        floor_x=payload.floor_x,
        floor_y=payload.floor_y,
        description=payload.description,
    )
    
    if payload.install_date:
        d.install_date = datetime.strptime(payload.install_date, "%Y-%m-%d").date()
    if payload.last_maintenance:
        d.last_maintenance = datetime.strptime(payload.last_maintenance, "%Y-%m-%d").date()
    if payload.next_maintenance:
        d.next_maintenance = datetime.strptime(payload.next_maintenance, "%Y-%m-%d").date()
    
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"message": "created", "device": {"id": d.id, "device_code": d.device_code}}


@router.put("/api/devices/{device_id}")
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id,
    ).first()
    if not d:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})
    
    update_data = payload.model_dump(exclude_none=True)

    if "building_id" in update_data:
        building = db.query(Building).filter(
            Building.id == update_data["building_id"],
            Building.tenant_id == tenant_id,
        ).first()
        if not building:
            return JSONResponse(status_code=404, content={"message": "建筑不存在"})
    
    date_fields = ["install_date", "last_maintenance", "next_maintenance"]
    for field in date_fields:
        if field in update_data and update_data[field]:
            update_data[field] = datetime.strptime(update_data[field], "%Y-%m-%d").date()
        elif field in update_data and update_data[field] is None:
            del update_data[field]
    
    for key, value in update_data.items():
        setattr(d, key, value)
    db.commit()
    return {"message": "updated"}


@router.delete("/api/devices/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id,
    ).first()
    if not d:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})
    db.delete(d)
    db.commit()
    return {"message": "deleted"}


@router.get("/api/device-telemetry")
def list_telemetry(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = db.query(DeviceTelemetry).filter(
        DeviceTelemetry.tenant_id == tenant_id,
    ).order_by(DeviceTelemetry.created_at.desc()).limit(100).all()
    result = []
    for t in rows:
        d = db.query(Device).filter(
            Device.id == t.device_id,
            Device.tenant_id == tenant_id,
        ).first()
        result.append({
            "id": t.id,
            "device_id": t.device_id,
            "device_name": d.device_name if d else "",
            "temperature": t.temperature,
            "smoke": t.smoke,
            "co": t.co,
            "battery": t.battery,
            "online": t.online,
            # 2026-09-17 补齐的 4 列：老数据为 null，前端按 null 显示「--」
            "current": t.current,
            "voltage": t.voltage,
            "pressure": t.pressure,
            "remaining_current": t.remaining_current,
            "created_at": t.created_at.isoformat() if t.created_at else "",
        })
    return result


@router.get("/api/telemetry/latest")
def latest_telemetry(
    device_type: str = Query(..., description="设备类型，如「配电箱」「消火栓」"),
    metric: str = Query(..., description="指标键，如 remaining_current / pressure / current / temperature"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """按设备类型取每台设备该指标的最新值，附阈值规则供前端展示。

    设备从未上报该指标时返回 value=null + status=offline（如实告知，不编数）。
    """
    return get_latest_telemetry_by_device_type(
        db,
        tenant_id=tenant_id,
        device_type=device_type,
        metric=metric,
    )


@router.post("/api/device-telemetry")
def create_telemetry(
    payload: TelemetryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    device = db.query(Device).filter(
        Device.id == payload.device_id,
        Device.tenant_id == tenant_id,
    ).first()
    if not device:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})

    row = DeviceTelemetry(
        tenant_id=tenant_id,
        device_id=payload.device_id,
        temperature=payload.temperature,
        smoke=payload.smoke,
        co=payload.co,
        battery=payload.battery,
        online=payload.online,
    )
    db.add(row)
    db.commit()
    return {"message": "created"}


@router.post("/api/telemetry/analyze-single")
def api_analyze_single_telemetry(
    metric_type: str = Form(...),
    value: float = Form(...),
    timestamp: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    # 时间戳是客户端表单字段、格式不受控：统一解析成无时区 UTC，
    # 非法值降级为「未提供」，不再让 fromisoformat 抛 ValueError 变成 500
    ts = parse_timestamp_utc(timestamp)
    return analyze_telemetry_single(metric_type, value, ts)


@router.post("/api/telemetry/analyze-history")
def api_analyze_telemetry_history(
    metric_type: str = Form(...),
    history: str = Form("[]"),
    days: int = Form(3),
    current_user: User = Depends(get_current_user),
):
    try:
        history_data = json.loads(history) if history else []
    except Exception:
        history_data = []
    return analyze_telemetry_history(metric_type, history_data, timedelta(days=days))


@router.post("/api/telemetry/analyze-multiple")
def api_analyze_multiple_telemetry(
    telemetry_data: str = Form("[]"),
    current_user: User = Depends(get_current_user),
):
    try:
        data = json.loads(telemetry_data) if telemetry_data else []
    except Exception:
        data = []
    return analyze_multiple_telemetry(data)
