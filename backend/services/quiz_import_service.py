from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List


REQUIRED_FIELDS = ["question", "options", "answer", "analysis"]


def parse_quiz_json(text: str) -> List[Dict[str, Any]]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("questions", [])
    if not isinstance(data, list):
        raise ValueError("JSON 题库应为数组，或包含 questions 数组。")
    return [normalize_question(x, i) for i, x in enumerate(data, start=1)]


def parse_quiz_csv(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    result = []
    for i, row in enumerate(reader, start=1):
        options = {
            "A": row.get("A", ""),
            "B": row.get("B", ""),
            "C": row.get("C", ""),
            "D": row.get("D", ""),
        }
        item = {
            "id": row.get("id") or f"import_{i:04d}",
            "exam_category": row.get("exam_category", "自定义题库"),
            "exam_level": row.get("exam_level", "未分级"),
            "module": row.get("module", row.get("topic", "综合")),
            "topic": row.get("topic", "综合"),
            "question_type": row.get("question_type", "single_choice"),
            "question": row.get("question", ""),
            "options": {k: v for k, v in options.items() if v},
            "answer": row.get("answer", ""),
            "analysis": row.get("analysis", ""),
            "difficulty": row.get("difficulty", "基础"),
            "source_type": row.get("source_type", "自定义导入题"),
        }
        result.append(normalize_question(item, i))
    return result


def parse_quiz_text(text: str) -> List[Dict[str, Any]]:
    """
    支持简单纯文本格式：
    题目：...
    A. ...
    B. ...
    C. ...
    D. ...
    答案：B
    解析：...
    用空行分隔多题。
    """
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    questions = []

    for i, block in enumerate(blocks, start=1):
        lines = [x.strip() for x in block.splitlines() if x.strip()]
        item = {
            "id": f"text_import_{i:04d}",
            "exam_category": "自定义题库",
            "exam_level": "未分级",
            "module": "综合",
            "topic": "综合",
            "question_type": "single_choice",
            "question": "",
            "options": {},
            "answer": "",
            "analysis": "",
            "difficulty": "基础",
            "source_type": "自定义导入题",
        }
        for line in lines:
            if line.startswith(("题目：", "题目:")):
                item["question"] = line.split("：", 1)[-1] if "：" in line else line.split(":", 1)[-1]
            elif len(line) > 2 and line[0] in "ABCD" and line[1] in [".", "、", "．"]:
                item["options"][line[0]] = line[2:].strip()
            elif line.startswith(("答案：", "答案:")):
                item["answer"] = line.split("：", 1)[-1].strip() if "：" in line else line.split(":", 1)[-1].strip()
            elif line.startswith(("解析：", "解析:")):
                item["analysis"] = line.split("：", 1)[-1].strip() if "：" in line else line.split(":", 1)[-1].strip()
        if item["question"]:
            questions.append(normalize_question(item, i))
    return questions


def normalize_question(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    options = item.get("options", {})
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            options = {}

    return {
        "id": item.get("id") or f"import_{index:04d}",
        "exam_type": item.get("exam_type", item.get("exam_category", "自定义题库")),
        "exam_category": item.get("exam_category", item.get("exam_type", "自定义题库")),
        "exam_level": item.get("exam_level", "未分级"),
        "module": item.get("module", item.get("topic", "综合")),
        "question_type": item.get("question_type", "single_choice"),
        "topic": item.get("topic", item.get("module", "综合")),
        "question": item.get("question", ""),
        "options": options,
        "answer": str(item.get("answer", "")).strip().upper(),
        "analysis": item.get("analysis", ""),
        "difficulty": item.get("difficulty", "基础"),
        "source_type": item.get("source_type", "自定义导入题"),
    }


def preview_import(filename: str, content: bytes) -> Dict[str, Any]:
    text = content.decode("utf-8-sig", errors="ignore")
    lower = filename.lower()
    if lower.endswith(".json"):
        questions = parse_quiz_json(text)
    elif lower.endswith(".csv"):
        questions = parse_quiz_csv(text)
    else:
        questions = parse_quiz_text(text)

    return {
        "filename": filename,
        "count": len(questions),
        "questions": questions[:20],
        "note": "当前接口用于预览导入结果。正式嵌入题库建议先人工校对后写入 quiz_bank.json。",
    }
