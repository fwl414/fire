"""设备数据接入服务

HTTP 与 MQTT 两条接入通道共用同一套落库与告警逻辑：
    上报 → 写入遥测 → 阈值判定 → 生成告警（自动去重/升级）→ 生成整改工单 → 闭环
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database import Building, Device, DeviceTelemetry
from services.alert_lifecycle_service import ingest_alert, persist_alert_workorder
from services.metrics_service import incr
from services.telemetry_analyzer import TELEMETRY_RULES, analyze_telemetry_single

SOURCE_LABELS = {
    "http": "设备HTTP直连",
    "mqtt": "设备MQTT接入",
}

# 上报指标别名 -> 阈值规则键
METRIC_ALIASES = {
    "smoke": "smoke",
    "temperature": "temperature",
    "temp": "temperature",
    "current": "current",
    "voltage": "voltage",
    "pressure": "pressure",
    "remaining_current": "remaining_current",
    "leakage": "remaining_current",
    "battery": "battery_level",
    "battery_level": "battery_level",
}

# 阈值规则键 -> 告警类型
ALERT_TYPE_BY_METRIC = {
    "smoke": "smoke_high",
    "temperature": "temperature_high",
    "current": "current_high",
    "voltage": "voltage_high",
    "remaining_current": "remaining_current",
    "battery_level": "battery_low",
}

# (指标, 状态) -> 告警严重度，未命中时按 alarm=high / warning=medium
SEVERITY_MATRIX = {
    ("smoke", "alarm"): "critical",
    ("smoke", "warning"): "high",
    ("battery_level", "alarm"): "medium",
    ("battery_level", "warning"): "low",
    ("temperature", "alarm"): "high",
    ("remaining_current", "alarm"): "high",
}

RISK_LEVEL_BY_SEVERITY = {
    "critical": "严重风险",
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
}

# 遥测列名映射：DeviceTelemetry 已为以下指标落列。
# 2026-09-17 起补齐 current/voltage/pressure/remaining_current 4 列——
# 此前硬件已在上报，但因列不存在而被丢进告警上下文不入时序表。
TELEMETRY_COLUMNS = {
    "temperature": "temperature",
    "smoke": "smoke",
    "co": "co",
    "battery_level": "battery",
    "current": "current",
    "voltage": "voltage",
    "pressure": "pressure",
    "remaining_current": "remaining_current",
}

DEADLINE_HOURS = {"alarm": 2, "warning": 24}


def _building_name(db: Session, device: Device) -> str:
    if not device.building_id:
        return ""
    building = db.query(Building).filter(Building.id == device.building_id).first()
    return building.building_name if building else ""


def _resolve_metric(raw_key: str) -> Optional[str]:
    return METRIC_ALIASES.get(str(raw_key or "").strip().lower())


def _severity_for(metric: str, status: str) -> str:
    if (metric, status) in SEVERITY_MATRIX:
        return SEVERITY_MATRIX[(metric, status)]
    return "high" if status == "alarm" else "medium"


def _alert_type_for(metric: str, value: float, rule: Dict[str, Any]) -> str:
    if metric == "pressure":
        alarm_low = rule.get("alarm_threshold_low")
        warning_low = rule.get("warning_threshold_low")
        normal_min = rule["normal_range"][0]
        if (alarm_low is not None and value <= alarm_low) or value < normal_min:
            return "pressure_low"
        if warning_low is not None and value <= warning_low:
            return "pressure_low"
        return "pressure_high"
    return ALERT_TYPE_BY_METRIC.get(metric, f"{metric}_abnormal")


def _workorder_payload(
    device: Device,
    rule: Dict[str, Any],
    analysis: Dict[str, Any],
    severity: str,
    status: str,
    building_name: str,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    location = device.location or building_name or device.device_name
    deadline = now + timedelta(hours=DEADLINE_HOURS.get(status, 24))
    return {
        "title": f"{location}-{rule.get('description', '设备指标')}异常处置工单",
        "recommended_action": analysis.get("recommendation") or analysis.get("analysis", ""),
        "risk_level": RISK_LEVEL_BY_SEVERITY.get(severity, "中风险"),
        "priority": "紧急" if severity == "critical" else ("高" if severity == "high" else "中"),
        "deadline": deadline.strftime("%Y-%m-%d %H:%M"),
        "responsible_role": "设备维护人员 / 区域安全责任人",
    }


def _raise_alert(
    db: Session,
    device: Device,
    *,
    alert_type: str,
    severity: str,
    description: str,
    alert_value: Optional[float] = None,
    alert_unit: str = "",
    analysis: Optional[Dict[str, Any]] = None,
    source: str = "http",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成告警（带自动去重/升级）并落库整改工单。"""
    building_name = _building_name(db, device)
    analysis = analysis or {}
    device_info = {
        "code": device.device_code,
        "name": device.device_name,
        "type": device.device_type,
        "location": device.location or "",
        "source": SOURCE_LABELS.get(source, source),
        **(extra or {}),
    }
    telemetry_history = [{
        "metric": alert_type,
        "value": alert_value,
        "unit": alert_unit,
        "at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
    }]

    outcome = ingest_alert(
        db,
        tenant_id=device.tenant_id,
        alert_type=alert_type,
        severity=severity,
        description=description,
        alert_value=alert_value,
        alert_unit=alert_unit,
        device_id=device.id,
        device_code=device.device_code,
        device_name=device.device_name,
        building_id=device.building_id,
        building_name=building_name,
        location=device.location or building_name,
        agent_analysis=json.dumps(analysis, ensure_ascii=False),
        device_info=device_info,
        telemetry_history=telemetry_history,
    )

    rule = {"description": description, **analysis}
    ticket = persist_alert_workorder(
        db,
        tenant_id=device.tenant_id,
        alert=outcome["alert"],
        workorder=_workorder_payload(
            device,
            rule,
            analysis,
            severity,
            "alarm" if severity in ("critical", "high") else "warning",
            building_name,
        ),
        reporter_name=SOURCE_LABELS.get(source, source),
    )

    return {
        "alert_id": outcome["alert"].id,
        "alert_code": outcome["alert"].alert_code,
        "severity": outcome["alert"].severity,
        "dedup_action": outcome["action"],
        "repeat_count": outcome["repeat_count"],
        "escalated": outcome["escalated"],
        "workorder_id": ticket.id if ticket else None,
    }


