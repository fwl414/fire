from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database import ModelConfig


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 12:
        return api_key[:3] + "***"
    return f"{api_key[:6]}***{api_key[-4:]}"


def serialize_config(c: ModelConfig, include_key: bool = False):
    return {
        "id": c.id,
        "name": c.name,
        "provider": c.provider,
        "base_url": c.base_url,
        "api_key": c.api_key if include_key else "",
        "api_key_preview": mask_key(c.api_key or ""),
        "text_model": c.text_model,
        "vision_model": c.vision_model,
        "supports_text": c.supports_text,
        "supports_vision": c.supports_vision,
        "is_active_text": c.is_active_text,
        "is_active_vision": c.is_active_vision,
        "enabled": c.enabled,
        "ready_text": bool(c.enabled and c.api_key and c.base_url and c.text_model and c.supports_text),
        "ready_vision": bool(c.enabled and c.api_key and c.base_url and c.vision_model and c.supports_vision),
        "remark": c.remark,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


def get_active_config(db: Session, mode: str) -> Optional[ModelConfig]:
    if mode == "vision":
        return (
            db.query(ModelConfig)
            .filter(ModelConfig.enabled == True, ModelConfig.is_active_vision == True)
            .first()
        )
    return (
        db.query(ModelConfig)
        .filter(ModelConfig.enabled == True, ModelConfig.is_active_text == True)
        .first()
    )


def activate_config(db: Session, config_id: int, mode: str) -> ModelConfig:
    c = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not c:
        raise ValueError("模型配置不存在")

    if mode == "vision":
        if not c.supports_vision:
            raise ValueError("该配置不支持视觉模型")
        db.query(ModelConfig).update({ModelConfig.is_active_vision: False})
        c.is_active_vision = True
    else:
        if not c.supports_text:
            raise ValueError("该配置不支持文本模型")
        db.query(ModelConfig).update({ModelConfig.is_active_text: False})
        c.is_active_text = True

    c.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(c)
    return c
