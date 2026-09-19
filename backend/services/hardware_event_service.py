from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from database import SessionLocal, HardwareEvent
from services.agent_decision_service import make_decision_policy, get_risk_style


EVENT_TYPES = [
    {"type": "smoke_alarm", "name": "烟感报警", "default_level": "高风险", "description": "烟感设备上报烟雾异常。"},
    {"type": "temperature_alarm", "name": "温度异常", "default_level": "中风险", "description": "温度传感器上报异常升温。"},
    {"type": "electrical_alarm", "name": "电气火灾探测", "default_level": "高风险", "description": "电气火灾探测器上报过载、漏电或温升异常。"},
    {"type": "camera_snapshot", "name": "摄像头截图", "default_level": "中风险", "description": "摄像头识别到通道堵塞、烟雾或设施遮挡。"},
    {"type": "manual_report", "name": "人工上报", "default_level": "中风险", "description": "巡检人员或师生人工提交隐患。"},
    {"type": "device_offline", "name": "设备离线", "default_level": "低风险", "description": "消防设备或传感器离线。"},
]


def _get_session(db: Optional[Session] = None) -> Session:
    if db is not None:
        return db
    return SessionLocal()


def _row_to_dict(record: HardwareEvent) -> Dict[str, Any]:
    if not record:
        return {}
    analysis = record.analysis or {}
    return {
        "id": record.event_code,
        "event_type": record.event_type,
        "event_name": record.event_name,
        "location": record.location,
        "device_id": record.device_id,
        "device_name": record.device_name,
        "description": record.description,
        "risk_level": record.risk_level,
        "risk_score": record.risk_score,
        "risk_style": get_risk_style(record.risk_level, record.risk_score),
        "status": record.status,
        "analysis": analysis,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
        "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S") if record.updated_at else "",
    }


def _seed_if_empty(db: Session) -> None:
    if db.query(HardwareEvent).count() > 0:
        return
    seeds = [
        ("smoke_alarm", "烟感报警", "机房B区", "SMK-001", "机房烟感", "烟感设备上报烟雾浓度异常。", "高风险", 78),
        ("electrical_alarm", "电气火灾探测", "实验室A区", "ELE-002", "电气火灾探测器", "探测到插排过载和线路温升。", "高风险", 82),
        ("camera_snapshot", "摄像头截图", "教学楼三层", "CAM-003", "走廊摄像头", "画面显示灭火器被杂物遮挡。", "中风险", 48),
    ]
    for etype, name, location, device_id, device_name, desc, level, score in seeds:
        event_code = f"EVT-{str(uuid.uuid4())[:8].upper()}"
        analysis = analyze_event_payload({"risk_level": level, "risk_score": score, "description": desc}, save=False)
        db.add(HardwareEvent(
            event_code=event_code,
            event_type=etype,
            event_name=name,
            location=location,
            device_id=device_id,
            device_name=device_name,
            description=desc,
            risk_level=level,
            risk_score=score,
            status="待处理",
            analysis=analysis,
        ))
    db.commit()


def get_event_types() -> List[Dict[str, Any]]:
    return EVENT_TYPES


def _default_level(event_type: str) -> str:
    for item in EVENT_TYPES:
        if item["type"] == event_type:
            return item["default_level"]
    return "中风险"


def _event_name(event_type: str) -> str:
    for item in EVENT_TYPES:
        if item["type"] == event_type:
            return item["name"]
    return "硬件事件"


def _infer_hazards(event_type: str, description: str) -> List[str]:
    text = f"{event_type} {description}"
    mapping = [
        ("烟", "烟雾"),
        ("明火", "明火"),
        ("温度", "温度异常"),
        ("电气", "插座过载"),
        ("过载", "插座过载"),
        ("漏电", "电气火灾探测"),
        ("通道", "消防通道堵塞"),
        ("遮挡", "消防设施被遮挡"),
        ("灭火器", "灭火器被遮挡"),
        ("离线", "设备离线"),
    ]
    result = []
    for k, v in mapping:
        if k in text and v not in result:
            result.append(v)
    return result or [_event_name(event_type)]


