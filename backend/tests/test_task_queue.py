"""后台任务队列测试

覆盖：
- 入队 / 抢占式领取 / 租约续期 / 进度上报 / 成功与失败收尾
- 取消语义（取消后不再被成功收尾覆盖）、失败重试入队
- 租约过期回收（未达重试上限回队列，达上限标记失败）
- 处理器注册表：未注册类型与处理器抛异常都要把任务标记为失败而不是静默丢失
- 批量巡检：从「同步端点里调 create_task 必崩」修好，能真正入队并被执行
- 报表异步导出：任务完成后能拿到归档产物
- worker 生命周期与指标暴露
"""
import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    BackgroundTask,
    ReportArtifact,
    Role,
    SessionLocal,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import batch_inspection_service, task_queue_service as queue
from services.task_worker_service import (
    ensure_handlers_loaded,
    process_pending_once,
    start_worker,
    stop_worker,
    worker_stats,
)

TEST_USERNAME = "task-queue-tester"
TEST_PASSWORD = "Test#12345"
TEST_ROLE_CODE = "task-queue-operator"
LIMITED_ROLE_CODE = "task-queue-limited"
LIMITED_USERNAME = "task-queue-limited-user"

# 运维角色：任务中心 + 批量巡检；受限角色只有 records:view，用于验证 403
OPERATOR_PERMISSIONS = ["system:tasks", "batch:view", "batch:create"]
LIMITED_PERMISSIONS = ["records:view"]

TASK_TYPE = "queue_unit_test"


def _purge_queue():
    db = SessionLocal()
    try:
        db.query(BackgroundTask).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _snapshot(task_id: str) -> dict:
    db = SessionLocal()
    try:
        task = db.query(BackgroundTask).filter(BackgroundTask.task_id == task_id).first()
        return queue.serialize(task, include_payload=True, include_result=True) if task else {}
    finally:
        db.close()


