from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import Dict, Any, List, Optional

from database import get_db, AlertRecord, FaultTicket, User
from services.auth_service import (
    get_current_tenant_id,
    get_current_user,
    require_permission,
)
from services.record_persistence_service import (
    list_workorders,
    get_workorder,
    update_workorder_status,
    submit_workorder_review,
    update_workorder_evidence,
)
from services.workorder_service import (
    generate_workorders_from_inspection,
    get_workorder_dashboard,
    simulate_workorder_flow,
)
from services.alert_lifecycle_service import MERGED_STATUS, RESOLVED_STATUS

router = APIRouter(dependencies=[Depends(get_current_user)])

# 整改/复查闭环状态机
RECTIFY_ALLOWED_STATUSES = ("待受理", "处理中")
REVIEW_ALLOWED_STATUSES = ("待复查",)


@router.get("/api/faults")
def list_faults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == current_user.tenant_id
    ).order_by(FaultTicket.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "record_id": f.record_id,
            "device_id": f.device_id,
            "title": f.title,
            "description": f.description,
            "risk_level": f.risk_level,
            "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else "",
            "updated_at": f.updated_at.isoformat() if f.updated_at else "",
        }
        for f in rows
    ]


@router.put("/api/faults/{fault_id}/status")
def update_fault_status(
    fault_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    f = db.query(FaultTicket).filter(
        FaultTicket.id == fault_id,
        FaultTicket.tenant_id == current_user.tenant_id
    ).first()
    if not f:
        return JSONResponse(status_code=404, content={"message": "工单不存在"})
    f.status = status
    f.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "updated"}


@router.get("/api/workorders/dashboard")
def api_workorder_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == current_user.tenant_id
    )
    
    total = base_query.count()
    pending = base_query.filter(FaultTicket.status == "待受理").count()
    processing = base_query.filter(FaultTicket.status == "处理中").count()
    review = base_query.filter(FaultTicket.status == "待复查").count()
    completed = base_query.filter(FaultTicket.status == "已完成").count()
    closed = base_query.filter(FaultTicket.status == "已关闭").count()
    
    by_priority_result = db.query(
        FaultTicket.priority, func.count(FaultTicket.id)
    ).filter(
        FaultTicket.tenant_id == current_user.tenant_id
    ).group_by(FaultTicket.priority).all()
    
    byPriority = [{"priority": row[0], "count": row[1]} for row in by_priority_result]
    
    by_type_result = db.query(
        FaultTicket.ticket_type, func.count(FaultTicket.id)
    ).filter(
        FaultTicket.tenant_id == current_user.tenant_id,
        FaultTicket.ticket_type != ""
    ).group_by(FaultTicket.ticket_type).all()
    
    byType = [{"type": row[0], "count": row[1]} for row in by_type_result]
    
    completionRate = 0.0
    if total > 0:
        completionRate = round((completed + closed) / total * 100, 1)
    
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "review": review,
        "completed": completed,
        "closed": closed,
        "byPriority": byPriority,
        "byType": byType,
        "completionRate": completionRate,
    }


# ---------------- 整改工单（运行库 work_orders） ----------------
# 系统里有两套工单，不要混：
#   - 故障工单：主库 fault_tickets（FaultTicket），由告警/故障/移动端产生，
#     状态 待受理 → 处理中 → 待复查 → 已完成 → 已关闭，走上面 /api/workorders/*
#   - 整改工单：运行库 work_orders（record_persistence_service），由巡检页与巡检档案产生
#     （POST /api/workorders/generate、POST /api/records/save-inspection 写入），
#     状态 待派单 → 整改中 → 待复查 → 已闭环，走下面 /api/workorders/rectification/*
#
# Web「整改工单」页（frontend/src/views/WorkOrders.vue）读的是整改工单这一套
# （含 hazard / responsible_role / recommended_action / timeline 与整改前后证据链）。
# 下面这些静态路径必须声明在 /api/workorders/{order_id} 之前，否则会被它按路径参数吃掉。

# 整改工单状态机（与 record_persistence_service / workorder_service 一致）
RECTIFICATION_STATUSES = ("待派单", "整改中", "待复查", "已闭环")


