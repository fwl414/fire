"""WebSocket 实时推送测试

背景：改造前 `/ws/notifications/{user_id}` 有三个问题，本文件把它们固化成回归守卫：

1. `user_id` 由 URL 自报，握手阶段不做任何令牌校验 —— 任何人都能以任意身份连上；
2. 推送是全量广播（遍历所有连接），A 租户的告警会推给 B 租户；
3. 触发推送用的是 `asyncio.create_task`，而调用它的接口是同步 `def`（跑在线程池里），
   会抛 `RuntimeError: no running event loop`，即推送从未真正发出过。
"""
import asyncio
import json
import os
import sys
import threading
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from database import AlertRecord, Role, SessionLocal, Tenant, User, hash_password, init_db
from services import alert_lifecycle_service, business_crud_service
from services.alert_lifecycle_service import ingest_alert
from services.auth_service import create_access_token
from services.websocket_service import Client, ConnectionManager

TENANT_A_CODE = "ws-test-tenant-a"
TENANT_B_CODE = "ws-test-tenant-b"
USER_A = "ws-tester-a"
USER_B = "ws-tester-b"
PASSWORD = "Test#12345"
ROLE_CODE = "ws-test-admin"
WS_URL = "/ws/notifications"


class _FakeWebSocket:
    """只记录收到什么的假连接：用来单独验证「推送范围」，不牵扯真实事件循环。"""

    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


