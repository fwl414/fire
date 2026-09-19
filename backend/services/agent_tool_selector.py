from __future__ import annotations

from typing import Any, Dict, List


def select_agent_tools(
    task_type: str,
    has_text: bool = False,
    has_image: bool = False,
    has_hardware_event: bool = False,
    need_report: bool = True,
    need_rag: bool = True,
) -> Dict[str, Any]:
    """
    根据输入条件自动选择 Agent 工具链。
    这是面向答辩展示的“工具选择器”，用于证明系统不是固定 if-else 流程，
    而是根据任务输入动态组织工具。
    """
    selected: List[Dict[str, Any]] = []

    def add(name: str, tool_type: str, reason: str, required: bool = True):
        selected.append({
            "name": name,
            "tool_type": tool_type,
            "reason": reason,
            "required": required,
        })

    add("TaskUnderstanding", "agent", "所有任务都需要先理解任务目标、输入信息和场景。")

    if has_hardware_event:
        add("HardwareEventParser", "hardware", "检测到硬件事件，需要先解析传感器或网关上报数据。")

    if has_text:
        add("RuleTextExtractor", "rule", "存在现场文字描述，使用规则识别稳定抽取典型消防隐患。")
        add("TextLLMAnalyzer", "llm", "存在现场文字描述，调用文本智能模型理解复杂语义和多隐患表达。")
    else:
        add("RuleTextExtractor", "rule", "无现场文字描述，规则文本识别降级跳过。", required=False)

    if has_image:
        add("VisionLLMAnalyzer", "llm", "检测到现场图片，调用视觉智能模型识别通道堵塞、设施遮挡等视觉隐患。")
    else:
        add("VisionLLMAnalyzer", "llm", "未上传图片，视觉智能模型跳过。", required=False)

    if need_rag:
        add("RAGRetriever", "rag", "需要消防知识依据，检索知识库降低智能模型幻觉。")

    add("HazardFusion", "fusion", "融合规则、智能模型、视觉和硬件事件结果，形成最终隐患列表。")
    add("RiskEngine", "algorithm", "根据隐患类型和严重程度计算风险评分。")
    add("RiskExplainer", "explainability", "输出风险评分依据和证据链。")
    add("DecisionOptimizer", "decision", "根据风险等级、场景和隐患类型优化处置决策。")

    if need_report:
        add("ReportGenerator", "template", "需要生成巡检报告用于归档、打印和答辩展示。")

    return {
        "task_type": task_type,
        "input_flags": {
            "has_text": has_text,
            "has_image": has_image,
            "has_hardware_event": has_hardware_event,
            "need_rag": need_rag,
            "need_report": need_report,
        },
        "selected_tools": selected,
        "tool_count": len(selected),
        "summary": f"Agent 根据输入条件自动选择 {len(selected)} 个工具，其中必选工具 {len([x for x in selected if x['required']])} 个。"
    }


def build_tool_selection_text(selection: Dict[str, Any]) -> str:
    lines = [selection.get("summary", "")]
    for i, tool in enumerate(selection.get("selected_tools", []), start=1):
        mark = "必选" if tool.get("required") else "可选/跳过"
        lines.append(f"{i}. [{mark}] {tool['name']}：{tool['reason']}")
    return "\n".join(lines)
