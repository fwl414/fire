from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.rag_examples import get_rag_recommended_questions, get_rag_scene_cards
from services.llm_fire_analyzer import answer_question_with_llm
from services.rag_engine import get_knowledge_overview, debug_retrieve



from services.rag_admin_service import (delete_rag_entry, get_rag_entry, get_rag_stats, list_rag_entries, search_rag_entries, upsert_rag_entry)
from routers.inspection import RAG_CATEGORIES_V121

from services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["知识库"])

@router.post("/api/qa/fire")
async def fire_qa(question: str = Form(...), db: Session = Depends(get_db)):
    return await answer_question_with_llm(db, question)


# ---------------- V6 Model Setting APIs ----------------

@router.get("/api/rag/overview")
def api_rag_overview():
    return get_knowledge_overview()


@router.get("/api/rag/debug")
def api_rag_debug(query: str, hazards: str = ""):
    hazard_list = [x.strip() for x in hazards.split(",") if x.strip()]
    return debug_retrieve(query, hazard_list)



@router.get("/api/rag/recommended-questions")
def api_rag_recommended_questions():
    return get_rag_recommended_questions()


@router.get("/api/rag/scene-cards")
def api_rag_scene_cards():
    return get_rag_scene_cards()



@router.get("/api/rag/categories")
def api_rag_categories():
    return {"categories": RAG_CATEGORIES_V121}


@router.get("/api/knowledge")
def api_knowledge_list(category: str = "", enabled: str = ""):
    return list_rag_entries(category, enabled)


@router.post("/api/knowledge")
def api_knowledge_create(payload: Dict[str, Any]):
    return upsert_rag_entry(payload)


@router.get("/api/knowledge/{entry_id}")
def api_knowledge_get(entry_id: str):
    return get_rag_entry(entry_id)


@router.put("/api/knowledge/{entry_id}")
def api_knowledge_update(entry_id: str, payload: Dict[str, Any]):
    payload["id"] = entry_id
    return upsert_rag_entry(payload)


@router.delete("/api/knowledge/{entry_id}")
def api_knowledge_delete(entry_id: str):
    return delete_rag_entry(entry_id)


@router.patch("/api/knowledge/{entry_id}/status")
def api_knowledge_status(entry_id: str, payload: Dict[str, Any]):
    old = get_rag_entry(entry_id)
    if not old:
        return JSONResponse(status_code=404, content={"message": "知识条目不存在"})
    old["enabled"] = bool(payload.get("enabled", True))
    return upsert_rag_entry(old)


@router.get("/api/rag/admin/entries")
def api_rag_admin_entries(category: str = "", enabled: str = ""):
    return list_rag_entries(category, enabled)


@router.post("/api/rag/admin/entries")
def api_rag_admin_upsert(payload: Dict[str, Any]):
    return upsert_rag_entry(payload)


@router.get("/api/rag/admin/entries/{entry_id}")
def api_rag_admin_get(entry_id: str):
    return get_rag_entry(entry_id)


@router.delete("/api/rag/admin/entries/{entry_id}")
def api_rag_admin_delete(entry_id: str):
    return delete_rag_entry(entry_id)


@router.get("/api/rag/admin/search")
def api_rag_admin_search(query: str = "", limit: int = 8):
    return search_rag_entries(query, limit)


@router.get("/api/rag/admin/stats")
def api_rag_admin_stats():
    return get_rag_stats()


@router.post("/api/qa/workorder-suggestion")
def api_qa_workorder_suggestion(payload: Dict[str, Any]):
    question = payload.get("question", "")
    answer = payload.get("answer", "")
    text = f"{question} {answer}"
    risk_level = "高风险" if any(k in text for k in ["堵塞", "烟感", "报警", "电气", "违规充电", "明火", "遮挡"]) else "中风险"
    deadline = "24小时内" if risk_level == "高风险" else "3日内"
    hazard = "消防通道堵塞" if "通道" in text or "堵塞" in text else "电气火灾风险" if "电" in text else "消防安全隐患"
    return {
        "suggested": True,
        "hazard": hazard,
        "risk_level": risk_level,
        "deadline": deadline,
        "responsible_role": "物业 / 安保 / 区域安全责任人",
        "review_method": "整改完成后上传整改后照片，并由安全管理员现场复查。",
        "workorder_title": f"{hazard}整改建议",
        "recommended_action": "根据问答处置建议生成整改任务，明确责任人、整改时限和复查要求。",
        "reason": "该问题涉及疏散、设施可用性或电气安全，建议纳入整改闭环管理。"
    }



