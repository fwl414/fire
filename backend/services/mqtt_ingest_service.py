"""设备 MQTT 接入服务

订阅主题规范：
    {MQTT_TOPIC_PREFIX}/{tenant_id}/{device_code}/{kind}
    kind ∈ telemetry | event | heartbeat

消息体（JSON 信封）：
    {"timestamp": 1710000000, "nonce": "<每次唯一>", "signature": "<hex>", "data": {...}}
    签名对象为 data 的规范 JSON（sort_keys=True，separators=(",", ":")），
    与 HTTP 通道使用同一签名公式（见 device_auth_service）。

本服务为可选能力：未安装 paho-mqtt 或 MQTT_ENABLED 非 true 时不启动，不影响其他功能。
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from database import SessionLocal
from services import device_message_service, task_queue_service as task_queue
from services.device_auth_service import (
    DeviceAuthError,
    canonical_payload_bytes,
    verify_device_request,
)

# 设备消息处理任务：由后台任务队列执行，失败按次数重试后进入死信
DEVICE_MESSAGE_TASK = "device_message"
DEVICE_MESSAGE_MAX_ATTEMPTS = int(os.environ.get("DEVICE_MESSAGE_MAX_ATTEMPTS", "3"))

MQTT_ENABLED = os.environ.get("MQTT_ENABLED", "false").lower() == "true"
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
MQTT_USE_TLS = os.environ.get("MQTT_USE_TLS", "false").lower() == "true"
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "fire")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "fire-ai-agent-backend")
# 多实例部署：MQTT client_id 必须每个进程唯一，否则会互相顶掉连接导致反复重连
MQTT_CLIENT_ID = f"{MQTT_CLIENT_ID}-{os.getpid()}"
# 共享订阅组：多实例同时订阅时，broker 只把每条消息投给组内一个实例（避免重复消费）。
# 留空表示普通订阅；此时靠 device_messages 的幂等约束兜底重复投递。
MQTT_SHARED_GROUP = os.environ.get("MQTT_SHARED_GROUP", "").strip()

VALID_KINDS = ("telemetry", "event", "heartbeat")

_client = None
_client_lock = threading.Lock()
_stats: Dict[str, Any] = {
    "received": 0,
    "accepted": 0,
    "queued": 0,
    "duplicated": 0,
    "rejected": 0,
    "last_error": "",
}


def subscription_topics() -> list:
    """订阅主题；配置了共享订阅组时加 `$share/{group}/` 前缀。

    多实例部署若用普通订阅，每个实例都会收到同一条消息（重复消费）；
    共享订阅让 broker 在组内只选一个实例投递，从源头避免重复。
    """
    base = [f"{MQTT_TOPIC_PREFIX}/+/{'+'}/{kind}" for kind in VALID_KINDS]
    if not MQTT_SHARED_GROUP:
        return base
    return [f"$share/{MQTT_SHARED_GROUP}/{topic}" for topic in base]


def parse_topic(topic: str) -> Optional[Tuple[int, str, str]]:
    """解析主题，返回 (tenant_id, device_code, kind)；不符合规范返回 None。"""
    parts = str(topic or "").split("/")
    if len(parts) != 4:
        return None
    prefix, tenant_raw, device_code, kind = parts
    if prefix != MQTT_TOPIC_PREFIX or kind not in VALID_KINDS or not device_code:
        return None
    try:
        tenant_id = int(tenant_raw)
    except (TypeError, ValueError):
        return None
    return tenant_id, device_code, kind


def handle_message(topic: str, payload: bytes, db=None) -> Dict[str, Any]:
    """处理单条 MQTT 消息（纯函数式，便于单测，不依赖 broker 连接）。

    分工：**验签与落收件箱在这里同步完成**（不能让未验签的数据落库），
    真正的业务处理（阈值判定、告警、工单）交给后台任务队列异步执行——
    MQTT 是即发即弃的，回调里同步跑业务会阻塞消费线程、失败也无法重试。
    """
    _stats["received"] += 1

    parsed = parse_topic(topic)
    if not parsed:
        _stats["rejected"] += 1
        _stats["last_error"] = f"主题不符合规范：{topic}"
        return {"ok": False, "reason": _stats["last_error"]}

    tenant_id, device_code, kind = parsed
    try:
        envelope = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _stats["rejected"] += 1
        _stats["last_error"] = f"消息体解析失败：{exc}"
        return {"ok": False, "reason": _stats["last_error"]}

    if not isinstance(envelope, dict):
        _stats["rejected"] += 1
        _stats["last_error"] = "消息体必须是 JSON 对象"
        return {"ok": False, "reason": _stats["last_error"]}

    data = envelope.get("data")
    if not isinstance(data, dict):
        _stats["rejected"] += 1
        _stats["last_error"] = "缺少 data 字段"
        return {"ok": False, "reason": _stats["last_error"]}

    owns_session = db is None
    session = db or SessionLocal()
    try:
        # 1) 验签：必须在同步路径完成，未验签的数据不得落库
        try:
            device = verify_device_request(
                session,
                device_code=device_code,
                timestamp=str(envelope.get("timestamp", "")),
                nonce=str(envelope.get("nonce", "")),
                signature=str(envelope.get("signature", "")),
                payload_bytes=canonical_payload_bytes(data),
                tenant_id=tenant_id,
            )
        except DeviceAuthError as exc:
            _stats["rejected"] += 1
            _stats["last_error"] = f"{device_code}: {exc.message}"
            return {"ok": False, "reason": exc.message, "status_code": exc.status_code}
        except ValueError as exc:
            _stats["rejected"] += 1
            _stats["last_error"] = f"{device_code}: {exc}"
            return {"ok": False, "reason": str(exc)}

        # 验签通过后立刻取出标量值：后续多次 commit 会让 ORM 实例过期，
        # 而本函数末尾会关闭会话，不能再去触碰实例属性
        device_row_id = device.id
        resolved_code = device.device_code

        # 2) 落收件箱：靠 (tenant_id, message_id) 唯一约束实现端到端幂等
        row, duplicated = device_message_service.begin_message(
            session,
            tenant_id=tenant_id,
            device_code=resolved_code,
            kind=kind,
            envelope=envelope,
            source="mqtt",
            topic=topic,
            device_id=device_row_id,
        )
        if duplicated:
            _stats["duplicated"] += 1
            return {
                "ok": True,
                "duplicate": True,
                "kind": kind,
                "message_id": row.message_id if row else "",
                "device_code": resolved_code,
                "reason": "同一消息重复投递，已忽略",
            }

        # 3) 交给后台任务队列，回调立即返回，不阻塞 MQTT 消费线程
        try:
            task_queue.enqueue(
                session,
                task_type=DEVICE_MESSAGE_TASK,
                payload={"message_id": row.message_id},
                tenant_id=tenant_id,
                task_name=f"设备消息 {resolved_code}/{kind}",
                total_items=1,
                max_attempts=DEVICE_MESSAGE_MAX_ATTEMPTS,
                created_by_name="设备接入",
            )
        except Exception as exc:  # noqa: BLE001
            _stats["rejected"] += 1
            _stats["last_error"] = f"{device_code}: 任务入队失败 {exc}"
            device_message_service.mark_failed(session, row.id, f"任务入队失败：{exc}", dead=True)
            return {"ok": False, "reason": f"任务入队失败：{exc}"}

        message_id = row.message_id
    except Exception as exc:  # 单条消息异常不应中断订阅
        _stats["rejected"] += 1
        _stats["last_error"] = f"{device_code}: {exc}"
        return {"ok": False, "reason": f"消息处理异常：{exc}"}
    finally:
        if owns_session:
            session.close()

    _stats["accepted"] += 1
    _stats["queued"] += 1
    return {
        "ok": True,
        "queued": True,
        "kind": kind,
        "topic": topic,
        "device_code": resolved_code,
        "message_id": message_id,
    }


def mqtt_stats() -> Dict[str, Any]:
    return {
        "enabled": MQTT_ENABLED,
        "connected": bool(_client is not None),
        "broker": f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}",
        "topic_prefix": MQTT_TOPIC_PREFIX,
        "subscriptions": subscription_topics(),
        **_stats,
    }


def _build_client():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("[warn] 未安装 paho-mqtt，MQTT 设备接入未启动（pip install paho-mqtt）")
        return None

    def on_connect(client, userdata, flags, reason_code, properties=None):
        for topic in subscription_topics():
            client.subscribe(topic, qos=1)
        print(f"[info] MQTT 已连接 {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}，订阅 {subscription_topics()}")

    def on_message(client, userdata, message):
        try:
            result = handle_message(message.topic, message.payload)
            if not result.get("ok"):
                print(f"[warn] MQTT 消息被拒绝：{result.get('reason')}")
        except Exception as exc:  # 保证消费线程存活
            print(f"[error] MQTT 消息处理异常：{exc}")

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_USE_TLS:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    return client


def start_mqtt() -> bool:
    """启动 MQTT 订阅（幂等）。未启用或缺少依赖时返回 False。"""
    global _client
    if not MQTT_ENABLED:
        print("[info] MQTT_ENABLED=false，跳过设备 MQTT 接入")
        return False

    with _client_lock:
        if _client is not None:
            return True
        client = _build_client()
        if client is None:
            return False
        try:
            client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
            client.loop_start()
        except Exception as exc:
            print(f"[error] MQTT 连接失败：{exc}")
            return False
        _client = client
        print(f"[info] MQTT 设备接入已启动（{datetime.utcnow().isoformat()}Z）")
        return True


def stop_mqtt() -> None:
    global _client
    with _client_lock:
        if _client is None:
            return
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
        _client = None
        print("[info] MQTT 设备接入已停止")
