"""
维保管理路由
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date, timedelta
import random

from database import get_db, MaintenanceCompany, MaintenancePlan, MaintenanceRecord, Building, Device

from services.auth_service import get_current_user, get_current_tenant_id

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["维保管理"])


def _generate_plan_no():
    return f"MP-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def _generate_record_no():
    return f"MR-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def _plan_to_dict(plan: MaintenancePlan, db: Session, tenant_id: int):
    building = db.query(Building).filter(Building.id == plan.building_id, Building.tenant_id == tenant_id).first()
    company = db.query(MaintenanceCompany).filter(MaintenanceCompany.id == plan.company_id, MaintenanceCompany.tenant_id == tenant_id).first()
    return {
        "id": plan.id,
        "plan_no": plan.plan_no,
        "plan_name": plan.plan_name,
        "type": plan.type,
        "building_id": plan.building_id,
        "building_name": building.building_name if building else "",
        "company_id": plan.company_id,
        "company": company.name if company else "",
        "device_count": plan.device_count,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "next_date": plan.next_date.isoformat() if plan.next_date else None,
        "content": plan.content,
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _record_to_dict(record: MaintenanceRecord, db: Session):
    return {
        "id": record.id,
        "record_no": record.record_no,
        "plan_id": record.plan_id,
        "plan_name": record.plan_name,
        "type": record.type,
        "building_id": record.building_id,
        "building_name": record.building_name,
        "device_count": record.device_count,
        "fault_count": record.fault_count,
        "maintainer": record.maintainer,
        "maintain_date": record.maintain_date.isoformat() if record.maintain_date else None,
        "result": record.result,
        "content": record.content,
        "remark": record.remark,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _company_to_dict(company: MaintenanceCompany, db: Session, tenant_id: int):
    device_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        Device.status != "已报废"
    ).count() if company.status == "active" else 0
    days_left = 0
    if company.contract_end:
        days_left = (company.contract_end - date.today()).days
    return {
        "id": company.id,
        "name": company.name,
        "qualification": company.qualification,
        "level": company.level,
        "contact": company.contact,
        "phone": company.phone,
        "address": company.address,
        "device_count": device_count,
        "contract_start": company.contract_start.isoformat() if company.contract_start else None,
        "contract_end": company.contract_end.isoformat() if company.contract_end else None,
        "days_left": days_left,
        "status": company.status,
        "remark": company.remark,
    }


# ============================================================
# 统计数据
# ============================================================

@router.get("/api/maintenance/stats")
def api_maintenance_stats(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    total_plans = db.query(MaintenancePlan).filter(MaintenancePlan.tenant_id == tenant_id).count()
    active_plans = db.query(MaintenancePlan).filter(MaintenancePlan.tenant_id == tenant_id, MaintenancePlan.status == "active").count()
    total_companies = db.query(MaintenanceCompany).filter(MaintenanceCompany.tenant_id == tenant_id).count()
    active_companies = db.query(MaintenanceCompany).filter(MaintenanceCompany.tenant_id == tenant_id, MaintenanceCompany.status == "active").count()

    today = date.today()
    first_of_month = today.replace(day=1)
    completed_this_month = db.query(MaintenanceRecord).filter(
        MaintenanceRecord.tenant_id == tenant_id,
        MaintenanceRecord.maintain_date >= first_of_month
    ).count()

    overdue_devices = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        Device.next_maintenance.isnot(None),
        Device.next_maintenance < today,
        Device.status != "已报废"
    ).count()

    return {
        "totalPlans": total_plans,
        "activePlans": active_plans,
        "completed": completed_this_month,
        "overdue": overdue_devices,
        "companies": total_companies,
        "activeCompanies": active_companies,
    }


# ============================================================
# 维保计划
# ============================================================

@router.get("/api/maintenance/plans")
def api_list_plans(
    type: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(MaintenancePlan).filter(MaintenancePlan.tenant_id == tenant_id)
    if type:
        query = query.filter(MaintenancePlan.type == type)
    if status:
        query = query.filter(MaintenancePlan.status == status)
    if keyword:
        query = query.filter(
            (MaintenancePlan.plan_name.contains(keyword)) |
            (MaintenancePlan.plan_no.contains(keyword))
        )
    plans = query.order_by(MaintenancePlan.id.desc()).all()
    return [_plan_to_dict(p, db, tenant_id) for p in plans]


@router.post("/api/maintenance/plans")
def api_create_plan(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    plan = MaintenancePlan(
        tenant_id=tenant_id,
        plan_no=_generate_plan_no(),
        plan_name=data.get("plan_name", ""),
        type=data.get("type", "monthly"),
        building_id=data.get("building_id"),
        company_id=data.get("company_id"),
        device_count=data.get("device_count", 0),
        start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else None,
        end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
        next_date=date.fromisoformat(data["next_date"]) if data.get("next_date") else None,
        content=data.get("content", ""),
        status=data.get("status", "active"),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _plan_to_dict(plan, db, tenant_id)


@router.put("/api/maintenance/plans/{plan_id}")
def api_update_plan(
    plan_id: int,
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    plan = db.query(MaintenancePlan).filter(MaintenancePlan.id == plan_id, MaintenancePlan.tenant_id == tenant_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="维保计划不存在")
    for key, value in data.items():
        if key in ("start_date", "end_date", "next_date") and value:
            setattr(plan, key, date.fromisoformat(value))
        elif hasattr(plan, key):
            setattr(plan, key, value)
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return _plan_to_dict(plan, db, tenant_id)


@router.delete("/api/maintenance/plans/{plan_id}")
def api_delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    plan = db.query(MaintenancePlan).filter(MaintenancePlan.id == plan_id, MaintenancePlan.tenant_id == tenant_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="维保计划不存在")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/api/maintenance/plans/{plan_id}/status")
def api_toggle_plan_status(
    plan_id: int,
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    plan = db.query(MaintenancePlan).filter(MaintenancePlan.id == plan_id, MaintenancePlan.tenant_id == tenant_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="维保计划不存在")
    plan.status = data.get("status", plan.status)
    plan.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ============================================================
# 维保记录
# ============================================================

@router.get("/api/maintenance/records")
def api_list_records(
    type: Optional[str] = None,
    result: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(MaintenanceRecord)
    if type:
        query = query.filter(MaintenanceRecord.type == type)
    if result:
        query = query.filter(MaintenanceRecord.result == result)
    if keyword:
        query = query.filter(
            (MaintenanceRecord.plan_name.contains(keyword)) |
            (MaintenanceRecord.record_no.contains(keyword)) |
            (MaintenanceRecord.building_name.contains(keyword))
        )
    query = query.filter(MaintenanceRecord.tenant_id == tenant_id)
    records = query.order_by(MaintenanceRecord.id.desc()).all()
    return [_record_to_dict(r, db) for r in records]


@router.post("/api/maintenance/records")
def api_create_record(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    record = MaintenanceRecord(
        tenant_id=tenant_id,
        record_no=_generate_record_no(),
        plan_id=data.get("plan_id"),
        plan_name=data.get("plan_name", ""),
        type=data.get("type", "monthly"),
        building_id=data.get("building_id"),
        building_name=data.get("building_name", ""),
        company_id=data.get("company_id"),
        device_count=data.get("device_count", 0),
        fault_count=data.get("fault_count", 0),
        maintainer=data.get("maintainer", ""),
        maintain_date=date.fromisoformat(data["maintain_date"]) if data.get("maintain_date") else None,
        result=data.get("result", "normal"),
        content=data.get("content", ""),
        remark=data.get("remark", ""),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_to_dict(record, db)


@router.get("/api/maintenance/records/{record_id}")
def api_get_record(
    record_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id, MaintenanceRecord.tenant_id == tenant_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="维保记录不存在")
    return _record_to_dict(record, db)


# ============================================================
# 维保单位
# ============================================================

@router.get("/api/maintenance/companies")
def api_list_companies(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(MaintenanceCompany).filter(MaintenanceCompany.tenant_id == tenant_id)
    if keyword:
        query = query.filter(MaintenanceCompany.name.contains(keyword))
    if status:
        query = query.filter(MaintenanceCompany.status == status)
    companies = query.order_by(MaintenanceCompany.id.desc()).all()
    return [_company_to_dict(c, db, tenant_id) for c in companies]


@router.post("/api/maintenance/companies")
def api_create_company(
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    company = MaintenanceCompany(
        tenant_id=tenant_id,
        name=data.get("name", ""),
        qualification=data.get("qualification", ""),
        level=data.get("level", ""),
        contact=data.get("contact", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        contract_start=date.fromisoformat(data["contract_start"]) if data.get("contract_start") else None,
        contract_end=date.fromisoformat(data["contract_end"]) if data.get("contract_end") else None,
        status=data.get("status", "active"),
        remark=data.get("remark", ""),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return _company_to_dict(company, db, tenant_id)


@router.put("/api/maintenance/companies/{company_id}")
def api_update_company(
    company_id: int,
    data: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    company = db.query(MaintenanceCompany).filter(MaintenanceCompany.id == company_id, MaintenanceCompany.tenant_id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="维保单位不存在")
    for key, value in data.items():
        if key in ("contract_start", "contract_end") and value:
            setattr(company, key, date.fromisoformat(value))
        elif hasattr(company, key):
            setattr(company, key, value)
    company.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(company)
    return _company_to_dict(company, db, tenant_id)


@router.delete("/api/maintenance/companies/{company_id}")
def api_delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    company = db.query(MaintenanceCompany).filter(MaintenanceCompany.id == company_id, MaintenanceCompany.tenant_id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="维保单位不存在")
    db.delete(company)
    db.commit()
    return {"ok": True}


# ============================================================
# 超期预警
# ============================================================

@router.get("/api/maintenance/overdue")
def api_overdue_devices(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    today = date.today()
    devices = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        Device.next_maintenance.isnot(None),
        Device.next_maintenance < today,
        Device.status != "已报废"
    ).order_by(Device.next_maintenance.asc()).all()

    result = []
    for d in devices:
        building = db.query(Building).filter(Building.id == d.building_id, Building.tenant_id == tenant_id).first()
        overdue_days = (today - d.next_maintenance).days if d.next_maintenance else 0
        result.append({
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "building_id": d.building_id,
            "building_name": building.building_name if building else "",
            "location": d.location,
            "last_maintenance": d.last_maintenance.isoformat() if d.last_maintenance else None,
            "next_maintenance": d.next_maintenance.isoformat() if d.next_maintenance else None,
            "overdue_days": overdue_days,
            "maintenance_company": "永安消防维保有限公司",
            "status": d.status,
        })
    return result


# ============================================================
# 初始化示例数据
# ============================================================

def init_maintenance_data(db: Session):
    if db.query(MaintenanceCompany).count() > 0:
        return

    from database import get_default_tenant_id
    tenant_id = get_default_tenant_id(db)

    companies = [
        MaintenanceCompany(name="永安消防维保有限公司", qualification="一级资质", level="一级", contact="张经理", phone="13800138000", address="永安路88号", contract_start=date(2025, 7, 1), contract_end=date(2027, 6, 30), status="active"),
        MaintenanceCompany(name="中信消防技术服务公司", qualification="二级资质", level="二级", contact="李经理", phone="13900139000", address="中信大厦15层", contract_start=date(2025, 1, 1), contract_end=date(2026, 12, 31), status="active"),
        MaintenanceCompany(name="安恒消防设备公司", qualification="一级资质", level="一级", contact="王经理", phone="13700137000", address="安恒路123号", contract_start=date(2025, 10, 1), contract_end=date(2026, 9, 30), status="active"),
        MaintenanceCompany(name="华宇消防工程公司", qualification="三级资质", level="三级", contact="赵经理", phone="13600136000", address="华宇工业园", contract_start=date(2025, 4, 1), contract_end=date(2026, 3, 31), status="inactive"),
    ]
    for company in companies:
        company.tenant_id = tenant_id
    db.add_all(companies)
    db.flush()

    c1_id = companies[0].id
    c2_id = companies[1].id
    c3_id = companies[2].id

    today = date.today()
    plans = [
        MaintenancePlan(plan_no="MP-2026-001", plan_name="综合办公楼月度消防维保", type="monthly", building_id=1, company_id=c1_id, device_count=156, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), next_date=today + timedelta(days=5), status="active", content="月度常规检查：烟感、温感、消火栓、喷淋系统、应急照明等"),
        MaintenancePlan(plan_no="MP-2026-002", plan_name="实验楼季度维保计划", type="quarterly", building_id=2, company_id=c2_id, device_count=89, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), next_date=today + timedelta(days=20), status="active", content="季度全面维保：火灾报警系统、消防联动系统、气体灭火系统"),
        MaintenancePlan(plan_no="MP-2026-003", plan_name="学生宿舍半年度维保", type="half_year", building_id=3, company_id=c1_id, device_count=234, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), next_date=today + timedelta(days=90), status="active", content="半年度深度维保：全面检测消防设施性能，更换老化部件"),
        MaintenancePlan(plan_no="MP-2026-004", plan_name="图书馆年度全面维保", type="yearly", building_id=4, company_id=c2_id, device_count=178, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), next_date=today + timedelta(days=60), status="active", content="年度全面维保：所有消防设施检测、维护、性能测试"),
        MaintenancePlan(plan_no="MP-2026-005", plan_name="地下车库月度维保", type="monthly", building_id=5, company_id=c1_id, device_count=67, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), next_date=today + timedelta(days=10), status="active", content="地下车库消防设施月度巡检"),
        MaintenancePlan(plan_no="MP-2026-006", plan_name="食堂燃气报警系统维保", type="monthly", building_id=6, company_id=c3_id, device_count=45, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), next_date=today + timedelta(days=3), status="paused", content="燃气报警系统专项维保"),
    ]
    for plan in plans:
        plan.tenant_id = tenant_id
    db.add_all(plans)
    db.flush()

    records = [
        MaintenanceRecord(record_no="MR-20260901", plan_id=plans[0].id, plan_name="综合办公楼月度消防维保", type="monthly", building_id=1, building_name="综合办公楼A座", company_id=c1_id, device_count=156, fault_count=2, maintainer="李工", maintain_date=today - timedelta(days=8), result="fault", content="完成156台设备巡检，发现2处故障：3层走廊烟感故障、地下室喷淋阀渗漏", remark="已安排整改"),
        MaintenanceRecord(record_no="MR-20260828", plan_id=plans[4].id, plan_name="地下车库月度维保", type="monthly", building_id=5, building_name="地下车库B1层", company_id=c1_id, device_count=67, fault_count=0, maintainer="王工", maintain_date=today - timedelta(days=12), result="normal", content="所有设备运行正常，无故障"),
        MaintenanceRecord(record_no="MR-20260820", plan_id=plans[1].id, plan_name="实验楼季度维保计划", type="quarterly", building_id=2, building_name="实验楼B座", company_id=c2_id, device_count=89, fault_count=5, maintainer="张工", maintain_date=today - timedelta(days=20), result="recheck", content="季度维保发现5处隐患，待复检", remark="已下发整改通知"),
        MaintenanceRecord(record_no="MR-20260815", plan_id=plans[0].id, plan_name="综合办公楼月度消防维保", type="monthly", building_id=1, building_name="综合办公楼A座", company_id=c1_id, device_count=156, fault_count=1, maintainer="李工", maintain_date=today - timedelta(days=25), result="normal", content="完成月度维保，1处小问题现场处理"),
        MaintenanceRecord(record_no="MR-20260728", plan_id=plans[4].id, plan_name="地下车库月度维保", type="monthly", building_id=5, building_name="地下车库B1层", company_id=c1_id, device_count=67, fault_count=0, maintainer="王工", maintain_date=today - timedelta(days=42), result="normal", content="正常"),
        MaintenanceRecord(record_no="MR-20260701", plan_id=plans[0].id, plan_name="综合办公楼月度消防维保", type="monthly", building_id=1, building_name="综合办公楼A座", company_id=c1_id, device_count=156, fault_count=3, maintainer="李工", maintain_date=today - timedelta(days=70), result="normal", content="完成维保，3处问题已处理"),
    ]
    for record in records:
        record.tenant_id = tenant_id
    db.add_all(records)
    db.commit()
