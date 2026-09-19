"""遥测历史分析的时间戳处理测试

`analyze_telemetry_history` 的输入来自客户端 JSON（`POST /api/telemetry/analyze-history`
与 `POST /api/multimodal/interpret-alert` 的 `history` / `telemetry_history` 表单字段），
格式完全不受控。改造前那行过滤会直接抛异常、变成 500：

- 带时区的时间戳（`Z` / `+08:00`）与 naive 的 `datetime.now()` 比较
  -> `TypeError: can't compare offset-naive and offset-aware datetimes`
- 时间戳缺失或不是合法 ISO 串 -> `ValueError: Invalid isoformat string`

本文件把这两条钉住，并验证带偏移的时间戳是**换算**到 UTC 参与窗口判断的
（而不是把偏移丢掉、让时间平白挪几个小时）。
"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    Role,
    SessionLocal,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services.telemetry_analyzer import (
    analyze_telemetry_history,
    parse_timestamp_utc,
)

USERNAME = "telemetry-tester"
PASSWORD = "Test#12345"
ROLE_CODE = "telemetry-tester-role"


class TestParseTimestampUtc(unittest.TestCase):

    def test_naive_iso_is_kept_as_is(self):
        self.assertEqual(
            parse_timestamp_utc("2026-09-16T08:00:00"),
            datetime(2026, 9, 16, 8, 0, 0),
        )

    def test_space_separated_iso_is_accepted(self):
        self.assertEqual(
            parse_timestamp_utc("2026-09-16 08:00:00"),
            datetime(2026, 9, 16, 8, 0, 0),
        )

    def test_utc_suffix_becomes_naive_utc(self):
        for raw in ("2026-09-16T08:00:00Z", "2026-09-16T08:00:00+00:00"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_timestamp_utc(raw), datetime(2026, 9, 16, 8, 0, 0))

    def test_offset_is_converted_to_utc_not_dropped(self):
        """`+08:00` 的 08:00 是 UTC 的 00:00；直接丢掉偏移会平白往后挪 8 小时。"""
        self.assertEqual(
            parse_timestamp_utc("2026-09-16T08:00:00+08:00"),
            datetime(2026, 9, 16, 0, 0, 0),
        )
        self.assertEqual(
            parse_timestamp_utc("2026-09-15T20:00:00-04:00"),
            datetime(2026, 9, 16, 0, 0, 0),
        )

    def test_aware_datetime_object_is_normalized(self):
        aware = datetime(2026, 9, 16, 8, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(parse_timestamp_utc(aware), datetime(2026, 9, 16, 0, 0, 0))

    def test_naive_datetime_object_is_kept(self):
        naive = datetime(2026, 9, 16, 8, 0, 0)
        self.assertEqual(parse_timestamp_utc(naive), naive)

    def test_unparseable_values_return_none(self):
        for value in ("", "   ", "yesterday", None, 123, [], {}, "2026-13-45"):
            with self.subTest(value=value):
                self.assertIsNone(parse_timestamp_utc(value))


class TestAnalyzeTelemetryHistoryTimestamps(unittest.TestCase):

    def _entry(self, timestamp, value=0.1):
        return {"metric": "smoke", "value": value, "unit": "mg/m³", "timestamp": timestamp}

    def test_offset_aware_timestamps_do_not_raise(self):
        """回归：改造前带时区的时间戳会抛 TypeError（500）。"""
        now = datetime.utcnow()
        history = [
            self._entry((now - timedelta(hours=1)).isoformat() + "Z"),
            self._entry((now - timedelta(hours=2)).isoformat() + "+00:00"),
            self._entry((now - timedelta(hours=3)).isoformat() + "+08:00"),
        ]
        result = analyze_telemetry_history("smoke", history)
        self.assertEqual(result["statistics"]["count"], 3)

    def test_missing_or_invalid_timestamp_does_not_raise(self):
        """回归：改造前 `fromisoformat('')` 抛 ValueError（500）。"""
        result = analyze_telemetry_history("smoke", [
            {"metric": "smoke", "value": 0.1},
            self._entry("yesterday"),
            self._entry(""),
        ])
        self.assertEqual(
            result["statistics"]["count"], 3,
            "无法解析时间戳的记录应保留，只是不参与时间过滤",
        )

    def test_offset_timestamp_is_compared_in_utc(self):
        """带偏移的时间戳必须换算后比较，否则边界附近的数据会被误判为「近期」。"""
        window = timedelta(hours=1)
        stale = datetime.utcnow() - timedelta(hours=2)
        # 真实 UTC 时刻在 2 小时前（窗口外），但用 +08:00 书写时墙上时间在未来；
        # 若不换算就会被当成近期数据而错误纳入
        written_as_plus8 = (stale + timedelta(hours=8)).isoformat() + "+08:00"

        result = analyze_telemetry_history("smoke", [self._entry(written_as_plus8)], window)
        self.assertEqual(result["trend"], "stale", "2 小时前的数据不该落进 1 小时窗口")

        # 同一时刻改用 UTC 书写，结论必须一致
        result_utc = analyze_telemetry_history(
            "smoke", [self._entry(stale.isoformat() + "Z")], window
        )
        self.assertEqual(result_utc["trend"], "stale")

    def test_recent_offset_timestamp_is_kept(self):
        window = timedelta(hours=1)
        fresh = datetime.utcnow() - timedelta(minutes=10)
        written_as_plus8 = (fresh + timedelta(hours=8)).isoformat() + "+08:00"

        result = analyze_telemetry_history("smoke", [self._entry(written_as_plus8)], window)
        self.assertEqual(result["statistics"]["count"], 1)
        self.assertNotEqual(result["trend"], "stale")

    def test_entries_outside_window_are_still_filtered(self):
        """原有语义不能丢：窗口外的记录仍然要被剔除。"""
        result = analyze_telemetry_history(
            "smoke",
            [self._entry((datetime.utcnow() - timedelta(days=10)).isoformat() + "Z")],
            timedelta(days=3),
        )
        self.assertEqual(result["trend"], "stale")

    def test_naive_and_aware_timestamps_agree_on_the_same_instant(self):
        """同一时刻的两种写法必须给出相同结论。"""
        instant = datetime.utcnow() - timedelta(days=1)
        aware = instant.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))

        naive_result = analyze_telemetry_history(
            "smoke", [self._entry(instant.isoformat())], timedelta(days=3)
        )
        aware_result = analyze_telemetry_history(
            "smoke", [self._entry(aware.isoformat())], timedelta(days=3)
        )
        self.assertEqual(naive_result["statistics"], aware_result["statistics"])

    def test_empty_history_still_reports_no_data(self):
        self.assertEqual(analyze_telemetry_history("smoke", [])["trend"], "no_data")

    def test_unknown_metric_type_still_reports_unknown(self):
        result = analyze_telemetry_history(
            "no_such_metric", [self._entry(datetime.utcnow().isoformat())]
        )
        self.assertEqual(result["trend"], "unknown")


class TestTelemetryEndpointsAcceptUncontrolledTimestamps(unittest.TestCase):
    """端到端：两类时间戳过去会让接口直接返回 500。

    时间戳由客户端 JSON 提供，两个接口（`/api/telemetry/analyze-history`、
    `/api/multimodal/interpret-alert`）都是无格式约束的表单字段。
    """

    client = None
    headers = {}
    tenant_id = None
    role_id = None
    user_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            role = db.query(Role).filter(Role.role_code == ROLE_CODE).first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code=ROLE_CODE,
                            role_name="遥测分析测试", permissions=json.dumps(["*"]))
                db.add(role)
                db.commit()
                db.refresh(role)
            cls.role_id = role.id

            user = db.query(User).filter(User.username == USERNAME).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(username=USERNAME, password_hash=hashed, password_salt=salt,
                            real_name="遥测分析测试员", role_id=role.id, status="active",
                            tenant_id=cls.tenant_id)
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.user_id = user.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        resp = cls.client.post("/api/auth/login",
                               data={"username": USERNAME, "password": PASSWORD})
        assert resp.status_code == 200, resp.text
        cls.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            if cls.user_id:
                db.query(User).filter(User.id == cls.user_id).delete(synchronize_session=False)
            if cls.role_id:
                db.query(Role).filter(Role.id == cls.role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _analyze(self, history):
        return self.client.post(
            "/api/telemetry/analyze-history",
            data={"metric_type": "smoke", "history": json.dumps(history), "days": 3},
            headers=self.headers,
        )

    def test_offset_aware_timestamps_return_200(self):
        now = datetime.utcnow()
        resp = self._analyze([
            {"value": 0.1, "timestamp": now.isoformat() + "Z"},
            {"value": 0.2, "timestamp": now.isoformat() + "+08:00"},
            {"value": 0.3, "timestamp": now.isoformat() + "+00:00"},
        ])
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["statistics"]["count"], 3)

    def test_missing_or_invalid_timestamps_return_200(self):
        resp = self._analyze([
            {"value": 0.1},
            {"value": 0.2, "timestamp": ""},
            {"value": 0.3, "timestamp": "not-a-timestamp"},
        ])
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_interpret_alert_endpoint_accepts_offset_timestamps(self):
        now = datetime.utcnow()
        resp = self.client.post(
            "/api/multimodal/interpret-alert",
            data={
                "device_id": "dev-1",
                "alert_type": "smoke",
                "telemetry_history": json.dumps([
                    {"value": 0.1, "timestamp": now.isoformat() + "+08:00"},
                ]),
            },
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def _analyze_single(self, timestamp):
        return self.client.post(
            "/api/telemetry/analyze-single",
            data={"metric_type": "smoke", "value": 0.1, "timestamp": timestamp},
            headers=self.headers,
        )

    def test_analyze_single_accepts_uncontrolled_timestamps(self):
        """回归：改造前 `datetime.fromisoformat(timestamp)` 对非法输入抛 ValueError（500）。"""
        for raw in ("", "2026-09-16T08:00:00", "2026-09-16T08:00:00Z",
                    "2026-09-16T08:00:00+08:00", "not-a-timestamp"):
            with self.subTest(timestamp=raw):
                resp = self._analyze_single(raw)
                self.assertEqual(resp.status_code, 200, resp.text)
                self.assertEqual(resp.json()["status"], "normal")

    def test_analyze_single_normalizes_offset_to_utc(self):
        """回显的时间戳必须换算成无时区 UTC，与全库时间口径一致。"""
        resp = self._analyze_single("2026-09-16T08:00:00+08:00")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["timestamp"], "2026-09-16T00:00:00")

        utc = self._analyze_single("2026-09-16T08:00:00Z")
        self.assertEqual(utc.json()["timestamp"], "2026-09-16T08:00:00")

    def test_analyze_single_drops_invalid_timestamp_without_failing(self):
        """非法时间戳降级为「未提供」，不影响数值本身的分析结果。"""
        resp = self._analyze_single("yesterday")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsNone(resp.json()["timestamp"])
        self.assertEqual(resp.json()["value"], 0.1)


if __name__ == "__main__":
    unittest.main()
