"""历史导入图纸的查看与撤销接口测试

覆盖用户故事："导入错了，我要在界面上把那张图纸连同它带来的楼层和设备一起删掉"。

- 空楼层上导入图纸 → 记下来源，列表里能看到它关联的楼层
- 已有设备的楼层再导入图纸 → 不抢占来源（否则删图会误删已有楼层）
- 历史数据没有来源字段 → 退回按文件名匹配楼层
- 删除 → 楼层、楼层上的设备、上传记录、磁盘文件一起清掉
"""
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ezdxf
from fastapi.testclient import TestClient

import main
from database import (
    Building,
    Device,
    Floor,
    Role,
    SessionLocal,
    UploadedFile,
    User,
    get_default_tenant_id,
    hash_password,
    init_db,
)

PASSWORD = "Test#12345"
USERNAME = "imported-drawing-tester"
ROLE_CODE = "imported-drawing-test-role"
BUILDING_CODE = "IMPORTEDTEST-BLD-001"
UPLOAD_PREFIX = "importedtest-"


def build_dxf_bytes() -> bytes:
    """最小可解析 DXF：墙体、一个消防设备圆、一条房间文字。"""
    doc = ezdxf.new("R2010")
    for name in ("WALL", "消防-烟感", "房间"):
        doc.layers.add(name)
    msp = doc.modelspace()
    for i in range(4):
        msp.add_line((i * 1000, 0), (i * 1000, 20000), dxfattribs={"layer": "WALL"})
    msp.add_circle((1500, 1500), 200, dxfattribs={"layer": "消防-烟感"})
    msp.add_text("办公室", dxfattribs={"layer": "房间", "height": 300}).set_placement((1200, 1200))
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


