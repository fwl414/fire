from __future__ import annotations

import json
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db
from services.common_utils import GlobalExceptionMiddleware, register_exception_handlers
from services.llm_usage_service import LlmCallContextMiddleware
from services.metrics_service import MetricsMiddleware
from services.operation_log_middleware import OperationLogMiddleware
from services.rate_limit_middleware import RateLimitMiddleware

load_dotenv()

ENV = os.environ.get("ENV", "development").lower()
IS_PRODUCTION = ENV in ("production", "prod")

if IS_PRODUCTION:
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "")
    if len(jwt_secret) < 32:
        raise RuntimeError("生产环境必须设置至少32字节的 JWT_SECRET_KEY")
    if os.environ.get("DEMO_MODE", "false").lower() == "true":
        raise RuntimeError("生产环境禁止启用 DEMO_MODE")
    if os.environ.get("DEBUG", "false").lower() == "true":
        raise RuntimeError("生产环境禁止启用 DEBUG")
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("生产环境必须使用受支持的共享数据库，禁止使用 SQLite")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库、演示数据与后台任务。"""
    init_db()
    if IS_PRODUCTION:
        # 生产分支只做「让系统可用」的最小初始化（租户/系统角色/首个管理员），
        # 不写任何演示业务数据；开发分支的 seed_data 已包含同等内容，故不重复调用。
        from database import SessionLocal
        from services.baseline_seed import run_if_empty
        from services.runtime_lock_service import run_exclusive

        def _seed_baseline() -> None:
            db = SessionLocal()
            try:
                run_if_empty(db)
            finally:
                db.close()

        # 多实例部署时避免各实例重复播种初始数据
        run_exclusive("startup_baseline_seed", _seed_baseline, ttl_seconds=180)
    else:
        from database import SessionLocal
        from routers.maintenance import init_maintenance_data
        from routers.business_ext import init_business_data
        from services.hardware_event_service import _seed_if_empty as seed_hardware_events
        from services.runtime_lock_service import run_exclusive

        def _seed_demo_all() -> None:
            db = SessionLocal()
            try:
                init_maintenance_data(db)
                init_business_data(db)
                seed_hardware_events(db)
            finally:
                db.close()

        # 多实例部署时避免各实例重复播种演示数据
        run_exclusive("startup_seed_demo", _seed_demo_all, ttl_seconds=180)
    from services.mqtt_ingest_service import start_mqtt, stop_mqtt
    from services.task_worker_service import start_worker, stop_worker
    from services.gb26875 import start_gb26875_server, stop_gb26875_server
    from services.gb28181 import start_gb28181_sip, stop_gb28181_sip
    start_mqtt()
    start_gb26875_server()
    start_gb28181_sip()
    # 后台任务 worker 必须在事件循环内启动（asyncio.create_task 需要运行中的 loop）
    start_worker()
    try:
        yield
    finally:
        # 关停必须放在 finally 里，否则应用异常退出时后台服务不会停止
        await stop_worker()
        stop_mqtt()
        stop_gb28181_sip()
        stop_gb26875_server()


app = FastAPI(
    title="智慧消防管理系统 API",
    version="1.0.0",
    lifespan=lifespan,
    description="""
智慧消防管理系统后端API接口文档。

## 功能模块

