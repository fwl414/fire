from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.auth_service import get_current_user, require_role

router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_role("admin"))], tags=["系统管理"])

@router.get("/api/system/llm-status")
def llm_status(db: Session = Depends(get_db)):
    text_cfg = db.query(ModelConfig).filter(ModelConfig.enabled == True, ModelConfig.text_model != "").first()
    vision_cfg = db.query(ModelConfig).filter(ModelConfig.enabled == True, ModelConfig.vision_model != "").first()
    return {
        "text_model_enabled": bool(text_cfg),
        "vision_model_enabled": bool(vision_cfg),
        "text_model": {
            "id": text_cfg.id,
            "name": text_cfg.name,
            "provider": text_cfg.provider,
            "model": text_cfg.text_model,
        } if text_cfg else None,
        "vision_model": {
            "id": vision_cfg.id,
            "name": vision_cfg.name,
            "provider": vision_cfg.provider,
            "model": vision_cfg.vision_model,
        } if vision_cfg else None,
        "message": "智能巡检会优先调用文本智能模型分析现场描述；上传图片且启用视觉模型时会调用视觉智能模型。"
    }


@router.get("/api/system/routes")
def api_system_routes():
    items = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = sorted([m for m in getattr(route, "methods", []) if m not in {"HEAD", "OPTIONS"}])
        if path.startswith("/api") or path == "/health":
            items.append({"path": path, "methods": methods, "name": getattr(route, "name", "")})
    return {"version": "V1.0.0", "count": len(items), "routes": sorted(items, key=lambda x: x["path"])}


# ---------------- WebSocket 实时推送 API ----------------


