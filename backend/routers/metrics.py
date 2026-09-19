"""可观测性端点：Prometheus 指标与就绪探针

- GET /metrics  供 Prometheus 抓取（访问控制见 services/metrics_service）
- GET /ready    就绪探针，用于滚动发布与负载均衡摘除
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from database import User, engine
from services import metrics_service
from services.auth_service import get_current_user

router = APIRouter(tags=["可观测性"])


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics(request: Request):
    provided = request.headers.get("X-Metrics-Token") or request.query_params.get("token")
    if not metrics_service.metrics_authorized(provided):
        raise HTTPException(
            status_code=403,
            detail="指标端点未授权，请配置 METRICS_TOKEN 并在抓取请求中携带",
        )
    return PlainTextResponse(
        metrics_service.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/ready")
def readiness():
    """就绪探针：数据库可连通才视为就绪。"""
    database_ready = False
    error = ""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database_ready = True
    except Exception as exc:  # 依赖不可用时返回 503，避免流量被导入
        error = str(exc)

    payload = {"status": "ready" if database_ready else "not-ready", "database": database_ready}
    if error:
        payload["error"] = error
    if not database_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/api/system/metrics-summary")
def metrics_summary(current_user: User = Depends(get_current_user)):
    """便于前端/运维快速查看关键计数（需登录，保持与其他业务接口一致）。"""
    from services.metrics_service import counter_value

    keys = [
        "login_failed",
        "login_locked",
        "alert_created",
        "alert_merged",
        "alert_escalated",
        "workorder_created",
        "device_ingest_telemetry",
        "device_ingest_event",
        "device_ingest_heartbeat",
    ]
    return {
        "metrics_token_configured": bool(metrics_service.METRICS_TOKEN),
        "counters": {k: counter_value(k) for k in keys},
    }


# ---------------- 系统监控页的真实指标 ----------------
# 这些接口替代 SystemMonitor.vue 原来的随机数模拟；实现见 services/system_metrics_service


@router.get("/api/system/host")
def system_host(current_user: User = Depends(get_current_user)):
    """主机实时指标（CPU / 内存 / 磁盘 / 网络）+ 本次启动以来的趋势采样点。"""
    from services.system_metrics_service import host_snapshot

    return host_snapshot()


@router.get("/api/system/processes")
def system_processes(limit: int = 8, current_user: User = Depends(get_current_user)):
    """按 CPU 占用排序的进程列表。"""
    from services.system_metrics_service import process_snapshot

    return process_snapshot(limit=max(1, min(limit, 50)))


@router.get("/api/system/database")
def system_database(current_user: User = Depends(get_current_user)):
    """数据库真实状态：连通性、库大小、连接池、各表行数。"""
    from services.system_metrics_service import database_snapshot

    return database_snapshot()


@router.get("/api/system/api-stats")
def system_api_stats(limit: int = 10, current_user: User = Depends(get_current_user)):
    """接口监控：本进程启动以来的真实请求计数与平均耗时。"""
    from services.system_metrics_service import api_snapshot

    return api_snapshot(limit=max(1, min(limit, 200)))
