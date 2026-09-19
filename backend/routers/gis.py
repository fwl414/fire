from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from database import get_db, Building, Device, AlertRecord, FaultTicket, InspectionRecord, DeviceTelemetry, User
from services.auth_service import get_current_user, get_current_tenant_id

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/api/gis/buildings")
def gis_buildings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()

    building_ids = [b.id for b in buildings]

    device_counts = {}
    devices = db.query(Device).filter(Device.building_id.in_(building_ids), Device.tenant_id == tenant_id).all()
    for d in devices:
        if d.building_id:
            device_counts[d.building_id] = device_counts.get(d.building_id, 0) + 1

    alert_counts = {}
    pending_alerts = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.building_id.in_(building_ids),
        AlertRecord.status != "handled"
    ).all()
    for a in pending_alerts:
        if a.building_id:
            alert_counts[a.building_id] = alert_counts.get(a.building_id, 0) + 1

    workorder_counts = {}
    device_building_map = {d.id: d.building_id for d in devices if d.building_id}
    pending_workorders = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id, FaultTicket.status != "已完成").all()
    for w in pending_workorders:
        bid = device_building_map.get(w.device_id)
        if bid:
            workorder_counts[bid] = workorder_counts.get(bid, 0) + 1

    result = []
    for b in buildings:
        result.append({
            "id": b.id,
            "building_code": b.building_code,
            "building_name": b.building_name,
            "building_type": b.building_type,
            "address": b.address,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "floors": b.floors,
            "area": b.area,
            "risk_score": b.risk_score,
            "risk_level": b.risk_level,
            "status": b.status,
            "device_count": device_counts.get(b.id, 0),
            "alert_count": alert_counts.get(b.id, 0),
            "workorder_count": workorder_counts.get(b.id, 0),
        })

    return {"buildings": result}


@router.get("/api/gis/devices")
def gis_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
    building_ids = list(set([d.building_id for d in devices if d.building_id]))
    buildings = db.query(Building).filter(Building.id.in_(building_ids), Building.tenant_id == tenant_id).all()
    building_map = {b.id: b for b in buildings}

    result = []
    for d in devices:
        item = {
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "status": d.status,
            "building_id": d.building_id,
            "floor_id": d.floor_id,
            "location": d.location,
            "floor_x": d.floor_x,
            "floor_y": d.floor_y,
        }
        if d.building_id and d.building_id in building_map:
            b = building_map[d.building_id]
            item["latitude"] = b.latitude
            item["longitude"] = b.longitude
        else:
            item["latitude"] = 0.0
            item["longitude"] = 0.0
        result.append(item)

    return {"devices": result}


@router.get("/api/gis/heatmap")
def gis_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()
    building_map = {b.id: b for b in buildings}

    devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
    device_building_map = {d.id: d.building_id for d in devices if d.building_id}

    hazard_counts: Dict[int, int] = {}

    high_risk_alerts = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.severity == "high",
        AlertRecord.status != "handled"
    ).all()
    for a in high_risk_alerts:
        bid = a.building_id or device_building_map.get(a.device_id)
        if bid:
            hazard_counts[bid] = hazard_counts.get(bid, 0) + 1

    pending_workorders = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id, FaultTicket.status != "已完成").all()
    for w in pending_workorders:
        bid = device_building_map.get(w.device_id)
        if bid:
            hazard_counts[bid] = hazard_counts.get(bid, 0) + 1

    high_risk_inspections = db.query(InspectionRecord).filter(
        InspectionRecord.tenant_id == tenant_id,
        InspectionRecord.risk_level == "高风险"
    ).all()
    for r in high_risk_inspections:
        bid = device_building_map.get(r.device_id)
        if bid:
            hazard_counts[bid] = hazard_counts.get(bid, 0) + 1

    result = []
    for bid, b in building_map.items():
        count = hazard_counts.get(bid, 0)
        if count > 0 or b.risk_score > 0:
            result.append({
                "building_id": b.id,
                "building_name": b.building_name,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "risk_score": b.risk_score,
                "count": count,
            })

    return {"heatmap": result}


@router.get("/api/gis/dashboard")
def gis_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building_count = db.query(Building).filter(Building.tenant_id == tenant_id).count()
    device_count = db.query(Device).filter(Device.tenant_id == tenant_id).count()

    latest_telemetry_subquery = db.query(
        DeviceTelemetry.device_id,
        DeviceTelemetry.online,
    ).filter(DeviceTelemetry.tenant_id == tenant_id).distinct(DeviceTelemetry.device_id).order_by(
        DeviceTelemetry.device_id, DeviceTelemetry.created_at.desc()
    ).subquery()

    device_online_count = db.query(latest_telemetry_subquery).filter(
        latest_telemetry_subquery.c.online == True
    ).count()
    device_offline_count = device_count - device_online_count

    alert_total = db.query(AlertRecord).filter(AlertRecord.tenant_id == tenant_id).count()
    alert_pending = db.query(AlertRecord).filter(AlertRecord.tenant_id == tenant_id, AlertRecord.status == "pending").count()

    workorder_total = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id).count()
    # 未闭环工单数（工单状态机为 待受理 / 处理中 / 待复查 / 已完成 / 已关闭）
    workorder_pending = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == tenant_id,
        FaultTicket.status.notin_(("已完成", "已关闭", "已闭环")),
    ).count()
    workorder_done = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id, FaultTicket.status == "已完成").count()

    inspection_total = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id).count()

    high_risk_building_count = db.query(Building).filter(Building.tenant_id == tenant_id, Building.risk_level == "高风险").count()

    risk_distribution = {
        "高风险": db.query(Building).filter(Building.tenant_id == tenant_id, Building.risk_level == "高风险").count(),
        "中风险": db.query(Building).filter(Building.tenant_id == tenant_id, Building.risk_level == "中风险").count(),
        "低风险": db.query(Building).filter(Building.tenant_id == tenant_id, Building.risk_level == "低风险").count(),
    }

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    recent_alerts_query = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.created_at >= seven_days_ago
    ).all()
    recent_alerts_map = {}
    for i in range(7):
        day = (datetime.utcnow() - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        recent_alerts_map[day] = 0
    for a in recent_alerts_query:
        if a.created_at:
            day = a.created_at.strftime("%Y-%m-%d")
            if day in recent_alerts_map:
                recent_alerts_map[day] += 1
    recent_alerts = [{"date": k, "count": v} for k, v in recent_alerts_map.items()]

    recent_inspections_query = db.query(InspectionRecord).filter(
        InspectionRecord.tenant_id == tenant_id,
        InspectionRecord.created_at >= seven_days_ago
    ).all()
    recent_inspections_map = {}
    for i in range(7):
        day = (datetime.utcnow() - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        recent_inspections_map[day] = 0
    for r in recent_inspections_query:
        if r.created_at:
            day = r.created_at.strftime("%Y-%m-%d")
            if day in recent_inspections_map:
                recent_inspections_map[day] += 1
    recent_inspections = [{"date": k, "count": v} for k, v in recent_inspections_map.items()]

    return {
        "building_count": building_count,
        "device_count": device_count,
        "device_online_count": device_online_count,
        "device_offline_count": device_offline_count,
        "alert_total": alert_total,
        "alert_pending": alert_pending,
        "workorder_total": workorder_total,
        "workorder_pending": workorder_pending,
        "workorder_done": workorder_done,
        "inspection_total": inspection_total,
        "high_risk_building_count": high_risk_building_count,
        "risk_distribution": risk_distribution,
        "recent_alerts": recent_alerts,
        "recent_inspections": recent_inspections,
    }
