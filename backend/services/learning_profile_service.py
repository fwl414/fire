from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from services.runtime_db import connect_runtime_db


def _connect():
    conn = connect_runtime_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS learning_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id TEXT,
        question TEXT,
        user_answer TEXT,
        correct_answer TEXT,
        is_correct INTEGER,
        exam_category TEXT,
        exam_level TEXT,
        exam_subject TEXT,
        module TEXT,
        topic TEXT,
        analysis TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    return conn


def save_learning_attempt(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    question = payload.get("question", {}) or {}
    submit = payload.get("submit_result", {}) or {}
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO learning_attempts
            (question_id, question, user_answer, correct_answer, is_correct, exam_category, exam_level,
             exam_subject, module, topic, analysis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("question_id") or question.get("id", ""),
                question.get("question", ""),
                payload.get("user_answer", ""),
                submit.get("correct_answer", ""),
                1 if payload.get("is_correct", submit.get("is_correct", False)) else 0,
                question.get("exam_category", ""),
                question.get("exam_level", ""),
                question.get("exam_subject", ""),
                question.get("module", ""),
                question.get("topic", ""),
                submit.get("analysis", ""),
                now,
            ),
        )
        conn.commit()
    return {"id": cur.lastrowid, "created_at": now}


def list_learning_attempts(limit: int = 200) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM learning_attempts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_wrongbook(limit: int = 100) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM learning_attempts WHERE is_correct = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_learning_profile() -> Dict[str, Any]:
    attempts = list_learning_attempts(1000)
    total = len(attempts)
    correct = len([a for a in attempts if a.get("is_correct")])
    wrong = total - correct
    accuracy = round(correct / total * 100, 1) if total else 0

    module_counter = Counter(a.get("module") or "未分类" for a in attempts)
    wrong_module_counter = Counter(a.get("module") or "未分类" for a in attempts if not a.get("is_correct"))

    weak_modules = [{"module": k, "wrong_count": v} for k, v in wrong_module_counter.most_common(6)]
    practiced_modules = [{"module": k, "count": v} for k, v in module_counter.most_common(6)]

    if not total:
        advice = "暂无学习记录。完成刷题后，系统会自动生成正确率、错题本和薄弱模块分析。"
    elif accuracy >= 85:
        advice = "整体掌握较好，建议继续进行模拟考试并重点复查少量错题。"
    elif accuracy >= 60:
        advice = "基础掌握尚可，建议围绕错题模块进行专项练习。"
    else:
        advice = "当前正确率偏低，建议先回到知识课程学习，再按模块进行分级练习。"

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
        "weak_modules": weak_modules,
        "practiced_modules": practiced_modules,
        "advice": advice,
        "latest": attempts[:10],
    }
