"""登录日志测试

覆盖：
- 登录成功 / 密码错误 / 用户不存在 / 账号禁用 都逐次写入 login_logs
- 设备、浏览器、归属地在读取时由 user_agent / ip 推导，不落冗余列
- 查询接口需要 logs:view 权限
- 过滤（用户名 / 状态 / IP / 时间范围）与分页
- 租户隔离：其它租户的成功登录不可见；未知用户名的失败尝试可见（跨租户的探测信号）
- 日志写入失败不影响登录本身
"""
import json
import os
import sys
import unittest
import uuid
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    LoginAttemptState,
    LoginLog,
    Role,
    SessionLocal,
    Tenant,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import auth_service, login_log_service as login_logs

TEST_USERNAME = "login-log-tester"
TEST_PASSWORD = "Test#12345"
TEST_ROLE_CODE = "login-log-viewer"
LIMITED_ROLE_CODE = "login-log-limited"
LIMITED_USERNAME = "login-log-limited-user"
OTHER_TENANT_CODE = "login-log-other-tenant"
OTHER_USERNAME = "login-log-other-user"

# 这些前缀下的账号会被本文件反复制造失败登录，必须连同失败计数一起清理
_TEST_USERNAME_PREFIXES = ("login-log-%", "no-such-user-%", "cross-tenant-%", "e2e-probe-%")


