"""
设备告警自动联动Agent服务
设备告警 → Agent分析 → 自动生成工单 → 推送通知 → 更新风险评分
形成完整的闭环处理流程
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
import json


ALERT_QUEUE: List[Dict[str, Any]] = []
PROCESSED_ALERTS: List[Dict[str, Any]] = []


def _get_alert_profile(alert_type: str) -> Dict[str, Any]:
    """
    获取告警类型的配置档案
    """
    profiles = {
        "smoke_high": {
            "name": "烟雾浓度超标",
            "category": "火灾预警",
            "severity": "critical",
            "priority": "紧急",
            "hazard_type": "烟雾异常",
            "risk_level": "严重风险",
            "possible_causes": [
                "发生火灾，烟雾蔓延",
                "烹饪或吸烟产生的烟雾触发",
                "灰尘或水汽导致误报",
                "设备故障或灵敏度偏移"
            ],
            "immediate_actions": [
                "立即确认现场情况，查看监控或安排人员现场核实",
                "如确认火情，立即启动应急预案，拨打119",
                "组织人员疏散，关闭相关区域电源"
            ],
            "investigation_steps": [
                "检查现场是否有明火或烟雾来源",
                "查看周边监控录像，确认异常时间点的情况",
                "检查设备是否有故障或校准问题",
                "记录并分析近期类似告警发生频率"
            ],
            "deadline_hours": 2
        },
        "temperature_high": {
            "name": "温度异常升高",
            "category": "电气安全",
            "severity": "high",
            "priority": "高",
            "hazard_type": "温度异常",
            "risk_level": "高风险",
            "possible_causes": [
                "电气设备过载或短路，导致局部过热",
                "接触不良导致接触电阻过大发热",
                "环境温度过高或通风不良",
                "设备老化或散热系统故障"
            ],
            "immediate_actions": [
                "降低相关区域负载，必要时切断电源",
                "检查发热点，确认是否有电气故障",
                "改善通风散热条件"
            ],
            "investigation_steps": [
                "使用红外热像仪检测异常发热点",
                "检查电气连接是否松动或氧化",
                "分析负载曲线，确认是否过载",
                "检查散热设备运行状态"
            ],
            "deadline_hours": 12
        },
        "remaining_current": {
            "name": "剩余电流超标",
            "category": "电气安全",
            "severity": "high",
            "priority": "高",
            "hazard_type": "漏电隐患",
            "risk_level": "高风险",
            "possible_causes": [
                "电气线路绝缘老化或破损导致漏电",
                "设备受潮或进水，绝缘性能下降",
                "相线与地线接反或接地不良",
                "设备内部故障导致对地泄漏"
            ],
            "immediate_actions": [
                "安排电工检测该回路绝缘电阻",
                "排查可能的漏电点，优先检查潮湿区域",
                "确认设备是否有外壳带电情况"
            ],
            "investigation_steps": [
                "使用漏电检测仪定位漏电点",
                "检查线路绝缘老化情况，特别是接头处",
                "测试设备对地绝缘电阻",
                "分析漏电趋势，判断是渐进还是突发"
            ],
            "deadline_hours": 24
        },
        "current_high": {
            "name": "电流过载",
            "category": "电气安全",
            "severity": "high",
            "priority": "高",
            "hazard_type": "电气过载",
            "risk_level": "高风险",
            "possible_causes": [
                "负载过大，超过线路或设备额定容量",
                "启动设备过多，瞬时冲击电流过大",
                "线路或设备存在短路故障",
                "三相负载严重不平衡"
            ],
            "immediate_actions": [
                "降低负载，关停部分非必要设备",
                "检查设备运行状态，是否有异常噪音或发热",
                "监控电流变化趋势"
            ],
            "investigation_steps": [
                "检查负载分配，确认是否超出设计容量",
                "检测各相电流，评估三相平衡度",
                "检查线路和设备是否有过热迹象",
                "分析历史电流数据，判断是常态还是突发"
            ],
            "deadline_hours": 24
        },
        "pressure_low": {
            "name": "水压过低",
            "category": "消防设施",
            "severity": "high",
            "priority": "高",
            "hazard_type": "消防供水不足",
            "risk_level": "高风险",
            "possible_causes": [
                "消防泵故障或未正常启动",
                "管道漏水或阀门未完全开启",
                "高位水箱水量不足",
                "减压阀或稳压装置故障"
            ],
            "immediate_actions": [
                "检查消防水泵运行状态，必要时手动启动",
                "确认消防水箱水位",
                "检查管道阀门状态"
            ],
            "investigation_steps": [
                "检查消防泵组运行和控制柜状态",
                "排查管网漏水点",
                "检查稳压设备工作情况",
                "测试最不利点水压"
            ],
            "deadline_hours": 24
        },
        "device_offline": {
            "name": "设备离线",
            "category": "设备状态",
            "severity": "medium",
            "priority": "中",
            "hazard_type": "设备故障",
            "risk_level": "中风险",
            "possible_causes": [
                "设备电源故障或断电",
                "网络连接中断",
                "设备硬件故障",
                "通信模块故障"
            ],
            "immediate_actions": [
                "检查设备供电情况",
                "确认网络连接状态",
                "安排维护人员现场检查"
            ],
            "investigation_steps": [
                "检查电源和供电线路",
                "测试网络连通性",
                "重启设备观察恢复情况",
                "检查设备日志，定位故障原因"
            ],
            "deadline_hours": 48
        },
        "battery_low": {
            "name": "电池电量低",
            "category": "设备状态",
            "severity": "medium",
            "priority": "中",
            "hazard_type": "设备维护",
            "risk_level": "中风险",
            "possible_causes": [
                "电池老化，容量下降",
                "充电系统故障",
                "长时间未充电",
                "环境温度过低影响电池性能"
            ],
            "immediate_actions": [
                "检查充电系统是否正常",
                "必要时更换电池"
            ],
            "investigation_steps": [
                "测试电池电压和内阻",
                "检查充电回路和充电电流",
                "评估电池使用年限",
                "记录电池更换周期"
            ],
            "deadline_hours": 72
        }
    }
    
    return profiles.get(alert_type, {
        "name": alert_type,
        "category": "其他",
        "severity": "medium",
        "priority": "中",
        "hazard_type": "设备告警",
        "risk_level": "中风险",
        "possible_causes": ["设备异常，需进一步排查"],
        "immediate_actions": ["安排人员检查告警原因"],
        "investigation_steps": ["核实告警真实性", "排查故障原因"],
        "deadline_hours": 48
    })


def process_device_alert(
    device_id: str,
    alert_type: str,
    alert_value: float = None,
    alert_unit: str = "",
    device_info: Dict[str, Any] = None,
    telemetry_history: List[Dict[str, Any]] = None,
    building_id: str = "default",
    building_name: str = "未指定区域"
) -> Dict[str, Any]:
    """
    处理设备告警，自动调用Agent分析并生成处置方案
    
    流程：
    1. 接收告警，获取告警档案
    2. 分析遥测历史，判断趋势
    3. 推断可能原因
    4. 生成处置建议
    5. 自动创建工单
    6. 更新风险评分
    7. 记录决策日志
    """
    device_info = device_info or {}
    telemetry_history = telemetry_history or []
    
    profile = _get_alert_profile(alert_type)
    
    alert_id = f"AL-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    analysis_result = _analyze_alert_with_agent(
        device_id=device_id,
        alert_type=alert_type,
        alert_value=alert_value,
        alert_unit=alert_unit,
        profile=profile,
        telemetry_history=telemetry_history,
        device_info=device_info
    )
    
    workorder = _generate_workorder(
        alert_id=alert_id,
        device_id=device_id,
        alert_type=alert_type,
        profile=profile,
        analysis=analysis_result,
        device_info=device_info,
        building_id=building_id,
        building_name=building_name
    )
    
    risk_update = _update_risk_for_alert(
        building_id=building_id,
        alert_type=alert_type,
        profile=profile,
        alert_value=alert_value
    )
    
    notification = _generate_alert_notification(
        alert_id=alert_id,
        profile=profile,
        device_info=device_info,
        building_name=building_name,
        workorder_id=workorder["id"]
    )
    
    decision_log = _create_decision_log(
        alert_id=alert_id,
        device_id=device_id,
        alert_type=alert_type,
        profile=profile,
        analysis=analysis_result,
        workorder=workorder,
        risk_update=risk_update,
        building_id=building_id,
        building_name=building_name
    )
    
    result = {
        "success": True,
        "alert_id": alert_id,
        "device_id": device_id,
        "alert_type": alert_type,
        "alert_name": profile["name"],
        "severity": profile["severity"],
        "risk_level": profile["risk_level"],
        "building_id": building_id,
        "building_name": building_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis": analysis_result,
        "workorder": workorder,
        "risk_update": risk_update,
        "notification": notification,
        "decision_log": decision_log
    }
    
    PROCESSED_ALERTS.insert(0, result)
    if len(PROCESSED_ALERTS) > 200:
        PROCESSED_ALERTS.pop()
    
    return result


def _analyze_alert_with_agent(
    device_id: str,
    alert_type: str,
    alert_value: float,
    alert_unit: str,
    profile: Dict[str, Any],
    telemetry_history: List[Dict[str, Any]],
    device_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Agent分析告警原因和趋势
    """
    trend = _analyze_trend(telemetry_history)
    
    most_likely_causes = profile["possible_causes"][:2]
    if trend.get("is_rising", False):
        most_likely_causes.insert(0, "指标持续上升，问题可能在恶化")
    
    confidence = _calculate_confidence(alert_value, profile, telemetry_history)
    
    steps = [
        {"step": 1, "name": "告警接收", "description": f"接收到设备 {device_id} 的 {profile['name']} 告警"},
        {"step": 2, "name": "数据校验", "description": f"校验告警值：{alert_value}{alert_unit}，确认超过阈值"},
        {"step": 3, "name": "趋势分析", "description": f"分析历史数据：{trend['description']}"},
        {"step": 4, "name": "原因推断", "description": f"最可能的原因：{'; '.join(most_likely_causes)}"},
        {"step": 5, "name": "风险评估", "description": f"评估告警风险等级为 {profile['risk_level']}"},
        {"step": 6, "name": "生成方案", "description": "生成处置建议和工单"},
    ]
    
    return {
        "trend": trend,
        "most_likely_causes": most_likely_causes,
        "confidence": confidence,
        "immediate_actions": profile["immediate_actions"],
        "investigation_steps": profile["investigation_steps"],
        "analysis_steps": steps
    }


