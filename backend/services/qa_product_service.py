from __future__ import annotations
from typing import Any, Dict, List

SCENE_TEMPLATES = [
    {"mode": "emergency", "title": "应急处置模式", "question": "烟感报警后怎么处置？", "description": "先处置现场风险，再判断是否报警和疏散。"},
    {"mode": "law", "title": "法规依据模式", "question": "消防通道堵塞违反了哪些管理要求？", "description": "突出依据、责任和管理要求。"},
    {"mode": "rectification", "title": "整改建议模式", "question": "消防通道堵塞怎么处理？", "description": "输出责任人、整改期限、复查要求。"},
    {"mode": "learning", "title": "学习解释模式", "question": "电气火灾如何预防？", "description": "用更适合学习的方式解释原因和预防方法。"},
]

FAQ_CARDS = [
    {"question": "消防通道堵塞怎么处理？", "scene": "疏散通道", "mode": "rectification"},
    {"question": "电气火灾如何预防？", "scene": "电气安全", "mode": "learning"},
    {"question": "实验室发现异味怎么办？", "scene": "实验室安全", "mode": "emergency"},
    {"question": "烟感报警后怎么处置？", "scene": "应急处置", "mode": "emergency"},
]


def _ref_titles(refs: List[Dict[str, Any]]) -> str:
    titles = [r.get("title") or r.get("source") for r in refs[:3] if r.get("title") or r.get("source")]
    return "、".join([f"《{t}》" for t in titles]) or "系统消防知识库相关条目"


def build_answer_cards(question: str, answer: str, refs: List[Dict[str, Any]], mode: str = "rectification") -> Dict[str, Any]:
    q = question or ""
    refs_text = _ref_titles(refs)
    lower = q + answer
    urgent = any(k in lower for k in ["烟", "明火", "异味", "报警", "火灾"])
    electrical = any(k in lower for k in ["电气", "插座", "插排", "电线", "配电"])
    lane = any(k in lower for k in ["通道", "出口", "疏散"])

    first_steps = ["确认现场是否存在明火、烟雾、人员被困等紧急情况。"]
    if electrical:
        first_steps.append("在确保安全前提下切断相关电源，禁止未断电直接用水扑救。")
    if lane:
        first_steps.append("立即清理通道和安全出口障碍物，恢复疏散宽度和救援通道。")
    if urgent:
        first_steps.append("通知现场负责人和消防安全责任人，必要时启动应急预案并拨打 119。")
    first_steps.append("拍照留存整改前证据，并在系统中生成巡检记录或整改工单。")

    forbid = ["不要只口头提醒后不留痕。", "不要在未确认电源状态时贸然处置电气火灾。", "不要占用、锁闭、遮挡疏散通道和消防设施。"]
    notify = "现场负责人、区域安全员、消防安全管理员"
    if electrical:
        notify += "、电工/设备管理员"
    deadline = "高风险建议立即处理；中风险建议 3 日内整改；低风险纳入日常巡检。"
    need_order = urgent or electrical or lane or any(k in lower for k in ["高风险", "严重", "整改"])

    return {
        "mode": mode,
        "one_sentence": "该问题应按消防安全隐患处理，先保障人员安全，再清除风险源，并形成整改闭环。",
        "manual_cards": [
            {"title": "先做什么", "items": first_steps, "type": "primary"},
            {"title": "禁止做什么", "items": forbid, "type": "danger"},
            {"title": "通知谁", "items": [notify], "type": "warning"},
            {"title": "多久内整改", "items": [deadline], "type": "info"},
            {"title": "依据是什么", "items": [f"可参考 {refs_text}。"], "type": "success"},
            {"title": "是否需要生成工单", "items": ["建议生成整改工单并复查闭环。" if need_order else "可作为巡检记录留痕，视现场情况生成工单。"], "type": "primary"},
        ],
        "keywords": [k for k in ["消防通道", "电气火灾", "烟感报警", "整改闭环", "RAG依据", "人工复核"] if k in lower or k in q] or ["消防安全", "整改闭环", "RAG依据"],
    }