def _purge_login_state():
    """清掉登录日志**以及失败计数**。

    失败计数（`login_attempt_states`）是跨用例、跨运行残留的：同一账号累计失败
    `MAX_LOGIN_ATTEMPTS` 次就会被锁定 15 分钟，之后用例拿到的是「账号已锁定」而不是
    「密码错误」，断言会莫名其妙地失败。只清日志不清计数是不够的。
    """
    db = SessionLocal()
    try:
        db.query(LoginLog).delete(synchronize_session=False)
        for prefix in _TEST_USERNAME_PREFIXES:
            db.query(LoginAttemptState).filter(
                LoginAttemptState.username.like(prefix)
            ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _login(username: str, password: str, ip: str = "", user_agent: str = ""):
    db = SessionLocal()
    try:
        return auth_service.login(username, password, db, ip=ip, user_agent=user_agent)
    finally:
        db.close()


def _latest_log(username: str):
    db = SessionLocal()
    try:
        row = (
            db.query(LoginLog)
            .filter(LoginLog.username == username)
            .order_by(LoginLog.id.desc())
            .first()
        )
        return login_logs.serialize(row) if row else {}
    finally:
        db.close()


class TestUserAgentAndIpParsing(unittest.TestCase):
    """设备 / 浏览器 / 归属地都是推导值，必须可预期。"""

    def test_windows_chrome(self):
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.assertEqual(login_logs.parse_user_agent(ua), {"os": "Windows 10", "browser": "Chrome 120"})

    def test_macos_safari_and_edge(self):
        safari = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
        self.assertEqual(login_logs.parse_user_agent(safari), {"os": "macOS", "browser": "Safari 17"})

        edge = ("Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91")
        self.assertEqual(login_logs.parse_user_agent(edge), {"os": "Windows 11", "browser": "Edge 120"})

    def test_unknown_user_agent_returns_empty(self):
        self.assertEqual(login_logs.parse_user_agent(""), {"os": "", "browser": ""})
        self.assertEqual(login_logs.parse_user_agent("SomeBot/1.0"), {"os": "", "browser": ""})

    def test_describe_ip_only_claims_what_it_can_know(self):
        """没有接 IP 库，就只能对内网地址下结论，公网地址留空由页面显示 —。"""
        self.assertEqual(login_logs.describe_ip("192.168.1.100"), "内网")
        self.assertEqual(login_logs.describe_ip("10.0.0.7"), "内网")
        self.assertEqual(login_logs.describe_ip("172.20.3.4"), "内网")
        self.assertEqual(login_logs.describe_ip("127.0.0.1"), "本机")
        self.assertEqual(login_logs.describe_ip("114.88.120.56"), "")
        self.assertEqual(login_logs.describe_ip(""), "")


class TestLoginLogRecording(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        _purge_login_state()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            role = db.query(Role).filter(Role.role_code == TEST_ROLE_CODE).first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code=TEST_ROLE_CODE,
                            role_name="登录日志查看", permissions=json.dumps(["logs:view"]))
                db.add(role)
                db.commit()
                db.refresh(role)
            cls.role_id = role.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(username=TEST_USERNAME, password_hash=hashed, password_salt=salt,
                            real_name="登录日志测试员", role_id=role.id, status="active",
                            tenant_id=cls.tenant_id)
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.user_id = user.id

            disabled = db.query(User).filter(User.username == "login-log-disabled").first()
            if not disabled:
                hashed, salt = hash_password(TEST_PASSWORD)
                disabled = User(username="login-log-disabled", password_hash=hashed,
                                password_salt=salt, real_name="已禁用账号", role_id=role.id,
                                status="disabled", tenant_id=cls.tenant_id)
                db.add(disabled)
                db.commit()
                db.refresh(disabled)
            cls.disabled_user_id = disabled.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        _purge_login_state()
        db = SessionLocal()
        try:
            for user_id in (cls.user_id, cls.disabled_user_id):
                if user_id:
                    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            if cls.role_id:
                db.query(Role).filter(Role.id == cls.role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        _purge_login_state()

    def test_successful_login_is_recorded(self):
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        result = _login(TEST_USERNAME, TEST_PASSWORD, ip="192.168.1.50", user_agent=ua)
        self.assertTrue(result["ok"], result)

        row = _latest_log(TEST_USERNAME)
        self.assertEqual(row["status"], "success")
        self.assertEqual(row["real_name"], "登录日志测试员")
        self.assertEqual(row["ip_address"], "192.168.1.50")
        self.assertEqual(row["location"], "内网")
        self.assertEqual(row["os"], "Windows 10")
        self.assertEqual(row["browser"], "Chrome 120")
        self.assertEqual(row["fail_reason"], "")
        self.assertRegex(row["login_time"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_wrong_password_is_recorded_with_reason(self):
        result = _login(TEST_USERNAME, "wrong-password", ip="192.168.1.51")
        self.assertFalse(result["ok"])

        row = _latest_log(TEST_USERNAME)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["fail_reason"], "密码错误")
        self.assertEqual(row["real_name"], "登录日志测试员", "已知用户应带上姓名")

    def test_unknown_username_is_recorded_without_tenant(self):
        """未知用户拿不到租户，tenant_id 留空，但必须记下探测行为。

        用户名每次唯一：固定名会被反复失败后锁定，锁定后走的是另一个分支
        （fail_reason 变成「账号已锁定」），断言就不再验证本用例想验证的东西了。
        """
        probe = f"no-such-user-{uuid.uuid4().hex[:8]}"
        result = _login(probe, "whatever", ip="203.0.113.9")
        self.assertFalse(result["ok"])

        row = _latest_log(probe)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["fail_reason"], "用户不存在")
        self.assertEqual(row["location"], "", "公网地址不做无依据的归属地判断")

        db = SessionLocal()
        try:
            stored = db.query(LoginLog).filter(LoginLog.username == probe).first()
            self.assertIsNone(stored.tenant_id)
            self.assertIsNone(stored.user_id)
        finally:
            db.close()

    def test_disabled_account_is_recorded(self):
        result = _login("login-log-disabled", TEST_PASSWORD, ip="192.168.1.52")
        self.assertFalse(result["ok"])
        self.assertIn("禁用", result["message"])

        row = _latest_log("login-log-disabled")
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["fail_reason"], "账号已禁用")

    def test_every_attempt_gets_its_own_row(self):
        """逐次明细：与 LoginAttemptState 的聚合计数不同，这里每次尝试都要留一行。"""
        for _ in range(3):
            _login(TEST_USERNAME, "wrong-password")

        db = SessionLocal()
        try:
            count = db.query(LoginLog).filter(LoginLog.username == TEST_USERNAME).count()
        finally:
            db.close()
        self.assertEqual(count, 3)

    def test_log_write_failure_is_swallowed(self):
        """写登录日志失败不能把登录本身带崩：吞掉异常并回滚本次写入。"""
        broken = mock.MagicMock()
        broken.add.side_effect = RuntimeError("db down")

        # 不应抛出
        login_logs.record_login_attempt(
            broken, username=TEST_USERNAME, status=login_logs.STATUS_SUCCESS
        )
        broken.rollback.assert_called_once()

    def test_login_still_succeeds_when_log_write_fails(self):
        """端到端：落库真的失败时，登录也必须返回成功。"""
        with mock.patch.object(login_logs, "LoginLog", side_effect=RuntimeError("db down")):
            result = _login(TEST_USERNAME, TEST_PASSWORD)
        self.assertTrue(result["ok"], result)


class TestLoginLogApi(unittest.TestCase):

    client = None
    headers = {}
    limited_headers = {}
    tenant_id = None
    role_id = None
    user_id = None
    limited_role_id = None
    limited_user_id = None
    other_tenant_id = None
    other_user_id = None
    other_role_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        _purge_login_state()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

            role = db.query(Role).filter(Role.role_code == TEST_ROLE_CODE).first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code=TEST_ROLE_CODE,
                            role_name="登录日志查看", permissions=json.dumps(["logs:view"]))
                db.add(role)
                db.commit()
                db.refresh(role)
            cls.role_id = role.id

            limited = db.query(Role).filter(Role.role_code == LIMITED_ROLE_CODE).first()
            if not limited:
                limited = Role(tenant_id=cls.tenant_id, role_code=LIMITED_ROLE_CODE,
                               role_name="登录日志受限", permissions=json.dumps(["dashboard:view"]))
                db.add(limited)
                db.commit()
                db.refresh(limited)
            cls.limited_role_id = limited.id

            for attr, username, real_name, role_id in (
                ("user_id", TEST_USERNAME, "登录日志测试员", role.id),
                ("limited_user_id", LIMITED_USERNAME, "受限用户", limited.id),
            ):
                user = db.query(User).filter(User.username == username).first()
                if not user:
                    hashed, salt = hash_password(TEST_PASSWORD)
                    user = User(username=username, password_hash=hashed, password_salt=salt,
                                real_name=real_name, role_id=role_id, status="active",
                                tenant_id=cls.tenant_id)
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                setattr(cls, attr, user.id)

            other = db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).first()
            if not other:
                other = Tenant(tenant_code=OTHER_TENANT_CODE, tenant_name="登录日志隔离租户",
                               status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
            cls.other_tenant_id = other.id

            other_role = db.query(Role).filter(Role.role_code == OTHER_TENANT_CODE).first()
            if not other_role:
                other_role = Role(tenant_id=other.id, role_code=OTHER_TENANT_CODE,
                                  role_name="隔离租户角色", permissions=json.dumps(["dashboard:view"]))
                db.add(other_role)
                db.commit()
                db.refresh(other_role)
            cls.other_role_id = other_role.id

            other_user = db.query(User).filter(User.username == OTHER_USERNAME).first()
            if not other_user:
                hashed, salt = hash_password(TEST_PASSWORD)
                other_user = User(username=OTHER_USERNAME, password_hash=hashed, password_salt=salt,
                                  real_name="隔离租户用户", role_id=other_role.id, status="active",
                                  tenant_id=other.id)
                db.add(other_user)
                db.commit()
                db.refresh(other_user)
            cls.other_user_id = other_user.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        for attr, username in (
            ("headers", TEST_USERNAME),
            ("limited_headers", LIMITED_USERNAME),
        ):
            resp = cls.client.post("/api/auth/login",
                                   data={"username": username, "password": TEST_PASSWORD})
            assert resp.status_code == 200, f"登录失败({username}): {resp.text}"
            setattr(cls, attr, {"Authorization": f"Bearer {resp.json()['access_token']}"})

        # 隔离租户用户直接走服务层登录，避免影响临时 client 的令牌状态
        _login(OTHER_USERNAME, TEST_PASSWORD, ip="10.9.9.9")

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            for user_id in (cls.user_id, cls.limited_user_id, cls.other_user_id):
                if user_id:
                    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            for role_id in (cls.role_id, cls.limited_role_id, cls.other_role_id):
                if role_id:
                    db.query(Role).filter(Role.id == role_id).delete(synchronize_session=False)
            other = db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).first()
            if other:
                db.query(LoginLog).filter(LoginLog.tenant_id == other.id).delete(
                    synchronize_session=False
                )
                db.delete(other)
            db.commit()
        finally:
            db.close()
        _purge_login_state()

    def _get(self, headers=None, **params):
        return self.client.get("/api/system/login-logs", params=params,
                               headers=headers or self.headers)

    def test_endpoint_requires_authentication(self):
        self.assertEqual(self.client.get("/api/system/login-logs").status_code, 401)

    def test_endpoint_requires_logs_view_permission(self):
        denied = self._get(self.limited_headers)
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertIn("logs:view", denied.json()["message"])

    def test_list_returns_real_records(self):
        body = self._get().json()
        self.assertIn("items", body)
        self.assertTrue(body["total"] >= 1)
        usernames = {item["username"] for item in body["items"]}
        self.assertIn(TEST_USERNAME, usernames)
        first = body["items"][0]
        for field in ("login_time", "username", "real_name", "ip_address", "location",
                      "os", "browser", "status", "fail_reason"):
            self.assertIn(field, first)

    def test_filter_by_status_and_username(self):
        failed = self.client.post("/api/auth/login",
                                  data={"username": TEST_USERNAME, "password": "wrong"})
        self.assertEqual(failed.status_code, 401)

        only_failed = self._get(status="failed").json()
        self.assertTrue(only_failed["items"])
        self.assertTrue(all(item["status"] == "failed" for item in only_failed["items"]))

        by_name = self._get(username=TEST_USERNAME).json()
        self.assertTrue(by_name["items"])
        self.assertTrue(all(TEST_USERNAME in item["username"] for item in by_name["items"]))

    def test_filter_by_ip(self):
        body = self._get(ip_address="127.0.0").json()
        for item in body["items"]:
            self.assertIn("127.0.0", item["ip_address"])

    def test_pagination(self):
        page1 = self._get(page=1, page_size=1).json()
        self.assertEqual(len(page1["items"]), 1)
        self.assertEqual(page1["page"], 1)
        self.assertEqual(page1["pageSize"], 1)
        if page1["total"] > 1:
            page2 = self._get(page=2, page_size=1).json()
            self.assertNotEqual(page2["items"][0]["id"], page1["items"][0]["id"])

    def test_tenant_isolation_but_unknown_user_attempts_stay_visible(self):
        """其它租户的成功登录不可见；未知用户名的探测尝试是跨租户的安全信号。"""
        body = self._get(page_size=200).json()
        usernames = {item["username"] for item in body["items"]}
        self.assertNotIn(OTHER_USERNAME, usernames, "不应看到其它租户用户的登录记录")

        probe = f"cross-tenant-{uuid.uuid4().hex[:8]}"
        _login(probe, "whatever", ip="198.51.100.7")
        after = self._get(page_size=200).json()
        probes = [item for item in after["items"] if item["username"] == probe]
        self.assertTrue(probes, "未知用户名的失败尝试应作为安全信号可见")
        self.assertEqual(probes[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