class TestTaskQueueCore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        _purge_queue()

    def _enqueue(self, **kwargs):
        db = SessionLocal()
        try:
            return queue.enqueue(db, task_type=kwargs.pop("task_type", TASK_TYPE), **kwargs)
        finally:
            db.close()

    def test_enqueue_creates_pending_task(self):
        task = self._enqueue(task_name="单元测试任务", total_items=3, payload={"a": 1})
        self.assertTrue(task.task_id.startswith("QUEU"))
        self.assertEqual(task.status, queue.STATUS_PENDING)
        self.assertEqual(task.total_items, 3)
        self.assertEqual(task.payload, {"a": 1})
        self.assertEqual(task.max_attempts, 1)

    def test_enqueue_requires_task_type(self):
        db = SessionLocal()
        try:
            with self.assertRaises(queue.TaskQueueError):
                queue.enqueue(db, task_type="")
        finally:
            db.close()

    def test_claim_marks_running_and_sets_lease(self):
        task = self._enqueue()
        db = SessionLocal()
        try:
            claimed = queue.claim_next(db, "worker-a")
        finally:
            db.close()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["task_id"], task.task_id)
        self.assertEqual(claimed["status"], queue.STATUS_RUNNING)
        self.assertEqual(claimed["attempts"], 1)
        self.assertEqual(claimed["lease_owner"], "worker-a")
        self.assertTrue(claimed["started_at"])

    def test_second_claim_returns_none(self):
        """抢占式领取：同一任务不会被领两次（多 worker 并发时不会重复执行）。"""
        self._enqueue()
        db = SessionLocal()
        try:
            first = queue.claim_next(db, "worker-a")
            second = queue.claim_next(db, "worker-b")
        finally:
            db.close()
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_claim_on_empty_queue(self):
        db = SessionLocal()
        try:
            self.assertIsNone(queue.claim_next(db, "worker-a"))
        finally:
            db.close()

    def test_claim_respects_priority(self):
        low = self._enqueue(task_name="低优先级", priority=0)
        high = self._enqueue(task_name="高优先级", priority=10)
        db = SessionLocal()
        try:
            claimed = queue.claim_next(db, "worker-a")
        finally:
            db.close()
        self.assertEqual(claimed["task_id"], high.task_id)
        self.assertNotEqual(claimed["task_id"], low.task_id)

    def test_progress_updates_and_merges_extra(self):
        task = self._enqueue(total_items=4)
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.update_progress(
                db, task.task_id, done=2, message="已完成一半",
                extra={"high_risk_count": 1, "current_item": "1层大厅"},
            )
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["done_items"], 2)
        self.assertEqual(data["progress"], 50)
        self.assertEqual(data["progress_message"], "已完成一半")
        self.assertEqual(data["result"]["high_risk_count"], 1)
        self.assertEqual(data["result"]["current_item"], "1层大厅")

    def test_finish_success_sets_result(self):
        task = self._enqueue()
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.finish_success(db, task.task_id, {"answer": 42})
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_SUCCESS)
        self.assertEqual(data["progress"], 100)
        self.assertEqual(data["result"]["answer"], 42)
        self.assertEqual(data["lease_owner"], "")

    def test_finish_failed_keeps_error(self):
        task = self._enqueue()
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.finish_failed(db, task.task_id, "ValueError: boom")
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_FAILED)
        self.assertIn("boom", data["error"])

    def test_cancel_wins_over_success(self):
        """任务被取消后不得再被成功收尾覆盖。"""
        task = self._enqueue()
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            self.assertTrue(queue.request_cancel(db, task.task_id))
            self.assertFalse(queue.finish_success(db, task.task_id, {"late": True}))
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_CANCELED)
        self.assertEqual(data["result"], {})

    def test_cancel_rejects_terminal_task(self):
        task = self._enqueue()
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.finish_success(db, task.task_id, {})
            self.assertFalse(queue.request_cancel(db, task.task_id))
        finally:
            db.close()

    def test_requeue_only_for_failed(self):
        task = self._enqueue()
        db = SessionLocal()
        try:
            self.assertFalse(queue.requeue(db, task.task_id), "pending 任务不需要重试")
            queue.claim_next(db, "worker-a")
            queue.finish_failed(db, task.task_id, "boom")
            self.assertTrue(queue.requeue(db, task.task_id))
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_PENDING)
        self.assertEqual(data["error"], "")
        self.assertEqual(data["attempts"], 1, "重试不清空历史尝试次数")

    def test_extend_lease_requires_current_owner(self):
        task = self._enqueue()
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            self.assertFalse(queue.extend_lease(db, task.task_id, "worker-b"))
            self.assertTrue(queue.extend_lease(db, task.task_id, "worker-a"))
        finally:
            db.close()

    def test_recover_expired_requeues_when_retry_left(self):
        task = self._enqueue(max_attempts=3)
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            # 手动把租约改成已过期，模拟 worker 崩溃
            db.query(BackgroundTask).filter(BackgroundTask.task_id == task.task_id).update(
                {BackgroundTask.lease_expires_at: datetime.utcnow() - timedelta(minutes=1)}
            )
            db.commit()
            self.assertEqual(queue.recover_expired(db), 1)
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_PENDING)
        self.assertIn("失联", data["progress_message"])

    def test_recover_expired_fails_when_retry_exhausted(self):
        task = self._enqueue(max_attempts=1)
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            db.query(BackgroundTask).filter(BackgroundTask.task_id == task.task_id).update(
                {BackgroundTask.lease_expires_at: datetime.utcnow() - timedelta(minutes=1)}
            )
            db.commit()
            self.assertEqual(queue.recover_expired(db), 1)
        finally:
            db.close()

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_FAILED)
        self.assertIn("最大重试次数", data["error"])

    def test_list_and_stats(self):
        self._enqueue(task_name="统计用任务A")
        done = self._enqueue(task_name="统计用任务B")
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.finish_success(db, done.task_id, {})

            listing = queue.list_tasks(db, None, status=queue.STATUS_SUCCESS, task_type=TASK_TYPE)
            stats = queue.stats(db, None)
            pending = queue.pending_count()
        finally:
            db.close()

        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["task_id"], done.task_id)
        self.assertEqual(stats["by_status"][queue.STATUS_SUCCESS], 1)
        self.assertEqual(stats["by_type"][0]["task_type"], TASK_TYPE)
        self.assertEqual(pending, 1, "只剩另一个未完成的任务计入待处理")