def analyze_event_payload(payload: Dict[str, Any], save: bool = False) -> Dict[str, Any]:
    event_type = payload.get("event_type", "")
    description = payload.get("description", "")
    risk_level = payload.get("risk_level") or _default_level(event_type)
    risk_score = payload.get("risk_score")
    if risk_score is None:
        risk_score = 75 if "高" in risk_level else 45 if "中" in risk_level else 20
    hazards = _infer_hazards(event_type, description)
    policy = make_decision_policy(risk_level, risk_score, hazards)
    return {
        "hazards": hazards,
        "decision_policy": policy,
        "agent_summary": f"硬件事件被识别为{policy['risk_level']}，{policy['decision_summary']}",
        "suggested_action": "建议进入智能巡检或生成整改工单，并根据风险等级安排复查。",
    }


def list_hardware_events(status: str = "", event_type: str = "", limit: int = 200, db: Optional[Session] = None, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = _get_session(db)
    owns_session = db is None
    try:
        query = session.query(HardwareEvent)
        if tenant_id is not None:
            query = query.filter(HardwareEvent.tenant_id == tenant_id)
        if status:
            query = query.filter(HardwareEvent.status == status)
        if event_type:
            query = query.filter(HardwareEvent.event_type == event_type)
        records = query.order_by(HardwareEvent.created_at.desc()).limit(limit).all()
        return [_row_to_dict(r) for r in records]
    finally:
        if owns_session:
            session.close()


def create_hardware_event(payload: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    event_type = payload.get("event_type", "manual_report")
    event_code = payload.get("id") or f"EVT-{str(uuid.uuid4())[:8].upper()}"
    level = payload.get("risk_level") or _default_level(event_type)
    score = payload.get("risk_score")
    if score is None:
        score = 75 if "高" in level else 45 if "中" in level else 20
    analysis = analyze_event_payload({**payload, "risk_level": level, "risk_score": score})

    session = _get_session(db)
    owns_session = db is None
    try:
        existing = session.query(HardwareEvent).filter(HardwareEvent.event_code == event_code).first()
        if existing:
            existing.event_type = event_type
            existing.event_name = _event_name(event_type)
            existing.location = payload.get("location", "")
            existing.device_id = payload.get("device_id", "")
            existing.device_name = payload.get("device_name", "")
            existing.description = payload.get("description", "")
            existing.risk_level = level
            existing.risk_score = float(score or 0)
            existing.status = payload.get("status", "待处理")
            existing.analysis = analysis
            existing.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(existing)
            return _row_to_dict(existing)

        record = HardwareEvent(
            event_code=event_code,
            event_type=event_type,
            event_name=_event_name(event_type),
            location=payload.get("location", ""),
            device_id=payload.get("device_id", ""),
            device_name=payload.get("device_name", ""),
            description=payload.get("description", ""),
            risk_level=level,
            risk_score=float(score or 0),
            status=payload.get("status", "待处理"),
            analysis=analysis,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _row_to_dict(record)
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_hardware_event(event_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    session = _get_session(db)
    owns_session = db is None
    try:
        record = session.query(HardwareEvent).filter(HardwareEvent.event_code == event_id).first()
        return _row_to_dict(record)
    finally:
        if owns_session:
            session.close()


def update_hardware_event_status(event_id: str, status: str, db: Optional[Session] = None) -> Dict[str, Any]:
    session = _get_session(db)
    owns_session = db is None
    try:
        record = session.query(HardwareEvent).filter(HardwareEvent.event_code == event_id).first()
        if record:
            record.status = status
            record.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(record)
        return _row_to_dict(record)
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_hardware_dashboard(db: Optional[Session] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    events = list_hardware_events(limit=500, db=db, tenant_id=tenant_id)
    pending = len([e for e in events if e["status"] == "待处理"])
    processing = len([e for e in events if e["status"] == "处理中"])
    closed = len([e for e in events if e["status"] == "已闭环"])
    serious = len([e for e in events if "严重" in e["risk_level"]])
    high = len([e for e in events if "高" in e["risk_level"]])
    return {
        "total": len(events),
        "pending": pending,
        "processing": processing,
        "closed": closed,
        "serious": serious,
        "high": high,
        "summary": f"当前接入 {len(events)} 条硬件事件，其中待处理 {pending} 条，高风险及以上 {high + serious} 条。",
    }
