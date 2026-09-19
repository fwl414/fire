"""设备接入路由

提供两条通道：
1. 设备直连 HTTP（HMAC 签名认证，不依赖用户 JWT）
2. MQTT（由 services/mqtt_ingest_service 订阅，见 GET /api/device-ingest/protocol）

同时提供设备凭证的管理接口（用户 JWT + devices:manage 权限）。
"""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import Device, User, get_db
from services import device_message_service as device_inbox
from services import task_queue_service as task_queue
from services.auth_service import get_current_tenant_id, get_current_user, require_permission
from services.device_auth_service import (
    DeviceAuthError,
    device_credentials_status,
    issue_device_credentials,
    revoke_device_credentials,
    verify_device_request,
)
from services.device_ingest_service import ingest_event, ingest_heartbeat, ingest_telemetry
from services.mqtt_ingest_service import (
    DEVICE_MESSAGE_MAX_ATTEMPTS,
    DEVICE_MESSAGE_TASK,
    mqtt_stats,
    subscription_topics,
)
from services.telemetry_analyzer import TELEMETRY_RULES

router = APIRouter(tags=["设备接入"])

DEVICE_KINDS = ("telemetry", "event", "heartbeat")


async def require_device_identity(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """设备身份依赖：校验设备签名（密钥 + 时间戳 + nonce），返回设备与请求数据。"""
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    try:
        device = verify_device_request(
            db,
            device_code=request.headers.get("X-Device-Code", ""),
            timestamp=request.headers.get("X-Device-Timestamp", ""),
            nonce=request.headers.get("X-Device-Nonce", ""),
            signature=request.headers.get("X-Device-Signature", ""),
            payload_bytes=raw_body,
        )
    except DeviceAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return {"device": device, "payload": payload, "raw_body": raw_body}


@router.post("/api/device-ingest/telemetry")
async def device_ingest_telemetry(
    context: Dict[str, Any] = Depends(require_device_identity),
    db: Session = Depends(get_db),
):
    """设备遥测上报：写入遥测并触发阈值告警与工单。"""
    device: Device = context["device"]
    try:
        result = ingest_telemetry(db, device, context["payload"], source="http")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, **result}


@router.post("/api/device-ingest/event")
async def device_ingest_event(
    context: Dict[str, Any] = Depends(require_device_identity),
    db: Session = Depends(get_db),
):
    """设备事件上报：直接生成告警与工单。"""
    device: Device = context["device"]
    result = ingest_event(db, device, context["payload"], source="http")
    return {"ok": True, **result}


@router.post("/api/device-ingest/heartbeat")
async def device_ingest_heartbeat(
    context: Dict[str, Any] = Depends(require_device_identity),
    db: Session = Depends(get_db),
):
    """设备心跳：刷新在线状态与最后上报时间。"""
    device: Device = context["device"]
    result = ingest_heartbeat(db, device, context["payload"], source="http")
    return {"ok": True, **result}


# ---------------- 设备凭证管理（用户 JWT + devices:manage） ----------------

def _owned_device(db: Session, device_id: int, tenant_id: int) -> Device:
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.post("/api/devices/{device_id}/credentials")
def api_issue_device_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """签发（或轮换）设备接入密钥；明文密钥仅本次返回。"""
    device = _owned_device(db, device_id, tenant_id)
    secret = issue_device_credentials(db, device)
    return {
        "message": "设备凭证已签发，请立即保存，密钥不会再次展示",
        "device": device_credentials_status(device),
        "device_secret": secret,
        "signature_algorithm": "HMAC-SHA256",
    }


@router.get("/api/devices/{device_id}/credentials")
def api_get_device_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """查看设备接入凭证状态（密钥脱敏）。"""
    device = _owned_device(db, device_id, tenant_id)
    return device_credentials_status(device)


@router.delete("/api/devices/{device_id}/credentials")
def api_revoke_device_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """吊销设备密钥并关闭接入。"""
    device = _owned_device(db, device_id, tenant_id)
    revoke_device_credentials(db, device)
    return {"message": "设备凭证已吊销", "device": device_credentials_status(device)}


