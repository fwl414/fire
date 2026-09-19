"""消防培训：培训计划 / 考试场次 / 培训档案

这三块数据此前只存在于前端 `FireTraining.vue` 的写死数组里（2024-01 的 6 个计划、
4 场考试、8 条档案），后端一张表都没有。本路由补齐读写接口。

「培训课程」页签不在这里：课程内容由学习模块统一维护（`/api/learning/courses`），
本页只读展示，避免两处各存一份课程数据。

权限：读用 training:view，写用 training:manage。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from database import User, get_db
from schemas import (
    TrainingExamCreate,
    TrainingExamUpdate,
    TrainingPlanCreate,
    TrainingPlanUpdate,
    TrainingRecordCreate,
    TrainingRecordUpdate,
)
from services import learning_service, training_service
from services.auth_service import get_current_tenant_id, get_current_user, require_permission

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["消防培训"])


def _reject(result: dict) -> JSONResponse:
    """业务校验不通过：返回 400 + {ok:false, message}，由前端统一提示。"""
    return JSONResponse(status_code=400, content=result)


# ========== 概览 ==========

@router.get("/api/training/stats")
def api_training_stats(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:view")),
):
    stats = training_service.training_stats(db, tenant_id)
    # 课程数来自学习模块（课程数据只有那一份），不是培训表里的
    stats["course_count"] = len(learning_service.get_courses())
    return stats


# ========== 培训计划 ==========

@router.get("/api/training/plans")
def api_training_plan_list(
    keyword: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:view")),
):
    return training_service.list_plans(
        db, tenant_id, keyword=keyword, status=status, page=page, page_size=page_size
    )


@router.post("/api/training/plans")
def api_training_plan_create(
    payload: TrainingPlanCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.create_plan(db, tenant_id, payload.model_dump())
    if not result.get("ok"):
        return _reject(result)
    return result


@router.put("/api/training/plans/{plan_id}")
def api_training_plan_update(
    plan_id: int,
    payload: TrainingPlanUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.update_plan(
        db, tenant_id, plan_id, payload.model_dump(exclude_unset=True)
    )
    if not result.get("ok"):
        return _reject(result)
    return result


@router.delete("/api/training/plans/{plan_id}")
def api_training_plan_delete(
    plan_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.delete_plan(db, tenant_id, plan_id)
    if not result.get("ok"):
        return _reject(result)
    return result


# ========== 考试场次 ==========

@router.get("/api/training/exams")
def api_training_exam_list(
    keyword: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:view")),
):
    return training_service.list_exams(
        db, tenant_id, keyword=keyword, status=status, page=page, page_size=page_size
    )


@router.post("/api/training/exams")
def api_training_exam_create(
    payload: TrainingExamCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.create_exam(db, tenant_id, payload.model_dump())
    if not result.get("ok"):
        return _reject(result)
    return result


@router.put("/api/training/exams/{exam_id}")
def api_training_exam_update(
    exam_id: int,
    payload: TrainingExamUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.update_exam(
        db, tenant_id, exam_id, payload.model_dump(exclude_unset=True)
    )
    if not result.get("ok"):
        return _reject(result)
    return result


@router.delete("/api/training/exams/{exam_id}")
def api_training_exam_delete(
    exam_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.delete_exam(db, tenant_id, exam_id)
    if not result.get("ok"):
        return _reject(result)
    return result


# ========== 培训档案 ==========

@router.get("/api/training/records")
def api_training_record_list(
    keyword: str = Query(""),
    department: str = Query(""),
    plan_id: Optional[int] = Query(None),
    exam_id: Optional[int] = Query(None),
    date_from: str = Query(""),
    date_to: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:view")),
):
    return training_service.list_records(
        db,
        tenant_id,
        keyword=keyword,
        department=department,
        plan_id=plan_id,
        exam_id=exam_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/api/training/records/export")
def api_training_record_export(
    keyword: str = Query(""),
    department: str = Query(""),
    plan_id: Optional[int] = Query(None),
    exam_id: Optional[int] = Query(None),
    date_from: str = Query(""),
    date_to: str = Query(""),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:view")),
):
    """按当前筛选条件导出全部档案（不限于当前页），UTF-8 BOM 便于 Excel 直接打开。"""
    csv_text = training_service.export_records_csv(
        db,
        tenant_id,
        keyword=keyword,
        department=department,
        plan_id=plan_id,
        exam_id=exam_id,
        date_from=date_from,
        date_to=date_to,
    )
    filename = f"training-records-{datetime.utcnow():%Y%m%d%H%M%S}.csv"
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/training/records")
def api_training_record_create(
    payload: TrainingRecordCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.create_record(db, tenant_id, payload.model_dump())
    if not result.get("ok"):
        return _reject(result)
    return result


@router.put("/api/training/records/{record_id}")
def api_training_record_update(
    record_id: int,
    payload: TrainingRecordUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.update_record(
        db, tenant_id, record_id, payload.model_dump(exclude_unset=True)
    )
    if not result.get("ok"):
        return _reject(result)
    return result


@router.delete("/api/training/records/{record_id}")
def api_training_record_delete(
    record_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("training:manage")),
):
    result = training_service.delete_record(db, tenant_id, record_id)
    if not result.get("ok"):
        return _reject(result)
    return result
