"""告警外部通知通道

站内通知由 WebSocket 实时推送（`websocket_service.send_alert_notification`）+ 通知中心聚合
提供；本模块负责把告警推送到**外部**通道，让没人盯屏时也能收到：

    通用 Webhook / 企业微信群机器人 / 钉钉群机器人 / 邮件

链路：

    ingest_alert 产生（或升级）告警
        → enqueue_alert_notifications 按「通道启用 + 最低级别 + 告警类型」匹配通道
        → 为每个命中通道写一条 notification_deliveries 台账并投递后台任务
        → worker 执行 deliver → 真正发送 → 记录成功/失败（失败自动重试）

三条刻意的设计：

1. **一个告警在同一通道上只发一次**：`(alert_code, channel_id)` 唯一约束既是幂等键，
   也是发送台账；升级后的告警若上次发送失败，允许复用该行重发。
2. **通知失败绝不能影响告警入库**：`enqueue_alert_notifications` 内部吞掉所有异常并记日志，
   告警本身已经在库里，不能因为「推送不出去」把告警一起丢掉。
3. **密钥不落明文、不回传**：群机器人 Webhook、SMTP 口令等字段用
   `video_credential_cipher` 加密落库，接口只回「已配置」与掩码。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import AlertRecord, NotificationChannel, NotificationDelivery
from services import video_credential_cipher
from services import task_queue_service as task_queue

logger = logging.getLogger(__name__)

# 后台任务类型：一条告警在一个通道上的投递
TASK_TYPE_ALERT_NOTIFY = "alert_notify"

MASK = "******"


# 通道类型 → 表单字段定义（前端据此渲染表单，后端据此校验与决定哪些字段要加密）
CHANNEL_TYPES: Dict[str, Dict[str, Any]] = {
    "webhook": {
        "label": "通用 Webhook",
        "description": "以 JSON POST 到你自己的告警接收端；配置签名密钥后会在 X-Signature 头带 HMAC-SHA256。",
        "fields": [
            {"key": "url", "label": "回调地址", "required": True, "secret": False, "placeholder": "https://example.com/hooks/fire-alert"},
            {"key": "secret", "label": "签名密钥（可选）", "required": False, "secret": True},
        ],
    },
    "wecom": {
        "label": "企业微信群机器人",
        "description": "在企业微信群中添加「群机器人」，把 Webhook 地址填到这里。",
        "fields": [
            {"key": "url", "label": "机器人 Webhook 地址", "required": True, "secret": True,
             "placeholder": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."},
        ],
    },
    "dingtalk": {
        "label": "钉钉群机器人",
        "description": "钉钉「自定义机器人」；若安全设置选的是「加签」，请把加签密钥一起填上。",
        "fields": [
            {"key": "url", "label": "机器人 Webhook 地址", "required": True, "secret": True,
             "placeholder": "https://oapi.dingtalk.com/robot/send?access_token=..."},
            {"key": "secret", "label": "加签密钥（安全设置=加签时必填）", "required": False, "secret": True},
        ],
    },
    "email": {
        "label": "邮件",
        "description": "用 SMTP 发送；465 端口走 SSL，587 端口走 STARTTLS。",
        "fields": [
            {"key": "smtp_host", "label": "SMTP 服务器", "required": True, "secret": False, "placeholder": "smtp.example.com"},
            {"key": "smtp_port", "label": "端口", "required": False, "secret": False, "placeholder": "465"},
            {"key": "smtp_user", "label": "账号", "required": False, "secret": False},
            {"key": "password", "label": "口令 / 授权码", "required": False, "secret": True},
            {"key": "sender", "label": "发件人（留空用账号）", "required": False, "secret": False},
            {"key": "recipients", "label": "收件人（多个用逗号分隔）", "required": True, "secret": False,
             "placeholder": "fire-safety@example.com,oncall@example.com"},
            {"key": "use_ssl", "label": "使用 SSL（465）", "required": False, "secret": False, "placeholder": "true"},
        ],
    },
}


class NotificationSendError(RuntimeError):
    """一次投递发送失败（可重试）。"""


# ---------------- 配置项 ----------------

def notify_enabled() -> bool:
    return os.environ.get("ALERT_NOTIFY_ENABLED", "true").strip().lower() == "true"


def timeout_seconds() -> float:
    try:
        return float(os.environ.get("ALERT_NOTIFY_TIMEOUT_SECONDS", "10"))
    except (TypeError, ValueError):
        return 10.0


def max_attempts() -> int:
    try:
        return max(1, int(os.environ.get("ALERT_NOTIFY_MAX_ATTEMPTS", "3")))
    except (TypeError, ValueError):
        return 3


def channel_types() -> List[Dict[str, Any]]:
    return [
        {"channel_type": key, **spec, "secret_fields": [f["key"] for f in spec["fields"] if f.get("secret")]}
        for key, spec in CHANNEL_TYPES.items()
    ]


def severity_levels() -> List[Dict[str, str]]:
    return [{"value": key, "label": _severity_label(key)} for key in _severity_order()]


def _severity_order() -> List[str]:
    # 级别顺序与文案都用告警生命周期服务那一份，避免两处各写一套
    from services.alert_lifecycle_service import SEVERITY_ORDER

    return list(SEVERITY_ORDER)


def _severity_label(value: str) -> str:
    from services.alert_lifecycle_service import ALERT_SEVERITY_LABELS

    return ALERT_SEVERITY_LABELS.get(value, value or "")


def _severity_index(severity: str) -> int:
    try:
        return _severity_order().index(str(severity or "").lower())
    except ValueError:
        return 0


# ---------------- 密钥字段加解密与脱敏 ----------------

def _secret_fields(channel_type: str) -> set:
    spec = CHANNEL_TYPES.get(channel_type) or {}
    return {field["key"] for field in spec.get("fields", []) if field.get("secret")}


def _encrypt_config(channel_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    secrets = _secret_fields(channel_type)
    encrypted: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key in secrets and value:
            encrypted[key] = video_credential_cipher.encrypt_secret(str(value))
        else:
            encrypted[key] = value
    return encrypted


def _decrypt_config(channel_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    secrets = _secret_fields(channel_type)
    plain: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key in secrets and value:
            try:
                plain[key] = video_credential_cipher.decrypt_secret(str(value))
            except video_credential_cipher.CredentialCipherError as exc:
                raise NotificationSendError(f"通道密钥无法解密，请重新填写：{exc}") from exc
        else:
            plain[key] = value
    return plain


def serialize(channel: NotificationChannel) -> Dict[str, Any]:
    """通道视图：密钥字段只回掩码与「是否已配置」。"""
    spec = CHANNEL_TYPES.get(channel.channel_type)
    fields = {field["key"]: field for field in (spec["fields"] if spec else [])}
    config: Dict[str, Any] = {}
    secrets_configured: Dict[str, bool] = {}
    for key, value in (channel.config or {}).items():
        if fields.get(key, {}).get("secret"):
            secrets_configured[key] = bool(value)
            config[key] = MASK if value else ""
        else:
            config[key] = value

    missing = []
    if spec:
        for field in spec["fields"]:
            if not field.get("required"):
                continue
            key = field["key"]
            has_value = bool(secrets_configured.get(key)) if field.get("secret") else bool(str(config.get(key) or "").strip())
            if not has_value:
                missing.append(field["label"])

    return {
        "id": channel.id,
        "tenant_id": channel.tenant_id,
        "name": channel.name,
        "channel_type": channel.channel_type,
        "channel_type_label": spec["label"] if spec else channel.channel_type,
        "enabled": bool(channel.enabled),
        "config": config,
        "secrets_configured": secrets_configured,
        "min_severity": channel.min_severity or "high",
        "min_severity_label": _severity_label(channel.min_severity or "high"),
        "alert_types": channel.alert_types or [],
        "remark": channel.remark or "",
        "last_success_at": channel.last_success_at.isoformat() if channel.last_success_at else "",
        "last_error": channel.last_error or "",
        "last_error_at": channel.last_error_at.isoformat() if channel.last_error_at else "",
        "created_at": channel.created_at.isoformat() if channel.created_at else "",
        "updated_at": channel.updated_at.isoformat() if channel.updated_at else "",
        "ready": bool(channel.enabled and not missing),
        "missing_fields": missing,
    }


def delivery_view(row: NotificationDelivery) -> Dict[str, Any]:
    return {
        "id": row.id,
        "alert_code": row.alert_code,
        "channel_id": row.channel_id,
        "channel_type": row.channel_type,
        "status": row.status,
        "attempts": row.attempts or 0,
        "error": row.error or "",
        "response_excerpt": row.response_excerpt or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


# ---------------- 通道 CRUD ----------------

def _normalize_alert_types(raw: Any) -> List[str]:
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        items = [piece.strip() for piece in raw.replace("，", ",").split(",")]
    else:
        items = [str(piece).strip() for piece in raw]
    return [item for item in items if item]


def _validate(channel_type: str, config: Dict[str, Any]) -> str:
    spec = CHANNEL_TYPES.get(channel_type)
    if not spec:
        return f"不支持的通道类型：{channel_type}"
    for field in spec["fields"]:
        if field.get("required") and not str(config.get(field["key"]) or "").strip():
            return f"{field['label']}不能为空"
    if channel_type == "email":
        recipients = str(config.get("recipients") or "")
        if "@" not in recipients:
            return "收件人至少填一个邮箱地址"
    else:
        url = str(config.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            return "回调地址必须以 http:// 或 https:// 开头"
    return ""


def _incoming_config(channel_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """只保留该类型声明过的字段（避免前端塞入任意键），密钥字段保留原值由调用方决定。"""
    spec = CHANNEL_TYPES.get(channel_type) or {}
    allowed = {field["key"] for field in spec.get("fields", [])}
    return {key: value for key, value in (raw or {}).items() if key in allowed}


def list_channels(db: Session, tenant_id: Optional[int]) -> List[NotificationChannel]:
    query = db.query(NotificationChannel)
    if tenant_id is not None:
        query = query.filter(NotificationChannel.tenant_id == tenant_id)
    return query.order_by(NotificationChannel.id.asc()).all()


def get_channel(db: Session, tenant_id: Optional[int], channel_id: int) -> Optional[NotificationChannel]:
    query = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id)
    if tenant_id is not None:
        query = query.filter(NotificationChannel.tenant_id == tenant_id)
    return query.first()


def create_channel(db: Session, tenant_id: Optional[int], payload: Dict[str, Any]) -> NotificationChannel:
    channel_type = str(payload.get("channel_type") or "webhook").strip().lower()
    config = _incoming_config(channel_type, payload.get("config") or {})
    error = _validate(channel_type, config)
    if error:
        raise ValueError(error)

    name = str(payload.get("name") or "").strip() or CHANNEL_TYPES[channel_type]["label"]
    channel = NotificationChannel(
        tenant_id=tenant_id,
        name=name,
        channel_type=channel_type,
        enabled=bool(payload.get("enabled", True)),
        config=_encrypt_config(channel_type, config),
        min_severity=str(payload.get("min_severity") or "high").strip().lower(),
        alert_types=_normalize_alert_types(payload.get("alert_types")),
        remark=str(payload.get("remark") or ""),
    )
    if channel.min_severity not in _severity_order():
        raise ValueError("最低推送级别只能是 low / medium / high / critical")
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def update_channel(db: Session, channel: NotificationChannel, payload: Dict[str, Any]) -> NotificationChannel:
    channel_type = str(payload.get("channel_type") or channel.channel_type).strip().lower()
    stored_plain = _decrypt_config(channel.channel_type, channel.config or {})
    incoming = _incoming_config(channel_type, payload.get("config") or {})

    # 密钥字段留空或仍是掩码 → 沿用已保存的值（前端不需要回显密钥也能改其它字段）
    secrets = _secret_fields(channel_type)
    for key in secrets:
        if key in incoming and str(incoming[key] or "").strip() in ("", MASK):
            incoming[key] = stored_plain.get(key, "")
    for key, value in stored_plain.items():
        incoming.setdefault(key, value)

    error = _validate(channel_type, incoming)
    if error:
        raise ValueError(error)

    if payload.get("name") is not None:
        channel.name = str(payload.get("name") or "").strip() or CHANNEL_TYPES.get(channel_type, {}).get("label", channel.name)
    if payload.get("min_severity") is not None:
        severity = str(payload["min_severity"]).strip().lower()
        if severity not in _severity_order():
            raise ValueError("最低推送级别只能是 low / medium / high / critical")
        channel.min_severity = severity
    if payload.get("alert_types") is not None:
        channel.alert_types = _normalize_alert_types(payload.get("alert_types"))
    if payload.get("enabled") is not None:
        channel.enabled = bool(payload.get("enabled"))
    if payload.get("remark") is not None:
        channel.remark = str(payload.get("remark") or "")

    channel.channel_type = channel_type
    channel.config = _encrypt_config(channel_type, incoming)
    channel.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(channel)
    return channel


def delete_channel(db: Session, channel: NotificationChannel) -> None:
    db.delete(channel)
    db.commit()


def list_deliveries(
    db: Session,
    tenant_id: Optional[int],
    *,
    channel_id: Optional[int] = None,
    alert_code: str = "",
    limit: int = 50,
) -> List[NotificationDelivery]:
    query = db.query(NotificationDelivery)
    if tenant_id is not None:
        query = query.filter(NotificationDelivery.tenant_id == tenant_id)
    if channel_id:
        query = query.filter(NotificationDelivery.channel_id == channel_id)
    if alert_code:
        query = query.filter(NotificationDelivery.alert_code == alert_code)
    return query.order_by(NotificationDelivery.id.desc()).limit(max(1, min(200, limit))).all()


# ---------------- 匹配与入队 ----------------

def match_channels(
    db: Session,
    tenant_id: Optional[int],
    severity: str,
    alert_type: str = "",
) -> List[NotificationChannel]:
    """命中条件：通道启用 + 告警级别不低于 min_severity + 告警类型在允许列表内（空=不限）。"""
    channels = [
        channel
        for channel in list_channels(db, tenant_id)
        if channel.enabled and channel.channel_type in CHANNEL_TYPES
    ]
    current = _severity_index(severity)
    matched = []
    for channel in channels:
        if current < _severity_index(channel.min_severity or "high"):
            continue
        allowed = channel.alert_types or []
        if allowed and alert_type and alert_type not in allowed:
            continue
        matched.append(channel)
    return matched


def _ensure_delivery(
    db: Session,
    alert: AlertRecord,
    channel: NotificationChannel,
    *,
    allow_retry: bool,
) -> Optional[NotificationDelivery]:
    """取得（或创建）投递台账；已成功或已在处理中的返回 None（幂等跳过）。"""
    existing = (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.alert_code == alert.alert_code,
            NotificationDelivery.channel_id == channel.id,
        )
        .first()
    )
    if existing:
        if existing.status == "success":
            return None
        if existing.status == "pending":
            return None
        # failed：仅在告警升级时允许复用该行重发（首次创建阶段不重发）
        if not allow_retry:
            return None
        existing.status = "pending"
        existing.error = ""
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    row = NotificationDelivery(
        tenant_id=alert.tenant_id,
        alert_code=alert.alert_code,
        channel_id=channel.id,
        channel_type=channel.channel_type,
        status="pending",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(row)
    return row


def enqueue_alert_notifications(db: Session, alert: AlertRecord, *, reason: str = "created") -> Dict[str, Any]:
    """把一条告警投递给所有命中的通道（写台账 + 入队）。任何异常都不向上抛。"""
    if not notify_enabled():
        return {"queued": 0, "reason": "ALERT_NOTIFY_ENABLED=false"}

    try:
        channels = match_channels(db, alert.tenant_id, alert.severity, alert.alert_type)
    except Exception as exc:  # noqa: BLE001 - 通知配置有问题不能影响告警入库
        logger.warning("告警通知通道匹配失败（alert=%s）：%s", alert.alert_code, exc)
        return {"queued": 0, "error": str(exc)}

    if not channels:
        return {"queued": 0, "reason": "没有命中任何已启用的通道"}

    queued = 0
    for channel in channels:
        try:
            row = _ensure_delivery(db, alert, channel, allow_retry=(reason == "escalated"))
            if row is None:
                continue
            task_queue.enqueue(
                db,
                task_type=TASK_TYPE_ALERT_NOTIFY,
                payload={"delivery_id": row.id},
                tenant_id=alert.tenant_id,
                task_name=f"告警通知 {alert.alert_code} → {channel.name}",
                total_items=1,
                max_attempts=max_attempts(),
                created_by_name="告警通知",
            )
            queued += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("告警通知入队失败（alert=%s channel=%s）：%s", alert.alert_code, channel.id, exc)

    return {"queued": queued, "matched_channels": len(channels), "reason": reason}


# ---------------- 发送 ----------------

def render_alert_text(alert: AlertRecord, *, title_prefix: str = "智慧消防告警") -> Tuple[str, str]:
    """把告警渲染成 (标题, 正文)，各通道共用同一份文案。"""
    from services.alert_lifecycle_service import ALERT_SEVERITY_LABELS, ALERT_STATUS_LABELS

    severity_label = ALERT_SEVERITY_LABELS.get(alert.severity, alert.severity)
    status_label = ALERT_STATUS_LABELS.get(alert.status, alert.status)
    title = f"【{severity_label}】{title_prefix} · {alert.alert_type}"
    lines = [
        f"告警编号：{alert.alert_code}",
        f"级别：{severity_label}（{alert.severity}）",
        f"状态：{status_label}",
        f"类型：{alert.alert_type}",
        f"设备：{alert.device_name or '-'}（{alert.device_code or '-'}）",
        f"位置：{alert.location or alert.building_name or '-'}",
    ]
    if alert.alert_value:
        lines.append(f"数值：{alert.alert_value}{alert.alert_unit or ''}")
    if alert.repeat_count and alert.repeat_count > 1:
        lines.append(f"重复次数：{alert.repeat_count}")
    if alert.escalated:
        lines.append(f"升级原因：{alert.escalation_reason or '-'}")
    if alert.created_at:
        lines.append(f"首次发生：{alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if alert.description:
        lines.append("")
        lines.append(f"描述：{alert.description}")
    return title, "\n".join(lines)


def _dingtalk_signed_url(url: str, secret: str) -> str:
    timestamp = str(int(time.time() * 1000))
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp}\n{secret}".encode("utf-8"), hashlib.sha256).digest()
    sign = quote(base64.b64encode(digest).decode("utf-8"), safe="")
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}timestamp={timestamp}&sign={sign}"


def _build_request(channel: NotificationChannel, config: Dict[str, Any], title: str, text: str) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """按通道类型构造 (url, headers, json_body)。"""
    if channel.channel_type == "wecom":
        return config["url"], {}, {"msgtype": "text", "text": {"content": f"{title}\n{text}"}}

    if channel.channel_type == "dingtalk":
        url = config["url"]
        if config.get("secret"):
            url = _dingtalk_signed_url(url, str(config["secret"]))
        return url, {}, {"msgtype": "markdown", "markdown": {"title": title, "text": f"### {title}\n\n{text}"}}

    # 通用 webhook：结构固定，接收端按 alert 字段取用；带密钥则附 HMAC-SHA256 签名
    body = {
        "type": "fire_alert",
        "title": title,
        "text": text,
        "sent_at": datetime.utcnow().isoformat() + "Z",
        "alert": {
            "alert_code": "",
            "alert_type": "",
            "severity": "",
            "status": "",
            "device_code": "",
            "device_name": "",
            "location": "",
            "description": "",
            "repeat_count": 0,
            "escalated": False,
        },
    }
    return config["url"], {}, body


def _apply_alert_to_body(body: Dict[str, Any], alert: AlertRecord) -> Dict[str, Any]:
    if isinstance(body.get("alert"), dict):
        body["alert"].update({
            "alert_code": alert.alert_code,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "device_code": alert.device_code or "",
            "device_name": alert.device_name or "",
            "location": alert.location or alert.building_name or "",
            "description": alert.description or "",
            "alert_value": alert.alert_value,
            "alert_unit": alert.alert_unit or "",
            "repeat_count": alert.repeat_count or 1,
            "escalated": bool(alert.escalated),
        })
    return body


def _post_json(url: str, body: Dict[str, Any], headers: Dict[str, str]) -> str:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json; charset=utf-8", **headers}
    try:
        with httpx.Client(timeout=timeout_seconds()) as client:
            response = client.post(url, content=payload, headers=request_headers)
    except httpx.HTTPError as exc:
        raise NotificationSendError(f"请求失败：{exc}") from exc

    excerpt = (response.text or "")[:200]
    if response.status_code >= 400:
        raise NotificationSendError(f"HTTP {response.status_code}：{excerpt}")

    # 企业微信/钉钉都用 200 + errcode 表达业务失败
    if excerpt.strip().startswith("{"):
        try:
            data = json.loads(response.text)
        except ValueError:
            data = {}
        errcode = data.get("errcode")
        if errcode not in (None, 0):
            raise NotificationSendError(f"接口返回 errcode={errcode} errmsg={data.get('errmsg')}")
    return excerpt


def _send_email(config: Dict[str, Any], title: str, text: str) -> str:
    recipients = [item.strip() for item in str(config.get("recipients") or "").replace("，", ",").split(",") if item.strip()]
    if not recipients:
        raise NotificationSendError("未配置收件人")

    message = EmailMessage()
    message["Subject"] = title
    message["From"] = str(config.get("sender") or config.get("smtp_user") or "")
    message["To"] = ", ".join(recipients)
    message.set_content(text)

    host = str(config.get("smtp_host") or "")
    try:
        port = int(config.get("smtp_port") or 465)
    except (TypeError, ValueError):
        port = 465
    use_ssl = str(config.get("use_ssl", "true")).strip().lower() not in ("false", "0", "no")
    user = str(config.get("smtp_user") or "")
    password = str(config.get("password") or "")

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout_seconds())
        else:
            server = smtplib.SMTP(host, port, timeout=timeout_seconds())
        with server:
            if not use_ssl:
                server.starttls()
            if user:
                server.login(user, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise NotificationSendError(f"SMTP 发送失败：{exc}") from exc
    return f"已投递 {len(recipients)} 个收件人"


def send_alert(channel: NotificationChannel, alert: AlertRecord) -> str:
    """按通道类型发送一条告警，返回响应摘要；失败抛 NotificationSendError。"""
    config = _decrypt_config(channel.channel_type, channel.config or {})
    title, text = render_alert_text(alert)

    if channel.channel_type == "email":
        return _send_email(config, title, text)

    url, headers, body = _build_request(channel, config, title, text)
    body = _apply_alert_to_body(body, alert)

    secret = str(config.get("secret") or "")
    if secret and channel.channel_type == "webhook":
        signature = hmac.new(secret.encode("utf-8"), json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
        headers = {**headers, "X-Signature": f"sha256={signature}"}
    return _post_json(url, body, headers)


def send_test(db: Session, channel: NotificationChannel) -> str:
    """给管理后台用的「发送测试」：构造一条演示告警文案发出去，失败原因记到通道上。"""
    now = datetime.utcnow()
    demo = AlertRecord(
        tenant_id=channel.tenant_id,
        alert_code=f"TEST-{now.strftime('%Y%m%d%H%M%S')}",
        alert_type="通道连通性测试",
        severity="high",
        status="pending",
        device_name="测试设备",
        device_code="TEST-001",
        location="管理后台",
        description="这是一条来自智慧消防管理系统的通道测试消息，收到即表示该通道配置可用。",
        first_seen_at=now,
        last_seen_at=now,
        repeat_count=1,
        created_at=now,
    )
    try:
        excerpt = send_alert(channel, demo)
    except NotificationSendError as exc:
        channel.last_error = str(exc)[:500]
        channel.last_error_at = now
        db.commit()
        raise
    channel.last_success_at = now
    channel.last_error = ""
    channel.updated_at = now
    db.commit()
    return excerpt


def deliver(db: Session, delivery_id: int) -> Dict[str, Any]:
    """执行一次投递（后台任务处理器调用）。

    - 已成功 → 幂等跳过
    - 通道不存在/停用、告警不存在 → 标记失败并返回 dead=True（不可恢复，不必重试）
    - 发送失败 → 记录原因后抛 NotificationSendError，由任务队列重试
    """
    row = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).first()
    if not row:
        return {"skipped": True, "reason": "投递记录不存在"}
    if row.status == "success":
        return {"skipped": True, "reason": "已发送成功（幂等跳过）"}

    channel = db.query(NotificationChannel).filter(NotificationChannel.id == row.channel_id).first()
    if not channel:
        return _mark_unrecoverable(db, row, None, "通道已删除")
    if not channel.enabled:
        return _mark_unrecoverable(db, row, channel, "通道已停用")

    alert = db.query(AlertRecord).filter(AlertRecord.alert_code == row.alert_code).first()
    if not alert:
        return _mark_unrecoverable(db, row, channel, "告警记录不存在")

    now = datetime.utcnow()
    try:
        excerpt = send_alert(channel, alert)
    except NotificationSendError as exc:
        row.status = "failed"
        row.attempts = (row.attempts or 0) + 1
        row.error = str(exc)[:500]
        row.updated_at = now
        channel.last_error = str(exc)[:500]
        channel.last_error_at = now
        db.commit()
        raise

    row.status = "success"
    row.attempts = (row.attempts or 0) + 1
    row.error = ""
    row.response_excerpt = (excerpt or "")[:500]
    row.updated_at = now
    channel.last_success_at = now
    channel.last_error = ""
    channel.updated_at = now
    db.commit()
    return {
        "delivered": True,
        "channel_id": channel.id,
        "channel_type": channel.channel_type,
        "alert_code": row.alert_code,
    }


def _mark_unrecoverable(
    db: Session,
    row: NotificationDelivery,
    channel: Optional[NotificationChannel],
    reason: str,
) -> Dict[str, Any]:
    row.status = "failed"
    row.attempts = (row.attempts or 0) + 1
    row.error = reason[:500]
    row.updated_at = datetime.utcnow()
    if channel is not None:
        channel.last_error = reason[:500]
        channel.last_error_at = datetime.utcnow()
    db.commit()
    logger.warning("告警通知投递 %s 放弃：%s", row.id, reason)
    return {"failed": True, "dead": True, "error": reason}
