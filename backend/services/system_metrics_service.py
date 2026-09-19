"""系统监控：真实的主机与运行时指标

改造前 `SystemMonitor.vue` 的 CPU / 内存 / 网络是 `Math.random()` 每 3 秒改写一次，
趋势曲线也是随机数滚出来的 —— 数字一直在动，但和服务器真实状态毫无关系；峰值/均值、
数据库连接数、接口调用量则全是写死的常量，页面标注的「每 5 秒刷新」也是假的。

这里统一提供真实数据，取不到的一律返回 `None` 交给前端显示「--」，不用估算值充数：

- 主机指标（CPU / 内存 / 磁盘 / 网络 / 进程）来自 psutil 的真实采样；
- 接口监控来自 `services.metrics_service` 的进程内真实计数（`MetricsMiddleware` 累加）；
- 数据库只给查得到的（连通性、库大小、连接池、各表行数），SQLite 不提供 QPS / 缓存命中率；
- CPU 使用率与网络速率需要两次采样之间的差值，**首次采样没有基准，返回 None**（不编一个数）。
"""
from __future__ import annotations

import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
from sqlalchemy import text

from database import DATABASE_URL, IS_SQLITE, engine
from services import metrics_service

# CPU 使用率 / 网络速率依赖「上次采样」做差值
_prev_cpu: Optional[Tuple[float, float]] = None
_prev_net: Optional[Tuple[float, float, float]] = None

# 本进程启动以来的真实采样点（用于趋势曲线与峰值/均值）。不做持久化，进程重启后重新累积。
_TREND: deque = deque(maxlen=120)

# psutil 的进程 CPU 占用需要两次采样，首次先建基准
_process_primed = False


def _disk_root() -> str:
    """应用所在磁盘 / 挂载点（Windows 取盘符，类 Unix 取 /）。"""
    return Path(__file__).resolve().anchor or os.sep


def _cpu_percent() -> Optional[float]:
    """整机 CPU 使用率（按两次调用之间的 CPU 时间差值计算）。"""
    global _prev_cpu

    times = psutil.cpu_times()
    total = float(sum(times))
    idle = float(times.idle)
    if _prev_cpu is None:
        _prev_cpu = (total, idle)
        return None
    prev_total, prev_idle = _prev_cpu
    _prev_cpu = (total, idle)

    total_delta = total - prev_total
    if total_delta <= 0:
        return None
    busy_delta = total_delta - (idle - prev_idle)
    return round(max(0.0, min(100.0, busy_delta / total_delta * 100)), 1)


def _net_rate(now: float) -> Optional[Dict[str, float]]:
    """网卡收发速率（KB/s），按两次调用之间的字节差值计算。"""
    global _prev_net

    counters = psutil.net_io_counters()
    current = (now, float(counters.bytes_sent), float(counters.bytes_recv))
    if _prev_net is None:
        _prev_net = current
        return None

    prev_time, prev_sent, prev_recv = _prev_net
    _prev_net = current
    elapsed = now - prev_time
    if elapsed <= 0:
        return None
    return {
        "sent_kbps": round(max(0.0, (current[1] - prev_sent) / elapsed / 1024), 1),
        "recv_kbps": round(max(0.0, (current[2] - prev_recv) / elapsed / 1024), 1),
    }


def host_snapshot() -> Dict[str, Any]:
    """主机实时指标 + 本次启动以来的趋势采样点。"""
    now = time.time()
    cpu = _cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(_disk_root())
    network = _net_rate(now)

    memory_percent = round(float(memory.percent), 1)
    if cpu is not None:
        _TREND.append({"timestamp": int(now), "cpu": cpu, "memory": memory_percent})

    return {
        "timestamp": int(now),
        "cpu": cpu,
        "memory": memory_percent,
        "memory_used_bytes": int(memory.used),
        "memory_total_bytes": int(memory.total),
        "disk": round(float(disk.percent), 1),
        "disk_used_bytes": int(disk.used),
        "disk_total_bytes": int(disk.total),
        "disk_mount": _disk_root(),
        "network": network,
        "cpu_count": psutil.cpu_count() or 0,
        "boot_time": int(psutil.boot_time()),
        "trend": list(_TREND),
        # 第一次调用只建立基准，CPU 与网络速率要到第二次才有值
        "sample_note": "CPU 与网络速率按两次采样的差值计算，首次访问没有基准值",
    }


