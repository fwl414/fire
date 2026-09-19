"""GB28181 SIP 信令服务（UAS，UDP + TCP）

平台侧只实现国标接入必需的信令：

    设备 → 平台   REGISTER（Digest 认证）→ 200 OK，登记台账并记录注册有效期
    设备 → 平台   MESSAGE(Catalog/DeviceInfo/DeviceStatus/Alarm/Keepalive) → 200 OK
                  Catalog 解析后写入 video_channels；Alarm 转告警工单链路
    平台 → 设备   MESSAGE(DeviceControl) 云台控制
    平台 → 设备   INVITE（SDP 指向 ZLMediaKit 的 RTP 端口）→ 设备回 200 OK → ACK
    平台 → 设备   BYE 停流

媒体不经过本进程：RTP 直推 ZLMediaKit，由它转 HLS/FLV/WebRTC 给前端。

服务跑在独立线程的 asyncio 事件循环里（与 GB26875 接入同一套模式），
数据库访问统一放到线程池，避免阻塞信令循环。
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from database import Device, SessionLocal

from . import catalog, device_registry as registry, media_proxy
from .sip_stack import (
    SipMessage,
    SipParseError,
    build_request,
    build_response,
    build_sdp,
    extract_tag,
    extract_uri,
    extract_user,
    new_tag,
    parse_message,
    parse_sdp,
    reason_of,
    split_stream,
    verify_authorization,
    www_authenticate,
)

logger = logging.getLogger(__name__)

# ---------------- 配置 ----------------

def enabled() -> bool:
    return os.environ.get("GB28181_ENABLED", "false").strip().lower() == "true"


def listen_host() -> str:
    return (os.environ.get("GB28181_SIP_LISTEN_HOST") or "0.0.0.0").strip()


def sip_port() -> int:
    try:
        return int(os.environ.get("GB28181_SIP_LISTEN_PORT", "5060"))
    except (TypeError, ValueError):
        return 5060


def server_id() -> str:
    return (os.environ.get("GB28181_SIP_SERVER_ID") or "34020000002000000001").strip()


def sip_domain() -> str:
    return (os.environ.get("GB28181_SIP_DOMAIN") or "3402000000").strip()


def password() -> str:
    return (os.environ.get("GB28181_SIP_PASSWORD") or "").strip()


def realm() -> str:
    return (os.environ.get("GB28181_SIP_REALM") or sip_domain()).strip()


def register_expires() -> int:
    try:
        return int(os.environ.get("GB28181_REGISTER_EXPIRES", "3600"))
    except (TypeError, ValueError):
        return 3600


def media_rtp_host() -> str:
    """设备推流目标地址（必须是设备能访问到的地址，容器名对设备不可达）。"""
    return (
        os.environ.get("GB28181_MEDIA_RTP_HOST")
        or os.environ.get("GB28181_MEDIA_HTTP_HOST")
        or os.environ.get("GB28181_MEDIA_SERVER_HOST")
        or ""
    ).strip()


# ---------------- 运行状态 ----------------

@dataclass
class Dialog:
    """平台发起的一次点播会话（INVITE → 200 OK → ACK）。"""

    channel_gb_id: str
    device_gb_id: str
    stream_id: str
    call_id: str
    from_tag: str
    to_tag: str
    cseq: int
    target: Tuple[str, int]
    rtp_port: int = 0
    ssrc: str = ""
    remote_rtp: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    stopped: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_gb_id": self.channel_gb_id,
            "device_gb_id": self.device_gb_id,
            "stream_id": self.stream_id,
            "call_id": self.call_id,
            "rtp_port": self.rtp_port,
            "ssrc": self.ssrc,
            "remote_rtp": self.remote_rtp,
            "target": f"{self.target[0]}:{self.target[1]}",
            "started_at": self.started_at.isoformat(),
        }


_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None
_sip_lock = threading.Lock()
_udp_transport: Optional[asyncio.DatagramTransport] = None
_tcp_server: Optional[asyncio.AbstractServer] = None
_started_at: Optional[datetime] = None
_dialogs: Dict[str, Dialog] = {}
_pending: Dict[str, asyncio.Future] = {}
_catalog_events: Dict[str, asyncio.Event] = {}
_seq = random.randint(1, 1000)

_stats: Dict[str, Any] = {
    "received": 0,
    "sent": 0,
    "register_ok": 0,
    "register_denied": 0,
    "messages": 0,
    "catalog_updated": 0,
    "invites": 0,
    "bye": 0,
    "errors": 0,
    "last_error": "",
    "last_frame_at": None,
}


def _next_seq() -> int:
    global _seq
    _seq = _seq + 1 if _seq < 0x7FFFFFFF else 1
    return _seq


def _new_ssrc() -> str:
    return "0" + f"{random.randint(0, 99999):05d}" + f"{random.randint(0, 9999):04d}"


def service_status() -> Dict[str, Any]:
    return {
        "enabled": enabled(),
        "running": bool(_udp_transport is not None or _tcp_server is not None),
        "listen": f"{listen_host()}:{sip_port()}",
        "server_id": server_id(),
        "domain": sip_domain(),
        "auth_required": bool(password()),
        "media": {
            "api_base": media_proxy.api_base(),
            "rtp_host": media_rtp_host(),
            "http": f"{media_proxy.media_host()}:{media_proxy.media_http_port()}" if media_proxy.media_host() else "",
        },
        "started_at": _started_at.isoformat() if _started_at else None,
        "registered_devices": registry.online_snapshot(),
        "dialogs": [dialog.to_dict() for dialog in _dialogs.values()],
        "last_frame_at": _stats["last_frame_at"].isoformat() if _stats["last_frame_at"] else None,
        **{key: value for key, value in _stats.items() if key != "last_frame_at"},
    }


# ---------------- 数据库与媒体（线程池执行） ----------------

def _run_db(func: Callable[[Any], Any]) -> Any:
    db = SessionLocal()
    try:
        return func(db)
    finally:
        db.close()


async def _in_db(func: Callable[[Any], Any]) -> Any:
    return await asyncio.get_running_loop().run_in_executor(None, _run_db, func)


# ---------------- 发送 ----------------

def _send(payload: bytes, target: Tuple[str, int]) -> None:
    if _udp_transport is None:
        raise RuntimeError("SIP 服务未启动")
    _udp_transport.sendto(payload, target)
    _stats["sent"] += 1


async def _send_and_wait(payload: bytes, target: Tuple[str, int], call_id: str, timeout: float) -> Optional[SipMessage]:
    """发请求并等待同 Call-ID 的响应。"""
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _pending[call_id] = future
    try:
        _send(payload, target)
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        _pending.pop(call_id, None)


def _build_platform_request(
    method: str,
    uri: str,
    call_id: str,
    cseq: int,
    *,
    body: bytes = b"",
    content_type: str = "",
    from_tag: str = "",
    to_tag: str = "",
) -> bytes:
    """构造平台发出的请求。

    对话内请求（ACK/BYE）必须复用 INVITE 建立的 From tag 与设备返回的 To tag，
    否则设备会按「未知对话」拒绝（481）。
    """
    headers = {
        "Via": f"SIP/2.0/UDP {_local_via()};branch=z9hG4bK{new_tag()}",
        "From": f"<sip:{server_id()}@{sip_domain()}>;tag={from_tag or new_tag()}",
        "To": f"<{uri}>" + (f";tag={to_tag}" if to_tag else ""),
        "Call-ID": call_id,
        "CSeq": f"{cseq} {method}",
        "Max-Forwards": "70",
        "User-Agent": "fire-ai-agent-gb28181",
        "Contact": f"<sip:{server_id()}@{_local_via()}>",
    }
    return build_request(method, uri, headers, body, content_type=content_type)


def _local_via() -> str:
    host = (os.environ.get("GB28181_SIP_ADVERTISE_HOST") or "").strip() or listen_host()
    return f"{host}:{sip_port()}"


# ---------------- 请求处理 ----------------

def _device_id_of(msg: SipMessage) -> str:
    user = extract_user(extract_uri(msg.get("From")))
    if user:
        return user
    return extract_user(msg.uri)


def _handle_register(msg: SipMessage, source: Tuple[str, int], transport: str) -> bytes:
    device_id = _device_id_of(msg)
    if not device_id:
        _stats["register_denied"] += 1
        return build_response(msg, 400, reason_of(400), to_tag=new_tag())

    expected = password()
    authorization = msg.get("Authorization")
    if expected:
        if not authorization:
            _stats["register_denied"] += 1
            return build_response(
                msg, 401, reason_of(401),
                extra_headers={"WWW-Authenticate": www_authenticate(realm(), new_tag())},
            )
        if not verify_authorization(authorization, expected, "REGISTER", realm=realm()):
            _stats["register_denied"] += 1
            return build_response(
                msg, 403, reason_of(403),
                extra_headers={"WWW-Authenticate": www_authenticate(realm(), new_tag())},
            )

    expires_header = msg.get("Expires")
    try:
        expires = int(expires_header) if expires_header else register_expires()
    except ValueError:
        expires = register_expires()

    registry.register(device_id, remote_ip=source[0], remote_port=source[1], transport=transport, expires=expires)
    _stats["register_ok"] += 1
    logger.info("GB28181 设备注册成功：%s（%s:%s/%s）", device_id, source[0], source[1], transport)
    return build_response(
        msg, 200, reason_of(200),
        extra_headers={
            "Date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "Expires": str(expires),
            "Contact": f"<sip:{server_id()}@{_local_via()}>",
        },
        to_tag=new_tag(),
    )


def _handle_message(msg: SipMessage, source: Tuple[str, int]) -> Optional[bytes]:
    _stats["messages"] += 1
    cmd_type = catalog.parse_cmd_type(msg.body)
    device_id = _device_id_of(msg)

    if cmd_type == catalog.CMD_KEEPALIVE:
        registry.keepalive(device_id)
        return build_response(msg, 200, reason_of(200), to_tag=new_tag())

    if cmd_type == catalog.CMD_CATALOG:
        _handle_catalog(device_id, msg.body)
        return build_response(msg, 200, reason_of(200), to_tag=new_tag())

    if cmd_type == catalog.CMD_DEVICE_INFO:
        info = catalog.parse_device_info(msg.body)
        _handle_device_info(device_id, info)
        return build_response(msg, 200, reason_of(200), to_tag=new_tag())

    if cmd_type == catalog.CMD_ALARM:
        _handle_alarm(device_id, msg.body)
        return build_response(msg, 200, reason_of(200), to_tag=new_tag())

    if cmd_type in (catalog.CMD_DEVICE_STATUS, catalog.CMD_DEVICE_CONTROL):
        return build_response(msg, 200, reason_of(200), to_tag=new_tag())

    logger.info("GB28181 收到未处理的 MESSAGE：CmdType=%s from=%s", cmd_type or "?", device_id)
    return build_response(msg, 200, reason_of(200), to_tag=new_tag())


def _handle_catalog(device_id: str, body: bytes) -> None:
    """目录应答：写入通道台账，并唤醒等待中的 refresh-catalog 请求。"""
    def work(db) -> Dict[str, int]:
        parsed = catalog.parse_catalog(body)
        owner = parsed.get("device_id") or device_id
        result = registry.upsert_channels(db, owner, parsed["items"])
        runtime = registry.runtime_of(owner)
        if runtime:
            runtime.channel_count = len(parsed["items"])
            runtime.catalog_synced_at = datetime.utcnow()
        return result

    try:
        result = _run_db(work)
    except Exception as exc:  # noqa: BLE001 - 目录异常不能中断信令
        _stats["errors"] += 1
        _stats["last_error"] = f"目录解析失败：{exc}"
        logger.warning("GB28181 目录处理失败：%s", exc)
        return

    _stats["catalog_updated"] += 1
    event = _catalog_events.get(device_id)
    if event:
        event.set()
    logger.info("GB28181 目录已更新：device=%s 新增 %s 更新 %s", device_id, result["created"], result["updated"])


def _handle_device_info(device_id: str, info: Dict[str, Any]) -> None:
    def work(db):
        return registry.upsert_device(
            db,
            device_id,
            name=info.get("name") or "",
            manufacturer=info.get("manufacturer") or "",
            model=info.get("model") or "",
        )

    try:
        _run_db(work)
    except Exception as exc:  # noqa: BLE001
        _stats["errors"] += 1
        _stats["last_error"] = f"设备信息写入失败：{exc}"
        return
    runtime = registry.runtime_of(device_id)
    if runtime:
        runtime.name = info.get("name") or runtime.name
        runtime.manufacturer = info.get("manufacturer") or runtime.manufacturer
        runtime.model = info.get("model") or runtime.model
        runtime.firmware = info.get("firmware") or runtime.firmware


def _handle_alarm(device_id: str, body: bytes) -> None:
    """设备报警转告警链路（复用 device_ingest_service 的事件入口）。"""
    parsed = catalog.parse_alarm(body)
    priority = str(parsed.get("alarm_priority") or "1")
    severity = {"1": "critical", "2": "high", "3": "medium", "4": "low"}.get(priority, "high")

    def work(db):
        from services.device_ingest_service import ingest_event

        device = db.query(Device).filter(Device.device_code == device_id).first()
        if not device:
            return {"handled": False, "reason": "设备未建档，仅记录日志"}
        return ingest_event(db, device, {
            "event_type": "fire" if priority == "1" else "fault",
            "severity": severity,
            "description": parsed.get("alarm_description") or f"GB28181 设备 {device_id} 上报报警",
            "alarm_time": parsed.get("alarm_time") or "",
            "alarm_method": parsed.get("alarm_method") or "",
        }, source="gb28181")

    try:
        result = _run_db(work)
        logger.info("GB28181 报警处理：device=%s priority=%s result=%s", device_id, priority, result)
    except Exception as exc:  # noqa: BLE001
        _stats["errors"] += 1
        _stats["last_error"] = f"报警处理失败：{exc}"


def _handle_bye(msg: SipMessage) -> bytes:
    call_id = msg.call_id
    dialog = _dialogs.pop(call_id, None)
    if dialog:
        dialog.stopped = True
        _stats["bye"] += 1
        _close_media(dialog)
    return build_response(msg, 200, reason_of(200), to_tag=new_tag())


def _handle_invite_from_device(msg: SipMessage) -> bytes:
    """设备主动发起的 INVITE（语音对讲/回传）本项目暂不支持，明确拒绝而不是静默丢弃。"""
    logger.info("GB28181 收到设备发起的 INVITE（call-id=%s），暂不支持", msg.call_id)
    return build_response(msg, 488, "Not Acceptable Here", to_tag=new_tag())


def _close_media(dialog: Dialog) -> None:
    async def closer():
        try:
            await media_proxy.close_stream(dialog.stream_id)
        except media_proxy.MediaProxyError as exc:
            logger.warning("GB28181 关闭流失败：%s", exc)

    try:
        asyncio.get_running_loop().create_task(closer())
    except RuntimeError:
        pass


async def _dispatch(raw: bytes, source: Tuple[str, int], transport: str, send: Optional[Callable[[bytes], None]] = None) -> None:
    """处理一条 SIP 报文并回写响应。"""
    try:
        msg = parse_message(raw, source)
    except SipParseError as exc:
        _stats["errors"] += 1
        _stats["last_error"] = str(exc)
        logger.warning("GB28181 报文解析失败（%s）：%s", source, exc)
        return

    _stats["received"] += 1
    _stats["last_frame_at"] = datetime.utcnow()
    responder = send or (lambda data: _send(data, source))

    if not msg.is_request:
        # 平台请求的响应：唤醒等待方
        future = _pending.get(msg.call_id)
        if future and not future.done():
            future.set_result(msg)
        return

    method = msg.method
    if method == "REGISTER":
        response = _handle_register(msg, source, transport)
    elif method == "MESSAGE":
        response = _handle_message(msg, source)
    elif method == "OPTIONS":
        response = build_response(msg, 200, reason_of(200), to_tag=new_tag())
    elif method == "BYE":
        response = _handle_bye(msg)
    elif method == "INVITE":
        response = _handle_invite_from_device(msg)
    elif method == "ACK":
        response = None
    else:
        response = build_response(msg, 501, "Not Implemented", to_tag=new_tag())

    if response:
        responder(response)
        _stats["sent"] += 1


# ---------------- 平台主动下发 ----------------

async def _query_catalog_async(device_gb_id: str, target: Tuple[str, int], *, wait: float = 5.0) -> Dict[str, Any]:
    call_id = f"{new_tag()}@{sip_domain()}"
    sn = catalog.next_sn()
    body = catalog.build_catalog_query(device_gb_id, sn)
    event = _catalog_events.setdefault(device_gb_id, asyncio.Event())
    event.clear()
    payload = _build_platform_request(
        "MESSAGE", f"sip:{device_gb_id}@{target[0]}:{target[1]}", call_id, _next_seq(),
        body=body, content_type="Application/MANSCDP+xml",
    )
    response = await _send_and_wait(payload, target, call_id, timeout=wait)
    if response is None:
        return {"sent": True, "acknowledged": False, "catalog_received": False, "sn": sn,
                "message": "目录查询已下发，但设备未在超时内响应"}
    try:
        await asyncio.wait_for(event.wait(), timeout=wait)
        received = True
    except asyncio.TimeoutError:
        received = False
    return {
        "sent": True,
        "acknowledged": True,
        "catalog_received": received,
        "sn": sn,
        "message": "目录已刷新" if received else "设备已确认查询，目录回传较慢，请稍后重新查看通道列表",
    }


async def _start_play_async(channel_gb_id: str, device_gb_id: str, target: Tuple[str, int], *, wait: float = 8.0) -> Dict[str, Any]:
    stream_id = channel_gb_id
    rtp_host = media_rtp_host()
    if not media_proxy.enabled():
        return {"ok": False, "message": "未配置 GB28181_MEDIA_API_BASE，无法开流（需部署 ZLMediaKit 并配置其 API 地址）"}
    if not rtp_host:
        return {"ok": False, "message": "未配置 GB28181_MEDIA_RTP_HOST，无法告知设备推流地址"}

    port = await media_proxy.open_rtp_server(stream_id)
    ssrc = _new_ssrc()
    call_id = f"{new_tag()}@{sip_domain()}"
    cseq = _next_seq()
    from_tag = new_tag()
    uri = f"sip:{channel_gb_id}@{target[0]}:{target[1]}"
    sdp = build_sdp(rtp_host, port, ssrc, channel_uri=uri)

    payload = _build_platform_request(
        "INVITE", uri, call_id, cseq,
        body=sdp.encode("utf-8"), content_type="application/sdp", from_tag=from_tag,
    )
    response = await _send_and_wait(payload, target, call_id, timeout=wait)
    if response is None:
        await media_proxy.close_rtp_server(stream_id)
        _stats["errors"] += 1
        _stats["last_error"] = f"INVITE 无响应：{channel_gb_id}"
        return {"ok": False, "message": "设备未响应 INVITE（检查设备在线状态与推流地址可达性）"}

    if response.status_code != 200:
        await media_proxy.close_rtp_server(stream_id)
        _stats["errors"] += 1
        _stats["last_error"] = f"INVITE 被拒绝：{response.status_code}"
        return {"ok": False, "message": f"设备拒绝 INVITE：{response.status_code} {response.reason}"}

    # 200 OK 里带设备侧 SDP（SSRC/接收地址），随后必须回 ACK 才真正建立会话
    remote_sdp = parse_sdp(response.body_text)
    to_tag = extract_tag(response.get("To"))
    ack = _build_platform_request("ACK", uri, call_id, cseq, from_tag=from_tag, to_tag=to_tag)
    _send(ack, target)

    dialog = Dialog(
        channel_gb_id=channel_gb_id,
        device_gb_id=device_gb_id,
        stream_id=stream_id,
        call_id=call_id,
        from_tag=from_tag,
        to_tag=to_tag,
        cseq=cseq,
        target=target,
        rtp_port=port,
        ssrc=remote_sdp.ssrc or ssrc,
        remote_rtp=f"{remote_sdp.address}:{remote_sdp.port}" if remote_sdp.address else "",
    )
    _dialogs[call_id] = dialog
    _stats["invites"] += 1
    return {
        "ok": True,
        "dialog": dialog.to_dict(),
        "stream_id": stream_id,
        "rtp": f"{rtp_host}:{port}",
        "urls": media_proxy.play_urls(stream_id),
        "message": "已发起点播，媒体流到达后即可播放",
    }


async def _stop_play_async(channel_gb_id: str) -> Dict[str, Any]:
    for call_id, dialog in list(_dialogs.items()):
        if dialog.channel_gb_id != channel_gb_id:
            continue
        uri = f"sip:{dialog.channel_gb_id}@{dialog.target[0]}:{dialog.target[1]}"
        payload = _build_platform_request(
            "BYE", uri, call_id, dialog.cseq + 1, from_tag=dialog.from_tag, to_tag=dialog.to_tag
        )
        _send(payload, dialog.target)
        _dialogs.pop(call_id, None)
        try:
            await media_proxy.close_stream(dialog.stream_id)
            await media_proxy.close_rtp_server(dialog.stream_id)
        except media_proxy.MediaProxyError as exc:
            logger.warning("GB28181 停流时关闭媒体失败：%s", exc)
        _stats["bye"] += 1
        return {"ok": True, "message": "已停止点播", "dialog": dialog.to_dict()}
    return {"ok": False, "message": "该通道当前没有进行中的点播会话"}


async def _ptz_async(channel_gb_id: str, device_gb_id: str, target: Tuple[str, int], *, action: str = "", speed: int = 5, raw_cmd: str = "", wait: float = 5.0) -> Dict[str, Any]:
    sn = catalog.next_sn()
    body = catalog.build_device_control(device_gb_id, channel_gb_id, sn, ptz_cmd=raw_cmd, action=action, speed=speed)
    call_id = f"{new_tag()}@{sip_domain()}"
    payload = _build_platform_request(
        "MESSAGE", f"sip:{device_gb_id}@{target[0]}:{target[1]}", call_id, _next_seq(),
        body=body, content_type="Application/MANSCDP+xml",
    )
    response = await _send_and_wait(payload, target, call_id, timeout=wait)
    if response is None:
        return {"ok": False, "sn": sn, "message": "云台指令已下发，设备未在超时内确认"}
    return {"ok": response.status_code == 200, "sn": sn, "status_code": response.status_code,
            "message": "云台指令已下发" if response.status_code == 200 else f"设备拒绝云台指令：{response.status_code}"}


# ---------------- 线程与生命周期 ----------------

class _SipProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport) -> None:  # noqa: ANN001
        global _udp_transport
        _udp_transport = transport

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        asyncio.get_running_loop().create_task(_dispatch(data, addr, "udp"))


async def _handle_tcp_client(reader: "asyncio.StreamReader", writer: "asyncio.StreamWriter") -> None:
    peer = writer.get_extra_info("peername") or ("", 0)
    source = (str(peer[0]), int(peer[1]) if len(peer) > 1 else 0)
    buffer = b""
    try:
        while True:
            data = await reader.read(65535)
            if not data:
                break
            buffer += data
            messages, buffer = split_stream(buffer)
            for raw in messages:
                await _dispatch(raw, source, "tcp", send=lambda payload: writer.write(payload))
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _serve(host: str, port: int) -> Tuple[asyncio.DatagramTransport, asyncio.AbstractServer]:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(_SipProtocol, local_addr=(host, port))
    tcp = await asyncio.start_server(_handle_tcp_client, host, port)
    return transport, tcp


def _target_of(device_gb_id: str) -> Tuple[str, int]:
    runtime = registry.runtime_of(device_gb_id)
    if runtime and runtime.remote_ip:
        return runtime.remote_ip, runtime.remote_port or sip_port()
    return "", 0


def _call_sync(coro, timeout: float):
    loop = _loop
    if loop is None or not loop.is_running():
        return {"ok": False, "message": "GB28181 信令服务未运行"}
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=timeout + 15)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"信令执行失败：{exc}"}


def refresh_catalog(device_gb_id: str, *, wait: float = 5.0) -> Dict[str, Any]:
    target = _target_of(device_gb_id)
    if not target[0]:
        return {"ok": False, "message": "设备未注册或未记录远端地址，无法下发目录查询"}
    result = _call_sync(_query_catalog_async(device_gb_id, target, wait=wait), wait)
    return {"ok": bool(result.get("sent")), **result}


def start_play(channel_gb_id: str, device_gb_id: str, *, wait: float = 8.0) -> Dict[str, Any]:
    target = _target_of(device_gb_id)
    if not target[0]:
        return {"ok": False, "message": "设备未注册或未记录远端地址，无法发起点播"}
    return _call_sync(_start_play_async(channel_gb_id, device_gb_id, target, wait=wait), wait)


def stop_play(channel_gb_id: str, *, wait: float = 5.0) -> Dict[str, Any]:
    return _call_sync(_stop_play_async(channel_gb_id), wait)


def send_ptz(channel_gb_id: str, device_gb_id: str, *, action: str = "", speed: int = 5, raw_cmd: str = "", wait: float = 5.0) -> Dict[str, Any]:
    target = _target_of(device_gb_id)
    if not target[0]:
        return {"ok": False, "message": "设备未注册或未记录远端地址，无法下发云台指令"}
    return _call_sync(_ptz_async(channel_gb_id, device_gb_id, target, action=action, speed=speed, raw_cmd=raw_cmd, wait=wait), wait)


def live_urls(channel_gb_id: str) -> Dict[str, str]:
    return media_proxy.play_urls(channel_gb_id)


def active_dialog(channel_gb_id: str) -> Optional[Dict[str, Any]]:
    for dialog in _dialogs.values():
        if dialog.channel_gb_id == channel_gb_id:
            return dialog.to_dict()
    return None


async def _shutdown() -> None:
    global _udp_transport, _tcp_server
    for dialog in list(_dialogs.values()):
        try:
            await media_proxy.close_stream(dialog.stream_id)
        except Exception:
            pass
    _dialogs.clear()
    if _tcp_server is not None:
        _tcp_server.close()
        _tcp_server = None
    if _udp_transport is not None:
        _udp_transport.close()
        _udp_transport = None


def _thread_main(host: str, port: int, ready: threading.Event, errors: Dict[str, str]) -> None:
    global _loop, _udp_transport, _tcp_server
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop
    try:
        _udp_transport, _tcp_server = loop.run_until_complete(_serve(host, port))
    except Exception as exc:  # noqa: BLE001 - 端口占用等启动失败只记录
        errors["message"] = str(exc)
        ready.set()
        loop.close()
        _loop = None
        return

    ready.set()
    try:
        loop.run_forever()
    finally:
        try:
            loop.run_until_complete(_shutdown())
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass
        _loop = None


def start_gb28181_sip() -> bool:
    """启动 GB28181 SIP 服务（幂等）。未启用或启动失败返回 False。"""
    global _thread, _started_at
    if not enabled():
        print("[info] GB28181_ENABLED=false，跳过 GB28181 视频接入")
        return False

    with _sip_lock:
        if _thread is not None and _thread.is_alive():
            return True

        host, port = listen_host(), sip_port()
        ready = threading.Event()
        errors: Dict[str, str] = {}
        thread = threading.Thread(
            target=_thread_main, args=(host, port, ready, errors), name="gb28181-sip", daemon=True
        )
        thread.start()
        ready.wait(timeout=10)
        if errors:
            print(f"[error] GB28181 信令服务启动失败（{host}:{port}）：{errors['message']}")
            _thread = None
            return False

        _thread = thread
        _started_at = datetime.utcnow()
        print(f"[info] GB28181 视频接入已启动（{host}:{port}，{server_id()}）")
        return True


def stop_gb28181_sip() -> None:
    """停止服务（幂等）。"""
    global _thread, _started_at
    with _sip_lock:
        loop, thread = _loop, _thread
        _thread = None
        _started_at = None
    if loop is None or thread is None:
        return
    try:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
    except Exception:
        pass
    print("[info] GB28181 视频接入已停止")
