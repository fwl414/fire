from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db


from services.competition_service import (get_agent_evaluation_matrix, get_competition_overview, get_demo_script, get_innovation_points, get_paper_materials, get_technical_route)

from services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["技能竞赛"])

@router.get("/api/competition/overview")
def api_competition_overview():
    return get_competition_overview()


@router.get("/api/competition/technical-route")
def api_competition_technical_route():
    return get_technical_route()


@router.get("/api/competition/innovations")
def api_competition_innovations():
    return get_innovation_points()


@router.get("/api/competition/demo-script")
def api_competition_demo_script():
    return get_demo_script()


@router.get("/api/competition/agent-evaluation")
def api_competition_agent_evaluation():
    return get_agent_evaluation_matrix()


@router.get("/api/competition/paper-materials")
def api_competition_paper_materials():
    return get_paper_materials()




