from __future__ import annotations

from typing import Any, Dict, List


def build_risk_explanation(
    hazards: List[str],
    hazard_items: List[Dict[str, Any]],
    risk_score: int,
    risk_level: str,
    fusion_result: Dict[str, Any],
    rag_references: List[Dict[str, Any]],
    emergency_decision: Dict[str, Any],
) -> Dict[str, Any]:
    score_cards: List[Dict[str, Any]] = []
    for item in hazard_items or []:
        score_cards.append({
            "hazard": item.get("type", "未知隐患"),
            "category": item.get("category", "其他"),
            "severity": item.get("severity", "中"),
            "score": item.get("score", 0),
            "reason": item.get("reason", ""),
            "measure": item.get("measure", ""),
            "plain_text": f"{item.get('type')} 属于 {item.get('category')}，风险等级为 {item.get('severity')}，计入 {item.get('score')} 分。"
        })

    source_evidence = []
    source_map = [
        ("规则识别", fusion_result.get("rule_hazards", [])),
        ("文本智能模型", fusion_result.get("text_llm_hazards", [])),
        ("视觉智能模型", fusion_result.get("vision_llm_hazards", [])),
    ]

    for source, values in source_map:
        for h in values or []:
            source_evidence.append({
                "source": source,
                "hazard": h,
                "evidence": f"{source}识别到“{h}”。"
            })

    reference_evidence = []
    for ref in rag_references or []:
        reference_evidence.append({
            "title": ref.get("title", ""),
            "source": ref.get("source", ""),
            "score": ref.get("score", 0),
            "matched_keywords": ref.get("matched_keywords", []),
            "evidence": f"知识库条目《{ref.get('title', '')}》与本次隐患相关，检索得分 {ref.get('score', 0)}。"
        })

    if risk_level == "严重风险":
        level_reason = "风险等级为严重风险，说明现场可能存在直接影响人员疏散、火灾初期处置或火情扩大的关键隐患。"
    elif risk_level == "高风险":
        level_reason = "风险等级为高风险，说明现场隐患需要尽快整改并进行复查。"
    elif risk_level == "中风险":
        level_reason = "风险等级为中风险，说明现场存在一定安全隐患，建议安排整改。"
    else:
        level_reason = "风险等级为低风险，说明当前未发现高危隐患，但仍需保持日常巡检。"

    plain_conclusion = (
        f"系统共识别 {len(hazards or [])} 项隐患，综合风险评分为 {risk_score} 分，判定为{risk_level}。"
        f"{level_reason}"
    )

    explain_steps = [
        "第一步：从现场文字和图片中识别可能存在的消防隐患。",
        "第二步：融合规则识别、文本智能模型和视觉智能模型结果，得到最终隐患列表。",
        "第三步：根据隐患类型、风险类别和严重程度计算风险分值。",
        "第四步：检索消防知识库，为风险判断和处置建议提供依据。",
        "第五步：根据风险等级生成立即处置、短期整改和后续复查建议。",
    ]

    return {
        "plain_conclusion": plain_conclusion,
        "level_reason": level_reason,
        "score_cards": score_cards,
        "source_evidence": source_evidence,
        "reference_evidence": reference_evidence,
        "explain_steps": explain_steps,
        "decision_mapping": {
            "priority": emergency_decision.get("priority"),
            "need_alarm": emergency_decision.get("need_alarm"),
            "need_evacuation": emergency_decision.get("need_evacuation"),
            "need_ticket": emergency_decision.get("need_ticket"),
            "reason": emergency_decision.get("decision_reason"),
        }
    }