class TestImportedDrawings(unittest.TestCase):
    client = None
    headers = {}
    tenant_id = None
    building_id = None
    _created_role_id = None
    _created_user_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

            # 删除接口要求 devices:manage，用 "*" 通配权限覆盖
            role = db.query(Role).filter(Role.role_code == ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=ROLE_CODE,
                    role_name="导入图纸测试角色",
                    permissions=json.dumps(["*"]),
                    is_system=False,
                )
                db.add(role)
                db.commit()
                db.refresh(role)
                cls._created_role_id = role.id

            user = db.query(User).filter(User.username == USERNAME).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(
                    username=USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="导入图纸测试员",
                    role_id=role.id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                cls._created_user_id = user.id

            building = db.query(Building).filter(Building.building_code == BUILDING_CODE).first()
            if not building:
                building = Building(
                    tenant_id=cls.tenant_id,
                    building_code=BUILDING_CODE,
                    building_name="导入图纸测试楼",
                    floors=1,
                )
                db.add(building)
                db.commit()
                db.refresh(building)
            cls.building_id = building.id
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
            from services.upload_archive_service import resolve_upload_path

            rows = db.query(UploadedFile).filter(
                UploadedFile.tenant_id == cls.tenant_id,
                UploadedFile.original_name.like(f"{UPLOAD_PREFIX}%"),
            ).all()
            for row in rows:
                resolved = resolve_upload_path(row)
                if resolved and resolved.exists():
                    resolved.unlink(missing_ok=True)
                db.delete(row)

            floor_ids = [f.id for f in db.query(Floor).filter(Floor.building_id == cls.building_id).all()]
            if floor_ids:
                db.query(Device).filter(Device.floor_id.in_(floor_ids)).delete(
                    synchronize_session=False
                )
            db.query(Floor).filter(Floor.building_id == cls.building_id).delete(
                synchronize_session=False
            )
            db.query(Building).filter(Building.id == cls.building_id).delete(
                synchronize_session=False
            )
            if cls._created_user_id:
                db.query(User).filter(User.id == cls._created_user_id).delete(
                    synchronize_session=False
                )
            if cls._created_role_id:
                db.query(Role).filter(Role.id == cls._created_role_id).delete(
                    synchronize_session=False
                )
            db.commit()
        finally:
            db.close()

    # ---------------- 工具 ----------------

    def _make_floor(self, name: str, number: int) -> int:
        db = SessionLocal()
        try:
            floor = Floor(
                tenant_id=self.tenant_id,
                building_id=self.building_id,
                floor_name=name,
                floor_number=number,
            )
            db.add(floor)
            db.commit()
            db.refresh(floor)
            return floor.id
        finally:
            db.close()

    def _parse(self, floor_id: int, filename: str):
        return self.client.post(
            f"/api/cad/parse/{floor_id}",
            files={"file": (filename, build_dxf_bytes(), "application/octet-stream")},
            headers=self.headers,
        )

    def _list(self):
        resp = self.client.get(
            f"/api/buildings/{self.building_id}/imported-drawings", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["items"]

    def _delete(self, upload_id: int):
        return self.client.delete(
            f"/api/buildings/{self.building_id}/imported-drawings/{upload_id}",
            headers=self.headers,
        )

    # ---------------- 来源记录 ----------------

    def test_empty_floor_import_records_source(self):
        floor_id = self._make_floor(f"{UPLOAD_PREFIX}空楼层", 900)
        resp = self._parse(floor_id, f"{UPLOAD_PREFIX}空楼层.dxf")
        self.assertEqual(resp.status_code, 200, resp.text)

        db = SessionLocal()
        try:
            floor = db.query(Floor).filter(Floor.id == floor_id).first()
            self.assertIsNotNone(floor.source_upload_id)
        finally:
            db.close()

        items = [i for i in self._list() if i["floor_id"] == floor_id]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["floor_name"], f"{UPLOAD_PREFIX}空楼层")

    def test_import_into_floor_with_devices_keeps_source_empty(self):
        """已有设备的楼层是"已有楼层"，不能把新图纸记成它的来源。"""
        floor_id = self._make_floor(f"{UPLOAD_PREFIX}有设备楼层", 901)
        db = SessionLocal()
        try:
            db.add(Device(
                tenant_id=self.tenant_id,
                device_code=f"{UPLOAD_PREFIX}D-001",
                device_name="既有设备",
                device_type="烟感探测器",
                building_id=self.building_id,
                floor_id=floor_id,
                status="正常",
            ))
            db.commit()
        finally:
            db.close()

        resp = self._parse(floor_id, f"{UPLOAD_PREFIX}有设备楼层.dxf")
        self.assertEqual(resp.status_code, 200, resp.text)

        db = SessionLocal()
        try:
            floor = db.query(Floor).filter(Floor.id == floor_id).first()
            self.assertIsNone(floor.source_upload_id)
        finally:
            db.close()

    def test_legacy_upload_without_source_matches_by_filename(self):
        """历史数据没有来源字段：按文件名（导入时楼层名取自 DXF 文件名）兜底匹配。"""
        name = f"{UPLOAD_PREFIX}legacy"
        floor_id = self._make_floor(name, 902)

        db = SessionLocal()
        try:
            record = UploadedFile(
                tenant_id=self.tenant_id,
                category="cad",
                filename=f"{name}.dxf",
                original_name=f"{name}.dxf",
                media_type="application/octet-stream",
                size_bytes=1,
                sha256="0" * 64,
                owner_name="legacy",
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            upload_id = record.id
        finally:
            db.close()

        items = [i for i in self._list() if i["id"] == upload_id]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["floor_id"], floor_id)

    # ---------------- 删除 ----------------

    def test_delete_removes_floor_devices_and_file(self):
        floor_id = self._make_floor(f"{UPLOAD_PREFIX}待删除楼层", 903)
        resp = self._parse(floor_id, f"{UPLOAD_PREFIX}待删除楼层.dxf")
        self.assertEqual(resp.status_code, 200, resp.text)
        parsed_devices = resp.json()["devices"]
        self.assertGreater(len(parsed_devices), 0)

        imported = self.client.post(
            f"/api/cad/import-devices/{floor_id}", json=parsed_devices, headers=self.headers
        )
        self.assertEqual(imported.status_code, 200, imported.text)

        item = [i for i in self._list() if i["floor_id"] == floor_id][0]
        self.assertGreater(item["device_count"], 0)

        db = SessionLocal()
        try:
            from services.upload_archive_service import resolve_upload_path

            record = db.query(UploadedFile).filter(UploadedFile.id == item["id"]).first()
            file_path = resolve_upload_path(record)
            self.assertIsNotNone(file_path)
            self.assertTrue(file_path.exists())
        finally:
            db.close()

        resp = self._delete(item["id"])
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["removed_floor"], f"{UPLOAD_PREFIX}待删除楼层")
        self.assertGreater(body["removed_devices"], 0)

        db = SessionLocal()
        try:
            self.assertIsNone(db.query(Floor).filter(Floor.id == floor_id).first())
            self.assertEqual(
                db.query(Device).filter(Device.floor_id == floor_id).count(), 0
            )
            self.assertIsNone(db.query(UploadedFile).filter(UploadedFile.id == item["id"]).first())
        finally:
            db.close()

        self.assertFalse(file_path.exists())
        self.assertNotIn(item["id"], [i["id"] for i in self._list()])

    def test_delete_unknown_upload_returns_404(self):
        self.assertEqual(self._delete(99999999).status_code, 404)


if __name__ == "__main__":
    unittest.main()
