from __future__ import annotations

from typing import Any, Dict, List


def build_agent_trace(
    task: Dict[str, Any],
    tool_selection: Dict[str, Any],
    agent_plan: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
    rag_references: List[Dict[str, Any]],
    risk_result: Dict[str, Any],
    decision: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构造可公开展示的 Agent 执行轨迹。
    注意：这里不是隐藏思维链，而是用于系统可解释展示的任务规划、工具调用和结果摘要。
    """
    observations = []

    for call in tool_calls:
        observations.append({
            "tool": call.get("name"),
            "status": call.get("status"),
            "used_llm": call.get("used_llm", False),
            "observation": call.get("output_summary", ""),
        })

    retrieval_summary = {
        "count": len(rag_references or []),
        "top_titles": [x.get("title", "") for x in (rag_references or [])[:3]],
    }

    reasoning_summary = (
        f"Agent 接收任务后，根据输入条件选择工具链；"
        f"随后执行隐患识别、多源融合、RAG 检索、风险评分和应急辅助决策。"
        f"最终风险等级为 {risk_result.get('risk_level')}，风险评分为 {risk_result.get('risk_score')}。"
    )

    return {
        "task": task,
        "tool_selection": tool_selection,
        "plan": agent_plan,
        "tool_calls": tool_calls,
        "observations": observations,
        "retrieval_summary": retrieval_summary,
        "risk_result": risk_result,
        "final_decision": decision,
        "reasoning_summary": reasoning_summary,
        "trace_explanation": "该执行轨迹用于展示 Agent 的任务规划、工具选择、工具调用和决策依据，不包含模型隐藏思维链。",
    }
