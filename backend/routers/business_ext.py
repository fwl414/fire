"""
业务扩展模块API
值班管理、重点单位、应急指挥
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional

from database import (
    get_db,
    Building, DutyShift, DutyRecord, DutyHandover,
    KeyUnit, UnitInspection,
    EmergencyPlan, EmergencySupply, EmergencyTeam, EvacuationRoute,
    User,
)
from services.auth_service import get_current_user, get_current_tenant_id, require_permission
from services import duty_schedule_service

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["业务扩展"])


# ============= 值班管理 =============

@router.get("/api/duty/stats")
def api_duty_stats(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    today = date.today()
    first_of_month = today.replace(day=1)

    on_duty = db.query(DutyShift).filter(
        DutyShift.tenant_id == tenant_id,
        DutyShift.duty_date == today,
        DutyShift.status == "active"
    ).count()

    monthly_records = db.query(DutyRecord).filter(
        DutyRecord.tenant_id == tenant_id,
        DutyRecord.record_date >= first_of_month
    ).count()

    alarm_count = db.query(DutyRecord).filter(
        DutyRecord.tenant_id == tenant_id,
        DutyRecord.record_date >= first_of_month
    ).all()
    total_alarm = sum(r.alarm_count or 0 for r in alarm_count)
    total_handled = sum(r.handled_count or 0 for r in alarm_count)

    return {
        "onDuty": on_duty,
        "monthlyRecords": monthly_records,
        "alarmCount": total_alarm,
        "handledAlarms": total_handled,
    }


@router.get("/api/duty/shifts")
def api_duty_shifts(
    date_param: Optional[str] = Query(None, alias="date"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(DutyShift).filter(DutyShift.tenant_id == tenant_id)
    if date_param:
        try:
            d = datetime.strptime(date_param, "%Y-%m-%d").date()
            query = query.filter(DutyShift.duty_date == d)
        except ValueError:
            pass
    # 周视图按区间取数：格式不对就忽略该边界，不因为一个参数让整页报错
    start = duty_schedule_service.parse_date(start_date)
    if start:
        query = query.filter(DutyShift.duty_date >= start)
    end = duty_schedule_service.parse_date(end_date)
    if end:
        query = query.filter(DutyShift.duty_date <= end)
    # 开始时间相同时也要有稳定顺序：页面取第一条当「当前班次」，顺序不定会取到旧数据
    shifts = query.order_by(
        DutyShift.duty_date.desc(), DutyShift.start_time.asc(), DutyShift.id.asc()
    ).all()
    return [duty_schedule_service.shift_to_dict(s) for s in shifts]


@router.get("/api/duty/records")
def api_duty_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(DutyRecord).filter(DutyRecord.tenant_id == tenant_id)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(or_(
            DutyRecord.duty_person.ilike(kw),
            DutyRecord.shift_name.ilike(kw),
        ))
    # 日期区间是筛选项：格式不对就忽略该条件，不因为一个筛选项让整页报错
    start = duty_schedule_service.parse_date(start_date)
    if start:
        query = query.filter(DutyRecord.record_date >= start)
    end = duty_schedule_service.parse_date(end_date)
    if end:
        query = query.filter(DutyRecord.record_date <= end)
    total = query.count()
    records = query.order_by(DutyRecord.record_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "list": [duty_schedule_service.record_to_dict(r) for r in records],
    }


@router.get("/api/duty/handovers")
def api_duty_handovers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    total = db.query(DutyHandover).filter(DutyHandover.tenant_id == tenant_id).count()
    records = db.query(DutyHandover).filter(
        DutyHandover.tenant_id == tenant_id
    ).order_by(DutyHandover.handover_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 交接班表只存 shift_id：一次性把本页涉及的班次名查出来，避免逐行查库
    shift_ids = [h.shift_id for h in records if h.shift_id]
    shift_names = {}
    if shift_ids:
        shift_names = {
            s.id: s.shift_name
            for s in db.query(DutyShift).filter(
                DutyShift.tenant_id == tenant_id, DutyShift.id.in_(shift_ids)
            ).all()
        }

    return {
        "total": total,
        "list": [
            duty_schedule_service.handover_to_dict(h, shift_names.get(h.shift_id, ""))
            for h in records
        ],
    }


@router.post("/api/duty/shifts")
def api_duty_shift_create(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    """新建排班（同一天同名班次、同一天同一人重复排班都会被拒绝）。"""
    result = duty_schedule_service.create_shift(db, tenant_id, data)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/duty/shifts/{shift_id}")
def api_duty_shift_update(
    shift_id: int,
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    result = duty_schedule_service.update_shift(db, tenant_id, shift_id, data)
    if not result.get("ok"):
        return JSONResponse(status_code=404 if result.get("not_found") else 400, content=result)
    return result


@router.delete("/api/duty/shifts/{shift_id}")
def api_duty_shift_delete(
    shift_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    result = duty_schedule_service.delete_shift(db, tenant_id, shift_id)
    if not result.get("ok"):
        return JSONResponse(status_code=404 if result.get("not_found") else 400, content=result)
    return result


@router.post("/api/duty/records")
def api_duty_record_create(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    """保存值班记录。"""
    result = duty_schedule_service.create_record(db, tenant_id, data)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/duty/records/{record_id}")
def api_duty_record_update(
    record_id: int,
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    result = duty_schedule_service.update_record(db, tenant_id, record_id, data)
    if not result.get("ok"):
        return JSONResponse(status_code=404 if result.get("not_found") else 400, content=result)
    return result


@router.delete("/api/duty/records/{record_id}")
def api_duty_record_delete(
    record_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    result = duty_schedule_service.delete_record(db, tenant_id, record_id)
    if not result.get("ok"):
        return JSONResponse(status_code=404 if result.get("not_found") else 400, content=result)
    return result


@router.post("/api/duty/handovers")
def api_duty_handover_create(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    """记录一次交接班。"""
    result = duty_schedule_service.create_handover(db, tenant_id, data)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/api/duty/handovers/{handover_id}")
def api_duty_handover_delete(
    handover_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("duty:manage")),
):
    result = duty_schedule_service.delete_handover(db, tenant_id, handover_id)
    if not result.get("ok"):
        return JSONResponse(status_code=404 if result.get("not_found") else 400, content=result)
    return result


# ============= 重点单位 =============

@router.get("/api/key-units/stats")
def api_key_unit_stats(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    today = date.today()
    first_of_month = today.replace(day=1)

    total = db.query(KeyUnit).filter(KeyUnit.tenant_id == tenant_id).count()
    high_risk = db.query(KeyUnit).filter(KeyUnit.tenant_id == tenant_id, KeyUnit.risk_level == "high").count()
    active = db.query(KeyUnit).filter(KeyUnit.tenant_id == tenant_id, KeyUnit.status == "active").count()

    checked_this_month = db.query(UnitInspection).filter(
        UnitInspection.tenant_id == tenant_id,
        UnitInspection.inspection_date >= first_of_month
    ).count()

    qualified = db.query(UnitInspection).filter(
        UnitInspection.tenant_id == tenant_id,
        UnitInspection.inspection_date >= first_of_month,
        UnitInspection.result == "qualified"
    ).count()
    qualified_rate = round((qualified / checked_this_month * 100), 1) if checked_this_month > 0 else 0

    return {
        "total": total,
        "highRisk": high_risk,
        "active": active,
        "checkedThisMonth": checked_this_month,
        "qualifiedRate": qualified_rate,
    }


@router.get("/api/key-units")
def api_key_unit_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    industry: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(KeyUnit).filter(KeyUnit.tenant_id == tenant_id)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(or_(
            KeyUnit.unit_name.ilike(kw),
            KeyUnit.unit_code.ilike(kw),
        ))
    if level:
        query = query.filter(KeyUnit.level == level)
    if industry:
        query = query.filter(KeyUnit.industry == industry)
    if risk_level:
        query = query.filter(KeyUnit.risk_level == risk_level)

    total = query.count()
    units = query.order_by(KeyUnit.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "list": [
            {
                "id": u.id,
                "unitName": u.unit_name,
                "unitCode": u.unit_code,
                "industry": u.industry,
                "level": u.level,
                "address": u.address,
                "legalPerson": u.legal_person,
                "contact": u.contact,
                "phone": u.phone,
                "buildingArea": u.building_area,
                "staffCount": u.staff_count,
                "fireManager": u.fire_manager,
                "firePhone": u.fire_phone,
                "riskLevel": u.risk_level,
                "status": u.status,
                "lastCheckDate": u.last_check_date.isoformat() if u.last_check_date else None,
                "remark": u.remark,
            }
            for u in units
        ],
    }


@router.post("/api/key-units")
def api_key_unit_create(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    unit = KeyUnit(
        tenant_id=tenant_id,
        unit_name=data.get("unit_name", data.get("unitName", "")),
        unit_code=data.get("unit_code", data.get("unitCode", "")),
        industry=data.get("industry", ""),
        level=data.get("level", "level2"),
        address=data.get("address", ""),
        legal_person=data.get("legal_person", data.get("legalPerson", "")),
        contact=data.get("contact", ""),
        phone=data.get("phone", ""),
        building_area=data.get("building_area", data.get("buildingArea", 0)),
        staff_count=data.get("staff_count", data.get("staffCount", 0)),
        fire_manager=data.get("fire_manager", data.get("fireManager", "")),
        fire_phone=data.get("fire_phone", data.get("firePhone", "")),
        risk_level=data.get("risk_level", data.get("riskLevel", "medium")),
        status=data.get("status", "active"),
        remark=data.get("remark", ""),
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return {"ok": True, "id": unit.id}


@router.put("/api/key-units/{unit_id}")
def api_key_unit_update(
    unit_id: int,
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    unit = db.query(KeyUnit).filter(KeyUnit.id == unit_id, KeyUnit.tenant_id == tenant_id).first()
    if not unit:
        return JSONResponse(status_code=404, content={"ok": False, "message": "单位不存在"})
    field_map = {
        "unit_name": ["unit_name", "unitName"],
        "unit_code": ["unit_code", "unitCode"],
        "industry": ["industry"],
        "level": ["level"],
        "address": ["address"],
        "legal_person": ["legal_person", "legalPerson"],
        "contact": ["contact"],
        "phone": ["phone"],
        "building_area": ["building_area", "buildingArea"],
        "staff_count": ["staff_count", "staffCount"],
        "fire_manager": ["fire_manager", "fireManager"],
        "fire_phone": ["fire_phone", "firePhone"],
        "risk_level": ["risk_level", "riskLevel"],
        "status": ["status"],
        "remark": ["remark"],
    }
    for col, keys in field_map.items():
        for k in keys:
            if k in data:
                setattr(unit, col, data[k])
                break
    unit.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.delete("/api/key-units/{unit_id}")
def api_key_unit_delete(
    unit_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    unit = db.query(KeyUnit).filter(KeyUnit.id == unit_id, KeyUnit.tenant_id == tenant_id).first()
    if not unit:
        return JSONResponse(status_code=404, content={"ok": False, "message": "单位不存在"})
    db.delete(unit)
    db.commit()
    return {"ok": True}


@router.get("/api/key-units/inspections")
def api_unit_inspections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(UnitInspection).filter(UnitInspection.tenant_id == tenant_id)
    if unit_id:
        unit = db.query(KeyUnit).filter(KeyUnit.id == unit_id, KeyUnit.tenant_id == tenant_id).first()
        if not unit:
            return JSONResponse(status_code=404, content={"ok": False, "message": "重点单位不存在"})
        query = query.filter(UnitInspection.unit_id == unit_id)
    total = query.count()
    inspections = query.order_by(UnitInspection.inspection_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "list": [
            {
                "id": i.id,
                "unitId": i.unit_id,
                "unitName": i.unit_name,
                "inspectionDate": i.inspection_date.isoformat() if i.inspection_date else None,
                "inspector": i.inspector,
                "inspectionType": i.inspection_type,
                "itemsChecked": i.items_checked,
                "itemsPassed": i.items_passed,
                "problemsFound": i.problems_found,
                "rectificationRequired": i.rectification_required,
                "result": i.result,
                "content": i.content,
            }
            for i in inspections
        ],
    }


# ============= 应急指挥 =============

@router.get("/api/emergency/stats")
def api_emergency_stats(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    plan_count = db.query(EmergencyPlan).filter(EmergencyPlan.tenant_id == tenant_id, EmergencyPlan.status == "active").count()
    supply_count = db.query(EmergencySupply).filter(EmergencySupply.tenant_id == tenant_id).count()
    team_count = db.query(EmergencyTeam).filter(EmergencyTeam.tenant_id == tenant_id, EmergencyTeam.status == "active").count()
    route_count = db.query(EvacuationRoute).filter(EvacuationRoute.tenant_id == tenant_id, EvacuationRoute.status == "active").count()

    total_quantity = 0
    for s in db.query(EmergencySupply).filter(EmergencySupply.tenant_id == tenant_id).all():
        total_quantity += s.quantity or 0

    total_members = 0
    for t in db.query(EmergencyTeam).filter(EmergencyTeam.tenant_id == tenant_id).all():
        total_members += t.member_count or 0

    return {
        "planCount": plan_count,
        "supplyCount": total_quantity,
        "supplyTypes": supply_count,
        "teamCount": team_count,
        "totalMembers": total_members,
        "routeCount": route_count,
    }


@router.get("/api/emergency/plans")
def api_emergency_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    plan_type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(EmergencyPlan).filter(EmergencyPlan.tenant_id == tenant_id)
    if plan_type:
        query = query.filter(EmergencyPlan.plan_type == plan_type)
    if status:
        query = query.filter(EmergencyPlan.status == status)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(EmergencyPlan.plan_name.ilike(kw))

    total = query.count()
    plans = query.order_by(EmergencyPlan.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "list": [
            {
                "id": p.id,
                "planName": p.plan_name,
                "type": p.plan_type,
                "planLevel": p.plan_level,
                "buildingId": p.building_id,
                "buildingName": p.building_name,
                "responsiblePerson": p.responsible_person,
                "contactPhone": p.contact_phone,
                "version": p.version,
                "status": p.status,
                "lastReviewDate": p.last_review_date.isoformat() if p.last_review_date else None,
                "nextReviewDate": p.next_review_date.isoformat() if p.next_review_date else None,
                "content": p.content,
                "procedures": json.loads(p.procedures or "[]"),
            }
            for p in plans
        ],
    }


@router.get("/api/emergency/supplies")
def api_emergency_supplies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    supply_type: Optional[str] = Query(None, alias="type"),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(EmergencySupply).filter(EmergencySupply.tenant_id == tenant_id)
    if supply_type:
        query = query.filter(EmergencySupply.supply_type == supply_type)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(EmergencySupply.supply_name.ilike(kw))

    total = query.count()
    supplies = query.order_by(EmergencySupply.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "list": [
            {
                "id": s.id,
                "supplyName": s.supply_name,
                "supplyType": s.supply_type,
                "specification": s.specification,
                "quantity": s.quantity,
                "unit": s.unit,
                "location": s.location,
                "manager": s.manager,
                "phone": s.phone,
                "expireDate": s.expire_date.isoformat() if s.expire_date else None,
                "status": s.status,
                "remark": s.remark,
            }
            for s in supplies
        ],
    }


@router.get("/api/emergency/teams")
def api_emergency_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    team_type: Optional[str] = Query(None, alias="type"),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(EmergencyTeam).filter(EmergencyTeam.tenant_id == tenant_id)
    if team_type:
        query = query.filter(EmergencyTeam.team_type == team_type)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(EmergencyTeam.team_name.ilike(kw))

    total = query.count()
    teams = query.order_by(EmergencyTeam.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "list": [
            {
                "id": t.id,
                "teamName": t.team_name,
                "teamType": t.team_type,
                "leader": t.leader,
                "leaderPhone": t.leader_phone,
                "memberCount": t.member_count,
                "members": json.loads(t.members or "[]"),
                "location": t.location,
                "equipment": json.loads(t.equipment or "[]"),
                "status": t.status,
                "remark": t.remark,
            }
            for t in teams
        ],
    }


@router.get("/api/emergency/routes")
def api_emergency_routes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    building_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(EvacuationRoute).filter(EvacuationRoute.tenant_id == tenant_id)
    if building_id:
        query = query.filter(EvacuationRoute.building_id == building_id)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(EvacuationRoute.route_name.ilike(kw))

    total = query.count()
    routes = query.order_by(EvacuationRoute.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "list": [
            {
                "id": r.id,
                "routeName": r.route_name,
                "buildingId": r.building_id,
                "buildingName": r.building_name,
                "floor": r.floor,
                "startPoint": r.start_point,
                "endPoint": r.end_point,
                "capacity": r.capacity,
                "distance": r.distance,
                "status": r.status,
                "remark": r.remark,
            }
            for r in routes
        ],
    }


def init_business_data(db: Session) -> None:
    """初始化示例数据"""
    from database import Building, get_default_tenant_id

    today = date.today()
    tenant_id = get_default_tenant_id(db)

    if db.query(DutyShift).count() == 0:
        shifts = [
            DutyShift(
                tenant_id=tenant_id,
                shift_name="白班", shift_type="day",
                start_time="08:00", end_time="20:00",
                duty_date=today,
                persons=json.dumps([
                    {"id": 1, "name": "张三", "role": "值班长"},
                    {"id": 2, "name": "李四", "role": "值班员"},
                ]),
                status="active",
            ),
            DutyShift(
                tenant_id=tenant_id,
                shift_name="夜班", shift_type="night",
                start_time="20:00", end_time="08:00",
                duty_date=today,
                persons=json.dumps([
                    {"id": 3, "name": "王五", "role": "值班长"},
                    {"id": 4, "name": "赵六", "role": "值班员"},
                ]),
                status="scheduled",
            ),
        ]
        db.add_all(shifts)

    if db.query(DutyRecord).count() == 0:
        for i in range(10):
            d = today - timedelta(days=i)
            db.add(DutyRecord(
                tenant_id=tenant_id,
                record_date=d,
                shift_name="白班" if i % 2 == 0 else "夜班",
                duty_person=["张三", "李四", "王五", "赵六"][i % 4],
                weather=["晴", "多云", "阴", "小雨"][i % 4],
                alarm_count=2 + (i % 5),
                handled_count=2 + (i % 5) - (i % 2),
                inspection_count=5 + (i % 3),
                abnormal_count=i % 2,
                equipment_status="normal" if i % 3 != 0 else "warning",
                content="值班期间设备运行正常，无重大异常情况。" if i % 3 != 0 else "发现1处设备异常，已通知维修。",
            ))

    if db.query(DutyHandover).count() == 0:
        for i in range(5):
            t = datetime.utcnow() - timedelta(days=i)
            db.add(DutyHandover(
                tenant_id=tenant_id,
                handover_time=t,
                from_person=["张三", "王五"][i % 2],
                to_person=["李四", "赵六"][i % 2],
                pending_matters="" if i > 0 else "3楼消防栓压力偏低，需跟进",
                equipment_status="normal",
                status="completed",
            ))

    if db.query(KeyUnit).count() == 0:
        units_data = [
            ("实验中学", "JY-001", "school", "level1", "人民路128号", "王建国", "主任", "13800138001", 25000, 800, "李明", "13900139001", "high"),
            ("人民医院", "YL-001", "hospital", "level1", "健康路56号", "陈院长", "院长", "13800138002", 35000, 1200, "张伟", "13900139002", "high"),
            ("华联购物中心", "SC-001", "mall", "level1", "商业街88号", "刘总", "总经理", "13800138003", 48000, 350, "孙强", "13900139003", "medium"),
            ("万达酒店", "JD-001", "hotel", "level2", "滨江路168号", "周经理", "经理", "13800138004", 18000, 180, "吴涛", "13900139004", "medium"),
            ("星光KTV", "YL-002", "entertainment", "level2", "娱乐街22号", "郑总", "老板", "13800138005", 3000, 25, "冯明", "13900139005", "high"),
            ("精工机械厂", "GY-001", "factory", "level2", "工业园区6号", "马厂长", "厂长", "13800138006", 52000, 200, "朱工", "13900139006", "medium"),
            ("平安仓储", "CK-001", "warehouse", "level3", "物流园B区", "胡经理", "经理", "13800138007", 15000, 15, "何伟", "13900139007", "low"),
        ]
        for name, code, industry, level, addr, legal, contact, phone, area, staff, fm, fp, risk in units_data:
            db.add(KeyUnit(
                tenant_id=tenant_id,
                unit_name=name, unit_code=code, industry=industry, level=level,
                address=addr, legal_person=legal, contact=contact, phone=phone,
                building_area=area, staff_count=staff,
                fire_manager=fm, fire_phone=fp, risk_level=risk,
                status="active",
            ))

    if db.query(UnitInspection).count() == 0:
        units = db.query(KeyUnit).all()
        for i, u in enumerate(units):
            d = today - timedelta(days=i * 5 + 3)
            items = 20 + (i % 5) * 3
            passed = items - (i % 3)
            problems = i % 3
            db.add(UnitInspection(
                tenant_id=tenant_id,
                unit_id=u.id, unit_name=u.unit_name,
                inspection_date=d,
                inspector=["李检查", "王检查", "张检查"][i % 3],
                inspection_type=["routine", "special", "seasonal"][i % 3],
                items_checked=items, items_passed=passed,
                problems_found=problems, rectification_required=1 if problems > 0 else 0,
                result="qualified" if problems == 0 else "unqualified",
                content="经检查，消防设施基本完好，部分灭火器需充装。" if problems > 0 else "检查合格，各项设施运行正常。",
            ))

    if db.query(EmergencyPlan).count() == 0:
        buildings = db.query(Building).all()
        bld_names = [b.building_name for b in buildings] if buildings else ["实验楼A栋", "教学楼B栋", "图书馆"]
        plans_data = [
            ("火灾应急预案", "fire", "general", 0, "李明", "13900139001", "V2.1", "active"),
            ("地震应急疏散预案", "earthquake", "special", 1, "王主任", "13900139002", "V1.5", "active"),
            ("台风防汛应急预案", "typhoon", "general", 0, "张经理", "13900139003", "V1.2", "active"),
            ("电梯困人应急预案", "elevator", "special", 0, "物业", "13900139004", "V1.0", "active"),
            ("危险化学品泄漏预案", "chemical", "special", 0, "安全办", "13900139005", "V1.3", "pending"),
            ("人员密集场所疏散", "stampede", "general", 0, "安保部", "13900139006", "V2.0", "active"),
        ]
        for i, (name, ptype, plevel, bi, resp, phone, ver, sta) in enumerate(plans_data):
            db.add(EmergencyPlan(
                tenant_id=tenant_id,
                plan_name=name, plan_type=ptype, plan_level=plevel,
                building_id=buildings[bi % len(buildings)].id if buildings else None,
                building_name=bld_names[bi % len(bld_names)],
                responsible_person=resp, contact_phone=phone,
                version=ver, status=sta,
                last_review_date=today - timedelta(days=30 * i),
                next_review_date=today + timedelta(days=180),
                content=f"{name}详细内容，包含应急响应流程、人员职责、处置措施等。",
                procedures=json.dumps([
                    {"step": 1, "title": "报警与接警", "desc": "发现险情立即拨打119并上报"},
                    {"step": 2, "title": "启动预案", "desc": "应急指挥部启动预案，通知相关人员"},
                    {"step": 3, "title": "疏散救援", "desc": "组织人员疏散，开展自救互救"},
                    {"step": 4, "title": "配合救援", "desc": "引导专业救援队伍，提供相关信息"},
                ]),
            ))

    if db.query(EmergencySupply).count() == 0:
        supplies_data = [
            ("正压式空气呼吸器", "equipment", "RHZKF6.8/30", 12, "具", "器材室A-01", "张主管", "13900139011", None, "normal"),
            ("消防战斗服", "equipment", "标准款", 30, "套", "器材室A-02", "张主管", "13900139011", None, "normal"),
            ("消防头盔", "equipment", "F2款", 30, "个", "器材室A-03", "张主管", "13900139011", None, "normal"),
            ("消防斧", "equipment", "标准款", 8, "把", "器材室A-04", "张主管", "13900139011", None, "normal"),
            ("应急照明灯", "equipment", "充电式", 50, "个", "器材室B-01", "李主管", "13900139012", None, "normal"),
            ("手电筒", "equipment", "LED强光电筒", 80, "个", "器材室B-02", "李主管", "13900139012", None, "normal"),
            ("急救箱", "medical", "标准配置", 15, "个", "各楼层", "王护士", "13900139013", None, "normal"),
            ("担架", "equipment", "折叠式", 6, "副", "器材室C-01", "刘主管", "13900139014", None, "normal"),
            ("扩音器", "equipment", "大功率", 10, "个", "器材室C-02", "刘主管", "13900139014", None, "normal"),
            ("警戒带", "equipment", "50m/卷", 30, "卷", "器材室C-03", "刘主管", "13900139014", None, "normal"),
        ]
        for name, stype, spec, qty, unit, loc, mgr, phone, exp, sta in supplies_data:
            db.add(EmergencySupply(
                tenant_id=tenant_id,
                supply_name=name, supply_type=stype, specification=spec,
                quantity=qty, unit=unit, location=loc,
                manager=mgr, phone=phone, expire_date=exp, status=sta,
            ))

    if db.query(EmergencyTeam).count() == 0:
        teams_data = [
            ("第一志愿消防队", "volunteer", "张队长", "13900139021", 15, "实验楼", ["灭火器", "水带", "扳手"]),
            ("第二志愿消防队", "volunteer", "李队长", "13900139022", 12, "教学楼", ["灭火器", "水带"]),
            ("应急疏散引导队", "evacuation", "王队长", "13900139023", 20, "全园区", ["扩音器", "手电筒", "哨子"]),
            ("医疗救护队", "medical", "赵护士长", "13900139024", 8, "医务室", ["急救箱", "担架", "AED"]),
            ("后勤保障队", "support", "刘主任", "13900139025", 10, "后勤处", ["应急物资", "车辆", "通讯设备"]),
        ]
        for name, ttype, leader, phone, count, loc, equip in teams_data:
            members = []
            for j in range(count):
                members.append({"id": j + 1, "name": f"队员{j+1}", "role": "队员"})
            db.add(EmergencyTeam(
                tenant_id=tenant_id,
                team_name=name, team_type=ttype,
                leader=leader, leader_phone=phone,
                member_count=count,
                members=json.dumps(members),
                location=loc,
                equipment=json.dumps(equip),
                status="active",
            ))

    if db.query(EvacuationRoute).count() == 0:
        buildings = db.query(Building).all()
        bld_names = [b.building_name for b in buildings] if buildings else ["实验楼A栋", "教学楼B栋"]
        routes_data = [
            ("A栋东疏散路线", 0, "1楼", "东侧走廊", "东安全出口", 100, 50),
            ("A栋西疏散路线", 0, "1楼", "西侧走廊", "西安全出口", 100, 45),
            ("B栋主疏散路线", 1, "1楼", "中央大厅", "南门", 150, 80),
            ("B栋次疏散路线", 1, "1楼", "北侧走廊", "北门", 80, 60),
            ("天台救援路线", 0, "天台", "楼梯间", "天台直升机坪", 30, 30),
        ]
        for i, (name, bi, floor, sp, ep, cap, dist) in enumerate(routes_data):
            db.add(EvacuationRoute(
                tenant_id=tenant_id,
                route_name=name,
                building_id=buildings[bi % len(buildings)].id if buildings else None,
                building_name=bld_names[bi % len(bld_names)],
                floor=floor, start_point=sp, end_point=ep,
                capacity=cap, distance=dist,
                status="active",
            ))

    db.commit()
