"""视频通道接入服务

职责：
- 视频通道台账的增删改查（凭证加密存储、接口一律脱敏）
- 通过平台适配器做真实连通性探测、抓拍、云台控制
- 抓拍图受控下发：短时令牌 + 进程内 TTL 缓存，避免多个浏览器把摄像头打满
- 抓拍 → 视觉识别 → 告警/工单，并复用人工复核闸门

浏览器无法直接播放 RTSP，因此实时预览以"抓拍图轮询"实现，取流信息如实返回但不假装可播。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import jwt
from sqlalchemy.orm import Session

from database import VideoChannel
from services import video_credential_cipher as cipher
from services.ai_review_service import (
    CONFIDENCE_LABELS,
    assess_confidence,
    create_review_task,
    needs_manual_review,
)
from services.alert_lifecycle_service import ingest_alert, persist_alert_workorder
from services.auth_service import ALGORITHM, SECRET_KEY
from services.metrics_service import incr
from services.risk_engine import calculate_risk
from services.upload_archive_service import resolve_upload_path, save_upload
from services.video_platform import (
    SUPPORTED_PLATFORMS,
    ProbeResult,
    VideoChannelConfig,
    VideoPlatformError,
    detect_image_type,
    get_adapter,
    platform_meta,
    supports_ptz,
)

PROBE_TIMEOUT_SECONDS = float(os.environ.get("VIDEO_PROBE_TIMEOUT_SECONDS", "10"))
SNAPSHOT_TIMEOUT_SECONDS = float(os.environ.get("VIDEO_SNAPSHOT_TIMEOUT_SECONDS", "10"))
SNAPSHOT_CACHE_SECONDS = float(os.environ.get("VIDEO_SNAPSHOT_CACHE_SECONDS", "3"))
SNAPSHOT_TOKEN_TTL_SECONDS = int(os.environ.get("VIDEO_SNAPSHOT_TOKEN_SECONDS", "3600"))
SNAPSHOT_TOKEN_TYPE = "video_snapshot"

ALLOWED_PROTOCOLS = ("http", "https")
ALLOWED_STREAM_SCHEMES = ("rtsp://", "rtsps://")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

SEVERITY_BY_RISK_LEVEL = {
    "严重风险": "critical",
    "高风险": "high",
    "中风险": "medium",
    "低风险": "low",
}

# 进程内抓拍缓存：同一通道在 TTL 内共享一张图，key -> {at, data, mime}
_snapshot_cache: Dict[int, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


# ---------------- 凭证与配置 ----------------


def build_config(row: VideoChannel) -> VideoChannelConfig:
    """把台账行转成适配器配置（此处才会解密密码）。"""
    try:
        password = cipher.decrypt_secret(row.password_cipher or "")
    except cipher.CredentialCipherError as exc:
        raise VideoPlatformError(str(exc), status_code=400) from exc

    return VideoChannelConfig(
        id=row.id,
        channel_code=row.channel_code or "",
        channel_name=row.channel_name or "",
        location=row.location or "",
        platform=row.platform or "generic",
        protocol=(row.protocol or "http").lower(),
        host=row.host or "",
        port=int(row.port or 80),
        channel_no=str(row.channel_no or "1"),
        username=row.username or "",
        password=password,
        snapshot_path=row.snapshot_path or "",
        rtsp_url=row.rtsp_url or "",
        ptz_enabled=bool(row.ptz_enabled),
        verify_tls=bool(row.verify_tls),
    )


def mask_stream_url(url: str) -> str:
    """把 RTSP 地址中的账号密码替换为 ***。"""
    if not url:
        return ""
    return re.sub(r"://([^:/@]+):([^@]+)@", "://***:***@", url)


def serialize_channel(row: VideoChannel, *, reveal_stream: bool = False) -> Dict[str, Any]:
    meta = platform_meta(row.platform)
    return {
        "id": row.id,
        "channel_code": row.channel_code,
        "channel_name": row.channel_name or "",
        "location": row.location or "",
        "platform": row.platform,
        "platform_label": meta.get("label", row.platform),
        "capabilities": meta.get("capabilities", []),
        "protocol": row.protocol or "http",
        "host": row.host or "",
        "port": row.port or 80,
        "channel_no": row.channel_no or "1",
        "username": row.username or "",
        "has_password": bool(row.password_cipher),
        "snapshot_path": row.snapshot_path or "",
        "rtsp_url": (row.rtsp_url or "") if reveal_stream else mask_stream_url(row.rtsp_url or ""),
        "ptz_enabled": bool(row.ptz_enabled),
        "ptz_supported": supports_ptz(row.platform),
        "verify_tls": bool(row.verify_tls),
        "enabled": bool(row.enabled),
        "status": row.status or "unknown",
        "device_model": row.device_model or "",
        "device_id": row.device_id,
        "building_id": row.building_id,
        "remark": row.remark or "",
        "last_probe_at": row.last_probe_at.isoformat() if row.last_probe_at else "",
        "last_snapshot_at": row.last_snapshot_at.isoformat() if row.last_snapshot_at else "",
        "last_error": row.last_error or "",
        "snapshot_endpoint": f"/api/video/channels/{row.id}/snapshot",
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


# ---------------- 台账 CRUD ----------------


def get_channel(db: Session, tenant_id: Optional[int], channel_id: int) -> Optional[VideoChannel]:
    return db.query(VideoChannel).filter(
        VideoChannel.id == channel_id,
        VideoChannel.tenant_id == tenant_id,
    ).first()


def list_channels(
    db: Session,
    tenant_id: Optional[int],
    *,
    enabled_only: bool = False,
    keyword: str = "",
) -> List[VideoChannel]:
    query = db.query(VideoChannel).filter(VideoChannel.tenant_id == tenant_id)
    if enabled_only:
        query = query.filter(VideoChannel.enabled == True)  # noqa: E712 - SQLAlchemy 需要显式比较
    keyword = (keyword or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            VideoChannel.channel_name.like(like)
            | VideoChannel.channel_code.like(like)
            | VideoChannel.location.like(like)
        )
    return query.order_by(VideoChannel.channel_code.asc()).all()


def _clean_host(value: str) -> str:
    host = (value or "").strip()
    if not host:
        raise ValueError("设备地址不能为空")
    if "://" in host or "/" in host:
        raise ValueError("设备地址只填主机名或 IP，不要带协议或路径")
    if not HOST_PATTERN.match(host):
        raise ValueError("设备地址含非法字符")
    return host


def _clean_snapshot_path(value: str) -> str:
    path = (value or "").strip()
    if not path:
        return ""
    if "://" in path or path.startswith("//"):
        raise ValueError("抓拍路径只填路径（如 /snap.jpg），不要带协议和主机，避免被用作跳转")
    if not path.startswith("/"):
        path = "/" + path
    return path


def _clean_rtsp_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(ALLOWED_STREAM_SCHEMES):
        raise ValueError("取流地址必须以 rtsp:// 或 rtsps:// 开头")
    return url


def _clean_port(value: Any, protocol: str) -> int:
    if value in (None, ""):
        return 443 if protocol == "https" else 80
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("端口必须是数字") from exc
    if not 1 <= port <= 65535:
        raise ValueError("端口范围应在 1-65535")
    return port


def apply_payload(
    db: Session,
    row: VideoChannel,
    payload: Dict[str, Any],
    *,
    tenant_id: Optional[int],
) -> VideoChannel:
    """把请求体写入台账行（新建与更新共用），含字段校验与凭证加密。"""
    text_fields = ("channel_name", "location", "username", "remark", "device_model")
    for field in text_fields:
        if field in payload:
            setattr(row, field, str(payload.get(field) or "").strip())

    if "channel_code" in payload:
        row.channel_code = str(payload.get("channel_code") or "").strip()

    if "platform" in payload:
        platform = str(payload.get("platform") or "").strip()
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"不支持的视频平台「{platform}」，可选：{'/'.join(SUPPORTED_PLATFORMS)}")
        row.platform = platform

    if "protocol" in payload:
        protocol = str(payload.get("protocol") or "http").strip().lower()
        if protocol not in ALLOWED_PROTOCOLS:
            raise ValueError("协议只能是 http 或 https")
        row.protocol = protocol

    if "host" in payload:
        row.host = _clean_host(str(payload.get("host") or ""))

    if "port" in payload or "protocol" in payload:
        row.port = _clean_port(payload.get("port", row.port), row.protocol or "http")

    if "channel_no" in payload:
        channel_no = str(payload.get("channel_no") or "1").strip() or "1"
        if not channel_no.isdigit():
            raise ValueError("通道号必须是数字")
        row.channel_no = channel_no

    if "snapshot_path" in payload:
        row.snapshot_path = _clean_snapshot_path(str(payload.get("snapshot_path") or ""))

    if "rtsp_url" in payload:
        row.rtsp_url = _clean_rtsp_url(str(payload.get("rtsp_url") or ""))

    if "ptz_enabled" in payload:
        enabled = bool(payload.get("ptz_enabled"))
        if enabled and not supports_ptz(row.platform or "generic"):
            raise ValueError(f"{platform_meta(row.platform).get('label')} 适配器暂不支持云台控制")
        row.ptz_enabled = enabled

    if "verify_tls" in payload:
        row.verify_tls = bool(payload.get("verify_tls"))

    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))

    for numeric_field in ("device_id", "building_id"):
        if numeric_field in payload:
            value = payload.get(numeric_field)
            setattr(row, numeric_field, int(value) if value not in (None, "") else None)

    # 密码：字段缺省表示保持不变，显式传空串表示清除
    if "password" in payload:
        raw_password = payload.get("password")
        row.password_cipher = cipher.encrypt_secret(str(raw_password)) if raw_password else ""

    if not row.channel_code:
        raise ValueError("通道编码不能为空")

    duplicated = db.query(VideoChannel).filter(
        VideoChannel.tenant_id == tenant_id,
        VideoChannel.channel_code == row.channel_code,
        VideoChannel.id != (row.id or 0),
    ).first()
    if duplicated:
        raise ValueError(f"通道编码「{row.channel_code}」已存在")

    return row


def create_channel(db: Session, tenant_id: Optional[int], payload: Dict[str, Any]) -> VideoChannel:
    row = VideoChannel(tenant_id=tenant_id, channel_code="", platform="generic", protocol="http", port=80)
    apply_payload(db, row, payload, tenant_id=tenant_id)
    row.status = "unknown"
    db.add(row)
    db.commit()
    db.refresh(row)
    incr("video_channel_created")
    return row


def update_channel(
    db: Session,
    tenant_id: Optional[int],
    channel_id: int,
    payload: Dict[str, Any],
) -> Optional[VideoChannel]:
    row = get_channel(db, tenant_id, channel_id)
    if not row:
        return None
    apply_payload(db, row, payload, tenant_id=tenant_id)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    clear_snapshot_cache(channel_id)
    return row


def delete_channel(db: Session, tenant_id: Optional[int], channel_id: int) -> bool:
    row = get_channel(db, tenant_id, channel_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    clear_snapshot_cache(channel_id)
    incr("video_channel_deleted")
    return True


# ---------------- 抓拍缓存 ----------------


def _cache_get(channel_id: int) -> Optional[Tuple[bytes, str]]:
    with _cache_lock:
        entry = _snapshot_cache.get(channel_id)
    if not entry:
        return None
    if time.time() - entry["at"] > SNAPSHOT_CACHE_SECONDS:
        return None
    return entry["data"], entry["mime"]


def _cache_put(channel_id: int, data: bytes, mime: str) -> None:
    with _cache_lock:
        _snapshot_cache[channel_id] = {"at": time.time(), "data": data, "mime": mime}


def clear_snapshot_cache(channel_id: Optional[int] = None) -> None:
    with _cache_lock:
        if channel_id is None:
            _snapshot_cache.clear()
        else:
            _snapshot_cache.pop(channel_id, None)


# ---------------- 真实设备交互 ----------------


def _record_probe(db: Session, row: VideoChannel, result: ProbeResult) -> None:
    row.status = "online" if result.online else "offline"
    row.last_probe_at = datetime.utcnow()
    row.last_error = "" if result.online else (result.message or "探测失败")[:255]
    if result.device_model:
        row.device_model = result.device_model[:128]
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    incr("video_probe_success" if result.online else "video_probe_failed")


async def probe_channel(db: Session, row: VideoChannel, *, client=None) -> Dict[str, Any]:
    """真实发起一次设备探测，并回写台账状态。"""
    try:
        config = build_config(row)
        adapter = get_adapter(config, client=client, timeout=PROBE_TIMEOUT_SECONDS)
        result = await adapter.probe()
    except VideoPlatformError as exc:
        result = ProbeResult(online=False, message=str(exc))

    _record_probe(db, row, result)
    return {
        "channel_id": row.id,
        "online": result.online,
        "status": row.status,
        "device_name": result.device_name,
        "device_model": result.device_model,
        "firmware": result.firmware,
        "channels": result.channels,
        "message": result.message,
        "probed_at": row.last_probe_at.isoformat() if row.last_probe_at else "",
    }


async def get_snapshot(
    db: Session,
    row: VideoChannel,
    *,
    use_cache: bool = True,
    client=None,
) -> Tuple[bytes, str]:
    """获取抓拍图；带 TTL 缓存，避免多路轮询把设备打满。"""
    if not row.enabled:
        raise VideoPlatformError("该视频通道已停用", status_code=400)

    if use_cache:
        cached = _cache_get(row.id)
        if cached:
            return cached

    config = build_config(row)
    adapter = get_adapter(config, client=client, timeout=SNAPSHOT_TIMEOUT_SECONDS)
    try:
        data = await adapter.snapshot()
    except VideoPlatformError as exc:
        if row.status != "offline" or row.last_error != str(exc)[:255]:
            row.status = "offline"
            row.last_error = str(exc)[:255]
            db.commit()
        incr("video_snapshot_failed")
        raise

    mime = detect_image_type(data) or "image/jpeg"
    _cache_put(row.id, data, mime)
    now = datetime.utcnow()
    if row.status != "online" or row.last_error:
        row.status = "online"
        row.last_error = ""
        row.updated_at = now
        db.commit()
    row.last_snapshot_at = now
    incr("video_snapshot_success")
    return data, mime


async def control_ptz(
    db: Session,
    row: VideoChannel,
    action: str,
    speed: int = 5,
    *,
    client=None,
) -> Dict[str, Any]:
    if not row.ptz_enabled:
        raise VideoPlatformError("该通道未启用云台控制，请先在台账中开启", status_code=400)
    if not supports_ptz(row.platform):
        raise VideoPlatformError(
            f"{platform_meta(row.platform).get('label')} 适配器不支持云台控制", status_code=400
        )

    config = build_config(row)
    adapter = get_adapter(config, client=client, timeout=PROBE_TIMEOUT_SECONDS)
    result = await adapter.ptz(action, speed)
    incr("video_ptz_command")
    return {"channel_id": row.id, **result}


async def search_recordings(
    row: VideoChannel,
    *,
    start: str,
    end: str,
    limit: int = 100,
    client=None,
) -> Dict[str, Any]:
    """按时间段检索某通道的录像片段。

    平台能力差异如实返回：海康走 ISAPI 真实检索，其余平台 `supported=False`，
    由界面显示「该平台未提供录像检索」。**不做「没查到就补几条」的兜底** ——
    空列表（真没有录像）与不支持（查不了）是两件事。
    """
    config = build_config(row)
    adapter = get_adapter(config, client=client, timeout=PROBE_TIMEOUT_SECONDS)
    result = await adapter.query_recordings(start, end, limit=limit)
    if result.get("supported"):
        incr("video_recording_search")
    result.update({
        "channel_id": row.id,
        "channel_code": row.channel_code,
        "channel_name": row.channel_name,
        "location": row.location or "",
        "platform": row.platform,
        "platform_label": platform_meta(row.platform).get("label") or row.platform,
        # 设备返回的 playbackURI 通常是 RTSP，浏览器不能直接播
        "playable_in_browser": False,
    })
    return result


def stream_info(row: VideoChannel, *, reveal: bool = False) -> Dict[str, Any]:
    rtsp = row.rtsp_url or ""
    return {
        "channel_id": row.id,
        "rtsp_url": rtsp if reveal else mask_stream_url(rtsp),
        "masked": not reveal,
        "playable_in_browser": False,
        "note": (
            "浏览器不能直接播放 RTSP。实时预览需部署流媒体网关（如 ZLMediaKit）转 HLS/FLV；"
            "当前版本使用抓拍图轮询提供准实时画面，取流地址可用于录像机或第三方平台的二次接入。"
        ),
    }


# ---------------- 抓拍令牌 ----------------


def issue_snapshot_token(row: VideoChannel, *, user=None, ttl: Optional[int] = None) -> Dict[str, Any]:
    """签发短时抓拍令牌，供 <img> 标签这类无法携带请求头的场景使用。"""
    lifetime = int(ttl or SNAPSHOT_TOKEN_TTL_SECONDS)
    now = datetime.utcnow()
    payload = {
        "sub": str(getattr(user, "id", "") or ""),
        "username": getattr(user, "username", "") or "",
        "tenant_id": row.tenant_id or 0,
        "channel_id": row.id,
        "type": SNAPSHOT_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(seconds=lifetime),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {
        "token": token,
        "expires_in": lifetime,
        "snapshot_url": f"/api/video/channels/{row.id}/snapshot?token={token}",
    }


def verify_snapshot_token(token: str, channel_id: int) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as exc:  # noqa: BLE001 - 统一转成鉴权失败
        raise PermissionError("抓拍令牌无效或已过期") from exc

    if payload.get("type") != SNAPSHOT_TOKEN_TYPE:
        raise PermissionError("令牌类型不正确")
    try:
        token_channel = int(payload.get("channel_id") or 0)
    except (TypeError, ValueError) as exc:
        raise PermissionError("抓拍令牌缺少通道信息") from exc
    if token_channel != int(channel_id):
        raise PermissionError("抓拍令牌与通道不匹配")

    return payload


# ---------------- 抓拍 → 识别 → 告警 ----------------


async def analyze_snapshot(
    db: Session,
    row: VideoChannel,
    *,
    tenant_id: Optional[int],
    user=None,
    create_alert: bool = True,
    client=None,
) -> Dict[str, Any]:
    """抓拍一张图做视觉识别，必要时生成告警与工单。

    识别链路结果沿用 AI 人工复核闸门：置信度不足或高风险时只生成待复核任务，
    由人工确认后才下发工单，避免本地兜底产生的假隐患自动进入处置流程。
    """
    from services.image_analyzer import analyze_image

    data, mime = await get_snapshot(db, row, client=client)
    ext = ".png" if mime == "image/png" else ".jpg"
    record = save_upload(
        db,
        tenant_id=tenant_id,
        category="video_snapshot",
        content=data,
        ext=ext,
        media_type=mime,
        original_name=f"{row.channel_code}{ext}",
        owner_id=getattr(user, "id", None),
        owner_name=getattr(user, "username", "") or "",
    )
    path = resolve_upload_path(record)
    if not path:
        raise VideoPlatformError("抓拍图片落盘失败，无法进行识别", status_code=500)

    analysis = await analyze_image(db, str(path))
    hazards = [str(item) for item in (analysis.get("hazards") or []) if item]
    confidence = assess_confidence(
        used_vision_api=bool(analysis.get("used_vision_api")),
        vision_error=analysis.get("vision_error") or "",
        requested_modalities=1,
    )
    risk = calculate_risk(hazards) if hazards else {"risk_score": 0, "risk_level": "低风险"}

    result: Dict[str, Any] = {
        "channel_id": row.id,
        "channel_code": row.channel_code,
        "upload_id": record.id,
        "snapshot_url": f"/api/files/{record.id}",
        "hazards": hazards,
        "description": analysis.get("description") or "",
        "risk_reasons": analysis.get("risk_reasons") or [],
        "risk_score": risk.get("risk_score", 0),
        "risk_level": risk.get("risk_level", "低风险"),
        "confidence": confidence,
        "confidence_label": CONFIDENCE_LABELS.get(confidence, confidence),
        "used_vision_api": bool(analysis.get("used_vision_api")),
        "vision_error": analysis.get("vision_error") or "",
        "alert_id": None,
        "alert_code": "",
        "dedup_action": "",
        "review_required": False,
        "review_task_id": None,
        "review_reason": "",
        "ticket_id": None,
    }

    if not hazards or not create_alert:
        return result

    severity = SEVERITY_BY_RISK_LEVEL.get(risk.get("risk_level", ""), "medium")
    agent_analysis = json.dumps({
        "source": "视频平台接入",
        "platform": row.platform,
        "channel": row.channel_code,
        "hazards": hazards,
        "description": analysis.get("description") or "",
        "risk_reasons": analysis.get("risk_reasons") or [],
        "confidence": confidence,
        "used_vision_api": bool(analysis.get("used_vision_api")),
        "vision_error": analysis.get("vision_error") or "",
    }, ensure_ascii=False)

    outcome = ingest_alert(
        db,
        tenant_id=tenant_id,
        alert_type="video_hazard",
        severity=severity,
        description=f"{row.channel_name or row.channel_code} 视频识别到隐患：{'、'.join(hazards)}",
        device_id=row.device_id,
        device_code=row.channel_code,
        device_name=row.channel_name or row.channel_code,
        building_id=row.building_id,
        location=row.location or "",
        agent_analysis=agent_analysis,
        device_info={
            "code": row.channel_code,
            "name": row.channel_name or row.channel_code,
            "type": "视频通道",
            "location": row.location or "",
            "source": "视频平台接入",
            "platform": row.platform,
        },
    )

    result["alert_id"] = outcome["alert"].id
    result["alert_code"] = outcome["alert"].alert_code
    result["dedup_action"] = outcome["action"]

    review_required, review_reason = needs_manual_review(
        risk_level=risk.get("risk_level", ""),
        confidence=confidence,
    )
    result["review_required"] = review_required
    result["review_reason"] = review_reason

    if review_required:
        task = create_review_task(
            db,
            tenant_id=tenant_id,
            source="video",
            record_id=record.id,
            risk_level=risk.get("risk_level", ""),
            risk_score=risk.get("risk_score", 0),
            hazards=hazards,
            confidence=confidence,
            reason=review_reason,
            ai_summary=analysis.get("description") or "",
            location=row.location or "",
        )
        db.commit()
        result["review_task_id"] = task.id
        incr("video_hazard_detected")
        return result

    ticket = persist_alert_workorder(
        db,
        tenant_id=tenant_id,
        alert=outcome["alert"],
        workorder={
            "title": f"{row.channel_name or row.channel_code} 视频识别隐患整改工单",
            "recommended_action": (
                f"视频识别到隐患：{'、'.join(hazards)}；"
                f"风险等级 {risk.get('risk_level')}（{risk.get('risk_score')} 分）。请现场核实并整改。"
            ),
            "risk_level": risk.get("risk_level", ""),
        },
        reporter_id=getattr(user, "id", None),
        reporter_name=getattr(user, "username", "") or "视频平台接入",
    )
    result["ticket_id"] = ticket.id if ticket else None
    incr("video_hazard_detected")
    return result