def process_snapshot(limit: int = 8) -> Dict[str, Any]:
    """按 CPU 占用排序的进程列表（psutil 真实数据）。"""
    global _process_primed

    if not _process_primed:
        # 首次先遍历一遍建基准，否则 cpu_percent 全是 0
        _process_primed = True
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.2)
        return process_snapshot(limit)

    rows: List[Dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "create_time"]):
        try:
            info = proc.info
            pid = int(info["pid"])
            if pid == 0:
                # Windows 的 System Idle Process 统计的就是空闲时间，排进去会一直霸榜
                continue
            rows.append({
                "pid": pid,
                "name": info.get("name") or "",
                "cpu_percent": round(float(proc.cpu_percent(None)), 1),
                "memory_percent": round(float(info.get("memory_percent") or 0.0), 1),
                "start_time": int(info["create_time"]) if info.get("create_time") else None,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    rows.sort(key=lambda item: (item["cpu_percent"], item["memory_percent"]), reverse=True)
    return {
        "items": rows[:limit],
        "total": len(rows),
        # psutil 的进程 CPU 占用按单核计，多线程进程会超过 100%
        "cpu_basis": "占单核百分比，多线程 / 多核进程可超过 100%",
    }


def _sqlite_file_size() -> Optional[int]:
    """SQLite 库文件大小；内存库或路径取不到时返回 None。"""
    raw = DATABASE_URL.split("sqlite:///", 1)[-1] if "sqlite:///" in DATABASE_URL else ""
    if not raw or raw.startswith(":memory:"):
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    if not path.is_file():
        return None
    return path.stat().st_size


def _sqlite_table_sizes(conn) -> Dict[str, int]:
    """用 dbstat 虚拟表统计每张表的字节数；该 SQLite 构建未启用时返回空字典（不估算）。"""
    try:
        result = conn.execute(text("SELECT name, SUM(pgsize) AS size FROM dbstat GROUP BY name"))
        return {row[0]: int(row[1] or 0) for row in result}
    except Exception:
        return {}


def _table_rows(conn) -> List[Dict[str, Any]]:
    names = [
        row[0]
        for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ))
    ]
    sizes = _sqlite_table_sizes(conn)
    rows = []
    for name in names:
        count = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        rows.append({
            "name": name,
            "row_count": int(count or 0),
            "size_bytes": sizes.get(name),
        })
    rows.sort(key=lambda item: (item["size_bytes"] or 0, item["row_count"]), reverse=True)
    return rows


def _pool_snapshot() -> Dict[str, Any]:
    pool = getattr(engine, "pool", None)
    if pool is None:
        return {}
    payload: Dict[str, Any] = {}
    try:
        payload["status"] = pool.status()
    except Exception:
        pass
    try:
        payload["checked_out"] = pool.checkedout()
    except Exception:
        pass
    return payload


def _mask_url(url: str) -> str:
    """隐去连接串里的密码，页面展示用。"""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url or "")


def database_snapshot() -> Dict[str, Any]:
    """数据库真实状态：连通性、库大小、连接池、各表行数。

    SQLite 没有 QPS / TPS / 缓存命中率这类概念，所以这些字段直接在
    `unsupported_metrics` 里列出来交给页面说明，而不是编一个数字。
    """
    payload: Dict[str, Any] = {
        "dialect": engine.dialect.name,
        "database_url_display": _mask_url(DATABASE_URL),
        "connected": False,
        "size_bytes": None,
        "tables": [],
        "pool": _pool_snapshot(),
        "unsupported_metrics": ["qps", "tps", "cache_hit_rate"] if IS_SQLITE else [],
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            payload["connected"] = True
            if IS_SQLITE:
                payload["size_bytes"] = _sqlite_file_size()
                payload["tables"] = _table_rows(conn)
            else:
                size = conn.execute(text("SELECT pg_database_size(current_database())")).scalar()
                payload["size_bytes"] = int(size) if size is not None else None
                payload["tables"] = [
                    {
                        "name": row[0],
                        "row_count": int(row[1] or 0),
                        "size_bytes": int(row[2]) if row[2] is not None else None,
                    }
                    for row in conn.execute(text(
                        "SELECT relname, n_live_tup, pg_total_relation_size(relid) "
                        "FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC"
                    ))
                ]
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


def api_snapshot(limit: int = 10) -> Dict[str, Any]:
    """接口监控：本进程启动以来的真实 HTTP 计数与耗时。"""
    return metrics_service.http_snapshot(limit=limit)
