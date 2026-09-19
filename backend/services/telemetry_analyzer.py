from __future__ import annotations

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_


def parse_timestamp_utc(value: Any) -> Optional[datetime]:
    """把客户端传入的时间戳解析成**无时区 UTC**；无法解析时返回 None。

    时间戳来自客户端表单/JSON，格式不受控，几种输入都必须兜住：

    - 带时区的 ISO 串（`...Z` / `+08:00`）：直接拿去和 naive 的
      `datetime.utcnow()` 比较会抛
      `TypeError: can't compare offset-naive and offset-aware datetimes`；
      归一化后还要**换算**到 UTC，否则 `+08:00` 的时间会被当成本地墙上时间，
      平白往后挪 8 小时，边界附近的数据就会误判为「近期」。
    - 缺失 / 空串 / 随便一个非时间戳字符串：`fromisoformat` 抛 `ValueError`。
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


TELEMETRY_RULES: Dict[str, Dict[str, Any]] = {
    "smoke": {
        "unit": "mg/m³",
        "normal_range": (0, 0.3),
        "warning_threshold": 0.5,
        "alarm_threshold": 1.0,
        "hazard_type": "烟雾",
        "description": "烟雾浓度",
        "analysis": {
            "normal": "当前烟雾浓度处于正常范围，未检测到异常。",
            "warning": "烟雾浓度偏高，可能存在阴燃或初期火灾风险，建议加强监控。",
            "alarm": "检测到高浓度烟雾，可能存在火灾隐患，建议立即排查并启动应急预案。"
        }
    },
    "temperature": {
        "unit": "°C",
        "normal_range": (0, 45),
        "warning_threshold": 55,
        "alarm_threshold": 70,
        "hazard_type": "电气过热",
        "description": "温度",
        "analysis": {
            "normal": "当前温度正常，设备运行状态良好。",
            "warning": "温度偏高，可能存在设备过载或散热不良问题。",
            "alarm": "温度超过安全阈值，存在电气火灾风险，建议立即断电检查。"
        }
    },
    "current": {
        "unit": "A",
        "normal_range": (0, 20),
        "warning_threshold": 25,
        "alarm_threshold": 30,
        "hazard_type": "电气过载",
        "description": "电流",
        "analysis": {
            "normal": "电流处于正常范围，用电设备运行正常。",
            "warning": "电流偏高，可能存在过载风险，建议检查用电设备。",
            "alarm": "电流严重超标，存在电气火灾风险，建议立即切断电源进行检查。"
        }
    },
    "voltage": {
        "unit": "V",
        "normal_range": (200, 240),
        "warning_threshold": 250,
        "alarm_threshold": 260,
        "hazard_type": "电压异常",
        "description": "电压",
        "analysis": {
            "normal": "电压稳定，处于正常范围。",
            "warning": "电压偏高，可能对电气设备造成损害。",
            "alarm": "电压严重超标，存在电气设备烧毁风险，建议立即采取保护措施。"
        }
    },
    "pressure": {
        "unit": "MPa",
        "normal_range": (0.3, 0.6),
        "warning_threshold_low": 0.25,
        "warning_threshold_high": 0.7,
        "alarm_threshold_low": 0.2,
        "alarm_threshold_high": 0.8,
        "hazard_type": "水压异常",
        "description": "水压",
        "analysis": {
            "normal": "消防水压处于正常范围，可满足灭火需求。",
            "warning": "水压偏低，可能影响灭火效果，建议检查水泵运行状态。",
            "alarm": "水压严重不足，无法满足灭火需求，建议立即启动备用泵。"
        }
    },
    "remaining_current": {
        "unit": "mA",
        "normal_range": (0, 300),
        "warning_threshold": 500,
        "alarm_threshold": 1000,
        "hazard_type": "漏电隐患",
        "description": "剩余电流",
        "analysis": {
            "normal": "剩余电流正常，未检测到漏电现象。",
            "warning": "剩余电流偏高，可能存在漏电风险，建议排查线路。",
            "alarm": "检测到严重漏电，存在触电和电气火灾风险，建议立即断电检修。"
        }
    },
    "battery_level": {
        "unit": "%",
        "normal_range": (30, 100),
        "warning_threshold": 20,
        "alarm_threshold": 10,
        "hazard_type": "设备低电量",
        "description": "电池电量",
        "analysis": {
            "normal": "设备电池电量充足。",
            "warning": "设备电池电量偏低，建议及时充电或更换电池。",
            "alarm": "设备电池电量严重不足，可能导致设备离线，建议立即更换电池。"
        }
    }
}


def analyze_telemetry_single(
    metric_type: str,
    value: float,
    timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    rule = TELEMETRY_RULES.get(metric_type)
    if not rule:
        return {
            "metric_type": metric_type,
            "value": value,
            "unit": "unknown",
            "status": "unknown",
            "hazard_type": None,
            "analysis": f"未知指标类型: {metric_type}",
            "recommendation": "请确认指标类型是否正确。"
        }

    unit = rule["unit"]
    normal_min, normal_max = rule["normal_range"]
    
    if "warning_threshold_low" in rule:
        if value <= rule["alarm_threshold_low"]:
            status = "alarm"
        elif value <= rule["warning_threshold_low"]:
            status = "warning"
        elif value >= rule["alarm_threshold_high"]:
            status = "alarm"
        elif value >= rule["warning_threshold_high"]:
            status = "warning"
        else:
            status = "normal"
    else:
        if value >= rule["alarm_threshold"]:
            status = "alarm"
        elif value >= rule["warning_threshold"]:
            status = "warning"
        elif normal_min <= value <= normal_max:
            status = "normal"
        elif value < normal_min:
            status = "warning"
        else:
            status = "normal"

    hazard_type = rule["hazard_type"] if status != "normal" else None
    analysis = rule["analysis"].get(status, "无法分析当前状态。")
    
    return {
        "metric_type": metric_type,
        "value": value,
        "unit": unit,
        "status": status,
        "hazard_type": hazard_type,
        "analysis": analysis,
        "recommendation": _generate_recommendation(rule, status),
        "timestamp": timestamp.isoformat() if timestamp else None
    }


def _generate_recommendation(rule: Dict[str, Any], status: str) -> str:
    recommendations = {
        "normal": "当前状态正常，继续保持监控。",
        "warning": f"【{rule['description']}】{rule['analysis']['warning']}建议安排人员进行检查。",
        "alarm": f"【{rule['description']}】{rule['analysis']['alarm']}建议立即采取措施，必要时启动应急预案。"
    }
    return recommendations.get(status, "请根据实际情况判断。")


def analyze_telemetry_history(
    metric_type: str,
    history: List[Dict[str, Any]],
    time_window: timedelta = timedelta(days=3)
) -> Dict[str, Any]:
    """分析近 `time_window` 内的历史数据。

    时间窗口用无时区 UTC 比较（与 `datetime.utcnow()`、与库里的时间列同口径），
    时间戳统一经 `parse_timestamp_utc` 归一化。

    缺少或无法解析时间戳的记录**保留**、只是不参与时间过滤：它们无法定位到具体时刻，
    当成过期数据丢掉可能漏报，留着让数值继续参与趋势与异常判定更稳妥。
    """
    if not history:
        return {
            "metric_type": metric_type,
            "trend": "no_data",
            "analysis": "暂无历史数据可供分析。",
            "anomalies": [],
            "risk_assessment": "无法评估"
        }

    cutoff = datetime.utcnow() - time_window
    recent_data = []
    for item in history:
        timestamp = parse_timestamp_utc(item.get("timestamp"))
        if timestamp is None or timestamp >= cutoff:
            recent_data.append(item)

    if not recent_data:
        return {
            "metric_type": metric_type,
            "trend": "stale",
            "analysis": "近期无有效数据，设备可能离线。",
            "anomalies": [],
            "risk_assessment": "低"
        }

    values = [h["value"] for h in recent_data if "value" in h]
    if not values:
        return {
            "metric_type": metric_type,
            "trend": "no_values",
            "analysis": "数据格式异常，无法提取数值。",
            "anomalies": [],
            "risk_assessment": "无法评估"
        }

    rule = TELEMETRY_RULES.get(metric_type)
    if not rule:
        return {
            "metric_type": metric_type,
            "trend": "unknown",
            "analysis": "未知指标类型，无法分析趋势。",
            "anomalies": [],
            "risk_assessment": "无法评估"
        }

    avg_value = sum(values) / len(values)
    max_value = max(values)
    min_value = min(values)
    trend = _detect_trend(values)

    anomalies = _detect_anomalies(metric_type, recent_data, rule)
    risk_level = _assess_risk(metric_type, anomalies, avg_value, rule)

    return {
        "metric_type": metric_type,
        "trend": trend,
        "analysis": _build_trend_analysis(metric_type, trend, avg_value, max_value, min_value, rule),
        "anomalies": anomalies,
        "risk_assessment": risk_level,
        "statistics": {
            "count": len(values),
            "average": round(avg_value, 2),
            "max": round(max_value, 2),
            "min": round(min_value, 2),
            "unit": rule["unit"]
        }
    }


def _detect_trend(values: List[float]) -> str:
    if len(values) < 3:
        return "stable"
    
    slope = sum(values[i+1] - values[i] for i in range(len(values)-1)) / (len(values)-1)
    avg_abs = sum(abs(v) for v in values) / len(values)
    
    if avg_abs == 0:
        return "stable"
    
    change_ratio = abs(slope) / avg_abs
    
    if change_ratio > 0.1:
        return "increasing" if slope > 0 else "decreasing"
    else:
        return "stable"


def _detect_anomalies(
    metric_type: str,
    history: List[Dict[str, Any]],
    rule: Dict[str, Any]
) -> List[Dict[str, Any]]:
    anomalies = []
    
    for data in history:
        value = data.get("value")
        timestamp = data.get("timestamp")
        
        if value is None:
            continue
        
        status = "normal"
        reason = ""
        
        if "warning_threshold_low" in rule:
            if value <= rule["alarm_threshold_low"]:
                status = "alarm"
                reason = f"数值低于报警阈值 {rule['alarm_threshold_low']} {rule['unit']}"
            elif value <= rule["warning_threshold_low"]:
                status = "warning"
                reason = f"数值低于警告阈值 {rule['warning_threshold_low']} {rule['unit']}"
            elif value >= rule["alarm_threshold_high"]:
                status = "alarm"
                reason = f"数值高于报警阈值 {rule['alarm_threshold_high']} {rule['unit']}"
            elif value >= rule["warning_threshold_high"]:
                status = "warning"
                reason = f"数值高于警告阈值 {rule['warning_threshold_high']} {rule['unit']}"
        else:
            if value >= rule["alarm_threshold"]:
                status = "alarm"
                reason = f"数值超过报警阈值 {rule['alarm_threshold']} {rule['unit']}"
            elif value >= rule["warning_threshold"]:
                status = "warning"
                reason = f"数值超过警告阈值 {rule['warning_threshold']} {rule['unit']}"
        
        if status != "normal":
            anomalies.append({
                "timestamp": timestamp,
                "value": value,
                "unit": rule["unit"],
                "status": status,
                "reason": reason
            })
    
    return anomalies


def _assess_risk(
    metric_type: str,
    anomalies: List[Dict[str, Any]],
    avg_value: float,
    rule: Dict[str, Any]
) -> str:
    alarm_count = sum(1 for a in anomalies if a["status"] == "alarm")
    warning_count = len(anomalies) - alarm_count
    
    if alarm_count >= 3:
        return "高"
    elif alarm_count >= 1:
        return "中高"
    elif warning_count >= 5:
        return "中"
    elif warning_count >= 2:
        return "中低"
    else:
        return "低"


def _build_trend_analysis(
    metric_type: str,
    trend: str,
    avg_value: float,
    max_value: float,
    min_value: float,
    rule: Dict[str, Any]
) -> str:
    analysis_parts = []
    
    if trend == "increasing":
        analysis_parts.append(f"{rule['description']}呈上升趋势")
    elif trend == "decreasing":
        analysis_parts.append(f"{rule['description']}呈下降趋势")
    else:
        analysis_parts.append(f"{rule['description']}保持稳定")
    
    analysis_parts.append(f"，平均值为 {avg_value:.2f}{rule['unit']}")
    
    if max_value > rule.get("warning_threshold", float('inf')):
        analysis_parts.append(f"，最高达到 {max_value:.2f}{rule['unit']}")
    
    return "".join(analysis_parts)


def analyze_multiple_telemetry(
    telemetry_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    results = {}
    hazard_types = []
    high_risk_count = 0
    
    for data in telemetry_data:
        metric_type = data.get("metric_type")
        value = data.get("value")
        
        if metric_type and value is not None:
            result = analyze_telemetry_single(metric_type, value)
            results[metric_type] = result
            
            if result["status"] == "alarm":
                high_risk_count += 1
                if result["hazard_type"]:
                    hazard_types.append(result["hazard_type"])
    
    overall_risk = "低"
    if high_risk_count >= 2:
        overall_risk = "高"
    elif high_risk_count == 1:
        overall_risk = "中"
    
    return {
        "individual_results": results,
        "hazard_types": list(set(hazard_types)),
        "high_risk_count": high_risk_count,
        "overall_risk": overall_risk,
        "summary": _build_summary(results, hazard_types, overall_risk)
    }


def _build_summary(
    results: Dict[str, Dict[str, Any]],
    hazard_types: List[str],
    overall_risk: str
) -> str:
    parts = []
    
    if hazard_types:
        parts.append(f"检测到 {len(hazard_types)} 类设备异常：{', '.join(hazard_types)}")
    else:
        parts.append("设备运行状态正常")
    
    if overall_risk == "高":
        parts.append("，整体风险等级为高风险，建议立即排查处理")
    elif overall_risk == "中":
        parts.append("，整体风险等级为中风险，建议安排检查")
    else:
        parts.append("，整体风险等级为低风险")
    
    return "".join(parts)


def interpret_device_alert(
    device_id: str,
    alert_type: str,
    telemetry_history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    analysis = analyze_telemetry_history(alert_type, telemetry_history)
    
    root_cause = _infer_root_cause(alert_type, analysis)
    recommendations = _generate_priority_recommendations(alert_type, analysis, root_cause)
    
    return {
        "device_id": device_id,
        "alert_type": alert_type,
        "analysis": analysis,
        "root_cause": root_cause,
        "recommendations": recommendations,
        "suggested_actions": _generate_action_items(recommendations)
    }


def _infer_root_cause(alert_type: str, analysis: Dict[str, Any]) -> str:
    if alert_type == "remaining_current":
        if analysis["risk_assessment"] == "高":
            return "某回路剩余电流连续超标，推断可能存在漏电隐患，建议重点排查线路绝缘状况和用电设备"
        return "剩余电流处于正常范围，线路运行状态良好"
    
    if alert_type == "temperature":
        if analysis["trend"] == "increasing":
            return f"温度持续上升，可能存在设备过载、散热不良或接触不良问题"
        return "温度稳定，设备运行正常"
    
    if alert_type == "pressure":
        if analysis["risk_assessment"] == "高":
            return f"水压严重不足，可能存在管网泄漏、水泵故障或阀门未正确开启"
        return "水压正常，消防供水系统运行良好"

    return f"{alert_type}指标异常，建议现场检查设备运行状态"


def _thresholds_for(metric: str) -> Dict[str, Any]:
    """从 TELEMETRY_RULES 抽出阈值摘要供前端展示。未配置的 metric 返回空 dict。"""
    rule = TELEMETRY_RULES.get(metric)
    if not rule:
        return {}
    payload = {
        "metric": metric,
        "unit": rule["unit"],
        "description": rule["description"],
        "normal_range": list(rule["normal_range"]),
        "warning_threshold": rule.get("warning_threshold"),
        "alarm_threshold": rule.get("alarm_threshold"),
    }
    if "warning_threshold_low" in rule:
        payload["warning_threshold_low"] = rule["warning_threshold_low"]
        payload["warning_threshold_high"] = rule["warning_threshold_high"]
        payload["alarm_threshold_low"] = rule["alarm_threshold_low"]
        payload["alarm_threshold_high"] = rule["alarm_threshold_high"]
    return payload


def get_latest_telemetry_by_device_type(
    db: Session,
    *,
    tenant_id: Optional[int],
    device_type: str,
    metric: str,
) -> Dict[str, Any]:
    """按设备类型取每设备最近一条非空指标值，附阈值规则。

    流程：
    1. 找出租户内 device_type 类型的所有设备；
    2. 对每设备取最近一条该 metric 非 null 的 DeviceTelemetry 行；
    3. 用 TELEMETRY_RULES[metric] 的阈值判定 status（normal/warning/alarm）；
    4. 设备从未上报该 metric 时返回 value=None, status="offline"，不编数。

    metric 必须命中 TELEMETRY_RULES，否则返回 thresholds=空 + items=空。
    """
    rule = TELEMETRY_RULES.get(metric)
    thresholds = _thresholds_for(metric)
    if not rule:
        return {"metric": metric, "unit": "", "thresholds": {}, "items": []}

    column_attr = _METRIC_COLUMN_MAP.get(metric)
    if column_attr is None:
        # 阈值规则里有但表里没对应列：返回空 items，不编数。
        return {
            "metric": metric,
            "unit": rule["unit"],
            "thresholds": thresholds,
            "items": [],
        }

    # 局部导入避免循环依赖（database 依赖链上有别的服务可能 import 此模块）
    from database import Device, DeviceTelemetry

    devices = (
        db.query(Device)
        .filter(
            Device.tenant_id == tenant_id if tenant_id is not None else Device.tenant_id.is_(None),
            Device.device_type == device_type,
        )
        .order_by(Device.id.asc())
        .all()
    )

    items: List[Dict[str, Any]] = []
    for device in devices:
        row = (
            db.query(DeviceTelemetry)
            .filter(
                DeviceTelemetry.device_id == device.id,
                column_attr.isnot(None),
            )
            .order_by(DeviceTelemetry.created_at.desc())
            .first()
        )
        if row is None:
            # 设备从未上报过该 metric：如实显示离线，不填值不编数
            items.append({
                "device_id": device.id,
                "device_code": device.device_code,
                "device_name": device.device_name,
                "location": device.location or "",
                "value": None,
                "unit": rule["unit"],
                "status": "offline",
                "warning_threshold": rule.get("warning_threshold"),
                "alarm_threshold": rule.get("alarm_threshold"),
                "normal_min": rule["normal_range"][0],
                "normal_max": rule["normal_range"][1],
                "update_time": None,
            })
            continue

        value = float(getattr(row, column_attr.name))
        analysis = analyze_telemetry_single(metric, value, row.created_at)
        items.append({
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "location": device.location or "",
            "value": value,
            "unit": rule["unit"],
            "status": analysis.get("status", "unknown"),
            "warning_threshold": rule.get("warning_threshold"),
            "alarm_threshold": rule.get("alarm_threshold"),
            "normal_min": rule["normal_range"][0],
            "normal_max": rule["normal_range"][1],
            "update_time": row.created_at.isoformat() if row.created_at else None,
        })

    return {
        "metric": metric,
        "unit": rule["unit"],
        "thresholds": thresholds,
        "items": items,
    }


# TELEMETRY_RULES 中 metric 与 DeviceTelemetry 列名对应表
# （battery_level 在规则里、列名是 battery）。延迟到模块加载末尾绑定，
# 避免在 database 还没就绪时被 import。
_METRIC_COLUMN_MAP: Dict[str, Any] = {}


def _init_metric_column_map() -> None:
    """延迟绑定 DeviceTelemetry 列，避免循环导入。"""
    from database import DeviceTelemetry

    _METRIC_COLUMN_MAP.clear()
    _METRIC_COLUMN_MAP.update({
        "temperature": DeviceTelemetry.temperature,
        "smoke": DeviceTelemetry.smoke,
        "co": DeviceTelemetry.co,
        "battery_level": DeviceTelemetry.battery,
        "current": DeviceTelemetry.current,
        "voltage": DeviceTelemetry.voltage,
        "pressure": DeviceTelemetry.pressure,
        "remaining_current": DeviceTelemetry.remaining_current,
    })


_init_metric_column_map()


def _generate_priority_recommendations(
    alert_type: str,
    analysis: Dict[str, Any],
    root_cause: str
) -> List[Dict[str, Any]]:
    recommendations = []
    
    if analysis["risk_assessment"] == "高":
        recommendations.append({
            "priority": "紧急",
            "action": f"立即检查相关设备和线路，确认{root_cause}",
            "responsible": "维修工程师",
            "timeframe": "立即"
        })
        recommendations.append({
            "priority": "紧急",
            "action": "必要时切断电源或停止设备运行，确保安全",
            "responsible": "值班人员",
            "timeframe": "立即"
        })
    elif analysis["risk_assessment"] == "中":
        recommendations.append({
            "priority": "高",
            "action": f"安排人员现场检查，核实{root_cause}",
            "responsible": "巡检员",
            "timeframe": "24小时内"
        })
    else:
        recommendations.append({
            "priority": "中",
            "action": f"持续监控{alert_type}变化趋势",
            "responsible": "系统自动监控",
            "timeframe": "持续"
        })
    
    return recommendations


def _generate_action_items(recommendations: List[Dict[str, Any]]) -> List[str]:
    return [f"{r['priority']} - {r['action']}（责任人：{r['responsible']}，时限：{r['timeframe']}）" 
            for r in recommendations]
