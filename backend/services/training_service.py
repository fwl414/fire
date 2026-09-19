"""消防培训：培训计划 / 考试场次 / 培训档案

这三块数据此前只存在于前端写死的演示数组里（2024-01 的 6 个计划、4 场考试、8 条档案），
后端一张表都没有。本模块提供三张表的 CRUD，并统一处理三件容易做错的事：

1. **聚合值现算**：计划的"实际参训人数"、考试的"参考人数/平均分/及格率"都从培训档案
   （training_records）现算，不落冗余列——否则档案一改，统计值就和档案对不上。
2. **合格判定在后端**：以关联考试的及格线为准（没关联考试则用默认及格线），
   接口直接返回 `is_passed` 与 `result_label`；"还没考试"既不是合格也不是不合格。
3. **不给悬空引用**：档案引用计划/考试时会校验同租户存在；计划/考试下还有档案时不允许删除。
"""
from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import TrainingExam, TrainingPlan, TrainingRecord

# 状态枚举与界面文案：与告警模块一样，全系统同一份，接口直接返回 label 供前端展示
PLAN_STATUS_LABELS = {"pending": "未开始", "ongoing": "进行中", "completed": "已完成"}
EXAM_STATUS_LABELS = {"pending": "未开始", "ongoing": "进行中", "ended": "已结束"}

# 培训计划类型（前端下拉与后端校验共用一份，避免两边枚举漂移）
PLAN_TYPES = ["综合培训", "入职培训", "专项培训", "技能培训", "演练培训"]

DEFAULT_PASS_SCORE = 60
MAX_PAGE_SIZE = 100


# ========== 通用工具 ==========

def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """转整数；空值返回 default；转不动返回 None（调用方据此报错）。"""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any, label: str) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label}格式应为 YYYY-MM-DD：{text}") from exc


def _parse_datetime(value: Any, label: str) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label}格式应为 YYYY-MM-DD HH:MM:SS：{text}") from exc


def _page_bounds(page: Any, page_size: Any) -> Tuple[int, int, int]:
    page_no = max(1, _coerce_int(page, 1) or 1)
    size = min(MAX_PAGE_SIZE, max(1, _coerce_int(page_size, 20) or 20))
    return page_no, size, (page_no - 1) * size


def _tenant_record(db: Session, model, record_id: int, tenant_id: int):
    return db.query(model).filter(model.id == record_id, model.tenant_id == tenant_id).first()


def _resolve_ref(db: Session, tenant_id: int, model, ref_id: Any, label: str):
    """校验被引用记录属于同一租户。返回 (id, error_message)。"""
    if ref_id is None or ref_id == "":
        return None, None
    rid = _coerce_int(ref_id)
    if rid is None:
        return None, f"{label}必须是数字"
    if not _tenant_record(db, model, rid, tenant_id):
        return None, f"{label}不存在"
    return rid, None


def _text(value: Any) -> str:
    return str(value or "").strip()


# ========== 聚合 ==========

def _plan_actual_counts(db: Session, tenant_id: int) -> Dict[int, int]:
    """按 plan_id 统计实际参训人数（档案条数）。"""
    rows = (
        db.query(TrainingRecord.plan_id, func.count(TrainingRecord.id))
        .filter(TrainingRecord.tenant_id == tenant_id, TrainingRecord.plan_id.isnot(None))
        .group_by(TrainingRecord.plan_id)
        .all()
    )
    return {plan_id: int(count) for plan_id, count in rows}


def _pass_score_map(db: Session, tenant_id: int) -> Dict[int, int]:
    rows = db.query(TrainingExam.id, TrainingExam.pass_score).filter(
        TrainingExam.tenant_id == tenant_id
    ).all()
    return {
        exam_id: (int(score) if score is not None else DEFAULT_PASS_SCORE)
        for exam_id, score in rows
    }


