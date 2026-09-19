"""告警外部通知通道测试

覆盖：通道 CRUD 与密钥加密/脱敏、级别与类型匹配、投递幂等、发送成功/失败、
不可恢复分支、任务处理器的重试与死信、以及 ingest_alert 的自动投递钩子。
"""
import os
import sys
import unittest
import uuid
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import (
    AlertRecord,
    BackgroundTask,
    NotificationChannel,
    NotificationDelivery,
    SessionLocal,
    get_default_tenant_id,
    init_db,
)
from services import alert_notify_service as notify
from services.alert_lifecycle_service import ingest_alert
from services.task_handlers import TASK_TYPE_ALERT_NOTIFY, run_alert_notify
from services.task_queue_service import TaskContext

WEBHOOK_URL = "https://example.com/hooks/fire"
SIGNING_SECRET = "top-secret-signing-key"


class AlertNotifyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
        finally:
            db.close()

    def setUp(self):
        self.db = SessionLocal()
        self.channel_ids = []
        self.alert_codes = []

    def tearDown(self):
        for code in self.alert_codes:
            self.db.query(NotificationDelivery).filter(
                NotificationDelivery.alert_code == code
            ).delete(synchronize_session=False)
            self.db.query(AlertRecord).filter(
                AlertRecord.alert_code == code
            ).delete(synchronize_session=False)
        if self.channel_ids:
            self.db.query(NotificationChannel).filter(
                NotificationChannel.id.in_(self.channel_ids)
            ).delete(synchronize_session=False)
        self.db.query(BackgroundTask).filter(
            BackgroundTask.task_type == TASK_TYPE_ALERT_NOTIFY
        ).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    # ---------------- 辅助 ----------------

    def _create_channel(self, **overrides) -> NotificationChannel:
        payload = {
            "name": f"测试通道-{uuid.uuid4().hex[:6]}",
            "channel_type": "webhook",
            "config": {"url": WEBHOOK_URL, "secret": SIGNING_SECRET},
            "min_severity": "high",
        }
        payload.update(overrides)
        channel = notify.create_channel(self.db, self.tenant_id, payload)
        self.channel_ids.append(channel.id)
        return channel

    def _create_alert(self, *, severity="high", alert_type="smoke_high") -> AlertRecord:
        now = datetime.utcnow()
        code = f"AL-TEST-{uuid.uuid4().hex[:8].upper()}"
        alert = AlertRecord(
            tenant_id=self.tenant_id,
            alert_code=code,
            dedup_key=f"test-{uuid.uuid4().hex}",
            alert_type=alert_type,
            severity=severity,
            status="pending",
            device_code=f"T-{uuid.uuid4().hex[:6]}",
            device_name="测试设备",
            location="测试点位",
            description="通道测试告警",
            repeat_count=1,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        self.alert_codes.append(code)
        return alert

    def _enqueue(self, alert, **kwargs):
        return notify.enqueue_alert_notifications(self.db, alert, **kwargs)

    def _delivery_of(self, alert, channel_id):
        return (
            self.db.query(NotificationDelivery)
            .filter(
                NotificationDelivery.alert_code == alert.alert_code,
                NotificationDelivery.channel_id == channel_id,
            )
            .first()
        )

    # ---------------- 通道配置 ----------------

    def test_create_encrypts_secret_and_masks_it(self):
        channel = self._create_channel()

        stored = channel.config or {}
        self.assertNotEqual(stored.get("secret"), SIGNING_SECRET, "签名密钥不能明文落库")
        self.assertTrue(stored.get("secret", "").startswith("v1:"), "应使用凭证加密格式存储")
        self.assertEqual(stored.get("url"), WEBHOOK_URL, "非密钥字段按原值保存")

        view = notify.serialize(channel)
        self.assertEqual(view["config"]["secret"], notify.MASK)
        self.assertEqual(view["config"]["url"], WEBHOOK_URL)
        self.assertTrue(view["secrets_configured"]["secret"])
        self.assertTrue(view["ready"])
        self.assertEqual(view["channel_type_label"], "通用 Webhook")

    def test_create_validates_required_fields(self):
        with self.assertRaises(ValueError):
            notify.create_channel(self.db, self.tenant_id, {"channel_type": "unknown", "config": {}})
        with self.assertRaises(ValueError):
            notify.create_channel(self.db, self.tenant_id, {"channel_type": "webhook", "config": {}})
        with self.assertRaises(ValueError):
            notify.create_channel(
                self.db, self.tenant_id,
                {"channel_type": "webhook", "config": {"url": "ftp://example.com/x"}},
            )
        with self.assertRaises(ValueError):
            notify.create_channel(
                self.db, self.tenant_id,
                {"channel_type": "email", "config": {"smtp_host": "smtp.example.com", "recipients": "not-an-email"}},
            )
        with self.assertRaises(ValueError):
            notify.create_channel(
                self.db, self.tenant_id,
                {"channel_type": "webhook", "config": {"url": WEBHOOK_URL}, "min_severity": "urgent"},
            )

    def test_update_keeps_secret_when_blank(self):
        channel = self._create_channel()

        updated = notify.update_channel(self.db, channel, {
            "name": "改名后的通道",
            "config": {"url": "https://example.com/hooks/v2", "secret": notify.MASK},
        })

        self.assertEqual(updated.name, "改名后的通道")
        self.assertEqual(updated.config.get("url"), "https://example.com/hooks/v2")
        self.assertEqual(
            notify._decrypt_config(updated.channel_type, updated.config)["secret"],
            SIGNING_SECRET,
            "密钥字段传掩码时应沿用原值",
        )

        replaced = notify.update_channel(self.db, updated, {"config": {"secret": "new-secret-value"}})
        self.assertEqual(
            notify._decrypt_config(replaced.channel_type, replaced.config)["secret"],
            "new-secret-value",
        )

    def test_match_respects_severity_type_and_enabled(self):
        low_channel = self._create_channel(name="低级别也推", min_severity="low")
        high_channel = self._create_channel(name="仅高级别", min_severity="high")
        typed_channel = self._create_channel(name="只看烟感", alert_types=["smoke_high"])
        off_channel = self._create_channel(name="已停用", enabled=False)

        matched_low = notify.match_channels(self.db, self.tenant_id, "low", "smoke_high")
        self.assertIn(low_channel.id, [c.id for c in matched_low])
        self.assertNotIn(high_channel.id, [c.id for c in matched_low])

        matched_high = notify.match_channels(self.db, self.tenant_id, "critical", "temperature_high")
        ids = [c.id for c in matched_high]
        self.assertIn(high_channel.id, ids)
        self.assertNotIn(typed_channel.id, ids, "告警类型不在允许列表内不应匹配")
        self.assertNotIn(off_channel.id, ids, "停用通道不应匹配")

        matched_typed = notify.match_channels(self.db, self.tenant_id, "high", "smoke_high")
        self.assertIn(typed_channel.id, [c.id for c in matched_typed])

    # ---------------- 入队与幂等 ----------------

    def test_enqueue_creates_delivery_and_task(self):
        channel = self._create_channel()
        alert = self._create_alert()

        result = self._enqueue(alert)

        self.assertEqual(result["queued"], 1)
        delivery = self._delivery_of(alert, channel.id)
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, "pending")
        tasks = self.db.query(BackgroundTask).filter(
            BackgroundTask.task_type == TASK_TYPE_ALERT_NOTIFY
        ).all()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].payload.get("delivery_id"), delivery.id)

    def test_enqueue_is_idempotent(self):
        channel = self._create_channel()
        alert = self._create_alert()

        self._enqueue(alert)
        second = self._enqueue(alert)

        self.assertEqual(second["queued"], 0, "同一告警同通道不应重复投递")
        rows = self.db.query(NotificationDelivery).filter(
            NotificationDelivery.alert_code == alert.alert_code
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            self.db.query(BackgroundTask).filter(
                BackgroundTask.task_type == TASK_TYPE_ALERT_NOTIFY
            ).count(),
            1,
        )

    def test_enqueue_without_matching_channel(self):
        # 只建一个「仅严重级别」通道，用低级别告警触发
        self._create_channel(min_severity="critical")
        alert = self._create_alert(severity="low")

        result = self._enqueue(alert)

        self.assertEqual(result["queued"], 0)
        self.assertNotIn("error", result)
        self.assertIsNone(self.db.query(NotificationDelivery).filter(
            NotificationDelivery.alert_code == alert.alert_code
        ).first())

    def test_enqueue_respects_global_switch(self):
        self._create_channel()
        alert = self._create_alert()

        with patch.dict(os.environ, {"ALERT_NOTIFY_ENABLED": "false"}):
            result = self._enqueue(alert)

        self.assertEqual(result["queued"], 0)
        self.assertIn("ALERT_NOTIFY_ENABLED", result["reason"])

    # ---------------- 投递执行 ----------------

    def test_deliver_success_marks_delivery_and_channel(self):
        channel = self._create_channel()
        alert = self._create_alert()
        self._enqueue(alert)
        delivery = self._delivery_of(alert, channel.id)

        with patch.object(notify, "_post_json", return_value='{"errcode":0}') as fake:
            result = notify.deliver(self.db, delivery.id)

        self.assertTrue(result["delivered"])
        self.assertEqual(fake.call_count, 1)
        url, _body, headers = fake.call_args[0]
        self.assertTrue(url.startswith("https://example.com/hooks/fire"))
        self.assertIn("X-Signature", headers, "配置了密钥应带 HMAC 签名头")

        self.db.refresh(delivery)
        self.assertEqual(delivery.status, "success")
        self.assertEqual(delivery.attempts, 1)
        self.db.refresh(channel)
        self.assertIsNotNone(channel.last_success_at)
        self.assertEqual(channel.last_error, "")

    def test_deliver_failure_records_error_and_raises(self):
        channel = self._create_channel()
        alert = self._create_alert()
        self._enqueue(alert)
        delivery = self._delivery_of(alert, channel.id)

        with patch.object(notify, "_post_json", side_effect=notify.NotificationSendError("HTTP 500：boom")):
            with self.assertRaises(notify.NotificationSendError):
                notify.deliver(self.db, delivery.id)

        self.db.refresh(delivery)
        self.assertEqual(delivery.status, "failed")
        self.assertEqual(delivery.attempts, 1)
        self.assertIn("HTTP 500", delivery.error)
        self.db.refresh(channel)
        self.assertIn("HTTP 500", channel.last_error)

    def test_deliver_skips_already_sent(self):
        channel = self._create_channel()
        alert = self._create_alert()
        self._enqueue(alert)
        delivery = self._delivery_of(alert, channel.id)

        with patch.object(notify, "_post_json", return_value="ok"):
            notify.deliver(self.db, delivery.id)
            again = notify.deliver(self.db, delivery.id)

        self.assertTrue(again["skipped"])

    def test_deliver_disabled_channel_is_unrecoverable(self):
        channel = self._create_channel()
        alert = self._create_alert()
        self._enqueue(alert)
        delivery = self._delivery_of(alert, channel.id)

        channel.enabled = False
        self.db.commit()

        result = notify.deliver(self.db, delivery.id)

        self.assertTrue(result["failed"])
        self.assertTrue(result["dead"])
        self.db.refresh(delivery)
        self.assertEqual(delivery.status, "failed")
        self.assertIn("停用", delivery.error)

    def test_post_json_detects_business_errcode(self):
        class FakeResponse:
            status_code = 200
            text = '{"errcode":40001,"errmsg":"invalid webhook url"}'

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, *args, **kwargs):
                return FakeResponse()

        with patch.object(notify.httpx, "Client", lambda **kwargs: FakeClient()):
            with self.assertRaises(notify.NotificationSendError) as ctx:
                notify._post_json("https://example.com/hooks/fire", {"msgtype": "text"}, {})

        self.assertIn("40001", str(ctx.exception))

    def test_email_failure_is_wrapped(self):
        channel = self._create_channel(
            channel_type="email",
            name="邮件通道",
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": "465",
                "smtp_user": "fire@example.com",
                "password": "smtp-password",
                "recipients": "oncall@example.com",
            },
        )
        alert = self._create_alert()

        with patch.object(notify.smtplib, "SMTP_SSL", side_effect=OSError("connection refused")):
            with self.assertRaises(notify.NotificationSendError) as ctx:
                notify.send_alert(channel, alert)

        self.assertIn("SMTP", str(ctx.exception))

    # ---------------- 任务处理器 ----------------

    def test_handler_retries_then_dead_on_last_attempt(self):
        channel = self._create_channel()
        alert = self._create_alert()
        self._enqueue(alert)
        delivery = self._delivery_of(alert, channel.id)

        with patch.object(notify, "_post_json", side_effect=notify.NotificationSendError("timeout")):
            retry_ctx = TaskContext(
                task_id="t-retry", task_type=TASK_TYPE_ALERT_NOTIFY,
                payload={"delivery_id": delivery.id}, attempts=1, max_attempts=3,
            )
            with self.assertRaises(notify.NotificationSendError):
                run_alert_notify(retry_ctx)

            dead_ctx = TaskContext(
                task_id="t-dead", task_type=TASK_TYPE_ALERT_NOTIFY,
                payload={"delivery_id": delivery.id}, attempts=3, max_attempts=3,
            )
            result = run_alert_notify(dead_ctx)

        self.assertTrue(result["dead"])
        self.assertEqual(result["delivery_id"], delivery.id)

    def test_handler_requires_delivery_id(self):
        with self.assertRaises(ValueError):
            run_alert_notify(TaskContext(task_id="t-bad", task_type=TASK_TYPE_ALERT_NOTIFY, payload={}))

    # ---------------- 与告警链路的接线 ----------------

    def test_ingest_alert_enqueues_external_notification(self):
        channel = self._create_channel()

        result = ingest_alert(
            self.db,
            tenant_id=self.tenant_id,
            alert_type="smoke_high",
            severity="high",
            description="接线测试：烟感告警",
            device_code=f"HOOK-{uuid.uuid4().hex[:6]}",
            device_name="接线测试设备",
            location="接线测试点位",
        )
        alert = result["alert"]
        self.alert_codes.append(alert.alert_code)

        delivery = self._delivery_of(alert, channel.id)
        self.assertIsNotNone(delivery, "新告警应自动生成外部投递记录")
        task = self.db.query(BackgroundTask).filter(
            BackgroundTask.task_type == TASK_TYPE_ALERT_NOTIFY
        ).first()
        self.assertIsNotNone(task)
        self.assertEqual(task.payload.get("delivery_id"), delivery.id)


if __name__ == "__main__":
    unittest.main()
