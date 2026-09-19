"""
风险评分动态更新服务
工单状态变更、复查通过、新巡检结果等都会触发风险评分重新计算
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from database import SessionLocal, RiskUpdateRecord


def _get_session(db: Optional[Session] = None) -> Session:
    """获取数据库会话：优先使用传入的会话，否则新建"""
    if db is not None:
        return db
    return SessionLocal()


def _record_to_dict(record: RiskUpdateRecord) -> Dict[str, Any]:
    """将数据库记录转为接口返回的字典格式"""
    return {
        "id": record.record_code,
        "building_id": record.building_id,
        "event_type": record.event_type,
        "event_data": record.event_data or {},
        "old_score": record.old_score,
        "new_score": record.new_score,
        "change": record.change,
        "reason": record.reason,
        "direction": record.direction,
        "operator": record.operator,
        "related_id": record.related_id,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
    }


def _calculate_score_change(
    event_type: str,
    current_score: int,
    event_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    根据事件类型计算风险评分变化

    规则：
    - 工单完成整改/复查通过：根据隐患等级扣减相应分数
    - 新增隐患/告警：根据严重程度增加相应分数
    - 逾期工单：每天增加少量分数
    - 环境改善：扣减相应分数
    """
    change = 0
    reason = ""

    if event_type == "workorder_completed":
        severity = event_data.get("severity", "C级")
        hazard_type = event_data.get("hazard_type", "")

        if severity in ["A级", "严重", "critical"]:
            change = -15
            reason = "严重隐患整改完成并复查通过"
        elif severity in ["B级", "高", "high"]:
            change = -10
            reason = "高风险隐患整改完成并复查通过"
        elif severity in ["C级", "中", "medium"]:
            change = -6
            reason = "中风险隐患整改完成并复查通过"
        else:
            change = -3
            reason = "低风险隐患整改完成并复查通过"

        is_overdue = event_data.get("is_overdue", False)
        if is_overdue:
            change += 2
            reason += "（逾期完成，扣分略减）"

    elif event_type == "workorder_overdue":
        days_overdue = event_data.get("days_overdue", 1)
        change = min(days_overdue * 2, 10)
        reason = f"工单逾期 {days_overdue} 天未闭环"

    elif event_type == "new_hazard":
        severity = event_data.get("severity", "C级")
        if severity in ["A级", "严重", "critical"]:
            change = 18
            reason = "新增严重隐患"
        elif severity in ["B级", "高", "high"]:
            change = 12
            reason = "新增高风险隐患"
        elif severity in ["C级", "中", "medium"]:
            change = 7
            reason = "新增中风险隐患"
        else:
            change = 3
            reason = "新增低风险隐患"

    elif event_type == "device_alert":
        alert_type = event_data.get("alert_type", "")
        if alert_type in ["fire", "smoke_high", "temperature_high"]:
            change = 15
            reason = f"设备告警：{alert_type}，疑似火灾风险"
        elif alert_type in ["remaining_current", "current_high"]:
            change = 10
            reason = f"设备告警：{alert_type}，可能漏电风险"
        elif alert_type in ["pressure_low", "water_pressure"]:
            change = 8
            reason = f"设备告警：{alert_type}，消防供水异常"
        else:
            change = 5
            reason = f"设备告警：{alert_type}"

    elif event_type == "inspection_passed":
        change = -5
        reason = "例行巡检无异常，风险小幅下降"

    elif event_type == "environment_improved":
        change = -8
        reason = "环境风险降低（如化学品清理、电动车规范管理等）"

    new_score = max(0, min(100, current_score + change))
    actual_change = new_score - current_score

    return {
        "change": actual_change,
        "new_score": new_score,
        "reason": reason,
        "direction": "down" if actual_change < 0 else "up" if actual_change > 0 else "none"
    }


