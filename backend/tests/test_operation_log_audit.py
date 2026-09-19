"""审计日志（操作日志）测试

覆盖：
- 哈希链：序号单调、前序哈希串联、校验通过
- 防篡改：内容被改 / 序号出现缺口 / 前序哈希对不上 都能被检出并定位
- 统一写入轨：业务日志经 add_operation_log 落到主库，且能被操作日志页面读到
- 通知中心兼容：业务日志读取不混入中间件按请求写的 HTTP 日志
- 租户隔离：A 租户看不到 B 租户的审计日志
- 审计导出：CSV / JSON 内容、导出留痕、参数校验
"""
import csv
import io
import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    LoginLog,
    OperationLog,
    Role,
    SessionLocal,
    Tenant,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import operation_log_service as audit
from services.operation_log_orm_service import (
    get_operation_log_dashboard_orm,
    list_operation_logs_orm,
)

TEST_USERNAME = "audit-log-tester"
TEST_PASSWORD = "Test#12345"
TEST_ROLE_CODE = "audit-log-viewer"
OTHER_TENANT_CODE = "audit-other-tenant"


def _append(module="测试模块", action="test_action", **kwargs):
    """追加一条日志并返回脱离会话的字段快照。"""
    db = SessionLocal()
    try:
        log = audit.append_operation_log(db, module=module, action=action, **kwargs)
        return {
            "id": log.id,
            "seq": log.seq,
            "hash": log.hash,
            "prev_hash": log.prev_hash,
            "description": log.description,
            "title": log.title,
            "username": log.username,
        }
    finally:
        db.close()


def _restore(log_id: int, **fields):
    """把被篡改的行改回原样，避免影响同批次后续用例。"""
    db = SessionLocal()
    try:
        db.query(OperationLog).filter(OperationLog.id == log_id).update(
            fields, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _verify(**kwargs):
    db = SessionLocal()
    try:
        return audit.verify_operation_log_chain(db, **kwargs)
    finally:
        db.close()


class TestOperationLogChain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_new_log_is_chained_to_previous(self):
        first = _append(action="chain_first")
        second = _append(action="chain_second")

        self.assertEqual(second["seq"], first["seq"] + 1)
        self.assertEqual(second["prev_hash"], first["hash"])
        self.assertEqual(len(second["hash"]), 64)
        self.assertNotEqual(first["hash"], second["hash"])

    def test_chain_verifies(self):
        _append(action="chain_verify")
        result = _verify()
        self.assertTrue(result["ok"], result)
        self.assertIsNone(result["first_broken"])
        self.assertGreaterEqual(result["checked"], 1)
        self.assertEqual(result["algorithm"], audit.CHAIN_ALGORITHM)

    def test_modified_content_is_detected(self):
        log = _append(action="chain_tamper_content", description="原始内容")
        try:
            _restore(log["id"], description="被篡改的内容")
            result = _verify()
            self.assertFalse(result["ok"])
            self.assertEqual(result["first_broken"]["seq"], log["seq"])
            self.assertEqual(result["first_broken"]["reason"], "内容与哈希不一致，该条记录已被修改")
            self.assertIn("expected_hash", result["first_broken"])
        finally:
            _restore(log["id"], description=log["description"])
        self.assertTrue(_verify()["ok"], "恢复后链路应重新通过校验")

    def test_seq_gap_is_detected(self):
        log = _append(action="chain_tamper_seq")
        try:
            _restore(log["id"], seq=log["seq"] + 1)
            result = _verify()
            self.assertFalse(result["ok"])
            self.assertEqual(result["first_broken"]["reason"], "序号不连续，疑似有记录被删除")
        finally:
            _restore(log["id"], seq=log["seq"])
        self.assertTrue(_verify()["ok"])

    def test_prev_hash_mismatch_is_detected(self):
        log = _append(action="chain_tamper_prev")
        try:
            _restore(log["id"], prev_hash="f" * 64)
            result = _verify()
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["first_broken"]["reason"], "前序哈希不匹配，疑似有记录被插入或替换"
            )
        finally:
            _restore(log["id"], prev_hash=log["prev_hash"])
        self.assertTrue(_verify()["ok"])

    def test_verify_can_be_limited(self):
        _append(action="chain_limit")
        total = _verify()["total_chained"]
        limited = _verify(max_rows=1)
        self.assertTrue(limited["ok"])
        self.assertEqual(limited["checked"], 1)
        self.assertTrue(limited["truncated"])
        self.assertGreaterEqual(total, 1)

    def test_hash_covers_key_fields(self):
        """标题、对象、变更前后状态都必须进入哈希，否则篡改这些字段不会被发现。"""
        created = _append(
            action="chain_fields", target_id="42", status_before="A", status_after="B"
        )
        db = SessionLocal()
        try:
            row = db.query(OperationLog).filter(OperationLog.id == created["id"]).first()
            content = audit.chain_content(row)
            recomputed = audit.compute_hash(content, row.prev_hash)
            self.assertEqual(recomputed, row.hash)
        finally:
            db.close()

        for field in ("seq", "title", "target_id", "status_before", "status_after", "username", "created_at"):
            self.assertIn(field, content)


