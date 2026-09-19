"""GB28181 视频接入（SIP 信令 + ZLMediaKit 媒体分发）

组成：

    sip_stack.py        最小化 SIP 报文解析/构造、Digest 认证、SDP
    catalog.py          GB28181 XML（目录/设备信息/报警）解析与查询、云台命令构造
    device_registry.py  设备与通道台账（复用 video_channels 表）+ 运行态
    media_proxy.py      ZLMediaKit HTTP API（开 RTP 端口、关流、播放地址）
    service.py          SIP 服务（UDP+TCP）生命周期与平台主动下发（点播/停流/云台）

对外只需 service 的少数入口：start_gb28181_sip / stop_gb28181_sip / service_status /
refresh_catalog / start_play / stop_play / send_ptz。
"""
from . import catalog, device_registry, media_proxy, sip_stack
from .service import (
    active_dialog,
    live_urls,
    refresh_catalog,
    send_ptz,
    service_status,
    start_gb28181_sip,
    start_play,
    stop_gb28181_sip,
    stop_play,
)

__all__ = [
    "active_dialog",
    "catalog",
    "device_registry",
    "live_urls",
    "media_proxy",
    "refresh_catalog",
    "send_ptz",
    "service_status",
    "sip_stack",
    "start_gb28181_sip",
    "start_play",
    "stop_gb28181_sip",
    "stop_play",
]
