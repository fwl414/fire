"""大模型调用用量与成本统计

- 每次调用（成功/失败/被熔断）都落一条 llm_call_logs 记录
- 通过 contextvar 传递租户与用户，避免改动所有调用方的函数签名
- 记录失败绝不影响主调用链路（内部捕获并降级为告警日志）
"""
from __future__ import annotations

import contextvars
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import LlmCallLog, SessionLocal
from services.llm_pricing import CURRENCY, estimate_cost

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 500

# 调用上下文：由认证依赖写入，供网关读取
_call_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("llm_call_context", default={})


def set_call_context(tenant_id: Optional[int], user_id: Optional[int]):
    return _call_context.set({"tenant_id": tenant_id, "user_id": user_id})


def reset_call_context(token) -> None:
    try:
        _call_context.reset(token)
    except (ValueError, LookupError):
        pass


def current_context() -> Dict[str, Any]:
    return dict(_call_context.get() or {})


def record_call(
    *,
    provider: str = "",
    model: str = "",
    purpose: str = "",
    status: str = "success",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    attempts: int = 1,
    http_status: Optional[int] = None,
    error: str = "",
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> Optional[LlmCallLog]:
    """落库一次调用记录；任何异常都被吞掉，不阻断业务。"""
    try:
        context = current_context()
        cost, priced = estimate_cost(model, prompt_tokens, completion_tokens)
        record = LlmCallLog(
            tenant_id=tenant_id if tenant_id is not None else context.get("tenant_id"),
            user_id=user_id if user_id is not None else context.get("user_id"),
            provider=provider or "",
            model=model or "",
            purpose=purpose or "",
            status=status,
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            total_tokens=total_tokens or (prompt_tokens or 0) + (completion_tokens or 0),
            cost=cost,
            currency=CURRENCY,
            priced=priced,
            latency_ms=latency_ms or 0,
            attempts=attempts or 1,
            http_status=http_status,
            error=(error or "")[:MAX_ERROR_LENGTH],
        )
        owns_session = db is None
        session = db or SessionLocal()
        try:
            session.add(record)
            session.commit()
            session.refresh(record)
        finally:
            if owns_session:
                session.close()
        return record
    except Exception as exc:  # noqa: BLE001 - 统计失败不应影响模型调用
        logger.warning("记录大模型调用日志失败: %s", exc)
        return None


def _range_start(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=max(1, days))


def aggregate_usage(
    db: Session,
    tenant_id: Optional[int],
    days: int = 30,
) -> Dict[str, Any]:
    """按模型/日期/用途聚合调用量、token 与成本。"""
    since = _range_start(days)
    base = db.query(LlmCallLog).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.created_at >= since,
    )

    total_calls = base.count()
    success_calls = base.filter(LlmCallLog.status == "success").count()
    failed_calls = base.filter(LlmCallLog.status != "success").count()

    totals = db.query(
        func.coalesce(func.sum(LlmCallLog.prompt_tokens), 0),
        func.coalesce(func.sum(LlmCallLog.completion_tokens), 0),
        func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
        func.coalesce(func.sum(LlmCallLog.cost), 0.0),
    ).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.created_at >= since,
    ).one()

    unpriced_calls = base.filter(LlmCallLog.priced == False).count()  # noqa: E712 - SQLAlchemy 需要显式比较

    by_model_rows = db.query(
        LlmCallLog.model,
        LlmCallLog.provider,
        func.count(LlmCallLog.id),
        func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
        func.coalesce(func.sum(LlmCallLog.cost), 0.0),
    ).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.created_at >= since,
    ).group_by(LlmCallLog.model, LlmCallLog.provider).all()

    by_day_rows = db.query(
        func.date(LlmCallLog.created_at),
        func.count(LlmCallLog.id),
        func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
        func.coalesce(func.sum(LlmCallLog.cost), 0.0),
    ).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.created_at >= since,
    ).group_by(func.date(LlmCallLog.created_at)).all()

    by_purpose_rows = db.query(
        LlmCallLog.purpose,
        func.count(LlmCallLog.id),
        func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
        func.coalesce(func.sum(LlmCallLog.cost), 0.0),
    ).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.created_at >= since,
    ).group_by(LlmCallLog.purpose).all()

    return {
        "days": days,
        "since": since.isoformat(),
        "currency": CURRENCY,
        "summary": {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "success_rate": round(success_calls / total_calls * 100, 1) if total_calls else 0.0,
            "prompt_tokens": int(totals[0] or 0),
            "completion_tokens": int(totals[1] or 0),
            "total_tokens": int(totals[2] or 0),
            "cost": round(float(totals[3] or 0.0), 6),
            "unpriced_calls": unpriced_calls,
        },
        "by_model": [
            {
                "model": row[0] or "unknown",
                "provider": row[1] or "",
                "calls": row[2],
                "tokens": int(row[3] or 0),
                "cost": round(float(row[4] or 0.0), 6),
            }
            for row in by_model_rows
        ],
        "by_day": [
            {
                "date": str(row[0]),
                "calls": row[1],
                "tokens": int(row[2] or 0),
                "cost": round(float(row[3] or 0.0), 6),
            }
            for row in by_day_rows
        ],
        "by_purpose": [
            {
                "purpose": row[0] or "unspecified",
                "calls": row[1],
                "tokens": int(row[2] or 0),
                "cost": round(float(row[3] or 0.0), 6),
            }
            for row in by_purpose_rows
        ],
    }


