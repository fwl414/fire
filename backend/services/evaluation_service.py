from __future__ import annotations

import time
from typing import Dict, List, Any

from services.text_analyzer import analyze_text, merge_hazards
from services.risk_engine import calculate_risk


EVALUATION_CASES = [
    {
        "id": "case_001",
        "scene": "消防通道堵塞",
        "description": "实验室门口消防通道被纸箱和杂物堵住，人员通过困难。",
        "expected": ["消防通道堵塞", "可燃物堆积"],
    },
    {
        "id": "case_002",
        "scene": "电气隐患",
        "description": "办公室存在多个插排串联，大功率设备同时使用，电线杂乱。",
        "expected": ["插座过载", "电线杂乱"],
    },
    {
        "id": "case_003",
        "scene": "电动车违规充电",
        "description": "宿舍楼楼道有电动车飞线充电，影响安全出口疏散。",
        "expected": ["电动车违规充电", "消防通道堵塞"],
    },
    {
        "id": "case_004",
        "scene": "设施遮挡",
        "description": "消火栓前堆放桌椅，灭火器被纸箱遮挡。",
        "expected": ["消防设施被遮挡", "灭火器被遮挡", "可燃物堆积"],
    },
    {
        "id": "case_005",
        "scene": "初期火情",
        "description": "机房配电箱附近有焦糊味和少量烟雾，旁边堆放塑料包装。",
        "expected": ["烟雾", "配电箱周围堆物", "可燃物堆积"],
    },
]


def _score(pred: List[str], expected: List[str]) -> Dict[str, Any]:
    pred_set = set(pred)
    exp_set = set(expected)
    hit = len(pred_set & exp_set)
    precision = hit / len(pred_set) if pred_set else 0
    recall = hit / len(exp_set) if exp_set else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {
        "hit": hit,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def run_rule_evaluation() -> Dict[str, Any]:
    rows = []
    start = time.perf_counter()

    for case in EVALUATION_CASES:
        t0 = time.perf_counter()
        rule_result = analyze_text(case["description"])
        pred = rule_result.get("hazards", [])
        risk = calculate_risk(pred)
        metric = _score(pred, case["expected"])
        rows.append({
            "id": case["id"],
            "scene": case["scene"],
            "description": case["description"],
            "expected": case["expected"],
            "rule_prediction": pred,
            "fusion_prediction": pred,
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "precision": metric["precision"],
            "recall": metric["recall"],
            "f1": metric["f1"],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        })

    avg_precision = sum(x["precision"] for x in rows) / len(rows)
    avg_recall = sum(x["recall"] for x in rows) / len(rows)
    avg_f1 = sum(x["f1"] for x in rows) / len(rows)

    return {
        "mode": "rule_baseline",
        "case_count": len(rows),
        "avg_precision": round(avg_precision, 3),
        "avg_recall": round(avg_recall, 3),
        "avg_f1": round(avg_f1, 3),
        "total_latency_ms": int((time.perf_counter() - start) * 1000),
        "rows": rows,
        "conclusion": "该评估用于论文中的规则基线分析；V8 智能巡检接口可进一步展示规则、智能模型与融合结果的差异。",
    }
