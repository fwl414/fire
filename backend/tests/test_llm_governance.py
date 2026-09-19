"""大模型治理测试：超时兜底、重试、熔断、用量与成本统计、指标暴露。"""
import asyncio
import contextlib
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from fastapi.testclient import TestClient

import main
from database import LlmCallLog, ModelConfig, SessionLocal, get_default_tenant_id, init_db
from services import llm_gateway, llm_pricing, llm_resilience, llm_usage_service

PURPOSE_TAG = "llm-gov-test"
PRICED_MODEL = "gpt-4o-mini"
UNPRICED_MODEL = "gov-test-unpriced-model"
AGG_MODEL = "gov-test-billed-model"


def _config(model: str = PRICED_MODEL) -> ModelConfig:
    return ModelConfig(
        provider="openai",
        base_url="https://llm.invalid/v1",
        api_key="test-key",
        text_model=model,
        vision_model=model,
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload if payload is not None else {})

    def json(self):
        if self._payload is None:
            raise ValueError("响应不是合法 JSON")
        return self._payload


def _ok_payload(content: str = "正常", prompt_tokens: int = 100, completion_tokens: int = 50):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@contextlib.contextmanager
def _patched_post(responses):
    """把 httpx.AsyncClient.post 替换为按序返回（或抛出）预设结果的桩。"""
    state = {"calls": 0}

    async def _side_effect(url, **kwargs):
        index = min(state["calls"], len(responses) - 1)
        state["calls"] += 1
        item = responses[index]
        if isinstance(item, Exception):
            raise item
        return item

    with mock.patch.object(
        httpx.AsyncClient, "post", new=mock.AsyncMock(side_effect=_side_effect)
    ):
        yield state


@contextlib.contextmanager
def _fast_retry(retries: int = 2, threshold: int = 2):
    """缩短重试与熔断参数，避免测试等待退避时间。"""
    with mock.patch.object(llm_resilience, "LLM_MAX_RETRIES", retries), \
            mock.patch.object(llm_resilience, "LLM_RETRY_BASE_DELAY", 0.0), \
            mock.patch.object(llm_resilience, "LLM_BREAKER_FAILURE_THRESHOLD", threshold):
        llm_resilience.reset_breakers()
        try:
            yield
        finally:
            llm_resilience.reset_breakers()


class TestLlmPricing(unittest.TestCase):

    def test_priced_model_cost(self):
        cost, priced = llm_pricing.estimate_cost(PRICED_MODEL, 1000, 1000)
        self.assertTrue(priced)
        self.assertAlmostEqual(cost, 0.00015 + 0.0006, places=6)

    def test_versioned_model_name_is_resolved(self):
        cost, priced = llm_pricing.estimate_cost(f"openai/{PRICED_MODEL}", 1000, 0)
        self.assertTrue(priced)
        self.assertAlmostEqual(cost, 0.00015, places=6)

    def test_unknown_model_is_not_estimated(self):
        cost, priced = llm_pricing.estimate_cost(UNPRICED_MODEL, 1000, 1000)
        self.assertIsNone(cost, "未知单价不应臆测成本")
        self.assertFalse(priced)

    def test_usage_extraction_supports_aliases(self):
        self.assertEqual(
            llm_pricing.extract_usage({"usage": {"prompt_tokens": 3, "completion_tokens": 4}})["total_tokens"],
            7,
        )
        self.assertEqual(
            llm_pricing.extract_usage({"usage": {"input_tokens": 5, "output_tokens": 6}})["total_tokens"],
            11,
        )
        self.assertEqual(llm_pricing.extract_usage({})["total_tokens"], 0)


