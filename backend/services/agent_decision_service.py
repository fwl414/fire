from __future__ import annotations

from typing import Any, Dict, List


RISK_COLOR_MAP = {
    "低风险": {"color": "#67C23A", "tag_type": "success", "level": "低风险"},
    "中风险": {"color": "#E6A23C", "tag_type": "warning", "level": "中风险"},
    "高风险": {"color": "#F56C6C", "tag_type": "danger", "level": "高风险"},
    "严重风险": {"color": "#8B0000", "tag_type": "danger", "level": "严重风险"},
    "未评估": {"color": "#909399", "tag_type": "info", "level": "未评估"},
}


def normalize_risk_level(level: str = "", score: float = 0) -> str:
    level = level or ""
    if "严重" in level:
        return "严重风险"
    if "高" in level:
        return "高风险"
    if "中" in level:
        return "中风险"
    if "低" in level:
        return "低风险"
    try:
        score = float(score or 0)
    except Exception:
        score = 0
    if score >= 85:
        return "严重风险"
    if score >= 65:
        return "高风险"
    if score >= 35:
        return "中风险"
    if score > 0:
        return "低风险"
    return "未评估"


def get_risk_style(level: str = "", score: float = 0) -> Dict[str, Any]:
    normalized = normalize_risk_level(level, score)
    return RISK_COLOR_MAP.get(normalized, RISK_COLOR_MAP["未评估"])


def make_decision_policy(risk_level: str = "", risk_score: float = 0, hazards: List[str] | None = None) -> Dict[str, Any]:
    hazards = hazards or []
    level = normalize_risk_level(risk_level, risk_score)
    urgent_hazards = {"明火", "烟雾", "电动车违规充电", "插座过载", "配电箱周围堆物"}
    has_urgent_hazard = any(h in urgent_hazards for h in hazards)

    if level == "严重风险":
        policy = {
            "risk_level": level,
            "risk_style": get_risk_style(level, risk_score),
            "need_immediate_action": True,
            "need_generate_workorder": True,
            "need_notify_responsible_person": True,
            "need_review": True,
            "need_learning_recommendation": True,
            "trigger_emergency_process": True,
            "deadline": "2小时内完成初步处置，24小时内完成复查",
            "decision_summary": "严重风险：建议立即处置，必要时停用相关区域，并通知消防安全负责人。"
        }
    elif level == "高风险" or has_urgent_hazard:
        policy = {
            "risk_level": "高风险" if level != "严重风险" else level,
            "risk_style": get_risk_style("高风险", risk_score),
            "need_immediate_action": True,
            "need_generate_workorder": True,
            "need_notify_responsible_person": True,
            "need_review": True,
            "need_learning_recommendation": True,
            "trigger_emergency_process": has_urgent_hazard,
            "deadline": "24小时内完成整改，整改后复查",
            "decision_summary": "高风险：建议生成整改工单并通知责任人，优先完成整改和复查。"
        }
    elif level == "中风险":
        policy = {
            "risk_level": level,
            "risk_style": get_risk_style(level, risk_score),
            "need_immediate_action": False,
            "need_generate_workorder": True,
            "need_notify_responsible_person": False,
            "need_review": True,
            "need_learning_recommendation": True,
            "trigger_emergency_process": False,
            "deadline": "3日内完成整改并复查",
            "decision_summary": "中风险：建议生成普通整改工单，并在规定时间内完成复查。"
        }
    elif level == "低风险":
        policy = {
            "risk_level": level,
            "risk_style": get_risk_style(level, risk_score),
            "need_immediate_action": False,
            "need_generate_workorder": False,
            "need_notify_responsible_person": False,
            "need_review": False,
            "need_learning_recommendation": True,
            "trigger_emergency_process": False,
            "deadline": "纳入日常巡检",
            "decision_summary": "低风险：记录巡检结果，纳入日常检查和知识学习即可。"
        }
    else:
        policy = {
            "risk_level": "未评估",
            "risk_style": get_risk_style("未评估", 0),
            "need_immediate_action": False,
            "need_generate_workorder": False,
            "need_notify_responsible_person": False,
            "need_review": False,
            "need_learning_recommendation": False,
            "trigger_emergency_process": False,
            "deadline": "-",
            "decision_summary": "当前未形成明确风险结论。"
        }

    policy["decision_items"] = [
        {"label": "是否需要立即处理", "value": policy["need_immediate_action"]},
        {"label": "是否需要生成工单", "value": policy["need_generate_workorder"]},
        {"label": "是否需要通知负责人", "value": policy["need_notify_responsible_person"]},
        {"label": "是否需要复查", "value": policy["need_review"]},
        {"label": "是否推荐学习内容", "value": policy["need_learning_recommendation"]},
        {"label": "是否触发应急流程", "value": policy["trigger_emergency_process"]},
    ]
    return policy
