from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from services.llm_gateway import call_vision_model, extract_hazards_from_text, safe_json
from services.model_registry import get_active_config
from services.text_analyzer import merge_hazards


VISION_PROMPT = """
你是智慧消防隐患识别助手。请识别图片中的消防安全隐患。
重点判断以下 8 类展示型隐患：
1. 消防通道堵塞；2. 灭火器遮挡；3. 消防栓遮挡；4. 电动车违规停放；
5. 可燃物堆积；6. 应急出口锁闭；7. 安全标识缺失；8. 电气线路杂乱。
同时关注：明火、烟雾、灭火器缺失、配电箱周围堆物。
请按 JSON 输出：
{
  "hazards": ["消防通道堵塞", "可燃物堆积"],
  "description": "现场情况描述",
  "risk_reasons": ["判断理由1"],
  "visual_evidence": ["图片证据1"]
}
如果无法确定，请说明不确定原因。不要输出与消防安全无关的内容。
"""


def _local_image_fallback(image_path: str):
    """视觉模型不可用时的演示兜底。

    优先尝试使用本地OpenCV进行轻量级图像分析，
    如果OpenCV不可用，则使用演示数据兜底。
    """
    try:
        from services.local_image_analyzer import analyze_image_local, check_opencv_available
        
        if check_opencv_available():
            local_result = analyze_image_local(image_path)
            if local_result.get("success"):
                return {
                    "hazards": local_result.get("hazards", []),
                    "hazard_details": local_result.get("hazard_details", []),
                    "description": local_result.get("description", ""),
                    "risk_reasons": local_result.get("risk_reasons", []),
                    "visual_evidence": local_result.get("visual_evidence", []),
                    "used_vision_api": False,
                    "used_local_vision": True,
                    "local_image_fallback": True,
                    "local_opencv_enabled": True,
                    "vision_error": "未启用云端视觉模型，已使用本地OpenCV进行轻量级图像分析。",
                    "provider": "local_opencv",
                    "model": "fire-inspection-local-v1",
                    "feature_analysis": local_result.get("feature_analysis", {}),
                    "image_info": local_result.get("image_info", {}),
                    "risk_level": local_result.get("risk_level", "低风险"),
                    "risk_score": local_result.get("risk_score", 25),
                }
    except Exception:
        pass
    
    return {
        "hazards": ["消防通道堵塞", "可燃物堆积"],
        "description": "已检测到现场图片输入。当前未启用视觉模型，系统使用智慧消防演示兜底场景进行风险链路展示。建议启用智谱/通义等视觉模型后进行真实图片识别。",
        "risk_reasons": [
            "图片已作为巡检证据上传，但后端未检测到可用视觉模型配置。",
            "演示兜底按常见消防巡检图片场景生成：通道区域堆放杂物、可燃物占用空间。",
        ],
        "visual_evidence": ["图片文件已接收", "本地兜底未读取图像语义，仅用于展示完整 Agent 闭环"],
        "used_vision_api": False,
        "used_local_vision": False,
        "local_image_fallback": True,
        "local_opencv_enabled": False,
        "vision_error": "未启用视觉模型配置，已使用本地演示兜底。",
        "provider": "local_fallback",
        "model": "fire-inspection-demo-fallback",
    }


async def analyze_image(db: Session, image_path: Optional[str]):
    if not image_path:
        return {
            "hazards": [],
            "description": "未上传图片，跳过视觉识别。",
            "risk_reasons": [],
            "visual_evidence": [],
            "used_vision_api": False,
            "used_local_vision": False,
            "local_image_fallback": False,
            "local_opencv_enabled": False,
            "vision_error": "",
            "provider": "",
            "model": "",
        }

    config = get_active_config(db, "vision")
    if not config:
        return _local_image_fallback(image_path)

    result = await call_vision_model(config, image_path, VISION_PROMPT, purpose="image_analysis")
    if not result.get("ok"):
        fallback = _local_image_fallback(image_path)
        fallback["vision_error"] = result.get("response_text") or result.get("message") or "视觉模型调用失败，已使用本地演示兜底。"
        fallback["provider"] = config.provider
        fallback["model"] = config.vision_model
        return fallback

    content = result.get("content", "")
    parsed = safe_json(content)
    hazards = parsed.get("hazards") if isinstance(parsed, dict) else []
    if not hazards:
        hazards = extract_hazards_from_text(content)

    hazards = merge_hazards(hazards)
    return {
        "hazards": hazards or [],
        "description": parsed.get("description") if isinstance(parsed, dict) and parsed.get("description") else content,
        "risk_reasons": parsed.get("risk_reasons") if isinstance(parsed, dict) and parsed.get("risk_reasons") else [],
        "visual_evidence": parsed.get("visual_evidence") if isinstance(parsed, dict) and parsed.get("visual_evidence") else [],
        "used_vision_api": True,
        "used_local_vision": False,
        "local_image_fallback": False,
        "local_opencv_enabled": False,
        "vision_error": "",
        "provider": config.provider,
        "model": config.vision_model,
        "raw_content": content,
    }
