from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.auth_service import get_current_user, require_role

router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_role("admin"))], tags=["租户管理"])

@router.get("/api/tenant/organizations")
def api_tenant_organizations(
    keyword: str = "",
    org_type: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    from services.tenant_service import list_organizations
    return list_organizations(db, keyword=keyword, org_type=org_type, page=page, page_size=page_size)


@router.get("/api/tenant/organizations/tree")
def api_tenant_organization_tree(db: Session = Depends(get_db)):
    from services.tenant_service import get_organization_tree
    return {"tree": get_organization_tree(db)}


@router.get("/api/tenant/organizations/{org_id}")
def api_tenant_organization_detail(org_id: int, db: Session = Depends(get_db)):
    from services.tenant_service import get_organization
    org = get_organization(db, org_id)
    if not org:
        return JSONResponse(status_code=404, content={"message": "组织不存在"})
    return {"org": org}


@router.post("/api/tenant/organizations")
def api_tenant_organization_create(
    org_code: str = Form(...),
    org_name: str = Form(...),
    parent_id: int = Form(0),
    org_type: str = Form("company"),
    address: str = Form(""),
    contact_name: str = Form(""),
    contact_phone: str = Form(""),
    db: Session = Depends(get_db),
):
    from services.tenant_service import create_organization
    result = create_organization(db, org_code=org_code, org_name=org_name,
                                  parent_id=parent_id or None, org_type=org_type,
                                  address=address, contact_name=contact_name, contact_phone=contact_phone)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/tenant/organizations/{org_id}")
def api_tenant_organization_update(
    org_id: int,
    org_name: str = Form(None),
    parent_id: int = Form(None),
    org_type: str = Form(None),
    address: str = Form(None),
    contact_name: str = Form(None),
    contact_phone: str = Form(None),
    status: str = Form(None),
    db: Session = Depends(get_db),
):
    from services.tenant_service import update_organization
    result = update_organization(db, org_id, org_name=org_name, parent_id=parent_id,
                                  org_type=org_type, address=address,
                                  contact_name=contact_name, contact_phone=contact_phone, status=status)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/api/tenant/organizations/{org_id}")
def api_tenant_organization_delete(org_id: int, db: Session = Depends(get_db)):
    from services.tenant_service import delete_organization
    result = delete_organization(db, org_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/api/tenant/organizations/{org_id}/buildings")
def api_tenant_org_buildings(org_id: int, db: Session = Depends(get_db)):
    from services.tenant_service import get_org_buildings
    return {"buildings": get_org_buildings(db, org_id)}



