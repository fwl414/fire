"""GB28181 设备/通道注册表（复用 `video_channels` 表）

不新增表：一台国标设备与它的通道都用 `video_channels` 表示，靠三个字段区分——

    platform     = 'gb28181'
    gb_device_id = 国标 20 位编码（设备自身或通道自身）
    parent_gb_id = 空表示「设备」节点，否则指向所属设备

这样「国标视频」与既有的海康/通用接入在同一张台账里，页面与权限也复用同一套。
运行态（注册有效期、最后心跳、远端地址、事务）放内存，重启后靠重新注册恢复。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from database import VideoChannel, get_default_tenant_id

PLATFORM = "gb28181"


@dataclass
class DeviceRuntime:
    """国标设备的运行态（内存）。"""

    gb_id: str
    remote_ip: str = ""
    remote_port: int = 0
    transport: str = "udp"
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_keepalive_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    firmware: str = ""
    channel_count: int = 0
    catalog_synced_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gb_id": self.gb_id,
            "remote": f"{self.remote_ip}:{self.remote_port}" if self.remote_ip else "",
            "transport": self.transport,
            "registered_at": self.registered_at.isoformat(),
            "last_keepalive_at": self.last_keepalive_at.isoformat() if self.last_keepalive_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "firmware": self.firmware,
            "channel_count": self.channel_count,
            "catalog_synced_at": self.catalog_synced_at.isoformat() if self.catalog_synced_at else None,
        }


_devices: Dict[str, DeviceRuntime] = {}


def default_expires_seconds() -> int:
    try:
        return int(os.environ.get("GB28181_REGISTER_EXPIRES", "3600"))
    except (TypeError, ValueError):
        return 3600


def register(
    gb_id: str,
    *,
    remote_ip: str = "",
    remote_port: int = 0,
    transport: str = "udp",
    expires: Optional[int] = None,
) -> DeviceRuntime:
    """记录（或刷新）设备注册。"""
    runtime = _devices.get(gb_id) or DeviceRuntime(gb_id=gb_id)
    runtime.remote_ip = remote_ip or runtime.remote_ip
    runtime.remote_port = remote_port or runtime.remote_port
    runtime.transport = transport
    runtime.registered_at = datetime.utcnow()
    if expires:
        runtime.expires_at = datetime.utcnow() + timedelta(seconds=max(60, expires))
    elif not runtime.expires_at:
        runtime.expires_at = datetime.utcnow() + timedelta(seconds=default_expires_seconds())
    _devices[gb_id] = runtime
    return runtime


def keepalive(gb_id: str) -> DeviceRuntime:
    runtime = _devices.get(gb_id) or register(gb_id)
    runtime.last_keepalive_at = datetime.utcnow()
    runtime.expires_at = datetime.utcnow() + timedelta(seconds=default_expires_seconds())
    return runtime


def unregister(gb_id: str) -> None:
    _devices.pop(gb_id, None)


def runtime_of(gb_id: str) -> Optional[DeviceRuntime]:
    return _devices.get(gb_id)


def is_online(gb_id: str) -> bool:
    runtime = _devices.get(gb_id)
    if not runtime:
        return False
    if runtime.expires_at and runtime.expires_at <= datetime.utcnow():
        return False
    return True


def online_snapshot() -> List[Dict[str, Any]]:
    return [runtime.to_dict() for runtime in _devices.values()]


def device_address(gb_id: str) -> str:
    """设备 SIP 地址（用于主动下发 INVITE / MESSAGE）。"""
    runtime = _devices.get(gb_id)
    if not runtime:
        return ""
    return f"sip:{gb_id}@{runtime.remote_ip}:{runtime.remote_port}"


# ---------------- 台账读写（video_channels） ----------------

def _tenant_id(db: Session) -> Optional[int]:
    return get_default_tenant_id(db)


def upsert_device(
    db: Session,
    gb_id: str,
    *,
    name: str = "",
    manufacturer: str = "",
    model: str = "",
    remote_ip: str = "",
    remote_port: int = 0,
) -> VideoChannel:
    """登记/更新一台国标设备（`parent_gb_id` 为空的行）。

    型号复用既有 `device_model` 列（与海康/通用接入共用同一字段），不再新增同义列。
    """
    row = (
        db.query(VideoChannel)
        .filter(VideoChannel.platform == PLATFORM, VideoChannel.gb_device_id == gb_id, VideoChannel.parent_gb_id == "")
        .first()
    )
    if not row:
        row = VideoChannel(
            tenant_id=_tenant_id(db),
            platform=PLATFORM,
            channel_code=gb_id,
            gb_device_id=gb_id,
            parent_gb_id="",
        )
        db.add(row)
    if name:
        row.channel_name = name
    elif not row.channel_name:
        row.channel_name = f"国标设备 {gb_id}"
    if manufacturer:
        row.manufacturer = manufacturer
    if model:
        row.device_model = model
    if remote_ip:
        row.host = remote_ip
    if remote_port:
        row.port = remote_port
    row.enabled = True
    row.status = "online"
    row.sip_register_at = datetime.utcnow()
    row.last_probe_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def upsert_channels(db: Session, device_gb_id: str, items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """按目录应答写入/更新通道，返回 {created, updated}。

    目录里可能出现设备自身的条目（ParentID 为空或等于设备编码），这类条目跳过，
    避免把设备当通道。
    """
    tenant_id = _tenant_id(db)
    created = updated = 0
    seen: List[str] = []
    for item in items:
        channel_id = (item.get("device_id") or "").strip()
        parent = (item.get("parent_id") or "").strip() or device_gb_id
        if not channel_id or channel_id == device_gb_id:
            continue
        seen.append(channel_id)
        row = (
            db.query(VideoChannel)
            .filter(VideoChannel.platform == PLATFORM, VideoChannel.gb_device_id == channel_id)
            .first()
        )
        if not row:
            row = VideoChannel(
                tenant_id=tenant_id,
                platform=PLATFORM,
                channel_code=channel_id,
                gb_device_id=channel_id,
                channel_no="1",
            )
            db.add(row)
            created += 1
        else:
            updated += 1
        row.parent_gb_id = parent
        row.channel_name = item.get("name") or row.channel_name or f"国标通道 {channel_id}"
        row.manufacturer = item.get("manufacturer") or row.manufacturer
        row.device_model = item.get("model") or row.device_model
        row.location = item.get("address") or row.location
        if item.get("ip_address"):
            row.host = item["ip_address"]
        try:
            row.port = int(item.get("port") or row.port or 0) or row.port
        except (TypeError, ValueError):
            pass
        row.status = "online" if (item.get("status") or "").upper() == "ON" else "offline"
        row.enabled = True
        row.updated_at = datetime.utcnow()

    # 目录里消失的通道标记为离线，而不是删除（保留历史抓拍与告警关联）
    stale = (
        db.query(VideoChannel)
        .filter(VideoChannel.platform == PLATFORM, VideoChannel.parent_gb_id == device_gb_id)
        .all()
    )
    for row in stale:
        if row.gb_device_id not in seen:
            row.status = "offline"
    db.commit()
    return {"created": created, "updated": updated}


def list_devices(db: Session, tenant_id: Optional[int] = None) -> List[VideoChannel]:
    query = db.query(VideoChannel).filter(VideoChannel.platform == PLATFORM, VideoChannel.parent_gb_id == "")
    if tenant_id is not None:
        query = query.filter(VideoChannel.tenant_id == tenant_id)
    return query.order_by(VideoChannel.id.asc()).all()


def get_device(db: Session, device_id: int, tenant_id: Optional[int] = None) -> Optional[VideoChannel]:
    query = db.query(VideoChannel).filter(
        VideoChannel.id == device_id,
        VideoChannel.platform == PLATFORM,
        VideoChannel.parent_gb_id == "",
    )
    if tenant_id is not None:
        query = query.filter(VideoChannel.tenant_id == tenant_id)
    return query.first()


def get_channel(db: Session, channel_id: int, tenant_id: Optional[int] = None) -> Optional[VideoChannel]:
    query = db.query(VideoChannel).filter(
        VideoChannel.id == channel_id,
        VideoChannel.platform == PLATFORM,
    )
    if tenant_id is not None:
        query = query.filter(VideoChannel.tenant_id == tenant_id)
    return query.first()


def list_channels(db: Session, device: VideoChannel) -> List[VideoChannel]:
    return (
        db.query(VideoChannel)
        .filter(
            VideoChannel.platform == PLATFORM,
            VideoChannel.parent_gb_id == (device.gb_device_id or ""),
        )
        .order_by(VideoChannel.id.asc())
        .all()
    )


def device_by_gb_id(db: Session, gb_id: str) -> Optional[VideoChannel]:
    return (
        db.query(VideoChannel)
        .filter(VideoChannel.platform == PLATFORM, VideoChannel.gb_device_id == gb_id, VideoChannel.parent_gb_id == "")
        .first()
    )


def owning_device(db: Session, channel: VideoChannel) -> Optional[VideoChannel]:
    if not channel.parent_gb_id:
        return None
    return device_by_gb_id(db, channel.parent_gb_id)


# ---------------- 视图 ----------------

def device_view(row: VideoChannel) -> Dict[str, Any]:
    runtime = runtime_of(row.gb_device_id or "")
    return {
        "id": row.id,
        "gb_device_id": row.gb_device_id,
        "name": row.channel_name,
        "manufacturer": row.manufacturer or "",
        "model": row.device_model or "",
        "remote": f"{row.host}:{row.port}" if row.host else "",
        "status": row.status,
        "online": is_online(row.gb_device_id or ""),
        "channel_no": row.channel_no or "",
        "sip_register_at": row.sip_register_at.isoformat() if row.sip_register_at else None,
        "remark": row.remark or "",
        "runtime": runtime.to_dict() if runtime else None,
    }


def channel_view(db: Session, row: VideoChannel) -> Dict[str, Any]:
    device = owning_device(db, row)
    return {
        "id": row.id,
        "gb_device_id": row.gb_device_id,
        "name": row.channel_name,
        "parent_gb_id": row.parent_gb_id or "",
        "device_id": device.id if device else None,
        "device_name": device.channel_name if device else "",
        "manufacturer": row.manufacturer or "",
        "model": row.device_model or "",
        "location": row.location or "",
        "host": row.host or "",
        "port": row.port,
        "status": row.status,
        "enabled": bool(row.enabled),
        "ptz_enabled": bool(row.ptz_enabled),
        "stream_id": stream_id_of(row),
        "last_error": row.last_error or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def stream_id_of(row: VideoChannel) -> str:
    """ZLMediaKit 里该通道的流 ID（用国标通道编码，便于与设备侧对账）。"""
    return row.gb_device_id or row.channel_code or f"channel{row.id}"


def rtp_stream_id(gb_id: str) -> str:
    return gb_id
