from __future__ import annotations

from typing import Any, Dict, List

from services.learning_service import get_courses, get_videos


def _match_resources(topic: str, module: str = "") -> Dict[str, Any]:
    text = f"{topic} {module}"
    courses = []
    for c in get_courses():
        hay = " ".join([
            c.get("title", ""),
            c.get("category", ""),
            c.get("summary", ""),
            " ".join(c.get("knowledge_points", [])),
            " ".join(c.get("related_hazards", [])),
        ])
        if topic and topic in hay or module and module in hay:
            courses.append(c)

    videos = []
    for v in get_videos():
        hay = " ".join([
            v.get("title", ""),
            v.get("topic", ""),
            v.get("description", ""),
            " ".join(v.get("keywords", [])),
        ])
        if topic and topic in hay or module and module in hay:
            videos.append(v)

    return {
        "courses": courses[:2],
        "videos": videos[:2],
    }


def build_quiz_agent_feedback(
    question: Dict[str, Any],
    submit_result: Dict[str, Any],
    recent_records: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    题目级学习 Agent：
    - 判断答题结果；
    - 解释为什么错/对；
    - 关联知识点；
    - 推荐复习资源；
    - 给出下一题策略。
    """
    recent_records = recent_records or []
    topic = question.get("topic", submit_result.get("topic", ""))
    module = question.get("module", "")

    is_correct = bool(submit_result.get("is_correct"))
    if is_correct:
        diagnosis = "本题回答正确，说明你对该知识点已有基本掌握。"
        next_strategy = "建议继续做同等级下一题，若连续答对 3 道，可提升到更高等级或综合案例题。"
        action = "继续练习"
    else:
        diagnosis = "本题回答错误，建议先理解解析，再回到对应课程复习后重做同类题。"
        next_strategy = "建议下一题继续选择同知识点或同模块题目，完成针对性巩固。"
        action = "专项复习"

    resources = _match_resources(topic, module)
    wrong_topics: Dict[str, int] = {}
    for r in recent_records:
        if not r.get("is_correct"):
            t = r.get("topic", "未分类")
            wrong_topics[t] = wrong_topics.get(t, 0) + 1

    tool_calls = [
        {
            "tool": "QuizResultChecker",
            "type": "rule",
            "result": "判断用户答案是否正确，并返回标准答案与解析。"
        },
        {
            "tool": "KnowledgePointMapper",
            "type": "rag/learning",
            "result": f"将题目关联到知识点：{topic or module or '基础知识'}。"
        },
        {
            "tool": "LearningResourceRecommender",
            "type": "recommendation",
            "result": f"推荐课程 {len(resources['courses'])} 个、视频 {len(resources['videos'])} 个。"
        },
        {
            "tool": "NextQuestionPlanner",
            "type": "agent",
            "result": next_strategy
        }
    ]

    return {
        "agent_name": "消防学习辅导 Agent",
        "is_correct": is_correct,
        "diagnosis": diagnosis,
        "knowledge_point": topic or module or "基础知识",
        "module": module,
        "standard_analysis": submit_result.get("analysis", ""),
        "next_strategy": next_strategy,
        "recommended_action": action,
        "weak_topics_snapshot": [
            {"topic": k, "wrong_count": v}
            for k, v in sorted(wrong_topics.items(), key=lambda x: x[1], reverse=True)[:3]
        ],
        "recommended_courses": resources["courses"],
        "recommended_videos": resources["videos"],
        "agent_tool_calls": tool_calls,
        "explainable_summary": (
            f"学习 Agent 根据答题结果、题目知识点和近期错题记录，判断当前应采取“{action}”策略。"
        )
    }
