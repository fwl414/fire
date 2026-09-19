"""GB/T 26875 接入服务（TCP 长连接，一连接对应一台用户信息传输装置）

上行处理链路与 HTTP / MQTT 两条通道完全一致，统一走
`device_ingest_service.dispatch`：落遥测 → 阈值判定 → 告警（去重/升级）→ 整改工单。

    注册/配置（类型 26，可携带 USER=xxx;PWD=yyy）→ 校验地址与口令 → 回「确认」
    运行状态（类型 21）/系统或传输装置时间（类型 8/28）→ 心跳：刷新在线状态与最后心跳时间
    系统状态（类型 1）/部件状态（类型 2）/操作信息（类型 4）→ 事件：按状态位生成告警
    模拟量值（类型 3）                        → 遥测：写 DeviceTelemetry 并做阈值判定

下行：确认(3) / 否认(6) / 应答(5)；控制命令(1) 用于时间同步（见 service.send_and_wait）。
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database import Device, GB26875Device, SessionLocal
from services.device_ingest_service import dispatch

from . import auth, commands as cmd
from .frame import AppObject, Frame, FrameError, decode_stream, encode, encode_app_data, parse_app_data

logger = logging.getLogger(__name__)

# 监控中心自身的国标地址（用户信息传输装置侧登记的中心地址，需两侧一致）
CENTER_ADDRESS = (os.environ.get("GB26875_CENTER_ADDRESS") or "000000000000").strip()
# 连接空闲多久未收到任何报文即断开（消防主机心跳一般 30s 内一次）
IDLE_TIMEOUT_SECONDS = 600

_stats: Dict[str, Any] = {
    "received": 0,
    "accepted": 0,
    "denied": 0,
    "errors": 0,
    "ignored": 0,
    "last_error": "",
    "last_frame_at": None,
    "connections_total": 0,
}


def stats() -> Dict[str, Any]:
    data = dict(_stats)
    data["last_frame_at"] = _stats["last_frame_at"].isoformat() if _stats["last_frame_at"] else None
    return data


# ---------------- 信息体解析 ----------------

def _signed_int16(raw: bytes) -> int:
    if len(raw) < 2:
        raise FrameError("数值字段需要 2 字节")
    return int.from_bytes(raw[0:2], "little", signed=True)


def _status_int16(raw: bytes) -> int:
    if len(raw) < 2:
        raise FrameError("状态字段需要 2 字节")
    return int.from_bytes(raw[0:2], "little")


def _component_address(raw: bytes) -> str:
    """部件地址（4 字节，低字节在前）→ 十六进制字符串，便于与台账对账。"""
    return bytes(reversed(raw)).hex().upper()


def _system_desc(system_type: Optional[int], system_address: Optional[int]) -> str:
    if system_type is None:
        return ""
    label = cmd.system_type_label(system_type)
    return f"{label}/{system_address}" if system_address is not None else label


def _analog_body_to_telemetry(body: bytes) -> Optional[Dict[str, Any]]:
    """模拟量信息体（10 字节）→ 遥测数据；类型未映射到本项目指标时返回 None。

    字段布局（8.2.1.3）：系统类型(1) + 系统地址(1) + 部件类型(1) + 部件地址(4) + 模拟量类型(1) + 值(2)
    """
    if len(body) < 10:
        raise FrameError("模拟量信息体长度不足 10 字节")
    analog_type = body[7]
    if analog_type not in cmd.ANALOG_TYPE_METRICS:
        return None
    # 表6：最小计量单元 0.1（电压 V / 电流 A）
    value = _signed_int16(body[8:10]) / 10.0
    return {
        cmd.analog_metric(analog_type): value,
        "unit": cmd.ANALOG_TYPE_UNITS.get(analog_type, ""),
        "analog_type": analog_type,
        "component_address": _component_address(body[3:7]),
        "system": _system_desc(body[0], body[1]),
    }


def _status_body_to_event(body: bytes, *, kind: str) -> Dict[str, Any]:
    """系统状态 / 部件状态信息体 → 事件数据。

    字段布局（8.2.1.1 / 8.2.1.2）：
        系统状态：系统类型(1) + 系统地址(1) + 状态(2)
        部件状态：系统类型(1) + 系统地址(1) + 部件类型(1) + 部件地址(4) + 状态(2) + 说明(31)
    """
    if len(body) < 4:
        raise FrameError(f"{kind} 信息体长度不足 4 字节")
    system_type, system_address = body[0], body[1]
    if kind == "component":
        if len(body) < 9:
            raise FrameError("部件状态信息体长度不足 9 字节")
        status = _status_int16(body[7:9])
        component = _component_address(body[3:7])
        component_type: Optional[int] = body[2]
        description = body[9:40].decode("gb18030", errors="ignore").strip("\x00").strip()
    else:
        status = _status_int16(body[2:4])
        component = ""
        component_type = None
        description = ""

    return {
        "event_types": cmd.status_events(status),
        "status": status,
        "status_labels": cmd.decode_status_bits(status),
        "system": _system_desc(system_type, system_address),
        "component_address": component,
        "component_type": component_type,
        "component_description": description,
    }


# ---------------- 设备台账绑定与兜底建档 ----------------

def _resolve_device(db: Session, gb_device: GB26875Device) -> Device:
    """取业务设备档案；台账未映射 device_code 时按国标地址兜底建档。

    火警不能因为「运维忘了把接入地址映射到设备档案」而丢失，因此这里自动补一条
    `devices` 记录并把 device_code 回填台账。设备名称/位置可在设备管理页补全。
    """
    if gb_device.device_code:
        device = db.query(Device).filter(Device.device_code == gb_device.device_code).first()
        if device:
            return device

    device_code = gb_device.device_code or f"GB{gb_device.gb_address}"
    device = Device(
        tenant_id=gb_device.tenant_id,
        device_code=device_code,
        device_name=f"GB26875 传输装置 {gb_device.gb_address}",
        device_type="用户信息传输装置",
        status="正常",
        description=f"由 GB/T 26875 接入自动建档（国标地址 {gb_device.gb_address}）",
    )
    db.add(device)
    db.flush()
    gb_device.device_code = device_code
    db.commit()
    logger.info("GB26875 地址 %s 自动建立设备档案 %s", gb_device.gb_address, device_code)
    return device


def _mark_online(db: Session, gb_device: GB26875Device, peer_ip: str, peer_port: int) -> None:
    gb_device.registered = True
    gb_device.last_heartbeat_at = datetime.utcnow()
    if peer_ip:
        gb_device.remote_ip = peer_ip
    if peer_port:
        gb_device.remote_port = peer_port
    gb_device.updated_at = datetime.utcnow()
    db.commit()


# ---------------- 上行报文处理 ----------------

def _ingest_payload(
    db: Session,
    gb_device: GB26875Device,
    app_type: int,
    objects: List[AppObject],
    peer_ip: str,
    peer_port: int,
) -> Dict[str, Any]:
    """按应用数据单元类型把报文送进统一接入链路。

    返回里的 `ack` 决定回「确认」还是「否认」：无法识别的类型按标准 6.5.3
    （不可识别的命令字节属校验错误）回否认，能识别但暂不落业务数据的类型仍回确认。
    """
    kind = cmd.INGEST_KIND_BY_TYPE.get(app_type)
    if not kind:
        return {"handled": False, "ack": "deny", "reason": f"未定义的上行类型：{app_type}"}

    device = _resolve_device(db, gb_device)
    summary: Dict[str, Any] = {"handled": True, "ack": "confirm", "kind": kind, "app_type": app_type, "results": []}

    if app_type in cmd.HEARTBEAT_TYPES:
        _mark_online(db, gb_device, peer_ip, peer_port)
        summary["results"].append(dispatch(
            db, device, "heartbeat",
            {"app_type": app_type, "type_label": cmd.type_label(app_type)},
            source="gb26875",
        ))
        return summary

    if app_type == cmd.TYPE_COMPONENT_ANALOG:
        metrics: Dict[str, Any] = {}
        for obj in objects:
            telemetry = _analog_body_to_telemetry(obj.body)
            if telemetry:
                metrics.update(telemetry)
        _mark_online(db, gb_device, peer_ip, peer_port)
        if not metrics:
            # 模拟量类型未映射到本项目指标：报文本身合法，回确认但不写遥测
            summary["handled"] = False
            summary["reason"] = "模拟量类型未映射到本项目指标"
            return summary
        summary["results"].append(dispatch(db, device, "telemetry", metrics, source="gb26875"))
        return summary

    if app_type == cmd.TYPE_COMPONENT_OPERATION:
        for obj in objects:
            if len(obj.body) < 3:
                raise FrameError("操作信息信息体长度不足 3 字节")
            summary["results"].append(dispatch(db, device, "event", {
                "event_type": "operation",
                "severity": "low",
                "description": f"{device.device_name} 现场操作（操作员编号 {obj.body[2]}）",
                "system": _system_desc(obj.body[0], obj.body[1]),
                "operator_no": obj.body[2],
            }, source="gb26875"))
        _mark_online(db, gb_device, peer_ip, peer_port)
        return summary

    if app_type in (cmd.TYPE_SYSTEM_STATUS, cmd.TYPE_COMPONENT_STATUS):
        kind_name = "component" if app_type == cmd.TYPE_COMPONENT_STATUS else "system"
        for obj in objects:
            event = _status_body_to_event(obj.body, kind=kind_name)
            status_labels = "、".join(event["status_labels"]) or "无状态位置位"
            if not event["event_types"]:
                summary["results"].append({"received": True, "ignored": True, "status_labels": event["status_labels"]})
                continue
            for event_type in event["event_types"]:
                summary["results"].append(dispatch(db, device, "event", {
                    "event_type": event_type,
                    "severity": cmd.EVENT_SEVERITIES.get(event_type, "high"),
                    "description": f"{device.device_name} {event['system']} 上报 {status_labels}",
                    "system": event["system"],
                    "component_address": event["component_address"],
                    "component_type": event["component_type"],
                    "component_description": event["component_description"],
                    "status": event["status"],
                }, source="gb26875"))
        _mark_online(db, gb_device, peer_ip, peer_port)
        return summary

    # 其余可识别的上行类型（软件版本/系统配置/部件配置等）只刷新在线状态
    _mark_online(db, gb_device, peer_ip, peer_port)
    summary["handled"] = False
    summary["reason"] = f"类型 {app_type}（{cmd.type_label(app_type)}）暂不落业务数据"
    return summary


def _build_response(frame: Frame, command: int, app_data: bytes = b"") -> bytes:
    return encode(
        command,
        source_address=CENTER_ADDRESS,
        dest_address=frame.source_address,
        app_data=app_data,
        seq=frame.seq,
    )


def _handle_read_request(frame: Frame, app_type: int) -> Tuple[int, bytes]:
    """下行读命令的应答：目前支持读系统/传输装置时间，其余一律否认。"""
    if app_type in (cmd.TYPE_READ_SYSTEM_TIME, cmd.TYPE_READ_TRANSMITTER_TIME):
        return cmd.COMMAND_RESPONSE, encode_app_data(app_type, [AppObject(body=b"", timestamp=datetime.now())])
    return cmd.COMMAND_DENY, b""


def handle_frame(db: Session, frame: Frame, *, peer_ip: str = "", peer_port: int = 0) -> Optional[bytes]:
    """处理一个完整上行数据包，返回需回写的响应帧（无需响应时返回 None）。

    本函数不碰 socket，便于单测直接构造帧验证接入逻辑。
    """
    _stats["received"] += 1
    _stats["last_frame_at"] = datetime.utcnow()

    if frame.command in (cmd.COMMAND_CONFIRM, cmd.COMMAND_DENY):
        # 设备对中心下行命令的确认/否认：交由 service 层等待方处理，这里不回任何报文
        _stats["accepted"] += 1
        return None

    if frame.command not in (cmd.COMMAND_SEND_DATA, cmd.COMMAND_REQUEST, cmd.COMMAND_CONTROL):
        _stats["ignored"] += 1
        return _build_response(frame, cmd.COMMAND_DENY)

    try:
        app_type, objects = parse_app_data(frame.app_data)
    except FrameError as exc:
        _stats["errors"] += 1
        _stats["last_error"] = str(exc)
        return _build_response(frame, cmd.COMMAND_DENY)

    try:
        gb_device = auth.authenticate(db, frame.source_address, _credentials_from(app_type, objects))
    except auth.GB26875AuthError as exc:
        _stats["denied"] += 1
        _stats["last_error"] = exc.message
        logger.warning("GB26875 拒绝来自 %s 的报文：%s", frame.source_address, exc.message)
        return _build_response(frame, cmd.COMMAND_DENY)

    try:
        if frame.command == cmd.COMMAND_REQUEST:
            command, app_data = _handle_read_request(frame, app_type)
            _stats["accepted"] += 1
            return _build_response(frame, command, app_data)

        result = _ingest_payload(db, gb_device, app_type, objects, peer_ip, peer_port)
        _stats["accepted"] += 1
        return _build_response(frame, cmd.COMMAND_CONFIRM if result.get("ack") == "confirm" else cmd.COMMAND_DENY)
    except Exception as exc:  # noqa: BLE001 - 单帧异常不能中断连接
        db.rollback()
        _stats["errors"] += 1
        _stats["last_error"] = str(exc)
        logger.exception("GB26875 报文处理失败：%s", exc)
        return _build_response(frame, cmd.COMMAND_DENY)


def _credentials_from(app_type: int, objects: List[AppObject]) -> Optional[Tuple[str, str]]:
    """注册报文（用户信息传输装置配置情况）里携带的用户名/口令。"""
    if app_type != cmd.TYPE_TRANSMITTER_CONFIG:
        return None
    for obj in objects:
        found = auth.parse_credentials(obj.body)
        if found:
            return found
    return None


# ---------------- TCP 服务 ----------------

@dataclass
class _Connection:
    address: str
    writer: "asyncio.StreamWriter"
    peer_ip: str
    peer_port: int
    connected_at: datetime = field(default_factory=datetime.now)
    last_frame_at: Optional[datetime] = None
    sent: int = 0
    pending: Dict[int, "asyncio.Future"] = field(default_factory=dict)


_connections: Dict[str, _Connection] = {}


def connection_snapshot() -> List[Dict[str, Any]]:
    return [
        {
            "address": conn.address,
            "peer": f"{conn.peer_ip}:{conn.peer_port}",
            "connected_at": conn.connected_at.isoformat(),
            "last_frame_at": conn.last_frame_at.isoformat() if conn.last_frame_at else None,
            "sent": conn.sent,
        }
        for conn in _connections.values()
    ]


def _new_session() -> Session:
    return SessionLocal()


async def _handle_client(reader: "asyncio.StreamReader", writer: "asyncio.StreamWriter") -> None:
    peer = writer.get_extra_info("peername") or ("", 0)
    peer_ip = str(peer[0])
    peer_port = int(peer[1]) if len(peer) > 1 else 0
    buffer = b""
    conn: Optional[_Connection] = None
    loop = asyncio.get_running_loop()
    _stats["connections_total"] += 1

    try:
        while True:
            try:
                data = await asyncio.wait_for(reader.read(4096), timeout=IDLE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.info("GB26875 连接空闲超时，断开 %s:%s", peer_ip, peer_port)
                break
            if not data:
                break

            frames, buffer, errors = decode_stream(buffer + data)
            for err in errors:
                _stats["errors"] += 1
                _stats["last_error"] = err
                logger.warning("GB26875 报文解析异常：%s", err)

            for frame in frames:
                if conn is None:
                    conn = _Connection(
                        address=frame.source_address, writer=writer, peer_ip=peer_ip, peer_port=peer_port
                    )
                    _connections[frame.source_address] = conn
                conn.last_frame_at = datetime.utcnow()

                # 设备对中心下行命令的确认/否认：唤醒等待方，不进入上行处理
                if frame.command in (cmd.COMMAND_CONFIRM, cmd.COMMAND_DENY):
                    future = conn.pending.pop(frame.seq, None)
                    if future and not future.done():
                        future.set_result("confirm" if frame.command == cmd.COMMAND_CONFIRM else "deny")
                    continue

                response = await loop.run_in_executor(None, _process_in_session, frame, peer_ip, peer_port)
                if response:
                    writer.write(response)
                    conn.sent += 1
                    await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    except Exception as exc:  # noqa: BLE001 - 连接级异常只记日志
        logger.exception("GB26875 连接处理异常：%s", exc)
    finally:
        if conn is not None:
            _connections.pop(conn.address, None)
        try:
            writer.close()
        except Exception:
            pass


def _process_in_session(frame: Frame, peer_ip: str, peer_port: int) -> Optional[bytes]:
    """在独立数据库会话里处理一帧，避免与主应用线程共用会话。"""
    db = _new_session()
    try:
        return handle_frame(db, frame, peer_ip=peer_ip, peer_port=peer_port)
    finally:
        db.close()


async def send_and_wait(address: str, payload: bytes, seq: int, timeout: float = 5.0) -> str:
    """向指定地址下发命令并等待确认，返回 confirm / deny / timeout / offline。"""
    conn = _connections.get(address)
    if conn is None:
        return "offline"
    loop = asyncio.get_running_loop()
    future: "asyncio.Future" = loop.create_future()
    conn.pending[seq] = future
    try:
        conn.writer.write(payload)
        conn.sent += 1
        await conn.writer.drain()
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return "timeout"
    except (ConnectionResetError, BrokenPipeError):
        return "offline"
    finally:
        conn.pending.pop(seq, None)
