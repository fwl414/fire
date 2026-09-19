from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.demo_scenario_service import get_demo_scenarios, get_demo_scenario
from services.project_overview import get_project_overview
from services.demo_seed import seed_demo_data, seed_runtime_demo_data, seed_hardware_demo_data
from services.defense_service import get_defense_demo_flow
from services.auth_service import get_current_user


router = APIRouter(dependencies=[Depends(get_current_user)])

@router.post("/api/demo/seed")
def api_seed_demo_data(db: Session = Depends(get_db)):
    if os.environ.get("ENV", "development").lower() in ("production", "prod"):
        raise HTTPException(status_code=404, detail="Not Found")
    sql_result = seed_demo_data(db)
    runtime_result = seed_runtime_demo_data()
    hardware_result = seed_hardware_demo_data()
    return {
        "message": "V1.0.0 演示数据已生成：设备、遥测、巡检记录、整改工单、报告和硬件事件均已准备。",
        "sqlalchemy_data": sql_result,
        "runtime_data": runtime_result,
        "hardware_data": hardware_result,
    }


@router.post("/api/demo/seed-all")
def api_seed_all_demo_data(db: Session = Depends(get_db)):
    return api_seed_demo_data(db)


@router.get("/api/defense/demo-flow")
def api_defense_demo_flow():
    return get_defense_demo_flow()



@router.get("/api/project/overview")
def api_project_overview():
    return get_project_overview()



@router.get("/api/demo/scenarios")
def api_demo_scenarios():
    return get_demo_scenarios()


@router.get("/api/demo/scenarios/{scenario_id}")
def api_demo_scenario(scenario_id: str):
    return get_demo_scenario(scenario_id)



