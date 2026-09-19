"""后台任务队列（数据库持久化 + 进程内 worker）

设计要点：
- 任务落库，重启不丢；不引入 Redis/Celery，单机 Docker Compose 即可运行
- **抢占式领取**：`UPDATE ... WHERE status='pending'` 按影响行数判定，SQLite 与 PostgreSQL
  都可用，天然支持多实例（多个 worker 抢同一批任务不会重复执行）
- **租约续期**：运行中的任务持续续租；worker 崩溃后租约过期，任务被重新领取
- **处理器注册表**：`@register_handler("xxx")` 声明式注册，worker 按 `task_type` 分发

调用方（业务代码）只需要 `enqueue(...)`；执行细节交给 `task_worker_service`。
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import BackgroundTask

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_CANCELED = "canceled"

ACTIVE_STATUSES = (STATUS_PENDING, STATUS_RUNNING)
TERMINAL_STATUSES = (STATUS_SUCCESS, STATUS_FAILED, STATUS_CANCELED)

# 任务租约时长（秒）：worker 崩溃后超过该时长未续租，任务可被其他人重新领取
DEFAULT_LEASE_SECONDS = 900

MAX_ERROR_LENGTH = 2000


class TaskQueueError(RuntimeError):
    """任务队列操作失败。"""


# ---------------- 处理器注册表 ----------------

_HANDLERS: Dict[str, Callable[["TaskContext"], Dict[str, Any]]] = {}


@dataclass
class TaskContext:
    """传给处理器的上下文：任务参数 + 进度上报 + 取消感知。"""

    task_id: str
    task_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    tenant_id: Optional[int] = None
    created_by_name: str = ""
    attempts: int = 1
    max_attempts: int = 1
    _db_factory: Optional[Callable[[], Session]] = None

    # -- 供处理器使用 --

    @property
    def is_last_attempt(self) -> bool:
        """本次已是最后一次尝试；处理器据此决定"重试"还是"进死信"。"""
        return self.attempts >= self.max_attempts

    def report(
        self,
        *,
        done: Optional[int] = None,
        total: Optional[int] = None,
        message: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """上报进度（同时续租）。`extra` 会合并进 `result`，供运行中也要展示的中间结果使用。"""
        self._with_db(lambda db: update_progress(
            db, self.task_id, done=done, total=total, message=message, extra=extra
        ))

    def canceled(self) -> bool:
        """长任务可据此提前退出。"""
        return bool(self._with_db(lambda db: is_canceled(db, self.task_id)))

    def _with_db(self, fn):
        if self._db_factory is None:
            return None
        db = self._db_factory()
        try:
            return fn(db)
        finally:
            db.close()


def register_handler(task_type: str):
    """注册任务处理器。处理器签名：`handler(ctx: TaskContext) -> dict`。"""

    def _decorator(func):
        if task_type in _HANDLERS:
            raise TaskQueueError(f"任务类型「{task_type}」的处理器已注册")
        _HANDLERS[task_type] = func
        return func

    return _decorator


def get_handler(task_type: str):
    return _HANDLERS.get(task_type)


def registered_types() -> List[str]:
    return sorted(_HANDLERS.keys())


# ---------------- 入队 ----------------


def build_task_id(task_type: str) -> str:
    prefix = "".join(part[:4].upper() for part in (task_type or "task").split("_")[:2]) or "TASK"
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def enqueue(
    db: Session,
    *,
    task_type: str,
    payload: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[int] = None,
    task_name: str = "",
    priority: int = 0,
    total_items: int = 0,
    max_attempts: int = 1,
    created_by: Optional[int] = None,
    created_by_name: str = "",
    task_id: Optional[str] = None,
) -> BackgroundTask:
    """把任务写入队列，等待 worker 领取。"""
    if not task_type:
        raise TaskQueueError("task_type 不能为空")

    task = BackgroundTask(
        tenant_id=tenant_id,
        task_id=task_id or build_task_id(task_type),
        task_type=task_type,
        task_name=(task_name or task_type)[:255],
        status=STATUS_PENDING,
        priority=int(priority or 0),
        payload=payload or {},
        progress=0,
        progress_message="已入队，等待执行",
        total_items=int(total_items or 0),
        done_items=0,
        attempts=0,
        max_attempts=max(1, int(max_attempts or 1)),
        created_by=created_by,
        created_by_name=created_by_name or "",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ---------------- 抢占式领取与租约 ----------------


def claim_next(
    db: Session,
    worker_id: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    task_types: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """领取一个待执行任务；没有可领取的任务时返回 None。

    通过 `UPDATE ... WHERE id=? AND status='pending'` 的影响行数判定是否抢到，
    因此多个 worker（含多实例）并发领取不会重复执行同一任务。
    """
    query = db.query(BackgroundTask.id).filter(BackgroundTask.status == STATUS_PENDING)
    if task_types:
        query = query.filter(BackgroundTask.task_type.in_(list(task_types)))

    candidate_rows = (
        query.order_by(BackgroundTask.priority.desc(), BackgroundTask.created_at.asc())
        .limit(10)
        .all()
    )

    now = datetime.utcnow()
    for (candidate_id,) in candidate_rows:
        claimed = (
            db.query(BackgroundTask)
            .filter(
                BackgroundTask.id == candidate_id,
                BackgroundTask.status == STATUS_PENDING,
            )
            .update(
                {
                    BackgroundTask.status: STATUS_RUNNING,
                    BackgroundTask.lease_owner: worker_id,
                    BackgroundTask.lease_expires_at: now + timedelta(seconds=lease_seconds),
                    BackgroundTask.started_at: now,
                    BackgroundTask.updated_at: now,
                    BackgroundTask.attempts: BackgroundTask.attempts + 1,
                    BackgroundTask.progress_message: "开始执行",
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if claimed == 1:
            return get_task_by_id(db, candidate_id)
    return None


def extend_lease(db: Session, task_id: str, worker_id: str, *, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
    """续租；只有当前持有者能续（避免已过期的任务被抢走后旧 worker 又续上）。"""
    updated = (
        db.query(BackgroundTask)
        .filter(
            BackgroundTask.task_id == task_id,
            BackgroundTask.status == STATUS_RUNNING,
            BackgroundTask.lease_owner == worker_id,
        )
        .update(
            {
                BackgroundTask.lease_expires_at: datetime.utcnow() + timedelta(seconds=lease_seconds),
                BackgroundTask.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return updated == 1


def recover_expired(db: Session, *, limit: int = 20) -> int:
    """把租约过期的 running 任务收回：还有重试次数则重新排队，否则标记失败。"""
    now = datetime.utcnow()
    expired = (
        db.query(BackgroundTask)
        .filter(
            BackgroundTask.status == STATUS_RUNNING,
            BackgroundTask.lease_expires_at.isnot(None),
            BackgroundTask.lease_expires_at < now,
        )
        .limit(limit)
        .all()
    )

    recovered = 0
    for task in expired:
        if (task.attempts or 0) < (task.max_attempts or 1):
            task.status = STATUS_PENDING
            task.progress_message = "上次执行的 worker 已失联，重新排队"
        else:
            task.status = STATUS_FAILED
            task.error = "执行中被中断（worker 失联），且已达最大重试次数"
            task.finished_at = now
        task.lease_owner = ""
    if expired:
        db.commit()
        recovered = len(expired)
        logger.warning(f"回收了 {recovered} 个租约过期的后台任务")
    return recovered


# ---------------- 进度与收尾 ----------------


def update_progress(
    db: Session,
    task_id: str,
    *,
    done: Optional[int] = None,
    total: Optional[int] = None,
    message: str = "",
    extra: Optional[Dict[str, Any]] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> None:
    task = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id).first()
    if not task:
        return
    if done is not None:
        task.done_items = max(0, int(done))
    if total is not None:
        task.total_items = max(0, int(total))
    if task.total_items:
        task.progress = max(0, min(100, round(task.done_items / task.total_items * 100)))
    elif done is not None:
        task.progress = 0
    if message:
        task.progress_message = message[:255]
    if extra:
        # 重新赋值而不是原地修改，否则 JSON 列的变更不会被 SQLAlchemy 检测到
        task.result = {**(task.result or {}), **extra}
    # 进度上报顺带续租
    if task.status == STATUS_RUNNING:
        task.lease_expires_at = datetime.utcnow() + timedelta(seconds=lease_seconds)
    task.updated_at = datetime.utcnow()
    db.commit()


def is_canceled(db: Session, task_id: str) -> bool:
    status = (
        db.query(BackgroundTask.status)
        .filter(BackgroundTask.task_id == task_id)
        .scalar()
    )
    return status == STATUS_CANCELED


def finish_success(db: Session, task_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
    task = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id).first()
    if not task or task.status == STATUS_CANCELED:
        return False
    now = datetime.utcnow()
    task.status = STATUS_SUCCESS
    task.result = result or {}
    task.progress = 100
    task.progress_message = "已完成"
    task.error = ""
    task.lease_owner = ""
    task.lease_expires_at = None
    task.finished_at = now
    task.updated_at = now
    db.commit()
    return True


def finish_failed(db: Session, task_id: str, error: str) -> bool:
    task = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id).first()
    if not task or task.status == STATUS_CANCELED:
        return False
    now = datetime.utcnow()
    task.status = STATUS_FAILED
    task.error = (error or "任务执行失败")[:MAX_ERROR_LENGTH]
    task.progress_message = "执行失败"
    task.lease_owner = ""
    task.lease_expires_at = None
    task.finished_at = now
    task.updated_at = now
    db.commit()
    return True


def requeue(db: Session, task_id: str) -> bool:
    """把失败任务重新入队（保留历史 attempts）。"""
    task = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id).first()
    if not task or task.status not in (STATUS_FAILED,):
        return False
    task.status = STATUS_PENDING
    task.error = ""
    task.progress_message = "已重新入队"
    task.lease_owner = ""
    task.lease_expires_at = None
    task.finished_at = None
    task.updated_at = datetime.utcnow()
    db.commit()
    return True


def request_cancel(db: Session, task_id: str) -> bool:
    task = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id).first()
    if not task or task.status in TERMINAL_STATUSES:
        return False
    now = datetime.utcnow()
    task.status = STATUS_CANCELED
    task.progress_message = "已取消"
    task.lease_owner = ""
    task.lease_expires_at = None
    task.finished_at = now
    task.updated_at = now
    db.commit()
    return True


# ---------------- 查询 ----------------


def get_task_by_id(db: Session, row_id: int) -> Optional[Dict[str, Any]]:
    task = db.query(BackgroundTask).filter(BackgroundTask.id == row_id).first()
    return serialize(task, include_payload=True, include_result=True) if task else None


def get_task(db: Session, tenant_id: Optional[int], task_id: str) -> Optional[BackgroundTask]:
    query = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id)
    if tenant_id is not None:
        query = query.filter(
            (BackgroundTask.tenant_id == tenant_id) | (BackgroundTask.tenant_id.is_(None))
        )
    return query.first()


def list_tasks(
    db: Session,
    tenant_id: Optional[int],
    *,
    status: str = "",
    task_type: str = "",
    keyword: str = "",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    query = db.query(BackgroundTask)
    if tenant_id is not None:
        query = query.filter(
            (BackgroundTask.tenant_id == tenant_id) | (BackgroundTask.tenant_id.is_(None))
        )
    if status:
        query = query.filter(BackgroundTask.status == status)
    if task_type:
        query = query.filter(BackgroundTask.task_type == task_type)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            BackgroundTask.task_name.like(like)
            | BackgroundTask.task_id.like(like)
            | BackgroundTask.progress_message.like(like)
        )
    rows = (
        query.order_by(BackgroundTask.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [serialize(row) for row in rows]


def stats(db: Session, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    query = db.query(BackgroundTask)
    if tenant_id is not None:
        query = query.filter(
            (BackgroundTask.tenant_id == tenant_id) | (BackgroundTask.tenant_id.is_(None))
        )
    counts = {status: 0 for status in (*ACTIVE_STATUSES, *TERMINAL_STATUSES)}
    for status, total in (
        query.with_entities(BackgroundTask.status, func.count(BackgroundTask.id))
        .group_by(BackgroundTask.status)
        .all()
    ):
        counts[status or STATUS_PENDING] = int(total)
    by_type = [
        {"task_type": row[0] or "", "count": int(row[1])}
        for row in query.with_entities(BackgroundTask.task_type, func.count(BackgroundTask.id))
        .group_by(BackgroundTask.task_type)
        .all()
    ]
    return {"by_status": counts, "by_type": by_type, "total": sum(counts.values())}


def pending_count() -> int:
    """供 /metrics 使用；失败降级为 0。"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        return int(
            db.query(func.count(BackgroundTask.id))
            .filter(BackgroundTask.status.in_(ACTIVE_STATUSES))
            .scalar()
            or 0
        )
    except Exception:
        return 0
    finally:
        db.close()


