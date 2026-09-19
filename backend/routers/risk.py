from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import User, get_db

from services.agent_decision_service import get_risk_style
from services.enhanced_risk_engine import calculate_building_risk



from services.risk_update_service import (get_risk_history, get_risk_trend, handle_new_inspection_result, handle_workorder_status_change, init_demo_risk_history, recalculate_building_risk, update_risk_score)

from services import risk_model_service
from services.auth_service import get_current_user, get_current_tenant_id, require_permission

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["风险评估"])


def _parse_form_json(raw: str, fallback: Any) -> Any:
    """解析表单里的 JSON 字段，只有「格式坏掉」时才退回默认值。

    这里刻意只捕获 `JSONDecodeError`：原先各处写的是 `except Exception`，
    会把代码错误一并吞掉 —— 本文件曾漏掉 `import json`，于是所有入参都被静默丢弃，
    接口按「什么都没有」算出 0 分并回复「整体安全状况良好」。
    """
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


@router.get("/api/risk/style")
def api_risk_style(risk_level: str = "", risk_score: float = 0):
    return get_risk_style(risk_level, risk_score)


@router.post("/api/risk/enhanced/calculate")
def api_calculate_enhanced_risk(
    building_id: str = Form(...),
    hazard_items: str = Form("[]"),
    telemetry_data: str = Form("[]"),
    inspection_stats: str = Form("{}"),
    environment_info: str = Form("{}"),
    history_accidents: int = Form(0),
    last_accident_days: int = Form(365),
):
    result = calculate_building_risk(
        building_id=building_id,
        hazard_items=_parse_form_json(hazard_items, []),
        telemetry_data=_parse_form_json(telemetry_data, []),
        inspection_stats=_parse_form_json(inspection_stats, {}),
        environment_info=_parse_form_json(environment_info, {}),
        history_accidents=history_accidents,
        last_accident_days=last_accident_days
    )
    return result


# ---------------- 风险评分动态更新 API ----------------

@router.post("/api/risk/update")
def api_update_risk(
    building_id: str = Form(...),
    current_score: int = Form(...),
    event_type: str = Form(...),
    event_data: str = Form("{}"),
    operator: str = Form("system"),
    related_id: str = Form(""),
):
    result = update_risk_score(
        building_id=building_id,
        current_score=current_score,
        event_type=event_type,
        event_data=_parse_form_json(event_data, {}),
        operator=operator,
        related_id=related_id
    )
    return result


@router.get("/api/risk/history")
def api_risk_history(
    building_id: str = None,
    limit: int = 50,
    event_type: str = None,
):
    result = get_risk_history(building_id=building_id, limit=limit, event_type=event_type)
    return result


@router.get("/api/risk/trend")
def api_risk_trend(
    building_id: str = "default",
    days: int = 30,
):
    result = get_risk_trend(building_id=building_id, days=days)
    return result


@router.post("/api/risk/workorder-status-change")
def api_workorder_status_change(
    workorder_data: str = Form(...),
    old_status: str = Form(...),
    new_status: str = Form(...),
    building_id: str = Form("default"),
    current_score: int = Form(50),
):
    result = handle_workorder_status_change(
        workorder=_parse_form_json(workorder_data, {}),
        old_status=old_status,
        new_status=new_status,
        building_id=building_id,
        current_score=current_score
    )
    return result


@router.post("/api/risk/new-inspection")
def api_new_inspection_risk(
    inspection_data: str = Form(...),
    building_id: str = Form("default"),
    current_score: int = Form(50),
):
    result = handle_new_inspection_result(
        inspection_result=_parse_form_json(inspection_data, {}),
        building_id=building_id,
        current_score=current_score
    )
    return result


@router.post("/api/risk/recalculate")
def api_recalculate_risk(
    building_id: str = Form(...),
    hazard_items: str = Form("[]"),
    workorders: str = Form("[]"),
    telemetry_alerts: str = Form("[]"),
    inspection_stats: str = Form("{}"),
):
    result = recalculate_building_risk(
        building_id=building_id,
        hazard_items=_parse_form_json(hazard_items, []),
        workorders=_parse_form_json(workorders, []),
        telemetry_alerts=_parse_form_json(telemetry_alerts, []),
        inspection_stats=_parse_form_json(inspection_stats, {})
    )
    return result


@router.post("/api/risk/init-demo")
def api_init_demo_risk():
    init_demo_risk_history()
    return {"success": True, "message": "演示数据已初始化"}


@router.get("/api/risk/enhanced/factors")
def api_get_risk_factors():
    return {
        "factors": [
            {"name": "隐患等级", "description": "隐患严重程度（A级、B级、C级）", "weight": 30},
            {"name": "隐患频次", "description": "近30天隐患发生频次", "weight": 15},
            {"name": "整改及时率", "description": "隐患整改完成的及时性", "weight": 20},
            {"name": "逾期任务", "description": "超期未整改的任务数量", "weight": 15},
            {"name": "设备在线率", "description": "设备在线状态比例", "weight": 10},
            {"name": "设备告警", "description": "设备告警发生频次", "weight": 15},
            {"name": "设备老化", "description": "设备老化程度", "weight": 10},
            {"name": "环境风险", "description": "实验室、化学品、电动车充电区等", "weight": 15},
            {"name": "历史事故", "description": "历史事故次数和时间衰减", "weight": 10},
            {"name": "巡检偏差", "description": "巡检计划执行偏差率", "weight": 10},
        ],
        "risk_levels": [
            {"score_range": "85-100", "level": "严重风险", "label": "critical"},
            {"score_range": "60-84", "level": "高风险", "label": "high"},
            {"score_range": "35-59", "level": "中风险", "label": "medium"},
            {"score_range": "0-34", "level": "低风险", "label": "low"},
        ]
    }


# ---------------- 风险预测模型（scikit-learn）----------------
#
# 上面那些接口都是规则算分；这一组才是「用历史数据训练出来的预测」：
# 预测某建筑未来 7 天是否会出现严重告警 / 告警升级。未训练时如实回报，不编造分数。

@router.get("/api/risk/model")
def api_risk_model_info():
    return risk_model_service.model_info()


@router.post("/api/risk/model/train")
def api_train_risk_model(
    observations: int = Query(risk_model_service.DEFAULT_OBSERVATIONS, ge=2, le=52),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_permission("risk:model")),
):
    result = risk_model_service.train_model(db, tenant_id, observations=observations)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/api/risk/predictions")
def api_risk_predictions(
    building_ids: str = Query("", description="逗号分隔的建筑 id，留空表示本租户全部建筑"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ids = [int(part) for part in building_ids.split(",") if part.strip().isdigit()]
    return risk_model_service.predict_buildings(db, tenant_id, building_ids=ids or None)


@router.get("/api/risk/prediction/{building_id}")
def api_risk_prediction(
    building_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = risk_model_service.predict_buildings(db, tenant_id, building_ids=[building_id])
    if not result["items"]:
        if not result.get("trained"):
            return result
        return JSONResponse(status_code=404, content={"ok": False, "message": "建筑不存在"})
    item = result["items"][0]
    item["trained"] = True
    item["trained_at"] = result.get("trained_at")
    item["window_days"] = result.get("window_days")
    item["label_definition"] = result.get("label_definition")
    item["metrics"] = result.get("metrics")
    item["limitations"] = result.get("limitations")
    return item


# ---------------- 设备告警联动 Agent API ----------------


