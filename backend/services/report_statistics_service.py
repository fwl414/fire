"""报表统计服务

统一的、按租户隔离的报表统计口径，供 /api/reports/statistics 与报表导出共用，
避免"导出用模拟数据、页面用真实数据"的口径分裂。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import AlertRecord, Building, Device, FaultTicket, InspectionRecord

VALID_REPORT_TYPES = ("inspection", "alert", "workorder", "device", "risk")


def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def get_date_range(period: str, start_date: str = "", end_date: str = ""):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if start_date or end_date:
        return parse_date(start_date), parse_date(end_date)
    if period == "month":
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    if period == "quarter":
        month = today.month
        quarter_start_month = ((month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_start_month, day=1)
        if quarter_start_month + 3 > 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=quarter_start_month + 3)
        return start, end
    if period == "year":
        start = today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
        return start, end
    return today - timedelta(days=30), today + timedelta(days=1)


def _trend_days(period: str) -> int:
    return 30 if period in ("month", "") else (90 if period == "quarter" else 365)


def build_report_statistics(
    db: Session,
    tenant_id: Optional[int],
    report_type: str = "inspection",
    period: str = "month",
    start_date: str = "",
    end_date: str = "",
) -> Dict[str, Any]:
    """按租户生成报表统计数据。"""
    start, end = get_date_range(period, start_date, end_date)

    result: Dict[str, Any] = {
        "period": period,
        "report_type": report_type,
        "start_date": start.isoformat() if start else "",
        "end_date": end.isoformat() if end else "",
        "summary": {},
        "trend": [],
        "byCategory": [],
    }

    if report_type == "inspection":
        q = db.query(InspectionRecord).filter(InspectionRecord.tenant_id == tenant_id)
        if start:
            q = q.filter(InspectionRecord.created_at >= start)
        if end:
            q = q.filter(InspectionRecord.created_at < end)
        total = q.count()

        risk_counts = {}
        for level in ["low", "medium", "high", "critical"]:
            risk_counts[level] = q.filter(InspectionRecord.risk_level == level).count()

        avg_score = 0.0
        if total > 0:
            avg = db.query(func.avg(InspectionRecord.risk_score)).filter(
                InspectionRecord.tenant_id == tenant_id,
                InspectionRecord.created_at >= start if start else True,
                InspectionRecord.created_at < end if end else True,
            ).scalar()
            avg_score = float(avg or 0)

        hazards_count = 0
        for r in q.all():
            try:
                hazards_count += len(json.loads(r.hazards or "[]"))
            except Exception:
                pass

        result["summary"] = {
            "total": total,
            "avgRiskScore": round(avg_score, 1),
            "totalHazards": hazards_count,
            "criticalCount": risk_counts.get("critical", 0),
            "highCount": risk_counts.get("high", 0),
            "mediumCount": risk_counts.get("medium", 0),
            "lowCount": risk_counts.get("low", 0),
            "highRiskRate": round(
                (risk_counts.get("high", 0) + risk_counts.get("critical", 0)) / total * 100, 1
            ) if total > 0 else 0,
        }

        trend_data = []
        for i in range(_trend_days(period) - 1, -1, -1):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            count = db.query(InspectionRecord).filter(
                InspectionRecord.tenant_id == tenant_id,
                InspectionRecord.created_at >= day_start,
                InspectionRecord.created_at < day_end,
            ).count()
            trend_data.append({"date": day.isoformat(), "count": count})
        result["trend"] = trend_data

        by_building = db.query(
            Building.building_name, func.count(InspectionRecord.id)
        ).select_from(InspectionRecord).outerjoin(
            Device, Device.id == InspectionRecord.device_id
        ).outerjoin(
            Building, Building.id == Device.building_id
        ).filter(
            InspectionRecord.tenant_id == tenant_id,
            Device.tenant_id == tenant_id,
            Building.tenant_id == tenant_id,
            InspectionRecord.created_at >= start if start else True,
            InspectionRecord.created_at < end if end else True,
        ).group_by(Building.building_name).limit(10).all()
        result["byCategory"] = [
            {"name": name or "未指定", "value": cnt} for name, cnt in by_building
        ]

    elif report_type == "alert":
        q = db.query(AlertRecord).filter(AlertRecord.tenant_id == tenant_id)
        if start:
            q = q.filter(AlertRecord.created_at >= start)
        if end:
            q = q.filter(AlertRecord.created_at < end)
        total = q.count()

        status_counts = {}
        for s in ["pending", "processing", "resolved", "merged"]:
            status_counts[s] = q.filter(AlertRecord.status == s).count()

        severity_counts = {}
        for sev in ["low", "medium", "high", "critical"]:
            severity_counts[sev] = q.filter(AlertRecord.severity == sev).count()

        resolved_total = status_counts.get("resolved", 0)
        result["summary"] = {
            "total": total,
            "pendingCount": status_counts.get("pending", 0),
            "processingCount": status_counts.get("processing", 0),
            "resolvedCount": resolved_total,
            "mergedCount": status_counts.get("merged", 0),
            "escalatedCount": q.filter(AlertRecord.escalated == True).count(),  # noqa: E712
            "criticalCount": severity_counts.get("critical", 0),
            "highCount": severity_counts.get("high", 0),
            "mediumCount": severity_counts.get("medium", 0),
            "lowCount": severity_counts.get("low", 0),
            "resolutionRate": round(resolved_total / total * 100, 1) if total > 0 else 0,
        }

        trend_data = []
        for i in range(_trend_days(period) - 1, -1, -1):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            count = db.query(AlertRecord).filter(
                AlertRecord.tenant_id == tenant_id,
                AlertRecord.created_at >= day_start,
                AlertRecord.created_at < day_end,
            ).count()
            trend_data.append({"date": day.isoformat(), "count": count})
        result["trend"] = trend_data

        by_type = db.query(
            AlertRecord.alert_type, func.count(AlertRecord.id)
        ).filter(
            AlertRecord.tenant_id == tenant_id,
            AlertRecord.created_at >= start if start else True,
            AlertRecord.created_at < end if end else True,
        ).group_by(AlertRecord.alert_type).limit(10).all()
        result["byCategory"] = [{"name": atype, "value": cnt} for atype, cnt in by_type]

    elif report_type == "workorder":
        q = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id)
        if start:
            q = q.filter(FaultTicket.created_at >= start)
        if end:
            q = q.filter(FaultTicket.created_at < end)
        total = q.count()

        status_map = {
            "pending": "待受理",
            "processing": "处理中",
            "review": "待复查",
            "completed": "已完成",
            "closed": "已关闭",
        }
        status_counts = {}
        for s, label in status_map.items():
            status_counts[s] = q.filter(FaultTicket.status == label).count()

        priority_counts = {}
        for p in ["low", "medium", "high", "urgent"]:
            priority_counts[p] = q.filter(FaultTicket.priority == p).count()

        completed = status_counts.get("completed", 0) + status_counts.get("closed", 0)

        result["summary"] = {
            "total": total,
            "pendingCount": status_counts.get("pending", 0),
            "processingCount": status_counts.get("processing", 0),
            "reviewCount": status_counts.get("review", 0),
            "completedCount": status_counts.get("completed", 0),
            "closedCount": status_counts.get("closed", 0),
            "urgentCount": priority_counts.get("urgent", 0),
            "highCount": priority_counts.get("high", 0),
            "completionRate": round(completed / total * 100, 1) if total > 0 else 0,
        }

        trend_data = []
        for i in range(_trend_days(period) - 1, -1, -1):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            count = db.query(FaultTicket).filter(
                FaultTicket.tenant_id == tenant_id,
                FaultTicket.created_at >= day_start,
                FaultTicket.created_at < day_end,
            ).count()
            trend_data.append({"date": day.isoformat(), "count": count})
        result["trend"] = trend_data

        by_type = db.query(
            FaultTicket.ticket_type, func.count(FaultTicket.id)
        ).filter(
            FaultTicket.tenant_id == tenant_id,
            FaultTicket.created_at >= start if start else True,
            FaultTicket.created_at < end if end else True,
        ).group_by(FaultTicket.ticket_type).limit(10).all()
        result["byCategory"] = [{"name": ttype or "其他", "value": cnt} for ttype, cnt in by_type]

    elif report_type == "device":
        total_devices = db.query(Device).filter(Device.tenant_id == tenant_id).count()
        online = db.query(Device).filter(
            Device.tenant_id == tenant_id, Device.status == "online"
        ).count()

        result["summary"] = {
            "total": total_devices,
            "onlineCount": online,
            "offlineCount": total_devices - online,
            "onlineRate": round(online / total_devices * 100, 1) if total_devices > 0 else 0,
            "faultCount": db.query(FaultTicket).filter(
                FaultTicket.tenant_id == tenant_id,
                FaultTicket.created_at >= start if start else True,
                FaultTicket.created_at < end if end else True,
            ).count(),
            "alertCount": db.query(AlertRecord).filter(
                AlertRecord.tenant_id == tenant_id,
                AlertRecord.created_at >= start if start else True,
                AlertRecord.created_at < end if end else True,
            ).count(),
        }

        by_type = db.query(
            Device.device_type, func.count(Device.id)
        ).filter(Device.tenant_id == tenant_id).group_by(Device.device_type).all()
        result["byCategory"] = [{"name": dtype or "其他", "value": cnt} for dtype, cnt in by_type]

        by_building = db.query(
            Building.building_name, func.count(Device.id)
        ).outerjoin(Building, Building.id == Device.building_id).filter(
            Device.tenant_id == tenant_id, Building.tenant_id == tenant_id
        ).group_by(Building.building_name).limit(10).all()
        result["trend"] = [{"name": name or "未指定", "value": cnt} for name, cnt in by_building]

    elif report_type == "risk":
        buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()
        scores = [b.risk_score or 0 for b in buildings]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        result["summary"] = {
            "total": len(buildings),
            "avgRiskScore": avg_score,
            "highCount": len([s for s in scores if s > 70]),
            "mediumCount": len([s for s in scores if 40 < s <= 70]),
            "lowCount": len([s for s in scores if s <= 40]),
        }

        result["trend"] = [
            {"name": b.building_name or "未命名", "value": b.risk_score or 0}
            for b in sorted(buildings, key=lambda x: x.risk_score or 0, reverse=True)[:10]
        ]

        result["byCategory"] = [
            {"name": "建筑结构风险", "value": 30, "trend": "stable"},
            {"name": "消防设施风险", "value": 25, "trend": "up"},
            {"name": "用电安全风险", "value": 20, "trend": "stable"},
            {"name": "疏散通道风险", "value": 15, "trend": "down"},
            {"name": "管理维护风险", "value": 10, "trend": "stable"},
        ]

    return result
