"""批量巡检任务（基于后台任务队列）

改造前这里是一套进程内字典实现，存在三个问题：
1. `create_batch_task` 是同步函数却调用 `asyncio.create_task`，由同步端点在线程池中执行时
   必然抛 `RuntimeError: no running event loop`，后台任务从未真正执行过；
2. 任务与进度只存在内存，进程重启即丢失；
3. 无任务时 `_ensure_demo_tasks()` 会凭空造出 3 条演示任务，让"数据还在"的假象掩盖问题。

现在改为写入 `background_tasks` 队列，由 `task_worker_service` 执行；对外接口的返回结构
保持不变，前端无需改动。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import User
from services import task_queue_service as queue

TASK_TYPE = "batch_inspection"

# 前端使用的状态词 -> 队列状态
STATUS_ALIASES = {"completed": queue.STATUS_SUCCESS, "done": queue.STATUS_SUCCESS}
# 队列状态 -> 前端使用的状态词
STATUS_LABELS = {queue.STATUS_SUCCESS: "completed"}

DEFAULT_LOCATIONS = [
    "1层大厅", "1层消防通道", "2层办公室", "2层楼梯间",
    "3层会议室", "3层配电室", "B1层车库", "B1层水泵房",
    "屋顶消防水箱", "电梯机房",
]


def default_inspection_items(count: int = 10) -> List[Dict[str, Any]]:
    """未提供巡检项时生成一份楼宇通用巡检清单（仅作为入参默认值）。"""
    return [
        {
            "id": f"ITEM-{i + 1:03d}",
            "location": location,
            "description": f"{location}日常巡检",
            "device_id": f"DEV-{i + 1:03d}",
            "device_name": f"巡检点-{i + 1}",
            "check_items": ["消防通道", "灭火器", "消防栓", "应急照明", "安全出口标识"],
        }
        for i, location in enumerate(DEFAULT_LOCATIONS[: max(1, count)])
    ]


def _to_frontend_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def _to_queue_status(status: str) -> str:
    return STATUS_ALIASES.get(status, status)


def create_batch_task(
    db: Session,
    payload: Dict[str, Any],
    *,
    tenant_id: Optional[int] = None,
    user: Optional[User] = None,
) -> Dict[str, Any]:
    """创建批量巡检任务并入队。"""
    inspection_items = payload.get("inspection_items") or default_inspection_items(10)
    task_name = payload.get("task_name") or "批量巡检任务"

    task = queue.enqueue(
        db,
        task_type=TASK_TYPE,
        payload={
            "task_name": task_name,
            "building_id": payload.get("building_id") or "default",
            "building_name": payload.get("building_name") or "综合办公楼",
            "inspector": payload.get("inspector") or "系统",
            "priority": payload.get("priority") or "中",
            "scheduled_time": payload.get("scheduled_time") or "",
            "inspection_items": inspection_items,
        },
        tenant_id=tenant_id,
        task_name=task_name,
        total_items=len(inspection_items),
        created_by=getattr(user, "id", None),
        created_by_name=getattr(user, "username", "") or "",
    )

    return {
        "success": True,
        "task_id": task.task_id,
        "task_name": task.task_name,
        "total_count": len(inspection_items),
        "status": "pending",
        "message": "批量巡检任务已创建，等待后台执行",
    }


def list_batch_tasks(
    db: Session,
    *,
    tenant_id: Optional[int] = None,
    status: str = "",
    building_id: str = "",
    limit: int = 50,
) -> Dict[str, Any]:
    rows = queue.list_tasks(
        db,
        tenant_id,
        status=_to_queue_status(status) if status else "",
        task_type=TASK_TYPE,
        limit=max(1, min(limit, 200)),
    )

    if building_id:
        rows = [r for r in rows if r["payload"].get("building_id") == building_id]

    return {
        "total": len(rows),
        "items": [
            {
                "id": row["task_id"],
                "task_name": row["task_name"],
                "building_name": (row.get("payload") or {}).get("building_name", ""),
                "total_count": row["total_items"],
                "completed_count": row["done_items"],
                "status": _to_frontend_status(row["status"]),
                "priority": (row.get("payload") or {}).get("priority", "中"),
                "inspector": (row.get("payload") or {}).get("inspector", ""),
                "created_at": _display_time(row.get("created_at")),
                "started_at": _display_time(row.get("started_at")),
                "completed_at": _display_time(row.get("finished_at")),
            }
            for row in rows
        ],
    }


def get_batch_task_detail(
    db: Session,
    task_id: str,
    *,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    task = queue.get_task(db, tenant_id, task_id)
    if not task:
        return {"success": False, "error": "任务不存在"}

    data = queue.serialize(task, include_payload=True, include_result=True)
    payload = data.get("payload") or {}
    result = data.get("result") or {}

    return {
        "success": True,
        "id": data["task_id"],
        "task_name": data["task_name"],
        "building_id": payload.get("building_id", ""),
        "building_name": payload.get("building_name", ""),
        "inspector": payload.get("inspector", ""),
        "priority": payload.get("priority", "中"),
        "scheduled_time": payload.get("scheduled_time", ""),
        "total_count": data["total_items"],
        "completed_count": data["done_items"],
        "status": _to_frontend_status(data["status"]),
        "inspection_items": payload.get("inspection_items", []),
        "results": result.get("results", []),
        "progress": data["progress"],
        "progress_message": data["progress_message"],
        "error": data["error"],
        "created_at": _display_time(data.get("created_at")),
        "started_at": _display_time(data.get("started_at")),
        "completed_at": _display_time(data.get("finished_at")),
    }


def get_batch_task_progress(
    db: Session,
    task_id: str,
    *,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    task = queue.get_task(db, tenant_id, task_id)
    if not task:
        return {"success": False, "error": "任务不存在"}

    data = queue.serialize(task, include_result=True)
    result = data.get("result") or {}

    return {
        "success": True,
        "task_id": data["task_id"],
        "status": _to_frontend_status(data["status"]),
        "progress": data["progress"],
        "progress_message": data["progress_message"],
        "current_item": result.get("current_item", ""),
        "completed_count": data["done_items"],
        "total_count": data["total_items"],
        "high_risk_count": result.get("high_risk_count", 0),
        "medium_risk_count": result.get("medium_risk_count", 0),
        "low_risk_count": result.get("low_risk_count", 0),
        "error": data["error"],
    }


def _display_time(value: str) -> str:
    """队列返回 ISO 格式，前端展示沿用 'YYYY-MM-DD HH:MM:SS'。"""
    if not value:
        return ""
    return value.replace("T", " ")[:19]
