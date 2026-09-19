from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db


from services.business_crud_service import (get_building as crud_get_building, list_buildings as crud_list_buildings, update_building_risk)

from services.auth_service import get_current_tenant_id, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["建筑管理"])

@router.get("/api/business/buildings")
def api_business_buildings(
    keyword: str = "",
    building_type: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return crud_list_buildings(db, tenant_id, keyword=keyword, building_type=building_type, page=page, page_size=page_size)


@router.get("/api/business/buildings/{building_id}")
def api_business_building_detail(building_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    building = crud_get_building(db, tenant_id, building_id)
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})
    return {"building": building}


@router.post("/api/business/buildings/{building_id}/risk")
def api_business_building_risk(
    building_id: int,
    risk_score: int = Form(...),
    risk_level: str = Form(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = update_building_risk(db, tenant_id, building_id, risk_score, risk_level)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/api/buildings")
def api_buildings_list(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    return crud_list_buildings(db, tenant_id, page=1, page_size=1000).get("items", [])


# ---------------- 多租户组织管理 API ----------------


