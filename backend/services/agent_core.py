from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_tool_call(
    name: str,
    tool_type: str,
    status: str,
    input_summary: str,
    output_summary: str,
    used_llm: bool = False,
    model: str = "",
    latency_ms: int | None = None,
    raw_output: Any = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "tool_type": tool_type,
        "status": status,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "used_llm": used_llm,
        "model": model,
        "latency_ms": latency_ms,
        "raw_output": raw_output,
        "time": now_text(),
    }


def build_agent_plan(has_image: bool, has_text_model: bool, has_vision_model: bool) -> List[Dict[str, Any]]:
    return [
        {
            "step": 1,
            "name": "任务理解",
            "goal": "理解巡检地点、现场描述、图片输入和关联设备信息。",
            "tool": "LLM/TextRule",
            "expected_output": "巡检任务类型与关键信息",
            "status": "ready",
        },
        {
            "step": 2,
            "name": "文本隐患识别",
            "goal": "从现场文字描述中抽取消防隐患。",
            "tool": "TextLLM + RuleExtractor" if has_text_model else "RuleExtractor",
            "expected_output": "文本隐患列表、判断理由",
            "status": "ready",
        },
        {
            "step": 3,
            "name": "图像隐患识别",
            "goal": "从现场图片中识别消防设施、通道、电气和可燃物隐患。",
            "tool": "VisionLLM" if has_image and has_vision_model else "Skipped/Downgrade",
            "expected_output": "视觉隐患列表、图像判断理由",
            "status": "ready" if has_image else "skipped",
        },
        {
            "step": 4,
            "name": "多源隐患融合",
            "goal": "融合规则识别、文本智能模型和视觉智能模型输出，去重并统一隐患表达。",
            "tool": "HazardFusion",
            "expected_output": "最终隐患列表",
            "status": "ready",
        },
        {
            "step": 5,
            "name": "消防知识检索",
            "goal": "检索与隐患相关的消防知识，为问答和决策提供依据。",
            "tool": "RAGRetriever",
            "expected_output": "知识库引用及检索得分",
            "status": "ready",
        },
        {
            "step": 6,
            "name": "风险量化评估",
            "goal": "根据隐患类型、严重程度和耦合关系计算风险评分。",
            "tool": "RiskEngine",
            "expected_output": "风险分数、风险等级、评分明细",
            "status": "ready",
        },
        {
            "step": 7,
            "name": "应急辅助决策",
            "goal": "生成立即处置、短期整改、后续复查和工单闭环建议。",
            "tool": "DecisionEngine + LLM",
            "expected_output": "结构化应急辅助决策",
            "status": "ready",
        },
        {
            "step": 8,
            "name": "报告生成",
            "goal": "生成可用于归档、打印和答辩展示的巡检报告。",
            "tool": "ReportGenerator",
            "expected_output": "巡检报告",
            "status": "ready",
        },
    ]


def summarize_agent(plan: List[Dict[str, Any]], tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    llm_count = len([x for x in tool_calls if x.get("used_llm")])
    ok_count = len([x for x in tool_calls if x.get("status") == "success"])
    return {
        "plan_steps": len(plan),
        "tool_calls": len(tool_calls),
        "successful_tool_calls": ok_count,
        "llm_tool_calls": llm_count,
        "summary": f"本次智能体共规划 {len(plan)} 个步骤，调用 {len(tool_calls)} 个工具，其中 {llm_count} 个涉及智能模型能力。",
    }
