"""视频平台适配器注册表

平台元数据（名称、能力、需要的字段）集中在这里，`/api/video/platforms` 直接读取，
不需要导入任何适配器实现；真正实例化时才按需 import，避免为一个未使用的平台付出导入成本。
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional, Type

from services.video_platform.base import (
    PTZ_ACTIONS,
    VideoChannelConfig,
    VideoPlatformAdapter,
    VideoPlatformError,
)

# platform -> (模块路径, 类名)
_ADAPTER_IMPORTS: Dict[str, tuple] = {
    "generic": ("services.video_platform.generic_adapter", "GenericAdapter"),
    "hikvision": ("services.video_platform.hikvision_adapter", "HikvisionAdapter"),
    "dahua": ("services.video_platform.dahua_adapter", "DahuaAdapter"),
    "mock": ("services.video_platform.mock_adapter", "MockAdapter"),
}

PLATFORMS: Dict[str, Dict[str, Any]] = {
    "generic": {
        "label": "通用 HTTP 快照 / RTSP",
        "description": "适用于任何提供 HTTP 抓拍接口的摄像头或视频网关；取流地址仅作登记，浏览器不能直接播放。",
        "capabilities": ["probe", "snapshot", "stream_info"],
        "required_fields": ["host", "snapshot_path"],
        "ptz": False,
        "recordings": False,
    },
    "hikvision": {
        "label": "海康威视 ISAPI",
        "description": "通过 ISAPI 读取设备信息与通道列表、抓拍图片、控制云台、按时间段检索录像；使用摘要认证。",
        "capabilities": ["probe", "snapshot", "ptz", "stream_info", "recordings"],
        "required_fields": ["host", "channel_no"],
        "ptz": True,
        "recordings": True,
    },
    "dahua": {
        "label": "大华 HTTP CGI",
        "description": "通过大华 CGI 接口读取设备型号与版本、抓拍图片、控制云台；使用摘要认证。录像检索未实现。",
        "capabilities": ["probe", "snapshot", "ptz", "stream_info"],
        "required_fields": ["host", "channel_no"],
        "ptz": True,
        "recordings": False,
    },
    "mock": {
        "label": "本地模拟设备",
        "description": "不做任何网络请求，返回合成抓拍图，用于开发与联调（生产环境请勿启用）。",
        "capabilities": ["probe", "snapshot", "ptz"],
        "required_fields": [],
        "ptz": True,
        "recordings": False,
    },
}

SUPPORTED_PLATFORMS = tuple(PLATFORMS.keys())


def list_platforms() -> List[Dict[str, Any]]:
    return [{"platform": key, **meta} for key, meta in PLATFORMS.items()]


def platform_meta(platform: str) -> Dict[str, Any]:
    return PLATFORMS.get(platform) or {
        "label": platform or "未知平台",
        "description": "",
        "capabilities": [],
        "required_fields": [],
        "ptz": False,
    }


def supports_ptz(platform: str) -> bool:
    return bool(platform_meta(platform).get("ptz"))


def supports_recordings(platform: str) -> bool:
    return bool(platform_meta(platform).get("recordings"))


def get_adapter_class(platform: str) -> Type[VideoPlatformAdapter]:
    entry = _ADAPTER_IMPORTS.get(platform)
    if not entry:
        raise VideoPlatformError(
            f"不支持的视频平台「{platform}」，可选：{'/'.join(SUPPORTED_PLATFORMS)}",
            status_code=400,
        )
    module = importlib.import_module(entry[0])
    return getattr(module, entry[1])


def get_adapter(
    config: VideoChannelConfig,
    *,
    client=None,
    timeout: Optional[float] = None,
) -> VideoPlatformAdapter:
    adapter_class = get_adapter_class(config.platform)
    kwargs = {"client": client} if client is not None else {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return adapter_class(config, **kwargs)


__all__ = [
    "PTZ_ACTIONS",
    "PLATFORMS",
    "SUPPORTED_PLATFORMS",
    "get_adapter",
    "get_adapter_class",
    "list_platforms",
    "platform_meta",
    "supports_ptz",
    "supports_recordings",
]