class TestLlmGatewayResilience(unittest.TestCase):

    def _call(self, model: str = PRICED_MODEL):
        return asyncio.run(
            llm_gateway.call_text_model(_config(model), "巡检提示", purpose=PURPOSE_TAG)
        )

    def test_timeout_does_not_raise(self):
        """超时此前会直接抛 500，现在必须降级为失败结果。"""
        with _fast_retry(), _patched_post([httpx.ConnectTimeout("超时")]) as state:
            result = self._call()
        self.assertFalse(result["ok"])
        self.assertIn("异常", result["message"])
        self.assertEqual(state["calls"], 3, "可重试异常应重试到上限（1 次初始 + 2 次重试）")

    def test_transient_error_is_retried_then_succeeds(self):
        responses = [
            _FakeResponse(503, text="busy"),
            _FakeResponse(429, text="rate limited"),
            _FakeResponse(200, _ok_payload()),
        ]
        with _fast_retry(), _patched_post(responses) as state:
            result = self._call()
        self.assertTrue(result["ok"], result)
        self.assertEqual(state["calls"], 3)
        self.assertEqual(result["usage"]["total_tokens"], 150)

    def test_exhausted_retry_returns_structured_failure(self):
        with _fast_retry(), _patched_post([_FakeResponse(500, text="boom")]) as state:
            result = self._call()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 500)
        self.assertEqual(state["calls"], 3)

    def test_non_retryable_error_fails_fast(self):
        with _fast_retry(), _patched_post([_FakeResponse(400, text="bad request")]) as state:
            result = self._call()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(state["calls"], 1, "4xx 属参数问题，不应重试")

    def test_circuit_opens_after_threshold(self):
        with _fast_retry(threshold=2), _patched_post([_FakeResponse(400, text="bad")]) as state:
            first = self._call()
            second = self._call()
            self.assertFalse(first["ok"])
            self.assertFalse(second["ok"])
            self.assertEqual(state["calls"], 2)

            blocked = self._call()
            self.assertFalse(blocked["ok"])
            self.assertTrue(blocked.get("circuit_open"))
            self.assertEqual(state["calls"], 2, "熔断后不应再发起真实调用")

            snapshot = llm_resilience.breaker_snapshots()
            self.assertTrue(any(item["state"] == "open" for item in snapshot.values()))

    def test_success_records_usage_and_cost(self):
        tenant_id = _default_tenant_id()
        token = llm_usage_service.set_call_context(tenant_id, None)
        try:
            with _fast_retry(), _patched_post([_FakeResponse(200, _ok_payload())]):
                result = self._call()
        finally:
            llm_usage_service.reset_call_context(token)

        self.assertTrue(result["ok"])
        db = SessionLocal()
        try:
            row = (
                db.query(LlmCallLog)
                .filter(LlmCallLog.purpose == PURPOSE_TAG, LlmCallLog.status == "success")
                .order_by(LlmCallLog.id.desc())
                .first()
            )
            self.assertIsNotNone(row, "成功调用应落库")
            self.assertEqual(row.tenant_id, tenant_id, "应归因到发起请求的租户")
            self.assertEqual(row.total_tokens, 150)
            self.assertTrue(row.priced)
            self.assertAlmostEqual(row.cost, 0.000045, places=6)
            self.assertEqual(row.attempts, 1)
        finally:
            db.close()

    def test_failure_records_error_without_breaking_request(self):
        with _fast_retry(), _patched_post([_FakeResponse(400, text="invalid api key")]):
            result = self._call()
        self.assertFalse(result["ok"])

        db = SessionLocal()
        try:
            row = (
                db.query(LlmCallLog)
                .filter(LlmCallLog.purpose == PURPOSE_TAG, LlmCallLog.status == "failed")
                .order_by(LlmCallLog.id.desc())
                .first()
            )
            self.assertIsNotNone(row, "失败调用应落库以便排障")
            self.assertEqual(row.http_status, 400)
            self.assertIn("400", row.error)
        finally:
            db.close()

    def test_missing_api_key_is_rejected_before_calling(self):
        config = _config()
        config.api_key = ""
        with _patched_post([_FakeResponse(200, _ok_payload())]) as state:
            result = asyncio.run(llm_gateway.call_text_model(config, "提示", purpose=PURPOSE_TAG))
        self.assertFalse(result["ok"])
        self.assertEqual(state["calls"], 0)


