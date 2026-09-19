from __future__ import annotations

from services.decision_optimizer import optimize_emergency_decision
from services.agent_trace import build_agent_trace
from services.agent_tool_selector import select_agent_tools

import json
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import UploadFile
from sqlalchemy.orm import Session

from database import Device, InspectionRecord, FaultTicket
from services.text_analyzer import analyze_text, merge_hazards
from services.image_analyzer import analyze_image
from services.llm_fire_analyzer import analyze_text_with_llm
from services.risk_engine import calculate_risk
from services.rag_engine import retrieve_fire_knowledge
from services.report_service import generate_report, build_executive_summary
from services.agent_core import build_agent_plan, make_tool_call, summarize_agent
from services.decision_engine import build_emergency_decision, decision_to_text
from services.model_registry import get_active_config
from services.ai_review_service import (
    CONFIDENCE_LABELS,
    assess_confidence,
    create_review_task,
    needs_manual_review,
)
from services.risk_explainer import build_risk_explanation
from services.common_utils import IMAGE_EXTENSIONS, random_upload_name, read_validated_upload


async def save_upload(file: Optional[UploadFile]) -> str:
    if not file:
        return ""

    content, ext = await read_validated_upload(file, IMAGE_EXTENSIONS, label="巡检图片")

    upload_dir = Path("uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / random_upload_name("inspection", ext)
    target.write_bytes(content)
    return str(target)





def _match_references_for_hazard(hazard: str, refs: list[dict], limit: int = 2) -> list[str]:
    matched: list[str] = []
    for ref in refs or []:
        text = f"{ref.get('title', '')} {ref.get('category', '')} {ref.get('content', '')} {' '.join(ref.get('matched_keywords', []) or [])}"
        if hazard in text or any(word in text for word in str(hazard).replace('电气线路杂乱', '电气 线路 插排').split()):
            title = ref.get('title') or ref.get('source') or '消防知识依据'
            if title not in matched:
                matched.append(title)
        if len(matched) >= limit:
            break
    if not matched:
        for ref in (refs or [])[:limit]:
            title = ref.get('title') or ref.get('source') or '消防知识依据'
            if title not in matched:
                matched.append(title)
    return matched


def _build_v119_hazard_results(hazard_items: list[dict], refs: list[dict]) -> list[dict]:
    results: list[dict] = []
    for idx, item in enumerate(hazard_items or [], start=1):
        hazard = item.get('hazard_name') or item.get('type') or f'隐患{idx}'
        results.append({
            'id': f'hazard_{idx:02d}',
            'hazard_name': hazard,
            'risk_level': item.get('risk_level') or ('高风险' if item.get('severity') in ['高', '严重'] else '中风险'),
            'category': item.get('category', '消防安全'),
            'score': item.get('score', 0),
            'evidence': item.get('evidence') or item.get('reason') or f'系统识别到“{hazard}”相关风险。',
            'possible_consequence': item.get('possible_consequence') or '可能影响人员疏散、初期火灾处置或消防设施可用性。',
            'suggestion': item.get('suggestion') or item.get('measure') or '建议现场复核并及时整改。',
            'related_knowledge_titles': _match_references_for_hazard(hazard, refs),
            'need_immediate_fix': bool(item.get('need_immediate_fix')),
        })
    return results


def _build_v120_decision_chain(location: str, description: str, image_path: str, tool_calls: list[dict], rag_references: list[dict], risk: dict, optimized_decision: dict) -> list[dict]:
    return [
        {
            'id': 'input_understanding',
            'title': '输入理解',
            'action': '解析巡检地点、现场描述和图片证据',
            'input': f"地点：{location or '未填写'}；描述：{(description or '未填写')[:120]}；图片：{'已上传' if image_path else '未上传'}",
            'output': '系统识别该任务为消防现场巡检，需要进行隐患识别、RAG检索、风险评分和整改建议生成。',
            'status': 'completed',
        },
        {
            'id': 'tool_calling',
            'title': '工具调用',
            'action': '自动选择并调用规则识别、视觉识别、RAG检索、风险评估和报告工具',
            'input': f"工具数量：{len(tool_calls or [])}",
            'output': '已完成工具编排，输出结构化工具调用记录。',
            'status': 'completed',
        },
        {
            'id': 'knowledge_retrieval',
            'title': '知识检索',
            'action': '从消防法规、巡检标准和整改知识库中检索依据',
            'input': '现场描述 + 隐患类型',
            'output': f"检索到 {len(rag_references or [])} 条知识引用。",
            'status': 'completed',
        },
        {
            'id': 'rule_matching',
            'title': '规则匹配',
            'action': '匹配消防通道、设施遮挡、电气线路、可燃物等风险规则',
            'input': '规则识别结果 + 模型识别结果',
            'output': f"最终隐患：{'、'.join(risk.get('hazards', [])) or '未发现明显隐患'}。",
            'status': 'completed',
        },
        {
            'id': 'risk_judgement',
            'title': '风险判断',
            'action': '根据隐患严重度、数量和叠加因素计算风险等级',
            'input': str(risk.get('score_detail', {})),
            'output': f"风险评分 {risk.get('risk_score', 0)}，等级 {risk.get('risk_level', '未评估')}。",
            'status': 'completed',
        },
        {
            'id': 'decision_output',
            'title': '决策输出',
            'action': '生成整改建议、责任角色、闭环复查和报告内容',
            'input': risk.get('risk_level', ''),
            'output': optimized_decision.get('decision_summary') or optimized_decision.get('summary') or '已生成整改决策和报告。',
            'status': 'completed',
        },
    ]


def _build_v120_tool_center(tool_calls: list[dict]) -> list[dict]:
    purpose_map = {
        'TaskUnderstanding': '理解巡检任务输入，确定分析目标。',
        'RuleTextExtractor': '通过规则从文字描述中抽取消防隐患。',
        'TextLLMAnalyzer': '调用文本智能模型理解复杂现场描述。',
        'VisionLLMAnalyzer': '调用视觉智能模型或演示兜底识别图片隐患。',
        'HazardFusion': '融合规则、文本模型和视觉模型输出。',
        'RAGRetriever': '检索消防知识库，提供法规与整改依据。',
        'RiskEngine': '计算风险评分和风险等级。',
        'EmergencyDecisionEngine': '生成应急处置和整改闭环建议。',
        'ReportGenerator': '生成巡检报告。',
    }
    tools: list[dict] = []
    for idx, call in enumerate(tool_calls or [], start=1):
        name = call.get('name', f'Tool{idx}')
        tools.append({
            'id': f'tool_{idx:02d}',
            'tool_name': name,
            'purpose': purpose_map.get(name, call.get('reason', 'Agent 工具调用。')),
            'status': call.get('status', 'success'),
            'input_params': {'summary': call.get('input_summary', '')},
            'output_result': {'summary': call.get('output_summary', '')},
            'duration_ms': call.get('latency_ms', 0),
            'used_llm': bool(call.get('used_llm')),
            'model': call.get('model', ''),
        })
    return tools


def _build_v120_result_explanation(risk: dict, hazards: list[str], hazard_results: list[dict], refs: list[dict]) -> dict:
    high_items = [h for h in hazard_results if h.get('risk_level') in ['高风险', '严重风险'] or h.get('need_immediate_fix')]
    top_hazards = high_items or hazard_results[:2]
    evidence = [h.get('evidence', '') for h in top_hazards if h.get('evidence')]
    referenced = [r.get('title') or r.get('source') for r in (refs or [])[:5] if r.get('title') or r.get('source')]
    priority = '；'.join([h.get('suggestion', '') for h in top_hazards[:2] if h.get('suggestion')]) or '保持日常巡检和闭环复查。'
    return {
        'why_high_risk': risk.get('risk_reason') or f"系统识别到 {'、'.join(hazards) or '无明显隐患'}，综合判定为{risk.get('risk_level', '未评估')}。",
        'evidence_list': evidence,
        'referenced_knowledge': referenced,
        'priority_fix': priority,
        'score_logic': f"风险评分={risk.get('risk_score', 0)}，评分明细={risk.get('score_detail', {})}。",
    }


def _build_rag_reference_cards(refs: list[dict]) -> list[dict]:
    cards: list[dict] = []
    for idx, ref in enumerate(refs or [], start=1):
        score = ref.get('score', ref.get('similarity', 0)) or 0
        try:
            similarity = round(float(score) * 100 if float(score) <= 1 else float(score), 1)
        except Exception:
            similarity = 0
        cards.append({
            'id': ref.get('chunk_id') or ref.get('id') or f'ref_{idx:02d}',
            'title': ref.get('title') or ref.get('source') or f'引用{idx}',
            'category': ref.get('category') or '消防知识',
            'similarity': similarity,
            'summary': (ref.get('content') or ref.get('summary') or '')[:160],
            'source': ref.get('source') or ref.get('source_type') or '系统知识库',
            'content_preview': ref.get('content') or ref.get('text') or ref.get('snippet') or '',
            'matched_keywords': ref.get('matched_keywords', []),
            'match_reasons': ref.get('match_reasons', []),
        })
    return cards


async def run_inspection_agent(
    db: Session,
    device_id: Optional[int],
    location: str,
    description: str,
    image_file: Optional[UploadFile] = None,
    tenant_id: Optional[int] = None,
):
    start_total = time.perf_counter()
    agent_steps = []
    tool_calls = []
    llm_outputs = {}

    device = (
        db.query(Device).filter(
            Device.id == device_id,
            Device.tenant_id == tenant_id,
        ).first()
        if device_id and tenant_id is not None
        else (db.query(Device).filter(Device.id == device_id).first() if device_id else None)
    )
    text_cfg = get_active_config(db, "text")
    vision_cfg = get_active_config(db, "vision")

    image_path = await save_upload(image_file)
    tool_selection = select_agent_tools(
        task_type="inspection",
        has_text=bool(description),
        has_image=bool(image_path),
        has_hardware_event=False,
        need_report=True,
        need_rag=True,
    )
    agent_plan = build_agent_plan(
        has_image=bool(image_path),
        has_text_model=bool(text_cfg),
        has_vision_model=bool(vision_cfg),
    )

    if device:
        agent_steps.append(f"已关联设备：{device.device_name}（{device.device_code}）。")
    else:
        agent_steps.append("未关联具体设备，本次按区域巡检任务处理。")

    # 步骤 1：任务理解
    task_summary = {
        "location": location,
        "has_description": bool(description),
        "has_image": bool(image_path),
        "device": device.device_name if device else "",
    }
    tool_calls.append(make_tool_call(
        name="TaskUnderstanding",
        tool_type="agent",
        status="success",
        input_summary="巡检地点、现场描述、图片、设备信息",
        output_summary=f"任务理解完成：{task_summary}",
        used_llm=False,
        raw_output=task_summary,
    ))

    # 步骤 2：规则文本抽取
    t0 = time.perf_counter()
    text_rule_result = analyze_text(description)
    tool_calls.append(make_tool_call(
        name="RuleTextExtractor",
        tool_type="rule",
        status="success",
        input_summary=description[:120] if description else "空描述",
        output_summary=f"规则识别隐患：{text_rule_result.get('hazards', [])}",
        used_llm=False,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        raw_output=text_rule_result,
    ))
    agent_steps.append(f"规则文本隐患抽取完成：{text_rule_result.get('hazards', [])}")

    # 步骤 3：文本智能模型抽取
    t0 = time.perf_counter()
    text_llm_result = await analyze_text_with_llm(db, description)
    llm_outputs["text_model"] = {
        "used": bool(text_llm_result.get("used_text_model_api")),
        "provider": text_llm_result.get("provider", ""),
        "model": text_llm_result.get("model", ""),
        "raw_content": text_llm_result.get("raw_content", ""),
        "error": text_llm_result.get("text_model_error", ""),
        "hazards": text_llm_result.get("hazards", []),
    }
    tool_calls.append(make_tool_call(
        name="TextLLMAnalyzer",
        tool_type="llm",
        status="success" if text_llm_result.get("used_text_model_api") else "fallback",
        input_summary="现场文字描述",
        output_summary=f"文本智能模型识别隐患：{text_llm_result.get('hazards', [])}",
        used_llm=bool(text_llm_result.get("used_text_model_api")),
        model=f"{text_llm_result.get('provider', '')}/{text_llm_result.get('model', '')}",
        latency_ms=int((time.perf_counter() - t0) * 1000),
        raw_output=text_llm_result,
    ))
    if text_llm_result.get("used_text_model_api"):
        agent_steps.append(
            f"文本智能模型调用成功：{text_llm_result.get('provider')} / {text_llm_result.get('model')}，"
            f"识别结果：{text_llm_result.get('hazards', [])}"
        )
    else:
        agent_steps.append(f"文本智能模型未调用或调用失败，原因：{text_llm_result.get('text_model_error') or '未知'}")

    # 步骤 4：视觉智能模型抽取
    t0 = time.perf_counter()
    image_result = await analyze_image(db, image_path)
    llm_outputs["vision_model"] = {
        "used": bool(image_result.get("used_vision_api")),
        "provider": image_result.get("provider", ""),
        "model": image_result.get("model", ""),
        "raw_content": image_result.get("raw_content", ""),
        "error": image_result.get("vision_error", ""),
        "hazards": image_result.get("hazards", []),
        "local_image_fallback": bool(image_result.get("local_image_fallback")),
    }
    tool_calls.append(make_tool_call(
        name="VisionLLMAnalyzer",
        tool_type="llm",
        status="success" if image_result.get("used_vision_api") else ("skipped" if not image_path else "fallback"),
        input_summary="现场图片" if image_path else "未上传图片",
        output_summary=f"视觉模型识别隐患：{image_result.get('hazards', [])}",
        used_llm=bool(image_result.get("used_vision_api")),
        model=f"{image_result.get('provider', '')}/{image_result.get('model', '')}",
        latency_ms=int((time.perf_counter() - t0) * 1000),
        raw_output=image_result,
    ))
    if image_result.get("used_vision_api"):
        agent_steps.append(
            f"视觉智能模型调用成功：{image_result.get('provider')} / {image_result.get('model')}，"
            f"识别结果：{image_result.get('hazards', [])}"
        )
    elif image_path:
        agent_steps.append(f"视觉智能模型未调用或调用失败，原因：{image_result.get('vision_error') or '未配置'}")

    # 步骤 5：结果融合
    hazards = merge_hazards(
        text_rule_result.get("hazards"),
        text_llm_result.get("hazards"),
        image_result.get("hazards"),
    )
    fusion_result = {
        "rule_hazards": text_rule_result.get("hazards", []),
        "text_llm_hazards": text_llm_result.get("hazards", []),
        "vision_llm_hazards": image_result.get("hazards", []),
        "final_hazards": hazards,
    }
    tool_calls.append(make_tool_call(
        name="HazardFusion",
        tool_type="fusion",
        status="success",
        input_summary="规则识别、文本智能模型、视觉智能模型输出",
        output_summary=f"融合后隐患：{hazards}",
        used_llm=False,
        raw_output=fusion_result,
    ))

    # 步骤 6：RAG 检索
    t0 = time.perf_counter()
    rag_references = retrieve_fire_knowledge(description, hazards)
    tool_calls.append(make_tool_call(
        name="RAGRetriever",
        tool_type="rag",
        status="success",
        input_summary="现场描述 + 最终隐患",
        output_summary=f"检索到 {len(rag_references)} 条消防知识引用",
        used_llm=False,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        raw_output=rag_references,
    ))
    agent_steps.append(f"消防知识库检索完成：命中 {len(rag_references)} 条参考知识。")

    # 步骤 7：风险引擎
    t0 = time.perf_counter()
    risk = calculate_risk(hazards)
    hazard_items = risk.get("hazard_items", [])
    tool_calls.append(make_tool_call(
        name="RiskEngine",
        tool_type="algorithm",
        status="success",
        input_summary=f"最终隐患：{hazards}",
        output_summary=f"风险评分 {risk['risk_score']}，等级 {risk['risk_level']}",
        used_llm=False,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        raw_output=risk,
    ))
    agent_steps.append(f"风险评分完成：{risk['risk_score']} 分，等级：{risk['risk_level']}")

    # 步骤 8：应急决策
    decision = build_emergency_decision(hazards, risk["risk_score"], risk["risk_level"])
    optimized_decision = optimize_emergency_decision(
        hazards=hazards,
        risk_score=risk["risk_score"],
        risk_level=risk["risk_level"],
        base_decision=decision,
        location=location,
    )
    suggestion = text_llm_result.get("suggestion") or decision_to_text(decision)
    tool_calls.append(make_tool_call(
        name="EmergencyDecisionEngine",
        tool_type="decision",
        status="success",
        input_summary="风险等级、风险评分、最终隐患、知识库引用",
        output_summary=f"处置优先级：{decision.get('priority')}，是否工单：{decision.get('need_ticket')}",
        used_llm=bool(text_llm_result.get("used_text_model_api")),
        model=f"{text_llm_result.get('provider', '')}/{text_llm_result.get('model', '')}" if text_llm_result.get("used_text_model_api") else "",
        raw_output=decision,
    ))

    # 步骤 8.5：可解释性分析
    risk_explanation = build_risk_explanation(
        hazards=hazards,
        hazard_items=hazard_items,
        risk_score=risk["risk_score"],
        risk_level=risk["risk_level"],
        fusion_result=fusion_result,
        rag_references=rag_references,
        emergency_decision=decision,
    )

    # 步骤 9：报告生成
    report = generate_report(
        device=device,
        location=location,
        description=description,
        hazards=hazards,
        risk_score=risk["risk_score"],
        risk_level=risk["risk_level"],
        suggestion=suggestion,
        knowledge_refs=rag_references,
        agent_steps=agent_steps,
        hazard_items=hazard_items,
        risk_reason=risk.get("risk_reason", ""),
    )
    tool_calls.append(make_tool_call(
        name="ReportGenerator",
        tool_type="template",
        status="success",
        input_summary="巡检全流程结构化结果",
        output_summary="巡检报告生成完成",
        used_llm=False,
    ))
    agent_steps.append("巡检报告生成完成。")

    provider = text_llm_result.get("provider") or image_result.get("provider") or ""
    model_name = text_llm_result.get("model") or image_result.get("model") or ""

    record = InspectionRecord(
        tenant_id=tenant_id,
        device_id=device.id if device else None,
        device_code=device.device_code if device else "",
        device_name=device.device_name if device else "",
        location=location,
        description=description,
        image_path=image_path,
        hazards=json.dumps(hazards, ensure_ascii=False),
        risk_score=risk["risk_score"],
        risk_level=risk["risk_level"],
        suggestion=suggestion,
        report=report,
        agent_steps=json.dumps(agent_steps, ensure_ascii=False),
        used_vision_api=bool(image_result.get("used_vision_api")),
        used_text_model_api=bool(text_llm_result.get("used_text_model_api")),
        model_provider=provider,
        model_name=model_name,
    )
    db.add(record)
    db.flush()

    auto_ticket = False
    review_task_id = None
    review_reason = ""
    confidence = assess_confidence(
        used_vision_api=bool(image_result.get("used_vision_api")),
        used_text_model_api=bool(text_llm_result.get("used_text_model_api")),
        vision_error=image_result.get("vision_error", ""),
        text_model_error=text_llm_result.get("text_model_error", ""),
    )

    if decision.get("need_ticket"):
        review_required, review_reason = needs_manual_review(
            risk_level=risk["risk_level"],
            confidence=confidence,
        )
        if review_required:
            # 低可信或高风险结论先进入人工复核，避免假结果直接下发工单
            task = create_review_task(
                db,
                tenant_id=tenant_id,
                source="inspection",
                record_id=record.id,
                risk_level=risk["risk_level"],
                risk_score=risk["risk_score"],
                hazards=hazards,
                confidence=confidence,
                reason=review_reason,
                ai_summary=suggestion,
                location=location,
            )
            review_task_id = task.id
            agent_steps.append(
                f"AI 结论置信度{CONFIDENCE_LABELS.get(confidence, confidence)}，"
                f"已提交人工复核（{review_reason}），工单待复核通过后生成。"
            )
        else:
            ticket = FaultTicket(
                tenant_id=tenant_id,
                record_id=record.id,
                device_id=device.id if device else None,
                title=f"{risk['risk_level']}消防隐患整改工单",
                description=f"隐患：{'、'.join(hazards)}\n\n整改建议：\n{suggestion}",
                risk_level=risk["risk_level"],
                status="待受理",
            )
            db.add(ticket)
            auto_ticket = True
            agent_steps.append("风险等级较高，已自动生成故障整改工单。")

    record.agent_steps = json.dumps(agent_steps, ensure_ascii=False)

    if device:
        device.last_inspection_time = datetime.utcnow()
        if risk["risk_level"] in ["高风险", "严重风险"]:
            device.status = "异常"
        elif risk["risk_level"] == "低风险":
            device.status = "正常"

    db.commit()
    db.refresh(record)

    agent_summary = summarize_agent(agent_plan, tool_calls)
    agent_trace = build_agent_trace(
        task={
            "type": "inspection",
            "location": location,
            "description": description,
            "has_image": bool(image_path),
            "device_id": device.id if device else None,
        },
        tool_selection=tool_selection,
        agent_plan=agent_plan,
        tool_calls=tool_calls,
        rag_references=rag_references,
        risk_result={
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "hazards": hazards,
        },
        decision=optimized_decision,
    )
    hazard_results = _build_v119_hazard_results(hazard_items, rag_references)
    rag_reference_cards = _build_rag_reference_cards(rag_references)
    agent_decision_chain = _build_v120_decision_chain(
        location=location,
        description=description,
        image_path=image_path,
        tool_calls=tool_calls,
        rag_references=rag_references,
        risk=risk,
        optimized_decision=optimized_decision,
    )
    agent_tool_center = _build_v120_tool_center(tool_calls)
    result_explanation = _build_v120_result_explanation(risk, hazards, hazard_results, rag_references)

    response_time_ms = int((time.perf_counter() - start_total) * 1000)

    return {
        "record_id": record.id,
        "device": {
            "id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "location": device.location,
        } if device else None,
        "location": location,
        "description": description,
        "image_path": image_path,
        "image_paths": [image_path] if image_path else [],

        "tool_selection": tool_selection,
        "agent_plan": agent_plan,
        "tool_calls": tool_calls,
        "agent_summary": agent_summary,
        "agent_trace": agent_trace,
        "llm_outputs": llm_outputs,

        "hazards": hazards,
        "hazard_items": hazard_items,
        "hazard_results": hazard_results,
        "fusion_result": fusion_result,
        "risk_score": risk["risk_score"],
        "risk_level": risk["risk_level"],
        "risk_label": risk.get("risk_label", ""),
        "risk_reason": risk.get("risk_reason", ""),
        "category_stats": risk.get("category_stats", {}),
        "score_detail": risk["score_detail"],

        "rag_references": rag_references,
        "rag_reference_cards": rag_reference_cards,
        "knowledge_refs": rag_references,
        "emergency_decision": decision,
        "optimized_decision": optimized_decision,
        "risk_explanation": risk_explanation,
        "agent_decision_chain": agent_decision_chain,
        "agent_tool_center": agent_tool_center,
        "result_explanation": result_explanation,

        "executive_summary": build_executive_summary(hazards, risk["risk_score"], risk["risk_level"]),
        "suggestion": suggestion,
        "report": report,
        "agent_steps": agent_steps,
        "auto_ticket": auto_ticket,
        "confidence": confidence,
        "review_required": review_task_id is not None,
        "review_task_id": review_task_id,
        "review_reason": review_reason,

        "used_text_model_api": bool(text_llm_result.get("used_text_model_api")),
        "text_model_error": text_llm_result.get("text_model_error", ""),
        "used_vision_api": bool(image_result.get("used_vision_api")),
        "local_image_fallback": bool(image_result.get("local_image_fallback")),
        "vision_error": image_result.get("vision_error", ""),
        "model_provider": provider,
        "model_name": model_name,
        "response_time_ms": response_time_ms,
    }