def update_risk_score(
    building_id: str,
    current_score: int,
    event_type: str,
    event_data: Dict[str, Any] = None,
    operator: str = "system",
    related_id: str = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    更新建筑/区域风险评分，并持久化到数据库

    Args:
        building_id: 建筑/区域ID
        current_score: 当前风险评分
        event_type: 事件类型
        event_data: 事件相关数据
        operator: 操作人
        related_id: 关联ID（如工单号、巡检ID等）
        db: 可选数据库会话

    Returns:
        更新后的评分信息
    """
    if event_data is None:
        event_data = {}

    result = _calculate_score_change(event_type, current_score, event_data)

    record_code = f"RS-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    session = _get_session(db)
    owns_session = db is None
    try:
        record = RiskUpdateRecord(
            record_code=record_code,
            building_id=building_id,
            event_type=event_type,
            event_data=event_data,
            old_score=current_score,
            new_score=result["new_score"],
            change=result["change"],
            reason=result["reason"],
            direction=result["direction"],
            operator=operator,
            related_id=related_id or "",
        )
        session.add(record)
        session.commit()
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()

    return {
        "success": True,
        "building_id": building_id,
        "old_score": current_score,
        "new_score": result["new_score"],
        "change": result["change"],
        "reason": result["reason"],
        "direction": result["direction"],
        "record_id": record_code,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_risk_history(
    building_id: str = None,
    limit: int = 50,
    event_type: str = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    获取风险评分更新历史（从数据库读取）
    """
    session = _get_session(db)
    owns_session = db is None
    try:
        query = session.query(RiskUpdateRecord)
        if building_id:
            query = query.filter(RiskUpdateRecord.building_id == building_id)
        if event_type:
            query = query.filter(RiskUpdateRecord.event_type == event_type)

        records = query.order_by(RiskUpdateRecord.created_at.desc()).limit(limit).all()
        items = [_record_to_dict(r) for r in records]
        return {
            "total": len(items),
            "items": items
        }
    finally:
        if owns_session:
            session.close()


def recalculate_building_risk(
    building_id: str,
    hazard_items: List[Dict[str, Any]] = None,
    workorders: List[Dict[str, Any]] = None,
    telemetry_alerts: List[Dict[str, Any]] = None,
    inspection_stats: Dict[str, Any] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    重新计算建筑风险评分（全量重算），并持久化记录

    当有重大变更时，使用增强版风险引擎重新计算
    """
    try:
        from services.enhanced_risk_engine import calculate_building_risk

        result = calculate_building_risk(
            building_id=building_id,
            hazard_items=hazard_items or [],
            telemetry_data=telemetry_alerts or [],
            inspection_stats=inspection_stats or {}
        )

        record_code = f"RS-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        session = _get_session(db)
        owns_session = db is None
        try:
            record = RiskUpdateRecord(
                record_code=record_code,
                building_id=building_id,
                event_type="full_recalculation",
                event_data={"reason": "全量重算"},
                old_score=0,
                new_score=result.get("risk_score", 0),
                change=0,
                reason="全量重新计算风险评分",
                direction="none",
                operator="system",
                related_id="",
            )
            session.add(record)
            session.commit()
        except Exception:
            if owns_session:
                session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "risk_score": 0,
            "risk_level": "未知"
        }


def handle_workorder_status_change(
    workorder: Dict[str, Any],
    old_status: str,
    new_status: str,
    building_id: str = None,
    current_score: int = 50,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    处理工单状态变更，自动更新风险评分

    状态流转：
    待派单 → 整改中：无变化
    整改中 → 待复查：无变化
    待复查 → 已闭环：扣分（整改完成）
    任何状态 → 逾期：加分
    """
    building_id = building_id or workorder.get("building_id") or "default"

    event_type = None
    event_data = {
        "workorder_id": workorder.get("id"),
        "hazard_type": workorder.get("hazard") or workorder.get("hazard_type", ""),
        "severity": workorder.get("risk_level") or workorder.get("severity", "C级"),
    }

    if new_status == "已闭环" and old_status != "已闭环":
        event_type = "workorder_completed"

        deadline = workorder.get("deadline")
        if deadline:
            try:
                deadline_time = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
                if datetime.now() > deadline_time:
                    event_data["is_overdue"] = True
                    event_data["days_overdue"] = (datetime.now() - deadline_time).days
            except Exception:
                pass

    if event_type:
        result = update_risk_score(
            building_id=building_id,
            current_score=current_score,
            event_type=event_type,
            event_data=event_data,
            operator="system",
            related_id=workorder.get("id"),
            db=db,
        )
        return result

    return {
        "success": True,
        "score_updated": False,
        "reason": f"状态从 {old_status} 变更为 {new_status}，无需调整风险评分"
    }


def handle_new_inspection_result(
    inspection_result: Dict[str, Any],
    building_id: str = None,
    current_score: int = 50,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    处理新的巡检结果，更新风险评分
    """
    building_id = building_id or inspection_result.get("building_id") or "default"
    hazards = inspection_result.get("hazards") or inspection_result.get("hazard_items") or []

    if not hazards:
        result = update_risk_score(
            building_id=building_id,
            current_score=current_score,
            event_type="inspection_passed",
            event_data={
                "inspection_id": inspection_result.get("id"),
                "location": inspection_result.get("location", "")
            },
            operator="system",
            related_id=inspection_result.get("id"),
            db=db,
        )
        return result

    total_change = 0
    reasons = []

    for hazard in hazards:
        severity = hazard.get("severity") or hazard.get("risk_level", "C级")
        event_data = {
            "hazard_type": hazard.get("type") or hazard.get("hazard_name", ""),
            "severity": severity,
            "evidence": hazard.get("evidence", "")
        }

        change_result = _calculate_score_change("new_hazard", 0, event_data)
        total_change += abs(change_result["change"])
        reasons.append(event_data["hazard_type"] or "隐患")

    new_score = min(100, current_score + total_change)
    actual_change = new_score - current_score

    result = update_risk_score(
        building_id=building_id,
        current_score=current_score,
        event_type="new_hazard",
        event_data={
            "inspection_id": inspection_result.get("id"),
            "hazard_count": len(hazards),
            "hazard_types": reasons
        },
        operator="system",
        related_id=inspection_result.get("id"),
        db=db,
    )

    result["new_score"] = new_score
    result["change"] = actual_change
    result["reason"] = f"新增 {len(hazards)} 项隐患：{', '.join(reasons[:3])}"

    return result


def get_risk_trend(
    building_id: str,
    days: int = 30,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    获取风险评分趋势数据（基于数据库历史记录）
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    daily_scores = []
    base_score = 55

    session = _get_session(db)
    owns_session = db is None
    try:
        history = session.query(RiskUpdateRecord).filter(
            RiskUpdateRecord.building_id == building_id,
            RiskUpdateRecord.created_at >= start_date,
        ).order_by(RiskUpdateRecord.created_at.asc()).all()

        history_dicts = [_record_to_dict(r) for r in history]
    finally:
        if owns_session:
            session.close()

    current_score = base_score

    for i in range(days + 1):
        day = start_date + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")

        day_changes = [
            r for r in history_dicts
            if r["created_at"].startswith(day_str)
        ]

        for change in day_changes:
            current_score = max(0, min(100, current_score + change["change"]))

        daily_scores.append({
            "date": day_str,
            "score": current_score
        })

    return {
        "building_id": building_id,
        "days": days,
        "current_score": current_score,
        "trend": daily_scores,
        "change_from_start": current_score - base_score
    }


def init_demo_risk_history(db: Optional[Session] = None):
    """
    初始化演示用风险历史数据（写入数据库）
    """
    session = _get_session(db)
    owns_session = db is None
    try:
        if session.query(RiskUpdateRecord).count() > 0:
            return

        buildings = ["building_001", "building_002", "building_003"]
        event_types = ["workorder_completed", "new_hazard", "device_alert", "inspection_passed"]

        base_time = datetime.now() - timedelta(days=30)

        records = []
        for i in range(50):
            event_time = base_time + timedelta(
                days=i % 30,
                hours=i % 8,
                minutes=(i * 7) % 60
            )

            building_id = buildings[i % len(buildings)]
            event_type = event_types[i % len(event_types)]

            if event_type == "workorder_completed":
                change = -8
                reason = "隐患整改完成，风险下降"
            elif event_type == "new_hazard":
                change = 10
                reason = "巡检发现新隐患，风险上升"
            elif event_type == "device_alert":
                change = 5
                reason = "设备告警，风险上升"
            else:
                change = -3
                reason = "例行巡检正常，风险小幅下降"

            records.append(RiskUpdateRecord(
                record_code=f"RS-DEMO-{i+1:04d}",
                building_id=building_id,
                event_type=event_type,
                event_data={"demo": True},
                old_score=50 + (i * 2) % 30,
                new_score=max(0, min(100, 50 + (i * 2) % 30 + change)),
                change=change,
                reason=reason,
                direction="down" if change < 0 else "up",
                operator="system",
                related_id=f"DEMO-{i}",
                created_at=event_time,
            ))
        session.add_all(records)
        session.commit()
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()
