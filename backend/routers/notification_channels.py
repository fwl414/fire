"""告警外部通知通道管理（仅管理员）

通道配置存在 `notification_channels` 表（见 services/alert_notify_service.py）：
群机器人 Webhook、SMTP 口令等密钥字段加密落库，接口只回掩码。
与 `/api/settings/*` 其余接口一致，整个路由要求 admin 角色。
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from database import User, get_db
from services import alert_notify_service as notify
from services.auth_service import get_current_tenant_id, get_current_user, require_role

router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_role("admin"))],
    tags=["通知通道"],
)


@router.get("/api/settings/notification-channels")
def api_list_channels(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """已配置的外部通知通道 + 表单元数据（通道类型、可选级别）。"""
    rows = notify.list_channels(db, tenant_id)
    return {
        "items": [notify.serialize(row) for row in rows],
        "total": len(rows),
        "types": notify.channel_types(),
        "severity_levels": notify.severity_levels(),
        "notify_enabled": notify.notify_enabled(),
        "max_attempts": notify.max_attempts(),
    }


@router.post("/api/settings/notification-channels")
def api_create_channel(
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """新增通道。密钥字段（群机器人地址、SMTP 口令）加密落库，不回传明文。"""
    try:
        channel = notify.create_channel(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "通知通道已创建", "channel": notify.serialize(channel)}


@router.put("/api/settings/notification-channels/{channel_id}")
def api_update_channel(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """更新通道；密钥字段留空或传掩码表示「保持不变」。"""
    channel = notify.get_channel(db, tenant_id, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="通知通道不存在")
    try:
        channel = notify.update_channel(db, channel, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "通知通道已更新", "channel": notify.serialize(channel)}


@router.post("/api/settings/notification-channels/{channel_id}/toggle")
def api_toggle_channel(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """启用 / 停用通道（停用后不再匹配新告警，历史投递记录保留）。"""
    channel = notify.get_channel(db, tenant_id, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="通知通道不存在")
    channel = notify.update_channel(db, channel, {"enabled": bool(payload.get("enabled", True))})
    return {"message": "通道状态已更新", "channel": notify.serialize(channel)}


@router.post("/api/settings/notification-channels/{channel_id}/test")
def api_test_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """立即发送一条测试消息，验证通道配置是否真的可达。"""
    channel = notify.get_channel(db, tenant_id, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="通知通道不存在")
    try:
        excerpt = notify.send_test(db, channel)
    except notify.NotificationSendError as exc:
        raise HTTPException(status_code=409, detail=f"测试发送失败：{exc}")
    return {"message": "测试消息已发送", "response_excerpt": excerpt[:500]}


@router.delete("/api/settings/notification-channels/{channel_id}")
def api_delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """删除通道（投递台账保留，便于回溯历史通知）。"""
    channel = notify.get_channel(db, tenant_id, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="通知通道不存在")
    notify.delete_channel(db, channel)
    return {"message": "通知通道已删除"}


@router.get("/api/settings/notification-deliveries")
def api_list_deliveries(
    channel_id: int = 0,
    alert_code: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """最近的通知投递记录（排查「告警产生了但没收到通知」）。"""
    rows = notify.list_deliveries(
        db, tenant_id, channel_id=channel_id or None, alert_code=alert_code, limit=limit
    )
    return {"items": [notify.delivery_view(row) for row in rows], "total": len(rows)}