def recent_calls(
    db: Session,
    tenant_id: Optional[int],
    limit: int = 50,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = db.query(LlmCallLog).filter(LlmCallLog.tenant_id == tenant_id)
    if status:
        query = query.filter(LlmCallLog.status == status)
    rows = query.order_by(LlmCallLog.created_at.desc()).limit(max(1, min(limit, 200))).all()
    return [
        {
            "id": r.id,
            "provider": r.provider,
            "model": r.model,
            "purpose": r.purpose,
            "status": r.status,
            "total_tokens": r.total_tokens or 0,
            "cost": r.cost,
            "priced": bool(r.priced),
            "latency_ms": r.latency_ms or 0,
            "attempts": r.attempts or 1,
            "http_status": r.http_status,
            "error": r.error or "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def usage_totals_for_metrics(tenant_id: Optional[int] = None) -> Dict[str, float]:
    """供 /metrics 使用的总量（默认近 24 小时）。"""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=24)
        base = db.query(LlmCallLog).filter(LlmCallLog.created_at >= since)
        if tenant_id is not None:
            base = base.filter(LlmCallLog.tenant_id == tenant_id)
        calls = base.count()
        failed = base.filter(LlmCallLog.status != "success").count()
        totals = db.query(
            func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
            func.coalesce(func.sum(LlmCallLog.cost), 0.0),
        ).filter(LlmCallLog.created_at >= since).one()
        circuit_open = base.filter(LlmCallLog.status == "circuit_open").count()
        return {
            "calls": float(calls),
            "failed": float(failed),
            "tokens": float(totals[0] or 0),
            "cost": float(totals[1] or 0.0),
            "circuit_open": float(circuit_open),
        }
    except Exception:
        return {"calls": 0.0, "failed": 0.0, "tokens": 0.0, "cost": 0.0, "circuit_open": 0.0}
    finally:
        db.close()


def _context_from_scope(scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """仅从令牌载荷中提取归因信息，不做鉴权（鉴权仍由认证依赖负责）。"""
    raw = dict(scope.get("headers") or []).get(b"authorization", b"")
    if not raw:
        return None
    value = raw.decode("latin-1")
    if not value.lower().startswith("bearer "):
        return None
    try:
        from services.auth_service import decode_token

        payload = decode_token(value[7:].strip())
    except Exception:  # noqa: BLE001 - 归因失败不影响请求
        return None
    if not payload:
        return None
    try:
        user_id = int(payload.get("sub") or 0) or None
        tenant_id = int(payload.get("tenant_id") or 0) or None
    except (TypeError, ValueError):
        return None
    return {"user_id": user_id, "tenant_id": tenant_id}


class LlmCallContextMiddleware:
    """把当前请求的租户/用户写入大模型调用上下文，使用量与成本可归因。

    必须在最外层注册：内层的同步路由会被派发到线程池，只有在此之前写入的上下文
    才会随 contextvars 一起复制进线程。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        context = _context_from_scope(scope)
        if not context:
            await self.app(scope, receive, send)
            return

        token = _call_context.set(context)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_call_context(token)


def llm_governance_config() -> Dict[str, Any]:
    """当前生效的调用治理参数（供运维查看）。"""
    from services import llm_resilience as res

    return {
        "timeout_seconds": res.LLM_TIMEOUT_SECONDS,
        "vision_timeout_seconds": res.LLM_VISION_TIMEOUT_SECONDS,
        "max_retries": res.LLM_MAX_RETRIES,
        "retry_base_delay_seconds": res.LLM_RETRY_BASE_DELAY,
        "breaker_failure_threshold": res.LLM_BREAKER_FAILURE_THRESHOLD,
        "breaker_reset_seconds": res.LLM_BREAKER_RESET_SECONDS,
        "retryable_status": sorted(res.RETRYABLE_STATUS),
        "pricing_override_configured": bool(os.environ.get("LLM_PRICING_JSON", "").strip()),
    }
