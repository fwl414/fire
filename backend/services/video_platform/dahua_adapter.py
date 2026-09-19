"""大华 HTTP CGI 适配器

使用大华设备自带的 CGI 接口（HTTP + 摘要认证）：
- 设备型号：GET /cgi-bin/magicBox.cgi?action=getDeviceType
- 软件版本：GET /cgi-bin/magicBox.cgi?action=getSoftwareVersion
- 序列号：  GET /cgi-bin/magicBox.cgi?action=getSerialNo
- 抓拍：    GET /cgi-bin/snapshot.cgi?channel={channel}
- 云台：    GET /cgi-bin/ptz.cgi?action=start&channel={channel}&code={code}&arg1=0&arg2={speed}&arg3=0

大华在出错时经常返回 200 + 纯文本（如 `Error`），所以统一解析文本并显式判错。
"""
from __future__ import annotations

from typing import Any, Dict

from services.video_platform.base import (
    PTZ_ACTIONS,
    ProbeResult,
    VideoPlatformAdapter,
    VideoPlatformError,
    ensure_image,
)

PTZ_CODES = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "zoom_in": "ZoomTele",
    "zoom_out": "ZoomWide",
}


def _parse_kv(text: str) -> Dict[str, str]:
    """解析 `key=value` 形式的纯文本响应。"""
    parsed: Dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip()
    return parsed


class DahuaAdapter(VideoPlatformAdapter):
    platform = "dahua"
    label = "大华 HTTP CGI"

    def channel(self) -> str:
        return (self.config.channel_no or "1").strip() or "1"

    async def _cgi(self, endpoint: str, **params) -> str:
        query = "&".join(f"{key}={value}" for key, value in params.items())
        path = f"/cgi-bin/{endpoint}"
        if query:
            path = f"{path}?{query}"
        response = await self.get(path)
        if response.status_code != 200:
            raise VideoPlatformError(self._status_hint(response))
        text = response.content.decode("utf-8", errors="ignore").strip()
        if text.startswith("Error") or text.lower().startswith("bad request"):
            raise VideoPlatformError(f"设备返回错误：{text[:120]}")
        return text

    async def probe(self) -> ProbeResult:
        try:
            device_type = _parse_kv(await self._cgi("magicBox.cgi", action="getDeviceType")).get("type", "")
            version = _parse_kv(await self._cgi("magicBox.cgi", action="getSoftwareVersion")).get("version", "")
        except VideoPlatformError as exc:
            return ProbeResult(online=False, message=str(exc))

        if not device_type:
            return ProbeResult(online=False, message="设备未返回型号信息，无法确认为大华设备")

        return ProbeResult(
            online=True,
            device_name=self.config.channel_name,
            device_model=device_type,
            firmware=version,
            channels=[{"id": self.channel(), "name": self.config.channel_name, "enabled": True}],
            message="大华 CGI 设备信息读取成功",
        )

    async def snapshot(self) -> bytes:
        response = await self.get(f"/cgi-bin/snapshot.cgi?channel={self.channel()}")
        if response.status_code != 200:
            raise VideoPlatformError(self._status_hint(response))
        ensure_image(response.content)
        return response.content

    async def ptz(self, action: str, speed: int = 5) -> Dict[str, Any]:
        if action not in PTZ_ACTIONS:
            raise VideoPlatformError(f"不支持的云台动作：{action}")

        magnitude = 0 if action == "stop" else max(1, min(int(speed or 5), 8))
        if action == "stop":
            # 大华需要按各方向分别下发停止指令
            for code in set(PTZ_CODES.values()):
                await self._cgi(
                    "ptz.cgi", action="stop", channel=self.channel(),
                    code=code, arg1=0, arg2=0, arg3=0,
                )
            return {"platform": self.platform, "action": action, "speed": 0, "message": "云台已停止"}

        await self._cgi(
            "ptz.cgi", action="start", channel=self.channel(),
            code=PTZ_CODES[action], arg1=0, arg2=magnitude, arg3=0,
        )
        return {
            "platform": self.platform,
            "action": action,
            "speed": magnitude,
            "message": f"云台动作已下发：{action}",
        }
