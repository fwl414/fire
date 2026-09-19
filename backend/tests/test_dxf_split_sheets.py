"""全套图拆分脚本（tools/dxf_split_sheets.py）的测试

施工图常把十几张图纸平铺在同一个模型空间里，系统按"一个 DXF = 一个楼层"解析，
所以要先按图框拆开。这里测的是拆分的关键判断：

- 图框识别：只认"够大且互不重叠"的矩形，图内的建筑轮廓/门窗方框不能当成图框
- 实体归属：每个实体只能落进一个区域，不能重复也不能丢
- 图名提取：拆出的图纸要用图名命名，才能直接当楼层名
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ezdxf  # noqa: E402

from tools import dxf_split_sheets as split  # noqa: E402


def build_multi_sheet_dxf() -> "ezdxf.document.Drawing":
    """两份图框并排，各自有墙线、喷头和图名；另外放一个门窗大小的方框当干扰。"""
    doc = ezdxf.new("R2010")
    for name in ("WIRE", "WALL", "PT", "TEXT"):
        doc.layers.add(name)
    msp = doc.modelspace()

    # 两个等尺寸图框（20000 × 30000），左右并排
    for x0 in (0, 40000):
        msp.add_lwpolyline(
            [(x0, 0), (x0 + 20000, 0), (x0 + 20000, 30000), (x0, 30000)],
            close=True,
            dxfattribs={"layer": "WIRE"},
        )

    # 图框 A：3 段墙 + 2 个喷头 + 图名
    for i in range(3):
        msp.add_line((1000 + i * 500, 1000), (1000 + i * 500, 20000), dxfattribs={"layer": "WALL"})
    msp.add_circle((3000, 3000), 125, dxfattribs={"layer": "PT"})
    msp.add_circle((5000, 3000), 125, dxfattribs={"layer": "PT"})
    msp.add_text("一层喷淋平面图", height=300, dxfattribs={"layer": "TEXT"}).set_placement((9000, 500))

    # 图框 B：1 段墙 + 1 个喷头 + 图名
    msp.add_line((41000, 1000), (41000, 20000), dxfattribs={"layer": "WALL"})
    msp.add_circle((43000, 3000), 125, dxfattribs={"layer": "PT"})
    msp.add_text("二层给排水平面图", height=300, dxfattribs={"layer": "TEXT"}).set_placement((49000, 500))

    # 干扰项：门窗大小的小方框，面积远小于图框，不能被当成图框
    msp.add_lwpolyline(
        [(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)],
        close=True,
        dxfattribs={"layer": "WALL"},
    )
    return doc


class TestRectDetection(unittest.TestCase):
    def test_axis_aligned_rectangle_is_recognized(self):
        doc = ezdxf.new("R2010")
        rect = doc.modelspace().add_lwpolyline(
            [(0, 0), (100, 0), (100, 50), (0, 50)], close=True
        )
        self.assertEqual(split.rect_of(rect), (0, 0, 100, 50))

    def test_non_rectangle_is_rejected(self):
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        triangle = msp.add_lwpolyline([(0, 0), (100, 0), (50, 80)], close=True)
        self.assertIsNone(split.rect_of(triangle))
        # 闭合但斜边的四边形也不算轴对齐矩形
        slanted = msp.add_lwpolyline([(0, 0), (100, 0), (120, 50), (0, 50)], close=True)
        self.assertIsNone(split.rect_of(slanted))


class TestFindFrames(unittest.TestCase):
    def test_finds_both_sheets_and_ignores_small_box(self):
        doc = build_multi_sheet_dxf()
        frames = split.find_frames(doc)
        self.assertEqual(len(frames), 2)
        # 左右各一个，尺寸一致
        self.assertAlmostEqual(frames[0].width, 20000, places=0)
        self.assertAlmostEqual(frames[1].width, 20000, places=0)
        self.assertLess(frames[0].x0, frames[1].x0)

    def test_entities_go_to_exactly_one_region(self):
        doc = build_multi_sheet_dxf()
        frames = split.find_frames(doc)
        unassigned = split.assign_entities(frames, doc.modelspace())
        self.assertEqual(unassigned, 0)
        counts = sorted(len(f.entities) for f in frames)
        # 图框 A：图框自身 + 3 墙 + 2 喷头 + 1 图名 + 1 小方框 = 8
        # 图框 B：图框自身 + 1 墙 + 1 喷头 + 1 图名 = 4
        self.assertEqual(counts, [4, 8])


class TestTitleAndNaming(unittest.TestCase):
    def test_title_is_taken_from_inside_region(self):
        doc = build_multi_sheet_dxf()
        frames = split.find_frames(doc)
        titles = [split.region_title(f, doc.modelspace()) for f in frames]
        self.assertEqual(titles, ["一层喷淋平面图", "二层给排水平面图"])

    def test_safe_name_strips_path_and_space(self):
        self.assertEqual(split.safe_name("一层/喷淋 平面图", "x"), "一层_喷淋_平面图")
        self.assertEqual(split.safe_name("", "sheet_01"), "sheet_01")


class TestExport(unittest.TestCase):
    def test_exported_sheet_has_only_its_own_entities(self):
        doc = build_multi_sheet_dxf()
        frames = split.find_frames(doc)
        split.assign_entities(frames, doc.modelspace())

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "01.dxf"
            split.export_region(doc, frames[0], out)
            self.assertTrue(out.is_file())

            exported = ezdxf.readfile(str(out))
            msp = exported.modelspace()
            circles = [e for e in msp if e.dxftype() == "CIRCLE"]
            lines = [e for e in msp if e.dxftype() == "LINE"]
            # 图框 A 的 2 个喷头、3 段墙都在；图框 B 的 1 个喷头不能跟过来
            self.assertEqual(len(circles), 2)
            self.assertEqual(len(lines), 3)
            self.assertIn("PT", {e.dxf.layer for e in msp})


if __name__ == "__main__":
    unittest.main()
