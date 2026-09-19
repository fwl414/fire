from __future__ import annotations

from typing import Dict, List, Any

ALIASES = {
    "消防设施被遮挡": "消防栓遮挡",
    "消火栓遮挡": "消防栓遮挡",
    "消火栓被遮挡": "消防栓遮挡",
    "灭火器被遮挡": "灭火器遮挡",
    "电线杂乱": "电气线路杂乱",
    "插座过载": "电气线路杂乱",
    "电动车违规充电": "电动车违规停放",
}

HAZARD_PROFILES: Dict[str, Dict[str, Any]] = {
    "明火": {
        "score": 50,
        "severity": "严重",
        "risk_level": "严重风险",
        "category": "火情",
        "reason": "现场存在明火，可能快速引燃周边可燃物并扩大火势。",
        "consequence": "可能造成人员伤害、火势扩大和财产损失。",
        "measure": "立即启动应急处置，疏散附近人员，切断相关电源，在确保安全前提下使用灭火器扑救并报警。",
        "immediate": True,
    },
    "烟雾": {
        "score": 40,
        "severity": "严重",
        "risk_level": "严重风险",
        "category": "火情",
        "reason": "现场出现烟雾或焦糊味，可能存在初期火灾、电气短路或阴燃风险。",
        "consequence": "可能发展为明火并影响人员疏散。",
        "measure": "立即排查烟雾来源，切断疑似区域电源，通知消防安全责任人并准备疏散。",
        "immediate": True,
    },
    "消防通道堵塞": {
        "score": 30,
        "severity": "高",
        "risk_level": "高风险",
        "category": "疏散通道",
        "reason": "消防通道或疏散通道被占用会影响人员逃生和消防救援进入。",
        "consequence": "火灾时可能延误疏散和救援，扩大人员伤亡风险。",
        "measure": "立即清理通道内杂物，设置禁止堆放提示标识，并纳入重点巡检。",
        "immediate": True,
    },
    "灭火器遮挡": {
        "score": 22,
        "severity": "中",
        "risk_level": "中风险",
        "category": "消防设施",
        "reason": "灭火器被遮挡会影响紧急情况下快速取用。",
        "consequence": "初期火灾时可能错过最佳扑救时机。",
        "measure": "清除遮挡物，保持灭火器位置明显、便于取用，并检查压力表和有效期。",
        "immediate": False,
    },
    "灭火器缺失": {
        "score": 26,
        "severity": "高",
        "risk_level": "高风险",
        "category": "消防设施",
        "reason": "灭火器缺失会影响初期火灾扑救能力。",
        "consequence": "初期火情无法及时控制，可能导致火势扩大。",
        "measure": "按场所火灾类别和危险等级补齐灭火器，并登记位置、型号和有效期。",
        "immediate": True,
    },
    "消防栓遮挡": {
        "score": 28,
        "severity": "高",
        "risk_level": "高风险",
        "category": "消防设施",
        "reason": "消火栓或消防箱被遮挡会影响灭火供水和消防救援效率。",
        "consequence": "火灾时消防设施无法及时启用，影响扑救。",
        "measure": "立即清理消火栓周边遮挡物，确保箱门可开启、水带水枪齐全可用。",
        "immediate": True,
    },
    "电动车违规停放": {
        "score": 35,
        "severity": "高",
        "risk_level": "高风险",
        "category": "电动车安全",
        "reason": "电动车违规停放或充电容易引发电池热失控和火灾蔓延。",
        "consequence": "可能产生猛烈燃烧、浓烟和快速蔓延。",
        "measure": "立即停止违规充电，将电动车移至集中停放充电区域，并检查充电线路。",
        "immediate": True,
    },
    "可燃物堆积": {
        "score": 20,
        "severity": "中",
        "risk_level": "中风险",
        "category": "可燃物管理",
        "reason": "纸箱、塑料、木板等可燃物堆积会增加火灾荷载。",
        "consequence": "一旦起火可能加速蔓延，并产生大量烟气。",
        "measure": "及时清理可燃杂物，远离电源、配电箱和热源，保持安全间距。",
        "immediate": False,
    },
    "应急出口锁闭": {
        "score": 34,
        "severity": "高",
        "risk_level": "高风险",
        "category": "疏散通道",
        "reason": "安全出口或应急出口锁闭会直接影响人员紧急疏散。",
        "consequence": "火灾时可能导致人员无法快速逃生。",
        "measure": "立即解除锁闭或障碍，确保安全出口保持可开启状态，并安排复查。",
        "immediate": True,
    },
    "安全标识缺失": {
        "score": 14,
        "severity": "中",
        "risk_level": "中风险",
        "category": "疏散通道",
        "reason": "安全出口或疏散指示标识缺失会影响紧急情况下路径识别。",
        "consequence": "烟雾环境下可能造成疏散方向混乱。",
        "measure": "补齐或修复疏散指示、安全出口和应急照明标识，确保清晰可见。",
        "immediate": False,
    },
    "电气线路杂乱": {
        "score": 24,
        "severity": "高",
        "risk_level": "高风险",
        "category": "电气安全",
        "reason": "私拉乱接、插排串联或线路杂乱可能造成短路、过热和电气火灾。",
        "consequence": "可能引发电气火灾，并伴随触电风险。",
        "measure": "停止违规用电，取消插排串联，由专业人员整理线路并核查用电容量。",
        "immediate": True,
    },
    "配电箱周围堆物": {
        "score": 18,
        "severity": "中",
        "risk_level": "中风险",
        "category": "电气安全",
        "reason": "配电箱周围堆物影响操作检修，也可能增加电气火灾风险。",
        "consequence": "紧急断电和检修受阻，周边可燃物可能被引燃。",
        "measure": "清空配电箱周边区域，保留检修和应急操作空间。",
        "immediate": False,
    },
}


