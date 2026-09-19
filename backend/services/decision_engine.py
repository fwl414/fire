from __future__ import annotations

from typing import Dict, List, Any


def build_emergency_decision(hazards: List[str], risk_score: int, risk_level: str) -> Dict[str, Any]:
    immediate_actions: List[str] = []
    rectification_actions: List[str] = []
    follow_up_actions: List[str] = []

    need_alarm = False
    need_evacuation = False
    need_ticket = risk_level in ["高风险", "严重风险"]
    priority = "低"

    if risk_level == "严重风险":
        priority = "紧急"
    elif risk_level == "高风险":
        priority = "高"
    elif risk_level == "中风险":
        priority = "中"

    if "明火" in hazards:
        need_alarm = True
        need_evacuation = True
        immediate_actions.append("立即启动火情应急响应，疏散附近人员，在确保安全前提下使用合适灭火器材处置。")
    if "烟雾" in hazards:
        need_evacuation = True
        immediate_actions.append("立即排查烟雾来源，切断疑似区域电源，组织人员远离风险区域。")
    if "消防通道堵塞" in hazards:
        immediate_actions.append("立即清理消防通道和疏散通道，确保人员疏散和消防救援通行。")
        follow_up_actions.append("将该区域纳入重点巡查，复查通道是否再次被占用。")
    if "电动车违规充电" in hazards:
        immediate_actions.append("立即停止电动车违规充电，将车辆移至指定集中充电区域。")
        rectification_actions.append("完善电动车集中充电管理制度和警示标识。")
    if "插座过载" in hazards or "电线杂乱" in hazards:
        immediate_actions.append("停止超负荷用电和违规接线，必要时切断相关电源。")
        rectification_actions.append("由专业人员复核用电负荷并规范线路敷设。")
    if "配电箱周围堆物" in hazards:
        immediate_actions.append("清理配电箱周边堆放物，保留检修和应急操作空间。")
    if "可燃物堆积" in hazards:
        rectification_actions.append("清理纸箱、塑料等可燃物，远离电源、配电箱和热源。")
    if "灭火器缺失" in hazards:
        rectification_actions.append("按要求补齐灭火器，并登记位置、型号和有效期。")
    if "灭火器被遮挡" in hazards or "消防设施被遮挡" in hazards:
        immediate_actions.append("移除消防设施周边遮挡物，确保设施可见、可达、可操作。")

    if need_ticket:
        follow_up_actions.append("自动生成整改工单，由消防安全责任人跟踪整改闭环。")
    if risk_level in ["高风险", "严重风险"]:
        follow_up_actions.append("整改完成后 24 小时内复查，并保留复查记录。")
    else:
        follow_up_actions.append("纳入日常巡检记录，按计划复查。")

    if not immediate_actions:
        immediate_actions.append("现场暂未发现需要立即处置的紧急火情，继续保持巡查。")
    if not rectification_actions:
        rectification_actions.append("保持消防设施完好、通道畅通和用电规范。")

    return {
        "priority": priority,
        "need_alarm": need_alarm,
        "need_evacuation": need_evacuation,
        "need_ticket": need_ticket,
        "immediate_actions": immediate_actions,
        "rectification_actions": rectification_actions,
        "follow_up_actions": follow_up_actions,
        "decision_reason": f"依据隐患数量、风险评分 {risk_score} 和风险等级 {risk_level} 生成分级处置建议。",
    }


def decision_to_text(decision: Dict[str, Any]) -> str:
    def block(title: str, items: List[str]) -> str:
        return title + "\n" + "\n".join([f"{i + 1}. {x}" for i, x in enumerate(items)])

    return "\n\n".join([
        f"处置优先级：{decision.get('priority')}",
        f"是否建议报警：{'是' if decision.get('need_alarm') else '否'}",
        f"是否建议疏散：{'是' if decision.get('need_evacuation') else '否'}",
        f"是否生成工单：{'是' if decision.get('need_ticket') else '否'}",
        block("一、立即处置措施", decision.get("immediate_actions", [])),
        block("二、短期整改措施", decision.get("rectification_actions", [])),
        block("三、后续复查措施", decision.get("follow_up_actions", [])),
        f"决策依据：{decision.get('decision_reason', '')}",
    ])
