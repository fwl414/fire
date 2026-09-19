from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


LEARNING_DIR = Path(__file__).resolve().parent.parent / "data" / "learning"


def _load_json(filename: str, default: Any):
    path = LEARNING_DIR / filename
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def get_learning_topics() -> List[Dict[str, Any]]:
    return _load_json("learning_topics.json", [])


def get_courses(category: str = "") -> List[Dict[str, Any]]:
    courses = _load_json("courses.json", [])
    if category:
        courses = [c for c in courses if c.get("category") == category]
    return courses


def get_course(course_id: str) -> Dict[str, Any]:
    for course in get_courses():
        if course.get("id") == course_id:
            return course
    return {}


def get_videos(topic: str = "") -> List[Dict[str, Any]]:
    videos = _load_json("online_video_index.json", [])
    if topic:
        videos = [
            v for v in videos
            if topic in v.get("topic", "") or topic in ",".join(v.get("keywords", [])) or topic in v.get("title", "")
        ]
    return videos




def get_quiz(topic: str = "", exam_type: str = "", limit: int = 3000, exam_category: str = "", exam_level: str = "", module: str = "", exam_subject: str = "") -> List[Dict[str, Any]]:
    questions = _load_json("quiz_bank.json", [])
    if topic:
        questions = [q for q in questions if topic in q.get("topic", "") or topic in q.get("question", "") or topic in q.get("module", "")]
    if exam_type:
        questions = [q for q in questions if exam_type in q.get("exam_type", "")]
    if exam_category:
        questions = [q for q in questions if q.get("exam_category") == exam_category]
    if exam_level:
        questions = [q for q in questions if q.get("exam_level") == exam_level]
    if exam_subject:
        questions = [q for q in questions if q.get("exam_subject") == exam_subject]
    if module:
        questions = [q for q in questions if q.get("module") == module]

    result = []
    for q in questions[:limit]:
        item = dict(q)
        item.pop("answer", None)
        item.pop("analysis", None)
        result.append(item)
    return result


def submit_quiz(question_id: str, user_answer: str) -> Dict[str, Any]:
    questions = _load_json("quiz_bank.json", [])
    for q in questions:
        if q.get("id") == question_id:
            correct = str(q.get("answer", "")).strip().upper()
            user = str(user_answer or "").strip().upper()
            return {
                "question_id": question_id,
                "user_answer": user,
                "correct_answer": correct,
                "is_correct": user == correct,
                "analysis": q.get("analysis", ""),
                "topic": q.get("topic", ""),
                "source_type": q.get("source_type", "模拟题"),
            }
    return {
        "question_id": question_id,
        "user_answer": user_answer,
        "correct_answer": "",
        "is_correct": False,
        "analysis": "未找到题目。",
    }


def recommend_learning_resources(query: str = "", hazards: List[str] | None = None) -> Dict[str, Any]:
    query = query or ""
    hazards = hazards or []
    text = query + " " + " ".join(hazards)

    courses = get_courses()
    videos = get_videos()
    questions = _load_json("quiz_bank.json", [])

    def score_item(item: Dict[str, Any]) -> int:
        haystack = " ".join([
            item.get("title", ""),
            item.get("topic", ""),
            item.get("category", ""),
            item.get("summary", ""),
            item.get("question", ""),
            " ".join(item.get("keywords", [])),
            " ".join(item.get("related_hazards", [])),
        ])
        score = 0
        for token in [x for x in ["电气", "火灾", "插排", "通道", "疏散", "灭火器", "电动车", "烟雾", "明火", "配电箱", "可燃物"] if x in text]:
            if token in haystack:
                score += 3
        for h in hazards:
            if h and h in haystack:
                score += 5
        return score

    ranked_courses = sorted(courses, key=score_item, reverse=True)
    ranked_videos = sorted(videos, key=score_item, reverse=True)
    ranked_questions = sorted(questions, key=score_item, reverse=True)

    # 即使评分较低也提供有用资源。
    return {
        "query": query,
        "hazards": hazards,
        "courses": ranked_courses[:3],
        "videos": ranked_videos[:3],
        "quiz": [
            {k: v for k, v in q.items() if k not in ["answer"]}
            for q in ranked_questions[:5]
        ],
        "learning_tip": "推荐资源基于问题关键词和隐患类型匹配。题目为系统内置模拟练习题，不宣称为官方真题。",
    }


def get_learning_overview() -> Dict[str, Any]:
    courses = get_courses()
    videos = get_videos()
    questions = _load_json("quiz_bank.json", [])
    categories: Dict[str, int] = {}
    for c in courses:
        categories[c.get("category", "其他")] = categories.get(c.get("category", "其他"), 0) + 1
    return {
        "course_count": len(courses),
        "video_count": len(videos),
        "quiz_count": len(questions),
        "categories": [{"name": k, "count": v} for k, v in categories.items()],
        "description": "消防知识学习系统包含知识课程、智能问答、模拟练习和网络视频资源推荐。"
    }



def get_exam_levels() -> List[Dict[str, Any]]:
    return _load_json("exam_levels.json", [])


def get_quiz_grouped() -> Dict[str, Any]:
    questions = _load_json("quiz_bank.json", [])
    grouped: Dict[str, Dict[str, Any]] = {}
    for q in questions:
        category = q.get("exam_category", q.get("exam_type", "其他"))
        level = q.get("exam_level", "基础")
        grouped.setdefault(category, {"category": category, "levels": {}})
        grouped[category]["levels"].setdefault(level, [])
        item = dict(q)
        item.pop("answer", None)
        item.pop("analysis", None)
        grouped[category]["levels"][level].append(item)

    return {
        "groups": list(grouped.values()),
        "total": len(questions),
        "note": "题目为系统内置模拟练习题，不宣称为官方真题。"
    }



def get_quiz_question(question_id: str) -> Dict[str, Any]:
    questions = _load_json("quiz_bank.json", [])
    for q in questions:
        if q.get("id") == question_id:
            item = dict(q)
            item.pop("answer", None)
            return item
    return {}


def get_learning_source_summary() -> Dict[str, Any]:
    return _load_json("imported_source_summary.json", {})


def get_learning_source_docs() -> List[Dict[str, Any]]:
    return _load_json("source_docs.json", [])



def get_exam_subjects() -> List[Dict[str, Any]]:
    return _load_json("exam_subjects.json", [])
