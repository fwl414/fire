"""设备接入（HTTP 签名 + MQTT）与设备身份认证的集成测试。

覆盖：
- 设备凭证签发/轮换/吊销与脱敏
- 签名校验、时间戳窗口、nonce 防重放、接入禁用
- 遥测落库、阈值告警、告警去重、工单闭环
- 事件上报与心跳
- MQTT 消息处理（直接调用消息处理函数，无需真实 broker）
- 协议说明接口
"""
import json
import os
import sys
import time
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AlertRecord,
    Device,
    DeviceRequestNonce,
    DeviceTelemetry,
    FaultTicket,
    Role,
    SessionLocal,
    User,
    hash_password,
    init_db,
    get_default_tenant_id,
)
from services import mqtt_ingest_service
from services.device_auth_service import canonical_payload_bytes, compute_signature

USERNAME = "device-ingest-tester"
PASSWORD = "Test#12345"
DEVICE_CODE = "AITEST-DEV-001"


class TestDeviceIngest(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None
    device_id = None
    secret = ""
    created_user_id = None
    created_role_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

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

            user = db.query(User).filter(User.username == USERNAME).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(
                    username=USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="设备接入测试员",
                    role_id=role_id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                cls.created_user_id = user.id

            device = db.query(Device).filter(Device.device_code == DEVICE_CODE).first()
            if not device:
                device = Device(
                    tenant_id=cls.tenant_id,
                    device_code=DEVICE_CODE,
                    device_name="接入测试烟感",
                    device_type="烟感探测器",
                    location="测试楼A区",
                    status="正常",
                )
                db.add(device)
                db.commit()
                db.refresh(device)
            cls.device_id = device.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        resp = cls.client.post("/api/auth/login", data={"username": USERNAME, "password": PASSWORD})
        assert resp.status_code == 200, f"登录失败: {resp.text}"
        cls.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(AlertRecord).filter(
                AlertRecord.tenant_id == cls.tenant_id,
                AlertRecord.device_code == DEVICE_CODE,
            ).delete(synchronize_session=False)
            db.query(FaultTicket).filter(
                FaultTicket.tenant_id == cls.tenant_id,
                FaultTicket.title.like("%测试楼A区%"),
            ).delete(synchronize_session=False)
            db.query(DeviceTelemetry).filter(
                DeviceTelemetry.device_id == cls.device_id
            ).delete(synchronize_session=False)
            db.query(DeviceRequestNonce).filter(
                DeviceRequestNonce.device_id == cls.device_id
            ).delete(synchronize_session=False)
            db.query(Device).filter(Device.device_code == DEVICE_CODE).delete(synchronize_session=False)
            if cls.created_user_id:
                db.query(User).filter(User.id == cls.created_user_id).delete(synchronize_session=False)
            if cls.created_role_id:
                db.query(Role).filter(Role.id == cls.created_role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    # ---------------- 工具方法 ----------------

    def _signed_post(self, path, data, *, device_code=DEVICE_CODE, secret=None, timestamp=None,
                     nonce=None, signature=None, headers=None):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ts = timestamp if timestamp is not None else str(int(time.time()))
        nc = nonce if nonce is not None else uuid.uuid4().hex
        sig = signature
        if sig is None:
            sig = compute_signature(secret if secret is not None else self.secret, device_code, ts, nc, raw)
        request_headers = {
            "X-Device-Code": device_code,
            "X-Device-Timestamp": ts,
            "X-Device-Nonce": nc,
            "X-Device-Signature": sig,
            **(headers or {}),
        }
        return self.client.post(path, headers=request_headers, content=raw)

    def _set_ingest_enabled(self, enabled):
        return self.client.post(
            f"/api/devices/{self.device_id}/ingest-toggle",
            headers=self.headers,
            json={"enabled": enabled},
        )

    # ---------------- 用例 ----------------

    def test_01_issue_and_read_credentials(self):
        resp = self.client.post(
            f"/api/devices/{self.device_id}/credentials", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        secret = body["device_secret"]
        self.assertEqual(len(secret), 64, "设备密钥应为 32 字节十六进制")
        self.assertEqual(body["signature_algorithm"], "HMAC-SHA256")
        self.assertNotIn(secret, json.dumps(body["device"], ensure_ascii=False), "响应中的设备信息不得包含明文密钥")
        self.__class__.secret = secret

        status = self.client.get(
            f"/api/devices/{self.device_id}/credentials", headers=self.headers
        )
        self.assertEqual(status.status_code, 200, status.text)
        status_body = status.json()
        self.assertTrue(status_body["credential_issued"])
        self.assertTrue(status_body["secret_masked"].endswith("*" * 8))
        self.assertNotIn(secret, json.dumps(status_body, ensure_ascii=False), "状态接口必须脱敏")

    def test_02_signature_timestamp_and_nonce_are_enforced(self):
        path = "/api/device-ingest/telemetry"
        payload = {"smoke": 0.1}

        # 缺少签名头
        self.assertEqual(self.client.post(path, content=b"{}").status_code, 401)

        # 错误签名
        bad = self._signed_post(path, payload, signature="0" * 64)
        self.assertEqual(bad.status_code, 401, bad.text)
        self.assertIn("签名", bad.text)

        # 时间戳超窗
        stale = self._signed_post(path, payload, timestamp=str(int(time.time()) - 3600))
        self.assertEqual(stale.status_code, 401, stale.text)

        # 未注册设备
        unknown = self._signed_post(path, payload, device_code="NOT-REGISTERED-DEV")
        self.assertEqual(unknown.status_code, 401, unknown.text)

        # 正确签名
        ok = self._signed_post(path, payload)
        self.assertEqual(ok.status_code, 200, ok.text)

        # nonce 重放
        replay = self._signed_post(path, payload)
        used_nonce = replay.request.headers["X-Device-Nonce"]
        self.assertEqual(replay.status_code, 200)
        replayed = self._signed_post(path, payload, nonce=used_nonce)
        self.assertEqual(replayed.status_code, 401, "重复 nonce 必须被拒绝")
        self.assertIn("nonce", replayed.text)

        # 接入禁用
        self._set_ingest_enabled(False)
        disabled = self._signed_post(path, payload)
        self.assertEqual(disabled.status_code, 403, disabled.text)
        self._set_ingest_enabled(True)

    def test_03_telemetry_persists_and_raises_alert_with_workorder(self):
        resp = self._signed_post(
            "/api/device-ingest/telemetry",
            {"smoke": 1.6, "temperature": 30, "battery_level": 90},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreaterEqual(body["alert_count"], 1, "烟雾超阈值应生成告警")
        self.assertIn("smoke", body["metrics"])

        alert_entry = body["alerts"][0]
        self.assertIsNotNone(alert_entry["workorder_id"], "设备告警必须落库整改工单")

        db = SessionLocal()
        try:
            telemetry = db.query(DeviceTelemetry).filter(
                DeviceTelemetry.device_id == self.device_id
            ).order_by(DeviceTelemetry.id.desc()).first()
            self.assertIsNotNone(telemetry)
            self.assertEqual(telemetry.tenant_id, self.tenant_id)
            self.assertAlmostEqual(telemetry.smoke, 1.6, places=3)

            alert = db.query(AlertRecord).filter(AlertRecord.id == alert_entry["alert_id"]).first()
            self.assertEqual(alert.tenant_id, self.tenant_id)
            self.assertEqual(alert.device_code, DEVICE_CODE)
            self.assertTrue(alert.dedup_key, "设备告警应写入去重指纹")
            self.assertIsNotNone(alert.workorder_id)

            ticket = db.query(FaultTicket).filter(FaultTicket.id == alert.workorder_id).first()
            self.assertEqual(ticket.status, "待受理")
            self.assertEqual(ticket.source, "设备告警")

            device = db.query(Device).filter(Device.id == self.device_id).first()
            self.assertIsNotNone(device.last_seen_at, "上报后应刷新 last_seen_at")
        finally:
            db.close()

    def test_04_repeated_telemetry_is_deduplicated(self):
        first = self._signed_post("/api/device-ingest/telemetry", {"smoke": 1.5}).json()["alerts"][0]
        second = self._signed_post("/api/device-ingest/telemetry", {"smoke": 1.5}).json()["alerts"][0]

        self.assertEqual(second["alert_id"], first["alert_id"], "同类告警应归并到同一记录")
        self.assertEqual(second["dedup_action"], "merged")
        self.assertEqual(
            second["repeat_count"], first["repeat_count"] + 1, "重复次数应累加"
        )
        self.assertEqual(
            second["workorder_id"], first["workorder_id"], "重复上报不应重复建单"
        )

    def test_05_event_and_heartbeat(self):
        event = self._signed_post(
            "/api/device-ingest/event",
            {"event_type": "fire", "description": "现场发现明火", "severity": "critical"},
        )
        self.assertEqual(event.status_code, 200, event.text)
        self.assertEqual(event.json()["event_type"], "fire")
        self.assertIsNotNone(event.json()["workorder_id"])

        heartbeat = self._signed_post("/api/device-ingest/heartbeat", {})
        self.assertEqual(heartbeat.status_code, 200, heartbeat.text)
        self.assertTrue(heartbeat.json()["received"])

    def test_06_mqtt_message_processing(self):
        topic = f"{mqtt_ingest_service.MQTT_TOPIC_PREFIX}/{self.tenant_id}/{DEVICE_CODE}/telemetry"
        data = {"temperature": 26.5, "battery_level": 88}
        envelope = {
            "timestamp": int(time.time()),
            "nonce": uuid.uuid4().hex,
            "data": data,
        }
        envelope["signature"] = compute_signature(
            self.secret,
            DEVICE_CODE,
            str(envelope["timestamp"]),
            envelope["nonce"],
            canonical_payload_bytes(data),
        )
        raw = json.dumps(envelope, ensure_ascii=False).encode("utf-8")

        result = mqtt_ingest_service.handle_message(topic, raw)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["kind"], "telemetry")

        # 主题不规范
        self.assertFalse(mqtt_ingest_service.handle_message("bad/topic", raw)["ok"])

        # 租户不匹配（设备属于默认租户）
        other_topic = f"{mqtt_ingest_service.MQTT_TOPIC_PREFIX}/999999/{DEVICE_CODE}/telemetry"
        mismatch = mqtt_ingest_service.handle_message(other_topic, raw)
        self.assertFalse(mismatch["ok"])
        self.assertEqual(mismatch.get("status_code"), 403)

        # 签名错误
        bad_envelope = dict(envelope, signature="0" * 64, nonce=uuid.uuid4().hex)
        bad = mqtt_ingest_service.handle_message(
            topic, json.dumps(bad_envelope, ensure_ascii=False).encode("utf-8")
        )
        self.assertFalse(bad["ok"])

        # 缺少 data
        no_data = mqtt_ingest_service.handle_message(
            topic, json.dumps({"timestamp": 1, "nonce": "n", "signature": "s"}).encode("utf-8")
        )
        self.assertFalse(no_data["ok"])

    def test_07_protocol_and_stats_endpoints(self):
        protocol = self.client.get("/api/device-ingest/protocol", headers=self.headers)
        self.assertEqual(protocol.status_code, 200, protocol.text)
        body = protocol.json()
        self.assertEqual(body["authentication"]["algorithm"], "HMAC-SHA256")
        self.assertIn("signature_base", body["authentication"])
        self.assertEqual(len(body["http"]["endpoints"]), 3)
        self.assertTrue(body["mqtt"]["subscriptions"])
        self.assertTrue(body["metrics"])

        stats = self.client.get("/api/device-ingest/stats", headers=self.headers)
        self.assertEqual(stats.status_code, 200, stats.text)
        self.assertIn("received", stats.json())

    def test_08_simulate_endpoint_requires_permission(self):
        resp = self.client.post(
            "/api/device-ingest/simulate",
            headers=self.headers,
            json={"device_id": self.device_id, "kind": "telemetry", "data": {"smoke": 0.1}},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        unauthenticated = self.client.post(
            "/api/device-ingest/simulate",
            json={"device_id": self.device_id, "kind": "telemetry", "data": {"smoke": 0.1}},
        )
        self.assertEqual(unauthenticated.status_code, 401)

    def test_09_revoke_credentials_blocks_ingest(self):
        resp = self.client.delete(
            f"/api/devices/{self.device_id}/credentials", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(resp.json()["device"]["credential_issued"])

        blocked = self._signed_post("/api/device-ingest/telemetry", {"smoke": 0.1})
        self.assertEqual(blocked.status_code, 401, "吊销后无凭证应拒绝接入（401 未认证）")
        self.assertIn("凭证", blocked.text)

        # 重新签发恢复
        reissue = self.client.post(
            f"/api/devices/{self.device_id}/credentials", headers=self.headers
        )
        self.assertEqual(reissue.status_code, 200, reissue.text)
        self.__class__.secret = reissue.json()["device_secret"]
        restored = self._signed_post("/api/device-ingest/telemetry", {"smoke": 0.1})
        self.assertEqual(restored.status_code, 200, restored.text)


if __name__ == "__main__":
    unittest.main()
