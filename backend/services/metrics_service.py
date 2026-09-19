"""可观测性指标服务（零外部依赖）

以进程内计数器采集 HTTP 与业务指标，并按 Prometheus 文本格式输出，
避免引入 prometheus_client 依赖，生产镜像无需新增依赖即可被抓取。

访问控制（/metrics）：
    - 配置 METRICS_TOKEN 时，需通过 X-Metrics-Token 头或 ?token= 提供
    - 未配置 METRICS_TOKEN 且 ENV=production 时拒绝访问（避免指标裸奔）
    - 非生产环境可直接访问，便于本地调试
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

IS_PRODUCTION = os.environ.get("ENV", "development").lower() in ("production", "prod")
METRICS_TOKEN = os.environ.get("METRICS_TOKEN", "")

_STARTED_AT = time.time()
_lock = threading.Lock()

# (method, path, status) -> count
_http_requests: Dict[Tuple[str, str, str], int] = defaultdict(int)
# (method, path) -> 累计耗时（秒）/ 次数
_http_duration_sum: Dict[Tuple[str, str], float] = defaultdict(float)
_http_duration_count: Dict[Tuple[str, str], int] = defaultdict(int)
# 业务计数：name -> value
_counters: Dict[str, float] = defaultdict(float)

# 需要归一化的路径片段（避免指标标签基数爆炸）
_NUMERIC_SEGMENT = re.compile(r"^\d+$")
_HEX_SEGMENT = re.compile(r"^[0-9a-fA-F]{16,}$")


def normalize_path(path: str) -> str:
    """把路径中的动态片段替换为 {id}，控制指标标签基数。"""
    if not path:
        return "/"
    parts = []
    for segment in path.split("/"):
        if _NUMERIC_SEGMENT.match(segment) or _HEX_SEGMENT.match(segment):
            parts.append("{id}")
        else:
            parts.append(segment)
    return "/".join(parts)


def observe_http(method: str, path: str, status: int, duration_seconds: float) -> None:
    key = (method.upper(), normalize_path(path), str(status))
    with _lock:
        _http_requests[key] += 1
        _http_duration_sum[(key[0], key[1])] += duration_seconds
        _http_duration_count[(key[0], key[1])] += 1


def incr(name: str, value: float = 1) -> None:
    """累加业务计数（如 alert_created / device_ingest）。"""
    with _lock:
        _counters[name] += value


def counter_value(name: str) -> float:
    with _lock:
        return _counters.get(name, 0.0)


def http_snapshot(limit: int = 10) -> Dict[str, object]:
    """把进程内 HTTP 计数导出成结构化数据，供系统监控页使用。

    这些计数由 `MetricsMiddleware` 在每个真实请求上累加，不是估算值。
    注意口径：仅统计本进程启动以来的请求，进程重启后从零开始。
    """
    with _lock:
        requests = dict(_http_requests)
        duration_sum = dict(_http_duration_sum)
        duration_count = dict(_http_duration_count)

    total = sum(requests.values())
    success = sum(count for (_, _, status), count in requests.items() if str(status).startswith(("1", "2", "3")))
    failed = total - success

    per_path: Dict[Tuple[str, str], Dict[str, int]] = {}
    for (method, path, status), count in requests.items():
        bucket = per_path.setdefault((method, path), {"count": 0, "failed": 0})
        bucket["count"] += count
        if not str(status).startswith(("1", "2", "3")):
            bucket["failed"] += count

    by_path = []
    for (method, path), bucket in per_path.items():
        calls = duration_count.get((method, path), 0)
        spent = duration_sum.get((method, path), 0.0)
        by_path.append({
            "method": method,
            "path": path,
            "count": bucket["count"],
            "failed": bucket["failed"],
            "avg_duration_ms": round(spent / calls * 1000, 1) if calls else None,
        })
    by_path.sort(key=lambda item: item["count"], reverse=True)

    total_duration = sum(duration_sum.values())
    total_calls = sum(duration_count.values())
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "avg_duration_ms": round(total_duration / total_calls * 1000, 1) if total_calls else None,
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "by_path": by_path[:limit],
    }


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric(lines: List[str], name: str, help_text: str, mtype: str) -> None:
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} {mtype}")


def _database_ready() -> bool:
    try:
        from sqlalchemy import text

        from database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _mqtt_snapshot() -> Dict[str, object]:
    try:
        from services.mqtt_ingest_service import mqtt_stats

        return mqtt_stats()
    except Exception:
        return {}


def _backup_age_seconds() -> Optional[float]:
    """最近一次数据库备份距今的秒数（用于备份过期告警）。"""
    try:
        from db_backup import DEFAULT_BACKUP_DIR

        # 只读探测：不创建目录，避免抓取指标产生副作用
        directory = Path(os.environ.get("BACKUP_DIR") or DEFAULT_BACKUP_DIR)
        if not directory.is_dir():
            return None
        files = [
            p for p in directory.iterdir()
            if p.is_file() and not p.name.endswith(".sha256")
        ]
        if not files:
            return None
        newest = max(p.stat().st_mtime for p in files)
        return max(0.0, time.time() - newest)
    except Exception:
        return None


def _llm_usage_snapshot() -> Dict[str, float]:
    """近 24 小时大模型调用量、token 与成本（失败时降级为 0，不影响抓取）。"""
    try:
        from services.llm_usage_service import usage_totals_for_metrics

        return usage_totals_for_metrics()
    except Exception:
        return {}


def _llm_breaker_snapshot() -> Dict[str, Dict[str, object]]:
    try:
        from services.llm_resilience import breaker_snapshots

        return breaker_snapshots()
    except Exception:
        return {}


def _ai_review_pending() -> Optional[float]:
    """待人工复核的 AI 结果数量（查询失败时不输出该指标）。"""
    try:
        from services.ai_review_service import pending_count

        return float(pending_count())
    except Exception:
        return None


def _background_task_snapshot() -> Dict[str, Any]:
    try:
        from database import SessionLocal
        from services.task_queue_service import pending_count, stats
        from services.task_worker_service import worker_stats

        db = SessionLocal()
        try:
            return {"pending": pending_count(), "stats": stats(db), "worker": worker_stats()}
        finally:
            db.close()
    except Exception:
        return {}


def render_prometheus() -> str:
    """输出 Prometheus 文本格式指标。"""
    with _lock:
        http_requests = dict(_http_requests)
        duration_sum = dict(_http_duration_sum)
        duration_count = dict(_http_duration_count)
        counters = dict(_counters)

    lines: List[str] = []

    _metric(lines, "fire_ai_up", "应用存活状态（1=运行中）", "gauge")
    lines.append("fire_ai_up 1")
    _metric(lines, "fire_ai_uptime_seconds", "进程已运行秒数", "gauge")
    lines.append(f"fire_ai_uptime_seconds {round(time.time() - _STARTED_AT, 3)}")
    _metric(lines, "fire_ai_database_ready", "数据库连通性（1=可连接）", "gauge")
    lines.append(f"fire_ai_database_ready {1 if _database_ready() else 0}")

    _metric(lines, "fire_ai_http_requests_total", "HTTP 请求总数", "counter")
    for (method, path, status), count in sorted(http_requests.items()):
        lines.append(
            f'fire_ai_http_requests_total{{method="{_escape(method)}",'
            f'path="{_escape(path)}",status="{_escape(status)}"}} {count}'
        )

    _metric(lines, "fire_ai_http_request_duration_seconds_sum", "HTTP 请求耗时累计（秒）", "counter")
    for (method, path), total in sorted(duration_sum.items()):
        lines.append(
            f'fire_ai_http_request_duration_seconds_sum{{method="{_escape(method)}",'
            f'path="{_escape(path)}"}} {round(total, 6)}'
        )
    _metric(lines, "fire_ai_http_request_duration_seconds_count", "HTTP 请求计数", "counter")
    for (method, path), count in sorted(duration_count.items()):
        lines.append(
            f'fire_ai_http_request_duration_seconds_count{{method="{_escape(method)}",'
            f'path="{_escape(path)}"}} {count}'
        )

    _metric(lines, "fire_ai_business_events_total", "业务事件计数", "counter")
    for name, value in sorted(counters.items()):
        lines.append(f'fire_ai_business_events_total{{event="{_escape(name)}"}} {value:g}')

    mqtt = _mqtt_snapshot()
    if mqtt:
        _metric(lines, "fire_ai_mqtt_enabled", "MQTT 接入是否启用（1=启用）", "gauge")
        lines.append(f"fire_ai_mqtt_enabled {1 if mqtt.get('enabled') else 0}")
        _metric(lines, "fire_ai_mqtt_connected", "MQTT 是否已连接（1=已连接）", "gauge")
        lines.append(f"fire_ai_mqtt_connected {1 if mqtt.get('connected') else 0}")
        _metric(lines, "fire_ai_mqtt_messages_total", "MQTT 消息处理计数", "counter")
        for key in ("received", "accepted", "rejected"):
            lines.append(f'fire_ai_mqtt_messages_total{{result="{key}"}} {int(mqtt.get(key) or 0)}')

    backup_age = _backup_age_seconds()
    if backup_age is not None:
        _metric(lines, "fire_ai_backup_age_seconds", "最近一次数据库备份距今秒数", "gauge")
        lines.append(f"fire_ai_backup_age_seconds {round(backup_age, 1)}")

    llm = _llm_usage_snapshot()
    if llm:
        _metric(lines, "fire_ai_llm_calls_total", "近 24 小时大模型调用次数", "gauge")
        lines.append(f'fire_ai_llm_calls_total{{status="success"}} {int(max(llm.get("calls", 0) - llm.get("failed", 0), 0))}')
        lines.append(f'fire_ai_llm_calls_total{{status="failed"}} {int(llm.get("failed", 0))}')
        _metric(lines, "fire_ai_llm_circuit_open_total", "近 24 小时因熔断被拒绝的调用次数", "gauge")
        lines.append(f'fire_ai_llm_circuit_open_total {int(llm.get("circuit_open", 0))}')
        _metric(lines, "fire_ai_llm_tokens_total", "近 24 小时大模型 token 消耗", "gauge")
        lines.append(f'fire_ai_llm_tokens_total {int(llm.get("tokens", 0))}')
        _metric(lines, "fire_ai_llm_cost_usd_total", "近 24 小时大模型费用估算（USD）", "gauge")
        lines.append(f'fire_ai_llm_cost_usd_total {round(float(llm.get("cost", 0.0)), 6)}')

    breakers = _llm_breaker_snapshot()
    state_code = {"closed": 0, "half-open": 1, "open": 2}
    if breakers:
        _metric(lines, "fire_ai_llm_breaker_state", "模型供应商熔断器状态（0=closed 1=half-open 2=open）", "gauge")
        for name, snap in sorted(breakers.items()):
            state = str(snap.get("state") or "closed")
            lines.append(
                f'fire_ai_llm_breaker_state{{provider="{_escape(name)}"}} {state_code.get(state, 0)}'
            )

    pending_review = _ai_review_pending()
    if pending_review is not None:
        _metric(lines, "fire_ai_review_pending", "待人工复核的 AI 结果数量", "gauge")
        lines.append(f"fire_ai_review_pending {int(pending_review)}")

    tasks = _background_task_snapshot()
    if tasks:
        _metric(lines, "fire_ai_background_tasks", "后台任务数量（按状态）", "gauge")
        for status, count in sorted((tasks.get("stats") or {}).get("by_status", {}).items()):
            lines.append(f'fire_ai_background_tasks{{status="{_escape(status)}"}} {int(count)}')
        _metric(lines, "fire_ai_task_worker_running", "后台任务 worker 是否在运行（1=运行中）", "gauge")
        lines.append(f"fire_ai_task_worker_running {1 if (tasks.get('worker') or {}).get('running') else 0}")
        _metric(lines, "fire_ai_task_worker_failed_total", "worker 启动以来失败的任务数", "counter")
        lines.append(f"fire_ai_task_worker_failed_total {int((tasks.get('worker') or {}).get('failed') or 0)}")

    return "\n".join(lines) + "\n"


def metrics_authorized(provided_token: Optional[str], client_host: str = "") -> bool:
    """判断是否允许读取指标。"""
    if METRICS_TOKEN:
        return bool(provided_token) and provided_token == METRICS_TOKEN
    if IS_PRODUCTION:
        return False
    return True


class MetricsMiddleware:
    """记录每个 HTTP 请求的计数与耗时。"""

    def __init__(self, app, exclude_paths=("/metrics", "/health", "/ready")):
        self.app = app
        self.exclude_paths = set(exclude_paths)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status_holder["status"] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            observe_http(
                scope.get("method", "GET"),
                path,
                status_holder["status"],
                time.perf_counter() - started,
            )