class TestOperationLogUnifiedWrite(unittest.TestCase):
    """业务日志必须落到主库，且能被操作日志页面读到。"""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_business_log_lands_in_main_store(self):
        record = audit.add_operation_log(
            module="整改工单",
            action="update_workorder_status",
            target_type="workorder",
            target_id="W-9001",
            title="整改工单状态更新",
            detail="隐患：通道堵塞：待复查 → 已闭环。",
            operator="安全管理员",
            level="success",
            status_before="待复查",
            status_after="已闭环",
            raw={"inspection_id": "INS-1"},
        )
        self.assertTrue(record.get("id"))
        self.assertEqual(record["level"], "success")
        self.assertEqual(record["detail"], "隐患：通道堵塞：待复查 → 已闭环。")
        self.assertEqual(record["operator"], "安全管理员")
        # 旧调用方依赖的自动 link
        self.assertEqual(record["link"], "/workorders?order_id=W-9001")

        db = SessionLocal()
        try:
            row = db.query(OperationLog).filter(OperationLog.id == record["id"]).first()
            self.assertIsNotNone(row, "业务日志必须写入主库")
            self.assertIsNotNone(row.seq, "业务日志同样要接入哈希链")
            self.assertEqual(row.source, audit.SOURCE_BUSINESS)
            self.assertEqual(row.target_id, "W-9001")
            self.assertEqual(row.payload, {"inspection_id": "INS-1"})

            page = list_operation_logs_orm(db, keyword="W-9001", tenant_id=None)
        finally:
            db.close()
        self.assertTrue(any(item["id"] == record["id"] for item in page["items"]))

    def test_business_list_excludes_http_request_logs(self):
        business = audit.add_operation_log(module="测试模块", action="business_only", title="业务日志")
        db = SessionLocal()
        try:
            # 模拟中间件按请求写入的日志
            audit.append_operation_log(
                db, module="系统操作", action="创建", title="创建",
                description="POST /api/whatever", source=audit.SOURCE_HTTP,
            )
        finally:
            db.close()

        rows = audit.list_operation_logs(limit=200)
        self.assertTrue(rows)
        self.assertTrue(all(item["source"] == audit.SOURCE_BUSINESS for item in rows))
        self.assertTrue(any(item["id"] == business["id"] for item in rows))

    def test_failure_is_swallowed(self):
        """写审计日志失败不能影响业务流程。"""
        with mock.patch.object(audit, "append_operation_log", side_effect=RuntimeError("db down")):
            result = audit.add_operation_log(module="测试模块", action="should_not_raise")
        self.assertEqual(result, {})


