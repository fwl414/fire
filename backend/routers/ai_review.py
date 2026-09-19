"""AI 结果人工复核接口

低可信或高风险的 AI 巡检结论不再自动下发工单，而是进入待复核队列，
由人工确认（通过 / 驳回）后才生成整改工单。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import User, get_db
from services import ai_review_service
from services.auth_service import get_current_user, require_permission

router = APIRouter(tags=["AI复核"])


@router.get("/api/ai-review/tasks")
def api_list_review_tasks(
    status: Optional[str] = Query(None, description="pending / approved / rejected"),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "items": ai_review_service.list_review_tasks(
            db, current_user.tenant_id, status=status, limit=limit
        )
    }


@router.get("/api/ai-review/summary")
def api_review_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ai_review_service.review_summary(db, current_user.tenant_id)


@router.post("/api/ai-review/tasks/{task_id}/approve")
def api_approve_review_task(
    task_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:create")),
):
    """复核通过：此时才生成整改工单。"""
    task = ai_review_service.get_task(db, task_id, current_user.tenant_id)
    if not task:
        raise HTTPException(status_code=404, detail="复核任务不存在")
    try:
        return ai_review_service.approve_task(db, task, current_user, payload.get("note", ""))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/api/ai-review/tasks/{task_id}/reject")
def api_reject_review_task(
    task_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    """复核驳回：不生成工单，仅留痕。"""
    task = ai_review_service.get_task(db, task_id, current_user.tenant_id)
    if not task:
        raise HTTPException(status_code=404, detail="复核任务不存在")
    try:
        return ai_review_service.reject_task(db, task, current_user, payload.get("note", ""))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
