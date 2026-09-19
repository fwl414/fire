from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.enhanced_evaluation import run_enhanced_evaluation
from services.evaluation_service import run_rule_evaluation


from services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["系统评估"])

@router.get("/api/evaluation/rule-baseline")
def api_rule_baseline_evaluation():
    return run_rule_evaluation()


@router.get("/api/evaluation/enhanced")
def api_enhanced_evaluation():
    return run_enhanced_evaluation()




