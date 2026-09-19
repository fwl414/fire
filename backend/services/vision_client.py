import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from services.text_analyzer import extract_hazards_from_text


def get_vision_config_status() -> Dict[str, Any]:
    load_dotenv(override=True)
    api_key = os.getenv("VISION_API_KEY", "")
    enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    base_url = os.getenv("VISION_BASE_URL", "").rstrip("/")
    model = os.getenv("VISION_MODEL", "")
    ready = enabled and bool(api_key) and bool(base_url) and bool(model)
    return {
        "vision_enabled": str(enabled).lower(),
        "ready": "ready" if ready else "not_ready",
        "has_api_key": bool(api_key),
        "api_key_preview": f"{api_key[:6]}***{api_key[-4:]}" if len(api_key) > 10 else "",
        "base_url": base_url,
        "model": model,
    }


def _guess_mime(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in [".png"]:
        return "image/png"
    if suffix in [".webp"]:
        return "image/webp"
    return "image/jpeg"


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


async def analyze_image_with_vision(image_path: str) -> Dict[str, Any]:
    load_dotenv(override=True)
    enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    api_key = os.getenv("VISION_API_KEY", "")
    base_url = os.getenv("VISION_BASE_URL", "").rstrip("/")
    model = os.getenv("VISION_MODEL", "")

    if not enabled:
        return {"used_vision_api": False, "tried_vision_api": False, "message": "VISION_ENABLED 未开启"}
    if not api_key or not base_url or not model:
        return {"used_vision_api": False, "tried_vision_api": True, "message": "视觉 API 配置不完整"}

    image_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:{_guess_mime(image_path)};base64,{b64}"

    prompt = (
        "你是一个智慧消防隐患识别助手。请分析图片中是否存在消防安全隐患。"
        "只允许从以下标签中选择：明火、烟雾、电动车违规充电、消防通道堵塞、消防设施被遮挡、灭火器缺失、插座过载、可燃物堆积、电线杂乱、配电箱周围堆物。"
        "请严格返回 JSON，不要输出 Markdown。格式："
        "{\"hazards\":[\"隐患标签\"],\"description\":\"现场描述\",\"risk_reasons\":[\"判断理由\"]}"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url}/chat/completions"

    try:
        print(f"[VISION] 正在调用真实视觉模型: {model}")
        print(f"[VISION] 请求地址: {url}")
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, json=payload, headers=headers)
        print(f"[VISION] 状态码: {resp.status_code}")
        if resp.status_code != 200:
            return {
                "used_vision_api": False,
                "tried_vision_api": True,
                "message": "视觉模型接口调用失败",
                "status_code": resp.status_code,
                "response_text": resp.text,
            }
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extract_json(content)
        if not parsed:
            text_result = extract_hazards_from_text(content)
            parsed = {
                "hazards": text_result.get("hazards", []),
                "description": content,
                "risk_reasons": text_result.get("risk_reasons", []),
            }
        parsed["used_vision_api"] = True
        parsed["tried_vision_api"] = True
        parsed["raw_content"] = content
        return parsed
    except Exception as exc:
        return {"used_vision_api": False, "tried_vision_api": True, "message": "视觉模型调用异常", "error": str(exc)}


async def test_vision_api_with_upload(file) -> Dict[str, Any]:
    from tempfile import NamedTemporaryFile
    suffix = Path(file.filename or "test.jpg").suffix or ".jpg"
    content = await file.read()
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = await analyze_image_with_vision(tmp_path)
        ok = bool(result.get("used_vision_api"))
        return {
            "ok": ok,
            "used_vision_api": ok,
            "message": "视觉模型 API 调用成功" if ok else result.get("message", "视觉模型未调用成功"),
            "result": result,
        }
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
