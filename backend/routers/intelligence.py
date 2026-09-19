"""
智能分析路由
提供8大智能分析能力的API接口
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from database import AlertRecord, Device, get_db
from services.intelligence_service import (
    analyze_alert_detail,
    analyze_inspection_risk,
    generate_rectification_plan,
    diagnose_device_fault,
    generate_daily_brief,
    analyze_alert_correlation,
    extract_experience_from_case,
    recommend_similar_knowledge,
    answer_natural_language_query,
)

from services.auth_service import get_current_tenant_id, get_current_user
from services.rag_admin_service import list_rag_entries
from services.alert_lifecycle_service import ALERT_STATUS_LABELS

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["智能分析"])


def _similar_alerts(db: Session, tenant_id: int, alert_type: str, exclude_code: str, limit: int = 3):
    """查本租户同类型的历史告警，作为「类似告警」展示。

    改造前这一块是 `random` 编出来的：随机 id、随机楼层、随机原因、随机处置结果。
    现在只给库里真有的记录；查不到就返回空列表。
    """
    if not alert_type:
        return []
    query = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.alert_type == alert_type,
    )
    if exclude_code:
        query = query.filter(AlertRecord.alert_code != exclude_code)
    records = query.order_by(AlertRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "id": record.alert_code,
            "time": record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "",
            "location": record.location or record.building_name or "",
            "result": ALERT_STATUS_LABELS.get(record.status, record.status or ""),
        }
        for record in records
    ]


# ============================================================
# 1. 告警深度分析
# ============================================================

class AlertAnalyzeRequest(BaseModel):
    alert_id: Optional[str] = None
    alert_type: str = ""
    alert_name: str = ""
    severity: str = "medium"
    device_id: str = ""
    building_name: str = ""
    building_id: Optional[str] = None
    alert_value: Optional[float] = None
    alert_unit: str = ""
    description: str = ""


@router.post("/api/intelligence/analyze-alert")
def api_analyze_alert(
    req: AlertAnalyzeRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    similar = _similar_alerts(db, tenant_id, req.alert_type, req.alert_id or "")
    result = analyze_alert_detail(req.dict(), similar_alerts=similar)
    return {"ok": True, "data": result}


# ============================================================
# 2. 巡检风险研判
# ============================================================

class InspectionAnalyzeRequest(BaseModel):
    inspection_id: Optional[str] = None
    building_name: str = ""
    inspector: str = ""
    content: str = ""
    items: List[Dict[str, Any]] = []


@router.post("/api/intelligence/analyze-inspection")
def api_analyze_inspection(req: InspectionAnalyzeRequest):
    result = analyze_inspection_risk(req.dict())
    return {"ok": True, "data": result}


# ============================================================
# 3. 工单整改辅助
# ============================================================

class RectificationPlanRequest(BaseModel):
    workorder_id: Optional[str] = None
    hazard_type: str = "消防设施"
    risk_level: str = "medium"
    description: str = ""
    building_name: str = ""
    device_id: Optional[str] = None


@router.post("/api/intelligence/generate-rectification-plan")
def api_generate_rectification_plan(req: RectificationPlanRequest):
    result = generate_rectification_plan(req.dict())
    return {"ok": True, "data": result}


# ============================================================
# 4. 设备故障诊断
# ============================================================

class DeviceDiagnoseRequest(BaseModel):
    device_id: str = ""
    device_name: str = ""
    device_type: str = ""
    status: str = "故障"
    building_name: str = ""


@router.post("/api/intelligence/diagnose-device")
def api_diagnose_device(
    req: DeviceDiagnoseRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    # 带了 device_id 就取本租户的设备台账，让权重基于设备真实数据（投用年限/维保/最近上报）来算；
    # 取不到（没传 id、或不属于本租户）就退回知识库先验权重，返回里会标明 basis
    device = None
    raw_device_id = (req.device_id or "").strip()
    if raw_device_id.isdigit():
        device = db.query(Device).filter(
            Device.id == int(raw_device_id), Device.tenant_id == tenant_id
        ).first()
    result = diagnose_device_fault(req.dict(), device=device)
    return {"ok": True, "data": result}


# ============================================================
# 5. 每日安全简报
# ============================================================

@router.get("/api/intelligence/daily-brief")
def api_daily_brief(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = generate_daily_brief(db, tenant_id, date)
    return {"ok": True, "data": result}


# ============================================================
# 6. 告警聚合分析
# ============================================================

class AlertCorrelationRequest(BaseModel):
    alerts: List[Dict[str, Any]]


@router.post("/api/intelligence/analyze-alert-correlation")
def api_analyze_alert_correlation(req: AlertCorrelationRequest):
    result = analyze_alert_correlation(req.alerts)
    return {"ok": True, "data": result}


# ============================================================
# 7. 知识经验沉淀
# ============================================================

class ExperienceExtractRequest(BaseModel):
    case_data: Dict[str, Any]


@router.post("/api/intelligence/extract-experience")
def api_extract_experience(req: ExperienceExtractRequest):
    result = extract_experience_from_case(req.case_data)
    return {"ok": True, "data": result}


@router.get("/api/intelligence/recommend-knowledge")
def api_recommend_knowledge(query: str):
    # 候选条目取自运行时库的 rag_entries（真实知识库），不再用函数里写死的假条目
    result = recommend_similar_knowledge(query, list_rag_entries(enabled="1"))
    return {"ok": True, "data": result}


# ============================================================
# 8. 数据自然语言查询
# ============================================================

@router.get("/api/intelligence/query-data")
def api_query_data(
    question: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = answer_natural_language_query(question, db, tenant_id)
    return {"ok": True, "data": result}
