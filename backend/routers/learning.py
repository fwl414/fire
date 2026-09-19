from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.learning_graph_service import get_learning_knowledge_graph, search_learning_rag, get_quiz_filter_options
from services.quiz_import_service import preview_import
from services.learning_quiz_agent import build_quiz_agent_feedback
from services.learning_smart_service import analyze_learning_progress



from services.learning_profile_service import (get_learning_profile, get_wrongbook, list_learning_attempts, save_learning_attempt)
from services.learning_service import (get_course, get_courses, get_exam_levels, get_exam_subjects, get_learning_overview, get_learning_source_docs, get_learning_source_summary, get_learning_topics, get_quiz, get_quiz_grouped, get_quiz_question, get_videos, recommend_learning_resources, submit_quiz)

from services.auth_service import get_current_user
from services.common_utils import TEXT_EXTENSIONS, read_validated_upload

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["学习培训"])

@router.get("/api/learning/overview")
def api_learning_overview():
    return get_learning_overview()


@router.get("/api/learning/topics")
def api_learning_topics():
    return get_learning_topics()


@router.get("/api/learning/courses")
def api_learning_courses(category: str = ""):
    return get_courses(category)


@router.get("/api/learning/course/{course_id}")
def api_learning_course(course_id: str):
    return get_course(course_id)


@router.get("/api/learning/videos")
def api_learning_videos(topic: str = ""):
    return get_videos(topic)


@router.get("/api/learning/quiz")
def api_learning_quiz(topic: str = "", exam_type: str = "", limit: int = 3000, exam_category: str = "", exam_level: str = "", module: str = "", exam_subject: str = ""):
    return get_quiz(topic, exam_type, limit, exam_category, exam_level, module, exam_subject)


@router.post("/api/learning/quiz/submit")
def api_learning_quiz_submit(payload: Dict[str, Any]):
    return submit_quiz(payload.get("question_id", ""), payload.get("user_answer", ""))


@router.get("/api/learning/recommendations")
def api_learning_recommendations(query: str = "", hazards: str = ""):
    hazard_list = [x.strip() for x in hazards.split(",") if x.strip()]
    return recommend_learning_resources(query, hazard_list)



@router.get("/api/learning/exam-levels")
def api_learning_exam_levels():
    return get_exam_levels()


@router.get("/api/learning/quiz-grouped")
def api_learning_quiz_grouped():
    return get_quiz_grouped()


@router.post("/api/learning/progress/analyze")
async def api_learning_progress_analyze(payload: Dict[str, Any]):
    records = payload.get("records", [])
    use_llm = bool(payload.get("use_llm", True))
    return await analyze_learning_progress(records, use_llm)



@router.post("/api/learning/quiz/agent-feedback")
def api_learning_quiz_agent_feedback(payload: Dict[str, Any]):
    question_id = payload.get("question_id", "")
    question = get_quiz_question(question_id)
    submit_result = payload.get("submit_result", {})
    recent_records = payload.get("recent_records", [])
    return build_quiz_agent_feedback(question, submit_result, recent_records)


@router.post("/api/learning/quiz/import-preview")
async def api_learning_quiz_import_preview(file: UploadFile = File(...)):
    content, _ = await read_validated_upload(
        file, TEXT_EXTENSIONS, max_bytes=5 * 1024 * 1024, label="题库文件"
    )
    return preview_import(file.filename or "question_bank.txt", content)


@router.get("/api/learning/source-summary")
def api_learning_source_summary():
    return get_learning_source_summary()


@router.get("/api/learning/source-docs")
def api_learning_source_docs():
    return get_learning_source_docs()



@router.get("/api/learning/knowledge-graph")
def api_learning_knowledge_graph(limit_questions: int = 80):
    return get_learning_knowledge_graph(limit_questions)


@router.get("/api/learning/rag-search")
def api_learning_rag_search(query: str = "", limit: int = 8):
    return search_learning_rag(query, limit)


@router.get("/api/learning/filter-options")
def api_learning_filter_options():
    return get_quiz_filter_options()



@router.get("/api/learning/exam-subjects")
def api_learning_exam_subjects():
    return get_exam_subjects()



@router.post("/api/learning/attempts")
def api_learning_attempts(payload: Dict[str, Any]):
    return save_learning_attempt(payload)


@router.get("/api/learning/attempts")
def api_learning_attempt_list(limit: int = 200):
    return list_learning_attempts(limit)


@router.get("/api/learning/wrongbook")
def api_learning_wrongbook(limit: int = 100):
    return get_wrongbook(limit)


@router.get("/api/learning/profile")
def api_learning_profile():
    return get_learning_profile()



