"""ZLMediaKit 媒体代理（GB28181 的 RTP 收流与 HLS/FLV/WebRTC 分发）

GB28181 只规定信令与 RTP 承载，媒体分发交给专业流媒体服务器（本项目用 ZLMediaKit）：

    平台 INVITE 设备 → 在 ZLMediaKit 上开一个 RTP 收流端口 → SDP 告知设备推到该端口
    → 设备推流 → ZLMediaKit 自动转 HLS / HTTP-FLV / WebRTC → 前端直接播放

本模块只做 HTTP API 调用与播放地址拼接，不含任何媒体处理逻辑；
`GB28181_MEDIA_API_BASE` 为空时视为未接入媒体服务器（enabled() 返回 False）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class MediaProxyError(RuntimeError):
    """媒体服务器调用失败。"""


def api_base() -> str:
    return (os.environ.get("GB28181_MEDIA_API_BASE") or "").strip().rstrip("/")


def secret() -> str:
    return (os.environ.get("GB28181_MEDIA_SECRET") or "").strip()


def media_host() -> str:
    return (os.environ.get("GB28181_MEDIA_HTTP_HOST") or os.environ.get("GB28181_MEDIA_SERVER_HOST") or "").strip()


def media_http_port() -> int:
    try:
        return int(os.environ.get("GB28181_MEDIA_HTTP_PORT", "8081"))
    except (TypeError, ValueError):
        return 8081


def rtp_port_range() -> tuple:
    raw = (os.environ.get("GB28181_RTP_PORT_RANGE") or "10000,10500").split(",")
    try:
        start, end = int(raw[0]), int(raw[1])
    except (IndexError, ValueError):
        return 10000, 10500
    return start, end


def enabled() -> bool:
    return bool(api_base())


def _require_config() -> None:
    if not api_base():
        raise MediaProxyError("未配置 GB28181_MEDIA_API_BASE，无法调用流媒体服务器")


async def _call(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    _require_config()
    query = {"secret": secret(), **{k: v for k, v in params.items() if v is not None}}
    url = f"{api_base()}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=query)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise MediaProxyError(f"流媒体服务器请求失败：{exc}") from exc
    except ValueError as exc:
        raise MediaProxyError(f"流媒体服务器返回非 JSON：{exc}") from exc

    if isinstance(data, dict) and "code" in data and int(data.get("code") or 0) != 0:
        raise MediaProxyError(f"流媒体服务器返回错误：code={data.get('code')} msg={data.get('msg')}")
    return data if isinstance(data, dict) else {}


async def open_rtp_server(stream_id: str, *, port: int = 0, enable_tcp: bool = True) -> int:
    """开一个 RTP 收流端口，返回实际端口（port=0 时由服务器从端口段分配）。"""
    start, end = rtp_port_range()
    data = await _call("openRtpServer", {
        "port": port or 0,
        "enable_tcp": 1 if enable_tcp else 0,
        "stream_id": stream_id,
        "tcp_mode": 1 if enable_tcp else 0,
        "range_start": start,
        "range_end": end,
    })
    returned = int(data.get("port") or 0)
    if not returned:
        raise MediaProxyError(f"流媒体服务器未返回 RTP 端口：{data}")
    return returned


async def close_rtp_server(stream_id: str) -> None:
    await _call("closeRtpServer", {"stream_id": stream_id})


async def add_stream_proxy(source_url: str, stream_id: str, *, app: str = "rtp") -> Dict[str, Any]:
    """主动拉流（RTSP/RTMP 源）并转成平台统一格式，用于非 GB28181 的设备源。"""
    return await _call("addStreamProxy", {
        "vhost": "__defaultVhost__",
        "app": app,
        "stream": stream_id,
        "url": source_url,
        "enable_hls": 1,
        "enable_mp4": 0,
        "rtp_type": 0,
    })


async def close_stream(stream_id: str, *, app: str = "rtp") -> None:
    await _call("close_streams", {
        "vhost": "__defaultVhost__",
        "app": app,
        "stream": stream_id,
        "force": 1,
    })


async def list_streams() -> list:
    data = await _call("getMediaList", {})
    return data.get("data") or []


async def media_info(stream_id: str, *, app: str = "rtp") -> Optional[Dict[str, Any]]:
    for item in await list_streams():
        if item.get("stream") == stream_id and (not app or item.get("app") == app):
            return item
    return None


def play_urls(stream_id: str, *, app: str = "rtp") -> Dict[str, str]:
    """按 ZLMediaKit 的路径规范拼接播放地址（前端按浏览器能力三选一）。"""
    host, port = media_host(), media_http_port()
    if not host:
        return {}
    http = f"http://{host}:{port}"
    return {
        "hls": f"{http}/{app}/{stream_id}/hls.m3u8",
        "flv": f"{http}/{app}/{stream_id}.live.flv",
        "webrtc": f"{http}/index/api/webrtc?app={app}&stream={stream_id}&type=play",
        "rtsp": f"rtsp://{host}:554/{app}/{stream_id}",
        "rtmp": f"rtmp://{host}:1935/{app}/{stream_id}",
    }


async def is_streaming(stream_id: str, *, app: str = "rtp") -> bool:
    try:
        return (await media_info(stream_id, app=app)) is not None
    except MediaProxyError:
        return False
