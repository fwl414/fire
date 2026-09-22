from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.notification_service import (
    build_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)


from services.auth_service import get_current_user, get_current_tenant_id

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["通知消息"])

@router.get("/api/notifications")
def api_notifications(limit: int = 100, tenant_id: int = Depends(get_current_tenant_id)):
    return build_notifications(limit=limit, tenant_id=tenant_id)


@router.get("/api/notifications/summary")
def api_notifications_summary(tenant_id: int = Depends(get_current_tenant_id)):
    return build_notifications(limit=300, tenant_id=tenant_id)["summary"]


@router.post("/api/notifications/mark-all-read")
def api_notifications_mark_all_read(tenant_id: int = Depends(get_current_tenant_id)):
    return mark_all_notifications_read(tenant_id=tenant_id)


@router.post("/api/notifications/{notification_id}/read")
def api_notification_mark_read(notification_id: str):
    return mark_notification_read(notification_id)



