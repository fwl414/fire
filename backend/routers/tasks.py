"""后台任务中心接口

- 列表 / 详情：按租户隔离，提交任务的用户可轮询进度
- 统计 / 取消 / 重试：运维操作，需要 `system:tasks` 权限
- 任务由 `task_worker_service` 在进程内执行，重启后未完成任务会被重新领取
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import User, get_db
from services import task_queue_service as task_queue
from services.auth_service import get_current_user, require_permission
from services.task_worker_service import worker_stats

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["任务中心"])


def _require_task(db: Session, tenant_id: Optional[int], task_id: str):
    task = task_queue.get_task(db, tenant_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/api/tasks/types")
def api_task_types(current_user: User = Depends(get_current_user)):
    """已注册的任务类型，供前端筛选与排查"任务没人执行"的问题。"""
    from services.task_worker_service import ensure_handlers_loaded

    ensure_handlers_loaded()
    return {"items": task_queue.registered_types()}


@router.get("/api/tasks")
def api_list_tasks(
    status: str = "",
    task_type: str = "",
    keyword: str = "",
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "items": task_queue.list_tasks(
            db,
            current_user.tenant_id,
            status=status,
            task_type=task_type,
            keyword=keyword,
            limit=limit,
        )
    }


@router.get("/api/tasks/stats")
def api_task_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system:tasks")),
):
    """任务与 worker 运行状态（运维视角）。"""
    return {
        "tasks": task_queue.stats(db, current_user.tenant_id),
        "worker": worker_stats(),
    }


@router.get("/api/tasks/{task_id}")
def api_get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, current_user.tenant_id, task_id)
    return task_queue.serialize(task, include_payload=True, include_result=True)


@router.post("/api/tasks/{task_id}/cancel")
def api_cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system:tasks")),
):
    """取消任务：运行中的任务会在处理器下次上报进度时自行退出。"""
    _require_task(db, current_user.tenant_id, task_id)
    if not task_queue.request_cancel(db, task_id):
        raise HTTPException(status_code=409, detail="任务已结束，无法取消")
    return {"message": "任务已取消"}


@router.post("/api/tasks/{task_id}/retry")
def api_retry_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system:tasks")),
):
    """把失败任务重新入队。"""
    _require_task(db, current_user.tenant_id, task_id)
    if not task_queue.requeue(db, task_id):
        raise HTTPException(status_code=409, detail="只有失败的任务可以重试")
    return {"message": "任务已重新入队"}
