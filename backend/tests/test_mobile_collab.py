"""移动端协同

移动端页面本身不做业务，所有数字都来自这几个接口，所以本文件重点固化：

- 首页/待办的统计与列表**只统计真实数据**（按租户 + 当前用户过滤，别的租户看不到）
- 领取工单的语义：只有「待受理」且没人认领的工单能被领取，领完变成「处理中」并指派给自己；
  被别人领走或已闭环的要给出原因，不能静默改指派
- 现场上报：至少要给建筑/设备/位置之一；提交后必须真的落一条巡检记录（复用巡检 Agent）
"""
import json
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AiReviewTask,
    AlertRecord,
    Building,
    Device,
    FaultTicket,
    InspectionRecord,
    Role,
    SessionLocal,
    Tenant,
    User,
    hash_password,
    init_db,
)
from services.auth_service import create_access_token

TENANT_CODE = "mobile-tenant"
OTHER_TENANT_CODE = "mobile-tenant-other"
FIELD_USER = "mobile-field"
VIEWER_USER = "mobile-viewer"
OTHER_USER = "mobile-other"
PASSWORD = "Test#12345"
FIELD_ROLE = "mobile-field-role"
VIEWER_ROLE = "mobile-viewer-role"

# 1x1 透明 PNG：用于「现场上报」的图片字段
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000100ffff03000006000557bfabd4000000"
    "0049454e44ae426082"
)