- **认证管理**：登录、登出、用户信息、权限管理
- **建筑管理**：建筑档案、楼层平面图、风险评估
- **消防设备**：设备管理、设备数据、故障管理
- **巡检管理**：巡检计划、巡检记录、批量巡检
- **维保管理**：维保单位、维保计划、维保记录
- **值班管理**：值班排班、值班记录、交接班
- **重点单位**：重点单位管理、监督检查
- **应急指挥**：应急预案、应急物资、应急队伍、疏散路线
- **告警中心**：告警管理、告警处理
- **工单管理**：工单创建、工单处理、工单跟踪
- **知识库**：消防知识管理、知识检索
- **系统管理**：用户管理、角色管理、字典管理、组织管理
- **操作日志**：系统操作记录、审计日志
    """,
    contact={
        "name": "系统管理员",
        "email": "admin@example.com",
    },
    license_info={
        "name": "Proprietary License",
    },
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
    tags_metadata=[
        {"name": "认证管理", "description": "用户登录、登出、token刷新等认证相关接口"},
        {"name": "用户管理", "description": "用户CRUD、角色分配等用户管理接口"},
        {"name": "角色管理", "description": "角色CRUD、权限配置等角色管理接口"},
        {"name": "建筑管理", "description": "建筑档案、楼层平面图、风险评估"},
        {"name": "消防设备", "description": "设备管理、设备数据采集、故障管理"},
        {"name": "巡检管理", "description": "巡检计划、巡检执行、巡检记录"},
        {"name": "维保管理", "description": "维保单位、维保计划、维保记录、超期预警"},
        {"name": "值班管理", "description": "值班排班、值班记录、交接班管理"},
        {"name": "重点单位", "description": "重点单位档案、监督检查记录"},
        {"name": "应急指挥", "description": "应急预案、应急物资、应急队伍、疏散路线"},
        {"name": "告警中心", "description": "告警接收、告警处理、告警统计"},
        {"name": "工单管理", "description": "工单创建、派单、处理、验收"},
        {"name": "知识库", "description": "消防知识文档管理、分类检索"},
        {"name": "系统管理", "description": "字典管理、组织管理、系统监控"},
        {"name": "操作日志", "description": "操作日志查询、审计追踪"},
        {"name": "通知消息", "description": "系统通知、消息推送"},
        {"name": "健康检查", "description": "系统健康状态检查"},
    ],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
# 上传内容不再通过静态目录对外暴露，统一经 /api/files/{id} 受控下载

_cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
if _cors_origins_raw:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
else:
    if IS_PRODUCTION:
        _cors_origins = []
    else:
        _cors_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(OperationLogMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    ip_limit=1000,
    ip_window=60,
    user_limit=500,
    user_window=60,
    exempt_paths=["/api/auth/login", "/api/auth/logout", "/health"],
)
# 指标中间件最后注册 => 位于最外层，可采集到包含限流/异常处理后的最终状态码
app.add_middleware(MetricsMiddleware)
# 大模型调用归因上下文：注册在最外层，保证内层路由（含线程池中的同步路由）都能读到
app.add_middleware(LlmCallContextMiddleware)

from sqlalchemy import text as sa_text
from database import SessionLocal


@app.get("/health", tags=["运维"])
def health_check():
    """服务健康检查 - 含数据库连通性，公开访问

    `instance_id` 用于多实例部署时确认请求落到了哪个实例（负载均衡是否生效）。
    """
    from services.runtime_lock_service import instance_id
    from services.storage_service import describe as describe_storage
    from services.task_worker_service import worker_stats
    from services.gb26875 import service_status as gb26875_status
    from services.gb28181 import service_status as gb28181_status

    checks = {"api": "ok"}
    try:
        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    all_ok = all(v == "ok" for v in checks.values())

    worker = worker_stats()
    gb26875 = gb26875_status()
    gb28181 = gb28181_status()
    return {
        "status": "healthy" if all_ok else "degraded",
        "version": "v1.0.0",
        "instance_id": instance_id(),
        "checks": checks,
        "worker": {"enabled": worker["enabled"], "running": worker["running"]},
        "gb26875": {
            "enabled": gb26875["enabled"],
            "running": gb26875["running"],
            "listen": gb26875["listen"],
            "connections": len(gb26875["connections"]),
            "received": gb26875["received"],
            "accepted": gb26875["accepted"],
            "denied": gb26875["denied"],
            "errors": gb26875["errors"],
            "last_frame_at": gb26875["last_frame_at"],
        },
        "gb28181": {
            "enabled": gb28181["enabled"],
            "running": gb28181["running"],
            "listen": gb28181["listen"],
            "server_id": gb28181["server_id"],
            "registered_devices": len(gb28181["registered_devices"]),
            "dialogs": len(gb28181["dialogs"]),
            "received": gb28181["received"],
            "register_ok": gb28181["register_ok"],
            "register_denied": gb28181["register_denied"],
            "errors": gb28181["errors"],
            "last_frame_at": gb28181["last_frame_at"],
        },
        "storage": describe_storage(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# 注册各模块路由
from routers import agent_api
from routers import ai_review
from routers import alert
from routers import intelligence
from routers import auth
from routers import building
from routers import building_detail
from routers import business
from routers import business_ext
from routers import competition
from routers import dashboard
from routers import demo
from routers import device
from routers import device_ingest
from routers import evaluation
from routers import files
from routers import floor
from routers import gb26875
from routers import gb28181
from routers import gis
from routers import hardware
from routers import inspection
from routers import knowledge
from routers import knowledge_graph
from routers import learning
from routers import maintenance
from routers import metrics
from routers import mobile
from routers import multimodal
from routers import notification
from routers import notification_channels
from routers import operation_log
from routers import product
from routers import report_center
from routers import report_verify
from routers import risk
from routers import settings
from routers import system
from routers import tasks
from routers import tenant
from routers import training
from routers import user
from routers import video
from routers import websocket_api
from routers import workorder

app.include_router(agent_api.router)
app.include_router(ai_review.router)
app.include_router(alert.router)
app.include_router(intelligence.router)
app.include_router(auth.public_router)
app.include_router(auth.router)
app.include_router(building.router)
app.include_router(building_detail.router)
app.include_router(business.router)
app.include_router(business_ext.router)
app.include_router(competition.router)
app.include_router(dashboard.router)
if not IS_PRODUCTION:
    app.include_router(demo.router)
app.include_router(device.router)
app.include_router(device_ingest.router)
app.include_router(evaluation.router)
app.include_router(files.router)
app.include_router(floor.router)
app.include_router(gb26875.router)
app.include_router(gb28181.router)
app.include_router(gis.router)
app.include_router(hardware.router)
app.include_router(inspection.router)
app.include_router(knowledge.router)
app.include_router(knowledge_graph.router)
app.include_router(learning.router)
app.include_router(maintenance.router)
app.include_router(metrics.router)
app.include_router(mobile.router)
app.include_router(multimodal.router)
app.include_router(notification.router)
app.include_router(notification_channels.router)
app.include_router(operation_log.router)
app.include_router(product.router)
app.include_router(report_center.router)
app.include_router(report_verify.router)
app.include_router(risk.router)
app.include_router(settings.router)
app.include_router(system.router)
app.include_router(tasks.router)
app.include_router(tenant.router)
app.include_router(training.router)
app.include_router(user.router)
app.include_router(video.router)
app.include_router(websocket_api.router)
app.include_router(websocket_api.ws_router)
app.include_router(workorder.router)


register_exception_handlers(app)