@router.get("/api/workorders/rectification")
def api_list_rectification_orders(
    status: str = "",
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """整改工单列表（运行库）。status 为空表示全部。"""
    return list_workorders(status=status, limit=limit, tenant_id=tenant_id)


@router.get("/api/workorders/rectification/dashboard")
def api_rectification_dashboard(
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """整改工单看板：待派单 / 整改中 / 待复查 / 已闭环 + 闭环率。"""
    return get_workorder_dashboard(tenant_id=tenant_id)


@router.get("/api/workorders/rectification/{order_id}")
def api_get_rectification_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    order = get_workorder(order_id, tenant_id=tenant_id)
    if not order:
        return JSONResponse(status_code=404, content={"message": "整改工单不存在"})
    return order


@router.post("/api/workorders/rectification/{order_id}/status")
def api_update_rectification_status(
    order_id: str,
    payload: Dict[str, Any],
    current_user: User = Depends(require_permission("workorders:update")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """推进整改工单状态。取值必须是整改工单状态机里的值，否则直接拒绝，
    避免再写进一个谁都不认的中间状态。"""
    status = payload.get("status", "")
    if status not in RECTIFICATION_STATUSES:
        return JSONResponse(
            status_code=400,
            content={"message": f"无效的状态值，有效值为: {', '.join(RECTIFICATION_STATUSES)}"},
        )
    order = update_workorder_status(
        order_id,
        status=status,
        operator=payload.get("operator") or current_user.real_name or current_user.username,
        note=payload.get("note", ""),
        tenant_id=tenant_id,
    )
    if not order:
        return JSONResponse(status_code=404, content={"message": "整改工单不存在"})
    return order


@router.post("/api/workorders/generate")
def api_generate_workorders(
    payload: Dict[str, Any],
    current_user: User = Depends(require_permission("workorders:create")),
):
    return generate_workorders_from_inspection(payload)


@router.post("/api/workorders/simulate-flow")
def api_simulate_workorder_flow(
    payload: Dict[str, Any],
    current_user: User = Depends(require_permission("workorders:update")),
):
    return simulate_workorder_flow(payload)


@router.get("/api/workorders")
def api_list_workorders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    building_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == current_user.tenant_id
    )
    
    if status:
        query = query.filter(FaultTicket.status == status)
    
    if priority:
        query = query.filter(FaultTicket.priority == priority)
    
    if assignee_id is not None:
        query = query.filter(FaultTicket.assignee_id == assignee_id)
    
    if building_id is not None:
        query = query.filter(FaultTicket.building_id == building_id)
    
    total = query.count()
    
    query = query.order_by(FaultTicket.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    tickets = query.all()
    
    items = []
    for ticket in tickets:
        items.append({
            "id": ticket.id,
            "record_id": ticket.record_id,
            "device_id": ticket.device_id,
            "building_id": ticket.building_id,
            "building_name": ticket.building_name,
            "title": ticket.title,
            "description": ticket.description,
            "risk_level": ticket.risk_level,
            "priority": ticket.priority,
            "ticket_type": ticket.ticket_type,
            "status": ticket.status,
            "source": ticket.source or "",
            "assignee_id": ticket.assignee_id,
            "assignee_name": ticket.assignee_name,
            "reporter_id": ticket.reporter_id,
            "reporter_name": ticket.reporter_name,
            "location": ticket.location,
            "deadline": ticket.deadline.isoformat() if ticket.deadline else "",
            "review_result": ticket.review_result or "",
            "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
        })
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/api/workorders/{order_id}")
def api_get_workorder(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == order_id,
        FaultTicket.tenant_id == current_user.tenant_id
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    source_alert = db.query(AlertRecord).filter(
        AlertRecord.workorder_id == ticket.id,
        AlertRecord.tenant_id == current_user.tenant_id,
    ).order_by(AlertRecord.created_at.desc()).first()

    return {
        "id": ticket.id,
        "record_id": ticket.record_id,
        "device_id": ticket.device_id,
        "building_id": ticket.building_id,
        "building_name": ticket.building_name,
        "title": ticket.title,
        "description": ticket.description,
        "risk_level": ticket.risk_level,
        "priority": ticket.priority,
        "ticket_type": ticket.ticket_type,
        "status": ticket.status,
        "source": ticket.source or "",
        "assignee_id": ticket.assignee_id,
        "assignee_name": ticket.assignee_name,
        "reporter_id": ticket.reporter_id,
        "reporter_name": ticket.reporter_name,
        "location": ticket.location,
        "deadline": ticket.deadline.isoformat() if ticket.deadline else "",
        "handle_result": ticket.handle_result,
        "review_result": ticket.review_result or "",
        "review_note": ticket.review_note or "",
        "reviewed_by": ticket.reviewed_by,
        "reviewed_at": ticket.reviewed_at.isoformat() if ticket.reviewed_at else "",
        "source_alert": {
            "id": source_alert.id,
            "alert_code": source_alert.alert_code,
            "alert_type": source_alert.alert_type,
            "severity": source_alert.severity,
            "repeat_count": source_alert.repeat_count or 1,
            "escalated": bool(source_alert.escalated),
        } if source_alert else None,
        "remark": ticket.remark,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
    }


@router.post("/api/workorders")
def api_create_workorder(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:create")),
):
    ticket = FaultTicket(
        tenant_id=current_user.tenant_id,
        record_id=payload.get("record_id"),
        device_id=payload.get("device_id"),
        building_id=payload.get("building_id"),
        building_name=payload.get("building_name", ""),
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        risk_level=payload.get("risk_level", ""),
        priority=payload.get("priority", "medium"),
        ticket_type=payload.get("ticket_type", ""),
        status=payload.get("status", "待受理"),
        reporter_id=current_user.id,
        reporter_name=current_user.real_name or current_user.username,
        location=payload.get("location", ""),
        remark=payload.get("remark", ""),
    )
    
    deadline_str = payload.get("deadline")
    if deadline_str:
        try:
            ticket.deadline = datetime.fromisoformat(deadline_str)
        except (ValueError, TypeError):
            pass
    
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "创建成功",
        "id": ticket.id,
    }


@router.put("/api/workorders/{order_id}")
def api_update_workorder(
    order_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == order_id,
        FaultTicket.tenant_id == current_user.tenant_id
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if "title" in payload:
        ticket.title = payload["title"]
    if "description" in payload:
        ticket.description = payload["description"]
    if "risk_level" in payload:
        ticket.risk_level = payload["risk_level"]
    if "priority" in payload:
        ticket.priority = payload["priority"]
    if "ticket_type" in payload:
        ticket.ticket_type = payload["ticket_type"]
    if "building_id" in payload:
        ticket.building_id = payload["building_id"]
    if "building_name" in payload:
        ticket.building_name = payload["building_name"]
    if "location" in payload:
        ticket.location = payload["location"]
    if "device_id" in payload:
        ticket.device_id = payload["device_id"]
    if "record_id" in payload:
        ticket.record_id = payload["record_id"]
    if "handle_result" in payload:
        ticket.handle_result = payload["handle_result"]
    if "remark" in payload:
        ticket.remark = payload["remark"]
    
    if "deadline" in payload:
        deadline_str = payload["deadline"]
        if deadline_str:
            try:
                ticket.deadline = datetime.fromisoformat(deadline_str)
            except (ValueError, TypeError):
                pass
        else:
            ticket.deadline = None
    
    ticket.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "更新成功",
        "id": ticket.id,
    }


@router.post("/api/workorders/{order_id}/status")
def api_update_workorder_status(
    order_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == order_id,
        FaultTicket.tenant_id == current_user.tenant_id
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    status = payload.get("status", "")
    valid_statuses = ["待受理", "处理中", "待复查", "已完成", "已关闭"]
    
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效的状态值，有效值为: {', '.join(valid_statuses)}")
    
    ticket.status = status
    ticket.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "状态更新成功",
        "id": ticket.id,
        "status": ticket.status,
    }


@router.post("/api/workorders/{order_id}/assign")
def api_assign_workorder(
    order_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == order_id,
        FaultTicket.tenant_id == current_user.tenant_id
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    assignee_id = payload.get("assignee_id")
    assignee_name = payload.get("assignee_name", "")
    
    if assignee_id is None:
        raise HTTPException(status_code=400, detail="assignee_id 不能为空")
    
    assignee = db.query(User).filter(
        User.id == assignee_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if assignee and not assignee_name:
        assignee_name = assignee.real_name or assignee.username
    
    ticket.assignee_id = assignee_id
    ticket.assignee_name = assignee_name
    
    if ticket.status == "待受理":
        ticket.status = "处理中"
    
    ticket.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "分配成功",
        "id": ticket.id,
        "assignee_id": ticket.assignee_id,
        "assignee_name": ticket.assignee_name,
        "status": ticket.status,
    }


@router.get("/api/workorders/export")
def api_export_workorders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    building_id: Optional[int] = None,
    format: str = "csv",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == current_user.tenant_id
    )
    
    if status:
        query = query.filter(FaultTicket.status == status)
    
    if priority:
        query = query.filter(FaultTicket.priority == priority)
    
    if assignee_id is not None:
        query = query.filter(FaultTicket.assignee_id == assignee_id)
    
    if building_id is not None:
        query = query.filter(FaultTicket.building_id == building_id)
    
    query = query.order_by(FaultTicket.created_at.desc())
    tickets = query.all()
    
    if format == "json":
        items = []
        for ticket in tickets:
            items.append({
                "id": ticket.id,
                "title": ticket.title,
                "description": ticket.description,
                "risk_level": ticket.risk_level,
                "priority": ticket.priority,
                "ticket_type": ticket.ticket_type,
                "status": ticket.status,
                "assignee_name": ticket.assignee_name,
                "reporter_name": ticket.reporter_name,
                "building_name": ticket.building_name,
                "location": ticket.location,
                "deadline": ticket.deadline.isoformat() if ticket.deadline else "",
                "handle_result": ticket.handle_result,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
            })
        return {
            "total": len(items),
            "items": items,
        }
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "标题", "描述", "风险等级", "优先级", "类型", "状态",
        "处理人", "报告人", "建筑", "位置", "截止时间",
        "处理结果", "创建时间", "更新时间"
    ])
    
    for ticket in tickets:
        writer.writerow([
            ticket.id,
            ticket.title,
            ticket.description,
            ticket.risk_level,
            ticket.priority,
            ticket.ticket_type,
            ticket.status,
            ticket.assignee_name,
            ticket.reporter_name,
            ticket.building_name,
            ticket.location,
            ticket.deadline.strftime("%Y-%m-%d %H:%M:%S") if ticket.deadline else "",
            ticket.handle_result,
            ticket.created_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.created_at else "",
            ticket.updated_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.updated_at else "",
        ])
    
    output.seek(0)
    
    filename = f"workorders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/api/workorders/{order_id}/evidence")
def api_update_workorder_evidence(
    order_id: str,
    payload: Dict[str, Any],
    current_user: User = Depends(require_permission("workorders:update")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return update_workorder_evidence(
        order_id,
        before_images=payload.get("before_images"),
        after_images=payload.get("after_images"),
        review_images=payload.get("review_images"),
        review_note=payload.get("review_note", ""),
        operator=payload.get("operator", "安全管理员"),
        tenant_id=tenant_id,
    )


@router.post("/api/workorders/{order_id}/review")
def api_submit_workorder_review(
    order_id: str,
    payload: Dict[str, Any],
    current_user: User = Depends(require_permission("workorders:update")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = submit_workorder_review(
        order_id,
        reviewer=payload.get("reviewer", "安全管理员"),
        result=payload.get("result", "通过"),
        note=payload.get("note", ""),
        review_images=payload.get("review_images"),
        auto_close=bool(payload.get("auto_close", True)),
        tenant_id=tenant_id,
    )
    if not data:
        return JSONResponse(status_code=404, content={"message": "工单不存在"})
    return data


@router.post("/api/workorders/{ticket_id}/rectify")
def api_submit_rectification(
    ticket_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    """整改完成提交复查：待受理/处理中 → 待复查。"""
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == ticket_id,
        FaultTicket.tenant_id == current_user.tenant_id,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    if ticket.status not in RECTIFY_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态为 {ticket.status}，只有 {'/'.join(RECTIFY_ALLOWED_STATUSES)} 的工单可以提交整改",
        )

    ticket.handle_result = payload.get("handle_result", ticket.handle_result or "")
    ticket.status = "待复查"
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)

    return {
        "message": "已提交复查",
        "id": ticket.id,
        "status": ticket.status,
        "handle_result": ticket.handle_result,
    }


@router.post("/api/workorders/{ticket_id}/verify")
def api_verify_workorder(
    ticket_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
):
    """复查判定：待复查 → 已完成（通过）/ 处理中（退回整改）。

    复查通过时同步关闭来源告警，形成 告警 → 工单 → 整改 → 复查 闭环。
    """
    ticket = db.query(FaultTicket).filter(
        FaultTicket.id == ticket_id,
        FaultTicket.tenant_id == current_user.tenant_id,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    if ticket.status not in REVIEW_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态为 {ticket.status}，只有 {'/'.join(REVIEW_ALLOWED_STATUSES)} 的工单可以复查",
        )

    result = str(payload.get("result", "通过"))
    passed = result in ("通过", "复查通过", "已通过", "pass", "True", "true")
    now = datetime.utcnow()

    ticket.review_result = "通过" if passed else "不通过"
    ticket.review_note = payload.get("note", "")
    ticket.reviewed_by = current_user.id
    ticket.reviewed_at = now
    ticket.status = "已完成" if passed else "处理中"
    ticket.updated_at = now

    closed_alert = None
    if passed:
        alert = db.query(AlertRecord).filter(
            AlertRecord.workorder_id == ticket.id,
            AlertRecord.tenant_id == current_user.tenant_id,
            AlertRecord.status.notin_((MERGED_STATUS, RESOLVED_STATUS)),
        ).first()
        if alert:
            alert.status = RESOLVED_STATUS
            alert.handled_by = current_user.id
            alert.handled_at = now
            alert.handle_result = ticket.handle_result or ticket.review_note or "工单复查通过"
            alert.updated_at = now
            db.flush()
            closed_alert = {"id": alert.id, "alert_code": alert.alert_code, "status": alert.status}

    db.commit()
    db.refresh(ticket)

    return {
        "message": "复查通过，工单已完成" if passed else "复查未通过，工单已退回整改",
        "id": ticket.id,
        "status": ticket.status,
        "review_result": ticket.review_result,
        "review_note": ticket.review_note,
        "reviewed_at": ticket.reviewed_at.isoformat() if ticket.reviewed_at else "",
        "closed_alert": closed_alert,
    }
