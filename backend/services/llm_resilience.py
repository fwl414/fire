"""大模型调用韧性：熔断器 + 重试退避

目的：
1. 超时/网络异常不再向上抛出导致 500，而是转为结构化失败结果并由业务层兜底
2. 瞬时故障（429/5xx/超时）按指数退避重试
3. 供应商持续不可用时快速失败（熔断），避免请求堆积与成本浪费

所有参数均可通过环境变量调整，便于按环境调优。
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

T = TypeVar("T")

# 可重试的 HTTP 状态码
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
LLM_VISION_TIMEOUT_SECONDS = float(os.environ.get("LLM_VISION_TIMEOUT_SECONDS", "90"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "2"))
LLM_RETRY_BASE_DELAY = float(os.environ.get("LLM_RETRY_BASE_DELAY", "0.5"))
LLM_BREAKER_FAILURE_THRESHOLD = int(os.environ.get("LLM_BREAKER_FAILURE_THRESHOLD", "5"))
LLM_BREAKER_RESET_SECONDS = float(os.environ.get("LLM_BREAKER_RESET_SECONDS", "60"))


class CircuitOpenError(RuntimeError):
    """熔断器打开，直接拒绝本次调用。"""

    def __init__(self, name: str):
        super().__init__(f"模型供应商 {name} 连续失败已被熔断，暂时拒绝调用")
        self.name = name


class RetryableHttpError(RuntimeError):
    """可重试的 HTTP 响应（429/5xx 等），由重试逻辑捕获。"""

    def __init__(self, status_code: int, body: str = ""):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body or ""


class CircuitBreaker:
    """按供应商维度累计连续失败；达到阈值后快速失败，冷却后放行一次试探。"""

    def __init__(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        reset_seconds: Optional[float] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold or LLM_BREAKER_FAILURE_THRESHOLD
        self.reset_seconds = reset_seconds if reset_seconds is not None else LLM_BREAKER_RESET_SECONDS
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            if self._failures < self.failure_threshold:
                return "closed"
            return "half-open" if time.monotonic() - self._opened_at >= self.reset_seconds else "open"

    @property
    def failures(self) -> int:
        with self._lock:
            return self._failures

    def allow(self) -> bool:
        with self._lock:
            if self._failures < self.failure_threshold:
                return True
            return time.monotonic() - self._opened_at >= self.reset_seconds

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": "closed" if self._failures < self.failure_threshold
                else ("half-open" if time.monotonic() - self._opened_at >= self.reset_seconds else "open"),
                "failures": self._failures,
                "failure_threshold": self.failure_threshold,
                "reset_seconds": self.reset_seconds,
            }


_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(name: str) -> CircuitBreaker:
    """按名称取（或创建）熔断器。"""
    key = name or "default"
    with _registry_lock:
        breaker = _breakers.get(key)
        if breaker is None:
            breaker = CircuitBreaker(key)
            _breakers[key] = breaker
        return breaker


def breaker_snapshots() -> Dict[str, Dict[str, Any]]:
    with _registry_lock:
        return {name: breaker.snapshot() for name, breaker in _breakers.items()}


def reset_breakers() -> None:
    """仅用于测试或人工恢复。"""
    with _registry_lock:
        _breakers.clear()


async def with_retry(
    call: Callable[[], Awaitable[T]],
    *,
    retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    retryable: Optional[Callable[[Exception], bool]] = None,
) -> T:
    """指数退避重试。全部失败后抛出最后一次异常。"""
    attempts = LLM_MAX_RETRIES if retries is None else retries
    delay = LLM_RETRY_BASE_DELAY if base_delay is None else base_delay
    last_error: Optional[Exception] = None

    for attempt in range(attempts + 1):
        try:
            return await call()
        except Exception as exc:  # noqa: BLE001 - 需要按类型判断是否重试
            last_error = exc
            if retryable is not None and not retryable(exc):
                raise
            if attempt >= attempts:
                break
            await asyncio.sleep(delay * (2 ** attempt))

    assert last_error is not None
    raise last_error
