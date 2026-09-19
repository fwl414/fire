"""操作日志（审计日志）接口

- 列表 / 看板：按租户隔离
- 完整性校验：重算哈希链，定位第一条被篡改或缺失的记录
- 审计导出：CSV / JSON，带链序号与哈希；导出动作本身也会留痕
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from database import User, get_db
from services.auth_service import get_current_user, require_permission
from services.login_log_service import list_login_logs
from services.operation_log_orm_service import (
    get_operation_log_dashboard_orm,
    list_operation_logs_orm,
)
from services.operation_log_service import (
    SOURCE_BUSINESS,
    append_operation_log,
    export_operation_logs,
    verify_operation_log_chain,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


def _parse_dt(value: str, *, end_of_day: bool = False) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d" and end_of_day:
            return parsed.replace(hour=23, minute=59, second=59)
        return parsed
    raise HTTPException(status_code=400, detail="时间格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")


@router.get("/api/system/operation-logs")
def api_system_operation_logs(
    module: str = "",
    action: str = "",
    status: str = "",
    level: str = "",
    source: str = "",
    username: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_permission("logs:view")),
    db: Session = Depends(get_db),
):
    return list_operation_logs_orm(
        db,
        module=module,
        action=action,
        status=status,
        level=level,
        source=source,
        username=username,
        keyword=keyword,
        page=page,
        page_size=page_size,
        tenant_id=current_user.tenant_id,
    )


@router.get("/api/system/operation-logs/dashboard")
def api_system_operation_logs_dashboard(
    current_user: User = Depends(require_permission("logs:view")),
    db: Session = Depends(get_db),
):
    return get_operation_log_dashboard_orm(db, tenant_id=current_user.tenant_id)


@router.get("/api/system/operation-logs/verify")
def api_verify_operation_logs(
    max_rows: Optional[int] = Query(None, description="最多校验多少条，缺省为全量"),
    current_user: User = Depends(require_permission("logs:view")),
    db: Session = Depends(get_db),
):
    """重算哈希链，确认审计日志未被篡改。

    链是全局的（序号全局单调），因此这里不做租户过滤，返回内容只有计数、
    异常位置与涉事行的摘要，不含其他租户的日志正文。
    """
    result = verify_operation_log_chain(db, max_rows=max_rows)
    result["verified_by"] = current_user.username
    return result


@router.get("/api/system/operation-logs/export")
def api_export_operation_logs(
    format: str = Query("csv", description="csv 或 json"),
    module: str = "",
    level: str = "",
    keyword: str = "",
    start: str = Query("", description="起始时间，支持 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS"),
    end: str = Query("", description="截止时间，传日期时按当天 23:59:59 处理"),
    limit: int = Query(20000, ge=1, le=20000),
    current_user: User = Depends(require_permission("logs:view")),
    db: Session = Depends(get_db),
):
    """导出审计日志（受控下载），并在日志中留下导出记录。"""
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end, end_of_day=True)

    try:
        content, filename, media_type, meta = export_operation_logs(
            db,
            tenant_id=current_user.tenant_id,
            fmt=format,
            module=module,
            level=level,
            keyword=keyword,
            start=start_dt,
            end=end_dt,
            limit=limit,
            exported_by=current_user.username or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 导出行为本身必须留痕，否则审计链不完整
    append_operation_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        username=current_user.username or "",
        module="操作日志",
        action="export",
        title="导出审计日志",
        description=(
            f"导出 {format.upper()} 格式审计日志 {meta['count']} 条；"
            f"筛选条件：模块={module or '全部'}，级别={level or '全部'}，"
            f"关键字={keyword or '无'}，时间范围={start or '不限'}~{end or '不限'}。"
        ),
        level="warning",
        source=SOURCE_BUSINESS,
        payload={"format": format, "count": meta["count"], "chain_verified": meta["chain"]["verified"]},
    )

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/api/system/login-logs")
def api_system_login_logs(
    username: str = "",
    status: str = Query("", description="success 或 failed"),
    ip_address: str = "",
    start: str = Query("", description="起始时间，支持 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS"),
    end: str = Query("", description="截止时间，传日期时按当天 23:59:59 处理"),
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_permission("logs:view")),
    db: Session = Depends(get_db),
):
    """登录日志：逐次的登录成功与失败明细。"""
    return list_login_logs(
        db,
        tenant_id=current_user.tenant_id,
        username=username,
        status=status,
        ip_address=ip_address,
        start=start,
        end=end,
        page=page,
        page_size=page_size,
    )
