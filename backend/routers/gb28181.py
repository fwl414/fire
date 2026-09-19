"""GB28181 视频接入路由

信令与媒体由 services/gb28181 的常驻服务提供（SIP 5060 + ZLMediaKit），
这里只做台账查询、点播/停流/云台等平台侧动作。权限与既有视频平台一致（devices:manage）。
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from database import User, get_db
from services.auth_service import get_current_user, require_permission
from services.gb28181 import device_registry as registry
from services.gb28181 import media_proxy, service
from services.video_platform.base import PTZ_ACTIONS

router = APIRouter(tags=["GB28181 视频接入"])


def _require_device(db: Session, device_id: int, tenant_id: int):
    row = registry.get_device(db, device_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="国标设备不存在")
    return row


def _require_channel(db: Session, channel_id: int, tenant_id: int):
    row = registry.get_channel(db, channel_id, tenant_id)
    if not row or not row.gb_device_id:
        raise HTTPException(status_code=404, detail="国标通道不存在")
    device = registry.owning_device(db, row)
    if not device:
        raise HTTPException(status_code=409, detail="该通道未关联到已注册的国标设备")
    return row, device


@router.get("/api/gb28181/devices")
def api_list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """已注册的国标设备列表（含注册运行态：远端地址、最后心跳、通道数）。"""
    rows = registry.list_devices(db, current_user.tenant_id)
    return {"items": [registry.device_view(row) for row in rows], "total": len(rows)}


@router.get("/api/gb28181/devices/{device_id}/channels")
def api_list_device_channels(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """某台国标设备下的通道列表（目录应答写入的台账）。"""
    device = _require_device(db, device_id, current_user.tenant_id)
    rows = registry.list_channels(db, device)
    return {
        "device": registry.device_view(device),
        "items": [registry.channel_view(db, row) for row in rows],
        "total": len(rows),
    }


@router.post("/api/gb28181/devices/{device_id}/refresh-catalog")
def api_refresh_catalog(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    """向设备下发目录查询（MESSAGE/Catalog），并尽量等待目录回传。"""
    device = _require_device(db, device_id, current_user.tenant_id)
    if not device.gb_device_id:
        raise HTTPException(status_code=409, detail="该设备缺少国标编码")
    result = service.refresh_catalog(device.gb_device_id)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message") or "目录查询下发失败")
    return {"device": registry.device_view(device), **result}


@router.post("/api/gb28181/channels/{channel_id}/play")
def api_play_channel(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    """发起点播（INVITE → 设备推 RTP 到 ZLMediaKit），返回 HLS/FLV/WebRTC 播放地址。

    `prefer` 仅影响返回给前端的首选地址（hls / flv / webrtc），三种地址都会返回。
    """
    channel, device = _require_channel(db, channel_id, current_user.tenant_id)
    prefer = str(payload.get("prefer") or "flv").strip().lower()
    if prefer not in ("hls", "flv", "webrtc"):
        raise HTTPException(status_code=400, detail="prefer 只支持 hls / flv / webrtc")

    result = service.start_play(channel.gb_device_id, device.gb_device_id)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message") or "点播失败")

    urls = result.get("urls") or {}
    return {
        "channel": registry.channel_view(db, channel),
        **result,
        "prefer": prefer,
        "preferred_url": urls.get(prefer, ""),
    }


@router.post("/api/gb28181/channels/{channel_id}/stop")
def api_stop_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    """停止点播（BYE）。"""
    channel, _device = _require_channel(db, channel_id, current_user.tenant_id)
    result = service.stop_play(channel.gb_device_id)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message") or "停流失败")
    return {"channel": registry.channel_view(db, channel), **result}


@router.post("/api/gb28181/channels/{channel_id}/ptz")
def api_channel_ptz(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    """云台控制（MESSAGE/DeviceControl）。

    默认按 `action` 生成 PTZCmd；厂商位序不同时可直接传 `ptz_cmd`（8 字节十六进制）覆盖。
    """
    channel, device = _require_channel(db, channel_id, current_user.tenant_id)
    action = str(payload.get("action") or "").strip().lower()
    raw_cmd = str(payload.get("ptz_cmd") or "").strip()
    if not raw_cmd and action not in PTZ_ACTIONS:
        raise HTTPException(status_code=400, detail=f"不支持的云台动作：{action or '空'}")
    try:
        speed = int(payload.get("speed") or 5)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="speed 必须是数字")

    result = service.send_ptz(channel.gb_device_id, device.gb_device_id, action=action, speed=speed, raw_cmd=raw_cmd)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message") or "云台指令下发失败")
    return {"channel": registry.channel_view(db, channel), **result}


@router.get("/api/gb28181/channels/{channel_id}/stream-info")
def api_channel_stream_info(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """该通道的取流地址与当前会话状态（未点播时也返回地址模板，便于前端预置播放器）。"""
    channel, _device = _require_channel(db, channel_id, current_user.tenant_id)
    return {
        "channel": registry.channel_view(db, channel),
        "urls": media_proxy.play_urls(channel.gb_device_id or ""),
        "dialog": service.active_dialog(channel.gb_device_id or ""),
        "media_enabled": media_proxy.enabled(),
    }


@router.get("/api/gb28181/status")
def api_status(
    current_user: User = Depends(get_current_user),
):
    """SIP 服务运行状态：监听端口、平台编码、已注册设备、进行中的点播会话与统计。"""
    return service.service_status()
