from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from database import get_db

from services.llm_gateway import call_text_model, call_vision_model
from services.llm_resilience import breaker_snapshots
from services.llm_usage_service import (
    aggregate_usage,
    llm_governance_config,
    recent_calls,
)
from services.model_registry import serialize_config, activate_config, get_active_config



from database import ModelConfig, User
from schemas import ModelConfigCreate, ModelConfigUpdate

from services.auth_service import get_current_user, get_tenant_id, require_role
from services.common_utils import IMAGE_EXTENSIONS, read_validated_upload
from services.upload_archive_service import resolve_upload_path, save_upload

router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_role("admin"))], tags=["系统设置"])

@router.get("/api/settings/model-providers")
def model_provider_templates():
    return [
        {
            "provider": "zhipu",
            "name": "智谱清言",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "text_models": ["glm-4-flash", "glm-4-plus", "glm-4-air"],
            "vision_models": ["glm-4v-flash", "glm-4.1v-thinking-flash"],
            "supports_text": True,
            "supports_vision": True,
        },
        {
            "provider": "dashscope",
            "name": "阿里云百炼 / 通义千问",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "text_models": ["qwen-plus", "qwen-turbo", "qwen-max"],
            "vision_models": ["qwen-vl-plus", "qwen-vl-max"],
            "supports_text": True,
            "supports_vision": True,
        },
        {
            "provider": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "text_models": ["deepseek-chat", "deepseek-reasoner"],
            "vision_models": [],
            "supports_text": True,
            "supports_vision": False,
        },
        {
            "provider": "openai",
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "text_models": ["gpt-4o-mini", "gpt-4o"],
            "vision_models": ["gpt-4o-mini", "gpt-4o"],
            "supports_text": True,
            "supports_vision": True,
        },
        {
            "provider": "moonshot",
            "name": "Moonshot Kimi",
            "base_url": "https://api.moonshot.cn/v1",
            "text_models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
            "vision_models": [],
            "supports_text": True,
            "supports_vision": False,
        },
        {
            "provider": "openrouter",
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "text_models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "google/gemini-flash-1.5"],
            "vision_models": ["openai/gpt-4o-mini", "google/gemini-flash-1.5"],
            "supports_text": True,
            "supports_vision": True,
        },
        {
            "provider": "custom",
            "name": "自定义 OpenAI 兼容接口",
            "base_url": "",
            "text_models": [],
            "vision_models": [],
            "supports_text": True,
            "supports_vision": True,
        },
    ]


@router.get("/api/settings/model-configs")
def list_model_configs(db: Session = Depends(get_db)):
    rows = db.query(ModelConfig).order_by(ModelConfig.id.desc()).all()
    return [serialize_config(r) for r in rows]


@router.post("/api/settings/model-configs")
def create_model_config(payload: ModelConfigCreate, db: Session = Depends(get_db)):
    c = ModelConfig(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return serialize_config(c)


@router.get("/api/settings/model-configs/{config_id}")
def get_model_config(config_id: int, db: Session = Depends(get_db)):
    c = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not c:
        return JSONResponse(status_code=404, content={"message": "配置不存在"})
    return serialize_config(c, include_key=True)


@router.put("/api/settings/model-configs/{config_id}")
def update_model_config(config_id: int, payload: ModelConfigUpdate, db: Session = Depends(get_db)):
    c = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not c:
        return JSONResponse(status_code=404, content={"message": "配置不存在"})

    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(c, key, value)
    c.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(c)
    return serialize_config(c)


@router.delete("/api/settings/model-configs/{config_id}")
def delete_model_config(config_id: int, db: Session = Depends(get_db)):
    c = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not c:
        return JSONResponse(status_code=404, content={"message": "配置不存在"})
    db.delete(c)
    db.commit()
    return {"message": "deleted"}


@router.post("/api/settings/model-configs/{config_id}/activate")
def activate_model_config(config_id: int, mode: str = Form("text"), db: Session = Depends(get_db)):
    try:
        c = activate_config(db, config_id, mode)
        return {"message": "activated", "config": serialize_config(c)}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"message": str(e)})


@router.get("/api/settings/active-models")
def active_models(db: Session = Depends(get_db)):
    text = get_active_config(db, "text")
    vision = get_active_config(db, "vision")
    return {
        "text": serialize_config(text) if text else None,
        "vision": serialize_config(vision) if vision else None,
    }


@router.post("/api/settings/model-test")
async def test_model(
    config_id: Optional[int] = Form(None),
    mode: str = Form("text"),
    prompt: str = Form("请用一句话说明你是否可以正常工作。"),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first() if config_id else get_active_config(db, mode)

    if not config:
        return JSONResponse(status_code=400, content={"ok": False, "message": "未找到可测试的模型配置"})

    if mode == "vision":
        if not file:
            return JSONResponse(status_code=400, content={"ok": False, "message": "视觉测试需要上传图片"})
        content, ext = await read_validated_upload(file, IMAGE_EXTENSIONS, label="模型测试图片")
        record = save_upload(
            db,
            tenant_id=None,
            category="model_test",
            content=content,
            ext=ext,
            media_type=file.content_type or "image/jpeg",
            original_name=file.filename or "",
        )
        path = resolve_upload_path(record)
        if not path:
            return JSONResponse(status_code=500, content={"ok": False, "message": "测试图片落盘失败"})
        result = await call_vision_model(config, str(path), prompt, purpose="model_test")
    else:
        result = await call_text_model(config, prompt, purpose="model_test")

    return {
        "config": serialize_config(config),
        "test_mode": mode,
        "result": result,
    }


@router.get("/api/settings/llm-usage")
def llm_usage(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """大模型调用量与成本统计（按当前租户聚合）。"""
    return aggregate_usage(db, get_tenant_id(current_user), days=max(1, min(days, 365)))


@router.get("/api/settings/llm-calls")
def llm_recent_calls(
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """最近的大模型调用明细，便于排查失败与超额。"""
    return {"items": recent_calls(db, get_tenant_id(current_user), limit=limit, status=status)}


@router.get("/api/settings/llm-governance")
def llm_governance():
    """当前生效的超时/重试/熔断参数与熔断器状态。"""
    return {
        "config": llm_governance_config(),
        "breakers": breaker_snapshots(),
    }


# ---------------- V7 Enhanced APIs ----------------


