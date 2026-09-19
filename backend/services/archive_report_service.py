from __future__ import annotations

import html
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
from typing import Any, Dict, List

from services.operation_log_service import list_operation_logs
from services.record_persistence_service import (
    list_inspection_records,
    get_inspection_record,
    list_workorders,
    export_report_text,
)


REPORT_TEMPLATES = [
    {
        "key": "standard",
        "name": "标准巡检报告",
        "description": "适用于常规消防巡检记录归档，包含基本信息、隐患明细、整改建议与复查要求。",
        "sections": ["巡检基本信息", "现场图片证据", "风险评估结论", "隐患明细", "整改建议", "RAG引用依据", "闭环复查建议"],
    },
    {
        "key": "high_risk",
        "name": "高风险专项报告",
        "description": "适用于消防通道堵塞、设施遮挡、电气火灾等高风险场景，突出立即整改和责任闭环。",
        "sections": ["高风险摘要", "风险证据", "法规依据", "应急处置建议", "整改工单", "复查要求"],
    },
    {
        "key": "archive",
        "name": "巡检档案归档单",
        "description": "适用于归档留存，突出档案编号、报告编号、复查状态和闭环记录。",
        "sections": ["档案信息", "巡检结果", "处置记录", "闭环状态", "归档说明"],
    },
]


def _parse_time(text: str) -> datetime | None:
    if not text:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"]:
        try:
            return datetime.strptime(text[:19] if " " in fmt else text[:10], fmt)
        except Exception:
            continue
    return None


def _in_date_range(row: Dict[str, Any], start_date: str = "", end_date: str = "") -> bool:
    created = _parse_time(row.get("created_at", ""))
    if not created:
        return True
    if start_date:
        start = _parse_time(start_date)
        if start and created.date() < start.date():
            return False
    if end_date:
        end = _parse_time(end_date)
        if end and created.date() > end.date():
            return False
    return True


def _keyword_match(row: Dict[str, Any], keyword: str) -> bool:
    if not keyword:
        return True
    text = " ".join([
        str(row.get("id", "")),
        str(row.get("report_no", "")),
        str(row.get("location", "")),
        str(row.get("description", "")),
        " ".join(row.get("hazards", []) or []),
        " ".join(row.get("tags", []) or []),
    ]).lower()
    return keyword.lower() in text


def _status_of_orders(record_id: str, tenant_id: int | None = None) -> Dict[str, Any]:
    orders = [
        order
        for order in list_workorders("", 500, tenant_id=tenant_id)
        if order.get("inspection_id") == record_id
    ]
    closed = len([o for o in orders if o.get("status") == "已闭环"])
    return {
        "orders": orders,
        "workorder_count": len(orders),
        "closed_count": closed,
        "closed_loop_rate": round(closed / len(orders) * 100, 1) if orders else 0,
        "has_pending": any(o.get("status") != "已闭环" for o in orders),
    }


