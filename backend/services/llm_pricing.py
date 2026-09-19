"""大模型调用计价

用于把 token 用量折算为成本。默认表为**示例单价**（USD / 1K tokens），
实际采购价格请通过环境变量 `LLM_PRICING_JSON` 覆盖：

    LLM_PRICING_JSON={"gpt-4o-mini": {"input": 0.00015, "output": 0.0006}}

未配置单价的模型不会被估算成本（返回 None），统计接口会单独给出未计价调用数，
避免用臆测的数字冒充成本。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

# 示例单价（USD / 1K tokens）：仅用于让成本统计可用，请按实际合同调整
DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "glm-4-flash": {"input": 0.0, "output": 0.0},
    "glm-4-plus": {"input": 0.0007, "output": 0.0007},
    "qwen-plus": {"input": 0.0004, "output": 0.0012},
    "qwen-vl-plus": {"input": 0.0012, "output": 0.0036},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "moonshot-v1-8k": {"input": 0.0017, "output": 0.0017},
}

CURRENCY = "USD"


def _load_override() -> Dict[str, Dict[str, float]]:
    raw = os.environ.get("LLM_PRICING_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    cleaned: Dict[str, Dict[str, float]] = {}
    for model, price in parsed.items():
        if not isinstance(price, dict):
            continue
        try:
            cleaned[str(model)] = {
                "input": float(price.get("input", 0) or 0),
                "output": float(price.get("output", 0) or 0),
            }
        except (TypeError, ValueError):
            continue
    return cleaned


def pricing_table() -> Dict[str, Dict[str, float]]:
    """当前生效的计价表（默认表 + 环境变量覆盖）。"""
    table = dict(DEFAULT_PRICING)
    table.update(_load_override())
    return table


def lookup_price(model: Optional[str]) -> Optional[Dict[str, float]]:
    if not model:
        return None
    table = pricing_table()
    if model in table:
        return table[model]
    # 兼容带版本前缀的模型名（如 "openai/gpt-4o-mini"）
    short = str(model).split("/")[-1]
    return table.get(short)


def estimate_cost(
    model: Optional[str],
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> Tuple[Optional[float], bool]:
    """返回 (成本, 是否已计价)。未配置单价时成本为 None。"""
    price = lookup_price(model)
    if not price:
        return None, False
    cost = (prompt_tokens or 0) / 1000 * price["input"] + (completion_tokens or 0) / 1000 * price["output"]
    return round(cost, 6), True


def extract_usage(data: Dict[str, Any]) -> Dict[str, int]:
    """从供应商响应中解析 token 用量，缺失字段记为 0。"""
    usage = (data or {}).get("usage") or {}
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    total = usage.get("total_tokens") or (prompt + completion)
    try:
        return {"prompt_tokens": int(prompt), "completion_tokens": int(completion), "total_tokens": int(total)}
    except (TypeError, ValueError):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
