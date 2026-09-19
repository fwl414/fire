"""设备遥测扩展（电气/水系统 4 个指标）测试

覆盖：
- 模型与迁移：DeviceTelemetry 的 current/voltage/pressure/remaining_current 4 列
  经 alembic 迁移补齐，且 downgrade 能干净回退（可逆）
- 落库：设备上报这 4 个指标后真的写进时序表（此前只进告警上下文、不入表）
- 查询：GET /api/telemetry/latest 需登录、按设备类型取最新值并附阈值；
  设备从未上报该指标时如实返回 value=null + status=offline，不编数
- 兼容：GET /api/device-telemetry 返回体也带这 4 个字段
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AlertRecord,
    Device,
    DeviceTelemetry,
    FaultTicket,
    Role,
    SessionLocal,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import db_migration_service as migration
from services.device_ingest_service import ingest_telemetry
from services.telemetry_analyzer import get_latest_telemetry_by_device_type

USERNAME = "telemetry-ext-tester"
PASSWORD = "Test#12345"
# 用独特设备类型，避免与演示数据（"配电箱"/"消火栓"）互相污染断言
DEVICE_TYPE = "遥测扩展测试配电箱"
DEVICE_CODE = "AITEST-TELE-001"

NEW_COLUMNS = ["current", "voltage", "pressure", "remaining_current"]


class TestTelemetryColumnsMigration(unittest.TestCase):
    """4 个新列必须由迁移补齐，且可回退——发布流程依赖 upgrade/downgrade 成对可用。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "telemetry.db"
        self.url = f"sqlite:///{self.path}"
        self.engine = create_engine(self.url)
        self._patches = [
            mock.patch.object(migration, "DATABASE_URL", self.url),
            mock.patch.object(migration, "engine", self.engine),
        ]
        for patch in self._patches:
            patch.start()

    def tearDown(self):
        for patch in self._patches:
            patch.stop()
        self.engine.dispose()
        self._tmp.cleanup()

    def _columns(self):
        return {col["name"] for col in inspect(self.engine).get_columns("device_telemetry")}

    def test_migration_adds_four_columns(self):
        migration.run_migrations()
        columns = self._columns()
        for name in NEW_COLUMNS:
            self.assertIn(name, columns, f"迁移没有补上 {name} 列")

    def test_downgrade_removes_four_columns(self):
        from alembic import command

        migration.run_migrations()
        self.assertIn("remaining_current", self._columns())

        # 回退到基线（init schema）：把遥测列迁移连同其后的迁移一起撤掉。
        # 不能用 "-1"——那只回退最新的一条迁移，head 往后追加迁移后就不再是这一条了。
        command.downgrade(migration.alembic_config(), "7dbc18758246")
        columns = self._columns()
        for name in NEW_COLUMNS:
            self.assertNotIn(name, columns, f"downgrade 之后 {name} 列仍然存在")

    def test_columns_are_nullable(self):
        """老数据行不存在这 4 个值，列必须可空，否则老库升级时会失败。"""
        migration.run_migrations()
        nullable = {col["name"]: col["nullable"] for col in inspect(self.engine).get_columns("device_telemetry")}
        for name in NEW_COLUMNS:
            self.assertTrue(nullable[name], f"{name} 应为可空列")


