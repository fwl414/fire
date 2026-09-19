"""系统监控页：数字必须来自真实采集

改造前 `SystemMonitor.vue` 每 3 秒用 `Math.random()` 改写 CPU / 内存 / 网络，趋势曲线也是
随机数滚出来的；峰值/均值、数据库连接数、接口调用量都是写死的常量，页面标注的「每 5 秒刷新」
同样是假的。本文件固化改造后的行为：每个数字都能和 psutil / 真实计数器对上，
拿不到就返回 None，不用估算值顶替。
"""
import importlib
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import psutil
from fastapi.testclient import TestClient
from sqlalchemy import text

import main
from database import Role, SessionLocal, Tenant, User, engine, hash_password, init_db
from services import system_metrics_service
from services.auth_service import create_access_token

TENANT_CODE = "system-metrics-tenant"
ADMIN_USER = "system-metrics-user"
ADMIN_ROLE = "system-metrics-role"
PASSWORD = "Test#12345"


class TestSystemMetricsCollection(unittest.TestCase):
    """采集层：返回值必须与 psutil / 数据库对得上。"""

    def test_cpu_and_network_need_two_samples(self):
        """CPU 与网络速率靠两次采样的差值：首次没有基准就给 None，不编一个数。"""
        module = importlib.reload(system_metrics_service)

        first = module.host_snapshot()
        self.assertIsNone(first["cpu"])
        self.assertIsNone(first["network"])
        self.assertEqual(first["trend"], [])

        # psutil.cpu_times() 的计数器有粒度（Linux /proc/stat 约 10ms，Windows 约 15.6ms），
        # 两次调用落在同一个时间片里差值就是 0，此时服务按设计返回 None。
        # 所以要等计数器真正推进再断言，否则用例会被采样粒度搞成偶发失败——
        # 同一份代码曾出现「全量跑 1 failed / 再跑一次 612 passed」。
        second = first
        for _ in range(20):
            time.sleep(0.02)
            second = module.host_snapshot()
            if second["cpu"] is not None:
                break

        self.assertIsNotNone(second["cpu"], "等待 0.4s 后 CPU 计数器仍未推进")
        self.assertGreaterEqual(second["cpu"], 0.0)
        self.assertLessEqual(second["cpu"], 100.0)
        self.assertIsNotNone(second["network"])
        self.assertEqual(len(second["trend"]), 1)
        self.assertEqual(second["trend"][0]["cpu"], second["cpu"])

    def test_memory_and_disk_match_psutil(self):
        snapshot = system_metrics_service.host_snapshot()
        memory = psutil.virtual_memory()
        self.assertEqual(snapshot["memory_total_bytes"], int(memory.total))
        self.assertLessEqual(abs(snapshot["memory"] - float(memory.percent)), 2.0)
        disk = psutil.disk_usage(snapshot["disk_mount"])
        self.assertEqual(snapshot["disk_total_bytes"], int(disk.total))
        self.assertLessEqual(abs(snapshot["disk"] - float(disk.percent)), 5.0)

    def test_process_list_excludes_idle_and_is_sorted(self):
        result = system_metrics_service.process_snapshot(limit=5)
        self.assertTrue(result["items"], "进程列表不该为空")
        self.assertTrue(all(item["pid"] != 0 for item in result["items"]), "空闲进程不该出现在占用排行里")
        cpu_values = [item["cpu_percent"] for item in result["items"]]
        self.assertEqual(cpu_values, sorted(cpu_values, reverse=True))
        for item in result["items"]:
            self.assertIn("name", item)
            self.assertIn("memory_percent", item)

    def test_database_snapshot_counts_real_rows(self):
        result = system_metrics_service.database_snapshot()
        self.assertTrue(result["connected"])
        self.assertEqual(result["dialect"], "sqlite")
        # SQLite 没有 QPS / 缓存命中率，如实列出来而不是编一个数字
        self.assertIn("qps", result["unsupported_metrics"])
        self.assertIn("cache_hit_rate", result["unsupported_metrics"])

        with engine.connect() as conn:
            expected = int(conn.execute(text("SELECT COUNT(*) FROM devices")).scalar() or 0)
        device_row = next(row for row in result["tables"] if row["name"] == "devices")
        self.assertEqual(device_row["row_count"], expected)

    def test_connection_url_is_masked(self):
        masked = system_metrics_service._mask_url("postgresql://user:secret@db.internal:5432/fire")
        self.assertNotIn("secret", masked)
        self.assertIn("user", masked)