def _exam_stats_map(db: Session, tenant_id: int) -> Dict[int, Dict[str, Any]]:
    """按 exam_id 聚合参考人数、平均分、及格率。

    只统计**已有成绩**的档案：`exam_score` 为 null 表示还没考，
    算进"参考人数"会让及格率被稀释。
    """
    pass_scores = _pass_score_map(db, tenant_id)
    rows = (
        db.query(TrainingRecord.exam_id, TrainingRecord.exam_score)
        .filter(
            TrainingRecord.tenant_id == tenant_id,
            TrainingRecord.exam_id.isnot(None),
            TrainingRecord.exam_score.isnot(None),
        )
        .all()
    )
    grouped: Dict[int, List[float]] = {}
    for exam_id, score in rows:
        grouped.setdefault(exam_id, []).append(float(score))

    stats: Dict[int, Dict[str, Any]] = {}
    for exam_id, scores in grouped.items():
        line = pass_scores.get(exam_id, DEFAULT_PASS_SCORE)
        passed = sum(1 for s in scores if s >= line)
        stats[exam_id] = {
            "attend_count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 1),
            "pass_rate": round(passed / len(scores) * 100, 1),
        }
    return stats


# ========== 序列化 ==========

def serialize_plan(row: TrainingPlan, actual_count: int = 0) -> Dict[str, Any]:
    return {
        "id": row.id,
        "plan_name": row.plan_name or "",
        "plan_type": row.plan_type or "",
        "target": row.target or "",
        "trainer": row.trainer or "",
        "start_date": row.start_date.isoformat() if row.start_date else "",
        "end_date": row.end_date.isoformat() if row.end_date else "",
        "person_count": row.person_count or 0,
        # 计划人数来自录入，实际人数来自档案聚合，两个都给出便于对照
        "actual_count": actual_count,
        "progress": row.progress or 0,
        "status": row.status or "pending",
        "status_label": PLAN_STATUS_LABELS.get(row.status, row.status or ""),
        "remark": row.remark or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def serialize_exam(row: TrainingExam, stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stats = stats or {}
    return {
        "id": row.id,
        "title": row.title or "",
        "description": row.description or "",
        "duration_minutes": row.duration_minutes or 0,
        "question_count": row.question_count or 0,
        "pass_score": row.pass_score if row.pass_score is not None else DEFAULT_PASS_SCORE,
        "start_time": row.start_time.strftime("%Y-%m-%d %H:%M") if row.start_time else "",
        "status": row.status or "pending",
        "status_label": EXAM_STATUS_LABELS.get(row.status, row.status or ""),
        # 三个聚合值：还没有成绩时 avg_score / pass_rate 为 null，前端显示「--」
        "attend_count": stats.get("attend_count", 0),
        "avg_score": stats.get("avg_score"),
        "pass_rate": stats.get("pass_rate"),
    }


def serialize_record(
    row: TrainingRecord,
    *,
    plan_name: str = "",
    pass_score: int = DEFAULT_PASS_SCORE,
) -> Dict[str, Any]:
    score = row.exam_score
    is_passed = None if score is None else float(score) >= pass_score
    return {
        "id": row.id,
        "trainee_name": row.trainee_name or "",
        "department": row.department or "",
        "plan_id": row.plan_id,
        "plan_name": plan_name,
        "course_name": row.course_name or "",
        "train_date": row.train_date.isoformat() if row.train_date else "",
        "study_hours": float(row.study_hours) if row.study_hours is not None else 0.0,
        "exam_id": row.exam_id,
        "exam_score": score,
        "pass_score": pass_score,
        "is_passed": is_passed,
        "result_label": "未考试" if is_passed is None else ("合格" if is_passed else "不合格"),
        "cert_no": row.cert_no or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _plan_name_map(db: Session, tenant_id: int) -> Dict[int, str]:
    rows = db.query(TrainingPlan.id, TrainingPlan.plan_name).filter(
        TrainingPlan.tenant_id == tenant_id
    ).all()
    return {plan_id: name for plan_id, name in rows}


# ========== 培训计划 ==========

def list_plans(
    db: Session,
    tenant_id: int,
    *,
    keyword: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    query = db.query(TrainingPlan).filter(TrainingPlan.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            TrainingPlan.plan_name.like(like)
            | TrainingPlan.trainer.like(like)
            | TrainingPlan.target.like(like)
        )
    if status:
        query = query.filter(TrainingPlan.status == status)

    total = query.count()
    page_no, size, offset = _page_bounds(page, page_size)
    rows = query.order_by(TrainingPlan.id.desc()).offset(offset).limit(size).all()
    actual = _plan_actual_counts(db, tenant_id)
    return {
        "total": total,
        "page": page_no,
        "page_size": size,
        "total_pages": math.ceil(total / size) if total else 0,
        "items": [serialize_plan(row, actual.get(row.id, 0)) for row in rows],
    }


def _validate_plan_payload(data: Dict[str, Any], *, require_name: bool) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """校验并归一化计划入参。返回 (字段字典, 错误信息)。"""
    fields: Dict[str, Any] = {}

    if require_name or "plan_name" in data:
        name = _text(data.get("plan_name"))
        if not name:
            return None, "计划名称不能为空"
        fields["plan_name"] = name

    if "status" in data or require_name:
        status = _text(data.get("status")) or "pending"
        if status not in PLAN_STATUS_LABELS:
            return None, f"计划状态只能是：{' / '.join(PLAN_STATUS_LABELS)}"
        fields["status"] = status

    if "progress" in data or require_name:
        progress = _coerce_int(data.get("progress"), 0)
        if progress is None or not 0 <= progress <= 100:
            return None, "进度必须在 0 ~ 100 之间"
        fields["progress"] = progress

    if "person_count" in data or require_name:
        count = _coerce_int(data.get("person_count"), 0)
        if count is None or count < 0:
            return None, "计划人数不能为负数"
        fields["person_count"] = count

    for key, label in (("start_date", "开始日期"), ("end_date", "结束日期")):
        if key in data or require_name:
            try:
                fields[key] = _parse_date(data.get(key), label)
            except ValueError as exc:
                return None, str(exc)

    start = fields.get("start_date")
    end = fields.get("end_date")
    if start and end and end < start:
        return None, "结束日期不能早于开始日期"

    if "plan_type" in data or require_name:
        plan_type = _text(data.get("plan_type")) or "综合培训"
        if plan_type not in PLAN_TYPES:
            return None, f"培训类型只能是：{' / '.join(PLAN_TYPES)}"
        fields["plan_type"] = plan_type

    for key in ("target", "trainer", "remark"):
        if key in data or require_name:
            fields[key] = _text(data.get(key))

    return fields, None


def create_plan(db: Session, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    fields, error = _validate_plan_payload(data or {}, require_name=True)
    if error:
        return {"ok": False, "message": error}
    row = TrainingPlan(tenant_id=tenant_id, **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "message": "培训计划已创建", "id": row.id, "item": serialize_plan(row, 0)}


def update_plan(db: Session, tenant_id: int, plan_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    row = _tenant_record(db, TrainingPlan, plan_id, tenant_id)
    if not row:
        return {"ok": False, "message": "培训计划不存在"}
    fields, error = _validate_plan_payload(data or {}, require_name=False)
    if error:
        return {"ok": False, "message": error}
    if not fields:
        return {"ok": False, "message": "没有需要更新的字段"}

    # 只传了 end_date 时也要拦住"结束早于开始"，所以用合并后的值判断
    merged_start = fields.get("start_date", row.start_date)
    merged_end = fields.get("end_date", row.end_date)
    if merged_start and merged_end and merged_end < merged_start:
        return {"ok": False, "message": "结束日期不能早于开始日期"}

    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return {"ok": True, "message": "培训计划已更新", "item": serialize_plan(row)}


def delete_plan(db: Session, tenant_id: int, plan_id: int) -> Dict[str, Any]:
    row = _tenant_record(db, TrainingPlan, plan_id, tenant_id)
    if not row:
        return {"ok": False, "message": "培训计划不存在"}
    used = (
        db.query(TrainingRecord)
        .filter(TrainingRecord.tenant_id == tenant_id, TrainingRecord.plan_id == plan_id)
        .count()
    )
    if used:
        return {"ok": False, "message": f"该计划下还有 {used} 条培训档案，请先调整档案再删除"}
    db.delete(row)
    db.commit()
    return {"ok": True, "message": "培训计划已删除"}


# ========== 考试场次 ==========

def list_exams(
    db: Session,
    tenant_id: int,
    *,
    keyword: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    query = db.query(TrainingExam).filter(TrainingExam.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(TrainingExam.title.like(like) | TrainingExam.description.like(like))
    if status:
        query = query.filter(TrainingExam.status == status)

    total = query.count()
    page_no, size, offset = _page_bounds(page, page_size)
    rows = query.order_by(TrainingExam.id.desc()).offset(offset).limit(size).all()
    stats = _exam_stats_map(db, tenant_id)
    return {
        "total": total,
        "page": page_no,
        "page_size": size,
        "total_pages": math.ceil(total / size) if total else 0,
        "items": [serialize_exam(row, stats.get(row.id)) for row in rows],
    }


def _validate_exam_payload(data: Dict[str, Any], *, require_title: bool) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    fields: Dict[str, Any] = {}

    if require_title or "title" in data:
        title = _text(data.get("title"))
        if not title:
            return None, "考试名称不能为空"
        fields["title"] = title

    if "status" in data or require_title:
        status = _text(data.get("status")) or "pending"
        if status not in EXAM_STATUS_LABELS:
            return None, f"考试状态只能是：{' / '.join(EXAM_STATUS_LABELS)}"
        fields["status"] = status

    for key, label, minimum in (
        ("duration_minutes", "考试时长", 1),
        ("question_count", "题目数量", 0),
        ("pass_score", "及格分", 0),
    ):
        if key in data or require_title:
            value = _coerce_int(data.get(key), 60 if key == "duration_minutes" else 0)
            if value is None or value < minimum:
                return None, f"{label}必须是不小于 {minimum} 的数字"
            fields[key] = value

    if "start_time" in data or require_title:
        try:
            fields["start_time"] = _parse_datetime(data.get("start_time"), "开始时间")
        except ValueError as exc:
            return None, str(exc)

    if "description" in data or require_title:
        fields["description"] = _text(data.get("description"))

    return fields, None


def create_exam(db: Session, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    fields, error = _validate_exam_payload(data or {}, require_title=True)
    if error:
        return {"ok": False, "message": error}
    row = TrainingExam(tenant_id=tenant_id, **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "message": "考试场次已创建", "id": row.id, "item": serialize_exam(row)}


def update_exam(db: Session, tenant_id: int, exam_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    row = _tenant_record(db, TrainingExam, exam_id, tenant_id)
    if not row:
        return {"ok": False, "message": "考试场次不存在"}
    fields, error = _validate_exam_payload(data or {}, require_title=False)
    if error:
        return {"ok": False, "message": error}
    if not fields:
        return {"ok": False, "message": "没有需要更新的字段"}
    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    stats = _exam_stats_map(db, tenant_id)
    return {"ok": True, "message": "考试场次已更新", "item": serialize_exam(row, stats.get(row.id))}


def delete_exam(db: Session, tenant_id: int, exam_id: int) -> Dict[str, Any]:
    row = _tenant_record(db, TrainingExam, exam_id, tenant_id)
    if not row:
        return {"ok": False, "message": "考试场次不存在"}
    used = (
        db.query(TrainingRecord)
        .filter(TrainingRecord.tenant_id == tenant_id, TrainingRecord.exam_id == exam_id)
        .count()
    )
    if used:
        return {"ok": False, "message": f"该场次下还有 {used} 条成绩记录，请先调整档案再删除"}
    db.delete(row)
    db.commit()
    return {"ok": True, "message": "考试场次已删除"}


# ========== 培训档案 ==========

def _record_query(
    db: Session,
    tenant_id: int,
    *,
    keyword: str = "",
    department: str = "",
    plan_id: Any = None,
    exam_id: Any = None,
    date_from: Any = None,
    date_to: Any = None,
):
    query = db.query(TrainingRecord).filter(TrainingRecord.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            TrainingRecord.trainee_name.like(like) | TrainingRecord.course_name.like(like)
        )
    if department:
        query = query.filter(TrainingRecord.department == department)
    if plan_id not in (None, ""):
        query = query.filter(TrainingRecord.plan_id == _coerce_int(plan_id))
    if exam_id not in (None, ""):
        query = query.filter(TrainingRecord.exam_id == _coerce_int(exam_id))
    # 日期区间是从前端传进来的字符串，非法值直接忽略而不是报错（筛选条件不该 500）
    try:
        start = _parse_date(date_from, "开始日期")
        end = _parse_date(date_to, "结束日期")
    except ValueError:
        start = end = None
    if start:
        query = query.filter(TrainingRecord.train_date >= start)
    if end:
        query = query.filter(TrainingRecord.train_date <= end)
    return query


def list_records(
    db: Session,
    tenant_id: int,
    *,
    keyword: str = "",
    department: str = "",
    plan_id: Any = None,
    exam_id: Any = None,
    date_from: Any = None,
    date_to: Any = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    query = _record_query(
        db, tenant_id, keyword=keyword, department=department,
        plan_id=plan_id, exam_id=exam_id, date_from=date_from, date_to=date_to,
    )
    total = query.count()
    page_no, size, offset = _page_bounds(page, page_size)
    rows = query.order_by(TrainingRecord.id.desc()).offset(offset).limit(size).all()

    plan_names = _plan_name_map(db, tenant_id)
    pass_scores = _pass_score_map(db, tenant_id)
    items = [
        serialize_record(
            row,
            plan_name=plan_names.get(row.plan_id, ""),
            pass_score=pass_scores.get(row.exam_id, DEFAULT_PASS_SCORE),
        )
        for row in rows
    ]
    return {
        "total": total,
        "page": page_no,
        "page_size": size,
        "total_pages": math.ceil(total / size) if total else 0,
        "items": items,
    }


def _validate_record_payload(
    db: Session,
    tenant_id: int,
    data: Dict[str, Any],
    *,
    require_name: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    fields: Dict[str, Any] = {}

    if require_name or "trainee_name" in data:
        name = _text(data.get("trainee_name"))
        if not name:
            return None, "参训人姓名不能为空"
        fields["trainee_name"] = name

    if "study_hours" in data or require_name:
        hours = _coerce_float(data.get("study_hours"), 0.0)
        if hours is None or hours < 0:
            return None, "学时不能为负数"
        fields["study_hours"] = hours

    if "exam_score" in data or require_name:
        raw = data.get("exam_score")
        # 空值表示"还没考试"，与 0 分区分开
        score = _coerce_float(raw, None) if raw not in (None, "") else None
        if raw not in (None, "") and (score is None or score < 0):
            return None, "考试成绩不能为负数"
        fields["exam_score"] = score

    if "train_date" in data or require_name:
        try:
            fields["train_date"] = _parse_date(data.get("train_date"), "培训日期")
        except ValueError as exc:
            return None, str(exc)

    for key, model, label in (("plan_id", TrainingPlan, "培训计划"), ("exam_id", TrainingExam, "考试场次")):
        if key in data or require_name:
            ref_id, ref_error = _resolve_ref(db, tenant_id, model, data.get(key), label)
            if ref_error:
                return None, ref_error
            fields[key] = ref_id

    for key in ("department", "course_name", "cert_no"):
        if key in data or require_name:
            fields[key] = _text(data.get(key))

    return fields, None


def create_record(db: Session, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    fields, error = _validate_record_payload(db, tenant_id, data or {}, require_name=True)
    if error:
        return {"ok": False, "message": error}
    row = TrainingRecord(tenant_id=tenant_id, **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    plan_names = _plan_name_map(db, tenant_id)
    pass_scores = _pass_score_map(db, tenant_id)
    return {
        "ok": True,
        "message": "培训档案已创建",
        "id": row.id,
        "item": serialize_record(
            row,
            plan_name=plan_names.get(row.plan_id, ""),
            pass_score=pass_scores.get(row.exam_id, DEFAULT_PASS_SCORE),
        ),
    }


def update_record(db: Session, tenant_id: int, record_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    row = _tenant_record(db, TrainingRecord, record_id, tenant_id)
    if not row:
        return {"ok": False, "message": "培训档案不存在"}
    fields, error = _validate_record_payload(db, tenant_id, data or {}, require_name=False)
    if error:
        return {"ok": False, "message": error}
    if not fields:
        return {"ok": False, "message": "没有需要更新的字段"}
    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    plan_names = _plan_name_map(db, tenant_id)
    pass_scores = _pass_score_map(db, tenant_id)
    return {
        "ok": True,
        "message": "培训档案已更新",
        "item": serialize_record(
            row,
            plan_name=plan_names.get(row.plan_id, ""),
            pass_score=pass_scores.get(row.exam_id, DEFAULT_PASS_SCORE),
        ),
    }


def delete_record(db: Session, tenant_id: int, record_id: int) -> Dict[str, Any]:
    row = _tenant_record(db, TrainingRecord, record_id, tenant_id)
    if not row:
        return {"ok": False, "message": "培训档案不存在"}
    db.delete(row)
    db.commit()
    return {"ok": True, "message": "培训档案已删除"}


# ========== 概览统计 ==========

def training_stats(db: Session, tenant_id: int) -> Dict[str, Any]:
    """概览卡片数据。

    及格率只在**已有成绩**的档案里算；一条成绩都没有时返回 None，
    页面显示「--」，而不是拿 0 去冒充一个通过率。
    """
    plan_count = db.query(TrainingPlan).filter(TrainingPlan.tenant_id == tenant_id).count()
    exam_count = db.query(TrainingExam).filter(TrainingExam.tenant_id == tenant_id).count()
    record_count = db.query(TrainingRecord).filter(TrainingRecord.tenant_id == tenant_id).count()
    trained_count = (
        db.query(func.count(func.distinct(TrainingRecord.trainee_name)))
        .filter(TrainingRecord.tenant_id == tenant_id)
        .scalar()
        or 0
    )

    pass_scores = _pass_score_map(db, tenant_id)
    scored = (
        db.query(TrainingRecord.exam_id, TrainingRecord.exam_score)
        .filter(TrainingRecord.tenant_id == tenant_id, TrainingRecord.exam_score.isnot(None))
        .all()
    )
    passed = sum(
        1
        for exam_id, score in scored
        if float(score) >= pass_scores.get(exam_id, DEFAULT_PASS_SCORE)
    )
    pass_rate = round(passed / len(scored) * 100, 1) if scored else None

    return {
        "plan_count": plan_count,
        "exam_count": exam_count,
        "record_count": record_count,
        "trained_count": int(trained_count),
        "scored_count": len(scored),
        "passed_count": passed,
        "pass_rate": pass_rate,
        "plan_status_labels": PLAN_STATUS_LABELS,
        "exam_status_labels": EXAM_STATUS_LABELS,
        "plan_types": PLAN_TYPES,
    }


# ========== 导出 ==========

CSV_HEADERS = ["姓名", "部门", "培训课程", "培训日期", "学时", "考试成绩", "是否合格", "证书编号"]


def export_records_csv(
    db: Session,
    tenant_id: int,
    *,
    keyword: str = "",
    department: str = "",
    plan_id: Any = None,
    exam_id: Any = None,
    date_from: Any = None,
    date_to: Any = None,
) -> str:
    """按当前筛选条件导出全部档案（不只是当前页）。

    开头加 UTF-8 BOM，否则 Excel 打开中文会乱码。
    """
    query = _record_query(
        db, tenant_id, keyword=keyword, department=department,
        plan_id=plan_id, exam_id=exam_id, date_from=date_from, date_to=date_to,
    )
    rows = query.order_by(TrainingRecord.train_date.desc(), TrainingRecord.id.desc()).all()

    plan_names = _plan_name_map(db, tenant_id)
    pass_scores = _pass_score_map(db, tenant_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for row in rows:
        item = serialize_record(
            row,
            plan_name=plan_names.get(row.plan_id, ""),
            pass_score=pass_scores.get(row.exam_id, DEFAULT_PASS_SCORE),
        )
        writer.writerow([
            item["trainee_name"],
            item["department"],
            item["course_name"] or item["plan_name"],
            item["train_date"],
            item["study_hours"],
            "" if item["exam_score"] is None else item["exam_score"],
            item["result_label"],
            item["cert_no"],
        ])
    return "\ufeff" + buffer.getvalue()


# ========== 初始种子 ==========

def seed_training_demo_data(db: Session, tenant_id: int) -> Dict[str, int]:
    """空表时种入一套**自洽**的培训初始数据（计划 → 考试 → 档案）。

    自洽很重要：考试的参考人数/平均分/及格率、计划的实际参训人数都由档案聚合而来，
    所以档案必须真实关联到计划与考试上，而不是各写各的。

    幂等：三张表里只要已有计划就不再种，避免重复启动或用户录入后被追加演示数据。
    """
    if db.query(TrainingPlan).filter(TrainingPlan.tenant_id == tenant_id).count():
        return {"created": 0}

    plan_specs = [
        {"key": "all_2026h1", "plan_name": "2026年上半年全员消防安全培训", "plan_type": "综合培训",
         "target": "全体员工", "trainer": "张教官", "start_date": date(2026, 3, 2),
         "end_date": date(2026, 3, 6), "person_count": 120, "progress": 100, "status": "completed"},
        {"key": "newbie_2026", "plan_name": "新员工入职消防培训", "plan_type": "入职培训",
         "target": "新入职员工", "trainer": "李教官", "start_date": date(2026, 4, 14),
         "end_date": date(2026, 4, 15), "person_count": 16, "progress": 100, "status": "completed"},
        {"key": "control_room_2026", "plan_name": "消防控制室值班员专项培训", "plan_type": "专项培训",
         "target": "控制室值班人员", "trainer": "王教官", "start_date": date(2026, 9, 21),
         "end_date": date(2026, 9, 25), "person_count": 8, "progress": 40, "status": "ongoing"},
        {"key": "drill_2026w", "plan_name": "2026年冬季消防疏散演练", "plan_type": "演练培训",
         "target": "全体员工", "trainer": "消防大队", "start_date": date(2026, 11, 10),
         "end_date": date(2026, 11, 11), "person_count": 150, "progress": 0, "status": "pending"},
    ]
    plan_rows: Dict[str, TrainingPlan] = {}
    for spec in plan_specs:
        fields = dict(spec)
        key = fields.pop("key")
        row = TrainingPlan(tenant_id=tenant_id, **fields)
        db.add(row)
        db.flush()
        plan_rows[key] = row

    exam_specs = [
        {"key": "h1_theory", "title": "2026年上半年消防安全知识考试",
         "description": "涵盖消防法规、防火知识、疏散逃生与消防器材使用",
         "duration_minutes": 60, "question_count": 50, "pass_score": 60,
         "start_time": datetime(2026, 3, 6, 9, 0), "status": "ended"},
        {"key": "newbie_test", "title": "新员工消防知识考核",
         "description": "新入职员工消防安全基础知识考核",
         "duration_minutes": 45, "question_count": 40, "pass_score": 60,
         "start_time": datetime(2026, 4, 15, 14, 0), "status": "ended"},
        {"key": "control_room_test", "title": "消防控制室值班员技能考核",
         "description": "消防控制室设备操作与应急处置流程考核",
         "duration_minutes": 90, "question_count": 60, "pass_score": 70,
         "start_time": datetime(2026, 9, 25, 9, 0), "status": "pending"},
    ]
    exam_rows: Dict[str, TrainingExam] = {}
    for spec in exam_specs:
        fields = dict(spec)
        key = fields.pop("key")
        row = TrainingExam(tenant_id=tenant_id, **fields)
        db.add(row)
        db.flush()
        exam_rows[key] = row

    # 特意覆盖三种情形：合格、不合格（低于及格线且没有证书）、尚未考试（成绩为 null）
    record_specs = [
        ("张建国", "安保部", "all_2026h1", date(2026, 3, 4), 8, "h1_theory", 92.0, "XF2026001"),
        ("李明华", "安保部", "all_2026h1", date(2026, 3, 4), 8, "h1_theory", 87.0, "XF2026002"),
        ("王志强", "技术部", "all_2026h1", date(2026, 3, 5), 8, "h1_theory", 55.0, ""),
        ("赵晓燕", "行政部", "all_2026h1", date(2026, 3, 5), 8, "h1_theory", 95.0, "XF2026003"),
        ("刘芳", "行政部", "newbie_2026", date(2026, 4, 15), 4, "newbie_test", 90.0, "XF2026004"),
        ("周明", "技术部", "newbie_2026", date(2026, 4, 15), 4, "newbie_test", 83.0, "XF2026005"),
        ("孙丽", "安保部", "control_room_2026", date(2026, 9, 23), 12, "control_room_test", None, ""),
        ("陈大伟", "后勤部", "control_room_2026", date(2026, 9, 23), 12, "control_room_test", None, ""),
    ]
    for name, dept, plan_key, train_date, hours, exam_key, score, cert in record_specs:
        plan = plan_rows[plan_key]
        db.add(TrainingRecord(
            tenant_id=tenant_id,
            trainee_name=name,
            department=dept,
            plan_id=plan.id,
            course_name=plan.plan_name,
            train_date=train_date,
            study_hours=hours,
            exam_id=exam_rows[exam_key].id,
            exam_score=score,
            cert_no=cert,
        ))

    db.commit()
    return {"created": len(plan_specs) + len(exam_specs) + len(record_specs)}
