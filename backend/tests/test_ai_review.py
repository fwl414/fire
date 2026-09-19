"""AI 结果人工复核测试

覆盖：
- 置信度判定与复核触发规则
- 待复核任务落库与租户隔离
- 复核通过后才生成工单、驳回不生成工单
- 重复复核被拒绝（409）
- AI 巡检链路：低可信结论不再自动下发工单，而是进入复核队列
- 指标暴露待复核数量
"""
import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AiReviewTask,
    FaultTicket,
    InspectionRecord,
    Role,
    SessionLocal,
    Tenant,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import ai_review_service

TEST_USERNAME = "ai-review-tester"
TEST_PASSWORD = "Test#12345"
OTHER_TENANT_CODE = "ai-review-other-tenant"


class TestAiReviewRules(unittest.TestCase):
    """置信度与复核触发规则（纯函数）。"""

    def test_confidence_without_cloud_model_is_low(self):
        self.assertEqual(ai_review_service.assess_confidence(), ai_review_service.CONFIDENCE_LOW)

    def test_confidence_with_single_modality_is_medium(self):
        self.assertEqual(
            ai_review_service.assess_confidence(used_text_model_api=True),
            ai_review_service.CONFIDENCE_MEDIUM,
        )

    def test_confidence_with_both_modalities_is_high(self):
        self.assertEqual(
            ai_review_service.assess_confidence(used_vision_api=True, used_text_model_api=True),
            ai_review_service.CONFIDENCE_HIGH,
        )

    def test_model_error_downgrades_confidence(self):
        self.assertEqual(
            ai_review_service.assess_confidence(
                used_vision_api=True, used_text_model_api=True, vision_error="调用超时"
            ),
            ai_review_service.CONFIDENCE_LOW,
        )

    def test_low_confidence_always_requires_review(self):
        required, reason = ai_review_service.needs_manual_review(
            risk_level="低风险", confidence=ai_review_service.CONFIDENCE_LOW
        )
        self.assertTrue(required)
        self.assertIn("置信度低", reason)

    def test_high_risk_requires_review_even_if_confident(self):
        required, reason = ai_review_service.needs_manual_review(
            risk_level="高风险", confidence=ai_review_service.CONFIDENCE_HIGH
        )
        self.assertTrue(required)
        self.assertIn("高风险", reason)

    def test_low_risk_with_high_confidence_needs_no_review(self):
        required, reason = ai_review_service.needs_manual_review(
            risk_level="低风险", confidence=ai_review_service.CONFIDENCE_HIGH
        )
        self.assertFalse(required)
        self.assertEqual(reason, "")


