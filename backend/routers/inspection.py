from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from database import InspectionRecord, get_db

from services.inspection_learning_recommend_service import recommend_learning_for_hazards
from services.agent_service import run_inspection_agent



from services.archive_report_service import (build_enhanced_report, get_archive_dashboard, get_archive_detail, list_archives, REPORT_TEMPLATES)
from services.business_crud_service import (get_inspection_record as crud_get_inspection, list_inspection_records as crud_list_inspections)
from services.record_persistence_service import (
    export_report_text,
    get_record_dashboard,
    get_inspection_record,
    list_inspection_records,
    save_inspection_record,
)
from services.workorder_service import build_inspection_report

from services.auth_service import get_current_tenant_id, get_current_user
from services.runtime_state import INSPECTION_TASK_CACHE

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["巡检管理"])

@router.post("/api/inspection/analyze")
async def analyze_inspection(
    task_id: Optional[int] = Form(None),
    device_id: Optional[int] = Form(None),
    location: str = Form(""),
    description: str = Form(""),
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    upload_file = file or image or image_file
    result = await run_inspection_agent(
        db, device_id, location, description, upload_file, tenant_id=tenant_id
    )
    return result


@router.get("/api/inspection/agent-steps")
def api_inspection_agent_steps():
    return {
        "version": "V1.0.0",
        "steps": [
            {"key": "task_understanding", "title": "任务理解", "description": "正在理解巡检任务、地点、文字描述和图片输入。"},
            {"key": "image_recognition", "title": "图像识别", "description": "正在识别图片中的消防设施与环境风险。"},
            {"key": "risk_extraction", "title": "风险提取", "description": "正在提取消防通道、设施遮挡、电气线路、可燃物等隐患。"},
            {"key": "rag_retrieval", "title": "RAG 检索", "description": "正在检索消防法规、巡检标准和整改知识库。"},
            {"key": "rule_check", "title": "规则校验", "description": "正在匹配消防安全规则并校验模型输出。"},
            {"key": "risk_scoring", "title": "风险评分", "description": "正在融合隐患数量、严重度和场景因素计算风险等级。"},
            {"key": "rectification_suggestion", "title": "整改建议", "description": "正在生成整改措施、责任角色和闭环复查要求。"},
            {"key": "report_generation", "title": "报告生成", "description": "正在生成巡检报告和可导出内容。"},
        ],
    }


@router.post("/api/inspection/tasks")
async def api_create_inspection_task(
    device_id: Optional[int] = Form(None),
    location: str = Form(""),
    description: str = Form(""),
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """V1.0.0 task-style interface.

    当前版本采用同步执行 + 前端动态进度展示；接口返回完整结果，并把结果缓存到内存，
    方便 /progress 和 /result 端点完成核心接口自检。
    """
    upload_file = file or image or image_file
    result = await run_inspection_agent(
        db, device_id, location, description, upload_file, tenant_id=tenant_id
    )
    task_id = f"task_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{result.get('record_id', 'local')}"
    result["task_id"] = task_id
    result["status"] = "completed"
    INSPECTION_TASK_CACHE[task_id] = {
        "tenant_id": tenant_id,
        "user_id": current_user.id,
        "result": result,
    }
    return {"task_id": task_id, "status": "completed", "result": result}


@router.get("/api/inspection/tasks/{task_id}/progress")
def api_inspection_task_progress(
    task_id: str,
    current_user=Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    cached = INSPECTION_TASK_CACHE.get(task_id)
    authorized = bool(
        cached
        and cached.get("tenant_id") == tenant_id
        and cached.get("user_id") == current_user.id
    )
    if cached and not authorized:
        return JSONResponse(status_code=404, content={"message": "任务不存在"})
    completed = authorized
    base_steps = api_inspection_agent_steps()["steps"]
    return {
        "task_id": task_id,
        "status": "completed" if completed else "running",
        "steps": [
            {**step, "status": "completed" if completed else ("running" if i == 0 else "waiting")}
            for i, step in enumerate(base_steps)
        ],
    }


@router.get("/api/inspection/tasks/{task_id}/result")
def api_inspection_task_result(
    task_id: str,
    current_user=Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    cached = INSPECTION_TASK_CACHE.get(task_id)
    if not cached or cached.get("tenant_id") != tenant_id or cached.get("user_id") != current_user.id:
        return JSONResponse(status_code=404, content={"message": "任务结果不存在或后端已重启"})
    return cached["result"]


@router.get("/api/records")
def list_records(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = db.query(InspectionRecord).filter(
        InspectionRecord.tenant_id == tenant_id
    ).order_by(InspectionRecord.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "device_code": r.device_code,
            "device_name": r.device_name,
            "location": r.location,
            "hazards": json.loads(r.hazards or "[]"),
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "used_vision_api": r.used_vision_api,
            "model_provider": r.model_provider,
            "model_name": r.model_name,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


@router.get("/api/records/{record_id}")
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    r = db.query(InspectionRecord).filter(
        InspectionRecord.id == record_id,
        InspectionRecord.tenant_id == tenant_id,
    ).first()
    if not r:
        return JSONResponse(status_code=404, content={"message": "记录不存在"})
    return {
        "id": r.id,
        "device_id": r.device_id,
        "device_code": r.device_code,
        "device_name": r.device_name,
        "location": r.location,
        "description": r.description,
        "image_path": r.image_path,
        "hazards": json.loads(r.hazards or "[]"),
        "risk_score": r.risk_score,
        "risk_level": r.risk_level,
        "suggestion": r.suggestion,
        "report": r.report,
        "agent_steps": json.loads(r.agent_steps or "[]"),
        "used_vision_api": r.used_vision_api,
        "used_text_model_api": r.used_text_model_api,
        "model_provider": r.model_provider,
        "model_name": r.model_name,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


@router.get("/api/inspection/demo-cases")
def inspection_demo_cases():
    return [
        {
            "name": "实验室综合高风险",
            "location": "实验室A区",
            "description": "实验室A区消防通道被杂物堵塞，插排串联，旁边堆放纸箱，配电箱周围有杂物，电线较为杂乱。"
        },
        {
            "name": "电动车违规充电",
            "location": "宿舍楼一层楼道",
            "description": "楼道内停放电动车并通过飞线充电，旁边堆放纸箱，疏散通道被占用。"
        },
        {
            "name": "设施遮挡与灭火器问题",
            "location": "教学楼B区二楼",
            "description": "消火栓被杂物遮挡，灭火器前堆放物品，部分灭火器疑似缺失。"
        },
        {
            "name": "疑似初期火情",
            "location": "机房C区",
            "description": "机房配电箱附近有焦糊味和少量烟雾，线路杂乱，周围堆放塑料包装。"
        }
    ]


@router.get("/api/records/{record_id}/report-text")
def download_record_report(
    record_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    r = db.query(InspectionRecord).filter(
        InspectionRecord.id == record_id,
        InspectionRecord.tenant_id == tenant_id,
    ).first()
    if not r:
        return JSONResponse(status_code=404, content={"message": "记录不存在"})
    filename = f"fire_inspection_report_{record_id}.txt"
    return Response(
        content=r.report or "",
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/api/inspection/learning-recommendations")
def api_inspection_learning_recommendations(payload: Dict[str, Any]):
    hazards = payload.get("hazards", [])
    return recommend_learning_for_hazards(hazards)



@router.post("/api/reports/inspection")
def api_build_inspection_report(payload: Dict[str, Any]):
    return build_inspection_report(payload)



@router.post("/api/records/save-inspection")
def api_save_inspection_record(
    payload: Dict[str, Any],
    tenant_id: int = Depends(get_current_tenant_id),
):
    return save_inspection_record(payload, tenant_id=tenant_id)


@router.get("/api/records/inspections")
def api_list_inspection_records(
    limit: int = 100,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return list_inspection_records(limit, tenant_id=tenant_id)


@router.get("/api/records/inspections/{record_id}")
def api_get_inspection_record(
    record_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return get_inspection_record(record_id, tenant_id=tenant_id)


@router.get("/api/records/dashboard")
def api_get_record_dashboard(tenant_id: int = Depends(get_current_tenant_id)):
    return get_record_dashboard(tenant_id=tenant_id)


@router.get("/api/reports/export-text/{record_id}")
def api_export_report_text(
    record_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return export_report_text(record_id, tenant_id=tenant_id)


# ---------------- V1.0.0 Report and Archive enhancement ----------------

@router.get("/api/reports/templates")
def api_report_templates():
    return {"templates": REPORT_TEMPLATES}


@router.get("/api/inspection-archives/dashboard")
def api_inspection_archive_dashboard(tenant_id: int = Depends(get_current_tenant_id)):
    return get_archive_dashboard(tenant_id=tenant_id)


@router.get("/api/inspection-archives")
def api_inspection_archives(
    keyword: str = "",
    risk_level: str = "",
    review_status: str = "",
    archive_status: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 200,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return list_archives(
        keyword=keyword,
        risk_level=risk_level,
        review_status=review_status,
        archive_status=archive_status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        tenant_id=tenant_id,
    )


@router.get("/api/inspection-archives/{record_id}")
def api_inspection_archive_detail(
    record_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = get_archive_detail(record_id, tenant_id=tenant_id)
    if not data:
        return JSONResponse(status_code=404, content={"message": "巡检档案不存在"})
    return data


@router.get("/api/reports/enhanced/{record_id}")
def api_enhanced_report(
    record_id: str,
    template: str = "standard",
    format: str = "markdown",
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = build_enhanced_report(
        record_id, template=template, fmt=format, tenant_id=tenant_id
    )
    if not data.get("content"):
        return JSONResponse(status_code=404, content={"message": "报告不存在"})
    return data


@router.get("/api/reports/enhanced-html/{record_id}")
def api_enhanced_report_html(
    record_id: str,
    template: str = "standard",
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = build_enhanced_report(
        record_id, template=template, fmt="html", tenant_id=tenant_id
    )
    if not data.get("content"):
        return JSONResponse(status_code=404, content={"message": "报告不存在"})
    return Response(content=data["content"], media_type="text/html; charset=utf-8")


@router.get("/api/archives/inspection")
def api_archives_compat(
    keyword: str = "",
    risk_level: str = "",
    review_status: str = "",
    archive_status: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 200,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return list_archives(
        keyword,
        risk_level,
        review_status,
        archive_status,
        start_date,
        end_date,
        limit,
        tenant_id=tenant_id,
    )


@router.get("/api/archives/inspection/{record_id}")
def api_archives_detail_compat(
    record_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return api_inspection_archive_detail(record_id, tenant_id=tenant_id)


RAG_CATEGORIES_V121 = ["消防法规", "消防设施", "疏散通道", "电气火灾", "仓储安全", "应急处置", "巡检标准", "处罚依据", "电动车安全", "可燃物管理"]


@router.get("/api/inspection-records")
def api_v118_inspection_records(
    limit: int = 100,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return list_inspection_records(limit, tenant_id=tenant_id)


@router.get("/api/inspection-records-dashboard")
def api_v118_inspection_records_dashboard(
    tenant_id: int = Depends(get_current_tenant_id),
):
    return get_record_dashboard(tenant_id=tenant_id)


@router.get("/api/inspection-records/{record_id}")
def api_v118_inspection_record_detail(
    record_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return get_inspection_record(record_id, tenant_id=tenant_id)


@router.get("/api/inspection-report-text/{record_id}")
def api_v118_inspection_report_text(
    record_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
):
    return export_report_text(record_id, tenant_id=tenant_id)