def serialize(
    task: BackgroundTask,
    *,
    include_payload: bool = False,
    include_result: bool = False,
) -> Dict[str, Any]:
    data = {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "task_name": task.task_name or "",
        "status": task.status,
        "priority": task.priority or 0,
        "progress": task.progress or 0,
        "progress_message": task.progress_message or "",
        "total_items": task.total_items or 0,
        "done_items": task.done_items or 0,
        "attempts": task.attempts or 0,
        "max_attempts": task.max_attempts or 1,
        "error": task.error or "",
        "lease_owner": task.lease_owner or "",
        "tenant_id": task.tenant_id,
        "created_by": task.created_by,
        "created_by_name": task.created_by_name or "",
        "created_at": _iso(task.created_at),
        "started_at": _iso(task.started_at),
        "finished_at": _iso(task.finished_at),
        "updated_at": _iso(task.updated_at),
    }
    if include_payload:
        data["payload"] = task.payload or {}
    if include_result:
        data["result"] = task.result or {}
    return data


def _iso(value: Optional[datetime]) -> str:
    return value.isoformat() if value else ""


__all__ = [
    "ACTIVE_STATUSES",
    "DEFAULT_LEASE_SECONDS",
    "STATUS_CANCELED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_SUCCESS",
    "TERMINAL_STATUSES",
    "TaskContext",
    "TaskQueueError",
    "claim_next",
    "enqueue",
    "extend_lease",
    "finish_failed",
    "finish_success",
    "get_handler",
    "get_task",
    "get_task_by_id",
    "is_canceled",
    "list_tasks",
    "pending_count",
    "recover_expired",
    "register_handler",
    "registered_types",
    "request_cancel",
    "requeue",
    "serialize",
    "stats",
    "update_progress",
]
