"""
操作日志ORM服务
基于SQLAlchemy，将日志持久化到主数据库
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from database import OperationLog


def add_operation_log_orm(
    db: Session,
    user_id: Optional[int] = None,
    username: str = "",
    module: str = "",
    action: str = "",
    description: str = "",
    ip_address: str = "",
    user_agent: str = "",
    request_data: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    status: str = "success",
    error_message: str = "",
    duration_ms: int = 0,
    tenant_id: Optional[int] = None,
) -> OperationLog:
    """写入操作日志到主数据库（含哈希链）。"""
    from services.operation_log_service import SOURCE_HTTP, append_operation_log

    return append_operation_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        username=username,
        module=module,
        action=action,
        title=action,
        description=description,
        status=status,
        source=SOURCE_HTTP,
        ip_address=ip_address,
        user_agent=user_agent,
        request_data=request_data,
        response_data=response_data,
        error_message=error_message,
        duration_ms=duration_ms,
    )


def _tenant_filter(query, tenant_id: Optional[int]):
    """审计日志按租户隔离；未归属租户的历史日志一并可见，避免升级后旧日志消失。"""
    if tenant_id is None:
        return query
    return query.filter(
        (OperationLog.tenant_id == tenant_id) | (OperationLog.tenant_id.is_(None))
    )


def list_operation_logs_orm(
    db: Session,
    module: str = "",
    action: str = "",
    status: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    level: str = "",
    source: str = "",
    username: str = "",
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """分页查询操作日志（默认已按租户隔离）。"""
    query = _tenant_filter(db.query(OperationLog), tenant_id)

    if module:
        query = query.filter(OperationLog.module == module)
    if action:
        query = query.filter(OperationLog.action == action)
    if status:
        query = query.filter(OperationLog.status == status)
    if level:
        query = query.filter(OperationLog.level == level)
    if source:
        query = query.filter(OperationLog.source == source)
    if username:
        query = query.filter(OperationLog.username.like(f"%{username}%"))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (OperationLog.username.like(like)) |
            (OperationLog.description.like(like)) |
            (OperationLog.module.like(like)) |
            (OperationLog.action.like(like)) |
            (OperationLog.title.like(like)) |
            (OperationLog.target_id.like(like))
        )

    total = query.count()
    logs = (
        query.order_by(desc(OperationLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_log_to_dict(l) for l in logs],
    }


def get_operation_log_dashboard_orm(db: Session, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """操作日志页的汇总数据（默认已按租户隔离）。

    页面的指标卡同时覆盖「操作日志」与「登录日志」两个标签页，所以这里一并返回
    `today_login_users`，避免前端为此再发一次请求并自行聚合。
    """
    base = _tenant_filter(db.query(OperationLog), tenant_id)
    total = base.count()
    error_count = base.filter(OperationLog.status == "error").count()
    warning_count = base.filter(OperationLog.status == "warning").count()
    # 业务状态流转：业务代码写入了 status_before / status_after 的记录
    # （历史行的这两列可能是 NULL，用 coalesce 兜住）
    status_changed_count = base.filter(
        or_(
            func.coalesce(OperationLog.status_before, "") != "",
            func.coalesce(OperationLog.status_after, "") != "",
        )
    ).count()

    # 按模块统计
    module_stats = (
        base.with_entities(OperationLog.module, func.count(OperationLog.id))
        .group_by(OperationLog.module)
        .order_by(func.count(OperationLog.id).desc())
        .limit(10)
        .all()
    )

    # 按操作统计
    action_stats = (
        base.with_entities(OperationLog.action, func.count(OperationLog.id))
        .group_by(OperationLog.action)
        .order_by(func.count(OperationLog.id).desc())
        .limit(10)
        .all()
    )

    # 最近日志
    latest_logs = (
        base.order_by(desc(OperationLog.created_at))
        .limit(12)
        .all()
    )

    return {
        "total": total,
        "error_count": error_count,
        "warning_count": warning_count,
        "status_changed_count": status_changed_count,
        "today_login_users": _count_today_login_users(db, tenant_id),
        "modules": [{"name": m[0] or "其他", "count": m[1]} for m in module_stats],
        "actions": [{"name": a[0] or "其他", "count": a[1]} for a in action_stats],
        "latest": [_log_to_dict(l) for l in latest_logs],
    }


def _count_today_login_users(db: Session, tenant_id: Optional[int]) -> int:
    """今日登录成功过的去重用户数（同一账号当天多次登录只算一次）。"""
    from database import LoginLog
    from services.common_utils import local_day_start_utc
    from services.login_log_service import STATUS_SUCCESS

    query = db.query(func.count(func.distinct(LoginLog.username))).filter(
        LoginLog.status == STATUS_SUCCESS,
        LoginLog.login_at >= local_day_start_utc(),
    )
    if tenant_id is not None:
        query = query.filter(
            (LoginLog.tenant_id == tenant_id) | (LoginLog.tenant_id.is_(None))
        )
    return int(query.scalar() or 0)


def _log_to_dict(log: OperationLog) -> Dict[str, Any]:
    """将OperationLog对象转为字典"""
    return {
        "id": log.id,
        "seq": log.seq,
        "tenant_id": log.tenant_id,
        "user_id": log.user_id,
        "username": log.username or "",
        "module": log.module or "",
        "action": log.action or "",
        "title": log.title or "",
        "description": log.description or "",
        "target_type": log.target_type or "",
        "target_id": log.target_id or "",
        "level": log.level or "",
        "status_before": log.status_before or "",
        "status_after": log.status_after or "",
        "link": log.link or "",
        "payload": log.payload or {},
        "source": log.source or "",
        "ip_address": log.ip_address or "",
        "user_agent": log.user_agent or "",
        "request_data": log.request_data or {},
        "response_data": log.response_data or {},
        "status": log.status or "success",
        "error_message": log.error_message or "",
        "duration_ms": log.duration_ms or 0,
        "prev_hash": log.prev_hash or "",
        "hash": log.hash or "",
        "created_at": log.created_at.isoformat() if log.created_at else "",
    }
