"""后台任务 worker（进程内常驻协程）

生命周期沿用了 MQTT 接入的模式（模块级单例 + 幂等 start/stop），但有一点关键差异：
**必须在事件循环内启动**。`main.py` 的 lifespan 里调用 `start_worker()`，`asyncio.create_task`
才能拿到运行中的 loop —— 此前批量巡检正是在同步端点里调用 `create_task`，必然抛
`RuntimeError: no running event loop`，后台任务从未真正执行过。

worker 循环：
1. 周期回收租约过期的任务（worker 崩溃后的自愈）
2. 抢占式领取一个待执行任务
3. 在独立线程里执行处理器（同步 SQLAlchemy / 文件 IO 不阻塞事件循环），期间后台协程持续续租
4. 写回成功或失败，继续下一轮

空闲时才轮询等待，有任务时立即继续，避免固定延迟。
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from database import SessionLocal
from services.task_queue_service import (
    TaskContext,
    claim_next,
    extend_lease,
    finish_failed,
    finish_success,
    get_handler,
    recover_expired,
)

logger = logging.getLogger(__name__)

TASK_WORKER_ENABLED = os.environ.get("TASK_WORKER_ENABLED", "true").lower() == "true"
POLL_SECONDS = float(os.environ.get("TASK_WORKER_POLL_SECONDS", "2"))
HEARTBEAT_SECONDS = float(os.environ.get("TASK_WORKER_HEARTBEAT_SECONDS", "60"))
RECOVER_INTERVAL_SECONDS = float(os.environ.get("TASK_WORKER_RECOVER_SECONDS", "60"))

_worker_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None
_lock = threading.Lock()
_worker_id = ""
_last_recover_at = 0.0

_state: Dict[str, Any] = {
    "processed": 0,
    "failed": 0,
    "last_error": "",
    "last_task_id": "",
    "started_at": "",
}


def worker_id() -> str:
    return _worker_id


def ensure_handlers_loaded() -> None:
    """import 处理器模块即完成注册（避免在业务模块里到处 import）。"""
    import services.task_handlers  # noqa: F401


# ---------------- 生命周期 ----------------


def start_worker() -> bool:
    """启动 worker（幂等）。必须在事件循环内调用。"""
    global _worker_task, _stop_event, _worker_id

    if not TASK_WORKER_ENABLED:
        print("[info] TASK_WORKER_ENABLED=false，跳过后台任务 worker")
        return False

    with _lock:
        if _worker_task is not None and not _worker_task.done():
            return True

        ensure_handlers_loaded()
        _worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        _stop_event = asyncio.Event()
        _worker_task = asyncio.create_task(_run_loop(_stop_event))
        _state["started_at"] = datetime.utcnow().isoformat()
        print(f"[info] 后台任务 worker 已启动（{_worker_id}）")
        return True


async def stop_worker() -> None:
    """优雅停止：通知循环退出并等待当前任务收尾。"""
    global _worker_task, _stop_event

    with _lock:
        task, stop = _worker_task, _stop_event
        _worker_task, _stop_event = None, None

    if stop is not None:
        stop.set()
    if task is None:
        return

    try:
        await asyncio.wait_for(task, timeout=10)
    except asyncio.TimeoutError:
        task.cancel()
        logger.warning("后台任务 worker 未在 10 秒内退出，已强制取消")
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001 - 停止阶段的异常不应影响关停流程
        logger.warning(f"停止后台任务 worker 时出现异常: {exc}")
    print("[info] 后台任务 worker 已停止")


def worker_stats() -> Dict[str, Any]:
    running = _worker_task is not None and not _worker_task.done()
    return {
        "enabled": TASK_WORKER_ENABLED,
        "running": bool(running),
        "worker_id": _worker_id,
        **_state,
    }


# ---------------- 主循环 ----------------


async def _run_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            processed = await process_pending_once()
        except Exception as exc:  # noqa: BLE001 - worker 不能因单次异常退出
            _state["last_error"] = f"{type(exc).__name__}: {exc}"
            logger.error(f"后台任务 worker 处理异常: {exc}")
            processed = False

        if processed:
            continue
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass


async def process_pending_once(*, task_types=None) -> bool:
    """领取并执行一个任务；没有可执行任务返回 False。

    对外暴露是为了测试与「立即执行」这类手动触发场景，正常情况下由 `_run_loop` 调用。
    """
    db = SessionLocal()
    try:
        _maybe_recover(db)
        task = await asyncio.to_thread(
            claim_next, db, _worker_id, task_types=list(task_types) if task_types else None
        )
    finally:
        db.close()

    if not task:
        return False

    await _execute(task)
    return True


def _maybe_recover(db) -> None:
    global _last_recover_at

    now = time.time()
    if now - _last_recover_at < RECOVER_INTERVAL_SECONDS:
        return
    _last_recover_at = now
    recover_expired(db)


async def _execute(task: Dict[str, Any]) -> None:
    task_id = task["task_id"]
    task_type = task["task_type"]
    _state["last_task_id"] = task_id

    handler = get_handler(task_type)
    if handler is None:
        await asyncio.to_thread(_finish_failed, task_id, f"没有注册任务类型「{task_type}」的处理器")
        _state["failed"] += 1
        logger.error(f"后台任务 {task_id} 失败：未注册处理器 {task_type}")
        return

    ctx = TaskContext(
        task_id=task_id,
        task_type=task_type,
        payload=task.get("payload") or {},
        tenant_id=task.get("tenant_id"),
        created_by_name=task.get("created_by_name") or "",
        attempts=int(task.get("attempts") or 1),
        max_attempts=int(task.get("max_attempts") or 1),
        _db_factory=SessionLocal,
    )

    beat_stop = asyncio.Event()
    beat_task = asyncio.create_task(_heartbeat(task_id, beat_stop))
    try:
        if asyncio.iscoroutinefunction(handler):
            result = await handler(ctx)
        else:
            # 同步处理器放到线程里跑：同步 SQLAlchemy / 文件 IO 不会阻塞事件循环
            result = await asyncio.to_thread(handler, ctx)

        ok = await asyncio.to_thread(_finish_success, task_id, result or {})
        if ok:
            _state["processed"] += 1
            logger.info(f"后台任务 {task_id}（{task_type}）执行完成")
    except Exception as exc:  # noqa: BLE001 - 单个任务失败不影响 worker
        _state["failed"] += 1
        _state["last_error"] = f"{type(exc).__name__}: {exc}"
        logger.error(f"后台任务 {task_id}（{task_type}）执行失败: {exc}", exc_info=True)
        await asyncio.to_thread(_finish_failed, task_id, f"{type(exc).__name__}: {exc}")
    finally:
        beat_stop.set()
        try:
            await beat_task
        except Exception:  # noqa: BLE001
            pass


async def _heartbeat(task_id: str, stop: asyncio.Event) -> None:
    """定期续租，避免长时间任务被误判为失联。"""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_SECONDS)
        except asyncio.TimeoutError:
            await asyncio.to_thread(_extend_lease, task_id)


# ---------------- 短会话包装（每次操作自建 Session 并及时关闭） ----------------


def _finish_success(task_id: str, result: Dict[str, Any]) -> bool:
    db = SessionLocal()
    try:
        return finish_success(db, task_id, result)
    finally:
        db.close()


def _finish_failed(task_id: str, error: str) -> bool:
    db = SessionLocal()
    try:
        return finish_failed(db, task_id, error)
    finally:
        db.close()


def _extend_lease(task_id: str) -> bool:
    db = SessionLocal()
    try:
        return extend_lease(db, task_id, _worker_id)
    finally:
        db.close()