@router.post("/api/devices/{device_id}/ingest-toggle")
def api_toggle_device_ingest(
    device_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """启用或禁用设备接入（不影响已有凭证）。"""
    device = _owned_device(db, device_id, tenant_id)
    device.ingest_enabled = bool(payload.get("enabled", True))
    db.commit()
    db.refresh(device)
    return {"message": "设备接入状态已更新", "device": device_credentials_status(device)}


# ---------------- 协议说明与接入状态 ----------------

@router.get("/api/device-ingest/protocol")
def api_device_ingest_protocol(
    current_user: User = Depends(get_current_user),
):
    """设备接入协议说明（HTTP 与 MQTT 的签名规则、主题规范、字段定义）。"""
    return {
        "version": "1.0",
        "authentication": {
            "algorithm": "HMAC-SHA256",
            "credential": "设备密钥（由 POST /api/devices/{id}/credentials 签发）",
            "signature_base": "f\"{device_code}\\n{timestamp}\\n{nonce}\\n{sha256(payload_bytes)}\"",
            "replay_protection": {
                "timestamp_window_seconds": 300,
                "nonce": "每次请求必须唯一，服务端保留期内重复即拒绝",
            },
        },
        "http": {
            "endpoints": {
                "telemetry": "POST /api/device-ingest/telemetry",
                "event": "POST /api/device-ingest/event",
                "heartbeat": "POST /api/device-ingest/heartbeat",
            },
            "headers": {
                "X-Device-Code": "设备编码",
                "X-Device-Timestamp": "Unix 秒级时间戳",
                "X-Device-Nonce": "随机串，建议 16 字节以上",
                "X-Device-Signature": "HMAC-SHA256 十六进制小写",
            },
            "payload_bytes": "请求体原始字节（签名对象）",
        },
        "mqtt": {
            "enabled": mqtt_stats()["enabled"],
            "topic_pattern": "{prefix}/{tenant_id}/{device_code}/{kind}",
            "topic_prefix": mqtt_stats()["topic_prefix"],
            "subscriptions": subscription_topics(),
            "envelope": {
                "timestamp": "Unix 秒级时间戳",
                "nonce": "随机串",
                "signature": "HMAC-SHA256 十六进制小写",
                "data": "业务数据对象",
            },
            "payload_bytes": "data 字段的规范 JSON：json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))",
        },
        "metrics": [
            {
                "key": metric,
                "unit": rule["unit"],
                "normal_range": list(rule["normal_range"]),
                "hazard_type": rule["hazard_type"],
            }
            for metric, rule in TELEMETRY_RULES.items()
        ],
        "telemetry_aliases": {
            "temperature": ["temperature", "temp"],
            "smoke": ["smoke"],
            "co": ["co"],
            "battery_level": ["battery", "battery_level"],
            "current": ["current"],
            "voltage": ["voltage"],
            "pressure": ["pressure"],
            "remaining_current": ["remaining_current", "leakage"],
        },
        "event_types": ["fire", "smoke", "temperature", "fault", "offline", "manual"],
    }


@router.get("/api/device-ingest/stats")
def api_device_ingest_stats(
    current_user: User = Depends(get_current_user),
):
    """MQTT 接入运行状态与消息统计。"""
    return mqtt_stats()


@router.post("/api/device-ingest/simulate")
def api_device_ingest_simulate(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """以指定设备身份模拟一次上报，用于联调与验收（跳过签名校验）。"""
    device_id = payload.get("device_id")
    kind = str(payload.get("kind") or "telemetry")
    if kind not in DEVICE_KINDS:
        raise HTTPException(status_code=400, detail=f"不支持的接入类型：{kind}")
    if not device_id:
        raise HTTPException(status_code=400, detail="需要提供 device_id")

    device = _owned_device(db, int(device_id), tenant_id)
    data = payload.get("data") or {}
    if kind == "telemetry":
        return {"ok": True, **ingest_telemetry(db, device, data, source="http")}
    if kind == "event":
        return {"ok": True, **ingest_event(db, device, data, source="http")}
    return {"ok": True, **ingest_heartbeat(db, device, data, source="http")}


# ---------------- 设备消息收件箱（幂等 / 削峰 / 死信） ----------------


@router.get("/api/device-messages")
def api_list_device_messages(
    status: str = "",
    device_code: str = "",
    kind: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """设备上报消息列表，可按状态/设备/类型筛选（status=dead 即死信）。"""
    return {
        "items": device_inbox.list_messages(
            db, tenant_id, status=status, device_code=device_code, kind=kind, limit=limit
        )
    }


@router.get("/api/device-messages/stats")
def api_device_message_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """收件箱各状态数量，用于判断是否有积压或死信。"""
    return device_inbox.stats(db, tenant_id)


@router.post("/api/device-messages/{message_row_id}/replay")
def api_replay_device_message(
    message_row_id: int,
    payload: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """人工重放失败或死信消息（重新入队执行）。"""
    row = device_inbox.get_message(db, tenant_id, message_row_id)
    if not row:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    if row.status == device_inbox.STATUS_PROCESSED:
        raise HTTPException(status_code=409, detail="消息已处理成功，无需重放")

    if not device_inbox.requeue(db, row):
        raise HTTPException(status_code=409, detail="该消息当前状态不支持重放")

    task = task_queue.enqueue(
        db,
        task_type=DEVICE_MESSAGE_TASK,
        payload={"message_id": row.message_id},
        tenant_id=row.tenant_id,
        task_name=f"设备消息重放 {row.device_code}/{row.kind}",
        total_items=1,
        max_attempts=(payload or {}).get("max_attempts") or DEVICE_MESSAGE_MAX_ATTEMPTS,
        created_by=current_user.id,
        created_by_name=current_user.username or "",
    )
    return {"message": "已重新入队", "task_id": task.task_id, "message_id": row.message_id}
