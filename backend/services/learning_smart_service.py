from __future__ import annotations

import inspect
from typing import Any, Dict, List


def _rule_based_analysis(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(records)
    correct = len([r for r in records if r.get("is_correct")])
    accuracy = round(correct / total, 3) if total else 0

    weak_topics: Dict[str, int] = {}
    strong_topics: Dict[str, int] = {}
    weak_modules: Dict[str, int] = {}

    for r in records:
        topic = r.get("topic") or "未分类"
        module = r.get("module") or topic
        if r.get("is_correct"):
            strong_topics[topic] = strong_topics.get(topic, 0) + 1
        else:
            weak_topics[topic] = weak_topics.get(topic, 0) + 1
            weak_modules[module] = weak_modules.get(module, 0) + 1

    weak_sorted = sorted(weak_topics.items(), key=lambda x: x[1], reverse=True)
    module_sorted = sorted(weak_modules.items(), key=lambda x: x[1], reverse=True)
    strong_sorted = sorted(strong_topics.items(), key=lambda x: x[1], reverse=True)

    if accuracy >= 0.85:
        level = "掌握较好"
        advice = "整体正确率较高，建议继续进行进阶题和综合案例题训练。"
    elif accuracy >= 0.6:
        level = "基本掌握"
        advice = "基础知识已有一定掌握，建议针对错题较多的知识点进行专项复习。"
    else:
        level = "需要加强"
        advice = "当前正确率偏低，建议先回到知识课程学习，再进行分模块练习。"

    focus = [x[0] for x in weak_sorted[:3]] or ["电气火灾", "疏散安全", "灭火器"]

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "learning_level": level,
        "weak_topics": [{"topic": k, "wrong_count": v} for k, v in weak_sorted],
        "weak_modules": [{"module": k, "wrong_count": v} for k, v in module_sorted],
        "strong_topics": [{"topic": k, "correct_count": v} for k, v in strong_sorted],
        "summary": f"本次共完成 {total} 道题，答对 {correct} 道，正确率 {int(accuracy * 100)}%。",
        "advice": advice,
        "next_plan": [
            f"优先复习：{focus[0]}",
            "完成对应知识课程的知识点学习。",
            "重新完成 5 道同类模拟题。",
            "结合智能问答追问不理解的知识点。",
        ],
        "recommended_topics": focus,
    }


def _build_rule_llm_style_advice(base: Dict[str, Any]) -> str:
    weak = base.get("weak_topics") or []
    weak_text = "、".join([x.get("topic", "") for x in weak[:3]]) or "基础消防知识"

    return (
        "总体评价：\n"
        f"{base.get('summary')}当前学习水平为“{base.get('learning_level')}”。\n\n"
        "薄弱知识点：\n"
        f"建议重点关注 {weak_text} 等内容，特别是与隐患识别、应急处置和整改闭环相关的题目。\n\n"
        "学习建议：\n"
        "1. 先回到知识课程复习对应知识点，理解风险原因而不是只记答案。\n"
        "2. 对错题进行二次练习，记录错误原因。\n"
        "3. 使用智能问答追问不理解的概念，例如“为什么电气火灾不能直接用水扑救”。\n"
        "4. 完成同类场景题后，再进入综合案例分析。\n\n"
        "下一步计划：\n"
        "建议按照“课程学习 → 模拟练习 → 错题复盘 → 智能问答追问 → 再练习”的路径提升。"
    )


async def _try_call_project_llm(prompt: str) -> str:
    """
    兼容项目中不同命名的 llm_client。
    如果当前 llm_client 没有可用文本调用函数，直接抛出异常，让上层回退到规则建议。
    """
    try:
        from services import llm_client
    except Exception as exc:
        raise RuntimeError(f"无法导入 llm_client：{exc}") from exc

    candidate_names = [
        "call_text_model",
        "call_llm",
        "call_text_llm",
        "chat_completion",
        "call_model",
        "generate_text",
        "ask_llm",
    ]

    for name in candidate_names:
        fn = getattr(llm_client, name, None)
        if not callable(fn):
            continue

        try:
            result = fn(prompt)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, dict):
                return str(result.get("content") or result.get("answer") or result.get("text") or result)
            return str(result)
        except TypeError:
            # 某些项目函数可能需要 provider/model 参数。
            continue

    raise RuntimeError("llm_client 中未找到兼容的文本智能模型调用函数。")


async def analyze_learning_progress(records: List[Dict[str, Any]], use_llm: bool = True) -> Dict[str, Any]:
    base = _rule_based_analysis(records)

    if not use_llm:
        base["used_llm"] = False
        base["llm_advice"] = _build_rule_llm_style_advice(base)
        return base

    prompt = f"""
你是智慧消防系统中的消防学习智能辅导 Agent。
请根据学习者的练习记录，分析其消防知识掌握情况，并给出学习建议。
要求：
1. 不要声称题目为官方真题；
2. 按“总体评价、薄弱知识点、学习建议、下一步计划”回答；
3. 建议要具体、可执行；
4. 语言适合学生或参赛答辩展示。

练习统计：
{base}
"""
    try:
        answer = await _try_call_project_llm(prompt)
        base["used_llm"] = True
        base["llm_advice"] = answer
    except Exception as e:
        base["used_llm"] = False
        base["llm_error"] = str(e)
        base["llm_advice"] = _build_rule_llm_style_advice(base)

    return base
