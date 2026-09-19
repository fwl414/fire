"""CAD 图纸解析（DXF）接口测试

覆盖：
- 只支持 DXF：DWG 按文件头被识别并给出转换指引
- 解析失败如实报错——改造前这里会返回一份固定的假平面图并标 success，
  界面照样画出来、还能把假设备写进设备表
- 真实 DXF：按图层名提取墙/门/消防设备/房间，坐标归一化到 0-100
- 没识别到任何构件时明确报错，而不是"成功但空图"
- 图层名一并回传，用户能据此判断是不是图层命名没匹配上
- 图纸筛选脚本（tools/dxf_layer_report.py）与解析器用同一份图层约定
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
USERNAME = "cad-parse-tester"
ROLE_CODE = "cad-test-role"
BUILDING_CODE = "CADTEST-BLD-001"
# 上传文件统一用这个前缀，方便用例结束时清理
UPLOAD_PREFIX = "cadtest-"


def build_dxf_bytes(*, with_geometry: bool = True) -> bytes:
    """生成一份最小但真实的文本 DXF。"""
    doc = ezdxf.new("R2010")
    for name in ("WALL", "DOOR", "消防-烟感", "房间", "DOTE"):
        doc.layers.add(name)
    msp = doc.modelspace()
    if with_geometry:
        for i in range(12):
            msp.add_line((i * 1000, 0), (i * 1000, 30000), dxfattribs={"layer": "WALL"})
        msp.add_lwpolyline(
            [(0, 0), (11000, 0), (11000, 30000)], dxfattribs={"layer": "WALL"}
        )
        msp.add_line((3000, 30000), (4000, 30000), dxfattribs={"layer": "DOOR"})
        msp.add_circle((1000, 1000), 200, dxfattribs={"layer": "消防-烟感"})
        # 半径很小但不在设备图层上：不能凭尺寸猜成消防设备
        msp.add_circle((9000, 9000), 3, dxfattribs={"layer": "DOTE"})
        doc.blocks.new("烟感探测器")
        msp.add_blockref("烟感探测器", (5000, 5000))
        doc.blocks.new("灭火器")
        msp.add_blockref("灭火器", (7000, 5000))
        # 房间名要先于房间轮廓出现——解析器在遇到多段线时回头找已收集的文字
        msp.add_text("办公室", dxfattribs={"layer": "房间", "height": 300}).set_placement(
            (2500, 2500)
        )
        # 非墙图层的闭合多段线才会被当成房间
        msp.add_lwpolyline(
            [(1000, 1000), (5000, 1000), (5000, 4000), (1000, 4000)],
            dxfattribs={"layer": "房间"},
        )
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


class TestCadParse(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None
    floor_id = None
    _created_role_id = None
    _created_user_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

            role = db.query(Role).filter(Role.role_code == ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=ROLE_CODE,
                    role_name="CAD解析测试角色",
                    permissions=json.dumps([]),
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
                    real_name="CAD解析测试员",
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
                    building_name="CAD解析测试楼",
                    floors=1,
                )
                db.add(building)
                db.commit()
                db.refresh(building)

            floor = db.query(Floor).filter(Floor.building_id == building.id).first()
            if not floor:
                floor = Floor(
                    tenant_id=cls.tenant_id,
                    building_id=building.id,
                    floor_name="1层",
                    floor_number=1,
                )
                db.add(floor)
                db.commit()
                db.refresh(floor)
            cls.floor_id = floor.id
            cls._building_id = building.id
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
            # 清理用例上传的图纸：先删磁盘文件再删登记记录
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

            db.query(Floor).filter(Floor.building_id == cls._building_id).delete(
                synchronize_session=False
            )
            db.query(Building).filter(Building.id == cls._building_id).delete(
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

    def _upload(self, filename: str, content: bytes):
        return self.client.post(
            f"/api/cad/parse/{self.floor_id}",
            files={"file": (filename, content, "application/octet-stream")},
            headers=self.headers,
        )

    def _upload_dxf(self, *, with_geometry: bool = True):
        return self._upload(f"{UPLOAD_PREFIX}plan.dxf", build_dxf_bytes(with_geometry=with_geometry))

    # ---------------- 权限 ----------------

    def test_parse_requires_login(self):
        resp = self.client.post(
            f"/api/cad/parse/{self.floor_id}",
            files={"file": (f"{UPLOAD_PREFIX}x.dxf", build_dxf_bytes(), "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 401)

    # ---------------- 格式与失败处理 ----------------

    def test_dwg_is_rejected_with_conversion_hint(self):
        """DWG 读不了，必须明确让人去转换，而不是硬解析或返回假图。"""
        resp = self._upload(f"{UPLOAD_PREFIX}plan.dwg", b"AC1015" + b"\x00" * 128)
        self.assertEqual(resp.status_code, 400, resp.text)
        # 全局异常处理器把 HTTPException.detail 转成了 message
        detail = resp.json()["message"]
        self.assertIn("DXF", detail)
        self.assertIn("DWG", detail)
        self.assertIn("转换", detail)

    def test_corrupt_dxf_reports_error_instead_of_fake_plan(self):
        """改造前这里会返回一份固定的假平面图并标 success，这里守住它别再回来。"""
        # 内容里带 SECTION 以通过扩展名内容校验，再让 ezdxf 解析失败
        resp = self._upload(f"{UPLOAD_PREFIX}broken.dxf", b"0\nSECTION\n2\nGARBAGE\n")
        self.assertEqual(resp.status_code, 400, resp.text)
        body = resp.text
        self.assertIn("DXF", body)
        # 任何情况下都不能再出现演示/假数据兜底
        for forbidden in ("演示数据", "mock", "mock_cad"):
            self.assertNotIn(forbidden, body)

    # ---------------- 真实解析 ----------------

    def test_real_dxf_parses_walls_doors_devices_rooms(self):
        resp = self._upload_dxf()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        self.assertTrue(body["success"])
        stats = body["stats"]
        # 12 条竖墙 + 闭合多段线拆出的墙段，至少 12
        self.assertGreaterEqual(stats["wallCount"], 12)
        self.assertGreaterEqual(stats["doorCount"], 1)
        # 1 个圆 + 2 个设备块（烟感探测器、灭火器）
        self.assertGreaterEqual(stats["deviceCount"], 3)
        self.assertGreater(stats["roomCount"], 0)

        device_types = {d["type"] for d in body["devices"]}
        self.assertIn("smoke", device_types)
        self.assertIn("extinguisher", device_types)

        # 坐标必须归一化到 0-100 区间，前端按百分比画
        for wall in body["walls"]:
            for key in ("x1", "y1", "x2", "y2"):
                self.assertGreaterEqual(wall[key], 0)
                self.assertLessEqual(wall[key], 100)

    def test_small_circle_outside_device_layer_is_not_a_device(self):
        """只有设备图层上的圆才算设备，不能凭半径大小猜。"""
        resp = self._upload_dxf()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # 1 个设备图层圆 + 2 个设备块；DOTE 图层上的小圆不算
        self.assertEqual(body["stats"]["deviceCount"], 3)

    def test_response_carries_layer_names(self):
        """图层名是解析的唯一依据，要回传给用户便于排查命名不匹配。"""
        resp = self._upload_dxf()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("WALL", body["layers"])
        self.assertIn("消防-烟感", body["layers"])
        self.assertEqual(body["layerCount"], len(body["layers"]))

    def test_empty_drawing_is_not_reported_as_success(self):
        """有图层但没有几何：如实报错，不返回"成功但空图"。"""
        resp = self._upload_dxf(with_geometry=False)
        self.assertEqual(resp.status_code, 422, resp.text)
        detail = resp.json()["message"]
        self.assertIn("图层名", detail)

    def test_unknown_floor_returns_404(self):
        resp = self.client.post(
            "/api/cad/parse/99999999",
            files={"file": (f"{UPLOAD_PREFIX}x.dxf", build_dxf_bytes(), "application/octet-stream")},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 404)


class TestLayerReportTool(unittest.TestCase):
    """筛选脚本与解析器共用同一份图层约定，结果必须一致。

    脚本用来判断"哪张图纸能被解析"，如果它和解析器的约定不一致，
    筛出来的"可解析"图纸就是假的。
    """

    def setUp(self):
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.dxf_path = Path(self._tmp.name) / "plan.dxf"
        self.dxf_path.write_bytes(build_dxf_bytes())

    def tearDown(self):
        self._tmp.cleanup()

    def test_report_counts_match_parser(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
        from tools.dxf_layer_report import analyze_dxf

        report = analyze_dxf(self.dxf_path)
        self.assertEqual(report.status, "ok", report.message)
        self.assertGreaterEqual(report.wall_segments, 12)
        self.assertGreaterEqual(report.device_points, 3)
        self.assertGreater(report.room_texts, 0)
        # 判定要落在"可测"以上，不能是"未命中图层约定"
        self.assertGreater(report.rank, 0)
        self.assertNotIn("未命中", report.verdict)
        # 命中的图层要落到对应类别，用户才能知道是靠哪些图层识别出来的
        self.assertIn("WALL", report.layers_by_category["wall"])
        self.assertIn("消防-烟感", report.layers_by_category["device"])

    def test_report_flags_empty_drawing_as_not_matching(self):
        from tools.dxf_layer_report import analyze_dxf

        self.dxf_path.write_bytes(build_dxf_bytes(with_geometry=False))
        report = analyze_dxf(self.dxf_path)
        self.assertEqual(report.status, "ok")
        self.assertEqual(report.wall_segments, 0)
        self.assertIn("未命中", report.verdict)

    def test_report_marks_dwg_as_needing_conversion(self):
        from tools.dxf_layer_report import analyze_dxf

        dwg_path = self.dxf_path.with_suffix(".dwg")
        dwg_path.write_bytes(b"AC1015" + b"\x00" * 64)
        report = analyze_dxf(dwg_path)
        # analyze_dxf 只负责 DXF；DWG 由 collect() 提前分流，这里确认它不会硬解析成功
        self.assertNotEqual(report.status, "ok")


class TestPinyinLayerCodes(unittest.TestCase):
    """拼音缩写码（XF/XHS/PL/PT）只能按整段比对。

    国内施工图常用 2-4 个字母的缩写命名图层与图块。这类码如果用"包含"判断，
    `PT` 会命中 `POINT`、`PTEXT`，`PL` 会命中 `PLOT`，把无关实体当成消防设备。
    """

    def test_tokens_split_on_separators_and_drop_index_suffix(self):
        from services.cad_layer_rules import code_tokens

        self.assertEqual(code_tokens("P_XF_GJ"), ["P", "XF", "GJ"])
        self.assertEqual(code_tokens("_XHS2"), ["XHS"])
        self.assertEqual(code_tokens("0喷淋"), ["喷淋"])
        self.assertEqual(code_tokens(""), [])

    def test_fire_layer_and_block_codes_are_recognized(self):
        from services.cad_layer_rules import classify_layer, device_type_by_block, device_type_by_layer

        self.assertIn("device", classify_layer("P_XF_GJ"))
        self.assertIn("device", classify_layer("P_PL_DIM"))
        self.assertIn("device", classify_layer("PT"))
        # 消火栓图块 _XHS2 -> hydrant；喷头层 PT -> sprinkler
        self.assertEqual(device_type_by_block("_XHS2"), "hydrant")
        self.assertEqual(device_type_by_layer("PT"), "sprinkler")
        self.assertEqual(device_type_by_layer("P_PL_"), "sprinkler")

    def test_unrelated_names_do_not_match_short_codes(self):
        """`POINT`/`PTEXT`/`PLOT` 这类名字不能被 PT/PL 误命中。"""
        from services.cad_layer_rules import classify_layer, device_type_by_block, device_type_by_layer

        for name in ("POINT", "PTEXT", "PLOT", "SPLINE", "TEMPLATE", "SCRIPT"):
            self.assertNotIn("device", classify_layer(name), name)
            self.assertEqual(device_type_by_block(name), "", name)
            self.assertEqual(device_type_by_layer(name), "", name)


if __name__ == "__main__":
    unittest.main()
