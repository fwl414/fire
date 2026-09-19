"""GB/T 26875 消防主机（用户信息传输装置）接入

对外接口：

    服务生命周期   start_gb26875_server / stop_gb26875_server / service_status
    下行命令       sync_device_time / initialize_device
    台账与身份     auth（resolve / authenticate / issue_credentials / device_view）
    报文编解码     frame（encode / decode / decode_stream / encode_app_data / parse_app_data）
    常量表         commands（命令字节、类型标志、系统类型、状态位）

接入链路与 HTTP / MQTT 共用 device_ingest_service.dispatch，不重复实现告警与工单逻辑。
"""
from . import auth, commands, frame, server, service
from .frame import (
    AppObject,
    ChecksumError,
    Frame,
    FrameError,
    decode,
    decode_address,
    decode_stream,
    decode_timestamp,
    encode,
    encode_address,
    encode_app_data,
    encode_timestamp,
    parse_app_data,
)
from .service import (
    initialize_device,
    service_status,
    start_gb26875_server,
    stop_gb26875_server,
    sync_device_time,
)

__all__ = [
    "AppObject",
    "ChecksumError",
    "Frame",
    "FrameError",
    "auth",
    "commands",
    "decode",
    "decode_address",
    "decode_stream",
    "decode_timestamp",
    "encode",
    "encode_address",
    "encode_app_data",
    "encode_timestamp",
    "frame",
    "initialize_device",
    "parse_app_data",
    "server",
    "service",
    "service_status",
    "start_gb26875_server",
    "stop_gb26875_server",
    "sync_device_time",
]
