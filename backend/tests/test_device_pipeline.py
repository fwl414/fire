"""设备消息队列 / 对象存储 / 跨实例锁 测试

覆盖：
- 设备消息幂等键生成与重复投递去重
- MQTT 回调改为「验签同步 + 业务异步」后：入收件箱、入队、worker 真正处理、幂等跳过
- 失败重试与死信（可恢复错误重试，不可恢复错误直接死信）
- 收件箱查询 / 统计 / 死信重放接口
- 存储抽象：本地读写、SigV4 签名结构、S3 镜像写入、本地缺失时从对象存储取回
- 跨实例锁：互斥、过期接管、只由持有者释放、run_exclusive 跳过语义
"""
import hashlib
import json
import os
import shutil
import sys
import time
import unittest
import uuid
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio

import httpx
from fastapi.testclient import TestClient

import main
from database import (
    Device,
    DeviceMessage,
    DeviceTelemetry,
    Role,
    RuntimeLock,
    SessionLocal,
    User,
    UploadedFile,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import (
    device_message_service as inbox,
    mqtt_ingest_service,
    runtime_lock_service as locks,
    storage_service as storage,
    upload_archive_service as uploads,
)
from services.device_auth_service import canonical_payload_bytes, compute_signature, issue_device_credentials
from services.task_queue_service import enqueue, registered_types
from services.task_worker_service import ensure_handlers_loaded, process_pending_once

USERNAME = "pipeline-tester"
PASSWORD = "Test#12345"
DEVICE_CODE = "PIPELINE-DEV-001"
OTHER_TENANT_CODE = "pipeline-other-tenant"


def _cleanup_device_messages():
    """清空收件箱、任务队列与运行时锁，保证用例互不干扰（worker 领取是全局的）。"""
    from database import BackgroundTask

    db = SessionLocal()
    try:
        db.query(DeviceMessage).delete(synchronize_session=False)
        db.query(BackgroundTask).delete(synchronize_session=False)
        db.query(RuntimeLock).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def asyncio_run(coro):
    return asyncio.run(coro)


class TestDeviceMessageInbox(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None
    other_tenant_id = None
    device_id = None
    secret = ""
    created_ids = {}

    @classmethod
    def setUpClass(cls):
        init_db()
        ensure_handlers_loaded()
        db = SessionLocal()
        try:
            from database import Tenant, FaultTicket, AlertRecord

            cls.tenant_id = get_default_tenant_id(db)

            other = db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).first()
            if not other:
                other = Tenant(tenant_code=OTHER_TENANT_CODE, tenant_name="管线隔离租户", status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
            cls.other_tenant_id = other.id

            role = db.query(Role).filter(Role.role_code == "admin").first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code="admin", role_name="系统管理员",
                            permissions='["*"]', is_system=True)
                db.add(role)
                db.commit()
                db.refresh(role)
                cls.created_ids["role"] = role.id

            user = db.query(User).filter(User.username == USERNAME).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(username=USERNAME, password_hash=hashed, password_salt=salt,
                            real_name="管线测试员", role_id=role.id, status="active",
                            tenant_id=cls.tenant_id)
                db.add(user)
                db.commit()
                db.refresh(user)
                cls.created_ids["user"] = user.id

            device = db.query(Device).filter(Device.device_code == DEVICE_CODE).first()
            if not device:
                device = Device(tenant_id=cls.tenant_id, device_code=DEVICE_CODE,
                                device_name="管线测试烟感", device_type="烟感探测器",
                                location="管线测试区", status="正常")
                db.add(device)
                db.commit()
                db.refresh(device)
            cls.device_id = device.id
            cls.secret = issue_device_credentials(db, device)
        finally:
            db.close()

        cls.client = TestClient(main.app)
        resp = cls.client.post("/api/auth/login", data={"username": USERNAME, "password": PASSWORD})
        assert resp.status_code == 200, f"登录失败: {resp.text}"
        cls.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        from database import AlertRecord, FaultTicket

        _cleanup_device_messages()
        db = SessionLocal()
        try:
            db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == cls.device_id).delete(
                synchronize_session=False
            )
            db.query(AlertRecord).filter(AlertRecord.device_code == DEVICE_CODE).delete(
                synchronize_session=False
            )
            db.query(FaultTicket).filter(FaultTicket.title.like("%管线测试%")).delete(
                synchronize_session=False
            )
            db.query(Device).filter(Device.device_code == DEVICE_CODE).delete(synchronize_session=False)
            if cls.created_ids.get("user"):
                db.query(User).filter(User.id == cls.created_ids["user"]).delete(synchronize_session=False)
            if cls.created_ids.get("role"):
                db.query(Role).filter(Role.id == cls.created_ids["role"]).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        _cleanup_device_messages()

    # ---------------- 工具 ----------------

    def _envelope(self, data, *, nonce=None, message_id=None):
        envelope = {
            "timestamp": int(time.time()),
            "nonce": nonce or uuid.uuid4().hex,
            "data": data,
        }
        if message_id:
            envelope["message_id"] = message_id
        envelope["signature"] = compute_signature(
            self.secret, DEVICE_CODE, str(envelope["timestamp"]), envelope["nonce"],
            canonical_payload_bytes(data),
        )
        return envelope

    def _publish(self, envelope, kind="telemetry", device_code=DEVICE_CODE, tenant_id=None):
        topic = f"{mqtt_ingest_service.MQTT_TOPIC_PREFIX}/{tenant_id or self.tenant_id}/{device_code}/{kind}"
        return mqtt_ingest_service.handle_message(
            topic, json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        )

    def _rows(self):
        db = SessionLocal()
        try:
            return db.query(DeviceMessage).order_by(DeviceMessage.id.asc()).all()
        finally:
            db.close()

    # ---------------- 幂等键 ----------------

    def test_message_id_prefers_device_supplied_value(self):
        self.assertEqual(inbox.build_message_id("D1", {"message_id": "abc", "nonce": "n1"}), "abc")

    def test_message_id_falls_back_to_device_and_nonce(self):
        self.assertEqual(inbox.build_message_id("D1", {"nonce": "n1"}), "D1:n1")

    def test_message_id_falls_back_to_content_hash(self):
        first = inbox.build_message_id("D1", {"timestamp": 1, "data": {"a": 1}})
        second = inbox.build_message_id("D1", {"timestamp": 1, "data": {"a": 1}})
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("D1:"))

    # ---------------- 投递与去重 ----------------

    def test_mqtt_publish_enqueues_without_blocking(self):
        result = self._publish(self._envelope({"temperature": 26.0}))
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["queued"])
        self.assertEqual(result["kind"], "telemetry")

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, inbox.STATUS_PENDING)
        self.assertEqual(rows[0].source, "mqtt")
        self.assertEqual(rows[0].device_code, DEVICE_CODE)

    def test_same_nonce_is_rejected_as_replay(self):
        """同一信封再投一次属于重放，由防重放机制直接拒绝（第一层）。"""
        envelope = self._envelope({"temperature": 26.0})
        self.assertTrue(self._publish(envelope)["ok"])
        replay = self._publish(envelope)
        self.assertFalse(replay["ok"])
        self.assertTrue(replay.get("reason"))
        self.assertEqual(len(self._rows()), 1, "重放不应产生第二条记录")

    def test_duplicate_delivery_is_ignored(self):
        """设备换了新 nonce 但业务消息相同（同一 message_id）时，收件箱只处理一次（第二层）。

        MQTT QoS1 在 ack 丢失时会重投；设备侧重试也可能换 nonce。
        没有这一层就会重复产生告警与工单。
        """
        first_envelope = self._envelope({"temperature": 26.0}, message_id="MSG-DUP-1")
        retry_envelope = self._envelope({"temperature": 26.0}, message_id="MSG-DUP-1")
        self.assertNotEqual(first_envelope["nonce"], retry_envelope["nonce"])

        first = self._publish(first_envelope)
        second = self._publish(retry_envelope)

        self.assertTrue(first["ok"], first)
        self.assertFalse(first.get("duplicate"))
        self.assertTrue(second["ok"], second)
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["message_id"], "MSG-DUP-1")

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(mqtt_ingest_service.mqtt_stats()["duplicated"], 1)

        db = SessionLocal()
        try:
            from database import BackgroundTask

            tasks = db.query(BackgroundTask).filter(
                BackgroundTask.task_type == "device_message"
            ).count()
        finally:
            db.close()
        self.assertEqual(tasks, 1, "重复投递不应产生第二个任务")

    def test_worker_processes_message_and_writes_telemetry(self):
        before = self._telemetry_count()
        self._publish(self._envelope({"temperature": 26.5, "battery_level": 88}))

        asyncio_run(process_pending_once())

        rows = self._rows()
        self.assertEqual(rows[0].status, inbox.STATUS_PROCESSED)
        self.assertTrue(rows[0].processed_at)
        self.assertGreater(self._telemetry_count(), before, "业务处理应真正落库遥测数据")

    def test_handler_is_idempotent_on_replay(self):
        self._publish(self._envelope({"temperature": 27.0}))
        asyncio_run(process_pending_once())
        after_first = self._telemetry_count()

        db = SessionLocal()
        try:
            message_id = db.query(DeviceMessage).order_by(DeviceMessage.id.asc()).first().message_id
            # 手工再入队一次同一消息
            enqueue(db, task_type="device_message", payload={"message_id": message_id}, max_attempts=1)
        finally:
            db.close()
        asyncio_run(process_pending_once())

        self.assertEqual(self._rows()[0].status, inbox.STATUS_PROCESSED)
        self.assertEqual(self._telemetry_count(), after_first, "重复处理不应重复写入")

    def test_unknown_device_goes_to_dead_letter(self):
        db = SessionLocal()
        try:
            row = DeviceMessage(
                tenant_id=self.tenant_id, message_id="DEAD-1", device_code="NOT-EXIST-DEV",
                kind="telemetry", source="mqtt", payload={"temperature": 1}, status=inbox.STATUS_PENDING,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            enqueue(db, task_type="device_message", payload={"message_id": "DEAD-1"}, max_attempts=3)
        finally:
            db.close()

        asyncio_run(process_pending_once())

        db = SessionLocal()
        try:
            reloaded = db.query(DeviceMessage).filter(DeviceMessage.message_id == "DEAD-1").first()
            self.assertEqual(reloaded.status, inbox.STATUS_DEAD)
            self.assertIn("设备不存在", reloaded.error)
        finally:
            db.close()

    def test_unsupported_kind_goes_to_dead_letter(self):
        db = SessionLocal()
        try:
            db.add(DeviceMessage(
                tenant_id=self.tenant_id, message_id="DEAD-2", device_code=DEVICE_CODE,
                kind="unknown_kind", source="mqtt", payload={}, status=inbox.STATUS_PENDING,
            ))
            db.commit()
            enqueue(db, task_type="device_message", payload={"message_id": "DEAD-2"}, max_attempts=3)
        finally:
            db.close()

        asyncio_run(process_pending_once())

        db = SessionLocal()
        try:
            row = db.query(DeviceMessage).filter(DeviceMessage.message_id == "DEAD-2").first()
            self.assertEqual(row.status, inbox.STATUS_DEAD)
            self.assertIn("不支持的接入类型", row.error)
        finally:
            db.close()

    # ---------------- 接口 ----------------

    def test_list_and_stats_endpoints(self):
        self._publish(self._envelope({"temperature": 26.0}))

        listing = self.client.get("/api/device-messages", headers=self.headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        items = listing.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "pending")

        stats = self.client.get("/api/device-messages/stats", headers=self.headers)
        self.assertEqual(stats.status_code, 200, stats.text)
        self.assertEqual(stats.json()["by_status"]["pending"], 1)

        filtered = self.client.get(
            "/api/device-messages", params={"status": "processed"}, headers=self.headers
        ).json()
        self.assertEqual(filtered["items"], [])

    def test_replay_endpoint_requeues_dead_letter(self):
        db = SessionLocal()
        try:
            row = inbox.DeviceMessage(
                tenant_id=self.tenant_id, message_id="REPLAY-1", device_id=self.device_id,
                device_code=DEVICE_CODE, kind="telemetry", source="mqtt",
                payload={"temperature": 28.0}, status=inbox.STATUS_DEAD, error="boom",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            row_id = row.id
        finally:
            db.close()

        resp = self.client.post(f"/api/device-messages/{row_id}/replay", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["task_id"])

        db = SessionLocal()
        try:
            row = db.query(DeviceMessage).filter(DeviceMessage.id == row_id).first()
            self.assertEqual(row.status, inbox.STATUS_PENDING)
            self.assertEqual(row.error, "")
        finally:
            db.close()

    def test_replay_rejects_processed_message(self):
        self._publish(self._envelope({"temperature": 26.0}))
        asyncio_run(process_pending_once())
        row_id = self._rows()[0].id

        resp = self.client.post(f"/api/device-messages/{row_id}/replay", headers=self.headers)
        self.assertEqual(resp.status_code, 409)

    def test_replay_unknown_message_returns_404(self):
        resp = self.client.post("/api/device-messages/999999/replay", headers=self.headers)
        self.assertEqual(resp.status_code, 404)

    def test_tenant_isolation(self):
        self._publish(self._envelope({"temperature": 26.0}))
        db = SessionLocal()
        try:
            other = inbox.list_messages(db, self.other_tenant_id)
        finally:
            db.close()
        self.assertEqual(other, [])

    def _telemetry_count(self):
        db = SessionLocal()
        try:
            return db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == self.device_id).count()
        finally:
            db.close()


class TestStorageBackend(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self._original = {
            "STORAGE_BACKEND": storage.STORAGE_BACKEND,
            "S3_ENDPOINT": storage.S3_ENDPOINT,
            "S3_BUCKET": storage.S3_BUCKET,
            "S3_REGION": storage.S3_REGION,
            "S3_ACCESS_KEY": storage.S3_ACCESS_KEY,
            "S3_SECRET_KEY": storage.S3_SECRET_KEY,
            "S3_PREFIX": storage.S3_PREFIX,
            "S3_PATH_STYLE": storage.S3_PATH_STYLE,
        }

    def tearDown(self):
        for key, value in self._original.items():
            setattr(storage, key, value)

    def _enable_fake_s3(self):
        storage.STORAGE_BACKEND = "s3"
        storage.S3_ENDPOINT = "http://minio.local:9000"
        storage.S3_BUCKET = "fire-ai-bucket"
        storage.S3_REGION = "cn-north-1"
        storage.S3_ACCESS_KEY = "AKIDEXAMPLE"
        storage.S3_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
        storage.S3_PREFIX = "fire-ai"
        storage.S3_PATH_STYLE = True

    # ---------------- 本地 ----------------

    def test_local_write_read_delete(self):
        key = f"_test/{uuid.uuid4().hex}.txt"
        path = storage.put(key, b"hello")
        try:
            self.assertTrue(path.is_file())
            self.assertEqual(storage.local_path(key).read_bytes(), b"hello")
            self.assertIsNotNone(storage.materialize(key))
            self.assertEqual(storage.read_bytes(key), b"hello")
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)

    def test_missing_file_returns_none(self):
        self.assertIsNone(storage.materialize(f"_test/{uuid.uuid4().hex}.nope"))
        self.assertEqual(storage.describe()["object_storage_enabled"], False)

    def test_s3_backend_without_config_falls_back_to_local(self):
        storage.STORAGE_BACKEND = "s3"
        storage.S3_ENDPOINT = ""
        self.assertFalse(storage.s3_enabled())
        described = storage.describe()
        self.assertFalse(described["object_storage_enabled"])
        self.assertIn("S3_ENDPOINT", described["missing_config"])

    # ---------------- SigV4 ----------------

    def test_signing_key_derivation_is_deterministic(self):
        first = storage.derive_signing_key("secret", "20260101", "cn-north-1")
        second = storage.derive_signing_key("secret", "20260101", "cn-north-1")
        third = storage.derive_signing_key("secret", "20260102", "cn-north-1")
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(len(first), 32)

    def test_canonical_request_structure(self):
        request, signed_headers = storage.canonical_request(
            "PUT", "/bucket/key.txt", {},
            {"Host": "minio.local:9000", "X-Amz-Date": "20260101T000000Z",
             "X-Amz-Content-Sha256": "abc"},
            storage.EMPTY_PAYLOAD_HASH,
        )
        self.assertEqual(
            signed_headers, "host;x-amz-content-sha256;x-amz-date",
            "signedHeaders 必须小写并按字典序排列",
        )
        lines = request.split("\n")
        self.assertEqual(lines[0], "PUT")
        self.assertEqual(lines[1], "/bucket/key.txt")
        self.assertEqual(lines[2], "")
        self.assertIn("host:minio.local:9000", request)
        self.assertTrue(request.endswith(storage.EMPTY_PAYLOAD_HASH))

    def test_sign_headers_produces_valid_authorization(self):
        headers = storage.sign_headers(
            method="PUT",
            canonical_uri="/fire-ai-bucket/fire-ai/a.txt",
            query={},
            host="minio.local:9000",
            payload=b"content",
            access_key="AKIDEXAMPLE",
            secret_key="secret",
            region="cn-north-1",
            now=datetime(2026, 1, 1, tzinfo=storage.timezone.utc),
        )
        self.assertEqual(headers["x-amz-date"], "20260101T000000Z")
        self.assertEqual(headers["x-amz-content-sha256"], hashlib.sha256(b"content").hexdigest())
        self.assertTrue(headers["Authorization"].startswith(
            "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20260101/cn-north-1/s3/aws4_request"
        ))
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", headers["Authorization"])
        signature = headers["Authorization"].rsplit("Signature=", 1)[1]
        self.assertEqual(len(signature), 64)
        int(signature, 16)  # 必须是合法 hex

    def test_signature_changes_with_payload(self):
        def _sign(payload):
            return storage.sign_headers(
                method="PUT", canonical_uri="/b/k", query={}, host="h",
                payload=payload, access_key="AK", secret_key="SK", region="r",
                now=datetime(2026, 1, 1, tzinfo=storage.timezone.utc),
            )["Authorization"]

        self.assertNotEqual(_sign(b"a"), _sign(b"b"))

    # ---------------- S3 镜像 ----------------

    def _fake_client(self, captured, responses):
        outer = self

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client_kwargs"] = kwargs

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def request(self, method, url, headers=None, content=None):
                captured.setdefault("calls", []).append(
                    {"method": method, "url": url, "headers": headers or {}, "content": content}
                )
                status, body = responses.get(method, (200, b""))
                return httpx.Response(
                    status_code=status, content=body,
                    request=httpx.Request(method, url),
                )

        return FakeClient

    def test_put_mirrors_to_object_storage(self):
        self._enable_fake_s3()
        captured = {}
        client = self._fake_client(captured, {"PUT": (200, b"")})
        key = f"_test/{uuid.uuid4().hex}.txt"

        with mock.patch("services.storage_service.httpx.Client", client):
            path = storage.put(key, b"payload-bytes")

        try:
            call = captured["calls"][0]
            self.assertEqual(call["method"], "PUT")
            self.assertEqual(call["url"], f"http://minio.local:9000/fire-ai-bucket/fire-ai/{key}")
            self.assertEqual(call["content"], b"payload-bytes")
            self.assertIn("AWS4-HMAC-SHA256", call["headers"]["Authorization"])
            self.assertEqual(
                call["headers"]["x-amz-content-sha256"], hashlib.sha256(b"payload-bytes").hexdigest()
            )
            self.assertTrue(path.is_file(), "本地缓存仍应写入，供本地路径链路使用")
        finally:
            shutil.rmtree(storage.local_path(key).parent, ignore_errors=True)

    def test_materialize_fetches_from_object_storage_when_local_missing(self):
        """模拟请求被负载均衡到另一个实例：本地没有文件，应从对象存储取回。"""
        self._enable_fake_s3()
        captured = {}
        client = self._fake_client(captured, {"GET": (200, b"from-s3")})
        key = f"_test/{uuid.uuid4().hex}.txt"

        with mock.patch("services.storage_service.httpx.Client", client):
            path = storage.materialize(key)

        try:
            self.assertIsNotNone(path)
            self.assertEqual(path.read_bytes(), b"from-s3")
            self.assertEqual(captured["calls"][0]["method"], "GET")
        finally:
            shutil.rmtree(storage.local_path(key).parent, ignore_errors=True)

    def test_object_storage_error_raises_on_put(self):
        self._enable_fake_s3()
        captured = {}
        client = self._fake_client(captured, {"PUT": (403, b"denied")})
        key = f"_test/{uuid.uuid4().hex}.txt"

        with mock.patch("services.storage_service.httpx.Client", client):
            with self.assertRaises(storage.StorageError):
                storage.put(key, b"x")
        shutil.rmtree(storage.local_path(key).parent, ignore_errors=True)

    def test_materialize_returns_none_when_absent_everywhere(self):
        self._enable_fake_s3()
        captured = {}
        client = self._fake_client(captured, {"GET": (404, b"")})
        key = f"_test/{uuid.uuid4().hex}.txt"

        with mock.patch("services.storage_service.httpx.Client", client):
            self.assertIsNone(storage.materialize(key))


class TestUploadWithStorageKey(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def tearDown(self):
        db = SessionLocal()
        try:
            db.query(UploadedFile).filter(UploadedFile.original_name.like("storage-test-%")).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    def test_save_upload_stores_key_derivable_path(self):
        db = SessionLocal()
        try:
            record = uploads.save_upload(
                db, tenant_id=None, category="cad", content=b"dxf-content", ext=".dxf",
                original_name="storage-test-plan.dxf",
            )
        finally:
            db.close()

        try:
            self.assertIn(os.path.abspath(str(uploads.UPLOAD_ROOT)), os.path.abspath(record.file_path))
            key = uploads.storage_key(record)
            self.assertEqual(key, f"cad/{record.filename}")
            self.assertTrue(storage.local_path(key).is_file())

            db = SessionLocal()
            try:
                reloaded = db.query(UploadedFile).filter(UploadedFile.id == record.id).first()
                self.assertIsNotNone(uploads.resolve_upload_path(reloaded))
                uploads.delete_upload(db, None, record.id)
            finally:
                db.close()
            self.assertFalse(storage.local_path(key).is_file(), "删除后本地文件应被清理")
        finally:
            shutil.rmtree(str(uploads.UPLOAD_ROOT / "cad"), ignore_errors=True)

    def test_legacy_absolute_path_still_resolves(self):
        """历史数据仍是绝对路径，必须继续可读。"""
        key = f"_test/{uuid.uuid4().hex}.dxf"
        path = storage.write_local(key, b"legacy")
        db = SessionLocal()
        try:
            record = UploadedFile(
                tenant_id=None, category="cad", filename=path.name,
                original_name="storage-test-legacy.dxf", file_path=str(path),
                media_type="", size_bytes=6, sha256="x",
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            self.assertIsNotNone(uploads.resolve_upload_path(record))
        finally:
            db.close()
            shutil.rmtree(path.parent, ignore_errors=True)


class TestRuntimeLocks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        _cleanup_device_messages()

    def test_mutual_exclusion(self):
        db = SessionLocal()
        try:
            self.assertTrue(locks.acquire(db, "unit-test-lock", owner="instance-a"))
            self.assertFalse(locks.acquire(db, "unit-test-lock", owner="instance-b"))
            # 同一持有者可重入
            self.assertTrue(locks.acquire(db, "unit-test-lock", owner="instance-a"))
        finally:
            db.close()

    def test_expired_lock_can_be_taken_over(self):
        db = SessionLocal()
        try:
            locks.acquire(db, "unit-test-expire", owner="instance-a", ttl_seconds=1)
            db.query(RuntimeLock).filter(RuntimeLock.name == "unit-test-expire").update(
                {RuntimeLock.expires_at: datetime.utcnow() - timedelta(seconds=1)}
            )
            db.commit()
            self.assertTrue(locks.acquire(db, "unit-test-expire", owner="instance-b"))
        finally:
            db.close()

    def test_only_owner_can_release(self):
        db = SessionLocal()
        try:
            locks.acquire(db, "unit-test-release", owner="instance-a")
            locks.release(db, "unit-test-release", owner="instance-b")
            self.assertFalse(locks.acquire(db, "unit-test-release", owner="instance-c"))
            locks.release(db, "unit-test-release", owner="instance-a")
            self.assertTrue(locks.acquire(db, "unit-test-release", owner="instance-c"))
        finally:
            db.close()

    def test_run_exclusive_skips_when_held(self):
        db = SessionLocal()
        try:
            locks.acquire(db, "unit-test-run", owner="other-instance")
        finally:
            db.close()

        calls = []
        result = locks.run_exclusive("unit-test-run", lambda: calls.append(1) or "ran", db=SessionLocal())
        self.assertIsNone(result)
        self.assertEqual(calls, [], "其他实例持锁时不应执行动作")

        # 直接清掉锁（release 只有持有者能调用，这里模拟锁被释放）
        db = SessionLocal()
        try:
            db.query(RuntimeLock).filter(RuntimeLock.name == "unit-test-run").delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

        result = locks.run_exclusive("unit-test-run", lambda: calls.append(2) or "ran", db=SessionLocal())
        self.assertEqual(result, "ran")
        self.assertEqual(calls, [2])

    def test_snapshot_reports_ownership(self):
        db = SessionLocal()
        try:
            locks.acquire(db, "unit-test-snapshot", owner="someone")
            rows = {row["name"]: row for row in locks.snapshot(db)}
            self.assertIn("unit-test-snapshot", rows)
            self.assertEqual(rows["unit-test-snapshot"]["owner"], "someone")
            self.assertFalse(rows["unit-test-snapshot"]["held_by_me"])
        finally:
            db.close()

    def test_instance_id_is_stable(self):
        self.assertEqual(locks.instance_id(), locks.instance_id())
        self.assertTrue(locks.instance_id())


class TestSharedSubscription(unittest.TestCase):

    def test_topics_without_shared_group(self):
        original = mqtt_ingest_service.MQTT_SHARED_GROUP
        mqtt_ingest_service.MQTT_SHARED_GROUP = ""
        try:
            topics = mqtt_ingest_service.subscription_topics()
            self.assertTrue(all(not topic.startswith("$share/") for topic in topics))
        finally:
            mqtt_ingest_service.MQTT_SHARED_GROUP = original

    def test_topics_with_shared_group(self):
        """多实例用共享订阅，broker 在组内只投给一个实例，从源头避免重复消费。"""
        original = mqtt_ingest_service.MQTT_SHARED_GROUP
        mqtt_ingest_service.MQTT_SHARED_GROUP = "fire-ai"
        try:
            topics = mqtt_ingest_service.subscription_topics()
            self.assertTrue(topics)
            self.assertTrue(all(topic.startswith("$share/fire-ai/") for topic in topics))
            self.assertIn("$share/fire-ai/fire/+/+/telemetry", topics)
        finally:
            mqtt_ingest_service.MQTT_SHARED_GROUP = original

    def test_client_id_is_process_unique(self):
        self.assertTrue(mqtt_ingest_service.MQTT_CLIENT_ID.endswith(str(os.getpid())))


class TestDeviceMessageHandlerRegistered(unittest.TestCase):

    def test_handler_registered(self):
        ensure_handlers_loaded()
        self.assertIn("device_message", registered_types())


if __name__ == "__main__":
    unittest.main()