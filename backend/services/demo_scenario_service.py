from __future__ import annotations

from typing import Any, Dict, List


DEMO_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "lab_blocked_exit",
        "title": "实验室消防通道堵塞",
        "location": "实验室A区",
        "description": "实验室门口消防通道被纸箱、桌椅和杂物堵塞，旁边堆放包装材料，影响人员疏散。",
        "tags": ["消防通道堵塞", "可燃物堆积", "疏散安全"],
        "risk_hint": "中高风险",
        "talking_point": "演示 Agent 如何识别通道堵塞和可燃物堆积，并生成整改闭环建议。"
    },
    {
        "id": "server_room_electrical",
        "title": "机房电气火灾隐患",
        "location": "机房B区",
        "description": "机房配电箱附近有焦糊味，多个插排串联，大功率设备同时使用，线缆缠绕且周边有纸箱。",
        "tags": ["插座过载", "电线杂乱", "配电箱周围堆物", "烟雾"],
        "risk_hint": "高风险",
        "talking_point": "演示多隐患叠加场景下的风险评分、RAG知识解释和应急决策优化。"
    },
    {
        "id": "dorm_ev_charging",
        "title": "宿舍电动车违规充电",
        "location": "宿舍楼一层",
        "description": "宿舍楼楼道内有电动车停放并飞线充电，充电线横跨通道，影响安全出口通行。",
        "tags": ["电动车违规充电", "消防通道堵塞"],
        "risk_hint": "高风险",
        "talking_point": "演示电动车违规充电风险识别和责任角色、整改时限生成。"
    },
    {
        "id": "teaching_extinguisher",
        "title": "教学楼灭火器被遮挡",
        "location": "教学楼三层走廊",
        "description": "走廊灭火器放置点被清洁工具和纸箱遮挡，灭火器标识不明显，紧急情况下不便取用。",
        "tags": ["灭火器被遮挡", "消防设施被遮挡"],
        "risk_hint": "中风险",
        "talking_point": "演示设施可见、可达、可操作的知识解释和学习题库推荐。"
    },
    {
        "id": "complex_multi_hazard",
        "title": "多隐患综合场景",
        "location": "综合楼地下空间",
        "description": "地下空间存在消防通道堆物、插排串联、电线杂乱、灭火器被遮挡和可燃物集中堆放等问题。",
        "tags": ["消防通道堵塞", "插座过载", "电线杂乱", "灭火器被遮挡", "可燃物堆积"],
        "risk_hint": "严重风险",
        "talking_point": "演示系统在复杂场景下的多源融合、风险解释和应急辅助决策能力。"
    }
]


def get_demo_scenarios() -> List[Dict[str, Any]]:
    return DEMO_SCENARIOS


def get_demo_scenario(scenario_id: str) -> Dict[str, Any]:
    for s in DEMO_SCENARIOS:
        if s["id"] == scenario_id:
            return s
    return {}
