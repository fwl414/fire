"""移动端协同接口

面向一线人员的移动端（Web 移动端页面 `MobileInspection.vue`，也可被 Flutter 端复用）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/mobile/home` | 首页：真实待办统计 + 待处理告警 / 我的工单 / 可领取工单 |
| GET | `/api/mobile/tasks` | 我的待办（工单 + 告警合成一个列表） |
| POST | `/api/mobile/workorders/{order_id}/claim` | 领取工单（指派给自己并进入「处理中」），需 `workorders:update` |
| POST | `/api/mobile/report` | 现场上报（图片 + 描述），复用巡检 Agent，需 `inspection:run` |

告警处置与工单状态流转沿用既有接口（`POST /api/alerts/{id}/handle`、`POST /api/workorders/{id}/status`），
移动端不另造一套。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import Building, Device, User, get_db
from services import mobile_collab_service
from services.agent_service import run_inspection_agent
from services.auth_service import get_current_tenant_id, get_current_user, require_permission

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["移动端协同"])


def _mirror_report_to_archive(
    result: Dict[str, Any],
    *,
    location: str,
    description: str,
    inspector: str,
    tenant_id: int,
) -> Dict[str, Any]:
    """把现场上报同步写入巡检档案（运行库）。

    巡检数据目前分开存在两处：

    - 主库 `inspection_records`（SQLAlchemy 模型）：`run_inspection_agent` 写这里，供 `/api/records`
      与首页统计使用；
    - 运行库 `inspection_records`（`record_persistence_service`）：Web「巡检档案 / 报告打印 / 复查」
      读的是这里。

    Web 巡检页走的是「`/api/inspection/analyze` 写主库 + `/api/records/save-inspection` 写运行库」两步，
    移动端此前只做了第一步，导致现场上报在 Web 巡检档案里看不到。这里补齐第二步。

    档案 id 由主库记录 id 派生（`REC-M-<id>`），配合 `save_inspection_record` 的 INSERT OR REPLACE 保证幂等。
    """
    from services.record_persistence_service import save_inspection_record

    hazards = result.get("hazards") or []
    risk_score = result.get("risk_score") or 0
    risk_level = result.get("risk_level") or "未评估"
    image_paths = result.get("image_paths") or []
    return save_inspection_record(
        {
            "id": f"REC-M-{result.get('record_id')}",
            "location": location,
            "description": description,
            "hazards": hazards,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "result": {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_reason": result.get("risk_reason", ""),
                "suggestion": result.get("suggestion", ""),
                "executive_summary": result.get("executive_summary", ""),
                "hazards": hazards,
                "hazard_results": result.get("hazard_results", []),
                "agent_steps": result.get("agent_steps", []),
                "used_vision_api": bool(result.get("used_vision_api")),
                "used_text_model_api": bool(result.get("used_text_model_api")),
                "image_path": result.get("image_path", ""),
                "image_paths": image_paths,
            },
            # 运行库的报告字段要的是对象，而 Agent 产出的是纯文本报告，包一层即可
            "report": {"title": "现场巡检报告", "content": result.get("report", ""), "source": "mobile"},
            "image_paths": image_paths,
            "inspector": inspector,
        },
        tenant_id=tenant_id,
    )


@router.get("/api/mobile/home")
def api_mobile_home(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return mobile_collab_service.home_overview(db, tenant_id, current_user)


@router.get("/api/mobile/tasks")
def api_mobile_tasks(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return mobile_collab_service.my_tasks(db, tenant_id, current_user, limit)


@router.post("/api/mobile/workorders/{order_id}/claim")
def api_mobile_claim_workorder(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workorders:update")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = mobile_collab_service.claim_workorder(db, tenant_id, current_user, order_id)
    if not result.get("ok"):
        return JSONResponse(status_code=404 if result.get("not_found") else 400, content=result)
    return result


@router.post("/api/mobile/report")
async def api_mobile_report(
    building_id: Optional[int] = Form(None),
    device_id: Optional[int] = Form(None),
    location: str = Form(""),
    description: str = Form(""),
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inspection:run")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """现场上报：拍照 + 描述 → 走巡检 Agent（规则 + 文本/视觉模型 + RAG + 评分）→ 落巡检记录 + 巡检档案。

    响应只回移动端需要的字段（风险分/等级/隐患/建议/图片），不带完整的 agent 轨迹与报告正文，
    以免手机上收到几百 KB 的 JSON。
    """
    if not building_id and not device_id and not location.strip():
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "至少要选一个建筑/设备，或填写现场位置"},
        )

    resolved_location = location.strip()
    if not resolved_location and building_id:
        building = db.query(Building).filter(
            Building.id == building_id, Building.tenant_id == tenant_id
        ).first()
        if not building:
            return JSONResponse(status_code=404, content={"ok": False, "message": "建筑不存在"})
        resolved_location = building.building_name
    if device_id:
        device = db.query(Device).filter(
            Device.id == device_id, Device.tenant_id == tenant_id
        ).first()
        if not device:
            return JSONResponse(status_code=404, content={"ok": False, "message": "设备不存在"})
        if not resolved_location:
            resolved_location = device.location or device.device_name

    result = await run_inspection_agent(
        db,
        device_id,
        resolved_location,
        description,
        file or image,
        tenant_id=tenant_id,
    )

    # 同步进巡检档案，否则 Web「巡检档案」页看不到这次现场上报（原因见 _mirror_report_to_archive）
    archive_id = ""
    try:
        archive_id = _mirror_report_to_archive(
            result,
            location=resolved_location,
            description=description,
            inspector=current_user.real_name or current_user.username,
            tenant_id=tenant_id,
        ).get("id", "")
    except Exception as exc:  # 档案是二次落库，失败不应让已经完成的现场上报整体失败
        print(f"[mobile] 现场上报写入巡检档案失败 record_id={result.get('record_id')}: {exc}")

    return {
        "ok": True,
        "message": "现场上报已完成分析",
        "recordId": result.get("record_id"),
        "archiveId": archive_id,
        "location": resolved_location,
        "riskScore": result.get("risk_score"),
        "riskLevel": result.get("risk_level"),
        "hazards": result.get("hazards", []),
        "suggestion": result.get("suggestion", ""),
        "executiveSummary": result.get("executive_summary", ""),
        "imagePath": result.get("image_path", ""),
        "usedVisionApi": result.get("used_vision_api", False),
        "usedTextModelApi": result.get("used_text_model_api", False),
    }