class TestTaskHandlers(unittest.TestCase):
    """通过 worker 的领取-执行链路验证处理器行为。"""

    @classmethod
    def setUpClass(cls):
        init_db()
        ensure_handlers_loaded()

    def setUp(self):
        _purge_queue()

    def _enqueue(self, task_type: str, payload=None, total_items=0, max_attempts=1):
        db = SessionLocal()
        try:
            return queue.enqueue(
                db, task_type=task_type, payload=payload or {},
                total_items=total_items, max_attempts=max_attempts,
            )
        finally:
            db.close()

    def test_handlers_are_registered(self):
        self.assertIn(batch_inspection_service.TASK_TYPE, queue.registered_types())
        self.assertIn("report_export", queue.registered_types())

    def test_unknown_task_type_fails_loudly(self):
        task = self._enqueue("no_such_handler")
        asyncio.run(process_pending_once())

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_FAILED)
        self.assertIn("没有注册任务类型", data["error"])

    def test_batch_inspection_runs_real_rule_analysis(self):
        """巡检结果来自规则引擎的真实抽取，而不是随机数。"""
        items = [
            {"id": "I1", "location": "1层消防通道", "description": "消防通道堵塞，堆放纸箱"},
            {"id": "I2", "location": "3层配电室", "description": "配电箱周围堆物，电线杂乱"},
            {"id": "I3", "location": "屋顶水箱", "description": "屋顶水箱巡检正常"},
        ]
        task = self._enqueue(
            batch_inspection_service.TASK_TYPE,
            payload={"building_name": "测试楼", "inspection_items": items},
            total_items=len(items),
        )

        asyncio.run(process_pending_once())

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_SUCCESS, data.get("error"))
        self.assertEqual(data["progress"], 100)

        result = data["result"]
        self.assertEqual(result["completed_count"], 3)
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual(result["high_risk_count"] + result["medium_risk_count"] + result["low_risk_count"], 3)

        first = result["results"][0]
        self.assertIn("消防通道堵塞", first["hazards"])
        self.assertGreater(first["risk_score"], 0)
        self.assertTrue(first["suggestion"])

    def test_handler_exception_marks_task_failed(self):
        from services.task_queue_service import register_handler

        @register_handler("queue_failing_handler")
        def _boom(ctx):
            raise RuntimeError("处理器内部错误")

        task = self._enqueue("queue_failing_handler")
        asyncio.run(process_pending_once())

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_FAILED)
        self.assertIn("处理器内部错误", data["error"])

    def test_canceled_task_lets_handler_exit_early(self):
        items = [{"id": f"I{i}", "location": f"{i}层", "description": "巡检"} for i in range(5)]
        task = self._enqueue(
            batch_inspection_service.TASK_TYPE,
            payload={"building_name": "测试楼", "inspection_items": items},
            total_items=len(items),
        )
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.request_cancel(db, task.task_id)
        finally:
            db.close()

        handler = queue.get_handler(batch_inspection_service.TASK_TYPE)
        from services.task_queue_service import TaskContext

        ctx = TaskContext(
            task_id=task.task_id,
            task_type=batch_inspection_service.TASK_TYPE,
            payload={"building_name": "测试楼", "inspection_items": items},
            _db_factory=SessionLocal,
        )
        output = handler(ctx)
        self.assertTrue(output.get("canceled"))
        self.assertEqual(output["results"], [], "取消后不应继续产出结果")

    def test_report_export_task_produces_artifact(self):
        task = self._enqueue(
            "report_export",
            payload={"report_type": "inspection", "period": "week", "format": "csv"},
            total_items=3,
        )
        asyncio.run(process_pending_once())

        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_SUCCESS, data.get("error"))
        artifact_id = data["result"]["artifact_id"]
        self.assertTrue(artifact_id)
        self.assertIn(".csv", data["result"]["filename"])

        db = SessionLocal()
        try:
            artifact = db.query(ReportArtifact).filter(ReportArtifact.id == artifact_id).first()
            self.assertIsNotNone(artifact, "报表产物应已归档")
        finally:
            db.close()


