from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from services.llm_gateway import call_text_model, extract_hazards_from_text, safe_json
from services.model_registry import get_active_config
from services.knowledge_base import search_knowledge
from services.rag_engine import retrieve_fire_knowledge, build_rag_context, build_retrieval_summary


FIRE_HAZARDS = [
    "明火",
    "烟雾",
    "电动车违规充电",
    "消防通道堵塞",
    "消防设施被遮挡",
    "灭火器缺失",
    "灭火器被遮挡",
    "插座过载",
    "可燃物堆积",
    "配电箱周围堆物",
    "电线杂乱",
]


INSPECTION_SYSTEM_PROMPT = """你是智慧消防风险评估系统中的Agent，负责根据现场文字描述识别消防安全隐患。
你必须只输出 JSON，不要输出 Markdown，不要输出解释性前后缀。
JSON 格式如下：
{
  "hazards": ["从给定候选隐患中选择"],
  "description": "对现场情况的简要判断",
  "risk_reasons": ["判断理由1", "判断理由2"],
  "suggestion": "整改和应急处置建议"
}
候选隐患只能从以下列表中选择：
明火、烟雾、电动车违规充电、消防通道堵塞、消防设施被遮挡、灭火器缺失、灭火器被遮挡、插座过载、可燃物堆积、配电箱周围堆物、电线杂乱。
如果没有明显隐患，hazards 返回空数组。
"""


async def analyze_text_with_llm(db: Session, description: str) -> Dict[str, Any]:
    config = get_active_config(db, "text")
    if not config:
        return {
            "used_text_model_api": False,
            "text_model_error": "未启用文本模型配置",
            "provider": "",
            "model": "",
            "hazards": [],
            "description": "",
            "risk_reasons": [],
            "suggestion": "",
            "raw_content": "",
        }

    prompt = f"""请分析以下消防巡检现场描述，识别消防安全隐患并输出 JSON。

现场描述：
{description or "未填写"}
"""

    result = await call_text_model(config, prompt, INSPECTION_SYSTEM_PROMPT, purpose="inspection_analysis")

    if not result.get("ok"):
        return {
            "used_text_model_api": False,
            "text_model_error": result.get("response_text") or result.get("message") or "文本模型调用失败",
            "provider": config.provider,
            "model": config.text_model,
            "hazards": [],
            "description": "",
            "risk_reasons": [],
            "suggestion": "",
            "raw_content": "",
        }

    content = result.get("content", "")
    parsed = safe_json(content)

    hazards = []
    if isinstance(parsed, dict):
        raw_hazards = parsed.get("hazards") or []
        if isinstance(raw_hazards, str):
            raw_hazards = [raw_hazards]
        hazards = [h for h in raw_hazards if h in FIRE_HAZARDS]

    if not hazards:
        hazards = extract_hazards_from_text(content)

    return {
        "used_text_model_api": True,
        "text_model_error": "",
        "provider": config.provider,
        "model": config.text_model,
        "hazards": hazards,
        "description": parsed.get("description", "") if isinstance(parsed, dict) else "",
        "risk_reasons": parsed.get("risk_reasons", []) if isinstance(parsed, dict) else [],
        "suggestion": parsed.get("suggestion", "") if isinstance(parsed, dict) else "",
        "raw_content": content,
    }


QA_SYSTEM_PROMPT = """你是智慧消防系统的消防知识问答智能体。
你必须结合提供的知识库检索结果回答问题，不要脱离引用内容编造依据。
回答要求：
1. 先给出明确结论；
2. 再给出处置建议；
3. 说明风险提醒；
4. 在关键结论后标注引用，例如【引用1】、【引用2】；
5. 不要编造法规条文编号；
6. 如果知识库没有足够依据，要明确说明“当前知识库依据不足”。
"""


async def answer_question_with_llm(db: Session, question: str) -> Dict[str, Any]:
    refs = retrieve_fire_knowledge(question)
    ref_text = build_rag_context(refs)
    retrieval_summary = build_retrieval_summary(refs)

    prompt = f"""用户问题：
{question}

知识库检索结果：
{ref_text}

请基于知识库回答用户问题。
"""

    config = get_active_config(db, "text")
    if not config:
        return {
            "answer": (
                "当前未启用文本智能模型，系统使用知识库检索结果直接回答：\n\n"
                + ref_text
                + "\n\n建议：如现场已出现明火、烟雾、人员被困等情况，应立即启动应急预案并报警。"
            ),
            "references": refs,
            "retrieval_count": len(refs),
            "retrieval_summary": retrieval_summary,
            "used_text_model_api": False,
            "text_model_error": "未启用文本模型配置",
            "model_provider": "",
            "model_name": "",
            "agent_steps": [
                "接收用户消防安全问题。",
                "从消防知识库中检索相关条目。",
                "未检测到可用文本智能模型，使用知识库结果直接生成回答。",
            ],
        }

    result = await call_text_model(config, prompt, QA_SYSTEM_PROMPT, purpose="qa")

    if not result.get("ok"):
        return {
            "answer": (
                "文本智能模型调用失败，系统已降级为知识库回答：\n\n"
                + ref_text
                + "\n\n建议：如现场已出现明火、烟雾、人员被困等情况，应立即启动应急预案并报警。"
            ),
            "references": refs,
            "retrieval_count": len(refs),
            "retrieval_summary": retrieval_summary,
            "used_text_model_api": False,
            "text_model_error": result.get("response_text") or result.get("message") or "文本模型调用失败",
            "model_provider": config.provider,
            "model_name": config.text_model,
            "agent_steps": [
                "接收用户消防安全问题。",
                "从消防知识库中检索相关条目。",
                "尝试调用文本智能模型。",
                "智能模型调用失败，降级为知识库回答。",
            ],
        }

    return {
        "answer": result.get("content", ""),
        "references": refs,
        "retrieval_count": len(refs),
        "used_text_model_api": True,
        "text_model_error": "",
        "model_provider": result.get("provider", config.provider),
        "model_name": result.get("model", config.text_model),
        "agent_steps": [
            "接收用户消防安全问题。",
            "从消防知识库中检索相关条目。",
            f"调用文本智能模型：{config.provider} / {config.text_model}。",
            "结合知识库结果生成回答。",
        ],
    }
