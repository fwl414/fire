"""消防培训（培训计划 / 考试场次 / 培训档案）接口测试

覆盖：
- 权限：读要 training:view、写要 training:manage，未登录 401、缺权限 403
- 计划的增删改查与入参校验（空名、进度越界、日期倒序、非法状态与类型）
- 档案的引用校验（plan_id / exam_id 必须同租户存在）
- 删除保护：计划/场次下还有档案时不允许删，避免档案里的引用变成悬空
- 聚合口径：考试参考人数/平均分/及格率、计划实际参训人数都从档案现算，
  且「没成绩」不算进参考人数
- 合格判定：及格线取自关联考试；未考试既不是合格也不是不合格
- CSV 导出：按筛选条件导出全部（不只当前页），带 BOM 与表头
- 租户隔离
"""
import json
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
    Role,
    SessionLocal,
    TrainingExam,
    TrainingPlan,
    TrainingRecord,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import db_migration_service as migration

PASSWORD = "Test#12345"
ADMIN_USER = "training-admin-tester"
VIEWER_USER = "training-viewer-tester"
OUTSIDER_USER = "training-outsider-tester"

MANAGE_ROLE = "training-test-manager"
VIEW_ROLE = "training-test-viewer"
NO_ROLE = "training-test-outsider"


def _ensure_role(db, tenant_id, role_code, permissions):
    role = db.query(Role).filter(Role.role_code == role_code).first()
    if role:
        return role, False
    role = Role(
        tenant_id=tenant_id,
        role_code=role_code,
        role_name=role_code,
        permissions=json.dumps(permissions),
        is_system=False,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role, True


def _ensure_user(db, tenant_id, username, role_id):
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user, False
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
    return user, True


def _login(client, username):
    resp = client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _clear_training(db, tenant_id):
    db.query(TrainingRecord).filter(TrainingRecord.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(TrainingExam).filter(TrainingExam.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(TrainingPlan).filter(TrainingPlan.tenant_id == tenant_id).delete(synchronize_session=False)
    db.commit()


class TestTrainingApi(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            manage_role, created_manage = _ensure_role(
                db, cls.tenant_id, MANAGE_ROLE, ["training:view", "training:manage"]
            )
            viewer_role, created_view = _ensure_role(
                db, cls.tenant_id, VIEW_ROLE, ["training:view"]
            )
            outsider_role, created_none = _ensure_role(
                db, cls.tenant_id, NO_ROLE, ["dashboard:view"]
            )
            _, created_user = _ensure_user(db, cls.tenant_id, ADMIN_USER, manage_role.id)
            _, created_viewer = _ensure_user(db, cls.tenant_id, VIEWER_USER, viewer_role.id)
            _, created_outsider = _ensure_user(db, cls.tenant_id, OUTSIDER_USER, outsider_role.id)

            cls._created = {
                "roles": [r.id for r, created in (
                    (manage_role, created_manage),
                    (viewer_role, created_view),
                    (outsider_role, created_none),
                ) if created],
                "users": [],
            }
            for username, created in (
                (ADMIN_USER, created_user),
                (VIEWER_USER, created_viewer),
                (OUTSIDER_USER, created_outsider),
            ):
                if created:
                    user = db.query(User).filter(User.username == username).first()
                    cls._created["users"].append(user.id)
        finally:
            db.close()

        cls.client = TestClient(main.app)
        cls.headers = _login(cls.client, ADMIN_USER)
        cls.viewer_headers = _login(cls.client, VIEWER_USER)
        cls.outsider_headers = _login(cls.client, OUTSIDER_USER)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            _clear_training(db, cls.tenant_id)
            for user_id in cls._created.get("users", []):
                db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            for role_id in cls._created.get("roles", []):
                db.query(Role).filter(Role.id == role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        db = SessionLocal()
        try:
            _clear_training(db, self.tenant_id)
        finally:
            db.close()

    # ---------------- 工具 ----------------

    def _create_plan(self, **overrides):
        payload = {
            "plan_name": "测试培训计划",
            "plan_type": "综合培训",
            "target": "全体员工",
            "trainer": "张教官",
            "start_date": "2026-03-02",
            "end_date": "2026-03-06",
            "person_count": 10,
            "progress": 0,
            "status": "pending",
        }
        payload.update(overrides)
        resp = self.client.post("/api/training/plans", json=payload, headers=self.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["id"]

    def _create_exam(self, **overrides):
        payload = {
            "title": "测试考试",
            "description": "",
            "duration_minutes": 60,
            "question_count": 50,
            "pass_score": 60,
            "start_time": "2026-03-06 09:00:00",
            "status": "ended",
        }
        payload.update(overrides)
        resp = self.client.post("/api/training/exams", json=payload, headers=self.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["id"]

    def _create_record(self, **overrides):
        payload = {"trainee_name": "测试人员", "department": "安保部", "study_hours": 8}
        payload.update(overrides)
        resp = self.client.post("/api/training/records", json=payload, headers=self.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    # ---------------- 权限 ----------------

    def test_endpoints_require_login(self):
        for path in (
            "/api/training/stats",
            "/api/training/plans",
            "/api/training/exams",
            "/api/training/records",
            "/api/training/records/export",
        ):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_read_requires_training_view(self):
        for path in ("/api/training/stats", "/api/training/plans", "/api/training/records"):
            resp = self.client.get(path, headers=self.outsider_headers)
            self.assertEqual(resp.status_code, 403, path)

    def test_write_requires_training_manage(self):
        cases = [
            ("post", "/api/training/plans", {"plan_name": "无权创建"}),
            ("post", "/api/training/exams", {"title": "无权创建"}),
            ("post", "/api/training/records", {"trainee_name": "无权创建"}),
            ("put", "/api/training/plans/999999", {"progress": 10}),
            ("delete", "/api/training/plans/999999", None),
        ]
        for method, path, body in cases:
            call = getattr(self.client, method)
            resp = call(path, json=body, headers=self.viewer_headers) if body else call(
                path, headers=self.viewer_headers
            )
            self.assertEqual(resp.status_code, 403, f"{method} {path}")

    def test_read_is_allowed_for_training_view(self):
        resp = self.client.get("/api/training/plans", headers=self.viewer_headers)
        self.assertEqual(resp.status_code, 200, resp.text)

    # ---------------- 培训计划 ----------------

    def test_plan_create_and_list_roundtrip(self):
        plan_id = self._create_plan(plan_name="上半年全员培训")
        body = self.client.get("/api/training/plans", headers=self.headers).json()
        self.assertEqual(body["total"], 1)
        item = body["items"][0]
        self.assertEqual(item["id"], plan_id)
        self.assertEqual(item["plan_name"], "上半年全员培训")
        self.assertEqual(item["status"], "pending")
        self.assertEqual(item["status_label"], "未开始")
        self.assertEqual(item["start_date"], "2026-03-02")
        self.assertEqual(item["actual_count"], 0)

    def test_plan_rejects_blank_name(self):
        resp = self.client.post(
            "/api/training/plans", json={"plan_name": "   "}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("计划名称", resp.json()["message"])

    def test_plan_rejects_invalid_enum_and_range(self):
        cases = [
            ({"plan_name": "x", "status": "finished"}, "计划状态"),
            ({"plan_name": "x", "plan_type": "野餐培训"}, "培训类型"),
            ({"plan_name": "x", "progress": 120}, "进度"),
            ({"plan_name": "x", "person_count": -1}, "计划人数"),
            ({"plan_name": "x", "start_date": "2026-03-10", "end_date": "2026-03-01"}, "结束日期"),
            ({"plan_name": "x", "start_date": "2026/03/10"}, "开始日期"),
        ]
        for payload, keyword in cases:
            resp = self.client.post("/api/training/plans", json=payload, headers=self.headers)
            self.assertEqual(resp.status_code, 400, payload)
            self.assertIn(keyword, resp.json()["message"], payload)

    def test_plan_update_partial_and_date_guard(self):
        plan_id = self._create_plan(start_date="2026-03-10", end_date="2026-03-20")
        # 只改进度：不影响日期
        resp = self.client.put(
            f"/api/training/plans/{plan_id}", json={"progress": 60, "status": "ongoing"}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        item = resp.json()["item"]
        self.assertEqual(item["progress"], 60)
        self.assertEqual(item["status_label"], "进行中")
        self.assertEqual(item["start_date"], "2026-03-10")

        # 只改结束日期，也要拦住"结束早于开始"
        resp = self.client.put(
            f"/api/training/plans/{plan_id}", json={"end_date": "2026-03-01"}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("结束日期", resp.json()["message"])

    def test_plan_list_filters(self):
        self._create_plan(plan_name="A 计划", status="completed")
        self._create_plan(plan_name="B 计划", status="pending")
        by_status = self.client.get(
            "/api/training/plans", params={"status": "pending"}, headers=self.headers
        ).json()
        self.assertEqual(by_status["total"], 1)
        self.assertEqual(by_status["items"][0]["plan_name"], "B 计划")

        by_keyword = self.client.get(
            "/api/training/plans", params={"keyword": "A 计划"}, headers=self.headers
        ).json()
        self.assertEqual(by_keyword["total"], 1)

    def test_plan_delete_blocked_while_records_exist(self):
        plan_id = self._create_plan()
        self._create_record(plan_id=plan_id, course_name="测试培训计划")
        resp = self.client.delete(f"/api/training/plans/{plan_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("培训档案", resp.json()["message"])

        record_id = self.client.get("/api/training/records", headers=self.headers).json()["items"][0]["id"]
        self.client.delete(f"/api/training/records/{record_id}", headers=self.headers)
        resp = self.client.delete(f"/api/training/plans/{plan_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)

    # ---------------- 培训档案 ----------------

    def test_record_rejects_unknown_references(self):
        resp = self.client.post(
            "/api/training/records", json={"trainee_name": "张三", "plan_id": 999999}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("培训计划不存在", resp.json()["message"])

        resp = self.client.post(
            "/api/training/records", json={"trainee_name": "张三", "exam_id": 999999}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("考试场次不存在", resp.json()["message"])

    def test_record_requires_trainee_name(self):
        resp = self.client.post("/api/training/records", json={"trainee_name": ""}, headers=self.headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("姓名", resp.json()["message"])

    def test_record_pass_judgement_uses_exam_pass_score(self):
        exam_id = self._create_exam(pass_score=70)
        # 65 分：按默认 60 算合格，但该场次及格线是 70，应为不合格
        item = self._create_record(trainee_name="李四", exam_id=exam_id, exam_score=65)["item"]
        self.assertEqual(item["pass_score"], 70)
        self.assertFalse(item["is_passed"])
        self.assertEqual(item["result_label"], "不合格")

        item = self._create_record(trainee_name="王五", exam_id=exam_id, exam_score=70)["item"]
        self.assertTrue(item["is_passed"])
        self.assertEqual(item["result_label"], "合格")

    def test_record_without_score_is_not_failed(self):
        """没参加考试既不是合格也不是不合格，不能被算成 0 分。"""
        item = self._create_record(trainee_name="赵六", exam_score=None)["item"]
        self.assertIsNone(item["exam_score"])
        self.assertIsNone(item["is_passed"])
        self.assertEqual(item["result_label"], "未考试")

    # ---------------- 聚合口径 ----------------

    def test_exam_stats_only_count_scored_records(self):
        exam_id = self._create_exam(pass_score=60, title="统计口径考试")
        self._create_record(trainee_name="甲", exam_id=exam_id, exam_score=90)
        self._create_record(trainee_name="乙", exam_id=exam_id, exam_score=50)
        self._create_record(trainee_name="丙", exam_id=exam_id, exam_score=None)

        body = self.client.get("/api/training/exams", headers=self.headers).json()
        item = body["items"][0]
        # 3 条档案里只有 2 条有成绩：参考人数 2，平均 70，及格 1/2
        self.assertEqual(item["attend_count"], 2)
        self.assertEqual(item["avg_score"], 70.0)
        self.assertEqual(item["pass_rate"], 50.0)

    def test_exam_without_scores_reports_none(self):
        """一条成绩都没有时，平均分与及格率返回 null，不能拿 0 冒充。"""
        self._create_exam(title="还没考的考试")
        item = self.client.get("/api/training/exams", headers=self.headers).json()["items"][0]
        self.assertEqual(item["attend_count"], 0)
        self.assertIsNone(item["avg_score"])
        self.assertIsNone(item["pass_rate"])

    def test_exam_delete_blocked_while_records_exist(self):
        exam_id = self._create_exam()
        self._create_record(trainee_name="甲", exam_id=exam_id, exam_score=80)
        resp = self.client.delete(f"/api/training/exams/{exam_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("成绩记录", resp.json()["message"])

    def test_plan_actual_count_comes_from_records(self):
        plan_id = self._create_plan(person_count=50)
        self._create_record(trainee_name="甲", plan_id=plan_id)
        self._create_record(trainee_name="乙", plan_id=plan_id)
        item = self.client.get("/api/training/plans", headers=self.headers).json()["items"][0]
        # 计划人数是录入值，实际人数来自档案聚合，两者分别给出
        self.assertEqual(item["person_count"], 50)
        self.assertEqual(item["actual_count"], 2)

    def test_stats_overview(self):
        exam_id = self._create_exam(pass_score=60)
        plan_id = self._create_plan()
        self._create_record(trainee_name="甲", plan_id=plan_id, exam_id=exam_id, exam_score=90)
        self._create_record(trainee_name="乙", plan_id=plan_id, exam_id=exam_id, exam_score=40)
        self._create_record(trainee_name="丙", plan_id=plan_id, exam_id=exam_id, exam_score=None)

        stats = self.client.get("/api/training/stats", headers=self.headers).json()
        self.assertEqual(stats["plan_count"], 1)
        self.assertEqual(stats["exam_count"], 1)
        self.assertEqual(stats["record_count"], 3)
        self.assertEqual(stats["trained_count"], 3)
        # 及格率只看有成绩的 2 条
        self.assertEqual(stats["scored_count"], 2)
        self.assertEqual(stats["passed_count"], 1)
        self.assertEqual(stats["pass_rate"], 50.0)
        # 课程数来自学习模块，不是培训表里的
        self.assertGreaterEqual(stats["course_count"], 1)

    def test_stats_pass_rate_is_null_without_scores(self):
        self._create_plan()
        stats = self.client.get("/api/training/stats", headers=self.headers).json()
        self.assertIsNone(stats["pass_rate"])

    # ---------------- 导出 ----------------

    def test_export_csv_follows_filters_and_has_bom(self):
        exam_id = self._create_exam()
        self._create_record(trainee_name="甲", department="安保部", exam_id=exam_id, exam_score=90, cert_no="C001")
        self._create_record(trainee_name="乙", department="技术部", exam_id=exam_id, exam_score=30)

        resp = self.client.get("/api/training/records/export", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("text/csv", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers["content-disposition"])
        text = resp.text
        # Excel 打开中文不乱码靠这个 BOM
        self.assertTrue(text.startswith("\ufeff"))
        lines = [line for line in text.lstrip("\ufeff").splitlines() if line.strip()]
        self.assertEqual(len(lines), 3, text)
        self.assertIn("姓名", lines[0])
        self.assertIn("证书编号", lines[0])
        self.assertIn("合格", text)
        self.assertIn("不合格", text)

        # 按部门筛选后只导出该部门的记录
        resp = self.client.get(
            "/api/training/records/export", params={"department": "技术部"}, headers=self.headers
        )
        lines = [line for line in resp.text.lstrip("\ufeff").splitlines() if line.strip()]
        self.assertEqual(len(lines), 2, resp.text)
        self.assertIn("乙", resp.text)
        self.assertNotIn("甲", resp.text)

    def test_export_requires_login(self):
        self.assertEqual(self.client.get("/api/training/records/export").status_code, 401)


class TestTrainingTenantIsolation(unittest.TestCase):
    """另一个租户看不到、也改不动本租户的培训数据。"""

    def setUp(self):
        init_db()
        self.db = SessionLocal()
        self.tenant_id = get_default_tenant_id(self.db)
        _clear_training(self.db, self.tenant_id)
        self.plan_id = self._create_plan_in_default_tenant()

        # 另建一个租户 + 管理员，用它访问本租户的数据
        from database import Tenant

        self.other_tenant = Tenant(
            tenant_code=f"training-iso-{os.getpid()}",
            tenant_name="培训隔离测试租户",
            status="active",
        )
        self.db.add(self.other_tenant)
        self.db.commit()
        self.db.refresh(self.other_tenant)

        role, _ = _ensure_role(
            self.db, self.other_tenant.id, f"{MANAGE_ROLE}-iso", ["training:view", "training:manage"]
        )
        user, _ = _ensure_user(
            self.db, self.other_tenant.id, f"{ADMIN_USER}-iso", role.id
        )
        self.other_user_id = user.id
        self.other_role_id = role.id
        self.other_tenant_id = self.other_tenant.id

        self.client = TestClient(main.app)
        self.headers = _login(self.client, f"{ADMIN_USER}-iso")

    def tearDown(self):
        _clear_training(self.db, self.tenant_id)
        self.db.query(User).filter(User.id == self.other_user_id).delete(synchronize_session=False)
        self.db.query(Role).filter(Role.id == self.other_role_id).delete(synchronize_session=False)
        from database import Tenant

        self.db.query(Tenant).filter(Tenant.id == self.other_tenant_id).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    def _create_plan_in_default_tenant(self):
        row = TrainingPlan(
            tenant_id=self.tenant_id, plan_name="本租户计划", plan_type="综合培训", status="pending"
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row.id

    def test_other_tenant_sees_nothing(self):
        body = self.client.get("/api/training/plans", headers=self.headers).json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["items"], [])

    def test_other_tenant_cannot_update_or_delete(self):
        resp = self.client.put(
            f"/api/training/plans/{self.plan_id}", json={"progress": 99}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("不存在", resp.json()["message"])

        resp = self.client.delete(f"/api/training/plans/{self.plan_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 400)

        still = self.db.query(TrainingPlan).filter(TrainingPlan.id == self.plan_id).first()
        self.assertIsNotNone(still)
        self.assertEqual(still.progress or 0, 0)


class TestTrainingMigration(unittest.TestCase):
    """培训三张表由迁移创建，且可干净回退。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "training.db"
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

    def _tables(self):
        return set(inspect(self.engine).get_table_names())

    def test_migration_creates_three_tables(self):
        migration.run_migrations()
        tables = self._tables()
        for name in ("training_plans", "training_exams", "training_records"):
            self.assertIn(name, tables, f"迁移没有创建 {name}")

    def test_downgrade_removes_three_tables(self):
        from alembic import command

        migration.run_migrations()
        # 回退到遥测迁移那一版（培训迁移的 down_revision）
        command.downgrade(migration.alembic_config(), "a1b2c3d4e5f6")
        tables = self._tables()
        for name in ("training_plans", "training_exams", "training_records"):
            self.assertNotIn(name, tables, f"downgrade 之后 {name} 仍然存在")


if __name__ == "__main__":
    unittest.main()