def _report_quality_score(record: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    checklist: List[Dict[str, Any]] = []
    checks = [
        ("巡检地点", bool(record.get("location"))),
        ("现场描述", bool(record.get("description"))),
        ("风险等级", bool(record.get("risk_level"))),
        ("隐患列表", bool(record.get("hazards"))),
        ("整改工单", bool(record.get("workorders"))),
        ("RAG依据", bool((record.get("result") or {}).get("rag_reference_cards") or (record.get("result") or {}).get("rag_references"))),
        ("报告编号", bool(record.get("report_no"))),
        ("复查状态", bool(record.get("review_status"))),
    ]
    for label, ok in checks:
        checklist.append({"label": label, "ok": ok})
        if ok:
            score += 12.5
    return {"score": round(score, 1), "checklist": checklist}


def list_archives(
    keyword: str = "",
    risk_level: str = "",
    review_status: str = "",
    archive_status: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 200,
    tenant_id: int | None = None,
) -> List[Dict[str, Any]]:
    rows = list_inspection_records(limit=500, tenant_id=tenant_id)
    result: List[Dict[str, Any]] = []
    for row in rows:
        if risk_level and row.get("risk_level") != risk_level:
            continue
        if review_status and row.get("review_status") != review_status:
            continue
        if archive_status and row.get("archive_status") != archive_status:
            continue
        if not _in_date_range(row, start_date, end_date):
            continue
        if not _keyword_match(row, keyword):
            continue
        orders = _status_of_orders(row.get("id", ""), tenant_id=tenant_id)
        row = dict(row)
        row.update({
            "workorder_count": orders["workorder_count"],
            "closed_loop_rate": orders["closed_loop_rate"],
            "report_status": "已生成" if row.get("report_no") else "待生成",
            "priority": "立即处理" if row.get("risk_level") in ["严重风险", "高风险"] else ("限期整改" if row.get("risk_level") == "中风险" else "持续观察"),
        })
        result.append(row)
    return result[:limit]


def get_archive_dashboard(tenant_id: int | None = None) -> Dict[str, Any]:
    records = list_archives(limit=500, tenant_id=tenant_id)
    orders = list_workorders("", 500, tenant_id=tenant_id)
    closed = len([o for o in orders if o.get("status") == "已闭环"])
    hazard_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    month_counter: defaultdict[str, int] = defaultdict(int)
    review_counter: Counter[str] = Counter()
    for row in records:
        hazard_counter.update(row.get("hazards", []) or [])
        risk_counter.update([row.get("risk_level") or "未评估"])
        review_counter.update([row.get("review_status") or "待复查"])
        dt = _parse_time(row.get("created_at", ""))
        if dt:
            month_counter[dt.strftime("%Y-%m")] += 1
    return {
        "archive_count": len(records),
        "report_count": len([r for r in records if r.get("report_no")]),
        "high_risk_count": len([r for r in records if r.get("risk_level") in ["高风险", "严重风险"]]),
        "pending_review_count": len([r for r in records if r.get("review_status") in ["待复查", "持续跟踪"]]),
        "workorder_count": len(orders),
        "closed_workorder_count": closed,
        "closed_loop_rate": round(closed / len(orders) * 100, 1) if orders else 0,
        "risk_distribution": dict(risk_counter),
        "review_distribution": dict(review_counter),
        "top_hazards": [{"name": k, "count": v} for k, v in hazard_counter.most_common(8)],
        "monthly_trend": [{"month": k, "count": v} for k, v in sorted(month_counter.items())[-8:]],
    }


def get_archive_detail(record_id: str, tenant_id: int | None = None) -> Dict[str, Any]:
    record = get_inspection_record(record_id, tenant_id=tenant_id)
    if not record:
        return {}
    quality = _report_quality_score(record)
    result = record.get("result", {}) or {}
    refs = result.get("rag_reference_cards", []) or result.get("rag_references", []) or []
    hazard_details = result.get("hazard_results", []) or result.get("hazard_items", []) or []
    source_type = "硬件转巡检" if any("硬件" in str(x) for x in record.get("tags", [])) else ("演示数据" if "DEMO" in str(record.get("description", "")).upper() else "人工巡检")
    orders = record.get("workorders", []) or []
    closed = len([o for o in orders if o.get("status") == "已闭环"])
    report_no = record.get("report_no") or record.get("id")
    report_hash = hashlib.sha256("|".join([str(record.get("id")), str(report_no), str(record.get("location")), str(record.get("risk_level"))]).encode("utf-8")).hexdigest()[:16].upper()
    archive_timeline = [
        {"time": record.get("created_at"), "title": "创建巡检档案", "content": "现场巡检结果已生成并写入档案库。"},
        {"time": record.get("created_at"), "title": "生成报告编号", "content": f"报告编号：{report_no or '未生成'}。"},
        {"time": record.get("updated_at"), "title": "归档状态更新", "content": f"档案状态：{record.get('archive_status')}；复查状态：{record.get('review_status')}。"},
    ]
    try:
        real_logs = list_operation_logs(target_id=record.get("id"), limit=50)
        # 追加关联工单日志。
        for o in orders:
            real_logs.extend(list_operation_logs(target_id=o.get("id"), limit=50))
        for log in sorted(real_logs, key=lambda x: x.get("created_at", "")):
            archive_timeline.append({
                "time": log.get("created_at"),
                "title": log.get("title") or log.get("action"),
                "content": f"{log.get('operator') or '系统'}｜{log.get('detail') or ''}",
                "module": log.get("module"),
                "link": log.get("link"),
            })
    except Exception:
        pass
    before_after_images = []
    for order in orders:
        archive_timeline.append({
            "time": order.get("updated_at") or order.get("created_at"),
            "title": f"工单：{order.get('status')}",
            "content": f"{order.get('hazard')}｜{order.get('recommended_action')}",
        })
        before_after_images.append({
            "order_id": order.get("id"),
            "hazard": order.get("hazard"),
            "before_images": order.get("before_images", []) or record.get("image_paths", []),
            "after_images": order.get("after_images", []),
            "review_images": order.get("review_images", []),
            "review_note": order.get("review_note", ""),
        })
    return {
        **record,
        "quality": quality,
        "hazard_details": hazard_details,
        "rag_references": refs,
        "source_type": source_type,
        "report_status": "已生成" if report_no else "待生成",
        "report_verify_url": f"/report-verify/{report_no}",
        "report_hash": report_hash,
        "closure_status": f"{closed}/{len(orders)} 工单已闭环" if orders else "暂无关联工单",
        "operation_logs": archive_timeline,
        "before_after_images": before_after_images,
        "archive_timeline": archive_timeline,
        "report_outline": [
            "巡检基本信息",
            "现场图片证据",
            "综合风险结论",
            "隐患识别明细",
            "整改与应急建议",
            "RAG引用依据",
            "整改工单与复查闭环",
        ],
    }


def build_enhanced_report(
    record_id: str,
    template: str = "standard",
    fmt: str = "markdown",
    tenant_id: int | None = None,
) -> Dict[str, Any]:
    base = export_report_text(record_id, tenant_id=tenant_id)
    detail = get_archive_detail(record_id, tenant_id=tenant_id)
    if not detail:
        return {"filename": "", "content": "", "mime_type": "text/plain"}
    if fmt == "html":
        return {
            "filename": f"{record_id}_enhanced_inspection_report.html",
            "mime_type": "text/html;charset=utf-8",
            "content": build_report_html(detail, template=template),
        }
    return {
        "filename": base.get("filename") or f"{record_id}_enhanced_inspection_report.md",
        "mime_type": "text/markdown;charset=utf-8",
        "content": base.get("content", ""),
    }


def _risk_color(level: str) -> str:
    if level in ["严重风险", "高风险"]:
        return "#dc2626"
    if level == "中风险":
        return "#d97706"
    return "#16a34a"


def build_report_html(detail: Dict[str, Any], template: str = "standard") -> str:
    esc = html.escape
    risk_level = detail.get("risk_level", "未评估")
    color = _risk_color(risk_level)
    hazards = detail.get("hazard_details") or []
    refs = detail.get("rag_references") or []
    workorders = detail.get("workorders") or []
    images = detail.get("image_paths") or []
    quality = detail.get("quality", {}).get("score", 0)

    hazard_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(str(h.get('hazard_name') or h.get('type') or '隐患'))}</td>"
        f"<td>{esc(str(h.get('risk_level') or h.get('severity') or risk_level))}</td>"
        f"<td>{esc(str(h.get('evidence') or h.get('reason') or '系统识别到相关风险'))}</td>"
        f"<td>{esc(str(h.get('suggestion') or h.get('measure') or '建议现场复核并整改'))}</td></tr>"
        for i, h in enumerate(hazards, start=1)
    ) or f"<tr><td colspan='5'>{esc('未发现明显隐患或暂无结构化隐患明细')}</td></tr>"

    ref_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(str(r.get('title') or r.get('source') or '引用依据'))}</td>"
        f"<td>{esc(str(r.get('category') or '消防知识'))}</td>"
        f"<td>{esc(str(r.get('similarity') or r.get('score') or ''))}</td>"
        f"<td>{esc(str(r.get('summary') or r.get('content') or r.get('content_preview') or ''))}</td></tr>"
        for i, r in enumerate(refs, start=1)
    ) or f"<tr><td colspan='5'>{esc('暂无 RAG 引用依据')}</td></tr>"

    order_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(str(o.get('hazard') or '整改事项'))}</td>"
        f"<td>{esc(str(o.get('status') or '待派单'))}</td>"
        f"<td>{esc(str(o.get('responsible_role') or '安全管理员'))}</td>"
        f"<td>{esc(str(o.get('deadline') or ''))}</td>"
        f"<td>{esc(str(o.get('recommended_action') or ''))}</td></tr>"
        for i, o in enumerate(workorders, start=1)
    ) or f"<tr><td colspan='6'>{esc('暂无整改工单')}</td></tr>"

    image_items = "".join(f"<li>{esc(str(p))}</li>" for p in images) or "<li>未记录图片路径。可在后续版本扩展为报告内嵌图片。</li>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{esc(detail.get('report_no') or detail.get('id'))} 智慧消防巡检报告</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; color:#0f172a; background:#f1f5f9; margin:0; padding:32px; }}
