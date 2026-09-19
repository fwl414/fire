"""GB28181 应用层 XML：目录查询/应答解析、设备控制命令构造

GB28181 的 MESSAGE 报文体是 XML（设备侧多按 GB2312 编码，这里解析时统一按
GB18030/UTF-8 容错解码）。字段名遵循 GB/T 28181-2016 附录 C。

只有平台侧（SIP UAS）需要的能力：发查询、解析设备返回；不实现设备侧应答构造
（本项目是监控中心，不是摄像机）。
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

XML_DECLARATION = '<?xml version="1.0" encoding="GB2312"?>\r\n'

# 命令类型（CmdType）
CMD_CATALOG = "Catalog"
CMD_DEVICE_INFO = "DeviceInfo"
CMD_DEVICE_STATUS = "DeviceStatus"
CMD_DEVICE_CONTROL = "DeviceControl"
CMD_KEEPALIVE = "Keepalive"
CMD_ALARM = "Alarm"
CMD_RECORD_INFO = "RecordInfo"
CMD_CONFIG_DOWNLOAD = "ConfigDownload"

# 云台指令码（GB/T 28181 附录 A 前端控制指令，PTZCmd 第 4 字节）
PTZ_COMMAND_BITS = {
    "stop": 0x00,
    "right": 0x01,
    "left": 0x02,
    "down": 0x04,
    "up": 0x08,
    "zoom_in": 0x10,
    "zoom_out": 0x20,
}
PTZ_CMD_PREFIX = bytes([0xA5, 0x0F, 0x01])


class CatalogParseError(ValueError):
    """目录/应答 XML 解析失败。"""


# ---------------- 通用解析 ----------------

def _decode(raw) -> str:
    if isinstance(raw, bytes):
        for encoding in ("gb18030", "utf-8"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
    return str(raw or "")


def parse_root(raw) -> ET.Element:
    text = _decode(raw).strip()
    if not text:
        raise CatalogParseError("XML 内容为空")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise CatalogParseError(f"XML 解析失败：{exc}") from exc


def _find_text(root: ET.Element, tag: str, default: str = "") -> str:
    """按标签名取值；厂商大小写不统一时做一次忽略大小写的兜底查找。"""
    found = root.find(tag)
    if found is not None and found.text is not None:
        return found.text.strip()
    lowered = tag.lower()
    for child in root.iter():
        if isinstance(child.tag, str) and child.tag.lower() == lowered and child.text:
            return child.text.strip()
    return default


def parse_cmd_type(raw) -> str:
    try:
        return _find_text(parse_root(raw), "CmdType")
    except CatalogParseError:
        return ""


def parse_sn(raw) -> int:
    try:
        return int(_find_text(parse_root(raw), "SN", "0") or 0)
    except (CatalogParseError, ValueError):
        return 0


def parse_item(element: ET.Element) -> Dict[str, Any]:
    """解析一个 <Item> 通道条目。"""
    return {
        "device_id": _find_text(element, "DeviceID"),
        "name": _find_text(element, "Name"),
        "manufacturer": _find_text(element, "Manufacturer"),
        "model": _find_text(element, "Model"),
        "owner": _find_text(element, "Owner"),
        "civil_code": _find_text(element, "CivilCode"),
        "address": _find_text(element, "Address"),
        "parental": _find_text(element, "Parental"),
        "parent_id": _find_text(element, "ParentID"),
        "register_way": _find_text(element, "RegisterWay"),
        "status": _find_text(element, "Status"),
        "secrecy": _find_text(element, "Secrecy"),
        "ip_address": _find_text(element, "IPAddress"),
        "port": _find_text(element, "Port"),
        "longitude": _find_text(element, "Longitude"),
        "latitude": _find_text(element, "Latitude"),
    }


def parse_catalog(raw) -> Dict[str, Any]:
    """解析目录应答：设备信息 + 全部通道条目。"""
    root = parse_root(raw)
    items: List[Dict[str, Any]] = []
    for element in root.iter():
        if isinstance(element.tag, str) and element.tag == "Item":
            item = parse_item(element)
            if item["device_id"]:
                items.append(item)
    sum_num = _find_text(root, "SumNum", "0")
    try:
        sum_num_value = int(sum_num or 0)
    except ValueError:
        sum_num_value = 0
    return {
        "cmd_type": _find_text(root, "CmdType"),
        "sn": parse_sn(raw),
        "device_id": _find_text(root, "DeviceID"),
        "sum_num": sum_num_value,
        "items": items,
    }


def parse_device_info(raw) -> Dict[str, Any]:
    """解析设备信息应答（DeviceInfo）。"""
    root = parse_root(raw)
    return {
        "cmd_type": _find_text(root, "CmdType"),
        "sn": parse_sn(raw),
        "device_id": _find_text(root, "DeviceID"),
        "name": _find_text(root, "DeviceName"),
        "result": _find_text(root, "Result"),
        "manufacturer": _find_text(root, "Manufacturer"),
        "model": _find_text(root, "Model"),
        "firmware": _find_text(root, "Firmware"),
        "channel_count": _find_text(root, "Channel"),
        "device_type": _find_text(root, "DeviceType"),
        "ip_address": _find_text(root, "IPAddress"),
        "port": _find_text(root, "Port"),
    }


def parse_device_status(raw) -> Dict[str, Any]:
    """解析设备状态应答（DeviceStatus）：Online / OK / Error。"""
    root = parse_root(raw)
    return {
        "cmd_type": _find_text(root, "CmdType"),
        "sn": parse_sn(raw),
        "device_id": _find_text(root, "DeviceID"),
        "result": _find_text(root, "Result"),
        "online": _find_text(root, "Online"),
        "status": _find_text(root, "Status"),
        "encode": _find_text(root, "Encode"),
        "record": _find_text(root, "Record"),
        "device_time": _find_text(root, "DeviceTime"),
    }


def parse_keepalive(raw) -> Dict[str, Any]:
    """解析心跳（Keepalive）：设备周期性上报，用于判定在线。"""
    root = parse_root(raw)
    return {
        "cmd_type": _find_text(root, "CmdType"),
        "sn": parse_sn(raw),
        "device_id": _find_text(root, "DeviceID"),
        "status": _find_text(root, "Status"),
    }


def parse_alarm(raw) -> Dict[str, Any]:
    """解析报警（Alarm）：报警类型、级别、时间与位置。"""
    root = parse_root(raw)
    return {
        "cmd_type": _find_text(root, "CmdType"),
        "sn": parse_sn(raw),
        "device_id": _find_text(root, "DeviceID"),
        "alarm_priority": _find_text(root, "AlarmPriority"),
        "alarm_method": _find_text(root, "AlarmMethod"),
        "alarm_time": _find_text(root, "AlarmTime"),
        "alarm_description": _find_text(root, "AlarmDescription"),
        "longitude": _find_text(root, "Longitude"),
        "latitude": _find_text(root, "Latitude"),
    }


# ---------------- 查询命令构造 ----------------

def next_sn() -> int:
    return int.from_bytes(os.urandom(2), "big") or 1


def build_query(device_id: str, cmd_type: str, sn: int) -> bytes:
    """构造查询类 MESSAGE 报文体（Catalog / DeviceInfo / DeviceStatus）。"""
    xml = (
        f'{XML_DECLARATION}<Query>'
        f"<CmdType>{cmd_type}</CmdType>"
        f"<SN>{int(sn)}</SN>"
        f"<DeviceID>{device_id}</DeviceID>"
        f"</Query>"
    )
    return xml.encode("gb18030", errors="replace")


def build_catalog_query(device_id: str, sn: int) -> bytes:
    return build_query(device_id, CMD_CATALOG, sn)


def build_device_info_query(device_id: str, sn: int) -> bytes:
    return build_query(device_id, CMD_DEVICE_INFO, sn)


def build_device_status_query(device_id: str, sn: int) -> bytes:
    return build_query(device_id, CMD_DEVICE_STATUS, sn)


# ---------------- 云台控制 ----------------

def build_ptz_cmd(action: str, speed: int = 5) -> str:
    """构造 PTZCmd（8 字节十六进制串）。

    结构：A5 0F 01 <指令码> <水平速度> <垂直速度> <缩放速度> <校验和>，
    校验和为前 7 字节之和取低 8 位。指令码位定义见 PTZ_COMMAND_BITS；
    现场设备位序若不同，可通过接口的 `ptz_cmd` 参数直接传原始指令码覆盖。
    """
    key = str(action or "").strip().lower()
    if key not in PTZ_COMMAND_BITS:
        raise CatalogParseError(f"不支持的云台动作：{action}")
    level = max(0, min(255, int(speed)))
    speed_byte = 0x00 if key == "stop" else _speed_to_byte(level)
    body = PTZ_CMD_PREFIX + bytes([PTZ_COMMAND_BITS[key], speed_byte, speed_byte, speed_byte])
    return (body + bytes([sum(body) & 0xFF])).hex().upper()


def _speed_to_byte(speed: int) -> int:
    """把 0~10 的档位映射到 0x00~0xFF（1 档约 0x19，10 档 0xFF）。"""
    level = max(0, min(10, speed))
    return int(round(level * 255 / 10)) & 0xFF


def build_device_control(
    device_id: str,
    channel_id: str,
    sn: int,
    *,
    ptz_cmd: str = "",
    action: str = "",
    speed: int = 5,
) -> bytes:
    """构造云台控制 MESSAGE（DeviceControl），可传原始 PTZCmd 或动作名。"""
    command = (ptz_cmd or "").strip().upper() or build_ptz_cmd(action, speed)
    xml = (
        f'{XML_DECLARATION}<Control>'
        f"<CmdType>{CMD_DEVICE_CONTROL}</CmdType>"
        f"<SN>{int(sn)}</SN>"
        f"<DeviceID>{channel_id or device_id}</DeviceID>"
        f"<PTZCmd>{command}</PTZCmd>"
        f"</Control>"
    )
    return xml.encode("gb18030", errors="replace")
