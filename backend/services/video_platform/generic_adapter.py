"""通用适配器：任何提供 HTTP 抓拍接口的摄像头 / 视频网关

只使用台账里的 host + port + snapshot_path 拼接地址，不接受完整 URL，
因此不存在把本系统当作跳板去访问任意地址的可能。
"""
from __future__ import annotations

from services.video_platform.base import (
    ProbeResult,
    VideoPlatformAdapter,
    VideoPlatformError,
    ensure_image,
)


class GenericAdapter(VideoPlatformAdapter):
    platform = "generic"
    label = "通用"

    def snapshot_url(self) -> str:
        path = (self.config.snapshot_path or "").strip()
        if not path:
            raise VideoPlatformError("未配置抓拍路径（snapshot_path），无法获取画面", status_code=400)
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.config.base_url}{path}"

    async def snapshot(self) -> bytes:
        response = await self.request("GET", self.snapshot_url())
        if response.status_code != 200:
            raise VideoPlatformError(self._status_hint(response))
        ensure_image(response.content)
        return response.content

    async def probe(self) -> ProbeResult:
        try:
            await self.snapshot()
        except VideoPlatformError as exc:
            return ProbeResult(online=False, message=str(exc))
        return ProbeResult(
            online=True,
            device_name=self.config.channel_name,
            message="抓拍地址可达",
        )
