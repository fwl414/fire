from __future__ import annotations

import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Form, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import Dict, Any, List, Optional
from database import get_db, AlertRecord, User

from services.alert_agent_service import (
    _get_alert_profile,
    process_device_alert,
    get_processed_alerts,
    get_alert_statistics,
    init_demo_alerts,
)
from services.alert_lifecycle_service import (
    ALERT_SEVERITY_LABELS,
    ALERT_STATUS_LABELS,
    MERGED_STATUS,
    alert_state_payload,
    escalate_overdue_alerts,
    ingest_alert,
    merge_alerts,
    persist_alert_workorder,
)


from services.auth_service import get_current_user, require_permission

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["告警中心"])

@router.post("/api/alert/process")
def api_process_alert(
    device_id: str = Form(...),
    alert_type: str = Form(...),
    alert_value: Optional[float] = Form(None),
    alert_unit: str = Form(""),
    device_info: str = Form("{}"),
    telemetry_history: str = Form("[]"),
    building_id: str = Form("default"),
    building_name: str = Form("未指定区域"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        dev_info = json.loads(device_info) if device_info else {}
    except Exception:
        dev_info = {}
    try:
        history = json.loads(telemetry_history) if telemetry_history else []
    except Exception:
        history = []
    
    result = process_device_alert(
        device_id=device_id,
        alert_type=alert_type,
        alert_value=alert_value,
        alert_unit=alert_unit,
        device_info=dev_info,
        telemetry_history=history,
        building_id=building_id,
        building_name=building_name
    )
    
    severity = result.get("severity", "medium")
    
    building_id_int = None
    try:
        if building_id and building_id != "default":
            building_id_int = int(building_id)
    except (ValueError, TypeError):
        building_id_int = None
    
    device_id_int = None
    try:
        if device_id:
            device_id_int = int(device_id)
    except (ValueError, TypeError):
        device_id_int = None
    
    agent_analysis = json.dumps(result.get("analysis", {}), ensure_ascii=False)
    
    outcome = ingest_alert(
        db,
        tenant_id=current_user.tenant_id,
        alert_type=alert_type,
        severity=severity,
        description=result.get("alert_name", alert_type),
        alert_value=alert_value,
        alert_unit=alert_unit,
        device_id=device_id_int,
        device_code=dev_info.get("code", ""),
        device_name=dev_info.get("name", device_id),
        building_id=building_id_int,
        building_name=building_name,
        location=dev_info.get("location", building_name),
        agent_analysis=agent_analysis,
        device_info=dev_info,
        telemetry_history=history,
    )
    alert_record = outcome["alert"]

    ticket = persist_alert_workorder(
        db,
        tenant_id=current_user.tenant_id,
        alert=alert_record,
        workorder=result.get("workorder"),
        reporter_id=current_user.id,
        reporter_name=current_user.real_name or current_user.username,
    )
    
    result["alert_id"] = alert_record.id
    result["alert_code"] = alert_record.alert_code
    result["dedup"] = {
        "action": outcome["action"],
        "merged": outcome["merged"],
        "repeat_count": outcome["repeat_count"],
        "escalated": outcome["escalated"],
    }
    result["workorder_id"] = alert_record.workorder_id
    if ticket is not None:
        result["workorder"]["ticket_id"] = ticket.id
        result["workorder"]["ticket_no"] = ticket.id
        result["workorder"]["status"] = ticket.status
    
    return result


@router.get("/api/alert/list")
def api_alert_list(
    building_id: Optional[int] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    include_merged: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AlertRecord).filter(AlertRecord.tenant_id == current_user.tenant_id)
    
    if not include_merged:
        query = query.filter(AlertRecord.status != MERGED_STATUS)
    
    if building_id is not None:
        query = query.filter(AlertRecord.building_id == building_id)
    
    if alert_type:
        query = query.filter(AlertRecord.alert_type == alert_type)
    
    if severity:
        query = query.filter(AlertRecord.severity == severity)
    
    query = query.order_by(AlertRecord.created_at.desc()).limit(limit)
    alerts = query.all()
    
    items = []
    for alert in alerts:
        items.append({
            "id": alert.id,
            "alert_code": alert.alert_code,
            "device_id": alert.device_id,
            "device_code": alert.device_code,
            "device_name": alert.device_name,
            "building_id": alert.building_id,
            "building_name": alert.building_name,
            "location": alert.location,
            "alert_type": alert.alert_type,
            # 界面文案统一由后端给（复用告警档案里的中文名与状态字典），避免各页面各写一套映射
            "alert_type_label": _get_alert_profile(alert.alert_type or "").get("name") or alert.alert_type or "",
            "severity_label": ALERT_SEVERITY_LABELS.get(alert.severity, alert.severity or ""),
            "status_label": ALERT_STATUS_LABELS.get(alert.status, alert.status or ""),
            "alert_value": alert.alert_value,
            "alert_unit": alert.alert_unit,
            "severity": alert.severity,
            "status": alert.status,
            "description": alert.description,
            "repeat_count": alert.repeat_count or 1,
            "escalated": bool(alert.escalated),
            "workorder_id": alert.workorder_id,
            "last_seen_at": alert.last_seen_at.isoformat() if alert.last_seen_at else "",
            "created_at": alert.created_at.isoformat() if alert.created_at else "",
        })
    
    return {
        "total": len(items),
        "items": items
    }


@router.get("/api/alert/statistics")
def api_alert_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = db.query(AlertRecord).filter(AlertRecord.tenant_id == current_user.tenant_id)
    
    total = base_query.count()
    
    pending = base_query.filter(AlertRecord.status == "pending").count()
    processing = base_query.filter(AlertRecord.status == "processing").count()
    resolved = base_query.filter(AlertRecord.status == "resolved").count()
    merged = base_query.filter(AlertRecord.status == MERGED_STATUS).count()
    escalated = base_query.filter(AlertRecord.escalated == True).count()  # noqa: E712 - SQLAlchemy 需要显式比较
    
    critical = base_query.filter(AlertRecord.severity == "critical").count()
    high = base_query.filter(AlertRecord.severity == "high").count()
    medium = base_query.filter(AlertRecord.severity == "medium").count()
    low = base_query.filter(AlertRecord.severity == "low").count()
    
    today = datetime.utcnow().date()
    todayCount = base_query.filter(
        cast(AlertRecord.created_at, Date) == today
    ).count()
    
    week_start = today - timedelta(days=today.weekday())
    thisWeek = base_query.filter(
        cast(AlertRecord.created_at, Date) >= week_start
    ).count()
    
    by_type_result = db.query(
        AlertRecord.alert_type, func.count(AlertRecord.id)
    ).filter(
        AlertRecord.tenant_id == current_user.tenant_id
    ).group_by(AlertRecord.alert_type).all()
    
    byType = [{"type": row[0], "count": row[1]} for row in by_type_result]
    
    trend = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        count = base_query.filter(
            cast(AlertRecord.created_at, Date) == date
        ).count()
        trend.append({
            "date": date.strftime("%Y-%m-%d"),
            "count": count
        })
    
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "resolved": resolved,
        "merged": merged,
        "escalated": escalated,
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "todayCount": todayCount,
        "thisWeek": thisWeek,
        "byType": byType,
        "trend": trend,
    }


@router.get("/api/alerts/{alert_id:int}")
def api_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(AlertRecord).filter(
        AlertRecord.id == alert_id,
        AlertRecord.tenant_id == current_user.tenant_id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    agent_analysis = {}
    if alert.agent_analysis:
        try:
            agent_analysis = json.loads(alert.agent_analysis)
        except Exception:
            agent_analysis = {}
    
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
        "agent_analysis": agent_analysis,
        "workorder_id": alert.workorder_id,
        "handled_by": alert.handled_by,
        "handled_at": alert.handled_at.isoformat() if alert.handled_at else "",
        "handle_result": alert.handle_result,
        "device_info": alert.device_info if alert.device_info else {},
        "telemetry_history": alert.telemetry_history if alert.telemetry_history else [],
        **alert_state_payload(alert),
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else "",
    }


@router.put("/api/alerts/{alert_id}/status")
def api_update_alert_status(
    alert_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(AlertRecord).filter(
        AlertRecord.id == alert_id,
        AlertRecord.tenant_id == current_user.tenant_id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    if alert.status == MERGED_STATUS:
        raise HTTPException(status_code=400, detail="该告警已合并到其他告警，请操作主告警")
    
    status = payload.get("status")
    if status not in ["pending", "processing", "resolved"]:
        raise HTTPException(status_code=400, detail="无效的状态值")
    
    alert.status = status
    alert.updated_at = datetime.utcnow()
    
    if status == "processing" and not alert.handled_by:
        alert.handled_by = current_user.id
    
    if status == "resolved":
        alert.handled_at = datetime.utcnow()
    
    db.commit()
    db.refresh(alert)
    
    return {"message": "状态更新成功", "status": alert.status}


@router.post("/api/alerts/{alert_id}/handle")
def api_handle_alert(
    alert_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(AlertRecord).filter(
        AlertRecord.id == alert_id,
        AlertRecord.tenant_id == current_user.tenant_id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    handle_result = payload.get("handle_result", "")
    status = payload.get("status", "resolved")
    
    if status not in ["processing", "resolved"]:
        raise HTTPException(status_code=400, detail="无效的状态值")
    
    alert.handle_result = handle_result
    alert.status = status
    alert.handled_by = current_user.id
    alert.handled_at = datetime.utcnow()
    alert.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(alert)
    
    return {
        "message": "处理成功",
        "id": alert.id,
        "status": alert.status,
        "handle_result": alert.handle_result,
        "handled_by": alert.handled_by,
        "handled_at": alert.handled_at.isoformat() if alert.handled_at else "",
    }


@router.post("/api/alerts/merge")
def api_merge_alerts(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """把多条同类告警合并到主告警，被合并告警累加重复次数并标记为 merged。"""
    primary_id = payload.get("primary_id")
    duplicate_ids = payload.get("duplicate_ids") or []
    if not primary_id or not duplicate_ids:
        raise HTTPException(status_code=400, detail="需要提供 primary_id 与 duplicate_ids")

    try:
        duplicated = [int(i) for i in duplicate_ids]
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="duplicate_ids 必须为告警ID列表")

    try:
        data = merge_alerts(db, current_user.tenant_id, int(primary_id), duplicated)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "合并成功", **data}


@router.post("/api/alerts/escalate-overdue")
def api_escalate_overdue(
    sla_minutes: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """把持续未闭环的告警批量升级，用于告警升级规则定时执行。"""
    return escalate_overdue_alerts(db, current_user.tenant_id, sla_minutes)


# ---------------- 批量巡检任务调度 API ----------------

@router.post("/api/batch-inspection/create")
def api_create_batch_inspection(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("batch:create")),
):
    from services.batch_inspection_service import create_batch_task
    return create_batch_task(db, payload, tenant_id=current_user.tenant_id, user=current_user)


@router.get("/api/batch-inspection/list")
def api_list_batch_inspections(
    status: str = "",
    building_id: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("batch:view")),
):
    from services.batch_inspection_service import list_batch_tasks
    return list_batch_tasks(
        db, tenant_id=current_user.tenant_id, status=status, building_id=building_id, limit=limit
    )


@router.get("/api/batch-inspection/{task_id}")
def api_get_batch_inspection(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("batch:view")),
):
    from services.batch_inspection_service import get_batch_task_detail
    return get_batch_task_detail(db, task_id, tenant_id=current_user.tenant_id)


@router.get("/api/batch-inspection/{task_id}/progress")
def api_batch_inspection_progress(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("batch:view")),
):
    from services.batch_inspection_service import get_batch_task_progress
    return get_batch_task_progress(db, task_id, tenant_id=current_user.tenant_id)


# ---------------- 统计报表导出 API ----------------
