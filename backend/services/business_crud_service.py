"""
业务数据CRUD服务
设备、巡检记录、工单、告警的完整数据库操作
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import Device, DeviceTelemetry, InspectionRecord, FaultTicket, AlertRecord, Building
from services.alert_notify_service import enqueue_alert_notifications
from services.websocket_service import send_alert_notification


def _tenant_record(db: Session, model, record_id: int, tenant_id: int):
    return db.query(model).filter(model.id == record_id, model.tenant_id == tenant_id).first()


# ========== 设备管理 ==========

def list_devices(
    db: Session,
    tenant_id: int,
    keyword: str = "",
    device_type: str = "",
    status: str = "",
    building_id: int = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """设备列表（分页）"""
    query = db.query(Device).filter(Device.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (Device.device_code.like(like)) |
            (Device.device_name.like(like)) |
            (Device.location.like(like))
        )
    if device_type:
        query = query.filter(Device.device_type == device_type)
    if status:
        query = query.filter(Device.status == status)
    if building_id:
        query = query.filter(Device.building_id == building_id)

    total = query.count()
    devices = (
        query.order_by(Device.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    result = []
    for d in devices:
        telemetry = db.query(DeviceTelemetry).filter(
            DeviceTelemetry.device_id == d.id,
            DeviceTelemetry.tenant_id == tenant_id,
        ).order_by(DeviceTelemetry.created_at.desc()).first()
        result.append({
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "location": d.location,
            "status": d.status,
            "last_inspection_time": d.last_inspection_time.isoformat() if d.last_inspection_time else "",
            "telemetry": {
                "temperature": telemetry.temperature if telemetry else 0,
                "smoke": telemetry.smoke if telemetry else 0,
                "co": telemetry.co if telemetry else 0,
                "battery": telemetry.battery if telemetry else 0,
                "online": telemetry.online if telemetry else False,
            } if telemetry else None,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": result,
    }


def get_device(db: Session, tenant_id: int, device_id: int) -> Optional[Dict[str, Any]]:
    """获取设备详情"""
    device = _tenant_record(db, Device, device_id, tenant_id)
    if not device:
        return None

    telemetry = db.query(DeviceTelemetry).filter(
        DeviceTelemetry.device_id == device.id,
        DeviceTelemetry.tenant_id == tenant_id,
    ).order_by(DeviceTelemetry.created_at.desc()).first()

    telemetry_history = db.query(DeviceTelemetry).filter(
        DeviceTelemetry.device_id == device.id,
        DeviceTelemetry.tenant_id == tenant_id,
    ).order_by(DeviceTelemetry.created_at.desc()).limit(50).all()

    return {
        "id": device.id,
        "device_code": device.device_code,
        "device_name": device.device_name,
        "device_type": device.device_type,
        "location": device.location,
        "status": device.status,
        "last_inspection_time": device.last_inspection_time.isoformat() if device.last_inspection_time else "",
        "telemetry": {
            "temperature": telemetry.temperature if telemetry else 0,
            "smoke": telemetry.smoke if telemetry else 0,
            "co": telemetry.co if telemetry else 0,
            "battery": telemetry.battery if telemetry else 0,
            "online": telemetry.online if telemetry else False,
        } if telemetry else None,
        "telemetry_history": [
            {"time": t.created_at.isoformat(), "temperature": t.temperature, "smoke": t.smoke, "co": t.co}
            for t in telemetry_history
        ],
        "created_at": device.created_at.isoformat() if device.created_at else "",
    }


def create_device(
    db: Session,
    tenant_id: int,
    device_code: str,
    device_name: str,
    device_type: str = "灭火器",
    location: str = "",
) -> Dict[str, Any]:
    """创建设备"""
    device_code = (device_code or "").strip()
    device_name = (device_name or "").strip()

    if not device_code:
        return {"ok": False, "message": "设备编号不能为空"}
    if not device_name:
        return {"ok": False, "message": "设备名称不能为空"}

    existing = db.query(Device).filter(
        Device.device_code == device_code,
        Device.tenant_id == tenant_id,
    ).first()
    if existing:
        return {"ok": False, "message": f"设备编号 {device_code} 已存在"}

    device = Device(
        tenant_id=tenant_id,
        device_code=device_code,
        device_name=device_name,
        device_type=device_type,
        location=location,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"ok": True, "message": "设备创建成功", "device": _device_to_dict(device)}


def update_device(
    db: Session,
    tenant_id: int,
    device_id: int,
    device_name: str = None,
    device_type: str = None,
    location: str = None,
    status: str = None,
) -> Dict[str, Any]:
    """更新设备"""
    device = _tenant_record(db, Device, device_id, tenant_id)
    if not device:
        return {"ok": False, "message": "设备不存在"}

    if device_name is not None:
        device.device_name = device_name.strip()
    if device_type is not None:
        device.device_type = device_type
    if location is not None:
        device.location = location
    if status is not None:
        device.status = status

    db.commit()
    db.refresh(device)
    return {"ok": True, "message": "设备更新成功", "device": _device_to_dict(device)}


def delete_device(db: Session, tenant_id: int, device_id: int) -> Dict[str, Any]:
    """删除设备"""
    device = _tenant_record(db, Device, device_id, tenant_id)
    if not device:
        return {"ok": False, "message": "设备不存在"}

    db.delete(device)
    db.commit()
    return {"ok": True, "message": "设备删除成功"}


def add_telemetry(
    db: Session,
    tenant_id: int,
    device_id: int,
    temperature: float = None,
    smoke: float = None,
    co: float = None,
    battery: float = None,
    online: bool = None,
) -> Dict[str, Any]:
    """添加设备遥测数据"""
    device = _tenant_record(db, Device, device_id, tenant_id)
    if not device:
        return {"ok": False, "message": "设备不存在"}

    telemetry = DeviceTelemetry(tenant_id=tenant_id, device_id=device_id)
    if temperature is not None:
        telemetry.temperature = temperature
    if smoke is not None:
        telemetry.smoke = smoke
    if co is not None:
        telemetry.co = co
    if battery is not None:
        telemetry.battery = battery
    if online is not None:
        telemetry.online = online

    db.add(telemetry)
    db.commit()
    return {"ok": True, "message": "遥测数据添加成功"}


def get_device_telemetry(db: Session, tenant_id: int, device_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """获取设备遥测历史"""
    records = db.query(DeviceTelemetry).filter(
        DeviceTelemetry.device_id == device_id,
        DeviceTelemetry.tenant_id == tenant_id,
    ).order_by(DeviceTelemetry.created_at.desc()).limit(limit).all()
    return [
        {"time": r.created_at.isoformat(), "temperature": r.temperature, "smoke": r.smoke, "co": r.co, "battery": r.battery, "online": r.online}
        for r in records
    ]


def _device_to_dict(device: Device) -> Dict[str, Any]:
    return {
        "id": device.id,
        "device_code": device.device_code,
        "device_name": device.device_name,
        "device_type": device.device_type,
        "location": device.location,
        "status": device.status,
        "last_inspection_time": device.last_inspection_time.isoformat() if device.last_inspection_time else "",
        "created_at": device.created_at.isoformat() if device.created_at else "",
    }


# ========== 巡检记录 ==========

def list_inspection_records(
    db: Session,
    tenant_id: int,
    keyword: str = "",
    device_id: int = None,
    risk_level: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """巡检记录列表（分页）"""
    query = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (InspectionRecord.device_code.like(like)) |
            (InspectionRecord.device_name.like(like)) |
            (InspectionRecord.description.like(like))
        )
    if device_id:
        query = query.filter(InspectionRecord.device_id == device_id)
    if risk_level:
        query = query.filter(InspectionRecord.risk_level == risk_level)

    total = query.count()
    records = (
        query.order_by(InspectionRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_inspection_to_dict(r) for r in records],
    }


def get_inspection_record(db: Session, tenant_id: int, record_id: int) -> Optional[Dict[str, Any]]:
    """获取巡检记录详情"""
    record = _tenant_record(db, InspectionRecord, record_id, tenant_id)
    return _inspection_to_dict(record) if record else None


def create_inspection_record(
    db: Session,
    tenant_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """创建巡检记录"""
    device_id = data.get("device_id")
    if device_id and not _tenant_record(db, Device, device_id, tenant_id):
        return {"ok": False, "message": "设备不存在"}

    record = InspectionRecord(
        tenant_id=tenant_id,
        device_id=device_id,
        device_code=data.get("device_code", ""),
        device_name=data.get("device_name", ""),
        location=data.get("location", ""),
        description=data.get("description", ""),
        image_path=data.get("image_path", ""),
        hazards=str(data.get("hazards", [])) if isinstance(data.get("hazards"), list) else (data.get("hazards", "[]")),
        risk_score=data.get("risk_score", 0),
        risk_level=data.get("risk_level", "低风险"),
        suggestion=data.get("suggestion", ""),
        report=data.get("report", ""),
        agent_steps=str(data.get("agent_steps", [])) if isinstance(data.get("agent_steps"), list) else (data.get("agent_steps", "[]")),
        used_vision_api=data.get("used_vision_api", False),
        used_text_model_api=data.get("used_text_model_api", False),
        model_provider=data.get("model_provider", ""),
        model_name=data.get("model_name", ""),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    if device_id:
        device = _tenant_record(db, Device, device_id, tenant_id)
        if device:
            device.last_inspection_time = datetime.utcnow()
            if data.get("risk_level") in ["高风险", "中风险"]:
                device.status = "异常"
            else:
                device.status = "正常"
            db.commit()

    return {"ok": True, "message": "巡检记录创建成功", "record": _inspection_to_dict(record)}


def update_inspection_record(
    db: Session,
    tenant_id: int,
    record_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """更新巡检记录"""
    record = _tenant_record(db, InspectionRecord, record_id, tenant_id)
    if not record:
        return {"ok": False, "message": "巡检记录不存在"}

    if "hazards" in data:
        record.hazards = str(data["hazards"]) if isinstance(data["hazards"], list) else data["hazards"]
    if "risk_score" in data:
        record.risk_score = data["risk_score"]
    if "risk_level" in data:
        record.risk_level = data["risk_level"]
    if "suggestion" in data:
        record.suggestion = data["suggestion"]
    if "report" in data:
        record.report = data["report"]

    db.commit()
    db.refresh(record)
    return {"ok": True, "message": "巡检记录更新成功", "record": _inspection_to_dict(record)}


def _inspection_to_dict(record: InspectionRecord) -> Dict[str, Any]:
    try:
        hazards = eval(record.hazards)
        if not isinstance(hazards, list):
            hazards = []
    except Exception:
        hazards = []

    try:
        agent_steps = eval(record.agent_steps)
        if not isinstance(agent_steps, list):
            agent_steps = []
    except Exception:
        agent_steps = []

    return {
        "id": record.id,
        "device_id": record.device_id,
        "device_code": record.device_code,
        "device_name": record.device_name,
        "location": record.location,
        "description": record.description,
        "image_path": record.image_path,
        "hazards": hazards,
        "risk_score": record.risk_score,
        "risk_level": record.risk_level,
        "suggestion": record.suggestion,
        "report": record.report,
        "agent_steps": agent_steps,
        "used_vision_api": bool(record.used_vision_api),
        "used_text_model_api": bool(record.used_text_model_api),
        "model_provider": record.model_provider,
        "model_name": record.model_name,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }


# ========== 工单管理 ==========

def list_workorders(
    db: Session,
    tenant_id: int,
    keyword: str = "",
    status: str = "",
    risk_level: str = "",
    device_id: int = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """工单列表（分页）"""
    query = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (FaultTicket.title.like(like)) |
            (FaultTicket.description.like(like))
        )
    if status:
        query = query.filter(FaultTicket.status == status)
    if risk_level:
        query = query.filter(FaultTicket.risk_level == risk_level)
    if device_id:
        query = query.filter(FaultTicket.device_id == device_id)

    total = query.count()
    tickets = (
        query.order_by(FaultTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_ticket_to_dict(t) for t in tickets],
    }


def get_workorder(db: Session, tenant_id: int, ticket_id: int) -> Optional[Dict[str, Any]]:
    """获取工单详情"""
    ticket = _tenant_record(db, FaultTicket, ticket_id, tenant_id)
    return _ticket_to_dict(ticket) if ticket else None


def create_workorder(
    db: Session,
    tenant_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """创建工单"""
    record_id = data.get("record_id")
    device_id = data.get("device_id")
    if record_id and not _tenant_record(db, InspectionRecord, record_id, tenant_id):
        return {"ok": False, "message": "巡检记录不存在"}
    if device_id and not _tenant_record(db, Device, device_id, tenant_id):
        return {"ok": False, "message": "设备不存在"}

    ticket = FaultTicket(
        tenant_id=tenant_id,
        record_id=record_id,
        device_id=device_id,
        title=data.get("title", ""),
        description=data.get("description", ""),
        risk_level=data.get("risk_level", ""),
        status=data.get("status", "待受理"),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "message": "工单创建成功", "ticket": _ticket_to_dict(ticket)}


def update_workorder_status(
    db: Session,
    tenant_id: int,
    ticket_id: int,
    status: str,
    description: str = "",
) -> Dict[str, Any]:
    """更新工单状态"""
    ticket = _tenant_record(db, FaultTicket, ticket_id, tenant_id)
    if not ticket:
        return {"ok": False, "message": "工单不存在"}

    ticket.status = status
    if description:
        ticket.description = description
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "message": f"工单状态已更新为 {status}", "ticket": _ticket_to_dict(ticket)}


def delete_workorder(db: Session, tenant_id: int, ticket_id: int) -> Dict[str, Any]:
    """删除工单"""
    ticket = _tenant_record(db, FaultTicket, ticket_id, tenant_id)
    if not ticket:
        return {"ok": False, "message": "工单不存在"}

    db.delete(ticket)
    db.commit()
    return {"ok": True, "message": "工单删除成功"}


def _ticket_to_dict(ticket: FaultTicket) -> Dict[str, Any]:
    return {
        "id": ticket.id,
        "record_id": ticket.record_id,
        "device_id": ticket.device_id,
        "title": ticket.title,
        "description": ticket.description,
        "risk_level": ticket.risk_level,
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
    }


# ========== 告警管理 ==========

def list_alerts(
    db: Session,
    tenant_id: int,
    keyword: str = "",
    alert_type: str = "",
    severity: str = "",
    status: str = "",
    device_id: int = None,
    building_id: int = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """告警列表（分页）"""
    query = db.query(AlertRecord).filter(AlertRecord.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (AlertRecord.alert_code.like(like)) |
            (AlertRecord.device_name.like(like)) |
            (AlertRecord.location.like(like)) |
            (AlertRecord.description.like(like))
        )
    if alert_type:
        query = query.filter(AlertRecord.alert_type == alert_type)
    if severity:
        query = query.filter(AlertRecord.severity == severity)
    if status:
        query = query.filter(AlertRecord.status == status)
    if device_id:
        query = query.filter(AlertRecord.device_id == device_id)
    if building_id:
        query = query.filter(AlertRecord.building_id == building_id)

    total = query.count()
    alerts = (
        query.order_by(AlertRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_alert_to_dict(a) for a in alerts],
    }


def get_alert(db: Session, tenant_id: int, alert_id: int) -> Optional[Dict[str, Any]]:
    """获取告警详情"""
    alert = _tenant_record(db, AlertRecord, alert_id, tenant_id)
    return _alert_to_dict(alert) if alert else None


def create_alert(
    db: Session,
    tenant_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """创建告警记录"""
    device_id = data.get("device_id")
    building_id = data.get("building_id")
    workorder_id = data.get("workorder_id")
    if device_id and not _tenant_record(db, Device, device_id, tenant_id):
        return {"ok": False, "message": "设备不存在"}
    if building_id and not _tenant_record(db, Building, building_id, tenant_id):
        return {"ok": False, "message": "建筑不存在"}
    if workorder_id and not _tenant_record(db, FaultTicket, workorder_id, tenant_id):
        return {"ok": False, "message": "工单不存在"}

    alert_code = data.get("alert_code") or f"ALERT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    alert = AlertRecord(
        tenant_id=tenant_id,
        alert_code=alert_code,
        device_id=device_id,
        device_code=data.get("device_code", ""),
        device_name=data.get("device_name", ""),
        building_id=building_id,
        building_name=data.get("building_name", ""),
        location=data.get("location", ""),
        alert_type=data.get("alert_type", ""),
        alert_value=data.get("alert_value", 0.0),
        alert_unit=data.get("alert_unit", ""),
        severity=data.get("severity", "medium"),
        status=data.get("status", "pending"),
        description=data.get("description", ""),
        agent_analysis=data.get("agent_analysis", ""),
        workorder_id=workorder_id,
        device_info=data.get("device_info", {}),
        telemetry_history=data.get("telemetry_history", []),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    payload = _alert_to_dict(alert)
    # 与设备接入链路（alert_lifecycle_service.ingest_alert）一致：新告警立即推给该租户
    send_alert_notification(tenant_id, payload)
    # 外部通知通道同样按「级别 + 类型」匹配后投递
    enqueue_alert_notifications(db, alert, reason="created")
    return {"ok": True, "message": "告警记录创建成功", "alert": payload}


def update_alert(
    db: Session,
    tenant_id: int,
    alert_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """更新告警记录"""
    alert = _tenant_record(db, AlertRecord, alert_id, tenant_id)
    if not alert:
        return {"ok": False, "message": "告警记录不存在"}

    if "workorder_id" in data and data["workorder_id"] and not _tenant_record(db, FaultTicket, data["workorder_id"], tenant_id):
        return {"ok": False, "message": "工单不存在"}

    if "status" in data:
        alert.status = data["status"]
    if "agent_analysis" in data:
        alert.agent_analysis = data["agent_analysis"]
    if "workorder_id" in data:
        alert.workorder_id = data["workorder_id"]
    if "handled_by" in data:
        alert.handled_by = data["handled_by"]
    if "handled_at" in data:
        alert.handled_at = data["handled_at"]
    if "handle_result" in data:
        alert.handle_result = data["handle_result"]

    alert.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return {"ok": True, "message": "告警记录更新成功", "alert": _alert_to_dict(alert)}


def get_alert_statistics(db: Session, tenant_id: int) -> Dict[str, Any]:
    """告警统计"""
    base_query = db.query(AlertRecord).filter(AlertRecord.tenant_id == tenant_id)
    total = base_query.count()
    pending = base_query.filter(AlertRecord.status == "pending").count()
    handled = base_query.filter(AlertRecord.status == "handled").count()
    resolved = base_query.filter(AlertRecord.status == "resolved").count()

    critical = base_query.filter(AlertRecord.severity == "critical").count()
    high = base_query.filter(AlertRecord.severity == "high").count()
    medium = base_query.filter(AlertRecord.severity == "medium").count()
    low = base_query.filter(AlertRecord.severity == "low").count()

    return {
        "total": total,
        "pending": pending,
        "handled": handled,
        "resolved": resolved,
        "severity_distribution": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
        },
    }


def _alert_to_dict(alert: AlertRecord) -> Dict[str, Any]:
    return {
        "id": alert.id,
        "alert_code": alert.alert_code,
        "device_id": alert.device_id,
        "device_code": alert.device_code,
        "device_name": alert.device_name,
        "building_id": alert.building_id,
        "building_name": alert.building_name,
        "location": alert.location,
        "alert_type": alert.alert_type,
        "alert_value": alert.alert_value,
        "alert_unit": alert.alert_unit,
        "severity": alert.severity,
        "status": alert.status,
        "description": alert.description,
        "agent_analysis": alert.agent_analysis,
        "workorder_id": alert.workorder_id,
        "handled_by": alert.handled_by,
        "handled_at": alert.handled_at.isoformat() if alert.handled_at else "",
        "handle_result": alert.handle_result,
        "device_info": alert.device_info or {},
        "telemetry_history": alert.telemetry_history or [],
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else "",
    }


# ========== 建筑管理 ==========

def list_buildings(
    db: Session,
    tenant_id: int,
    keyword: str = "",
    building_type: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """建筑列表（分页）"""
    query = db.query(Building).filter(Building.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (Building.building_code.like(like)) |
            (Building.building_name.like(like)) |
            (Building.address.like(like))
        )
    if building_type:
        query = query.filter(Building.building_type == building_type)

    total = query.count()
    buildings = (
        query.order_by(Building.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_building_to_dict(b) for b in buildings],
    }


def get_building(db: Session, tenant_id: int, building_id: int) -> Optional[Dict[str, Any]]:
    """获取建筑详情"""
    building = _tenant_record(db, Building, building_id, tenant_id)
    return _building_to_dict(building) if building else None


def update_building_risk(
    db: Session,
    tenant_id: int,
    building_id: int,
    risk_score: int,
    risk_level: str,
) -> Dict[str, Any]:
    """更新建筑风险评分"""
    building = _tenant_record(db, Building, building_id, tenant_id)
    if not building:
        return {"ok": False, "message": "建筑不存在"}

    building.risk_score = risk_score
    building.risk_level = risk_level
    building.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(building)
    return {"ok": True, "message": "风险评分已更新", "building": _building_to_dict(building)}


def _building_to_dict(building: Building) -> Dict[str, Any]:
    return {
        "id": building.id,
        "building_code": building.building_code,
        "building_name": building.building_name,
        "building_type": building.building_type,
        "address": building.address,
        "floors": building.floors,
        "area": building.area,
        "risk_score": building.risk_score,
        "risk_level": building.risk_level,
        "manager_id": building.manager_id,
        "description": building.description,
        "status": building.status,
        "created_at": building.created_at.isoformat() if building.created_at else "",
        "updated_at": building.updated_at.isoformat() if building.updated_at else "",
    }
