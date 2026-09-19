from __future__ import annotations

from typing import Any, Dict, List


def _contains(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)


def build_manual_answer(question: str, base_answer: str = "", references: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    text = f"{question} {base_answer}"
    refs = references or []
    need_workorder = True
    deadline = "高风险立即处理，中风险限期整改，低风险纳入日常巡检。"
    first_actions = [
        "立即确认现场风险点，必要时疏散无关人员。",
        "拍照留证，记录地点、时间、责任区域和现场状态。",
        "按风险等级启动整改或应急处置流程。",
    ]
    forbidden = [
        "不要只口头提醒而不记录、不复查。",
        "不要在风险未解除前继续扩大使用现场设备。",
        "不要遮挡消防设施、占用疏散通道或安全出口。",
    ]
    notify = ["现场负责人", "消防安全管理员", "区域责任人"]
    rectification = [
        "明确整改责任人和截止时间。",
        "上传整改前后照片或现场复查记录。",
        "复查通过后更新为已闭环并归档。",
    ]
    conclusion = "该问题涉及消防安全隐患，应及时处置并形成整改闭环。"
    learning = "处理消防问题时，要按“先控险、再通知、再整改、后复查”的顺序理解，重点是依据、时限和闭环留痕。"

    if _contains(text, ["通道", "安全出口", "疏散"]):
        conclusion = "消防通道或安全出口被占用会影响人员疏散和消防救援，应立即清理。"
        first_actions = ["立即移除通道内纸箱、杂物、车辆等障碍物。", "确认疏散指示、应急照明和出口门可正常使用。", "拍摄整改前后照片并登记复查结果。"]
        forbidden = ["禁止继续堆放物品或临时占用疏散通道。", "禁止锁闭、遮挡安全出口。", "禁止整改后不复查。"]
        notify = ["楼层安全员", "物业巡查人员", "消防安全管理员"]
        deadline = "建议立即整改；高风险场景应当天完成复查。"
    elif _contains(text, ["电气", "插排", "过载", "线路", "电线"]):
        conclusion = "电气火灾风险通常来自过载、短路、线路老化或违规用电，应先断开风险电源。"
        first_actions = ["停止使用异常插排、线路或设备。", "由电工检查负载、温升、绝缘和漏电保护。", "对老化线路、串联插排和违规用电进行整改。"]
        forbidden = ["禁止带电拆修非专业电气设备。", "禁止插排串联和超负荷运行。", "电气火灾风险未解除前禁止恢复使用。"]
        notify = ["电工", "设备管理员", "消防安全管理员"]
        deadline = "高风险应立即停用并在 24 小时内完成整改复查。"
    elif _contains(text, ["烟感", "报警", "烟雾", "明火"]):
        conclusion = "烟感报警应先确认是否真实火情，同时保护人员安全并启动应急流程。"
        first_actions = ["立即派人到报警位置核查烟雾、明火或异常气味。", "必要时切断局部电源，组织人员疏散。", "无法确认安全时拨打 119 并启动单位应急预案。"]
        forbidden = ["禁止未核查就直接消音或复位。", "禁止人员聚集围观。", "禁止在烟雾来源不明时继续使用相关设备。"]
        notify = ["现场负责人", "应急小组", "消防控制室或安全管理员"]
        deadline = "报警事件应立即处置，处置后必须复盘和登记。"
    elif _contains(text, ["灭火器", "消防栓", "消防设施"]):
        conclusion = "消防设施被遮挡、缺失或压力异常会影响初期火灾处置，应及时恢复可见、可达、可用。"
        first_actions = ["核查设施位置、压力、铅封、有效期和周边遮挡。", "移除遮挡物或补齐缺失设施。", "更新设施巡检记录并安排复查。"]
        forbidden = ["禁止遮挡消防设施。", "禁止使用过期或压力不足的灭火器。", "禁止设施异常后不登记。"]
        notify = ["消防设施管理员", "区域责任人", "安全管理员"]
        deadline = "影响可用性的异常建议当天处理，严重缺失应立即补齐。"
    elif _contains(text, ["学习", "考试", "解释"]):
        need_workorder = False
        conclusion = "该问题更适合按消防知识点学习，重点理解风险原因、判断标准和处置顺序。"
        deadline = "学习类问题不需要整改时限，可作为培训记录。"

    basis_titles = [r.get("title") or r.get("source") for r in refs[:3] if r.get("title") or r.get("source")]
    basis = "；".join(basis_titles) if basis_titles else "可参考消防法规、单位消防安全制度、巡检标准和系统 RAG 知识库条目。"
    return {
        "conclusion": conclusion,
        "first_actions": first_actions,
        "forbidden_actions": forbidden,
        "notify_roles": notify,
        "deadline": deadline,
        "basis": basis,
        "need_workorder": need_workorder,
        "rectification_steps": rectification,
        "learning_explanation": learning,
    }
