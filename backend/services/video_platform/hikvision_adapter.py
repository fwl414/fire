"""海康威视 ISAPI 适配器

使用 ISAPI（HTTP + 摘要认证）完成设备信息读取、通道枚举、抓拍、云台控制与录像检索：
- 设备信息：GET  /ISAPI/System/deviceInfo
- 通道列表：GET  /ISAPI/Streaming/channels
- 抓拍：    GET  /ISAPI/Streaming/channels/{channel}01/picture
- 云台：    PUT  /ISAPI/PTZCtrl/channels/{channel}/continuous
- 录像检索：POST /ISAPI/ContentMgmt/search

注意：不同固件对云台方向取值区间（0~100 或 -100~100）要求不同，现场若方向不生效，
需要按设备手册调整 _ptz_payload 中的取值，这一点已在接口返回中如实说明。
录像检索按 ISAPI 标准实现，检索时间以 **UTC** 解释；不同固件返回的字段名可能略有差异，
现场需以设备手册为准（返回的片段直接来自设备，不做任何补造）。
"""
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List

from services.video_platform.base import (
    PTZ_ACTIONS,
    ProbeResult,
    VideoPlatformAdapter,
    VideoPlatformError,
    ensure_image,
)

DEVICE_INFO_PATH = "/ISAPI/System/deviceInfo"
CHANNEL_LIST_PATH = "/ISAPI/Streaming/channels"
RECORD_SEARCH_PATH = "/ISAPI/ContentMgmt/search"
PTZ_ACTIONS_MAP = {
    "up": {"pan": 0, "tilt": 1, "zoom": 0},
    "down": {"pan": 0, "tilt": -1, "zoom": 0},
    "left": {"pan": -1, "tilt": 0, "zoom": 0},
    "right": {"pan": 1, "tilt": 0, "zoom": 0},
    "zoom_in": {"pan": 0, "tilt": 0, "zoom": 1},
    "zoom_out": {"pan": 0, "tilt": 0, "zoom": -1},
    "stop": {"pan": 0, "tilt": 0, "zoom": 0},
}


def _local_name(tag: str) -> str:
    return tag.split("}")[-1]


