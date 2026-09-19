"""告警 → 工单 → 整改 → 复查 闭环的 API 集成测试。

覆盖：
- 告警去重（重复告警归并到同一条记录并累加重复次数）
- 告警自动升级（重复次数达阈值）
- 超时未闭环告警批量升级
- 告警人工合并
- 告警生成的工单落库并与告警双向关联
- 工单整改 → 复查 → 通过后同步关闭来源告警
- 跨租户隔离
"""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AlertRecord,
    FaultTicket,
    Role,
    SessionLocal,
    Tenant,
    User,
    hash_password,
    init_db,
    get_default_tenant_id,
)
from services.alert_lifecycle_service import MERGED_STATUS

TEST_USERNAME = "alert-lifecycle-tester"
TEST_PASSWORD = "Test#12345"
TEST_DEVICE_CODE = "TEST-DEV-001"


class TestAlertLifecycle(unittest.TestCase):
    """告警闭环 API 集成测试。"""

    client = None
    headers = {}
    tenant_id = None
    user_id = None
    created_alert_ids = []
    created_ticket_ids = []
    created_user_id = None
    created_role_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            if not cls.tenant_id:
                tenant = Tenant(tenant_code="default", tenant_name="默认租户", status="active")
                db.add(tenant)
                db.commit()
                cls.tenant_id = tenant.id

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
            role_id = role.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(
                    username=TEST_USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="闭环测试员",
                    role_id=role_id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                cls.created_user_id = user.id
            cls.user_id = user.id
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
            if cls.created_alert_ids:
                db.query(AlertRecord).filter(
                    AlertRecord.id.in_(cls.created_alert_ids)
                ).delete(synchronize_session=False)
            if cls.created_ticket_ids:
                db.query(FaultTicket).filter(
                    FaultTicket.id.in_(cls.created_ticket_ids)
                ).delete(synchronize_session=False)
            if cls.created_user_id:
                db.query(User).filter(User.id == cls.created_user_id).delete(synchronize_session=False)
            if cls.created_role_id:
                db.query(Role).filter(Role.id == cls.created_role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    # ---------------- 工具方法 ----------------

    def _ingest_alert(self, alert_type="smoke_high", value=0.85, device_code=TEST_DEVICE_CODE, alert_value_unit="%obs/m"):
        resp = self.client.post(
            "/api/alert/process",
            headers=self.headers,
            data={
                "device_id": device_code,
                "alert_type": alert_type,
                "alert_value": value,
                "alert_unit": alert_value_unit,
                "device_info": (
                    '{"code":"%s","name":"测试烟感","location":"实验室A区"}' % device_code
                ),
                "building_name": "综合办公楼A座",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        if payload.get("alert_id"):
            self.__class__.created_alert_ids.append(payload["alert_id"])
        ticket_id = payload.get("workorder", {}).get("ticket_id")
        if ticket_id:
            self.__class__.created_ticket_ids.append(ticket_id)
        return payload

    def _ticket_of(self, alert_id):
        db = SessionLocal()
        try:
            alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
            if not alert or not alert.workorder_id:
                return None
            return db.query(FaultTicket).filter(FaultTicket.id == alert.workorder_id).first()
        finally:
            db.close()

    # ---------------- 用例 ----------------

    def test_01_ingest_creates_alert_and_persisted_ticket(self):
        payload = self._ingest_alert()

        self.assertEqual(payload["dedup"]["action"], "created")
        self.assertFalse(payload["dedup"]["merged"])
        self.assertEqual(payload["dedup"]["repeat_count"], 1)

        alert_id = payload["alert_id"]
        ticket_id = payload["workorder"]["ticket_id"]
        self.assertTrue(alert_id and ticket_id, "告警必须生成并关联工单")

        db = SessionLocal()
        try:
            alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
            self.assertIsNotNone(alert, "告警应已落库")
            self.assertEqual(alert.workorder_id, ticket_id, "alert.workorder_id 应回填为工单ID")
            self.assertTrue(alert.dedup_key, "应写入去重指纹")

            ticket = db.query(FaultTicket).filter(FaultTicket.id == ticket_id).first()
            self.assertIsNotNone(ticket, "工单应已落库到 fault_tickets")
            self.assertEqual(ticket.status, "待受理")
            self.assertEqual(ticket.source, "设备告警")
            self.assertEqual(ticket.tenant_id, self.tenant_id)
        finally:
            db.close()

        detail = self.client.get(f"/api/workorders/{ticket_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(body["source"], "设备告警")
        self.assertIsNotNone(body["source_alert"], "工单详情应能回溯来源告警")
        self.assertEqual(body["source_alert"]["id"], alert_id)

    def test_02_repeat_alerts_are_deduplicated_and_escalated(self):
        first = self._ingest_alert(device_code="TEST-DEV-DUP")
        alert_id = first["alert_id"]
        ticket_id = first["workorder"]["ticket_id"]
        self.assertEqual(first["dedup"]["action"], "created")

        second = self._ingest_alert(device_code="TEST-DEV-DUP")
        self.assertEqual(second["dedup"]["action"], "merged")
        self.assertTrue(second["dedup"]["merged"])
        self.assertEqual(second["alert_id"], alert_id, "重复告警应归并到同一条记录")
        self.assertEqual(second["dedup"]["repeat_count"], 2)

        third = self._ingest_alert(device_code="TEST-DEV-DUP")
        self.assertEqual(third["alert_id"], alert_id)
        self.assertEqual(third["dedup"]["repeat_count"], 3)
        self.assertTrue(third["dedup"]["escalated"], "重复达到阈值应触发升级")
        self.assertEqual(third["workorder"]["ticket_id"], ticket_id, "重复告警不应重复建单")

        db = SessionLocal()
        try:
            alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
            self.assertEqual(alert.repeat_count, 3)
            self.assertTrue(alert.escalated)
            self.assertIsNotNone(alert.escalated_at)
            self.assertIn("重复", alert.escalation_reason)
            self.assertIsNotNone(alert.first_seen_at)
            self.assertIsNotNone(alert.last_seen_at)

            tickets = db.query(FaultTicket).filter(
                FaultTicket.id == ticket_id
            ).count()
            self.assertEqual(tickets, 1, "同一告警只应存在一张工单")

            rows = db.query(AlertRecord).filter(
                AlertRecord.tenant_id == self.tenant_id,
                AlertRecord.device_code == "TEST-DEV-DUP",
            ).all()
            self.assertEqual(len(rows), 1, "去重后数据库中只应保留一条告警记录")
        finally:
            db.close()

    def test_03_closed_loop_alert_to_ticket_to_review(self):
        payload = self._ingest_alert(device_code="TEST-DEV-LOOP", alert_type="temperature_high")
        alert_id = payload["alert_id"]
        ticket_id = payload["workorder"]["ticket_id"]
        self.assertEqual(payload["dedup"]["action"], "created")

        # 未提交整改前不能直接复查
        early = self.client.post(
            f"/api/workorders/{ticket_id}/verify",
            headers=self.headers,
            json={"result": "通过"},
        )
        self.assertEqual(early.status_code, 400, "待受理工单不应允许复查")

        # 整改完成 → 待复查
        rectify = self.client.post(
            f"/api/workorders/{ticket_id}/rectify",
            headers=self.headers,
            json={"handle_result": "已更换老化线路并复测正常"},
        )
        self.assertEqual(rectify.status_code, 200, rectify.text)
        self.assertEqual(rectify.json()["status"], "待复查")

        # 重复提交整改应被拒绝
        again = self.client.post(
            f"/api/workorders/{ticket_id}/rectify",
            headers=self.headers,
            json={"handle_result": "重复提交"},
        )
        self.assertEqual(again.status_code, 400)

        # 复查通过 → 工单完成 + 来源告警闭环
        verify = self.client.post(
            f"/api/workorders/{ticket_id}/verify",
            headers=self.headers,
            json={"result": "通过", "note": "现场复查合格"},
        )
        self.assertEqual(verify.status_code, 200, verify.text)
        body = verify.json()
        self.assertEqual(body["status"], "已完成")
        self.assertEqual(body["review_result"], "通过")
        self.assertIsNotNone(body["closed_alert"], "复查通过应同步关闭来源告警")
        self.assertEqual(body["closed_alert"]["status"], "resolved")

        alert_resp = self.client.get(f"/api/alerts/{alert_id}", headers=self.headers)
        self.assertEqual(alert_resp.status_code, 200)
        self.assertEqual(alert_resp.json()["status"], "resolved")
        self.assertEqual(alert_resp.json()["workorder_id"], ticket_id)

    def test_04_manual_merge_and_merged_alert_is_hidden(self):
        primary = self._ingest_alert(device_code="TEST-DEV-MERGE", alert_type="remaining_current")
        other = self._ingest_alert(device_code="TEST-DEV-MERGE-2", alert_type="current_high")
        primary_id = primary["alert_id"]
        other_id = other["alert_id"]
        self.assertNotEqual(primary_id, other_id)

        merge = self.client.post(
            "/api/alerts/merge",
            headers=self.headers,
            json={"primary_id": primary_id, "duplicate_ids": [other_id]},
        )
        self.assertEqual(merge.status_code, 200, merge.text)
        body = merge.json()
        self.assertIn(other_id, body["merged_ids"])
        self.assertEqual(body["merged_count"], 1)
        self.assertEqual(body["repeat_count"], 2)

        db = SessionLocal()
        try:
            merged = db.query(AlertRecord).filter(AlertRecord.id == other_id).first()
            self.assertEqual(merged.status, MERGED_STATUS)
            self.assertEqual(merged.merged_into_id, primary_id)
        finally:
            db.close()

        # 默认列表不返回已合并告警
        listing = self.client.get("/api/alert/list?limit=200", headers=self.headers).json()
        ids = [item["id"] for item in listing["items"]]
        self.assertNotIn(other_id, ids, "已合并告警不应出现在默认列表")
        self.assertIn(primary_id, ids)

        listing_all = self.client.get(
            "/api/alert/list?limit=200&include_merged=true", headers=self.headers
        ).json()
        self.assertIn(other_id, [item["id"] for item in listing_all["items"]])

        # 已合并告警不能单独变更状态
        blocked = self.client.put(
            f"/api/alerts/{other_id}/status",
            headers=self.headers,
            json={"status": "resolved"},
        )
        self.assertEqual(blocked.status_code, 400)

    def test_05_escalate_overdue_alerts(self):
        payload = self._ingest_alert(device_code="TEST-DEV-OVERDUE", alert_type="battery_low")
        alert_id = payload["alert_id"]
        before_severity = None

        db = SessionLocal()
        try:
            alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
            before_severity = alert.severity
            alert.created_at = datetime.utcnow() - timedelta(hours=5)
            alert.escalated = False
            db.commit()
        finally:
            db.close()

        resp = self.client.post(
            "/api/alerts/escalate-overdue?sla_minutes=60", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreaterEqual(body["escalated_count"], 1)
        self.assertIsNotNone(body["items"])
        self.assertIn(alert_id, [item["id"] for item in body["items"]])

        db = SessionLocal()
        try:
            alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
            self.assertTrue(alert.escalated)
            self.assertIn("未闭环", alert.escalation_reason or "")
            from services.alert_lifecycle_service import severity_index
            self.assertGreaterEqual(
                severity_index(alert.severity), severity_index(before_severity)
            )
        finally:
            db.close()

    def test_06_cross_tenant_alerts_are_not_visible_or_mergeable(self):
        db = SessionLocal()
        try:
            other_tenant = Tenant(tenant_code="alert-iso-tenant", tenant_name="隔离测试租户")
            db.add(other_tenant)
            db.commit()

            foreign = AlertRecord(
                tenant_id=other_tenant.id,
                alert_code="AL-ISOLATION-0001",
                alert_type="smoke_high",
                severity="high",
                status="pending",
                device_code="FOREIGN-DEV",
                dedup_key=f"{other_tenant.id}:FOREIGN-DEV:smoke_high:",
                repeat_count=1,
            )
            db.add(foreign)
            db.commit()
            foreign_id = foreign.id
            other_tenant_id = other_tenant.id
        finally:
            db.close()

        try:
            listing = self.client.get("/api/alert/list?limit=500", headers=self.headers).json()
            self.assertNotIn(foreign_id, [item["id"] for item in listing["items"]])

            detail = self.client.get(f"/api/alerts/{foreign_id}", headers=self.headers)
            self.assertEqual(detail.status_code, 404, "不应能读取其他租户的告警")

            mine = self._ingest_alert(device_code="TEST-DEV-ISO", alert_type="smoke_high")
            merge = self.client.post(
                "/api/alerts/merge",
                headers=self.headers,
                json={"primary_id": mine["alert_id"], "duplicate_ids": [foreign_id]},
            )
            self.assertEqual(merge.status_code, 200, merge.text)
            self.assertEqual(merge.json()["merged_count"], 0, "不应能合并其他租户的告警")
        finally:
            db = SessionLocal()
            try:
                db.query(AlertRecord).filter(AlertRecord.id == foreign_id).delete(synchronize_session=False)
                db.query(Tenant).filter(Tenant.id == other_tenant_id).delete(synchronize_session=False)
                db.commit()
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
