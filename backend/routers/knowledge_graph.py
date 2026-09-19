"""知识图谱接口

两块图谱，数据来源不同，不混在一张图里：

- **业务实体图谱**（本文件）：建筑 / 楼层 / 设备 / 告警 / 工单 / 巡检 / 隐患类型 / 知识条目，
  查询时从业务表现算（见 `services/entity_graph_service.py`）
- **学习知识图谱**：资格方向 / 等级 / 模块 / 知识点 / 题目 / 课程，已有接口在
  `GET /api/learning/knowledge-graph`（数据源是题库与课程 JSON）

读接口只要登录；与其它业务读接口一致，不额外要求权限码。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from services import entity_graph_service
from services.auth_service import get_current_tenant_id, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["知识图谱"])


@router.get("/api/kg/overview")
def api_kg_overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """各类型节点数、关系数与数据来源说明（页面顶部的统计用）。"""
    return entity_graph_service.overview(db, tenant_id)


@router.get("/api/kg/graph")
def api_kg_graph(
    alerts: int = Query(200, ge=1, le=1000, description="告警节点上限（按时间倒序）"),
    workorders: int = Query(200, ge=1, le=1000, description="工单节点上限"),
    inspections: int = Query(200, ge=1, le=1000, description="巡检记录节点上限"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """完整图谱（受上限约束，响应里带 truncated 说明是否被截断）。"""
    return entity_graph_service.build_graph(
        db, tenant_id, {"alerts": alerts, "workorders": workorders, "inspections": inspections}
    )


@router.get("/api/kg/subgraph")
def api_kg_subgraph(
    entity_type: str = Query(..., description="building/floor/device/alert/workorder/inspection/hazard/knowledge"),
    entity_id: str = Query(..., description="实体 id（hazard 用隐患名，knowledge 用条目 id）"),
    depth: int = Query(1, ge=1, le=3),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """以某个实体为中心取 N 度邻居（点击节点下钻用）。"""
    result = entity_graph_service.subgraph(db, tenant_id, entity_type, entity_id, depth)
    if not result.get("found"):
        return JSONResponse(status_code=404, content=result)
    return result


@router.get("/api/kg/search")
def api_kg_search(
    keyword: str = Query("", description="按实体名称/编号模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return entity_graph_service.search(db, tenant_id, keyword, limit)
