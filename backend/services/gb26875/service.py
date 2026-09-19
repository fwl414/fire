"""GB/T 26875 接入服务生命周期（模块级单例）

与 MQTT 接入一致：未启用（`GB26875_ENABLED=false`，默认）或端口被占用时只打印日志，
不影响应用其他功能；`start_*` / `stop_*` 幂等，重复调用安全。

服务跑在独立线程的 asyncio 事件循环里，避免与 FastAPI 主循环互相阻塞；
数据库访问由 server 层放到线程池执行（每次一个会话）。
"""
from __future__ import annotations

import asyncio
import itertools
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from . import commands as cmd
from . import server
from .frame import encode, encode_app_data

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_server: Optional["asyncio.AbstractServer"] = None
_started_at: Optional[datetime] = None
_seq_counter = itertools.count(1)


def enabled() -> bool:
    return os.environ.get("GB26875_ENABLED", "false").strip().lower() == "true"


def listen_host() -> str:
    return (os.environ.get("GB26875_LISTEN_HOST") or "127.0.0.1").strip()


def listen_port() -> int:
    try:
        return int(os.environ.get("GB26875_LISTEN_PORT", "5016"))
    except (TypeError, ValueError):
        return 5016


def _thread_main(host: str, port: int, ready: threading.Event, errors: Dict[str, str]) -> None:
    global _loop, _server
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop

    async def _serve() -> "asyncio.AbstractServer":
        return await asyncio.start_server(server._handle_client, host, port)

    try:
        _server = loop.run_until_complete(_serve())
    except Exception as exc:  # noqa: BLE001 - 端口占用等启动失败只记录
        errors["message"] = f"{exc}"
        ready.set()
        loop.close()
        _loop = None
        return

    ready.set()
    try:
        loop.run_forever()
    finally:
        try:
            _server.close()
            loop.run_until_complete(_server.wait_closed())
        except Exception:
            pass
        _server = None
        try:
            loop.close()
        except Exception:
            pass
        _loop = None


def start_gb26875_server() -> bool:
    """启动 GB 26875 TCP 接入服务（幂等）。未启用或启动失败返回 False。"""
    global _thread, _started_at
    if not enabled():
        print("[info] GB26875_ENABLED=false，跳过 GB 26875 消防主机接入")
        return False

    with _lock:
        if _thread is not None and _thread.is_alive():
            return True

        host, port = listen_host(), listen_port()
        ready = threading.Event()
        errors: Dict[str, str] = {}
        thread = threading.Thread(
            target=_thread_main,
            args=(host, port, ready, errors),
            name="gb26875-ingest",
            daemon=True,
        )
        thread.start()
        ready.wait(timeout=10)
        if errors:
            print(f"[error] GB 26875 接入服务启动失败（{host}:{port}）：{errors['message']}")
            _thread = None
            return False

        _thread = thread
        _started_at = datetime.utcnow()
        print(f"[info] GB 26875 消防主机接入已启动（{host}:{port}）")
        return True


def stop_gb26875_server() -> None:
    """停止服务（幂等）。"""
    global _thread, _started_at
    with _lock:
        loop, thread = _loop, _thread
        _thread = None
        _started_at = None
    if loop is None or thread is None:
        return
    try:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
    except Exception:
        pass
    print("[info] GB 26875 消防主机接入已停止")


def service_status() -> Dict[str, Any]:
    """服务运行状态，供 /api/gb26875/status 与 /health 使用。"""
    thread = _thread
    return {
        "enabled": enabled(),
        "running": bool(thread is not None and thread.is_alive()),
        "listen": f"{listen_host()}:{listen_port()}",
        "center_address": server.CENTER_ADDRESS,
        "started_at": _started_at.isoformat() if _started_at else None,
        "connections": server.connection_snapshot(),
        **server.stats(),
    }


async def _send_and_wait(payload: bytes, address: str, seq: int, timeout: float) -> str:
    return await server.send_and_wait(address, payload, seq, timeout=timeout)


def _run_coroutine(coro, timeout: float):
    loop = _loop
    if loop is None or not loop.is_running():
        return None
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout + 1)


def _send_control(address: str, app_type: int, *, timeout: float = 5.0) -> Dict[str, Any]:
    """下发控制命令并等待确认；服务未运行或设备未连接时返回对应状态。"""
    if not enabled() or _loop is None:
        return {"sent": False, "result": "service_not_running", "message": "GB 26875 接入服务未运行"}
    seq = next(_seq_counter) & 0xFFFF
    payload = encode(
        cmd.COMMAND_CONTROL,
        source_address=server.CENTER_ADDRESS,
        dest_address=address,
        app_data=encode_app_data(app_type),
        seq=seq,
    )
    result = _run_coroutine(_send_and_wait(payload, address, seq, timeout), timeout)
    messages = {
        "confirm": "设备已确认",
        "deny": "设备否认该命令",
        "timeout": "等待设备确认超时",
        "offline": "设备当前未连接",
        None: "GB 26875 接入服务未运行",
    }
    return {"sent": result is not None and result != "offline", "result": result, "seq": seq,
            "message": messages.get(result, "未知结果")}


def sync_device_time(address: str, *, timeout: float = 5.0) -> Dict[str, Any]:
    """下发时间同步（控制命令 + 同步用户信息传输装置时钟）。"""
    return _send_control(address, cmd.TYPE_SYNC_TRANSMITTER_TIME, timeout=timeout)


def initialize_device(address: str, *, timeout: float = 5.0) -> Dict[str, Any]:
    """下发初始化命令。"""
    return _send_control(address, cmd.TYPE_INIT_TRANSMITTER, timeout=timeout)
