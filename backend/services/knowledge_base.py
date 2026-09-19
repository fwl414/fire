from __future__ import annotations

from typing import List, Dict, Any


KNOWLEDGE: List[Dict[str, Any]] = [
    {
        "title": "消防通道与疏散通道管理",
        "keywords": ["消防通道", "疏散通道", "通道堵塞", "安全出口", "逃生通道"],
        "content": "消防通道、疏散通道和安全出口应保持畅通，不得堆放杂物、停放车辆或设置影响疏散的障碍物。发现堵塞应立即清理，并建立巡查台账。",
        "scene": "疏散安全"
    },
    {
        "title": "电气火灾处置原则",
        "keywords": ["电气火灾", "插座", "插排", "电线", "配电箱", "短路", "超负荷"],
        "content": "电气火灾处置应优先切断电源，严禁在未断电情况下直接用水扑救。可使用干粉灭火器或二氧化碳灭火器，并通知专业人员排查线路。",
        "scene": "电气安全"
    },
    {
        "title": "可燃物堆放管理",
        "keywords": ["纸箱", "可燃物", "杂物", "易燃物", "泡沫", "塑料"],
        "content": "纸箱、塑料、木板等可燃物应远离电源、配电箱和热源。仓库、实验室、机房等场景应控制堆放数量并保持安全间距。",
        "scene": "可燃物管理"
    },
    {
        "title": "灭火器配置与维护",
        "keywords": ["灭火器", "缺失", "遮挡", "压力", "有效期"],
        "content": "灭火器应放置在明显、便于取用的位置，定期检查压力表、铅封、喷管和有效期，严禁被遮挡、挪用或长期缺失。",
        "scene": "设施管理"
    },
    {
        "title": "消火栓与消防设施可用性",
        "keywords": ["消火栓", "消防栓", "消防设施", "遮挡", "消防箱"],
        "content": "消火栓、消防箱和报警按钮等消防设施应保持完好可用，周边不得堆放物品，箱门应能正常开启。",
        "scene": "设施管理"
    },
    {
        "title": "电动车违规充电风险",
        "keywords": ["电动车", "电瓶车", "违规充电", "飞线", "室内充电"],
        "content": "电动车及蓄电池不得在楼道、疏散通道、安全出口或室内违规停放充电，应在集中充电区域规范充电，避免热失控和火灾蔓延。",
        "scene": "电气安全"
    },
    {
        "title": "初期火情应急处置",
        "keywords": ["明火", "烟雾", "冒烟", "火灾", "疏散", "报警"],
        "content": "发现明火、烟雾或焦糊味时，应立即确认险情，切断相关电源，组织人员疏散，使用合适灭火器材处置初期火灾，必要时拨打 119。",
        "scene": "应急处置"
    },
]


def search_knowledge(query: str, hazards=None, limit: int = 4):
    text = (query or "") + " " + " ".join(hazards or [])
    scored = []
    for item in KNOWLEDGE:
        score = 0
        for kw in item["keywords"]:
            if kw in text:
                score += 2
        if item.get("scene", "") in text:
            score += 1
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:limit]] or KNOWLEDGE[:3]


def answer_question(question: str):
    refs = search_knowledge(question)
    content = "\n".join([f"【{x['title']}】{x['content']}" for x in refs])

    answer = (
        "根据系统消防知识库检索结果，建议如下：\n\n"
        f"{content}\n\n"
        "处置原则：先确保人员安全，再判断是否需要切断电源、清理通道、隔离可燃物或通知消防安全责任人。"
        "如果现场已出现明火、烟雾、刺激性气味或人员被困，应立即启动应急预案并报警。"
    )

    return {
        "answer": answer,
        "references": refs,
        "retrieval_count": len(refs),
        "agent_steps": [
            "接收用户消防安全问题。",
            "从消防知识库中检索相关条目。",
            "结合检索结果生成面向现场处置的回答。",
        ]
    }