class TestSystemMetricsApi(unittest.TestCase):
    """接口层：需要登录，且返回真实值。"""

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.tenant_code == TENANT_CODE).first()
            if not tenant:
                tenant = Tenant(tenant_code=TENANT_CODE, tenant_name="系统监控测试租户", status="active")
                db.add(tenant)
                db.commit()
                db.refresh(tenant)

            role = db.query(Role).filter(Role.role_code == ADMIN_ROLE).first()
            if not role:
                role = Role(tenant_id=tenant.id, role_code=ADMIN_ROLE, role_name=ADMIN_ROLE,
                            permissions=json.dumps(["*"]))
                db.add(role)
                db.commit()
                db.refresh(role)

            user = db.query(User).filter(User.username == ADMIN_USER).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(username=ADMIN_USER, password_hash=hashed, password_salt=salt,
                            tenant_id=tenant.id, role_id=role.id, real_name=ADMIN_USER,
                            status="active")
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.token = create_access_token(user)
        finally:
            db.close()
        cls.client = TestClient(main.app)

    def _get(self, path):
        return self.client.get(path, headers={"Authorization": f"Bearer {self.token}"})

    def test_endpoints_require_login(self):
        for path in ("/api/system/host", "/api/system/processes",
                     "/api/system/database", "/api/system/api-stats"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_host_endpoint_returns_real_values(self):
        first = self._get("/api/system/host")
        self.assertEqual(first.status_code, 200, first.text)
        payload = first.json()
        self.assertIn("memory", payload)
        self.assertIn("disk", payload)
        self.assertIn("disk_total_bytes", payload)

        # 第二次调用才有 CPU（首次只建基准）
        second = self._get("/api/system/host").json()
        self.assertIsNotNone(second["cpu"])

    def test_repeated_reads_are_stable_not_random(self):
        """磁盘总量与内存总量短时间内不会变 —— 以前页面每 3 秒用随机数改写这些数字。"""
        first = self._get("/api/system/host").json()
        second = self._get("/api/system/host").json()
        self.assertEqual(first["disk"], second["disk"])
        self.assertEqual(first["disk_total_bytes"], second["disk_total_bytes"])
        self.assertEqual(first["memory_total_bytes"], second["memory_total_bytes"])

    def test_process_endpoint_honours_limit(self):
        resp = self._get("/api/system/processes?limit=3")
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertLessEqual(len(payload["items"]), 3)
        self.assertIn("cpu_basis", payload)

    def test_database_endpoint_reports_real_tables(self):
        resp = self._get("/api/system/database")
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertTrue(payload["connected"])
        self.assertGreater(payload["size_bytes"] or 0, 0)
        self.assertIn("devices", {row["name"] for row in payload["tables"]})

    def test_api_stats_counts_real_requests(self):
        # 先制造一次可识别的请求；注意中间件是在响应之后才计数，所以请求自身不会出现在当次结果里
        self._get("/api/system/host")
        first = self._get("/api/system/api-stats?limit=200").json()
        self.assertGreater(first["total"], 0, "本进程已经处理过请求，计数不该是 0")
        paths = {item["path"] for item in first["by_path"]}
        self.assertIn("/api/system/host", paths)
        for item in first["by_path"]:
            self.assertGreater(item["count"], 0)

        # 真实计数只会累加，不会像随机数那样上下跳
        second = self._get("/api/system/api-stats?limit=200").json()
        self.assertGreater(second["total"], first["total"])


if __name__ == "__main__":
    unittest.main()
