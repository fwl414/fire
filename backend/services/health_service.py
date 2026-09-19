from __future__ import annotations

import os
from typing import Any, Dict, List

from services.record_persistence_service import list_inspection_records, list_workorders
from services.runtime_db import connect_runtime_db, runtime_db_path
from services.rag_admin_service import get_rag_stats
from services.learning_service import get_quiz


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _env_keys() -> Dict[str, str]:
    names = [
        "ZHIPUAI_API_KEY",
        "ZHIPU_API_KEY",
        "BIGMODEL_API_KEY",
        "GLM_API_KEY",
        "OPENAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENROUTER_API_KEY",
        "LLM_API_KEY",
    ]
    return {name: os.getenv(name, "") for name in names if os.getenv(name)}


def _detect_model_config() -> Dict[str, Any]:
    """Detect model configs saved in Settings plus environment keys.

    V1.0.0 uses the database config first because the user normally enters the
    Zhipu/OpenAI compatible key in the Settings page instead of .env.
    """
    data: Dict[str, Any] = {
        "saved_configs": 0,
        "saved_key_configs": 0,
        "active_text": None,
        "active_vision": None,
        "env_keys": _env_keys(),
        "error": "",
    }
    try:
        from database import SessionLocal, ModelConfig
        from services.model_registry import serialize_config

        db = SessionLocal()
        try:
            configs = db.query(ModelConfig).all()
            data["saved_configs"] = len(configs)
            data["saved_key_configs"] = len([c for c in configs if (c.api_key or "").strip()])
            text = db.query(ModelConfig).filter(
                ModelConfig.enabled == True,
                ModelConfig.is_active_text == True,
                ModelConfig.text_model != "",
            ).first()
            vision = db.query(ModelConfig).filter(
                ModelConfig.enabled == True,
                ModelConfig.is_active_vision == True,
                ModelConfig.vision_model != "",
            ).first()
            # 兼容旧数据：如果没点“启用文本/视觉”，但保存了 Key，也提示为可配置候选。
            if not text:
                text = next((c for c in configs if c.enabled and c.text_model and (c.api_key or "").strip()), None)
            if not vision:
                vision = next((c for c in configs if c.enabled and c.vision_model and (c.api_key or "").strip()), None)
            data["active_text"] = serialize_config(text) if text else None
            data["active_vision"] = serialize_config(vision) if vision else None
        finally:
            db.close()
    except Exception as exc:
        data["error"] = str(exc)
    return data


def get_system_health(tenant_id: int | None = None) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []

    checks.append({
        "name": "后端服务",
        "status": "正常",
        "detail": "FastAPI 服务已启动并可响应接口。",
    })

    try:
        with connect_runtime_db() as conn:
            conn.execute("SELECT 1")
        checks.append({"name": "运行数据库", "status": "正常", "detail": str(runtime_db_path())})
    except Exception as exc:
        checks.append({"name": "运行数据库", "status": "异常", "detail": str(exc)})

    try:
        records = list_inspection_records(500, tenant_id=tenant_id)
        orders = list_workorders("", 500, tenant_id=tenant_id)
        closed = len([o for o in orders if o.get("status") == "已闭环"])
        checks.append({
            "name": "业务闭环数据",
            "status": "正常" if records else "警告",
            "detail": f"巡检记录 {len(records)} 条，整改工单 {len(orders)} 条，已闭环 {closed} 条。",
        })
    except Exception as exc:
        checks.append({"name": "业务闭环数据", "status": "异常", "detail": str(exc)})

    try:
        from database import SessionLocal, Device, DeviceTelemetry, InspectionRecord, FaultTicket
        db = SessionLocal()
        try:
            device_query = db.query(Device)
            telemetry_query = db.query(DeviceTelemetry)
            legacy_record_query = db.query(InspectionRecord)
            ticket_query = db.query(FaultTicket)
            if tenant_id is not None:
                device_query = device_query.filter(Device.tenant_id == tenant_id)
                telemetry_query = telemetry_query.filter(DeviceTelemetry.tenant_id == tenant_id)
                legacy_record_query = legacy_record_query.filter(InspectionRecord.tenant_id == tenant_id)
                ticket_query = ticket_query.filter(FaultTicket.tenant_id == tenant_id)
            device_count = device_query.count()
            telemetry_count = telemetry_query.count()
            legacy_record_count = legacy_record_query.count()
            ticket_count = ticket_query.count()
        finally:
            db.close()
        checks.append({
            "name": "设备与旧表数据",
            "status": "正常" if device_count else "警告",
            "detail": f"设备 {device_count} 个，遥测 {telemetry_count} 条，旧巡检记录 {legacy_record_count} 条，故障工单 {ticket_count} 条。",
        })
    except Exception as exc:
        checks.append({"name": "设备与旧表数据", "status": "异常", "detail": str(exc)})

    try:
        stats = get_rag_stats()
        total = int(stats.get("total", 0) or 0)
        enabled = int(stats.get("enabled", 0) or 0)
        checks.append({
            "name": "RAG知识库",
            "status": "正常" if enabled else "警告",
            "detail": f"知识条目 {total} 条，启用 {enabled} 条。",
        })
    except Exception as exc:
        checks.append({"name": "RAG知识库", "status": "异常", "detail": str(exc)})

    try:
        quiz_count = len(get_quiz(limit=5000))
        checks.append({"name": "消防题库", "status": "正常" if quiz_count else "警告", "detail": f"可加载题目 {quiz_count} 道。"})
    except Exception as exc:
        checks.append({"name": "消防题库", "status": "异常", "detail": str(exc)})

    model = _detect_model_config()
    if model.get("error"):
        checks.append({"name": "智能模型配置", "status": "异常", "detail": model["error"]})
    else:
        env_key_names = list(model.get("env_keys", {}).keys())
        active_text = model.get("active_text")
        active_vision = model.get("active_vision")
        saved_key_configs = model.get("saved_key_configs", 0)
        saved_configs = model.get("saved_configs", 0)

        if active_text or active_vision or saved_key_configs or env_key_names:
            status = "已配置" if (active_text or active_vision) else "部分配置"
            parts = [f"系统设置保存配置 {saved_configs} 个，其中已填写 Key {saved_key_configs} 个"]
            if active_text:
                parts.append(f"文本模型：{active_text.get('name')} / {active_text.get('text_model')}")
            else:
                parts.append("文本模型：未启用或未选择")
            if active_vision:
                parts.append(f"视觉模型：{active_vision.get('name')} / {active_vision.get('vision_model')}")
            else:
                parts.append("视觉模型：未启用或未选择")
            if env_key_names:
                parts.append("环境变量Key：" + "、".join(env_key_names))
            checks.append({"name": "智能模型配置", "status": status, "detail": "；".join(parts)})
        else:
            checks.append({
                "name": "智能模型配置",
                "status": "未配置",
                "detail": "未检测到系统设置页保存的 API Key，也未检测到常见环境变量；系统会使用规则与演示兜底能力。",
            })

    has_error = any(c["status"] == "异常" for c in checks)
    has_warning = any(c["status"] in ["警告", "未配置", "部分配置"] for c in checks)
    overall = "异常" if has_error else "警告" if has_warning else "正常"
    return {
        "overall": overall,
        "checks": checks,
        "suggestion": "V1.0.0 已覆盖页面路由、核心接口、演示数据、配置检测和业务闭环。若业务数据为空，可点击“一键生成演示数据”。",
        "version": "V1.0.0",
    }