class TestWebSocketPush(unittest.TestCase):

    client = None
    tenant_a_id = None
    tenant_b_id = None
    token_a = ""
    token_b = ""
    created = {}

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_a_id = cls._ensure_tenant(db, TENANT_A_CODE, "推送测试租户A")
            cls.tenant_b_id = cls._ensure_tenant(db, TENANT_B_CODE, "推送测试租户B")

            role = db.query(Role).filter(Role.role_code == ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_a_id,
                    role_code=ROLE_CODE,
                    role_name="推送测试管理员",
                    permissions=json.dumps(["*"]),
                )
                db.add(role)
                db.commit()
                db.refresh(role)
                cls.created["role"] = role.id

            user_a = cls._ensure_user(db, USER_A, cls.tenant_a_id, role.id)
            user_b = cls._ensure_user(db, USER_B, cls.tenant_b_id, role.id)
            # 直接签发令牌：本文件只关心握手校验，不必再走一遍登录流程
            cls.token_a = create_access_token(user_a)
            cls.token_b = create_access_token(user_b)
        finally:
            db.close()

        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(AlertRecord).filter(
                AlertRecord.tenant_id.in_([cls.tenant_a_id, cls.tenant_b_id])
            ).delete(synchronize_session=False)
            db.query(User).filter(User.username.in_([USER_A, USER_B])).delete(synchronize_session=False)
            if cls.created.get("role"):
                db.query(Role).filter(Role.id == cls.created["role"]).delete(synchronize_session=False)
            db.query(Tenant).filter(Tenant.tenant_code.in_([TENANT_A_CODE, TENANT_B_CODE])).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    @classmethod
    def _ensure_tenant(cls, db, code, name):
        tenant = db.query(Tenant).filter(Tenant.tenant_code == code).first()
        if not tenant:
            tenant = Tenant(tenant_code=code, tenant_name=name, status="active")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return tenant.id

    @classmethod
    def _ensure_user(cls, db, username, tenant_id, role_id):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            hashed, salt = hash_password(PASSWORD)
            user = User(
                username=username,
                password_hash=hashed,
                password_salt=salt,
                real_name=username,
                role_id=role_id,
                status="active",
                tenant_id=tenant_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def _receive_json_within(self, ws, timeout=5.0):
        """带超时的接收。

        TestClient 的 `receive_json()` 没有超时，推送没到达时会把整个用例挂死，
        因此放到子线程里等，超时即判定失败。
        """
        result = {}

        def _worker():
            try:
                result["message"] = ws.receive_json()
            except Exception as exc:  # noqa: BLE001 - 测试辅助，异常统一带回主线程
                result["error"] = exc

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            self.fail(f"{timeout} 秒内没有收到推送")
        if "error" in result:
            raise result["error"]
        return result["message"]

    # ---------------- 握手鉴权 ----------------

    def test_first_frame_must_be_auth(self):
        """首帧不是认证帧就关连接（改造前根本不校验，发什么都能连上）。"""
        with self.client.websocket_connect(WS_URL) as ws:
            ws.send_json({"action": "subscribe", "channels": ["alert"]})
            with self.assertRaises(WebSocketDisconnect) as ctx:
                ws.receive_json()
        self.assertEqual(ctx.exception.code, 4401)

    def test_invalid_token_is_rejected(self):
        with self.client.websocket_connect(WS_URL) as ws:
            ws.send_json({"action": "auth", "token": "not-a-real-token"})
            with self.assertRaises(WebSocketDisconnect) as ctx:
                ws.receive_json()
        self.assertEqual(ctx.exception.code, 4401)

    def test_identity_comes_from_token_not_client_claims(self):
        """身份只认令牌：客户端自报的 user_id / tenant_id 必须被忽略。"""
        with self.client.websocket_connect(WS_URL) as ws:
            ws.send_json({
                "action": "auth",
                "token": self.token_a,
                "user_id": 999999,
                "tenant_id": self.tenant_b_id,
            })
            hello = self._receive_json_within(ws)
            self.assertEqual(hello["type"], "auth_ok")
            self.assertEqual(hello["data"]["tenant_id"], self.tenant_a_id)
            self.assertNotEqual(hello["data"]["user_id"], 999999)

    # ---------------- 推送范围 ----------------

    def test_send_to_tenant_does_not_leak_across_tenants(self):
        """推送只发本租户：改造前是遍历所有连接广播。"""
        scoped = ConnectionManager()
        fake_a = _FakeWebSocket()
        fake_b = _FakeWebSocket()
        scoped.add(Client(websocket=fake_a, user_id=1, username="a", tenant_id=101))
        scoped.add(Client(websocket=fake_b, user_id=2, username="b", tenant_id=202))
        self.assertEqual(scoped.active_connection_count(), 2)

        asyncio.run(scoped.send_to_tenant(101, {"type": "alert", "data": {"id": 1}}))

        self.assertEqual(len(fake_a.sent), 1, "本租户连接必须收到")
        self.assertEqual(fake_b.sent, [], "其它租户连接不能收到")
        self.assertEqual(fake_a.sent[0]["type"], "alert")

    def test_new_alert_is_pushed_to_its_tenant(self):
        """新告警经真实入库链路产生后，应推到该租户已认证的连接上。"""
        with self.client.websocket_connect(WS_URL) as ws:
            ws.send_json({"action": "auth", "token": self.token_a})
            self.assertEqual(self._receive_json_within(ws)["type"], "auth_ok")

            db = SessionLocal()
            try:
                ingest_alert(
                    db,
                    tenant_id=self.tenant_a_id,
                    alert_type="推送用例-烟雾浓度超限",
                    severity="critical",
                    description="用于验证推送链路",
                )
            finally:
                db.close()

            event = self._receive_json_within(ws)
        self.assertEqual(event["type"], "alert")
        self.assertEqual(event["data"]["alert_type"], "推送用例-烟雾浓度超限")
        self.assertEqual(event["data"]["severity"], "critical")

    # ---------------- 推送时机 ----------------

    def test_merged_repeat_pushes_only_when_escalated(self):
        """归并不推送，只有升级才再推一次：否则高频重复上报会把大屏刷爆。"""
        pushed = []
        original = alert_lifecycle_service.send_alert_notification
        alert_lifecycle_service.send_alert_notification = (
            lambda tenant_id, alert: pushed.append((tenant_id, alert))
        )
        try:
            db = SessionLocal()
            try:
                def _ingest(description):
                    return ingest_alert(
                        db,
                        tenant_id=self.tenant_a_id,
                        alert_type="推送用例-重复告警",
                        severity="low",
                        description=description,
                        repeat_threshold=3,
                    )

                first = _ingest("首次上报")
                second = _ingest("第二次上报（归并）")
                third = _ingest("第三次上报（升级）")
            finally:
                db.close()
        finally:
            alert_lifecycle_service.send_alert_notification = original

        self.assertEqual(first["action"], "created")
        self.assertEqual(second["action"], "merged")
        self.assertFalse(second["escalated"], "未达阈值时不应升级")
        self.assertTrue(third["escalated"], "达到重复阈值后应升级")
        self.assertEqual(len(pushed), 2, "只推「新建」与「升级」两次")
        self.assertTrue(all(tenant_id == self.tenant_a_id for tenant_id, _ in pushed))

    def test_alert_created_via_business_api_is_pushed_too(self):
        """手工建告警与设备接入链路保持一致的推送行为。"""
        pushed = []
        original = business_crud_service.send_alert_notification
        business_crud_service.send_alert_notification = (
            lambda tenant_id, alert: pushed.append((tenant_id, alert))
        )
        try:
            db = SessionLocal()
            try:
                result = business_crud_service.create_alert(db, self.tenant_a_id, {
                    "alert_code": f"WS-TEST-{uuid.uuid4().hex[:8]}",
                    "alert_type": "推送用例-手工建单",
                    "severity": "high",
                    "description": "通过 CRUD 服务直接创建",
                })
            finally:
                db.close()
        finally:
            business_crud_service.send_alert_notification = original

        self.assertTrue(result["ok"], result)
        self.assertEqual(len(pushed), 1)
        self.assertEqual(pushed[0][0], self.tenant_a_id)


if __name__ == "__main__":
    unittest.main()
