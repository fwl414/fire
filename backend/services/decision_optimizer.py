from __future__ import annotations

from typing import Any, Dict, List


RESPONSIBLE_ROLE_MAP = {
    "消防通道堵塞": "楼层安全员 / 物业巡查人员",
    "可燃物堆积": "区域责任人 / 实验室管理员",
    "插座过载": "电工 / 设备管理员",
    "电线杂乱": "电工 / 设备管理员",
    "配电箱周围堆物": "电工 / 物业维修人员",
    "电动车违规充电": "宿管人员 / 安全管理员",
    "灭火器缺失": "消防设施管理员",
    "灭火器被遮挡": "区域责任人",
    "消防设施被遮挡": "消防设施管理员",
    "烟雾": "现场负责人 / 应急小组",
    "明火": "应急小组 / 消防安全负责人",
}


def optimize_emergency_decision(
    hazards: List[str],
    risk_score: int,
    risk_level: str,
    base_decision: Dict[str, Any],
    location: str = "",
) -> Dict[str, Any]:
    """
    对基础应急决策进行优化：
    - 明确处置优先级；
    - 给出建议时限；
    - 推断责任角色；
    - 给出升级条件；
    - 生成更适合工单闭环和答辩展示的结构。
    """
    if risk_level == "严重风险":
        deadline = "立即处置，建议 2 小时内完成初步整改或现场控制"
        escalation = "如出现明火、浓烟、人员被困或风险扩大，应立即报警并组织疏散。"
    elif risk_level == "高风险":
        deadline = "建议 24 小时内完成整改，整改后复查"
        escalation = "如隐患涉及电气异常、疏散受阻或重复发生，应升级为重点督办。"
    elif risk_level == "中风险":
        deadline = "建议 3 日内完成整改，并纳入后续巡检"
        escalation = "如整改逾期或隐患扩大，应升级为高风险工单。"
    else:
        deadline = "纳入日常巡检，按计划复查"
        escalation = "如出现新的高危隐患，应重新评估风险等级。"

    roles = []
    for h in hazards:
        role = RESPONSIBLE_ROLE_MAP.get(h)
        if role and role not in roles:
            roles.append(role)

    if not roles:
        roles = ["区域安全责任人"]

    optimized_actions = []
    for h in hazards:
        optimized_actions.append({
            "hazard": h,
            "responsible_role": RESPONSIBLE_ROLE_MAP.get(h, "区域安全责任人"),
            "recommended_deadline": deadline,
            "verification": "整改完成后拍照或记录复查结果，确认隐患已消除。",
        })

    return {
        "base_decision": base_decision,
        "optimized_priority": base_decision.get("priority", "中"),
        "recommended_deadline": deadline,
        "responsible_roles": roles,
        "hazard_action_map": optimized_actions,
        "escalation_condition": escalation,
        "closed_loop_required": risk_level in ["高风险", "严重风险"],
        "location": location,
        "optimization_reason": f"根据风险等级 {risk_level}、风险评分 {risk_score} 和隐患类型，补充责任角色、整改时限、复查要求和升级条件。",
    }