def _find_text(root: ET.Element, name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text:
            return element.text.strip()
    return ""


def _parse_xml(content: bytes) -> ET.Element:
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        preview = content[:120].decode("utf-8", errors="ignore")
        raise VideoPlatformError(f"设备返回内容不是合法 XML：{preview}") from exc


def _raise_if_status_failed(root: ET.Element) -> None:
    """ISAPI 出错时仍返回 200，需要看 ResponseStatus 节点。"""
    status_code = _find_text(root, "statusCode")
    if status_code and status_code not in ("1", "OK"):
        raise VideoPlatformError(
            f"设备返回错误状态：{_find_text(root, 'statusString') or status_code}"
        )


def _isapi_time(value: str) -> str:
    """把日期/日期时间统一成 ISAPI 需要的 `YYYY-MM-DDTHH:MM:SSZ`（按 UTC 解释）。"""
    text = (value or "").strip().replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    raise VideoPlatformError(f"无法解析的时间格式：{value}", status_code=400)


class HikvisionAdapter(VideoPlatformAdapter):
    platform = "hikvision"
    label = "海康威视 ISAPI"

    def picture_path(self) -> str:
        channel = (self.config.channel_no or "1").strip() or "1"
        return f"/ISAPI/Streaming/channels/{channel}01/picture"

    async def probe(self) -> ProbeResult:
        response = await self.get(DEVICE_INFO_PATH)
        if response.status_code != 200:
            return ProbeResult(online=False, message=self._status_hint(response))

        root = _parse_xml(response.content)
        if _find_text(root, "statusCode") not in ("", "1"):
            return ProbeResult(
                online=False,
                message=f"设备返回错误状态：{_find_text(root, 'statusString') or _find_text(root, 'statusCode')}",
            )

        result = ProbeResult(
            online=True,
            device_name=_find_text(root, "deviceName") or self.config.channel_name,
            device_model=_find_text(root, "model"),
            firmware=_find_text(root, "firmwareVersion"),
            message="ISAPI 设备信息读取成功",
        )
        try:
            result.channels = await self.list_channels()
        except VideoPlatformError:
            # 通道列表属于附加信息，拿不到不影响在线判定
            result.channels = []
        return result

    async def list_channels(self) -> List[Dict[str, Any]]:
        response = await self.get(CHANNEL_LIST_PATH)
        if response.status_code != 200:
            raise VideoPlatformError(self._status_hint(response))

        root = _parse_xml(response.content)
        _raise_if_status_failed(root)

        channels: List[Dict[str, Any]] = []
        for element in root.iter():
            if _local_name(element.tag) != "StreamingChannel":
                continue
            channels.append({
                "id": _find_text(element, "id"),
                "name": _find_text(element, "channelName"),
                "enabled": _find_text(element, "enabled").lower() != "false",
            })
        return channels

    async def snapshot(self) -> bytes:
        response = await self.get(self.picture_path())
        if response.status_code != 200:
            raise VideoPlatformError(self._status_hint(response))
        ensure_image(response.content)
        return response.content

    async def ptz(self, action: str, speed: int = 5) -> Dict[str, Any]:
        if action not in PTZ_ACTIONS:
            raise VideoPlatformError(f"不支持的云台动作：{action}")

        magnitude = 0 if action == "stop" else max(1, min(int(speed or 5), 10)) * 10
        direction = PTZ_ACTIONS_MAP[action]
        payload = ET.Element("PTZData")
        for axis, sign in direction.items():
            ET.SubElement(payload, axis).text = str(sign * magnitude)
        body = ET.tostring(payload, encoding="utf-8", xml_declaration=True)

        channel = (self.config.channel_no or "1").strip() or "1"
        response = await self.request(
            "PUT",
            f"{self.config.base_url}/ISAPI/PTZCtrl/channels/{channel}/continuous",
            content=body,
            headers={"Content-Type": "application/xml"},
        )
        if response.status_code not in (200, 201):
            raise VideoPlatformError(self._status_hint(response))

        # 部分固件只返回状态码、不带响应体
        if response.content.strip():
            _raise_if_status_failed(_parse_xml(response.content))
        return {
            "platform": self.platform,
            "action": action,
            "speed": magnitude,
            "message": f"云台动作已下发：{action}",
        }

    async def query_recordings(self, start: str, end: str, *, limit: int = 100) -> Dict[str, Any]:
        """按时间段检索录像片段（ISAPI `ContentMgmt/search`）。

        返回的片段完全来自设备：`responseStatusStrg` 为 `NO MATCH` 时如实说明该时间段没有录像，
        不补造任何片段。
        """
        channel = (self.config.channel_no or "1").strip() or "1"
        payload = ET.Element("CMSearchDescription")
        ET.SubElement(payload, "searchID").text = uuid.uuid4().hex
        track_list = ET.SubElement(payload, "trackList")
        ET.SubElement(track_list, "trackID").text = f"{channel}01"
        span_list = ET.SubElement(payload, "timeSpanList")
        span = ET.SubElement(span_list, "timeSpan")
        ET.SubElement(span, "startTime").text = _isapi_time(start)
        ET.SubElement(span, "endTime").text = _isapi_time(end)
        ET.SubElement(payload, "maxResults").text = str(max(1, min(int(limit or 100), 200)))
        ET.SubElement(payload, "searchResultPostion").text = "0"
        metadata_list = ET.SubElement(payload, "metadataList")
        ET.SubElement(metadata_list, "metadataDescriptor").text = "//recordType.meta.std-cgi.com"
        body = ET.tostring(payload, encoding="utf-8", xml_declaration=True)

        response = await self.request(
            "POST",
            f"{self.config.base_url}{RECORD_SEARCH_PATH}",
            content=body,
            headers={"Content-Type": "application/xml"},
        )
        if response.status_code != 200:
            raise VideoPlatformError(self._status_hint(response))

        root = _parse_xml(response.content)
        _raise_if_status_failed(root)

        items: List[Dict[str, Any]] = []
        for element in root.iter():
            if _local_name(element.tag) != "searchMatchItem":
                continue
            items.append({
                "start_time": _find_text(element, "startTime"),
                "end_time": _find_text(element, "endTime"),
                "content_type": _find_text(element, "contentType"),
                "playback_uri": _find_text(element, "playbackURI"),
            })

        status_text = _find_text(root, "responseStatusStrg").upper()
        if items:
            message = ""
        elif status_text == "NO MATCH":
            message = "该时间段设备里没有录像"
        else:
            message = f"设备未返回录像片段（状态：{status_text or '未知'}）"
        return {
            "supported": True,
            "items": items,
            "message": message,
            "platform": self.platform,
        }