class TestAiReviewApi(unittest.TestCase):
    """复核队列的 API 集成测试。"""

    client = None
    headers = {}
    tenant_id = None
    other_tenant_id = None
    created_user_id = None
    created_role_id = None
    created_tenant_id = None
    task_ids = []
    ticket_ids = []

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

            other = db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).first()
            if not other:
                other = Tenant(tenant_code=OTHER_TENANT_CODE, tenant_name="复核隔离租户", status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
                cls.created_tenant_id = other.id
            cls.other_tenant_id = other.id

            role = db.query(Role).filter(Role.role_code == "admin").first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code="admin",
                    role_name="系统管理员",
                    permissions='["*"]',
                    is_system=True,
                )
                db.add(role)
                db.commit()
                db.refresh(role)
                cls.created_role_id = role.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(
                    username=TEST_USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="AI复核测试员",
                    role_id=role.id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                cls.created_user_id = user.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        resp = cls.client.post(
            "/api/auth/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, f"登录失败: {resp.text}"
        cls.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            if cls.task_ids:
                db.query(AiReviewTask).filter(AiReviewTask.id.in_(cls.task_ids)).delete(
                    synchronize_session=False
                )
            if cls.ticket_ids:
                db.query(FaultTicket).filter(FaultTicket.id.in_(cls.ticket_ids)).delete(
                    synchronize_session=False
                )
            if cls.created_user_id:
                db.query(User).filter(User.id == cls.created_user_id).delete(synchronize_session=False)
            if cls.created_role_id:
                db.query(Role).filter(Role.id == cls.created_role_id).delete(synchronize_session=False)
            if cls.created_tenant_id:
                db.query(Tenant).filter(Tenant.id == cls.created_tenant_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _make_task(self, tenant_id=None, risk_level="高风险"):
        db = SessionLocal()
        try:
            task = ai_review_service.create_review_task(
                db,
                tenant_id=tenant_id if tenant_id is not None else self.tenant_id,
                source="inspection",
                record_id=None,
                risk_level=risk_level,
                risk_score=85,
                hazards=["消防通道堵塞"],
                confidence=ai_review_service.CONFIDENCE_LOW,
                reason="AI 结果置信度低：云端模型未生效或调用失败",
                ai_summary="建议现场复核并及时整改。",
                location="测试楼栋",
            )
            db.commit()
            db.refresh(task)
            self.__class__.task_ids.append(task.id)
            return task.id
        finally:
            db.close()

    def test_api_requires_authentication(self):
        for path in ("/api/ai-review/tasks", "/api/ai-review/summary"):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post("/api/ai-review/tasks/1/approve").status_code, 401)

    def test_pending_task_is_visible_in_queue(self):
        task_id = self._make_task()
        resp = self.client.get("/api/ai-review/tasks?status=pending", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        ids = [item["id"] for item in resp.json()["items"]]
        self.assertIn(task_id, ids)

        summary = self.client.get("/api/ai-review/summary", headers=self.headers).json()
        self.assertGreaterEqual(summary["pending"], 1)

    def test_approve_creates_workorder(self):
        task_id = self._make_task()
        resp = self.client.post(
            f"/api/ai-review/tasks/{task_id}/approve",
            json={"note": "现场已确认，同意开工单"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertIsNotNone(payload["ticket_id"])
        self.__class__.ticket_ids.append(payload["ticket_id"])

        db = SessionLocal()
        try:
            task = db.query(AiReviewTask).filter(AiReviewTask.id == task_id).first()
            self.assertEqual(task.status, ai_review_service.STATUS_APPROVED)
            self.assertEqual(task.ticket_id, payload["ticket_id"])
            self.assertEqual(task.reviewer_name, TEST_USERNAME)

            ticket = db.query(FaultTicket).filter(FaultTicket.id == payload["ticket_id"]).first()
            self.assertIsNotNone(ticket)
            self.assertEqual(ticket.status, "待受理")
            self.assertEqual(ticket.source, "AI复核")
            self.assertIn("消防通道堵塞", ticket.description)
        finally:
            db.close()

    def test_reject_does_not_create_workorder(self):
        task_id = self._make_task()
        resp = self.client.post(
            f"/api/ai-review/tasks/{task_id}/reject",
            json={"note": "图片模糊，判定为误报"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsNone(resp.json()["ticket_id"])

        db = SessionLocal()
        try:
            task = db.query(AiReviewTask).filter(AiReviewTask.id == task_id).first()
            self.assertEqual(task.status, ai_review_service.STATUS_REJECTED)
            self.assertIsNone(task.ticket_id)
            self.assertIn("误报", task.review_note)
        finally:
            db.close()

    def test_repeated_review_is_rejected(self):
        task_id = self._make_task()
        first = self.client.post(f"/api/ai-review/tasks/{task_id}/reject", json={}, headers=self.headers)
        self.assertEqual(first.status_code, 200)
        second = self.client.post(f"/api/ai-review/tasks/{task_id}/approve", json={}, headers=self.headers)
        self.assertEqual(second.status_code, 409, second.text)

    def test_unknown_task_returns_404(self):
        resp = self.client.post("/api/ai-review/tasks/999999999/approve", json={}, headers=self.headers)
        self.assertEqual(resp.status_code, 404)

    def test_other_tenant_cannot_access_task(self):
        task_id = self._make_task()
        db = SessionLocal()
        try:
            self.assertIsNone(ai_review_service.get_task(db, task_id, self.other_tenant_id))
            self.assertEqual(ai_review_service.list_review_tasks(db, self.other_tenant_id), [])
        finally:
            db.close()


class TestInspectionAgentReviewGate(unittest.TestCase):
    """AI 巡检链路：低可信结论进入复核，不再自动下发工单。"""

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
        finally:
            db.close()

    def test_no_cloud_model_routes_to_review_instead_of_ticket(self):
        from services import agent_service

        db = SessionLocal()
        record_id = None
        try:
            with mock.patch.object(agent_service, "get_active_config", return_value=None), \
                    mock.patch("services.llm_fire_analyzer.get_active_config", return_value=None), \
                    mock.patch("services.image_analyzer.get_active_config", return_value=None):
                result = asyncio.run(
                    agent_service.run_inspection_agent(
                        db,
                        device_id=None,
                        location="AI复核测试楼栋",
                        description="现场发现明火，消防通道堵塞",
                        image_file=None,
                        tenant_id=self.tenant_id,
                    )
                )
            record_id = result["record_id"]

            decision = result["emergency_decision"]
            self.assertTrue(decision.get("need_ticket"), "该描述应触发工单建议")
            self.assertEqual(result["confidence"], ai_review_service.CONFIDENCE_LOW)
            self.assertTrue(result["review_required"], "低可信 AI 结论必须进入人工复核")
            self.assertIsNotNone(result["review_task_id"])
            self.assertFalse(result["auto_ticket"], "复核未通过前不得自动生成工单")

            task = db.query(AiReviewTask).filter(
                AiReviewTask.id == result["review_task_id"]
            ).first()
            self.assertIsNotNone(task)
            self.assertEqual(task.status, ai_review_service.STATUS_PENDING)
            self.assertEqual(task.record_id, record_id)
            self.assertIn("消防通道堵塞", task.hazards)

            self.assertIsNone(
                db.query(FaultTicket).filter(FaultTicket.record_id == record_id).first(),
                "复核闸门应拦住工单下发",
            )
        finally:
            if record_id:
                db.query(FaultTicket).filter(FaultTicket.record_id == record_id).delete(
                    synchronize_session=False
                )
                db.query(AiReviewTask).filter(AiReviewTask.record_id == record_id).delete(
                    synchronize_session=False
                )
                db.query(InspectionRecord).filter(InspectionRecord.id == record_id).delete(
                    synchronize_session=False
                )
            db.commit()
            db.close()


class TestAiReviewObservability(unittest.TestCase):

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(main.app)

    def test_metrics_exposes_pending_review_gauge(self):
        body = self.client.get("/metrics").text
        self.assertIn("fire_ai_review_pending", body)

    def test_business_counters_are_recorded(self):
        db = SessionLocal()
        try:
            task = ai_review_service.create_review_task(
                db,
                tenant_id=get_default_tenant_id(db),
                source="inspection",
                record_id=None,
                risk_level="高风险",
                risk_score=80,
                hazards=["明火"],
                confidence=ai_review_service.CONFIDENCE_LOW,
                reason="指标用例",
            )
            db.commit()
            db.refresh(task)
            task_id = task.id
        finally:
            db.close()

        body = self.client.get("/metrics").text
        self.assertIn('event="ai_review_created"', body)

        db = SessionLocal()
        try:
            row = db.query(AiReviewTask).filter(AiReviewTask.id == task_id).first()
            ai_review_service.reject_task(db, row, None, "指标用例清理")
            db.query(AiReviewTask).filter(AiReviewTask.id == task_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
