"""消防业务实体图谱

把散落在业务表里的实体与关系抽出来，组成一张可查询、可可视化的图：

    建筑 ── 楼层 ── 设备 ── 告警 ── 工单
                      └── 巡检记录 ── 隐患类型 ── 知识条目

设计取舍（与「知识图谱」这个词的常见实现不同，这里刻意不引入图数据库）：

- **不建节点表/边表**：实体就是业务表里的行，关系就是外键与既有字段。
  另建一套图存储意味着「同一份事实存两遍」，业务写入时还得同步，迟早不一致。
  这里改成查询时现算，图谱永远等于库里的真实状态。
- **量级可控**：建筑/楼层/设备是全量（同租户），告警/工单/巡检按时间倒序各取前 N 条
  （默认 200），响应里如实回报 `truncated` 与各自的条数。
- **租户隔离**：业务实体一律按 `tenant_id` 过滤；知识条目来自运行时库的全局知识库
  （`rag_entries`），不带租户概念，节点上会标 `global: true`。
- **关系来源可追溯**：每条边都记 `relation` 与产生它的字段依据，前端展示时不至于变成玄学。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from database import AlertRecord, Building, Device, FaultTicket, Floor, InspectionRecord
from services.risk_engine import HAZARD_PROFILES, canonical_hazard
from services.runtime_db import connect_runtime_db

DEFAULT_LIMITS = {"alerts": 200, "workorders": 200, "inspections": 200}
MAX_KNOWLEDGE_PER_HAZARD = 3

# 节点类型 → 展示名（前端也按这份定义上色，避免两边各写一套）
NODE_TYPES: Dict[str, Dict[str, str]] = {
    "building": {"label": "建筑"},
    "floor": {"label": "楼层"},
    "device": {"label": "设备"},
    "alert": {"label": "告警"},
    "workorder": {"label": "工单"},
    "inspection": {"label": "巡检记录"},
    "hazard": {"label": "隐患类型"},
    "knowledge": {"label": "知识条目"},
}

RELATION_LABELS: Dict[str, str] = {
    "contains": "包含楼层",
    "locates": "布置设备",
    "triggers": "触发告警",
    "creates": "生成工单",
    "inspected_by": "被巡检",
    "found": "发现隐患",
    "documented_in": "知识支撑",
}

SEVERE_SEVERITIES = ("critical", "high")


def _node(node_type: str, node_id: str, label: str, **extra: Any) -> Dict[str, Any]:
    return {"id": f"{node_type}:{node_id}", "type": node_type, "label": label, **extra}


def _load_knowledge_entries() -> List[Dict[str, str]]:
    """读运行时库里的知识条目；运行时库还没建表或读不到时返回空列表（不编造条目）。"""
    try:
        conn = connect_runtime_db()
    except sqlite3.Error:  # pragma: no cover - 运行时库不可用时图谱仍应可用
        return []
    try:
        rows = conn.execute(
            "SELECT id, title, category, keywords, source FROM rag_entries WHERE enabled = 1"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"] or "",
                "category": row["category"] or "",
                "keywords": row["keywords"] or "",
                "source": row["source"] or "",
            }
            for row in rows
        ]
    except sqlite3.Error:  # pragma: no cover - 表不存在等情况
        return []
    finally:
        conn.close()


def _hazards_of(record: InspectionRecord) -> List[str]:
    """把巡检记录里 JSON 文本形态的隐患名解析出来（同时兼容 ["张三"] 与 [{name:...}]）。"""
    try:
        raw = json.loads(record.hazards or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    names: List[str] = []
    for item in raw:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("type") or item.get("name") or item.get("hazard_name") or ""
        else:
            name = ""
        name = canonical_hazard(str(name).strip())
        if name and name not in names:
            names.append(name)
    return names


def build_graph(db: Session, tenant_id: int, limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """构建本租户的实体图谱（节点 + 边 + 截断说明）。

    分两趟：先把所有实体读成节点，再连边。否则「告警 → 工单」这类边会因为
    被指向的节点还没加载而被丢掉（工单比告警后读，早期版本就踩过这个坑）。
    """
    limits = {**DEFAULT_LIMITS, **(limits or {})}

    buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()
    floors = db.query(Floor).filter(Floor.tenant_id == tenant_id).all()
    devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
    alerts = (
        db.query(AlertRecord)
        .filter(AlertRecord.tenant_id == tenant_id)
        .order_by(AlertRecord.created_at.desc())
        .limit(limits["alerts"])
        .all()
    )
    tickets = (
        db.query(FaultTicket)
        .filter(FaultTicket.tenant_id == tenant_id)
        .order_by(FaultTicket.created_at.desc())
        .limit(limits["workorders"])
        .all()
    )
    inspections = (
        db.query(InspectionRecord)
        .filter(InspectionRecord.tenant_id == tenant_id)
        .order_by(InspectionRecord.created_at.desc())
        .limit(limits["inspections"])
        .all()
    )

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, str]] = []
    seen_edges: Set[Tuple[str, str, str]] = set()

    def add_edge(source: str, relation: str, target: str) -> None:
        if source == target:
            return
        key = (source, relation, target)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"source": source, "target": target, "relation": relation,
                      "relationLabel": RELATION_LABELS.get(relation, relation)})

    # ---------- 第一趟：实体 → 节点 ----------
    for building in buildings:
        nodes[f"building:{building.id}"] = _node(
            "building", str(building.id), building.building_name,
            riskScore=building.risk_score, riskLevel=building.risk_level,
            buildingType=building.building_type, status=building.status,
        )

    for floor in floors:
        nodes[f"floor:{floor.id}"] = _node(
            "floor", str(floor.id), floor.floor_name,
            floorNumber=floor.floor_number, status=floor.status,
        )

    for device in devices:
        nodes[f"device:{device.id}"] = _node(
            "device", str(device.id), device.device_name,
            deviceType=device.device_type, status=device.status,
            location=device.location, buildingId=device.building_id, floorId=device.floor_id,
        )

    for alert in alerts:
        nodes[f"alert:{alert.id}"] = _node(
            "alert", str(alert.id), alert.alert_code,
            alertType=alert.alert_type, severity=alert.severity, status=alert.status,
            buildingName=alert.building_name, location=alert.location,
            repeatCount=alert.repeat_count, escalated=bool(alert.escalated),
            createdAt=alert.created_at.isoformat() if alert.created_at else None,
        )

    for ticket in tickets:
        nodes[f"workorder:{ticket.id}"] = _node(
            "workorder", str(ticket.id), ticket.title or f"工单#{ticket.id}",
            status=ticket.status, riskLevel=ticket.risk_level, priority=ticket.priority,
            buildingName=ticket.building_name, source=ticket.source,
            createdAt=ticket.created_at.isoformat() if ticket.created_at else None,
        )

    hazard_names: Set[str] = set()
    unlinked_inspections = 0
    inspection_hazards: Dict[int, List[str]] = {}
    for record in inspections:
        nodes[f"inspection:{record.id}"] = _node(
            "inspection", str(record.id), record.device_name or f"巡检#{record.id}",
            location=record.location, riskScore=record.risk_score, riskLevel=record.risk_level,
            createdAt=record.created_at.isoformat() if record.created_at else None,
        )
        inspection_hazards[record.id] = _hazards_of(record)
        hazard_names.update(inspection_hazards[record.id])
        if not (record.device_id and f"device:{record.device_id}" in nodes):
            unlinked_inspections += 1

    for name in sorted(hazard_names):
        nodes[f"hazard:{name}"] = _node(
            "hazard", name, name,
            # 隐患类型没有独立表：能对上规则表的是规则表类别，对不上的是巡检里的自由文本
            inRuleTable=name in HAZARD_PROFILES,
            category=HAZARD_PROFILES.get(name, {}).get("category", "其他"),
            baseScore=HAZARD_PROFILES.get(name, {}).get("score"),
        )

    # 隐患类型 → 知识条目：按「隐患名出现在条目标题或关键词里」这条可解释规则连边，
    # 每个隐患最多连 MAX_KNOWLEDGE_PER_HAZARD 条，避免一个高频隐患把全库挂满
    knowledge_entries = _load_knowledge_entries() if hazard_names else []
    knowledge_edges = 0
    for name in sorted(hazard_names):
        matched = [
            entry for entry in knowledge_entries
            if name and name in f"{entry['title']} {entry['keywords']}"
        ]
        for entry in matched[:MAX_KNOWLEDGE_PER_HAZARD]:
            node_id = f"knowledge:{entry['id']}"
            if node_id not in nodes:
                nodes[node_id] = _node(
                    "knowledge", entry["id"], entry["title"],
                    category=entry["category"], source=entry["source"], isGlobal=True,
                )
            add_edge(f"hazard:{name}", "documented_in", node_id)
            knowledge_edges += 1

    # ---------- 第二趟：关系 → 边 ----------
    for floor in floors:
        if f"building:{floor.building_id}" in nodes:
            add_edge(f"building:{floor.building_id}", "contains", f"floor:{floor.id}")

    for device in devices:
        if device.floor_id and f"floor:{device.floor_id}" in nodes:
            add_edge(f"floor:{device.floor_id}", "locates", f"device:{device.id}")
        elif device.building_id and f"building:{device.building_id}" in nodes:
            # 只有建筑没有楼层的设备直接挂在建筑下，避免设备变成孤点
            add_edge(f"building:{device.building_id}", "locates", f"device:{device.id}")

    for alert in alerts:
        if alert.device_id and f"device:{alert.device_id}" in nodes:
            add_edge(f"device:{alert.device_id}", "triggers", f"alert:{alert.id}")
        elif alert.building_id and f"building:{alert.building_id}" in nodes:
            add_edge(f"building:{alert.building_id}", "triggers", f"alert:{alert.id}")
        if alert.workorder_id and f"workorder:{alert.workorder_id}" in nodes:
            add_edge(f"alert:{alert.id}", "creates", f"workorder:{alert.workorder_id}")

    for ticket in tickets:
        if ticket.building_id and f"building:{ticket.building_id}" in nodes:
            add_edge(f"building:{ticket.building_id}", "creates", f"workorder:{ticket.id}")
        if ticket.device_id and f"device:{ticket.device_id}" in nodes:
            add_edge(f"device:{ticket.device_id}", "creates", f"workorder:{ticket.id}")

    for record in inspections:
        if record.device_id and f"device:{record.device_id}" in nodes:
            add_edge(f"device:{record.device_id}", "inspected_by", f"inspection:{record.id}")
        for name in inspection_hazards[record.id]:
            add_edge(f"inspection:{record.id}", "found", f"hazard:{name}")

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "node_types": NODE_TYPES,
        "relation_labels": RELATION_LABELS,
        "counts": _counts_by_type(list(nodes.values())),
        "limits": limits,
        "truncated": {
            "alerts": len(alerts) >= limits["alerts"],
            "workorders": len(tickets) >= limits["workorders"],
            "inspections": len(inspections) >= limits["inspections"],
        },
        "unlinked_inspections": unlinked_inspections,
        "knowledge_edges": knowledge_edges,
    }


def _counts_by_type(nodes: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {node_type: 0 for node_type in NODE_TYPES}
    for node in nodes:
        counts[node["type"]] = counts.get(node["type"], 0) + 1
    return counts


def overview(db: Session, tenant_id: int, limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """图谱概览：各类型节点数、关系数、以及数据来源与截断说明。"""
    graph = build_graph(db, tenant_id, limits)
    relation_counts: Dict[str, int] = {}
    for edge in graph["edges"]:
        relation_counts[edge["relation"]] = relation_counts.get(edge["relation"], 0) + 1
    return {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "node_counts": graph["counts"],
        "relation_counts": relation_counts,
        "node_types": NODE_TYPES,
        "relation_labels": RELATION_LABELS,
        "limits": graph["limits"],
        "truncated": graph["truncated"],
        "unlinked_inspections": graph["unlinked_inspections"],
        "knowledge_edges": graph["knowledge_edges"],
        "sources": [
            "建筑 / 楼层 / 设备：全量（本租户）",
            f"告警：最近 {graph['limits']['alerts']} 条",
            f"工单：最近 {graph['limits']['workorders']} 条",
            f"巡检记录：最近 {graph['limits']['inspections']} 条",
            "知识条目：运行时库 rag_entries（全局知识库，非本租户数据）",
        ],
    }


def subgraph(
    db: Session,
    tenant_id: int,
    entity_type: str,
    entity_id: str,
    depth: int = 1,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """以某个实体为中心取 N 度邻居。

    `entity_id` 对 `building/floor/device/alert/workorder/inspection` 是数字 id，
    对 `hazard` 是隐患名，对 `knowledge` 是知识条目 id。
    """
    graph = build_graph(db, tenant_id, limits)
    nodes = {node["id"]: node for node in graph["nodes"]}
    center_id = f"{entity_type}:{entity_id}"
    if center_id not in nodes:
        return {"found": False, "message": "实体不存在或不在当前图谱范围内", "nodes": [], "edges": []}

    adjacency: Dict[str, List[str]] = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge["target"])
        adjacency.setdefault(edge["target"], []).append(edge["source"])

    visited = {center_id}
    frontier = [center_id]
    for _ in range(max(1, min(depth, 3))):
        next_frontier: List[str] = []
        for current in frontier:
            for neighbour in adjacency.get(current, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    next_frontier.append(neighbour)
        frontier = next_frontier
        if not frontier:
            break

    selected_edges = [
        edge for edge in graph["edges"]
        if edge["source"] in visited and edge["target"] in visited
    ]
    selected_nodes = [nodes[node_id] for node_id in visited]
    return {
        "found": True,
        "center": nodes[center_id],
        "depth": depth,
        "nodes": selected_nodes,
        "edges": selected_edges,
        "node_types": NODE_TYPES,
        "relation_labels": RELATION_LABELS,
        "counts": _counts_by_type(selected_nodes),
    }


def search(db: Session, tenant_id: int, keyword: str, limit: int = 20) -> Dict[str, Any]:
    """按名称/编号模糊搜索实体（供前端「以某实体为中心」用）。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return {"keyword": keyword, "items": []}
    graph = build_graph(db, tenant_id)
    lowered = keyword.lower()
    items = [
        {
            "id": node["id"],
            "type": node["type"],
            "typeLabel": NODE_TYPES.get(node["type"], {}).get("label", node["type"]),
            "label": node["label"],
        }
        for node in graph["nodes"]
        if lowered in str(node["label"]).lower()
    ]
    return {"keyword": keyword, "items": items[:limit], "total": len(items)}
