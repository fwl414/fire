"""报表后端生成 / 落盘登记 / 受控下载 的 API 集成测试。

覆盖：
- 导出报表为后端真实租户数据并落盘登记
- 报表产物清单与下载（带租户隔离）
- 不支持的格式/类型返回 400
- 删除报表产物同时清理磁盘文件
"""
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    ReportArtifact,
    Role,
    SessionLocal,
    Tenant,
    User,
    hash_password,
    init_db,
    get_default_tenant_id,
)
from services.report_archive_service import REPORT_STORAGE_DIR

OWNER_USERNAME = "report-archive-owner"
OUTSIDER_USERNAME = "report-archive-outsider"
PASSWORD = "Test#12345"


class TestReportArchive(unittest.TestCase):

    client = None
    owner_tenant_id = None
    outsider_tenant_id = None
    created_user_ids = []
    created_role_id = None
    created_tenant_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.owner_tenant_id = get_default_tenant_id(db)

            role = db.query(Role).filter(Role.role_code == "admin").first()
            if not role:
                role = Role(
                    tenant_id=cls.owner_tenant_id,
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

            outsider_tenant = Tenant(tenant_code="report-outsider", tenant_name="报表隔离租户")
            db.add(outsider_tenant)
            db.commit()
            cls.outsider_tenant_id = outsider_tenant.id
            cls.created_tenant_id = outsider_tenant.id

            for username, tenant_id in (
                (OWNER_USERNAME, cls.owner_tenant_id),
                (OUTSIDER_USERNAME, cls.outsider_tenant_id),
            ):
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
                cls.created_user_ids.append(user.id)
        finally:
            db.close()

        cls.client = TestClient(main.app)
        cls.owner_headers = cls._login(OWNER_USERNAME)
        cls.outsider_headers = cls._login(OUTSIDER_USERNAME)

    @classmethod
    def _login(cls, username):
        resp = cls.client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
        assert resp.status_code == 200, f"{username} 登录失败: {resp.text}"
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(ReportArtifact).filter(
                ReportArtifact.tenant_id.in_(
                    [cls.owner_tenant_id, cls.outsider_tenant_id]
                )
            ).delete(synchronize_session=False)
            if cls.created_user_ids:
                db.query(User).filter(User.id.in_(cls.created_user_ids)).delete(synchronize_session=False)
            if cls.created_tenant_id:
                db.query(Tenant).filter(Tenant.id == cls.created_tenant_id).delete(synchronize_session=False)
            if cls.created_role_id:
                db.query(Role).filter(Role.id == cls.created_role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

        # 清理本轮产生的报表文件
        for tenant_id in (cls.owner_tenant_id, cls.outsider_tenant_id):
            if tenant_id is None:
                continue
            shutil.rmtree(REPORT_STORAGE_DIR / f"tenant_{tenant_id}", ignore_errors=True)

    def test_01_statistics_uses_real_tenant_data(self):
        resp = self.client.get(
            "/api/reports/statistics?report_type=alert&period=month", headers=self.owner_headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["report_type"], "alert")
        self.assertIn("summary", body)
        self.assertIn("total", body["summary"])
        self.assertIsInstance(body["trend"], list)
        self.assertIsInstance(body["byCategory"], list)

    def test_02_export_persists_artifact_and_downloads(self):
        resp = self.client.post(
            "/api/reports/export",
            headers=self.owner_headers,
            json={"report_type": "inspection", "format": "csv", "period": "month"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertGreater(len(resp.content), 0)
        report_id = resp.headers.get("X-Report-Id")
        report_no = resp.headers.get("X-Report-No")
        self.assertTrue(report_id, "导出应返回报表ID")
        self.assertTrue(report_no, "导出应返回报表编号")

        db = SessionLocal()
        try:
            artifact = db.query(ReportArtifact).filter(ReportArtifact.id == int(report_id)).first()
            self.assertIsNotNone(artifact, "报表产物应登记入库")
            self.assertEqual(artifact.tenant_id, self.owner_tenant_id)
            self.assertEqual(artifact.report_type, "inspection")
            self.assertEqual(artifact.report_format, "csv")
            self.assertTrue(artifact.sha256, "应记录内容指纹")
            self.assertGreater(artifact.size_bytes, 0)
            self.assertTrue(os.path.exists(artifact.file_path), "报表文件应已落盘")
            self.assertIn(
                os.path.abspath(str(REPORT_STORAGE_DIR)), os.path.abspath(artifact.file_path)
            )
        finally:
            db.close()

        listing = self.client.get("/api/reports/artifacts", headers=self.owner_headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        ids = [item["id"] for item in listing.json()["items"]]
        self.assertIn(int(report_id), ids)

        download = self.client.get(
            f"/api/reports/artifacts/{report_id}/download", headers=self.owner_headers
        )
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(download.content, resp.content, "下载内容应与生成内容一致")

    def test_03_export_rejects_unsupported_format_and_type(self):
        bad_format = self.client.post(
            "/api/reports/export",
            headers=self.owner_headers,
            json={"report_type": "inspection", "format": "exe"},
        )
        self.assertEqual(bad_format.status_code, 400, bad_format.text)

        bad_type = self.client.post(
            "/api/reports/export",
            headers=self.owner_headers,
            json={"report_type": "not-exist", "format": "csv"},
        )
        self.assertEqual(bad_type.status_code, 400, bad_type.text)

    def test_04_artifacts_are_tenant_isolated(self):
        created = self.client.post(
            "/api/reports/export",
            headers=self.owner_headers,
            json={"report_type": "workorder", "format": "csv"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        report_id = created.headers["X-Report-Id"]

        outsider_list = self.client.get("/api/reports/artifacts", headers=self.outsider_headers)
        self.assertEqual(outsider_list.status_code, 200, outsider_list.text)
        self.assertNotIn(
            int(report_id),
            [item["id"] for item in outsider_list.json()["items"]],
            "不应看到其他租户的报表",
        )

        detail = self.client.get(f"/api/reports/artifacts/{report_id}", headers=self.outsider_headers)
        self.assertEqual(detail.status_code, 404)

        download = self.client.get(
            f"/api/reports/artifacts/{report_id}/download", headers=self.outsider_headers
        )
        self.assertEqual(download.status_code, 404, "不应能下载其他租户的报表")

        delete = self.client.delete(
            f"/api/reports/artifacts/{report_id}", headers=self.outsider_headers
        )
        self.assertEqual(delete.status_code, 404, "不应能删除其他租户的报表")

    def test_05_delete_artifact_removes_file(self):
        created = self.client.post(
            "/api/reports/export",
            headers=self.owner_headers,
            json={"report_type": "risk", "format": "csv"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        report_id = int(created.headers["X-Report-Id"])

        db = SessionLocal()
        try:
            file_path = db.query(ReportArtifact).filter(
                ReportArtifact.id == report_id
            ).first().file_path
        finally:
            db.close()
        self.assertTrue(os.path.exists(file_path))

        deleted = self.client.delete(
            f"/api/reports/artifacts/{report_id}", headers=self.owner_headers
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertFalse(os.path.exists(file_path), "删除报表应同时清理磁盘文件")

        missing = self.client.get(
            f"/api/reports/artifacts/{report_id}/download", headers=self.owner_headers
        )
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
