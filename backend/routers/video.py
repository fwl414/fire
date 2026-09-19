"""视频平台接入接口

- 台账维护：真实保存摄像头/NVR 的地址、通道、账号（密码加密落库，接口不回传）
- 能力探测：真实发起 ISAPI / CGI / HTTP 抓拍请求，回写在线状态
- 画面获取：抓拍图经短时令牌受控下发，供 <img> 轮询，避免浏览器直连设备
- 云台控制：按平台能力下发（通用适配器不支持时明确报错）
- 智能识别：抓拍 → 视觉识别 → 告警/工单，并复用 AI 人工复核闸门
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from database import User, get_db
from services import video_service
from services.auth_service import get_current_user, require_permission
from services.video_platform import PTZ_ACTIONS, VideoPlatformError, list_platforms

router = APIRouter(tags=["视频接入"])


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, VideoPlatformError):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


def _require_channel(db: Session, tenant_id: Optional[int], channel_id: int):
    row = video_service.get_channel(db, tenant_id, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="视频通道不存在")
    return row


@router.get("/api/video/platforms")
def api_platforms(current_user: User = Depends(get_current_user)):
    """支持的视频平台与各自能力，供前端渲染接入表单。"""
    return {
        "platforms": list_platforms(),
        "ptz_actions": list(PTZ_ACTIONS),
        "playback": {
            "mode": "snapshot_polling",
            "description": "当前以抓拍图轮询提供准实时画面；浏览器无法直接播放 RTSP。",
            "recording_search": (
                "按时间段检索录像片段的能力因平台而异："
                "海康 ISAPI 已实现，其余平台调用检索接口会返回 supported=false。"
            ),
        },
    }


@router.get("/api/video/channels")
def api_list_channels(
    keyword: str = Query(""),
    enabled_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = video_service.list_channels(
        db, current_user.tenant_id, enabled_only=enabled_only, keyword=keyword
    )
    return {
        "items": [video_service.serialize_channel(row) for row in rows],
        "total": len(rows),
    }


@router.post("/api/video/channels")
def api_create_channel(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    try:
        row = video_service.create_channel(db, current_user.tenant_id, payload)
    except (VideoPlatformError, ValueError) as exc:
        raise _translate(exc)
    return video_service.serialize_channel(row)


@router.get("/api/video/channels/{channel_id}")
def api_get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _require_channel(db, current_user.tenant_id, channel_id)
    return video_service.serialize_channel(row)


@router.put("/api/video/channels/{channel_id}")
def api_update_channel(
    channel_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    try:
        row = video_service.update_channel(db, current_user.tenant_id, channel_id, payload)
    except (VideoPlatformError, ValueError) as exc:
        raise _translate(exc)
    if not row:
        raise HTTPException(status_code=404, detail="视频通道不存在")
    return video_service.serialize_channel(row)


@router.delete("/api/video/channels/{channel_id}")
def api_delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    if not video_service.delete_channel(db, current_user.tenant_id, channel_id):
        raise HTTPException(status_code=404, detail="视频通道不存在")
    return {"message": "deleted"}


@router.post("/api/video/channels/{channel_id}/probe")
async def api_probe_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    """真实连接设备读取信息，并回写在线状态。"""
    row = _require_channel(db, current_user.tenant_id, channel_id)
    return await video_service.probe_channel(db, row)


@router.post("/api/video/channels/{channel_id}/snapshot-token")
def api_snapshot_token(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """签发短时抓拍令牌，用于 <img> 这类不能带请求头的场景。"""
    row = _require_channel(db, current_user.tenant_id, channel_id)
    return video_service.issue_snapshot_token(row, user=current_user)


@router.get("/api/video/channels/{channel_id}/snapshot")
async def api_snapshot(
    channel_id: int,
    token: str = Query(..., description="由 /snapshot-token 签发的短时令牌"),
    fresh: bool = Query(False, description="跳过缓存强制重新抓拍"),
    db: Session = Depends(get_db),
):
    """返回抓拍图。鉴权走短时令牌，避免把设备凭证暴露给浏览器。"""
    try:
        payload = video_service.verify_snapshot_token(token, channel_id)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    row = _require_channel(db, payload.get("tenant_id"), channel_id)
    try:
        data, mime = await video_service.get_snapshot(db, row, use_cache=not fresh)
    except (VideoPlatformError, ValueError) as exc:
        raise _translate(exc)

    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": f"private, max-age={int(video_service.SNAPSHOT_CACHE_SECONDS)}",
            "X-Video-Channel": row.channel_code or "",
        },
    )


@router.post("/api/video/channels/{channel_id}/ptz")
async def api_ptz(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    action = str(payload.get("action") or "").strip().lower()
    if action not in PTZ_ACTIONS:
        raise HTTPException(status_code=400, detail=f"不支持的云台动作：{action or '空'}")
    try:
        speed = int(payload.get("speed") or 5)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="speed 必须是数字") from exc

    row = _require_channel(db, current_user.tenant_id, channel_id)
    try:
        return await video_service.control_ptz(db, row, action, speed)
    except (VideoPlatformError, ValueError) as exc:
        raise _translate(exc)


@router.get("/api/video/channels/{channel_id}/stream-info")
def api_stream_info(
    channel_id: int,
    reveal: bool = Query(False, description="是否返回完整取流地址（含账号信息）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    row = _require_channel(db, current_user.tenant_id, channel_id)
    return video_service.stream_info(row, reveal=reveal)


@router.post("/api/video/channels/{channel_id}/recordings/search")
async def api_search_recordings(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按时间段检索该通道的录像片段。

    平台能力不同：海康走 ISAPI 真实检索；其余平台返回 `supported=False`，
    界面据此显示「该平台未提供录像检索」，而不是显示一个空列表让人误以为没有录像。
    """
    row = _require_channel(db, current_user.tenant_id, channel_id)
    start = str(payload.get("start_time") or "").strip()
    end = str(payload.get("end_time") or "").strip()
    if not start or not end:
        raise HTTPException(status_code=400, detail="start_time 与 end_time 不能为空")

    try:
        limit = int(payload.get("limit") or 100)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="limit 必须是整数")

    try:
        return await video_service.search_recordings(row, start=start, end=end, limit=limit)
    except (VideoPlatformError, ValueError) as exc:
        raise _translate(exc)


@router.post("/api/video/channels/{channel_id}/analyze")
async def api_analyze(
    channel_id: int,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
):
    """抓拍一帧做视觉识别；识别到隐患时生成告警，必要时转人工复核。"""
    row = _require_channel(db, current_user.tenant_id, channel_id)
    create_alert = bool(payload.get("create_alert", True))
    try:
        return await video_service.analyze_snapshot(
            db, row, tenant_id=current_user.tenant_id, user=current_user, create_alert=create_alert
        )
    except (VideoPlatformError, ValueError) as exc:
        raise _translate(exc)
