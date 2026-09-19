from __future__ import annotations

from typing import Dict, List

# V1.0.0：面向消防巡检核心隐患的关键词识别。
# 规则识别不是为了替代视觉模型，而是作为演示和离线场景的稳定兜底。
KEYWORDS: Dict[str, List[str]] = {
    "明火": ["明火", "火苗", "起火", "燃烧", "着火", "火光"],
    "烟雾": ["烟雾", "冒烟", "浓烟", "焦糊味", "烧焦味", "异味"],
    "消防通道堵塞": [
        "通道堵塞", "消防通道", "疏散通道", "安全通道", "逃生通道", "楼梯间堆物", "楼梯口堆物",
        "堵住", "占用通道", "杂物堵塞", "通道堆放", "门口堆放", "出口堆物", "通行受阻"
    ],
    "灭火器遮挡": ["灭火器被遮挡", "灭火器遮挡", "挡住灭火器", "灭火器前堆放", "灭火器拿不到", "灭火器不便取用"],
    "灭火器缺失": ["灭火器缺失", "没有灭火器", "灭火器不见", "灭火器少", "未配置灭火器", "灭火器过期", "压力不足"],
    "消防栓遮挡": [
        "消防栓被遮挡", "消火栓被遮挡", "消防栓遮挡", "消火栓遮挡", "消防箱被挡", "消防栓门打不开",
        "消火栓门打不开", "水带被挡", "消防设施被遮挡", "遮挡消防"
    ],
    "电动车违规停放": ["电动车", "电瓶车", "飞线", "违规充电", "楼道充电", "室内充电", "电动车停放", "电动车违规停放"],
    "可燃物堆积": ["纸箱", "纸盒", "可燃物", "杂物堆放", "塑料", "木板", "泡沫", "包装箱", "易燃物", "纸板", "垃圾堆放"],
    "应急出口锁闭": ["安全出口锁闭", "应急出口锁闭", "出口上锁", "逃生门锁闭", "安全门锁闭", "安全出口打不开", "出口被锁"],
    "安全标识缺失": ["安全标识缺失", "疏散指示缺失", "应急标识缺失", "标识不清", "指示牌缺失", "安全出口标识缺失", "标志损坏"],
    "电气线路杂乱": [
        "电线杂乱", "电线凌乱", "线路杂乱", "乱拉电线", "线缆杂乱", "私拉乱接", "电线缠绕", "电气线路杂乱",
        "插座过载", "插排串联", "多个插排", "超负荷", "大功率", "多孔插座", "插线板串联", "拖线板串联"
    ],
    "配电箱周围堆物": ["配电箱周围", "配电箱旁", "配电箱附近", "电箱旁边", "电柜旁", "配电柜前堆物"],
}

ALIASES = {
    "消防设施被遮挡": "消防栓遮挡",
    "消火栓遮挡": "消防栓遮挡",
    "消火栓被遮挡": "消防栓遮挡",
    "灭火器被遮挡": "灭火器遮挡",
    "电线杂乱": "电气线路杂乱",
    "插座过载": "电气线路杂乱",
    "电动车违规充电": "电动车违规停放",
}


def canonical_hazard(name: str) -> str:
    name = (name or "").strip()
    return ALIASES.get(name, name)


def analyze_text(description: str):
    text = description or ""
    hazards: List[str] = []
    reasons: List[str] = []
    evidence = {}

    for hazard, words in KEYWORDS.items():
        normalized = canonical_hazard(hazard)
        for word in words:
            if word in text:
                if normalized not in hazards:
                    hazards.append(normalized)
                evidence[normalized] = word
                reasons.append(f"文本中出现“{word}”，判断可能存在“{normalized}”。")
                break

    return {
        "hazards": hazards,
        "description": "已根据巡检文字描述抽取消防隐患。" if hazards else "未从文字中发现明显消防隐患。",
        "risk_reasons": reasons,
        "evidence": evidence,
    }


def merge_hazards(*lists):
    result: List[str] = []
    for item_list in lists:
        for h in item_list or []:
            normalized = canonical_hazard(str(h))
            if normalized and normalized not in result:
                result.append(normalized)
    return result
