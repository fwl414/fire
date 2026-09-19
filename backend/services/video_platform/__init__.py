"""视频平台接入适配器包

对外只需要用到 registry 里的几个函数，各厂商实现按需加载。
"""
from services.video_platform.base import (
    PTZ_ACTIONS,
    ProbeResult,
    VideoChannelConfig,
    VideoPlatformAdapter,
    VideoPlatformError,
    detect_image_type,
    ensure_image,
)
from services.video_platform.registry import (
    PLATFORMS,
    SUPPORTED_PLATFORMS,
    get_adapter,
    get_adapter_class,
    list_platforms,
    platform_meta,
    supports_ptz,
    supports_recordings,
)

__all__ = [
    "PLATFORMS",
    "PTZ_ACTIONS",
    "SUPPORTED_PLATFORMS",
    "ProbeResult",
    "VideoChannelConfig",
    "VideoPlatformAdapter",
    "VideoPlatformError",
    "detect_image_type",
    "ensure_image",
    "get_adapter",
    "get_adapter_class",
    "list_platforms",
    "platform_meta",
    "supports_ptz",
    "supports_recordings",
]
