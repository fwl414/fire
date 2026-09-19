from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from database import User, get_db
from services.auth_service import get_current_tenant_id, get_current_user, require_permission
from services.report_archive_service import (
    artifact_to_dict,
    delete_artifact,
    get_artifact,
    list_artifacts,
    resolve_artifact_path,
)
from services import task_queue_service as task_queue
from services.report_export_service import export_report
from services.report_statistics_service import VALID_REPORT_TYPES, build_report_statistics

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["报表中心"])


@router.get("/api/reports/statistics")
def api_report_statistics(
    report_type: str = "inspection",
    period: str = "month",
    start_date: str = "",
    end_date: str = "",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """按租户生成报表统计数据（与报表导出共用同一统计口径）。"""
    return build_report_statistics(
        db,
        tenant_id,
        report_type=report_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


def _export_and_respond(
    payload: Dict[str, Any],
    db: Session,
    current_user: User,
    tenant_id: int,
):
    """生成报表 → 落盘登记 → 返回文件流（并带出报表编号，便于后续受控下载）。"""
    try:
        result = export_report(
            db,
            tenant_id=tenant_id,
            payload=payload,
            user_id=current_user.id,
            user_name=current_user.real_name or current_user.username,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "message": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=500, content={"ok": False, "message": str(exc)})

    path = resolve_artifact_path(result.artifact)
    if not path:
        return JSONResponse(status_code=500, content={"ok": False, "message": "报表已生成但文件不可读"})

    headers = {
        "X-Report-Id": str(result.artifact.id),
        "X-Report-No": result.artifact.report_no,
        "Access-Control-Expose-Headers": "X-Report-Id, X-Report-No",
    }
    return FileResponse(
        path,
        media_type=result.media_type,
        filename=result.filename,
        headers=headers,
    )


@router.post("/api/reports/export")
def api_export_report(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """导出报表：后端生成并保存，返回文件流，同时登记为可下载报表产物。"""
    return _export_and_respond(payload, db, current_user, tenant_id)


@router.get("/api/reports/export/csv")
def api_export_report_csv(
    report_type: str = "inspection",
    period: str = "month",
    start_date: str = "",
    end_date: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """导出 CSV 报表：与 /api/reports/export 走同一生成与归档链路。"""
    return _export_and_respond(
        {
            "report_type": report_type,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "format": "csv",
        },
        db,
        current_user,
        tenant_id,
    )


@router.post("/api/reports/export/tasks")
def api_export_report_async(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """把报表生成放到后台任务队列执行。

    报表统计在 `period=year` 时会串行发出数百条 count 查询，同步导出会让前端长时间等待，
    因此提供异步入口：立即返回 task_id，前端轮询 `GET /api/tasks/{task_id}` 获取进度，
    完成后用返回的 artifact_id 走 `/api/reports/artifacts/{id}/download` 受控下载。
    """
    report_type = str(payload.get("report_type") or "inspection")
    if report_type not in VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的报表类型：{report_type}，可选值：{', '.join(VALID_REPORT_TYPES)}",
        )

    task = task_queue.enqueue(
        db,
        task_type="report_export",
        payload={
            "report_type": report_type,
            "period": payload.get("period") or "month",
            "format": payload.get("format") or "xlsx",
            "start_date": payload.get("start_date") or "",
            "end_date": payload.get("end_date") or "",
            "user_id": current_user.id,
        },
        tenant_id=tenant_id,
        task_name=f"{report_type} 报表导出",
        total_items=3,
        created_by=current_user.id,
        created_by_name=current_user.real_name or current_user.username or "",
    )
    return {
        "success": True,
        "task_id": task.task_id,
        "status": task.status,
        "message": "报表导出任务已入队，可通过 /api/tasks/{task_id} 查询进度",
    }


@router.get("/api/reports/artifacts")
def api_list_report_artifacts(
    report_type: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """已保存报表清单（按租户隔离）。"""
    rows = list_artifacts(db, tenant_id, report_type or None, limit)
    return {"total": len(rows), "items": [artifact_to_dict(row) for row in rows]}


@router.get("/api/reports/artifacts/{artifact_id}")
def api_get_report_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    artifact = get_artifact(db, tenant_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="报表不存在")
    return artifact_to_dict(artifact)


@router.get("/api/reports/artifacts/{artifact_id}/download")
def api_download_report_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """受控下载已保存报表：校验租户归属后返回文件，不暴露静态目录。"""
    artifact = get_artifact(db, tenant_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="报表不存在")

    path = resolve_artifact_path(artifact)
    if not path:
        raise HTTPException(status_code=404, detail="报表文件不存在或已被清理")

    return FileResponse(path, media_type=artifact.media_type, filename=artifact.filename)


@router.delete("/api/reports/artifacts/{artifact_id}")
def api_delete_report_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    if not delete_artifact(db, tenant_id, artifact_id):
        raise HTTPException(status_code=404, detail="报表不存在")
    return {"message": "删除成功", "id": artifact_id}


@router.get("/api/reports/templates")
def api_report_templates():
    return {
        "templates": [
            {"code": "inspection_monthly", "name": "月度巡检报表", "type": "inspection", "period": "month"},
            {"code": "inspection_quarterly", "name": "季度巡检报表", "type": "inspection", "period": "quarter"},
            {"code": "inspection_yearly", "name": "年度巡检报表", "type": "inspection", "period": "year"},
            {"code": "alert_monthly", "name": "月度告警报表", "type": "alert", "period": "month"},
            {"code": "alert_quarterly", "name": "季度告警报表", "type": "alert", "period": "quarter"},
            {"code": "workorder_monthly", "name": "月度工单报表", "type": "workorder", "period": "month"},
            {"code": "workorder_quarterly", "name": "季度工单报表", "type": "workorder", "period": "quarter"},
            {"code": "device_status", "name": "设备状态报表", "type": "device", "period": "month"},
            {"code": "risk_analysis", "name": "风险分析报表", "type": "risk", "period": "month"},
        ]
    }
