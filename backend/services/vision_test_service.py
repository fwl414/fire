import base64
import os
from typing import Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import UploadFile


load_dotenv()


def get_vision_config_status() -> Dict[str, Any]:
    api_key = os.getenv("VISION_API_KEY", "")
    return {
        "vision_enabled": os.getenv("VISION_ENABLED", "false"),
        "has_api_key": bool(api_key),
        "api_key_preview": f"{api_key[:6]}***{api_key[-4:]}" if len(api_key) > 10 else "",
        "base_url": os.getenv("VISION_BASE_URL", ""),
        "model": os.getenv("VISION_MODEL", ""),
    }


async def test_vision_api(file: UploadFile) -> Dict[str, Any]:
    vision_enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    api_key = os.getenv("VISION_API_KEY", "")
    base_url = os.getenv("VISION_BASE_URL", "").rstrip("/")
    model = os.getenv("VISION_MODEL", "")

    if not vision_enabled:
        return {
            "ok": False,
            "message": "VISION_ENABLED 未开启，请在 .env 中设置 VISION_ENABLED=true",
        }

    if not api_key:
        return {
            "ok": False,
            "message": "VISION_API_KEY 未配置",
        }

    if not base_url:
        return {
            "ok": False,
            "message": "VISION_BASE_URL 未配置",
        }

    if not model:
        return {
            "ok": False,
            "message": "VISION_MODEL 未配置",
        }

    image_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:{content_type};base64,{image_base64}"

    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "你是一个智慧消防隐患识别助手。"
                            "请分析这张图片中是否存在消防安全隐患，"
                            "例如消防通道堵塞、灭火器遮挡、电线杂乱、插座过载、"
                            "可燃物堆积、烟雾、明火等。"
                            "请用中文回答，并列出隐患、风险等级和整改建议。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        },
                    },
                ],
            }
        ],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        print(f"[VISION_TEST] 正在调用视觉模型: {model}")
        print(f"[VISION_TEST] 请求地址: {url}")

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)

        print(f"[VISION_TEST] 状态码: {response.status_code}")

        if response.status_code != 200:
            return {
                "ok": False,
                "status_code": response.status_code,
                "message": "视觉模型接口调用失败",
                "response_text": response.text,
            }

        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        return {
            "ok": True,
            "used_vision_api": True,
            "model": model,
            "message": "视觉模型 API 调用成功",
            "result": content,
            "raw_response": data,
        }

    except Exception as e:
        return {
            "ok": False,
            "message": "视觉模型 API 调用异常",
            "error": str(e),
        }
