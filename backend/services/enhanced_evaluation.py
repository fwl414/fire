from __future__ import annotations

import time
from typing import Any, Dict, List

from services.text_analyzer import analyze_text, merge_hazards
from services.risk_engine import calculate_risk


EVAL_CASES = [
    {
        "id": "scene_001",
        "scene": "消防通道堵塞",
        "description": "实验室门口消防通道被纸箱和桌椅堵住，旁边堆放包装材料。",
        "expected": ["消防通道堵塞", "可燃物堆积"],
        "llm_mock": ["消防通道堵塞", "可燃物堆积"],
    },
    {
        "id": "scene_002",
        "scene": "复杂电气隐患",
        "description": "办公室多个插排串联，大功率设备同时使用，电线缠绕在桌脚附近。",
        "expected": ["插座过载", "电线杂乱"],
        "llm_mock": ["插座过载", "电线杂乱"],
    },
    {
        "id": "scene_003",
        "scene": "电动车违规充电",
        "description": "宿舍楼楼道内有电动车飞线充电，影响安全出口通行。",
        "expected": ["电动车违规充电", "消防通道堵塞"],
        "llm_mock": ["电动车违规充电", "消防通道堵塞"],
    },
    {
        "id": "scene_004",
        "scene": "设施遮挡",
        "description": "消火栓前堆放桌椅，灭火器被纸箱挡住，不便取用。",
        "expected": ["消防设施被遮挡", "灭火器被遮挡", "可燃物堆积"],
        "llm_mock": ["消防设施被遮挡", "灭火器被遮挡"],
    },
    {
        "id": "scene_005",
        "scene": "初期火情",
        "description": "机房配电箱附近有焦糊味和少量烟雾，线缆较为杂乱。",
        "expected": ["烟雾", "电线杂乱"],
        "llm_mock": ["烟雾", "电线杂乱", "配电箱周围堆物"],
    },
]


def _metric(pred: List[str], expected: List[str]) -> Dict[str, float]:
    p, e = set(pred), set(expected)
    hit = len(p & e)
    precision = hit / len(p) if p else 0
    recall = hit / len(e) if e else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "hit": hit,
    }


def run_enhanced_evaluation() -> Dict[str, Any]:
    rows = []
    start = time.perf_counter()

    for case in EVAL_CASES:
        rule_result = analyze_text(case["description"])
        rule_pred = rule_result.get("hazards", [])
        llm_pred = case["llm_mock"]
        fusion_pred = merge_hazards(rule_pred, llm_pred)

        rule_metric = _metric(rule_pred, case["expected"])
        llm_metric = _metric(llm_pred, case["expected"])
        fusion_metric = _metric(fusion_pred, case["expected"])

        risk = calculate_risk(fusion_pred)

        rows.append({
            "id": case["id"],
            "scene": case["scene"],
            "description": case["description"],
            "expected": case["expected"],
            "rule_prediction": rule_pred,
            "llm_prediction": llm_pred,
            "fusion_prediction": fusion_pred,
            "rule_f1": rule_metric["f1"],
            "llm_f1": llm_metric["f1"],
            "fusion_f1": fusion_metric["f1"],
            "rule_recall": rule_metric["recall"],
            "llm_recall": llm_metric["recall"],
            "fusion_recall": fusion_metric["recall"],
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
        })

    def avg(key: str) -> float:
        return round(sum(x[key] for x in rows) / len(rows), 3)

    return {
        "mode": "rule_llm_fusion_comparison",
        "case_count": len(rows),
        "summary": {
            "avg_rule_f1": avg("rule_f1"),
            "avg_llm_f1": avg("llm_f1"),
            "avg_fusion_f1": avg("fusion_f1"),
            "avg_rule_recall": avg("rule_recall"),
            "avg_llm_recall": avg("llm_recall"),
            "avg_fusion_recall": avg("fusion_recall"),
        },
        "rows": rows,
        "total_latency_ms": int((time.perf_counter() - start) * 1000),
        "conclusion": "融合识别综合利用规则稳定性和智能模型语义理解能力，通常比单一规则识别更适合复杂消防隐患场景。",
    }