def canonical_hazard(name: str) -> str:
    return ALIASES.get((name or "").strip(), (name or "").strip())


def normalize_hazards(hazards: List[str]) -> List[str]:
    unique: List[str] = []
    for h in hazards or []:
        normalized = canonical_hazard(str(h))
        if normalized and normalized not in unique:
            unique.append(normalized)
    return unique


def _default_profile(hazard: str) -> Dict[str, Any]:
    return {
        "score": 8,
        "severity": "低",
        "risk_level": "低风险",
        "category": "其他",
        "reason": f"系统识别到疑似消防安全隐患：{hazard}。",
        "consequence": "可能造成管理风险或局部安全隐患。",
        "measure": "建议现场复核并按消防安全管理要求整改。",
        "immediate": False,
    }


def build_hazard_items(hazards: List[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for h in normalize_hazards(hazards):
        profile = HAZARD_PROFILES.get(h, _default_profile(h))
        items.append({
            "type": h,
            "hazard_name": h,
            "category": profile["category"],
            "severity": profile["severity"],
            "risk_level": profile["risk_level"],
            "score": profile["score"],
            "reason": profile["reason"],
            "evidence": profile["reason"],
            "possible_consequence": profile["consequence"],
            "measure": profile["measure"],
            "suggestion": profile["measure"],
            "need_immediate_fix": bool(profile.get("immediate")),
        })
    return items


def calculate_risk(hazards: List[str]) -> Dict[str, Any]:
    unique = normalize_hazards(hazards)
    items = build_hazard_items(unique)
    raw_score = sum(item["score"] for item in items)

    # 多隐患叠加修正：隐患越多，风险耦合越明显，但总分仍封顶 100。
    if len(items) >= 5:
        raw_score += 10
    elif len(items) >= 3:
        raw_score += 6

    has_emergency = any(item["type"] in ["明火", "烟雾"] for item in items)
    has_high_direct = any(item.get("need_immediate_fix") and item["score"] >= 28 for item in items)
    score = min(int(raw_score), 100)

    if has_emergency or score >= 85:
        level = "严重风险"
        label = "critical"
    elif score >= 60 or (has_high_direct and score >= 45):
        level = "高风险"
        label = "high"
    elif score >= 25:
        level = "中风险"
        label = "medium"
    else:
        level = "低风险"
        label = "low"

    categories: Dict[str, int] = {}
    for item in items:
        categories[item["category"]] = categories.get(item["category"], 0) + 1

    return {
        "hazards": unique,
        "hazard_items": items,
        "risk_score": score,
        "risk_level": level,
        "risk_label": label,
        "score_detail": {item["type"]: item["score"] for item in items},
        "category_stats": categories,
        "risk_reason": build_risk_reason(items, level),
    }


def build_risk_reason(items: List[Dict[str, Any]], level: str) -> str:
    if not items:
        return "未识别到明显消防安全隐患，当前风险较低。"
    top = sorted(items, key=lambda x: x["score"], reverse=True)[:3]
    names = "、".join([x["type"] for x in top])
    return f"系统综合识别到 {len(items)} 项隐患，主要风险包括：{names}。综合判定为{level}。"
