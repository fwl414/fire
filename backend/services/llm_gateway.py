from __future__ import annotations

import base64
import json
import re
import time
from typing import Optional, Dict, Any, List

import httpx

from database import ModelConfig
from services import llm_pricing
from services.llm_resilience import (
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SECONDS,
    LLM_VISION_TIMEOUT_SECONDS,
    RETRYABLE_STATUS,
    RetryableHttpError,
    get_breaker,
    with_retry,
)
from services.llm_usage_service import record_call


def _chat_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _provider_key(config: ModelConfig) -> str:
    return f"{config.provider or 'custom'}:{(config.base_url or '').rstrip('/')}"


def _retryable(exc: Exception) -> bool:
    return isinstance(exc, (RetryableHttpError, httpx.TimeoutException, httpx.TransportError))


async def _invoke_chat(
    config: ModelConfig,
    *,
    payload: Dict[str, Any],
    timeout: float,
    model: str,
    purpose: str,
    kind: str,
) -> Dict[str, Any]:
    """统一的 Chat Completions 调用：熔断 + 重试 + 异常兜底 + 用量与成本落库。

    任何异常都不再向上抛出（此前超时会导致接口 500），而是返回结构化的失败结果，
    由业务层按既有逻辑降级。
    """
    breaker = get_breaker(_provider_key(config))
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    if not breaker.allow():
        record_call(
            provider=config.provider, model=model, purpose=purpose,
            status="circuit_open", error="供应商已被熔断",
        )
        return {
            "ok": False,
            "circuit_open": True,
            "message": f"模型供应商 {config.provider} 连续失败已熔断，请稍后重试或切换模型",
        }

    attempts = {"count": 0}
    started = time.perf_counter()

    async def _attempt() -> httpx.Response:
        attempts["count"] += 1
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_chat_url(config.base_url), json=payload, headers=headers)
        if resp.status_code in RETRYABLE_STATUS:
            raise RetryableHttpError(resp.status_code, resp.text)
        return resp

    try:
        resp = await with_retry(_attempt, retryable=_retryable)
    except RetryableHttpError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        breaker.record_failure()
        record_call(
            provider=config.provider, model=model, purpose=purpose, status="failed",
            latency_ms=latency, attempts=attempts["count"], http_status=exc.status_code,
            error=f"HTTP {exc.status_code}: {exc.body[:200]}",
        )
        return {
            "ok": False,
            "status_code": exc.status_code,
            "message": f"{kind}模型调用失败（已重试 {attempts['count']} 次）",
            "response_text": exc.body,
        }
    except Exception as exc:  # noqa: BLE001 - 超时/网络异常统一兜底，避免接口 500
        latency = int((time.perf_counter() - started) * 1000)
        breaker.record_failure()
        error = f"{type(exc).__name__}: {exc}"
        record_call(
            provider=config.provider, model=model, purpose=purpose, status="failed",
            latency_ms=latency, attempts=attempts["count"], error=error,
        )
        return {
            "ok": False,
            "message": f"{kind}模型调用异常（已重试 {attempts['count']} 次）",
            "error": error,
        }

    latency = int((time.perf_counter() - started) * 1000)
    if resp.status_code != 200:
        breaker.record_failure()
        record_call(
            provider=config.provider, model=model, purpose=purpose, status="failed",
            latency_ms=latency, attempts=attempts["count"], http_status=resp.status_code,
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
        return {
            "ok": False,
            "status_code": resp.status_code,
            "message": f"{kind}模型调用失败",
            "response_text": resp.text,
        }

    try:
        data = resp.json()
    except ValueError as exc:
        breaker.record_failure()
        record_call(
            provider=config.provider, model=model, purpose=purpose, status="failed",
            latency_ms=latency, attempts=attempts["count"], http_status=resp.status_code,
            error=f"响应解析失败: {exc}",
        )
        return {"ok": False, "status_code": resp.status_code, "message": f"{kind}模型响应解析失败"}

    breaker.record_success()
    usage = llm_pricing.extract_usage(data)
    record_call(
        provider=config.provider, model=model, purpose=purpose, status="success",
        prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"], latency_ms=latency,
        attempts=attempts["count"], http_status=200,
    )

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {
        "ok": True,
        "provider": config.provider,
        "model": model,
        "content": content,
        "usage": usage,
        "latency_ms": latency,
        "raw_response": data,
    }


async def call_text_model(
    config: ModelConfig,
    prompt: str,
    system: str = "",
    purpose: str = "text",
) -> Dict[str, Any]:
    if not config or not config.api_key:
        return {"ok": False, "message": "未配置可用文本模型 API Key"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": config.text_model,
        "messages": messages,
        "temperature": 0.2,
    }

    return await _invoke_chat(
        config,
        payload=payload,
        timeout=LLM_TIMEOUT_SECONDS,
        model=config.text_model,
        purpose=purpose,
        kind="文本",
    )


async def call_vision_model(
    config: ModelConfig,
    image_path: str,
    prompt: str,
    purpose: str = "vision",
) -> Dict[str, Any]:
    if not config or not config.api_key:
        return {"ok": False, "message": "未配置可用视觉模型 API Key"}

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except OSError as exc:
        return {"ok": False, "message": f"读取图片失败：{exc}"}

    suffix = image_path.lower().split(".")[-1]
    mime = "image/png" if suffix == "png" else "image/jpeg"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:{mime};base64,{image_base64}"

    payload = {
        "model": config.vision_model,
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

    return await _invoke_chat(
        config,
        payload=payload,
        timeout=LLM_VISION_TIMEOUT_SECONDS,
        model=config.vision_model,
        purpose=purpose,
        kind="视觉",
    )


def extract_hazards_from_text(content: str) -> List[str]:
    hazards = [
        "明火", "烟雾", "电动车违规充电", "消防通道堵塞", "消防设施被遮挡",
        "灭火器缺失", "灭火器被遮挡", "插座过载", "可燃物堆积",
        "配电箱周围堆物", "电线杂乱"
    ]
    found = []
    for h in hazards:
        if h in (content or ""):
            found.append(h)

    # 兼容模型使用近义表达
    synonym_map = {
        "消防通道堵塞": ["通道被占用", "疏散通道被占用", "通道堆放杂物"],
        "可燃物堆积": ["纸箱堆放", "杂物堆积", "易燃物堆放"],
        "电线杂乱": ["线路凌乱", "线缆凌乱", "乱拉电线"],
        "插座过载": ["插排串联", "超负荷用电"],
        "灭火器被遮挡": ["灭火器遮挡"],
    }
    for hazard, words in synonym_map.items():
        if hazard not in found and any(w in (content or "") for w in words):
            found.append(hazard)

    return found


def safe_json(content: str) -> Dict[str, Any]:
    if not content:
        return {}
    try:
        return json.loads(content)
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", content)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}