class TestLlmUsageAggregation(unittest.TestCase):

    def test_aggregate_reports_models_and_unpriced_calls(self):
        tenant_id = _default_tenant_id()
        # 使用专属模型名 + 环境变量覆盖单价，避免与其他用例的历史记录相互影响
        pricing = json.dumps({AGG_MODEL: {"input": 0.001, "output": 0.003}})
        with mock.patch.dict(os.environ, {"LLM_PRICING_JSON": pricing}):
            llm_usage_service.record_call(
                provider="openai", model=AGG_MODEL, purpose=PURPOSE_TAG, status="success",
                prompt_tokens=1000, completion_tokens=1000, tenant_id=tenant_id,
            )
            llm_usage_service.record_call(
                provider="openai", model=UNPRICED_MODEL, purpose=PURPOSE_TAG, status="success",
                prompt_tokens=10, completion_tokens=10, tenant_id=tenant_id,
            )

        db = SessionLocal()
        try:
            stats = llm_usage_service.aggregate_usage(db, tenant_id, days=1)
        finally:
            db.close()

        models = {item["model"]: item for item in stats["by_model"]}
        self.assertIn(AGG_MODEL, models)
        self.assertEqual(models[AGG_MODEL]["calls"], 1)
        self.assertEqual(models[AGG_MODEL]["cost"], 0.004, "1000/1000 tokens 按覆盖单价应为 0.004")
        self.assertEqual(models[UNPRICED_MODEL]["cost"], 0.0)
        self.assertGreaterEqual(stats["summary"]["unpriced_calls"], 1)
        self.assertGreaterEqual(stats["summary"]["total_calls"], 2)
        self.assertIn("by_day", stats)
        self.assertTrue(any(item["purpose"] == PURPOSE_TAG for item in stats["by_purpose"]))

    def test_recent_calls_returns_details(self):
        tenant_id = _default_tenant_id()
        llm_usage_service.record_call(
            provider="openai", model=PRICED_MODEL, purpose=PURPOSE_TAG, status="failed",
            error="HTTP 429", http_status=429, tenant_id=tenant_id,
        )
        db = SessionLocal()
        try:
            items = llm_usage_service.recent_calls(db, tenant_id, limit=10, status="failed")
        finally:
            db.close()

        self.assertTrue(items)
        self.assertTrue(all(item["status"] == "failed" for item in items))
        self.assertIn("http_status", items[0])

    def test_governance_config_is_exposed(self):
        config = llm_usage_service.llm_governance_config()
        for key in ("timeout_seconds", "vision_timeout_seconds", "max_retries",
                    "breaker_failure_threshold", "breaker_reset_seconds"):
            self.assertIn(key, config)
        self.assertIn(500, config["retryable_status"])


class TestLlmContextAttribution(unittest.TestCase):

    def test_scope_header_parsed_into_context(self):
        from database import User
        from services.auth_service import create_access_token

        token = create_access_token(User(id=4242, username="gov-probe", tenant_id=7))
        scope = {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
        context = llm_usage_service._context_from_scope(scope)
        self.assertEqual(context, {"user_id": 4242, "tenant_id": 7})

    def test_scope_without_token_yields_nothing(self):
        self.assertIsNone(llm_usage_service._context_from_scope({"type": "http", "headers": []}))
        self.assertIsNone(
            llm_usage_service._context_from_scope(
                {"type": "http", "headers": [(b"authorization", b"Basic abc")]}
            )
        )

    def test_middleware_sets_and_restores_context(self):
        from database import User
        from services.auth_service import create_access_token

        token = create_access_token(User(id=99, username="gov-probe2", tenant_id=3))
        captured = []

        async def _app(scope, receive, send):
            captured.append(llm_usage_service.current_context())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = llm_usage_service.LlmCallContextMiddleware(_app)
        scope = {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }

        async def _receive():
            return {"type": "http.request"}

        async def _send(message):
            return None

        asyncio.run(middleware(scope, _receive, _send))

        self.assertEqual(captured, [{"user_id": 99, "tenant_id": 3}])
        self.assertEqual(llm_usage_service.current_context(), {}, "请求结束后应清理上下文")


class TestLlmObservability(unittest.TestCase):

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(main.app)

    def test_metrics_exposes_llm_series(self):
        body = self.client.get("/metrics").text
        self.assertIn("fire_ai_llm_calls_total", body)
        self.assertIn("fire_ai_llm_tokens_total", body)
        self.assertIn("fire_ai_llm_cost_usd_total", body)

    def test_breaker_state_series(self):
        llm_resilience.reset_breakers()
        llm_resilience.get_breaker("test-provider:https://x").record_failure()
        body = self.client.get("/metrics").text
        self.assertIn("fire_ai_llm_breaker_state", body)
        self.assertIn('provider="test-provider:https://x"', body)
        llm_resilience.reset_breakers()

    def test_llm_admin_endpoints_require_authentication(self):
        for path in ("/api/settings/llm-usage", "/api/settings/llm-calls", "/api/settings/llm-governance"):
            resp = self.client.get(path)
            self.assertIn(resp.status_code, (401, 403), f"{path} 不应匿名可访问")


def _default_tenant_id():
    db = SessionLocal()
    try:
        return get_default_tenant_id(db)
    finally:
        db.close()


def setUpModule():
    init_db()


def tearDownModule():
    db = SessionLocal()
    try:
        db.query(LlmCallLog).filter(LlmCallLog.purpose == PURPOSE_TAG).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    unittest.main()