.paper {{ max-width: 980px; margin:0 auto; background:#fff; padding:46px; box-shadow:0 10px 30px rgba(15,23,42,.10); }}
h1 {{ text-align:center; margin:0 0 8px; font-size:28px; }}
.subtitle {{ text-align:center; color:#64748b; margin-bottom:30px; }}
.meta {{ display:grid; grid-template-columns:repeat(2,1fr); border:1px solid #cbd5e1; margin:24px 0; }}
.meta div {{ padding:10px 12px; border-bottom:1px solid #e2e8f0; }}
.section {{ margin-top:28px; page-break-inside:avoid; }}
h2 {{ font-size:18px; border-left:5px solid #2563eb; padding-left:10px; }}
.badge {{ display:inline-block; padding:6px 12px; border-radius:999px; color:white; background:{color}; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
th, td {{ border:1px solid #cbd5e1; padding:9px; vertical-align:top; }}
th {{ background:#f8fafc; }}
.summary-card {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
.summary-card div {{ border:1px solid #e2e8f0; border-radius:12px; padding:12px; background:#f8fafc; }}
.summary-card strong {{ display:block; font-size:22px; color:#2563eb; margin-top:6px; }}
.footer {{ margin-top:40px; color:#64748b; font-size:12px; text-align:center; }}
@media print {{ body {{ background:white; padding:0; }} .paper {{ box-shadow:none; max-width:none; padding:0; }} }}
</style>
</head>
<body>
<div class="paper">
<h1>智慧消防风险评估与应急辅助决策报告</h1>
<div class="subtitle">巡检报告与档案增强版 V1.0.0 · 模板：{esc(template)}</div>

<div class="meta">
  <div>报告编号：{esc(str(detail.get('report_no') or '-'))}</div>
  <div>档案编号：{esc(str(detail.get('id') or '-'))}</div>
  <div>巡检地点：{esc(str(detail.get('location') or '-'))}</div>
  <div>巡检时间：{esc(str(detail.get('created_at') or '-'))}</div>
  <div>巡检人员：{esc(str(detail.get('inspector') or '安全管理员'))}</div>
  <div>复查状态：{esc(str(detail.get('review_status') or '-'))}</div>
  <div>风险等级：<span class="badge">{esc(risk_level)}</span></div>
  <div>风险评分：{esc(str(detail.get('risk_score') or 0))}</div>
</div>

<div class="section summary-card">
  <div>隐患数量<strong>{len(detail.get('hazards') or [])}</strong></div>
  <div>整改工单<strong>{len(workorders)}</strong></div>
  <div>图片证据<strong>{len(images)}</strong></div>
  <div>报告完整度<strong>{quality}%</strong></div>
</div>

<div class="section"><h2>一、巡检基本信息</h2><p>{esc(str(detail.get('description') or '未填写'))}</p></div>
<div class="section"><h2>二、现场图片证据</h2><ul>{image_items}</ul></div>
<div class="section"><h2>三、综合风险结论</h2><p>本次巡检综合风险等级为 <b style="color:{color}">{esc(risk_level)}</b>，风险评分 {esc(str(detail.get('risk_score') or 0))} 分，识别隐患：{esc('、'.join(detail.get('hazards') or []) or '无')}。</p></div>
<div class="section"><h2>四、隐患明细与整改建议</h2><table><thead><tr><th>#</th><th>隐患</th><th>等级</th><th>识别依据</th><th>整改建议</th></tr></thead><tbody>{hazard_rows}</tbody></table></div>
<div class="section"><h2>五、RAG 引用依据</h2><table><thead><tr><th>#</th><th>标题</th><th>分类</th><th>相似度</th><th>摘要</th></tr></thead><tbody>{ref_rows}</tbody></table></div>
<div class="section"><h2>六、整改工单与复查</h2><table><thead><tr><th>#</th><th>隐患</th><th>状态</th><th>责任角色</th><th>整改时限</th><th>整改建议</th></tr></thead><tbody>{order_rows}</tbody></table></div>
<div class="section"><h2>七、归档说明</h2><p>报告由巡检模块生成，包含现场输入、隐患识别、风险评分、知识引用和整改工单信息。报告可作为内部巡检记录和整改追踪使用。</p></div>
<div class="footer">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 智慧消防系统 V1.0.0</div>
</div>
</body>
</html>"""
