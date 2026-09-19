"""可观测性端点测试：Prometheus 指标、路径归一化、就绪探针与业务计数。"""
import os
import re
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import LoginAttemptState, Role, SessionLocal, User, hash_password, init_db, get_default_tenant_id

PROBE_USERNAME_PREFIX = "metrics-probe-"


def _metric_value(text: str, metric: str, labels: str = "") -> float:
    pattern = rf"^{re.escape(metric)}\{{{re.escape(labels)}\}} ([0-9.eE+-]+)$" if labels else rf"^{re.escape(metric)} ([0-9.eE+-]+)$"
    for line in text.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            return float(match.group(1))
    return 0.0


class TestObservability(unittest.TestCase):

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(main.app)
        # /health 与 /metrics 属于探针路径，不纳入指标；这里制造一次业务请求
        cls.client.get("/api/alerts/1")

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(LoginAttemptState).filter(
                LoginAttemptState.username.like(PROBE_USERNAME_PREFIX + "%")
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def test_metrics_endpoint_exposes_core_series(self):
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.text
        self.assertIn("fire_ai_up 1", body)
        self.assertIn("fire_ai_uptime_seconds", body)
        self.assertIn("fire_ai_database_ready 1", body)
        self.assertIn("fire_ai_http_requests_total", body)
        self.assertIn('path="/api/alerts/{id}"', body)
        # 探针路径不应污染指标
        self.assertNotIn('path="/health"', body)

    def test_metrics_path_labels_are_normalized(self):
        self.client.get("/api/alerts/123456")
        body = self.client.get("/metrics").text
        self.assertIn('path="/api/alerts/{id}"', body)
        self.assertNotIn('path="/api/alerts/123456"', body)

    def test_ready_probe_reports_database(self):
        resp = self.client.get("/ready")
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["database"])

    def test_failed_login_increments_business_counter(self):
        username = PROBE_USERNAME_PREFIX + uuid.uuid4().hex[:8]
        before = _metric_value(
            self.client.get("/metrics").text,
            "fire_ai_business_events_total",
            'event="login_failed"',
        )

        login = self.client.post("/api/auth/login", data={"username": username, "password": "wrong"})
        self.assertEqual(login.status_code, 401)

        after = _metric_value(
            self.client.get("/metrics").text,
            "fire_ai_business_events_total",
            'event="login_failed"',
        )
        self.assertGreater(after, before, "登录失败应反映到指标中")

    def test_metrics_summary_requires_authentication(self):
        anonymous = self.client.get("/api/system/metrics-summary")
        self.assertEqual(anonymous.status_code, 401)

    def test_metrics_access_policy(self):
        """生产环境必须配置 METRICS_TOKEN 才能抓取指标，避免指标裸奔。"""
        from unittest import mock

        from services import metrics_service

        # 生产 + 已配置令牌：必须携带正确令牌
        with mock.patch.object(metrics_service, "IS_PRODUCTION", True), \
                mock.patch.object(metrics_service, "METRICS_TOKEN", "s3cret-token"):
            self.assertFalse(metrics_service.metrics_authorized(None))
            self.assertFalse(metrics_service.metrics_authorized("wrong"))
            self.assertTrue(metrics_service.metrics_authorized("s3cret-token"))

        # 生产 + 未配置令牌：一律拒绝
        with mock.patch.object(metrics_service, "IS_PRODUCTION", True), \
                mock.patch.object(metrics_service, "METRICS_TOKEN", ""):
            self.assertFalse(metrics_service.metrics_authorized(None))
            self.assertFalse(metrics_service.metrics_authorized("anything"))

        # 非生产：便于本地调试
        with mock.patch.object(metrics_service, "IS_PRODUCTION", False), \
                mock.patch.object(metrics_service, "METRICS_TOKEN", ""):
            self.assertTrue(metrics_service.metrics_authorized(None))

    def test_metrics_token_enforced_by_endpoint(self):
        """端点层同样执行令牌校验（生产策略下匿名请求应 403）。"""
        from unittest import mock

        from services import metrics_service

        with mock.patch.object(metrics_service, "IS_PRODUCTION", True), \
                mock.patch.object(metrics_service, "METRICS_TOKEN", "s3cret-token"):
            unauthorized = self.client.get("/metrics")
            self.assertEqual(unauthorized.status_code, 403)
            authorized = self.client.get("/metrics", headers={"X-Metrics-Token": "s3cret-token"})
            self.assertEqual(authorized.status_code, 200)
            via_query = self.client.get("/metrics?token=s3cret-token")
            self.assertEqual(via_query.status_code, 200)


if __name__ == "__main__":
    unittest.main()
