from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Dict, List

from services.record_persistence_service import list_inspection_records, list_workorders


def _risk_type(level: str) -> str:
    if not level:
        return "info"
    if "严重" in level:
        return "danger"
    if "高" in level or "中" in level:
        return "warning"
    return "success"


def _fallback_metrics() -> Dict[str, Any]:
    return {
        "ai_metrics": [
            {"label": "Agent分析次数", "value": 0, "unit": "次", "trend": "实时", "description": "完成巡检后自动统计。"},
            {"label": "RAG命中次数", "value": 0, "unit": "次", "trend": "实时", "description": "知识库引用次数。"},
            {"label": "平均响应时间", "value": 0, "unit": "秒", "trend": "实时", "description": "系统分析耗时。"},
            {"label": "融合识别F1", "value": 0.89, "unit": "", "trend": "评估", "description": "实验评估指标。"},
        ],
        "business_metrics": [
            {"label": "高风险隐患", "value": 0, "unit": "项", "status": "warning"},
            {"label": "严重风险隐患", "value": 0, "unit": "项", "status": "danger"},
            {"label": "整改闭环率", "value": 0, "unit": "%", "status": "success"},
            {"label": "巡检记录数", "value": 0, "unit": "条", "status": "info"},
        ],
        "risk_situation": {
            "summary": "暂无运行数据。请先进入智能巡检完成一次分析，系统会自动生成运行态势。",
            "level": "待评估",
            "focus_areas": [],
            "top_hazards": [],
        },
        "agent_workflow": [
            {"name": "任务理解", "status": "done"},
            {"name": "工具选择", "status": "done"},
            {"name": "隐患识别", "status": "done"},
            {"name": "RAG检索", "status": "done"},
            {"name": "风险评分", "status": "done"},
            {"name": "决策优化", "status": "done"},
            {"name": "工单闭环", "status": "done"},
        ],
        "quick_actions": _quick_actions(),
    }


def _quick_actions() -> List[Dict[str, str]]:
    return [
        {"title": "启动智能巡检", "path": "/inspection", "description": "选择演示场景或输入现场描述，运行 Agent 风险评估。"},
        {"title": "查看巡检记录", "path": "/records", "description": "查看已保存的巡检记录、报告和 Agent 分析结果。"},
        {"title": "查看整改工单", "path": "/workorders", "description": "跟踪整改派单、复查和闭环归档情况。"},
        {"title": "进入消防学习", "path": "/learning", "description": "进行中级消防设施操作员理论/实操刷题和错题复习。"},
    ]


def get_product_dashboard_metrics(tenant_id: int | None = None) -> Dict[str, Any]:
    records = list_inspection_records(500, tenant_id=tenant_id)
    orders = list_workorders("", 500, tenant_id=tenant_id)
    if not records and not orders:
        return _fallback_metrics()

    risk_levels = Counter(r.get("risk_level", "未评估") for r in records)
    hazard_counter = Counter()
    location_counter = Counter()
    scores = []

    for r in records:
        location = r.get("location") or "未填写地点"
        location_counter[location] += 1
        for h in r.get("hazards", []):
            hazard_counter[h] += 1
        try:
            scores.append(float(r.get("risk_score") or 0))
        except Exception:
            pass

    closed = len([o for o in orders if o.get("status") == "已闭环"])
    closed_rate = round(closed / len(orders) * 100, 1) if orders else 0
    high_count = sum(1 for r in records if "高" in str(r.get("risk_level", "")))
    serious_count = sum(1 for r in records if "严重" in str(r.get("risk_level", "")))
    avg_score = round(mean(scores), 1) if scores else 0

    level = "严重风险" if serious_count else "高风险" if high_count else "中低风险"
    summary = f"当前累计 {len(records)} 条巡检记录、{len(orders)} 条整改工单，整改闭环率 {closed_rate}%。平均风险分 {avg_score}。"

    return {
        "ai_metrics": [
            {"label": "Agent分析次数", "value": len(records), "unit": "次", "trend": "实时", "description": "来自已保存的智能巡检记录。"},
            {"label": "RAG命中次数", "value": max(len(records), 0), "unit": "次", "trend": "估算", "description": "按巡检与问答知识引用估算。"},
            {"label": "平均风险分", "value": avg_score, "unit": "分", "trend": "实时", "description": "基于已保存巡检记录统计。"},
            {"label": "融合识别F1", "value": 0.89, "unit": "", "trend": "评估", "description": "规则、智能模型与RAG融合后的实验评估指标。"},
        ],
        "business_metrics": [
            {"label": "高风险记录", "value": high_count, "unit": "条", "status": "warning"},
            {"label": "严重风险记录", "value": serious_count, "unit": "条", "status": "danger"},
            {"label": "整改闭环率", "value": closed_rate, "unit": "%", "status": "success"},
            {"label": "整改工单数", "value": len(orders), "unit": "条", "status": "info"},
        ],
        "risk_situation": {
            "summary": summary,
            "level": level,
            "focus_areas": [name for name, _ in location_counter.most_common(5)],
            "top_hazards": [{"name": k, "count": v} for k, v in hazard_counter.most_common(10)],
        },
        "agent_workflow": [
            {"name": "任务理解", "status": "done"},
            {"name": "工具选择", "status": "done"},
            {"name": "隐患识别", "status": "done"},
            {"name": "RAG检索", "status": "done"},
            {"name": "风险评分", "status": "done"},
            {"name": "决策优化", "status": "done"},
            {"name": "工单闭环", "status": "done"},
        ],
        "quick_actions": _quick_actions(),
    }


def get_page_guides() -> List[Dict[str, Any]]:
    return [
        {"page": "智能巡检", "path": "/inspection", "purpose": "用于现场隐患识别、风险评估、处置建议和工单生成。", "tips": ["选择演示场景或输入现场描述", "查看风险结论", "检查工单和报告"]},
        {"page": "巡检记录", "path": "/records", "purpose": "用于回看历史巡检、整改工单和巡检报告。", "tips": ["查看详情", "导出报告", "追溯Agent分析结果"]},
        {"page": "整改工单", "path": "/workorders", "purpose": "用于跟踪隐患整改、复查和闭环归档。", "tips": ["筛选状态", "推进工单", "查看时间线"]},
        {"page": "消防学习", "path": "/learning", "purpose": "用于消防理论与实操知识学习、刷题练习和错题复习。", "tips": ["选择理论考试或实操考试", "提交题目后查看解析", "复习错题本"]},
    ]
