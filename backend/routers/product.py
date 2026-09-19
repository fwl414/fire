from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.product_metrics_service import get_product_dashboard_metrics, get_page_guides


from services.auth_service import get_current_user, get_current_tenant_id

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["产品管理"])

@router.get("/api/product/dashboard-metrics")
def api_product_dashboard_metrics(tenant_id: int = Depends(get_current_tenant_id)):
    return get_product_dashboard_metrics(tenant_id=tenant_id)


@router.get("/api/product/page-guides")
def api_product_page_guides():
    return get_page_guides()




