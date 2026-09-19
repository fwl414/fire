"""可选的智能模型客户端。

第一版默认不启用，避免用户没有 API Key 时无法运行。
如需接入 OpenAI 兼容接口，在 .env 中设置 ENABLE_LLM=true。
"""
import base64
import json
import os
import urllib.request
from pathlib import Path
from typing import Any


def enabled() -> bool:
    return os.getenv("ENABLE_LLM", "false").lower() == "true" and bool(os.getenv("LLM_API_KEY"))


def chat(messages: list[dict[str, Any]], model_env: str = "LLM_MODEL") -> str:
    if not enabled():
        return ""
    url = os.getenv("LLM_BASE_URL", "")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv(model_env, os.getenv("LLM_MODEL", ""))
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0.2}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def image_to_base64(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{mime};base64,{b64}"
