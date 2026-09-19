"""本地模拟视频设备适配器

不做任何网络请求，直接合成一张带通道名与时间戳的抓拍图，用于开发联调与自动化测试：
既能在没有真实摄像头时把整条链路（抓拍 → 受控下发 → 视觉识别 → 告警）跑通，
也让测试可以确定性地断言"确实拿到了图片"。
"""
from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Any, Dict

from services.video_platform.base import (
    PTZ_ACTIONS,
    ProbeResult,
    VideoPlatformAdapter,
    VideoPlatformError,
)

# Pillow 不可用时的兜底：1x1 的合法 JPEG
_FALLBACK_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

FRAME_WIDTH = 640
FRAME_HEIGHT = 360


def _render_frame(channel_name: str, channel_code: str) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return _FALLBACK_JPEG

    image = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), (24, 28, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, FRAME_WIDTH - 16, FRAME_HEIGHT - 16], outline=(90, 160, 220), width=2)
    draw.text((32, 40), f"MOCK CAMERA  {channel_code}", fill=(220, 230, 240))
    draw.text((32, 68), channel_name or "未命名通道", fill=(150, 200, 250))
    draw.text((32, FRAME_HEIGHT - 56), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fill=(160, 170, 180))
    draw.text((32, FRAME_HEIGHT - 32), "本地模拟画面（未连接真实设备）", fill=(120, 130, 140))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


class MockAdapter(VideoPlatformAdapter):
    platform = "mock"
    label = "本地模拟设备"

    def channel(self) -> str:
        return (self.config.channel_no or "1").strip() or "1"

    async def probe(self) -> ProbeResult:
        return ProbeResult(
            online=True,
            device_name=self.config.channel_name or self.config.channel_code,
            device_model="MOCK-IPC-2000",
            firmware="v1.0.0-mock",
            channels=[{"id": self.channel(), "name": self.config.channel_name, "enabled": True}],
            message="模拟设备：未发起真实网络请求",
        )

    async def snapshot(self) -> bytes:
        return _render_frame(self.config.channel_name, self.config.channel_code)

    async def ptz(self, action: str, speed: int = 5) -> Dict[str, Any]:
        if action not in PTZ_ACTIONS:
            raise VideoPlatformError(f"不支持的云台动作：{action}")
        magnitude = 0 if action == "stop" else max(1, min(int(speed or 5), 10))
        return {
            "platform": self.platform,
            "action": action,
            "speed": magnitude,
            "message": f"模拟设备已接收云台指令：{action}",
        }

    def stream_info(self) -> Dict[str, Any]:
        return {
            "rtsp_url": self.config.rtsp_url,
            "playable_in_browser": False,
            "note": "模拟设备不提供实时流，请使用抓拍轮询。",
        }
