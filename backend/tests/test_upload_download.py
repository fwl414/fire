"""上传文件受控下载的集成测试。

覆盖：
- 楼层平面图上传后返回受控地址，不再写入可匿名访问的 static 目录
- /static 静态挂载已移除（匿名访问上传内容返回 404）
- 受控下载需登录且按租户隔离（其他租户 404、匿名 401）
- 兼容旧链接的 /api/uploads/{category}/{filename} 亦做租户校验
- 文件清单与删除
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    Building,
    Floor,
    Role,
    SessionLocal,
    Tenant,
    UploadedFile,
    User,
    hash_password,
    init_db,
    get_default_tenant_id,
)
from services.upload_archive_service import UPLOAD_ROOT, resolve_upload_path

OWNER = "upload-owner"
OUTSIDER = "upload-outsider"
PASSWORD = "Test#12345"

# 最小合法 PNG 头，满足内容特征校验
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class TestUploadDownload(unittest.TestCase):

    client = None
    owner_tenant_id = None
    outsider_tenant_id = None
    floor_id = None
    building_id = None
    created_user_ids = []
    created_role_id = None
    created_tenant_id = None
    # 本用例造出来的上传记录（owner 就是默认租户，清理必须按 id 精确删除）
    uploaded_id = None
    legacy_id = None

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

            outsider = Tenant(tenant_code="upload-outsider", tenant_name="上传隔离租户")
            db.add(outsider)
            db.commit()
            cls.outsider_tenant_id = outsider.id
            cls.created_tenant_id = outsider.id

            for username, tenant_id in ((OWNER, cls.owner_tenant_id), (OUTSIDER, cls.outsider_tenant_id)):
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

            building = Building(
                tenant_id=cls.owner_tenant_id,
                building_code="UP-TEST-BLD",
                building_name="上传测试楼",
            )
            db.add(building)
            db.commit()
            db.refresh(building)
            cls.building_id = building.id

            floor = Floor(
                tenant_id=cls.owner_tenant_id,
                building_id=building.id,
                floor_name="上传测试层",
                floor_number=98,
            )
            db.add(floor)
            db.commit()
            db.refresh(floor)
            cls.floor_id = floor.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        cls.owner_headers = cls._login(OWNER)
        cls.outsider_headers = cls._login(OUTSIDER)

    @classmethod
    def _login(cls, username):
        resp = cls.client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
        assert resp.status_code == 200, f"{username} 登录失败: {resp.text}"
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        # owner 用的是默认租户，所以只能删本用例造出来的那几条记录。
        # 早先这里按租户整体删 uploaded_files、并 rmtree 上传目录，
        # 会把开发库里真实导入的图纸记录和文件一起清掉。
        db = SessionLocal()
        try:
            created_ids = [i for i in (cls.uploaded_id, cls.legacy_id) if i]
            if created_ids:
                for record in db.query(UploadedFile).filter(UploadedFile.id.in_(created_ids)).all():
                    resolved = resolve_upload_path(record)
                    if resolved and resolved.exists():
                        resolved.unlink(missing_ok=True)
                    db.delete(record)

            # 隔离租户是本用例新建的，整体清理不会碰到真实数据
            db.query(UploadedFile).filter(
                UploadedFile.tenant_id == cls.outsider_tenant_id
            ).delete(synchronize_session=False)
            db.query(Floor).filter(Floor.id == cls.floor_id).delete(synchronize_session=False)
            db.query(Building).filter(Building.id == cls.building_id).delete(synchronize_session=False)
            if cls.created_user_ids:
                db.query(User).filter(User.id.in_(cls.created_user_ids)).delete(synchronize_session=False)
            if cls.created_tenant_id:
                db.query(Tenant).filter(Tenant.id == cls.created_tenant_id).delete(synchronize_session=False)
            if cls.created_role_id:
                db.query(Role).filter(Role.id == cls.created_role_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    # ---------------- 用例 ----------------

    def test_01_static_mount_is_gone(self):
        """上传内容不得再通过静态目录匿名访问。"""
        resp = self.client.get("/static/floor_plans/anything.png")
        self.assertEqual(resp.status_code, 404, "静态目录不应再暴露")

    def test_02_upload_returns_controlled_url(self):
        resp = self.client.post(
            f"/api/floors/{self.floor_id}/plan",
            headers=self.owner_headers,
            files={"file": ("plan.png", io.BytesIO(PNG_BYTES), "image/png")},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["image_url"].startswith("/api/files/"), body["image_url"])
        self.assertNotIn("/static/", body["image_url"])

        file_id = body["file_id"]
        db = SessionLocal()
        try:
            record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
            self.assertEqual(record.tenant_id, self.owner_tenant_id)
            self.assertEqual(record.category, "floor_plan")
            self.assertTrue(record.sha256)
            self.assertIn(os.path.abspath(str(UPLOAD_ROOT)), os.path.abspath(record.file_path))
        finally:
            db.close()

        # 楼层详情返回的仍是受控地址
        detail = self.client.get(f"/api/floors/{self.floor_id}", headers=self.owner_headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertTrue(detail.json()["floor_plan_image"].startswith("/api/files/"))

        self.__class__.uploaded_id = file_id

    def test_03_download_is_authenticated_and_tenant_scoped(self):
        file_id = self.uploaded_id

        anonymous = self.client.get(f"/api/files/{file_id}")
        self.assertEqual(anonymous.status_code, 401, "匿名不应能下载上传内容")

        owner = self.client.get(f"/api/files/{file_id}", headers=self.owner_headers)
        self.assertEqual(owner.status_code, 200, owner.text)
        self.assertEqual(owner.content, PNG_BYTES, "下载内容应与上传一致")

        outsider = self.client.get(f"/api/files/{file_id}", headers=self.outsider_headers)
        self.assertEqual(outsider.status_code, 404, "不应能下载其他租户的上传内容")

        outsider_list = self.client.get("/api/files", headers=self.outsider_headers)
        self.assertEqual(outsider_list.status_code, 200)
        self.assertNotIn(file_id, [item["id"] for item in outsider_list.json()["items"]])

    def test_04_legacy_upload_endpoint_is_tenant_scoped(self):
        """兼容旧链接的 /api/uploads/cad/{filename} 也必须校验租户。"""
        db = SessionLocal()
        try:
            record = UploadedFile(
                tenant_id=self.owner_tenant_id,
                category="cad",
                filename="legacy-plan.dxf",
                original_name="legacy-plan.dxf",
                file_path=str(UPLOAD_ROOT / "cad" / "legacy-plan.dxf"),
                media_type="application/octet-stream",
                size_bytes=4,
            )
            (UPLOAD_ROOT / "cad").mkdir(parents=True, exist_ok=True)
            (UPLOAD_ROOT / "cad" / "legacy-plan.dxf").write_bytes(b"0\nSECTION\n")
            db.add(record)
            db.commit()
            db.refresh(record)
            legacy_id = record.id
        finally:
            db.close()

        owner = self.client.get("/api/uploads/cad/legacy-plan.dxf", headers=self.owner_headers)
        self.assertEqual(owner.status_code, 200, owner.text)

        outsider = self.client.get("/api/uploads/cad/legacy-plan.dxf", headers=self.outsider_headers)
        self.assertEqual(outsider.status_code, 404, "旧链接也不得跨租户读取")

        # 路径穿越尝试
        traversal = self.client.get(
            "/api/uploads/cad/%2e%2e%2f%2e%2e%2fmain.py", headers=self.owner_headers
        )
        self.assertEqual(traversal.status_code, 404)

        self.__class__.legacy_id = legacy_id

    def test_05_delete_removes_file(self):
        file_id = self.uploaded_id
        db = SessionLocal()
        try:
            path = db.query(UploadedFile).filter(UploadedFile.id == file_id).first().file_path
        finally:
            db.close()
        self.assertTrue(os.path.exists(path))

        deleted = self.client.delete(f"/api/files/{file_id}", headers=self.owner_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertFalse(os.path.exists(path), "删除应同时清理磁盘文件")

        missing = self.client.get(f"/api/files/{file_id}", headers=self.owner_headers)
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