class TestMobileCollab(unittest.TestCase):

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = cls._ensure_tenant(db, TENANT_CODE, "移动端测试租户").id
            cls.other_tenant_id = cls._ensure_tenant(db, OTHER_TENANT_CODE, "移动端测试租户B").id
            # 现场人员的角色要能上报（inspection:run）与领取工单（workorders:update）
            field_role = cls._ensure_role(
                db, FIELD_ROLE, cls.tenant_id, ["dashboard:view", "inspection:run", "workorders:update"]
            )
            viewer_role = cls._ensure_role(db, VIEWER_ROLE, cls.tenant_id, ["dashboard:view"])
            field_user = cls._ensure_user(db, FIELD_USER, cls.tenant_id, field_role.id)
            viewer = cls._ensure_user(db, VIEWER_USER, cls.tenant_id, viewer_role.id)
            other = cls._ensure_user(db, OTHER_USER, cls.tenant_id, field_role.id)
            cls.field_user_id = field_user.id
            cls.other_user_id = other.id
            cls.token_field = create_access_token(field_user)
            cls.token_viewer = create_access_token(viewer)
            # 设备/建筑各建一个，供上报时选择（按编号幂等：上一轮跑挂在中途也不会重复插入）
            building = db.query(Building).filter(
                Building.tenant_id == cls.tenant_id, Building.building_code == "mobile-bld-1"
            ).first()
            if not building:
                building = Building(
                    tenant_id=cls.tenant_id, building_code="mobile-bld-1", building_name="移动端测试楼"
                )
                db.add(building)
                db.flush()
            device = db.query(Device).filter(
                Device.tenant_id == cls.tenant_id, Device.device_code == "mobile-dev-1"
            ).first()
            if not device:
                device = Device(
                    tenant_id=cls.tenant_id, device_code="mobile-dev-1", device_name="移动端烟感01",
                    device_type="烟感探测器", status="正常", building_id=building.id,
                    location="移动端测试楼2层",
                )
                db.add(device)
            db.commit()
            cls.building_id = building.id
            cls.device_id = device.id
        finally:
            db.close()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            for tenant_id in (cls.tenant_id, cls.other_tenant_id):
                # 现场上报会走巡检 Agent：置信度低时会落一条 AI 复核任务，必须一起清掉，
                # 否则残留的 (tenant_id → 已删除租户) 会被后续用例按 id 复用后「串门」
                db.query(AiReviewTask).filter(AiReviewTask.tenant_id == tenant_id).delete(
                    synchronize_session=False
                )
                cls._purge_business(db, tenant_id)
            db.query(User).filter(User.username.in_([FIELD_USER, VIEWER_USER, OTHER_USER])).delete(
                synchronize_session=False
            )
            db.query(Role).filter(Role.role_code.in_([FIELD_ROLE, VIEWER_ROLE])).delete(
                synchronize_session=False
            )
            db.query(Tenant).filter(Tenant.tenant_code.in_([TENANT_CODE, OTHER_TENANT_CODE])).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _purge_business(db, tenant_id):
        for model in (InspectionRecord, AlertRecord, FaultTicket):
            db.query(model).filter(model.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Device).filter(Device.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Building).filter(Building.tenant_id == tenant_id).delete(synchronize_session=False)

    # ---------------- 造数与工具 ----------------

    @classmethod
    def _ensure_tenant(cls, db, code, name):
        tenant = db.query(Tenant).filter(Tenant.tenant_code == code).first()
        if not tenant:
            tenant = Tenant(tenant_code=code, tenant_name=name, status="active")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return tenant

    @classmethod
    def _ensure_role(cls, db, code, tenant_id, permissions):
        role = db.query(Role).filter(Role.role_code == code).first()
        if not role:
            role = Role(tenant_id=tenant_id, role_code=code, role_name=code,
                        permissions=json.dumps(permissions))
            db.add(role)
            db.commit()
            db.refresh(role)
        return role

    @classmethod
    def _ensure_user(cls, db, username, tenant_id, role_id):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            hashed, salt = hash_password(PASSWORD)
            user = User(username=username, password_hash=hashed, password_salt=salt,
                        tenant_id=tenant_id, role_id=role_id, real_name=username, status="active")
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def setUp(self):
        """每个用例从干净的业务数据开始（建筑/设备保留，它们由 setUpClass 建一次）。"""
        db = SessionLocal()
        try:
            for tenant_id in (self.tenant_id, self.other_tenant_id):
                db.query(AiReviewTask).filter(AiReviewTask.tenant_id == tenant_id).delete(
                    synchronize_session=False
                )
                for model in (InspectionRecord, AlertRecord, FaultTicket):
                    db.query(model).filter(model.tenant_id == tenant_id).delete(synchronize_session=False)
            db.commit()
            self._seed(db)
        finally:
            db.close()

    def _seed(self, db):
        now = datetime.utcnow()
        # 告警：2 条待处置（1 条升级）+ 1 条已处置（不计入待办）
        db.add(AlertRecord(
            tenant_id=self.tenant_id, alert_code="MOB-ALERT-1", alert_type="smoke_high",
            severity="critical", status="pending", location="移动端测试楼2层",
            building_id=self.building_id, device_id=self.device_id, repeat_count=3,
            escalated=True, created_at=now,
        ))
        db.add(AlertRecord(
            tenant_id=self.tenant_id, alert_code="MOB-ALERT-2", alert_type="temperature_high",
            severity="high", status="processing", location="移动端测试楼3层",
            building_id=self.building_id, created_at=now,
        ))
        db.add(AlertRecord(
            tenant_id=self.tenant_id, alert_code="MOB-ALERT-3", alert_type="smoke_high",
            severity="low", status="resolved", location="移动端测试楼1层", created_at=now,
        ))
        # 工单：待受理（可领取）、我名下处理中、别人名下处理中、已完成
        db.add(FaultTicket(
            tenant_id=self.tenant_id, title="可领取的工单", status="待受理",
            building_id=self.building_id, risk_level="高风险", created_at=now,
        ))
        db.add(FaultTicket(
            tenant_id=self.tenant_id, title="我在办的工单", status="处理中",
            building_id=self.building_id, assignee_id=self.field_user_id, assignee_name=FIELD_USER,
            risk_level="高风险", created_at=now,
        ))
        db.add(FaultTicket(
            tenant_id=self.tenant_id, title="别人在办的工单", status="处理中",
            building_id=self.building_id, assignee_id=self.other_user_id, assignee_name=OTHER_USER,
            risk_level="中风险", created_at=now,
        ))
        db.add(FaultTicket(
            tenant_id=self.tenant_id, title="已完成的工单", status="已完成",
            building_id=self.building_id, assignee_id=self.field_user_id,
            risk_level="低风险", created_at=now,
        ))
        db.commit()

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def _ticket_id(self, title):
        db = SessionLocal()
        try:
            ticket = db.query(FaultTicket).filter(
                FaultTicket.tenant_id == self.tenant_id, FaultTicket.title == title
            ).first()
            return ticket.id if ticket else None
        finally:
            db.close()

    # ---------------- 首页 / 待办 ----------------

    def test_home_counts_only_real_open_items(self):
        resp = self.client.get("/api/mobile/home", headers=self._headers(self.token_field))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        self.assertEqual(body["stats"]["pendingAlerts"], 2)  # 已处置的那条不算
        self.assertEqual(body["stats"]["claimableWorkorders"], 1)
        self.assertEqual(body["stats"]["myWorkorders"], 1)  # 我已完成的工单不算在办
        self.assertEqual(len(body["pendingAlerts"]), 2)
        self.assertEqual([item["title"] for item in body["claimableWorkorders"]], ["可领取的工单"])
        self.assertTrue(body["pendingAlerts"][0]["escalated"])
        self.assertEqual(body["pendingAlerts"][0]["statusLabel"], "待处置")
        # 身份信息来自登录态，不是前端写死的
        self.assertEqual(body["user"]["id"], self.field_user_id)

    def test_tasks_merge_workorders_and_alerts(self):
        resp = self.client.get("/api/mobile/tasks", headers=self._headers(self.token_field))
        body = resp.json()
        self.assertEqual(body["workorderCount"], 1)
        self.assertEqual(body["alertCount"], 2)
        self.assertEqual({item["type"] for item in body["items"]}, {"workorder", "alert"})

        workorder = next(item for item in body["items"] if item["type"] == "workorder")
        self.assertTrue(workorder["mine"], "我名下的工单要标出 mine")
        self.assertEqual(workorder["title"], "我在办的工单")
        # 列表按时间倒序
        times = [item["createdAt"] for item in body["items"]]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_other_tenants_data_is_not_visible(self):
        db = SessionLocal()
        try:
            db.add(FaultTicket(
                tenant_id=self.other_tenant_id, title="别家的工单", status="待受理",
                risk_level="高风险", created_at=datetime.utcnow(),
            ))
            db.commit()
        finally:
            db.close()

        body = self.client.get("/api/mobile/home", headers=self._headers(self.token_field)).json()
        self.assertEqual(body["stats"]["claimableWorkorders"], 1)
        self.assertEqual([item["title"] for item in body["claimableWorkorders"]], ["可领取的工单"])

    # ---------------- 领取工单 ----------------

    def test_claim_assigns_the_ticket_to_me(self):
        order_id = self._ticket_id("可领取的工单")
        resp = self.client.post(
            f"/api/mobile/workorders/{order_id}/claim", headers=self._headers(self.token_field)
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["workorder"]["status"], "处理中")
        self.assertEqual(body["workorder"]["assigneeId"], self.field_user_id)

        db = SessionLocal()
        try:
            ticket = db.query(FaultTicket).filter(FaultTicket.id == order_id).first()
            self.assertEqual(ticket.status, "处理中")
            self.assertEqual(ticket.assignee_id, self.field_user_id)
        finally:
            db.close()

        # 已经领过的工单不能重复领
        again = self.client.post(
            f"/api/mobile/workorders/{order_id}/claim", headers=self._headers(self.token_field)
        )
        self.assertEqual(again.status_code, 400)

    def test_claim_rejects_ticket_taken_by_someone_else(self):
        order_id = self._ticket_id("别人在办的工单")
        resp = self.client.post(
            f"/api/mobile/workorders/{order_id}/claim", headers=self._headers(self.token_field)
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("处理中", resp.json()["message"])

        db = SessionLocal()
        try:
            ticket = db.query(FaultTicket).filter(FaultTicket.id == order_id).first()
            self.assertEqual(ticket.assignee_id, self.other_user_id, "不能抢走别人名下的工单")
        finally:
            db.close()

    def test_claim_rejects_closed_ticket(self):
        order_id = self._ticket_id("已完成的工单")
        resp = self.client.post(
            f"/api/mobile/workorders/{order_id}/claim", headers=self._headers(self.token_field)
        )
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_claim_requires_workorders_update_permission(self):
        order_id = self._ticket_id("可领取的工单")
        resp = self.client.post(
            f"/api/mobile/workorders/{order_id}/claim", headers=self._headers(self.token_viewer)
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_claim_unknown_ticket_returns_404(self):
        resp = self.client.post(
            "/api/mobile/workorders/99999999/claim", headers=self._headers(self.token_field)
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    # ---------------- 现场上报 ----------------

    def test_report_needs_a_target(self):
        resp = self.client.post(
            "/api/mobile/report",
            data={"description": "现场有些异常"},
            headers=self._headers(self.token_field),
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("建筑", resp.json()["message"])

    def test_report_requires_inspection_permission(self):
        resp = self.client.post(
            "/api/mobile/report",
            data={"location": "移动端测试楼2层", "description": "灭火器被挡住"},
            headers=self._headers(self.token_viewer),
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_report_creates_an_inspection_record(self):
        resp = self.client.post(
            "/api/mobile/report",
            data={
                "building_id": str(self.building_id),
                "location": "",
                "description": "现场发现消防通道堵塞，且有电动车违规充电",
            },
            files={"image": ("site.png", PNG_BYTES, "image/png")},
            headers=self._headers(self.token_field),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["location"], "移动端测试楼")  # 没填位置时用建筑名
        self.assertIsNotNone(body["recordId"])
        self.assertIsInstance(body["riskScore"], int)
        self.assertTrue(body["hazards"], "规则引擎应识别出隐患")

        db = SessionLocal()
        try:
            record = db.query(InspectionRecord).filter(InspectionRecord.id == body["recordId"]).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.tenant_id, self.tenant_id)
            self.assertEqual(record.location, "移动端测试楼")
            self.assertGreater(record.risk_score, 0)
        finally:
            db.close()

    def test_report_rejects_unknown_building(self):
        resp = self.client.post(
            "/api/mobile/report",
            data={"building_id": "99999999"},
            headers=self._headers(self.token_field),
        )
        self.assertEqual(resp.status_code, 404, resp.text)


if __name__ == "__main__":
    unittest.main()