class TestOperationLogTenantIsolation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            other = db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).first()
            if not other:
                other = Tenant(tenant_code=OTHER_TENANT_CODE, tenant_name="审计隔离租户", status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
            cls.other_tenant_id = other.id
        finally:
            db.close()

    def test_other_tenant_cannot_read_logs(self):
        marker = f"AUDIT-ISO-{uuid.uuid4().hex[:8]}"
        db = SessionLocal()
        try:
            audit.append_operation_log(
                db, tenant_id=self.tenant_id, module="隔离测试", action=marker,
                title="仅本租户可见",
            )
        finally:
            db.close()

        db = SessionLocal()
        try:
            mine = list_operation_logs_orm(db, keyword=marker, tenant_id=self.tenant_id)
            others = list_operation_logs_orm(db, keyword=marker, tenant_id=self.other_tenant_id)
        finally:
            db.close()

        self.assertTrue(any(item["action"] == marker for item in mine["items"]))
        self.assertEqual(others["total"], 0, "其他租户不应看到该条审计日志")


class TestOperationLogApi(unittest.TestCase):

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

            role = db.query(Role).filter(Role.role_code == TEST_ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=TEST_ROLE_CODE,
                    role_name="审计日志查看",
                    permissions=json.dumps(["logs:view"]),
                )
                db.add(role)
                db.commit()
                db.refresh(role)
            cls.role_id = role.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(
                    username=TEST_USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="审计测试员",
                    role_id=role.id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
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
            if cls.user_id:
                db.query(User).filter(User.id == cls.user_id).delete(synchronize_session=False)
            if cls.role_id:
                db.query(Role).filter(Role.id == cls.role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    # ---------------- 列表 / 校验 ----------------

    def test_endpoints_require_authentication(self):
        for path in (
            "/api/system/operation-logs",
            "/api/system/operation-logs/dashboard",
            "/api/system/operation-logs/verify",
            "/api/system/operation-logs/export",
        ):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_verify_endpoint_reports_intact_chain(self):
        resp = self.client.get("/api/system/operation-logs/verify", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["verified_by"], TEST_USERNAME)
        self.assertGreaterEqual(body["checked"], 1)

    def test_list_endpoint_filters_by_keyword(self):
        marker = f"API-AUDIT-{uuid.uuid4().hex[:8]}"
        audit.add_operation_log(
            module="接口测试", action=marker, title="列表可见性", tenant_id=self.tenant_id
        )

        resp = self.client.get(
            "/api/system/operation-logs", params={"keyword": marker}, headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreaterEqual(body["total"], 1)
        self.assertTrue(all(marker in (item["action"] or "") for item in body["items"]))

    # ---------------- 审计导出 ----------------

    def test_csv_export_contains_chain_columns(self):
        audit.add_operation_log(
            module="导出测试", action="export_case_csv", title="CSV 导出用例", tenant_id=self.tenant_id
        )

        resp = self.client.get("/api/system/operation-logs/export?format=csv", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        disposition = resp.headers["content-disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn(".csv", disposition)

        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
        header = rows[0]
        self.assertIn("链序号", header)
        self.assertIn("本行哈希", header)
        self.assertIn("前序哈希", header)
        self.assertGreater(len(rows), 2)
        self.assertTrue(any("哈希链校验" in cell for row in rows for cell in row))

    def test_json_export_carries_meta_and_items(self):
        resp = self.client.get("/api/system/operation-logs/export?format=json", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("application/json", resp.headers["content-type"])

        body = json.loads(resp.content.decode("utf-8"))
        meta = body["export_meta"]
        self.assertGreaterEqual(meta["count"], 1)
        self.assertEqual(meta["chain"]["algorithm"], audit.CHAIN_ALGORITHM)
        self.assertTrue(meta["chain"]["verified"])
        self.assertEqual(meta["exported_by"], TEST_USERNAME)
        self.assertTrue(all("hash" in item for item in body["items"]))

    def test_export_is_audited(self):
        """导出动作本身必须留痕，否则审计链不完整。"""
        db = SessionLocal()
        try:
            before_count = db.query(OperationLog).filter(
                OperationLog.module == "操作日志", OperationLog.action == "export"
            ).count()
        finally:
            db.close()

        resp = self.client.get("/api/system/operation-logs/export?format=json", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)

        db = SessionLocal()
        try:
            rows = db.query(OperationLog).filter(
                OperationLog.module == "操作日志", OperationLog.action == "export"
            ).order_by(OperationLog.id.desc()).all()
            latest = {
                "count": len(rows),
                "username": rows[0].username,
                "level": rows[0].level,
                "seq": rows[0].seq,
            }
        finally:
            db.close()

        self.assertEqual(latest["count"], before_count + 1)
        self.assertEqual(latest["username"], TEST_USERNAME)
        self.assertEqual(latest["level"], "warning")
        self.assertIsNotNone(latest["seq"], "导出留痕同样要接入哈希链")

    def test_invalid_format_is_rejected(self):
        resp = self.client.get("/api/system/operation-logs/export?format=xlsx", headers=self.headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("csv", resp.json()["message"])

    def test_invalid_time_is_rejected(self):
        resp = self.client.get("/api/system/operation-logs/export?start=2026-13-99", headers=self.headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("时间格式", resp.json()["message"])

    def test_export_respects_module_filter(self):
        resp = self.client.get(
            "/api/system/operation-logs/export?format=json&module=不存在的模块", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = json.loads(resp.content.decode("utf-8"))
        self.assertEqual(body["export_meta"]["count"], 0)
        self.assertEqual(body["items"], [])


class TestDashboardMetrics(unittest.TestCase):
    """页面顶部指标卡必须是真实统计。

    改造前四张卡写死为 1,268 / 342 / 87 / 36，与真实数据无关。
    这里用「前后差值」断言，避免受同库中其它用例产生的日志影响。
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
        finally:
            db.close()

    def _dashboard(self) -> dict:
        db = SessionLocal()
        try:
            return get_operation_log_dashboard_orm(db, tenant_id=self.tenant_id)
        finally:
            db.close()

    def test_dashboard_has_all_metric_fields(self):
        body = self._dashboard()
        for field in ("total", "error_count", "warning_count",
                      "status_changed_count", "today_login_users"):
            self.assertIn(field, body)
            self.assertIsInstance(body[field], int)

    def test_status_change_count_tracks_real_rows(self):
        before = self._dashboard()["status_changed_count"]
        suffix = uuid.uuid4().hex[:6]

        # 两条带状态流转
        audit.add_operation_log(
            module="整改工单", action="update_status", target_type="workorder",
            target_id=f"DASH-{suffix}", title="状态流转",
            status_before="待整改", status_after="整改中", tenant_id=self.tenant_id,
        )
        audit.add_operation_log(
            module="巡检档案", action="archive", target_type="inspection",
            target_id=f"DASH-{suffix}", title="归档",
            status_after="已归档", tenant_id=self.tenant_id,
        )
        # 一条不带状态流转，不应计入
        audit.add_operation_log(
            module="知识库", action="query", target_id=f"DASH-{suffix}",
            title="检索", tenant_id=self.tenant_id,
        )

        self.assertEqual(self._dashboard()["status_changed_count"] - before, 2)

    def test_today_login_users_counts_distinct_successful_accounts(self):
        before = self._dashboard()["today_login_users"]
        suffix = uuid.uuid4().hex[:6]
        now = datetime.utcnow()

        db = SessionLocal()
        try:
            db.add_all([
                # 同一账号两次成功登录只算一个
                LoginLog(tenant_id=None, username=f"dash-{suffix}-a",
                         status="success", login_at=now),
                LoginLog(tenant_id=None, username=f"dash-{suffix}-a",
                         status="success", login_at=now),
                LoginLog(tenant_id=None, username=f"dash-{suffix}-b",
                         status="success", login_at=now),
                # 失败登录不算「访问」
                LoginLog(tenant_id=None, username=f"dash-{suffix}-c",
                         status="failed", login_at=now),
                # 两天前的不算今日
                LoginLog(tenant_id=None, username=f"dash-{suffix}-old",
                         status="success", login_at=now - timedelta(days=2)),
            ])
            db.commit()
        finally:
            db.close()

        self.assertEqual(self._dashboard()["today_login_users"] - before, 2)

    def test_local_day_start_is_a_utc_instant_not_local_midnight(self):
        """「今日」边界必须换算到 UTC，否则 UTC+8 下会漏掉本地 00:00-08:00。"""
        from services.common_utils import local_day_start_utc

        offset = datetime.now() - datetime.utcnow()
        expected = datetime.combine(datetime.now().date(), datetime.min.time()) - offset
        self.assertAlmostEqual(
            local_day_start_utc().timestamp(), expected.timestamp(), delta=1
        )
        self.assertLess(local_day_start_utc(), datetime.utcnow(),
                        "今日起点必须早于当前时刻，否则刚写下的记录不计入今日")


if __name__ == "__main__":
    unittest.main()