class TestTelemetryPersistence(unittest.TestCase):
    """硬件上报的 4 个指标必须真落时序表，而不只是进告警上下文。"""

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            device = db.query(Device).filter(Device.device_code == DEVICE_CODE).first()
            if not device:
                device = Device(
                    tenant_id=cls.tenant_id,
                    device_code=DEVICE_CODE,
                    device_name="遥测扩展测试设备",
                    device_type=DEVICE_TYPE,
                    location="遥测测试区域",
                    status="正常",
                )
                db.add(device)
                db.commit()
                db.refresh(device)
            cls.device_id = device.id
        finally:
            db.close()

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
                FaultTicket.title.like("%遥测测试区域%"),
            ).delete(synchronize_session=False)
            db.query(DeviceTelemetry).filter(
                DeviceTelemetry.device_id == cls.device_id
            ).delete(synchronize_session=False)
            db.query(Device).filter(Device.device_code == DEVICE_CODE).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == self.device_id).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    def test_four_metrics_are_persisted(self):
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == self.device_id).first()
            ingest_telemetry(
                db,
                device,
                {
                    "remaining_current": 120.5,
                    "current": 15.5,
                    "voltage": 220.0,
                    "pressure": 0.45,
                },
                source="http",
            )
            row = (
                db.query(DeviceTelemetry)
                .filter(DeviceTelemetry.device_id == self.device_id)
                .order_by(DeviceTelemetry.id.desc())
                .first()
            )
            self.assertIsNotNone(row)
            self.assertAlmostEqual(row.remaining_current, 120.5)
            self.assertAlmostEqual(row.current, 15.5)
            self.assertAlmostEqual(row.voltage, 220.0)
            self.assertAlmostEqual(row.pressure, 0.45)
        finally:
            db.close()

    def test_latest_query_reads_back_persisted_value(self):
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == self.device_id).first()
            ingest_telemetry(db, device, {"remaining_current": 88.0}, source="http")
            payload = get_latest_telemetry_by_device_type(
                db, tenant_id=self.tenant_id, device_type=DEVICE_TYPE, metric="remaining_current"
            )
            self.assertEqual(len(payload["items"]), 1)
            item = payload["items"][0]
            self.assertAlmostEqual(item["value"], 88.0)
            self.assertEqual(item["unit"], "mA")
            self.assertEqual(item["status"], "normal")
            self.assertEqual(payload["thresholds"]["alarm_threshold"], 1000)
        finally:
            db.close()

    def test_device_without_metric_reports_offline_not_fabricated(self):
        """只上报过电流的设备，查剩余电流时应显示离线，而不是编一个数。"""
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == self.device_id).first()
            ingest_telemetry(db, device, {"voltage": 221.0}, source="http")
            payload = get_latest_telemetry_by_device_type(
                db, tenant_id=self.tenant_id, device_type=DEVICE_TYPE, metric="remaining_current"
            )
            item = payload["items"][0]
            self.assertIsNone(item["value"])
            self.assertEqual(item["status"], "offline")
            self.assertIsNone(item["update_time"])
        finally:
            db.close()

    def test_unknown_metric_returns_empty(self):
        db = SessionLocal()
        try:
            payload = get_latest_telemetry_by_device_type(
                db, tenant_id=self.tenant_id, device_type=DEVICE_TYPE, metric="不存在的指标"
            )
            self.assertEqual(payload["items"], [])
            self.assertEqual(payload["thresholds"], {})
        finally:
            db.close()

    def test_unknown_device_type_returns_empty(self):
        db = SessionLocal()
        try:
            payload = get_latest_telemetry_by_device_type(
                db, tenant_id=self.tenant_id, device_type="不存在的设备类型", metric="remaining_current"
            )
            self.assertEqual(payload["items"], [])
            self.assertEqual(payload["metric"], "remaining_current")
        finally:
            db.close()


class TestTelemetryApi(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None
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
                    real_name="遥测扩展测试员",
                    role_id=role_id,
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
        resp = cls.client.post("/api/auth/login", data={"username": USERNAME, "password": PASSWORD})
        assert resp.status_code == 200, f"登录失败: {resp.text}"
        cls.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            if cls.created_user_id:
                db.query(User).filter(User.id == cls.created_user_id).delete(synchronize_session=False)
            if cls.created_role_id:
                db.query(Role).filter(Role.id == cls.created_role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def test_latest_requires_login(self):
        resp = self.client.get(
            "/api/telemetry/latest", params={"device_type": DEVICE_TYPE, "metric": "remaining_current"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_latest_returns_items_and_thresholds(self):
        resp = self.client.get(
            "/api/telemetry/latest",
            params={"device_type": DEVICE_TYPE, "metric": "remaining_current"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["metric"], "remaining_current")
        self.assertEqual(body["unit"], "mA")
        self.assertEqual(body["thresholds"]["warning_threshold"], 500)
        self.assertIsInstance(body["items"], list)

    def test_latest_rejects_missing_params(self):
        """两个查询参数都是必填：缺了要 422，而不是悄悄返回全量数据。"""
        resp = self.client.get("/api/telemetry/latest", headers=self.headers)
        self.assertEqual(resp.status_code, 422)

    def test_device_telemetry_list_exposes_new_columns(self):
        resp = self.client.get("/api/device-telemetry", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()
        self.assertIsInstance(rows, list)
        if rows:
            for name in NEW_COLUMNS:
                self.assertIn(name, rows[0], f"列表接口未暴露 {name} 字段")


if __name__ == "__main__":
    unittest.main()