def ingest_telemetry(
    db: Session,
    device: Device,
    data: Dict[str, Any],
    source: str = "http",
) -> Dict[str, Any]:
    """处理设备遥测：写入遥测表，并对超阈值指标生成告警与工单。"""
    values: Dict[str, float] = {}
    for raw_key, raw_value in (data or {}).items():
        metric = _resolve_metric(raw_key)
        if not metric:
            continue
        try:
            values[metric] = float(raw_value)
        except (TypeError, ValueError):
            continue

    if not values:
        raise ValueError("遥测数据为空或指标无法识别")

    row = DeviceTelemetry(
        tenant_id=device.tenant_id,
        device_id=device.id,
        online=bool(data.get("online", True)),
        created_at=datetime.utcnow(),
    )
    for metric, column in TELEMETRY_COLUMNS.items():
        if metric in values:
            setattr(row, column, values[metric])
    db.add(row)
    device.last_seen_at = datetime.utcnow()
    db.commit()
    incr("device_ingest_telemetry")

    alerts = []
    for metric, value in values.items():
        rule = TELEMETRY_RULES.get(metric)
        if not rule:
            continue
        analysis = analyze_telemetry_single(metric, value)
        status = analysis.get("status")
        if status not in ("warning", "alarm"):
            continue
        severity = _severity_for(metric, status)
        alerts.append(
            _raise_alert(
                db,
                device,
                alert_type=_alert_type_for(metric, value, rule),
                severity=severity,
                description=f"{rule['description']}{'严重超标' if status == 'alarm' else '偏高'}（{value}{rule['unit']}）",
                alert_value=value,
                alert_unit=rule["unit"],
                analysis=analysis,
                source=source,
                extra={"metric_status": status},
            )
        )

    if data.get("online") is False:
        alerts.append(
            _raise_alert(
                db,
                device,
                alert_type="device_offline",
                severity="high",
                description=f"{device.device_name} 上报离线状态",
                analysis={"analysis": "设备上报离线，可能断电或通信中断", "recommendation": "检查供电与通信链路"},
                source=source,
            )
        )

    return {
        "received": True,
        "device_code": device.device_code,
        "metrics": values,
        "telemetry_id": row.id,
        "alert_count": len(alerts),
        "alerts": alerts,
    }


def ingest_event(
    db: Session,
    device: Device,
    data: Dict[str, Any],
    source: str = "http",
) -> Dict[str, Any]:
    """处理设备事件上报（如手动报警、硬件故障）。"""
    DATA_TO_ALERT = {
        "fire": "smoke_high",
        "smoke": "smoke_high",
        "temperature": "temperature_high",
        "fault": "device_fault",
        "offline": "device_offline",
        "manual": "manual_alarm",
    }
    SEVERITIES = ("low", "medium", "high", "critical")

    raw_type = str(data.get("event_type") or data.get("type") or "manual").strip().lower()
    alert_type = DATA_TO_ALERT.get(raw_type, f"device_event_{raw_type}" if raw_type else "device_event")

    requested = str(data.get("severity") or data.get("level") or "").strip().lower()
    severity = requested if requested in SEVERITIES else ("critical" if raw_type == "fire" else "high")

    value = data.get("value")
    try:
        alert_value = float(value) if value is not None else None
    except (TypeError, ValueError):
        alert_value = None

    description = str(data.get("description") or data.get("message") or f"{device.device_name} 上报事件：{raw_type}")

    alert = _raise_alert(
        db,
        device,
        alert_type=alert_type,
        severity=severity,
        description=description,
        alert_value=alert_value,
        alert_unit=str(data.get("unit") or ""),
        analysis={
            "analysis": description,
            "recommendation": str(data.get("recommendation") or "现场核实并按预案处置"),
        },
        source=source,
        extra={"reported_event_type": raw_type},
    )
    incr("device_ingest_event")
    return {"received": True, "device_code": device.device_code, "event_type": raw_type, **alert}

def ingest_heartbeat(
    db: Session,
    device: Device,
    data: Optional[Dict[str, Any]] = None,
    source: str = "http",
) -> Dict[str, Any]:
    """处理设备心跳：刷新在线时间与在线状态。"""
    data = data or {}
    now = datetime.utcnow()
    device.last_seen_at = now
    if device.status in ("离线", "offline"):
        device.status = "正常"
    db.commit()
    incr("device_ingest_heartbeat")

    return {
        "received": True,
        "device_code": device.device_code,
        "status": device.status,
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "source": SOURCE_LABELS.get(source, source),
        "reported": data,
    }


INGEST_HANDLERS = {
    "telemetry": ingest_telemetry,
    "event": ingest_event,
    "heartbeat": ingest_heartbeat,
}


def dispatch(db: Session, device: Device, kind: str, data: Dict[str, Any], source: str = "mqtt") -> Dict[str, Any]:
    """按消息类型分发到对应处理函数。"""
    handler = INGEST_HANDLERS.get(kind)
    if not handler:
        raise ValueError(f"不支持的接入类型：{kind}")
    return handler(db, device, data, source=source)