class TestBatchInspectionApi(unittest.TestCase):
    """批量巡检接口：修复前该接口必然 500（同步上下文里调用 asyncio.create_task）。"""

    client = None
    headers = {}
    limited_headers = {}
    tenant_id = None
    other_tenant_id = None
    role_id = None
    user_id = None
    limited_role_id = None
    limited_user_id = None
    created = False

    @classmethod
    def setUpClass(cls):
        init_db()
        ensure_handlers_loaded()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            from database import Tenant

            other = db.query(Tenant).filter(Tenant.tenant_code == "task-queue-other").first()
            if not other:
                other = Tenant(tenant_code="task-queue-other", tenant_name="任务隔离租户", status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
            cls.other_tenant_id = other.id

            role = db.query(Role).filter(Role.role_code == TEST_ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=TEST_ROLE_CODE,
                    role_name="任务中心运维",
                    permissions=json.dumps(OPERATOR_PERMISSIONS),
                )
                db.add(role)
                db.commit()
                db.refresh(role)
            elif not set(OPERATOR_PERMISSIONS).issubset(set(json.loads(role.permissions or "[]"))):
                # 角色可能已被其它测试类创建，补齐本类需要的权限码
                role.permissions = json.dumps(OPERATOR_PERMISSIONS)
                db.commit()
            cls.role_id = role.id

            limited = db.query(Role).filter(Role.role_code == LIMITED_ROLE_CODE).first()
            if not limited:
                limited = Role(
                    tenant_id=cls.tenant_id,
                    role_code=LIMITED_ROLE_CODE,
                    role_name="仅查看",
                    permissions=json.dumps(LIMITED_PERMISSIONS),
                )
                db.add(limited)
                db.commit()
                db.refresh(limited)
            cls.limited_role_id = limited.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(
                    username=TEST_USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="任务队列测试员",
                    role_id=role.id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                cls.created = True
            cls.user_id = user.id

            limited_user = db.query(User).filter(User.username == LIMITED_USERNAME).first()
            if not limited_user:
                hashed, salt = hash_password(TEST_PASSWORD)
                limited_user = User(
                    username=LIMITED_USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="受限用户",
                    role_id=limited.id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(limited_user)
                db.commit()
                db.refresh(limited_user)
            cls.limited_user_id = limited_user.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        for attr, username in (("headers", TEST_USERNAME), ("limited_headers", LIMITED_USERNAME)):
            resp = cls.client.post(
                "/api/auth/login",
                data={"username": username, "password": TEST_PASSWORD},
            )
            assert resp.status_code == 200, f"登录失败({username}): {resp.text}"
            setattr(cls, attr, {"Authorization": f"Bearer {resp.json()['access_token']}"})

    @classmethod
    def tearDownClass(cls):
        _purge_queue()
        db = SessionLocal()
        try:
            for user_id in (cls.user_id, cls.limited_user_id):
                if user_id:
                    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            for role_id in (cls.role_id, cls.limited_role_id):
                if role_id:
                    db.query(Role).filter(Role.id == role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        _purge_queue()

    def _create(self, **overrides):
        payload = {
            "task_name": "接口用例批量巡检",
            "building_name": "测试楼",
            "inspection_items": [
                {"id": "I1", "location": "1层消防通道", "description": "消防通道堵塞"},
                {"id": "I2", "location": "2层办公室", "description": "办公室巡检正常"},
            ],
        }
        payload.update(overrides)
        return self.client.post("/api/batch-inspection/create", json=payload, headers=self.headers)

    def test_create_returns_task_id(self):
        """回归守卫：修复前这里是 500 no running event loop。"""
        resp = self._create()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["total_count"], 2)
        self.assertTrue(body["task_id"])

    def test_create_without_items_uses_default_checklist(self):
        resp = self._create(inspection_items=[])
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["total_count"], 10)

    def test_list_detail_and_progress(self):
        task_id = self._create().json()["task_id"]

        listing = self.client.get("/api/batch-inspection/list", headers=self.headers).json()
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["items"][0]["id"], task_id)
        self.assertEqual(listing["items"][0]["status"], "pending")

        detail = self.client.get(f"/api/batch-inspection/{task_id}", headers=self.headers).json()
        self.assertTrue(detail["success"])
        self.assertEqual(detail["total_count"], 2)
        self.assertEqual(len(detail["inspection_items"]), 2)

        progress = self.client.get(
            f"/api/batch-inspection/{task_id}/progress", headers=self.headers
        ).json()
        self.assertTrue(progress["success"])
        self.assertEqual(progress["progress"], 0)
        self.assertEqual(progress["high_risk_count"], 0)

    def test_after_worker_run_status_becomes_completed(self):
        task_id = self._create().json()["task_id"]
        asyncio.run(process_pending_once(task_types=[batch_inspection_service.TASK_TYPE]))

        listing = self.client.get("/api/batch-inspection/list", headers=self.headers).json()
        row = listing["items"][0]
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["completed_count"], 2)

        detail = self.client.get(f"/api/batch-inspection/{task_id}", headers=self.headers).json()
        self.assertEqual(len(detail["results"]), 2)
        self.assertIn("消防通道堵塞", detail["results"][0]["hazards"])

    def test_missing_task_returns_error_payload(self):
        detail = self.client.get("/api/batch-inspection/NOPE", headers=self.headers).json()
        self.assertFalse(detail["success"])
        self.assertEqual(detail["error"], "任务不存在")

    def test_tenant_isolation(self):
        from services.batch_inspection_service import get_batch_task_detail

        task_id = self._create().json()["task_id"]
        db = SessionLocal()
        try:
            other = get_batch_task_detail(db, task_id, tenant_id=self.other_tenant_id)
        finally:
            db.close()
        self.assertFalse(other["success"])

    def test_list_no_longer_fabricates_demo_tasks(self):
        """空队列必须返回 0 条，而不是伪造 3 条演示任务。"""
        listing = self.client.get("/api/batch-inspection/list", headers=self.headers).json()
        self.assertEqual(listing["total"], 0)
        self.assertEqual(listing["items"], [])

    # ---------------- 权限码接线 ----------------

    def test_create_requires_batch_create_permission(self):
        """回归守卫：接线前任何登录用户都能建批量任务，batch:create 形同虚设。"""
        denied = self.client.post(
            "/api/batch-inspection/create",
            json={"task_name": "越权批量巡检", "inspection_items": []},
            headers=self.limited_headers,
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertIn("batch:create", denied.json()["message"])

        allowed = self._create()
        self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_read_endpoints_require_batch_view_permission(self):
        task_id = self._create().json()["task_id"]
        for path in (
            "/api/batch-inspection/list",
            f"/api/batch-inspection/{task_id}",
            f"/api/batch-inspection/{task_id}/progress",
        ):
            with self.subTest(path=path):
                denied = self.client.get(path, headers=self.limited_headers)
                self.assertEqual(denied.status_code, 403, denied.text)
                self.assertIn("batch:view", denied.json()["message"])

                allowed = self.client.get(path, headers=self.headers)
                self.assertEqual(allowed.status_code, 200, allowed.text)


class TestTaskApi(unittest.TestCase):

    client = None
    headers = {}
    limited_headers = {}
    tenant_id = None
    role_id = None
    user_id = None
    limited_role_id = None
    limited_user_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        ensure_handlers_loaded()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

            role = db.query(Role).filter(Role.role_code == TEST_ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=TEST_ROLE_CODE,
                    role_name="任务中心运维",
                    permissions=json.dumps(["system:tasks"]),
                )
                db.add(role)
                db.commit()
                db.refresh(role)
            cls.role_id = role.id

            limited = db.query(Role).filter(Role.role_code == LIMITED_ROLE_CODE).first()
            if not limited:
                limited = Role(
                    tenant_id=cls.tenant_id,
                    role_code=LIMITED_ROLE_CODE,
                    role_name="仅查看",
                    permissions=json.dumps(["records:view"]),
                )
                db.add(limited)
                db.commit()
                db.refresh(limited)
            cls.limited_role_id = limited.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(
                    username=TEST_USERNAME, password_hash=hashed, password_salt=salt,
                    real_name="任务队列测试员", role_id=role.id, status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.user_id = user.id

            limited_user = db.query(User).filter(User.username == LIMITED_USERNAME).first()
            if not limited_user:
                hashed, salt = hash_password(TEST_PASSWORD)
                limited_user = User(
                    username=LIMITED_USERNAME, password_hash=hashed, password_salt=salt,
                    real_name="受限用户", role_id=limited.id, status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(limited_user)
                db.commit()
                db.refresh(limited_user)
            cls.limited_user_id = limited_user.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        for attr, username in (("headers", TEST_USERNAME), ("limited_headers", LIMITED_USERNAME)):
            resp = cls.client.post(
                "/api/auth/login", data={"username": username, "password": TEST_PASSWORD}
            )
            assert resp.status_code == 200, f"登录失败({username}): {resp.text}"
            setattr(cls, attr, {"Authorization": f"Bearer {resp.json()['access_token']}"})

    @classmethod
    def tearDownClass(cls):
        _purge_queue()
        db = SessionLocal()
        try:
            for user_id in (cls.user_id, cls.limited_user_id):
                if user_id:
                    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            for role_id in (cls.role_id, cls.limited_role_id):
                if role_id:
                    db.query(Role).filter(Role.id == role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        _purge_queue()

    def _enqueue_via_api(self, **payload):
        body = {"report_type": "inspection", "period": "week", "format": "csv"}
        body.update(payload)
        return self.client.post("/api/reports/export/tasks", json=body, headers=self.headers)

    def test_endpoints_require_authentication(self):
        for path in ("/api/tasks", "/api/tasks/stats", "/api/tasks/types"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_types_endpoint_lists_registered_handlers(self):
        resp = self.client.get("/api/tasks/types", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        types = resp.json()["items"]
        self.assertIn("batch_inspection", types)
        self.assertIn("report_export", types)

    def test_report_async_export_enqueues_task(self):
        resp = self._enqueue_via_api()
        self.assertEqual(resp.status_code, 200, resp.text)
        task_id = resp.json()["task_id"]

        detail = self.client.get(f"/api/tasks/{task_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(body["task_type"], "report_export")
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["payload"]["report_type"], "inspection")

    def test_report_async_export_rejects_unknown_type(self):
        resp = self._enqueue_via_api(report_type="unknown_type")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("不支持的报表类型", resp.json()["message"])

    def test_list_filter_by_task_type(self):
        self._enqueue_via_api()
        listing = self.client.get(
            "/api/tasks", params={"task_type": "report_export"}, headers=self.headers
        )
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(len(listing.json()["items"]), 1)

        empty = self.client.get(
            "/api/tasks", params={"task_type": "batch_inspection"}, headers=self.headers
        ).json()
        self.assertEqual(empty["items"], [])

    def test_stats_requires_system_tasks_permission(self):
        self.assertEqual(
            self.client.get("/api/tasks/stats", headers=self.limited_headers).status_code, 403
        )
        resp = self.client.get("/api/tasks/stats", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("pending", body["tasks"]["by_status"])
        self.assertIn("worker", body)

    def test_cancel_and_retry_require_permission(self):
        task_id = self._enqueue_via_api().json()["task_id"]
        self.assertEqual(
            self.client.post(f"/api/tasks/{task_id}/cancel", headers=self.limited_headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f"/api/tasks/{task_id}/cancel", headers=self.headers).status_code, 200
        )
        # 已取消的任务不能重试
        retry = self.client.post(f"/api/tasks/{task_id}/retry", headers=self.headers)
        self.assertEqual(retry.status_code, 409)

    def test_retry_failed_task(self):
        task_id = self._enqueue_via_api().json()["task_id"]
        db = SessionLocal()
        try:
            queue.claim_next(db, "worker-a")
            queue.finish_failed(db, task_id, "模拟失败")
        finally:
            db.close()

        resp = self.client.post(f"/api/tasks/{task_id}/retry", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(_snapshot(task_id)["status"], queue.STATUS_PENDING)

    def test_unknown_task_returns_404(self):
        self.assertEqual(self.client.get("/api/tasks/NOPE", headers=self.headers).status_code, 404)

    def test_metrics_expose_queue_state(self):
        self._enqueue_via_api()
        body = self.client.get("/metrics").text
        self.assertIn("fire_ai_background_tasks", body)
        self.assertIn('fire_ai_background_tasks{status="pending"} 1', body)
        self.assertIn("fire_ai_task_worker_running", body)


class TestWorkerLifecycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        ensure_handlers_loaded()

    def test_start_and_stop(self):
        async def _scenario():
            started = start_worker()
            self.assertTrue(started)
            self.assertTrue(worker_stats()["running"])
            self.assertTrue(worker_stats()["worker_id"])
            await stop_worker()
            self.assertFalse(worker_stats()["running"])
            # 重复停止不应报错
            await stop_worker()

        asyncio.run(_scenario())

    def test_worker_consumes_queued_task(self):
        _purge_queue()
        db = SessionLocal()
        try:
            task = queue.enqueue(
                db,
                task_type=batch_inspection_service.TASK_TYPE,
                payload={
                    "building_name": "后台执行楼",
                    "inspection_items": [{"id": "I1", "location": "1层", "description": "消防通道堵塞"}],
                },
                total_items=1,
            )
        finally:
            db.close()

        async def _scenario():
            start_worker()
            try:
                for _ in range(40):  # 最多等 4 秒
                    if _snapshot(task.task_id)["status"] == queue.STATUS_SUCCESS:
                        break
                    await asyncio.sleep(0.1)
            finally:
                await stop_worker()

        asyncio.run(_scenario())
        data = _snapshot(task.task_id)
        self.assertEqual(data["status"], queue.STATUS_SUCCESS, data.get("error"))
        _purge_queue()


if __name__ == "__main__":
    unittest.main()
