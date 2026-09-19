from __future__ import annotations

import hashlib
import io
from typing import Any, Dict

from services.record_persistence_service import get_inspection_record, list_inspection_records


def verify_report(report_no: str) -> Dict[str, Any]:
    for r in list_inspection_records(1000):
        if r.get("report_no") == report_no or r.get("id") == report_no:
            detail = get_inspection_record(r.get("id"))
            raw = f"{detail.get('id')}|{detail.get('report_no')}|{detail.get('risk_level')}|{detail.get('created_at')}"
            return {
                "valid": True,
                "report_no": detail.get("report_no") or detail.get("id"),
                "record_id": detail.get("id"),
                "location": detail.get("location"),
                "risk_level": detail.get("risk_level"),
                "closed_loop_status": detail.get("review_status"),
                "created_at": detail.get("created_at"),
                "verify_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper(),
            }
    return {"valid": False, "report_no": report_no, "message": "未查询到该报告编号"}


def build_pdf_bytes(record_id: str, base_url: str = "http://127.0.0.1:5173") -> Dict[str, Any]:
    record = get_inspection_record(record_id)
    if not record:
        return {"ok": False, "message": "报告不存在"}
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        import qrcode
    except Exception as exc:
        return {"ok": False, "message": f"缺少 PDF 依赖：{exc}，请执行 pip install -r requirements.txt"}

    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CNTitle', fontName='STSong-Light', fontSize=24, leading=32, alignment=1, spaceAfter=14))
    styles.add(ParagraphStyle(name='CNH2', fontName='STSong-Light', fontSize=15, leading=22, textColor=colors.HexColor('#0f172a'), spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name='CN', fontName='STSong-Light', fontSize=10.5, leading=17))
    styles.add(ParagraphStyle(name='SmallCN', fontName='STSong-Light', fontSize=9, leading=14, textColor=colors.HexColor('#475569')))
    report_no = record.get('report_no') or record.get('id')
    verify_url = f"{base_url.rstrip('/')}/report-verify/{report_no}"
    qr = qrcode.make(verify_url)
    qr_buf = io.BytesIO(); qr.save(qr_buf, format='PNG'); qr_buf.seek(0)

    story = []
    story.append(Paragraph('智慧消防智能巡检评估报告', styles['CNTitle']))
    story.append(Spacer(1, 10))
    cover = [
        ['报告编号', report_no], ['档案编号', record.get('id')], ['巡检地点', record.get('location')],
        ['风险等级', record.get('risk_level')], ['风险评分', str(record.get('risk_score'))], ['整改闭环状态', record.get('review_status')],
        ['生成时间', record.get('created_at')], ['验真链接', verify_url],
    ]
    t = Table(cover, colWidths=[35*mm, 120*mm])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'STSong-Light'),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cbd5e1')),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f8fafc')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(t)
    story.append(Spacer(1, 14))
    story.append(Paragraph(f"风险等级章：{record.get('risk_level')}　　报告二维码验真：{verify_url}", styles['CN']))
    story.append(PageBreak())
    story.append(Paragraph('一、AI 生成说明', styles['CNH2']))
    story.append(Paragraph('本报告由智慧消防Agent根据现场描述、图片证据、RAG 知识库引用、风险评分规则和整改闭环状态自动生成，建议由消防安全管理员复核后归档。', styles['CN']))
    story.append(Paragraph('二、现场描述', styles['CNH2']))
    story.append(Paragraph(record.get('description') or '未填写现场描述。', styles['CN']))
    story.append(Paragraph('三、主要隐患', styles['CNH2']))
    hazards = record.get('hazards') or []
    story.append(Paragraph('、'.join(hazards) if hazards else '未发现明显隐患。', styles['CN']))
    story.append(Paragraph('四、RAG 引用依据', styles['CNH2']))
    refs = (record.get('result') or {}).get('rag_reference_cards') or (record.get('result') or {}).get('rag_references') or []
    if refs:
        for i, r in enumerate(refs[:8], 1):
            story.append(Paragraph(f"{i}. {r.get('title') or r.get('source') or '消防知识依据'}：{r.get('summary') or r.get('content') or r.get('content_preview') or ''}", styles['SmallCN']))
    else:
        story.append(Paragraph('暂无结构化 RAG 引用依据。', styles['CN']))
    story.append(Paragraph('五、现场图片证据', styles['CNH2']))
    imgs = (record.get('result') or {}).get('image_evidence_cards') or []
    if imgs:
        for img in imgs:
            story.append(Paragraph(f"{img.get('title')}｜疑似隐患：{'、'.join(img.get('hazard_tags') or [])}｜置信度：{img.get('confidence')}｜{img.get('risk_description')}", styles['SmallCN']))
    else:
        paths = record.get('image_paths') or []
        story.append(Paragraph('；'.join(paths) if paths else '未上传图片证据或未记录图片路径。', styles['CN']))
    story.append(Paragraph('六、整改闭环状态', styles['CNH2']))
    orders = record.get('workorders') or []
    if orders:
        data = [['隐患', '状态', '责任角色', '截止时间']]
        for o in orders:
            data.append([o.get('hazard',''), o.get('status',''), o.get('responsible_role',''), o.get('deadline','')])
        wt = Table(data, colWidths=[40*mm, 25*mm, 55*mm, 35*mm])
        wt.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'STSong-Light'),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cbd5e1')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f1f5f9')),('VALIGN',(0,0),(-1,-1),'TOP')]))
        story.append(wt)
    else:
        story.append(Paragraph('暂无整改工单。', styles['CN']))
    story.append(Spacer(1, 20))
    story.append(Paragraph('签字确认：巡检人__________　复查人__________　负责人__________', styles['CN']))
    doc.build(story)
    return {"ok": True, "filename": f"{report_no}_智慧消防巡检报告.pdf", "content": buf.getvalue(), "report_no": report_no}
