from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


LEARNING_DIR = Path(__file__).resolve().parent.parent / "data" / "learning"


def _load_json(filename: str, default: Any):
    path = LEARNING_DIR / filename
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def get_learning_knowledge_graph(limit_questions: int = 80) -> Dict[str, Any]:
    questions = _load_json("quiz_bank.json", [])
    courses = _load_json("courses.json", [])

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    def add_node(node_id: str, label: str, node_type: str, count: int = 1):
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "label": label,
                "type": node_type,
                "count": 0,
            }
        nodes[node_id]["count"] += count

    def add_edge(source: str, target: str, relation: str, weight: int = 1):
        edges.append({
            "source": source,
            "target": target,
            "relation": relation,
            "weight": weight,
        })

    # 按类别 -> 等级 -> 模块 -> 知识点 -> 题目构建图谱。
    question_count_by_topic = Counter()
    for q in questions:
        category = _clean(q.get("exam_category") or "消防学习")
        level = _clean(q.get("exam_level") or "未分级")
        module = _clean(q.get("module") or q.get("topic") or "综合模块")
        topic = _clean(q.get("topic") or module)
        question = _clean(q.get("question"))

        category_id = f"category::{category}"
        level_id = f"level::{category}::{level}"
        module_id = f"module::{module}"
        topic_id = f"topic::{topic}"

        add_node(category_id, category, "资格方向")
        add_node(level_id, level, "等级")
        add_node(module_id, module, "模块")
        add_node(topic_id, topic, "知识点")

        add_edge(category_id, level_id, "包含等级")
        add_edge(level_id, module_id, "学习模块")
        add_edge(module_id, topic_id, "覆盖知识点")
        question_count_by_topic[topic] += 1

    # 仅添加代表性题目节点，避免图谱过大。
    added_question = 0
    for q in questions:
        if added_question >= limit_questions:
            break
        topic = _clean(q.get("topic") or q.get("module") or "综合")
        question = _clean(q.get("question"))
        if not question:
            continue
        qid = f"question::{q.get('id')}"
        topic_id = f"topic::{topic}"
        add_node(qid, question[:34] + ("..." if len(question) > 34 else ""), "题目")
        add_edge(topic_id, qid, "关联题目")
        added_question += 1

    # 关联课程到知识点/模块。
    for c in courses:
        cid = f"course::{c.get('id')}"
        title = _clean(c.get("title"))
        add_node(cid, title, "课程")
        for h in c.get("related_hazards", []):
            topic_id = f"topic::{_clean(h)}"
            add_node(topic_id, _clean(h), "知识点")
            add_edge(cid, topic_id, "课程关联")

    # 合并重复边。
    edge_counter = Counter((e["source"], e["target"], e["relation"]) for e in edges)
    merged_edges = [
        {"source": s, "target": t, "relation": r, "weight": w}
        for (s, t, r), w in edge_counter.items()
    ]

    top_modules = Counter(_clean(q.get("module") or "综合") for q in questions).most_common(12)
    top_topics = Counter(_clean(q.get("topic") or q.get("module") or "综合") for q in questions).most_common(12)

    return {
        "node_count": len(nodes),
        "edge_count": len(merged_edges),
        "question_count": len(questions),
        "nodes": list(nodes.values()),
        "edges": merged_edges[:1000],
        "top_modules": [{"name": k, "count": v} for k, v in top_modules],
        "top_topics": [{"name": k, "count": v} for k, v in top_topics],
        "explanation": "知识图谱将资格方向、等级、模块、知识点、课程和题目关联起来，用于学习路径推荐和题目检索解释。"
    }


def search_learning_rag(query: str, limit: int = 8) -> Dict[str, Any]:
    query = _clean(query)
    questions = _load_json("quiz_bank.json", [])
    courses = _load_json("courses.json", [])

    tokens = [t for t in re.split(r"[\s,，。；;、]+", query) if t]
    if not tokens and query:
        tokens = [query]

    def score_text(text: str) -> int:
        text = _clean(text)
        score = 0
        for t in tokens:
            if not t:
                continue
            if t in text:
                score += 5
            # loose partial matching for Chinese phrases
            for i in range(0, max(len(t) - 1, 0), 2):
                sub = t[i:i+2]
                if len(sub) >= 2 and sub in text:
                    score += 1
        return score

    q_results = []
    for q in questions:
        hay = " ".join([
            _clean(q.get("exam_category")),
            _clean(q.get("exam_level")),
            _clean(q.get("module")),
            _clean(q.get("topic")),
            _clean(q.get("question")),
            " ".join([_clean(x) for x in (q.get("options") or {}).values()]),
            _clean(q.get("analysis")),
        ])
        score = score_text(hay)
        if score > 0:
            item = dict(q)
            item.pop("answer", None)
            item["score"] = score
            item["match_reason"] = f"命中查询词：{query}"
            q_results.append(item)

    c_results = []
    for c in courses:
        hay = " ".join([
            _clean(c.get("title")),
            _clean(c.get("category")),
            _clean(c.get("summary")),
            " ".join(map(_clean, c.get("knowledge_points", []))),
            " ".join(map(_clean, c.get("related_hazards", []))),
        ])
        score = score_text(hay)
        if score > 0:
            item = dict(c)
            item["score"] = score
            c_results.append(item)

    q_results = sorted(q_results, key=lambda x: x["score"], reverse=True)[:limit]
    c_results = sorted(c_results, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "query": query,
        "tokens": tokens,
        "question_results": q_results,
        "course_results": c_results,
        "summary": f"检索到相关题目 {len(q_results)} 道，相关课程 {len(c_results)} 个。"
    }


def get_quiz_filter_options() -> Dict[str, Any]:
    questions = _load_json("quiz_bank.json", [])
    categories = sorted(set(_clean(q.get("exam_category")) for q in questions if _clean(q.get("exam_category"))))
    levels = sorted(set(_clean(q.get("exam_level")) for q in questions if _clean(q.get("exam_level"))))
    modules = sorted(set(_clean(q.get("module")) for q in questions if _clean(q.get("module"))))
    subjects = sorted(set(_clean(q.get("exam_subject")) for q in questions if _clean(q.get("exam_subject"))))
    counts = Counter((_clean(q.get("exam_category")), _clean(q.get("exam_level"))) for q in questions)
    return {
        "categories": categories,
        "levels": levels,
        "modules": modules,
        "subjects": subjects,
        "category_level_counts": [
            {"category": k[0], "level": k[1], "count": v}
            for k, v in counts.most_common()
        ]
    }
