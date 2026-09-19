from __future__ import annotations

from typing import Any, Dict, List

from services.learning_service import get_courses, get_videos


HAZARD_KEYWORDS = {
    "消防通道堵塞": ["消防通道", "疏散", "安全出口", "通道"],
    "可燃物堆积": ["可燃物", "火灾荷载", "堆放", "纸箱"],
    "插座过载": ["电气", "插座", "插排", "过载"],
    "电线杂乱": ["电气", "电线", "线缆"],
    "配电箱周围堆物": ["配电箱", "电气", "可燃物"],
    "电动车违规充电": ["电动车", "飞线充电", "热失控"],
    "灭火器缺失": ["灭火器", "设施"],
    "灭火器被遮挡": ["灭火器", "遮挡", "设施"],
    "消防设施被遮挡": ["消防设施", "消火栓", "灭火器", "遮挡"],
    "烟雾": ["烟雾", "初期火灾", "报警"],
    "明火": ["明火", "初期火灾", "报警"],
}


def recommend_learning_for_hazards(hazards: List[str], limit: int = 4) -> Dict[str, Any]:
    hazards = hazards or []
    keywords: List[str] = []
    for h in hazards:
        keywords.extend(HAZARD_KEYWORDS.get(h, [h]))

    def score_text(text: str) -> int:
        score = 0
        for k in keywords:
            if k and k in text:
                score += 4
        for h in hazards:
            if h and h in text:
                score += 6
        return score

    courses = []
    for c in get_courses():
        hay = " ".join([
            c.get("title", ""),
            c.get("category", ""),
            c.get("summary", ""),
            " ".join(c.get("knowledge_points", [])),
            " ".join(c.get("related_hazards", [])),
        ])
        score = score_text(hay)
        if score > 0:
            item = dict(c)
            item["score"] = score
            courses.append(item)

    videos = []
    for v in get_videos():
        hay = " ".join([
            v.get("title", ""),
            v.get("topic", ""),
            v.get("description", ""),
            " ".join(v.get("keywords", [])),
        ])
        score = score_text(hay)
        if score > 0:
            item = dict(v)
            item["score"] = score
            videos.append(item)

    courses = sorted(courses, key=lambda x: x["score"], reverse=True)[:limit]
    videos = sorted(videos, key=lambda x: x["score"], reverse=True)[:limit]

    topic_suggestions = []
    for h in hazards:
        if h in ["插座过载", "电线杂乱", "配电箱周围堆物"]:
            topic_suggestions.append("建议学习：电气火灾处置与电气消防基础")
        elif h in ["消防通道堵塞", "可燃物堆积"]:
            topic_suggestions.append("建议学习：消防通道与疏散安全")
        elif h in ["灭火器缺失", "灭火器被遮挡", "消防设施被遮挡"]:
            topic_suggestions.append("建议学习：灭火器配置与使用、消防设施巡检")
        elif h == "电动车违规充电":
            topic_suggestions.append("建议学习：电动车违规充电风险")
        elif h in ["烟雾", "明火"]:
            topic_suggestions.append("建议学习：初期火情应急处置")

    return {
        "hazards": hazards,
        "keywords": sorted(set(keywords)),
        "courses": courses,
        "videos": videos,
        "topic_suggestions": list(dict.fromkeys(topic_suggestions))[:limit],
        "summary": f"根据本次隐患类型，推荐 {len(courses)} 个课程资源和 {len(videos)} 个视频资源，用于整改后的知识学习与能力提升。"
    }