def _analyze_trend(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析遥测数据趋势
    """
    if not history or len(history) < 3:
        return {
            "is_rising": False,
            "is_falling": False,
            "description": "历史数据不足，无法判断趋势",
            "change_rate": 0
        }
    
    values = [h.get("value", 0) for h in history[-10:]]
    if len(values) < 3:
        return {
            "is_rising": False,
            "is_falling": False,
            "description": "数据点不足",
            "change_rate": 0
        }
    
    first_half = sum(values[:len(values)//2]) / (len(values)//2)
    second_half = sum(values[len(values)//2:]) / len(values[len(values)//2:])
    
    change_rate = (second_half - first_half) / first_half * 100 if first_half else 0
    
    is_rising = change_rate > 10
    is_falling = change_rate < -10
    
    if is_rising:
        description = f"指标呈上升趋势，近期增长约 {abs(change_rate):.1f}%"
    elif is_falling:
        description = f"指标呈下降趋势，近期下降约 {abs(change_rate):.1f}%"
    else:
        description = "指标相对稳定，波动较小"
    
    return {
        "is_rising": is_rising,
        "is_falling": is_falling,
        "description": description,
        "change_rate": round(change_rate, 1)
    }


def _calculate_confidence(
    alert_value: float,
    profile: Dict[str, Any],
    history: List[Dict[str, Any]]
) -> float:
    """
    计算告警置信度
    """
    confidence = 0.6
    
    if history and len(history) >= 5:
        recent_values = [h.get("value", 0) for h in history[-5:]]
        above_threshold = sum(1 for v in recent_values if v > alert_value * 0.8)
        if above_threshold >= 3:
            confidence += 0.2
    
    severity = profile.get("severity", "medium")
    if severity == "critical":
        confidence += 0.1
    
    return min(0.95, confidence)


def _generate_workorder(
    alert_id: str,
    device_id: str,
    alert_type: str,
    profile: Dict[str, Any],
    analysis: Dict[str, Any],
    device_info: Dict[str, Any],
    building_id: str,
    building_name: str
) -> Dict[str, Any]:
    """
    自动生成整改工单
    """
    device_name = device_info.get("name", device_id)
    location = device_info.get("location", building_name)
    
    deadline = (datetime.now() + timedelta(hours=profile.get("deadline_hours", 24))).strftime("%Y-%m-%d %H:%M")
    
    workorder_id = f"WO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    responsible_role = _get_responsible_role(profile["category"])
    
    actions = profile["immediate_actions"][:2]
    
    return {
        "id": workorder_id,
        "alert_id": alert_id,
        "device_id": device_id,
        "device_name": device_name,
        "title": f"{location}-{profile['name']}处置工单",
        "hazard": profile["hazard_type"],
        "hazard_type": alert_type,
        "location": location,
        "building_id": building_id,
        "building_name": building_name,
        "risk_level": profile["risk_level"],
        "risk_score": _estimate_risk_score(profile["severity"]),
        "priority": profile["priority"],
        "status": "待派单",
        "source": "设备告警自动生成",
        "alert_value": analysis.get("alert_value"),
        "confidence": analysis.get("confidence", 0.7),
        "responsible_role": responsible_role,
        "recommended_action": "；".join(actions),
        "investigation_steps": profile["investigation_steps"],
        "deadline": deadline,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auto_generated": True,
        "timeline": [
            {
                "status": "待派单",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator": "系统Agent",
                "note": f"设备告警自动生成：{profile['name']}，置信度{int(analysis.get('confidence', 0.7)*100)}%"
            }
        ]
    }


def _get_responsible_role(category: str) -> str:
    """
    根据告警类别获取责任人角色
    """
    roles = {
        "火灾预警": "应急小组 / 消防安全负责人",
        "电气安全": "电工 / 设备管理员",
        "消防设施": "消防设施管理员",
        "设备状态": "设备维护人员",
    }
    return roles.get(category, "区域安全责任人")


def _estimate_risk_score(severity: str) -> int:
    """
    根据严重程度估算风险分
    """
    if severity == "critical":
        return 85
    if severity == "high":
        return 65
    if severity == "medium":
        return 45
    return 25


def _update_risk_for_alert(
    building_id: str,
    alert_type: str,
    profile: Dict[str, Any],
    alert_value: float
) -> Dict[str, Any]:
    """
    更新建筑风险评分
    """
    try:
        from services.risk_update_service import update_risk_score
        
        base_score = 50
        
        result = update_risk_score(
            building_id=building_id,
            current_score=base_score,
            event_type="device_alert",
            event_data={
                "alert_type": alert_type,
                "alert_value": alert_value,
                "severity": profile["severity"]
            },
            operator="system",
            related_id=alert_type
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "score_change": 0
        }


def _generate_alert_notification(
    alert_id: str,
    profile: Dict[str, Any],
    device_info: Dict[str, Any],
    building_name: str,
    workorder_id: str
) -> Dict[str, Any]:
    """
    生成告警通知
    """
    device_name = device_info.get("name", "设备")
    location = device_info.get("location", building_name)
    
    levels = {
        "critical": ("danger", "严重"),
        "high": ("warning", "高"),
        "medium": ("warning", "中"),
        "low": ("info", "低")
    }
    level_type, level_text = levels.get(profile["severity"], ("info", "普通"))
    
    return {
        "id": f"NOTIFY-{alert_id}",
        "title": f"{level_text}级告警：{profile['name']}",
        "content": f"设备 [{device_name}] 发生 {profile['name']}，位置：{location}，请及时处理。",
        "level": level_type,
        "level_text": level_text,
        "source": "设备告警联动Agent",
        "related_id": workorder_id,
        "link": f"/workorders/{workorder_id}",
        "notify_roles": [_get_responsible_role(profile["category"]), "安全管理员"],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def _create_decision_log(
    alert_id: str,
    device_id: str,
    alert_type: str,
    profile: Dict[str, Any],
    analysis: Dict[str, Any],
    workorder: Dict[str, Any],
    risk_update: Dict[str, Any],
    building_id: str,
    building_name: str
) -> Dict[str, Any]:
    """
    创建设备告警决策日志
    """
    return {
        "id": f"DL-{alert_id}",
        "analysis_type": "alert_analysis",
        "title": f"{building_name}-{profile['name']}告警分析",
        "device_id": device_id,
        "alert_id": alert_id,
        "alert_type": alert_type,
        "location": building_name,
        "building_name": building_name,
        "building_id": building_id,
        "risk_score": workorder.get("risk_score", 50),
        "risk_level": profile["risk_level"],
        "risk_explanation": f"设备告警：{profile['name']}，{analysis.get('trend', {}).get('description', '请现场核实')}",
        "hazard_count": 1,
        "hazards": [
            {
                "name": profile["hazard_type"],
                "severity": _map_severity(profile["severity"]),
                "evidence": f"设备告警值异常，{analysis.get('trend', {}).get('description', '')}"
            }
        ],
        "recommendations": [
            {
                "action": action,
                "priority": profile["priority"],
                "responsible": workorder.get("responsible_role"),
                "timeframe": f"{profile.get('deadline_hours', 24)}小时内"
            }
            for action in profile["immediate_actions"]
        ],
        "analysis_steps": analysis.get("analysis_steps", []),
        "knowledge_refs": [],
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent_version": "AlertAgent v1.0"
    }


def _map_severity(severity: str) -> str:
    """
    映射严重程度到通用格式
    """
    if severity == "critical":
        return "A级"
    if severity == "high":
        return "B级"
    return "C级"


def get_processed_alerts(
    building_id: str = None,
    alert_type: str = None,
    severity: str = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    获取已处理的告警列表
    """
    alerts = PROCESSED_ALERTS
    
    if building_id:
        alerts = [a for a in alerts if a.get("building_id") == building_id]
    
    if alert_type:
        alerts = [a for a in alerts if a.get("alert_type") == alert_type]
    
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    
    alerts = alerts[:limit]
    
    return {
        "total": len(alerts),
        "items": alerts
    }


def get_alert_statistics() -> Dict[str, Any]:
    """
    获取告警统计信息
    """
    total = len(PROCESSED_ALERTS)
    critical = len([a for a in PROCESSED_ALERTS if a.get("severity") == "critical"])
    high = len([a for a in PROCESSED_ALERTS if a.get("severity") == "high"])
    medium = len([a for a in PROCESSED_ALERTS if a.get("severity") == "medium"])
    
    auto_workorder = len([a for a in PROCESSED_ALERTS if a.get("workorder", {}).get("auto_generated")])
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = len([a for a in PROCESSED_ALERTS if a.get("created_at", "").startswith(today)])
    
    return {
        "total": total,
        "today_count": today_count,
        "by_severity": {
            "critical": critical,
            "high": high,
            "medium": medium
        },
        "auto_workorder_count": auto_workorder,
        "auto_workorder_rate": round(auto_workorder / total * 100, 1) if total else 0
    }


def init_demo_alerts():
    """
    初始化演示用告警数据
    """
    if PROCESSED_ALERTS:
        return
    
    demo_devices = [
        {"id": "DEV-SM-001", "name": "1层烟感-01", "location": "综合办公楼A座1层", "type": "smoke_detector"},
        {"id": "DEV-TM-003", "name": "配电室温度传感器", "location": "综合办公楼A座B1层配电室", "type": "temperature"},
        {"id": "DEV-RC-005", "name": "3层剩余电流探测器", "location": "实验楼B座3层", "type": "remaining_current"},
        {"id": "DEV-PS-002", "name": "消防栓压力传感器", "location": "学生宿舍C区", "type": "pressure"},
    ]
    
    alert_types = ["smoke_high", "temperature_high", "remaining_current", "pressure_low"]
    
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(12):
        idx = i % len(demo_devices)
        device = demo_devices[idx]
        alert_type = alert_types[idx]
        
        event_time = base_time + timedelta(
            days=i // 2,
            hours=(i * 3) % 24,
            minutes=(i * 17) % 60
        )
        
        history = []
        for j in range(10):
            base_val = 50 + (i + j) * 5
            history.append({
                "value": base_val + j * 2,
                "timestamp": (event_time - timedelta(minutes=j * 10)).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        result = {
            "success": True,
            "alert_id": f"AL-DEMO-{i+1:04d}",
            "device_id": device["id"],
            "alert_type": alert_type,
            "alert_name": _get_alert_profile(alert_type)["name"],
            "severity": _get_alert_profile(alert_type)["severity"],
            "risk_level": _get_alert_profile(alert_type)["risk_level"],
            "building_id": f"building_{(i % 3) + 1:03d}",
            "building_name": ["综合办公楼A座", "实验楼B座", "学生宿舍C区"][i % 3],
            "created_at": event_time.strftime("%Y-%m-%d %H:%M:%S"),
            "analysis": {
                "trend": {"description": f"{'持续上升' if i % 2 == 0 else '波动较大'}", "is_rising": i % 2 == 0},
                "confidence": 0.7 + (i % 3) * 0.1
            },
            "workorder": {"id": f"WO-DEMO-{i+1:04d}", "auto_generated": True},
            "risk_update": {"new_score": 50 + (i % 4) * 15},
        }
        PROCESSED_ALERTS.append(result)
    
    PROCESSED_ALERTS.sort(key=lambda x: x["created_at"], reverse=True)
