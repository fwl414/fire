from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Floor, Building, Device, User
from services.auth_service import get_current_user, get_current_tenant_id, require_permission
from services.common_utils import IMAGE_EXTENSIONS, read_validated_upload
from services.upload_archive_service import find_upload, save_upload

router = APIRouter(dependencies=[Depends(get_current_user)])

# 旧版本把平面图放在可匿名访问的 static/floor_plans 下，迁移时按需登记
LEGACY_FLOOR_PLANS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "floor_plans"
)


def floor_plan_url(db: Session, tenant_id: int, floor: Floor) -> str:
    """返回受控下载地址；历史 static 路径会在首次读取时就地登记迁移。"""
    stored = floor.floor_plan_image or ""
    if not stored:
        return ""
    if stored.startswith("/api/files/"):
        return stored
    if stored.startswith("/static/floor_plans/"):
        filename = os.path.basename(stored)
        existing = find_upload(db, tenant_id, "floor_plan", filename)
        if existing:
            return f"/api/files/{existing.id}"
        legacy_path = os.path.join(LEGACY_FLOOR_PLANS_DIR, filename)
        if os.path.isfile(legacy_path):
            with open(legacy_path, "rb") as handle:
                content = handle.read()
            record = save_upload(
                db,
                tenant_id=tenant_id,
                category="floor_plan",
                content=content,
                ext=os.path.splitext(filename)[1].lower() or ".jpg",
                media_type="image/jpeg",
                original_name=filename,
                filename=filename,
            )
            return f"/api/files/{record.id}"
        return ""
    return stored


class FloorCreate(BaseModel):
    building_id: int
    floor_name: str
    floor_number: int = 1
    description: str = ""


class FloorUpdate(BaseModel):
    floor_name: Optional[str] = None
    floor_number: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


class DevicePositionUpdate(BaseModel):
    floor_x: float = 0.0
    floor_y: float = 0.0
    floor_id: Optional[int] = None


@router.get("/api/floors")
def list_floors(
    building_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building = db.query(Building).filter(Building.id == building_id, Building.tenant_id == tenant_id).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    rows = db.query(Floor).filter(Floor.building_id == building_id, Floor.tenant_id == tenant_id).order_by(Floor.floor_number.asc()).all()
    return [
        {
            "id": f.id,
            "building_id": f.building_id,
            "floor_name": f.floor_name,
            "floor_number": f.floor_number,
            "floor_plan_image": floor_plan_url(db, tenant_id, f),
            "description": f.description,
            "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else "",
        }
        for f in rows
    ]


@router.get("/api/floors/{floor_id}")
def get_floor_detail(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    devices = db.query(Device).filter(Device.floor_id == floor_id, Device.tenant_id == tenant_id).all()
    device_list = [
        {
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "location": d.location,
            "status": d.status,
            "floor_x": d.floor_x,
            "floor_y": d.floor_y,
            "floor_id": d.floor_id,
            "building_id": d.building_id,
        }
        for d in devices
    ]

    return {
        "id": floor.id,
        "building_id": floor.building_id,
        "floor_name": floor.floor_name,
        "floor_number": floor.floor_number,
        "floor_plan_image": floor_plan_url(db, tenant_id, floor),
        "description": floor.description,
        "status": floor.status,
        "created_at": floor.created_at.isoformat() if floor.created_at else "",
        "devices": device_list,
    }


@router.post("/api/floors")
def create_floor(
    payload: FloorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building = db.query(Building).filter(Building.id == payload.building_id, Building.tenant_id == tenant_id).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    existing = db.query(Floor).filter(
        Floor.building_id == payload.building_id,
        Floor.floor_number == payload.floor_number,
        Floor.tenant_id == tenant_id
    ).first()
    if existing:
        return JSONResponse(status_code=400, content={"message": "该楼层号已存在"})

    floor = Floor(
        tenant_id=tenant_id,
        building_id=payload.building_id,
        floor_name=payload.floor_name,
        floor_number=payload.floor_number,
        description=payload.description,
    )
    db.add(floor)
    db.commit()
    db.refresh(floor)

    return {
        "message": "created",
        "floor": {
            "id": floor.id,
            "building_id": floor.building_id,
            "floor_name": floor.floor_name,
            "floor_number": floor.floor_number,
        }
    }


@router.put("/api/floors/{floor_id}")
def update_floor(
    floor_id: int,
    payload: FloorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    update_data = payload.model_dump(exclude_none=True)
    if "floor_number" in update_data:
        existing = db.query(Floor).filter(
            Floor.building_id == floor.building_id,
            Floor.floor_number == update_data["floor_number"],
            Floor.id != floor_id,
            Floor.tenant_id == tenant_id
        ).first()
        if existing:
            return JSONResponse(status_code=400, content={"message": "该楼层号已存在"})

    for key, value in update_data.items():
        setattr(floor, key, value)
    floor.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "updated"}


@router.delete("/api/floors/{floor_id}")
def delete_floor(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    devices = db.query(Device).filter(Device.floor_id == floor_id, Device.tenant_id == tenant_id).all()
    for d in devices:
        d.floor_id = None
        d.floor_x = 0.0
        d.floor_y = 0.0

    db.delete(floor)
    db.commit()

    return {"message": "deleted"}


@router.post("/api/floors/{floor_id}/plan")
async def upload_floor_plan(
    floor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    content, ext = await read_validated_upload(file, IMAGE_EXTENSIONS, label="楼层平面图")

    record = save_upload(
        db,
        tenant_id=tenant_id,
        category="floor_plan",
        content=content,
        ext=ext,
        media_type="image/jpeg",
        original_name=file.filename or "",
        owner_id=current_user.id,
        owner_name=current_user.real_name or current_user.username,
    )

    image_url = f"/api/files/{record.id}"
    floor.floor_plan_image = image_url
    floor.updated_at = datetime.utcnow()
    db.commit()

    return {
        "message": "uploaded",
        "image_url": image_url,
        "file_id": record.id,
    }


@router.post("/api/devices/{device_id}/position")
def update_device_position(
    device_id: int,
    payload: DevicePositionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == tenant_id).first()
    if not device:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})

    if payload.floor_id is not None:
        floor = db.query(Floor).filter(Floor.id == payload.floor_id, Floor.tenant_id == tenant_id).first()
        if not floor:
            return JSONResponse(status_code=404, content={"message": "楼层不存在"})
        device.floor_id = payload.floor_id
        device.building_id = floor.building_id

    device.floor_x = payload.floor_x
    device.floor_y = payload.floor_y

    db.commit()

    return {"message": "updated"}
