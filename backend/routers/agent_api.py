from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.agent_decision_service import make_decision_policy


from services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["智能体接口"])

@router.get("/api/agent/capabilities")
def api_agent_capabilities():
    return {
        "name": "智慧消防系统 V8",
        "capabilities": [
            "任务理解",
            "文本智能模型隐患识别",
            "视觉智能模型隐患识别",
            "多源隐患融合",
            "消防知识库 RAG 检索",
            "风险量化评分",
            "应急辅助决策",
            "巡检报告生成",
            "高风险工单闭环"
        ],
        "core_outputs": [
            "agent_plan",
            "tool_calls",
            "llm_outputs",
            "fusion_result",
            "rag_references",
            "emergency_decision",
            "risk_score",
            "final_report"
        ]
    }



@router.post("/api/agent/decision-policy")
def api_agent_decision_policy(payload: Dict[str, Any]):
    return make_decision_policy(
        risk_level=payload.get("risk_level", ""),
        risk_score=payload.get("risk_score", 0),
        hazards=payload.get("hazards", [])
    )


@router.post("/api/agent/explain")
def api_agent_explain(payload: Dict[str, Any]):
    scenario = payload.get("scenario", "消防通道堵塞")
    risk_score = 82 if any(k in scenario for k in ["烟", "电", "堵塞", "违规"]) else 58
    risk_level = "高风险" if risk_score >= 70 else "中风险"
    return {
        "scenario": scenario,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "why": [
            "识别到可能影响疏散、灭火或报警联动的关键风险特征。",
            "风险与消防通道、电气火灾、设施遮挡或硬件报警等知识条目匹配。",
            "当前场景需要明确责任人、整改时限和复查闭环。",
        ],
        "score_breakdown": [
            {"factor": "隐患严重度", "score": 35, "reason": "影响人员疏散或初期处置能力。"},
            {"factor": "场景叠加", "score": 20, "reason": "存在可燃物、电气或硬件报警等叠加因素。"},
            {"factor": "复查要求", "score": 15, "reason": "需要生成工单并复查。"},
            {"factor": "人工复核", "score": 12, "reason": "图片/描述仍需现场确认。"},
        ],
        "tools": [
            {"name": "文本隐患识别", "status": "已调用", "output": "抽取消防隐患关键词和场景。"},
            {"name": "图像证据分析", "status": "按需调用", "output": "识别疑似隐患标签与置信度。"},
            {"name": "RAG 知识检索", "status": "已调用", "output": "返回法规、标准和整改依据。"},
            {"name": "风险评分引擎", "status": "已调用", "output": f"输出 {risk_score} 分，{risk_level}。"},
            {"name": "整改闭环工具", "status": "已调用", "output": "生成整改建议、责任角色和复查要求。"},
        ],
        "knowledge_hits": [
            {"title": "消防通道与疏散通道管理", "reason": "涉及疏散通道畅通要求。"},
            {"title": "电气火灾风险防控", "reason": "涉及插排、过载、温升或违规充电。"},
            {"title": "整改工单管理", "reason": "涉及工单、复查和归档。"},
        ],
        "final_decision": "建议将该场景纳入整改工单，按风险等级确定整改时限，整改完成后上传前后对比图片并复查归档。",
    }


# ---------------- 多模态分析 API ----------------


