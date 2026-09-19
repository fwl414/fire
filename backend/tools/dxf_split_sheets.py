#!/usr/bin/env python
"""把一份"全套图" DXF 按图框拆成单张图纸。

为什么需要：施工图常把整套图平铺在同一个模型空间里（一层~五层平面图、各系统图、
剖面图、图例……十几张并排摆放）。系统按"一个 DXF = 一个楼层"解析，
整份导入会把所有楼层混成一层，而且归一化基准会覆盖整张布局，点位挤成一团。

拆分依据（按可靠性排序）：
1. **图框矩形**（首选）。图框是一组"尺寸相同、互不重叠"的大矩形，
   可靠且边界精确。图框也可能是图块（INSERT），本脚本两种都认。
2. **空白带**（兜底）。没有图框时，按实体投影的空白列/行带切分，
   空白宽度用 --gap 指定（图纸单位）。

每张拆出的图纸会用图名（"一层喷淋平面图"之类）命名，便于直接当楼层名用。

用法：

    # 只看会拆成几张、各自叫什么
    python tools/dxf_split_sheets.py "全套图.dxf" --out "输出目录" --dry-run

    # 实际拆分
    python tools/dxf_split_sheets.py "全套图.dxf" --out "输出目录"

    # 没有图框时用空白带兜底，并指定空白宽度
    python tools/dxf_split_sheets.py "全套图.dxf" --out "输出目录" --no-frame --gap 8000
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import ezdxf
from ezdxf.addons import Importer

# 图名关键字：带这些词的文字通常就是图纸标题
TITLE_KEYWORDS = (
    "平面图", "系统图", "详图", "剖面图", "大样", "图例", "原理图",
    "轴测图", "设计说明", "施工说明", "材料表", "设备表", "节点图",
)
# 图块名里带这些词的，视为图框块
FRAME_BLOCK_KEYWORDS = ("图框", "图签", "TITLE", "FRAME", "BORDER", "A0", "A1", "A2", "A3", "A4")

# 认定图框的阈值（相对整张布局）
FRAME_MIN_AREA_RATIO = 0.01      # 图框面积至少占布局外接框的 1%
FRAME_MIN_SIDE_RATIO = 0.10      # 图框短边至少占布局短边的 10%

_FILENAME_BAD_RE = re.compile(r'[\\/:*?"<>|\s]+')


@dataclass
class Region:
    """一张图纸的区域。"""
    x0: float
    y0: float
    x1: float
    y1: float
    source: str = "frame"                 # frame / gap
    title: str = ""
    entities: list = field(default_factory=list)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (self.x0 - margin) <= x <= (self.x1 + margin) and (self.y0 - margin) <= y <= (self.y1 + margin)

    def overlaps(self, other: "Region") -> float:
        """返回与另一区域的重叠面积占较小者面积的比例。"""
        ox = min(self.x1, other.x1) - max(self.x0, other.x0)
        oy = min(self.y1, other.y1) - max(self.y0, other.y0)
        if ox <= 0 or oy <= 0:
            return 0.0
        smaller = min(self.area, other.area)
        return (ox * oy) / smaller if smaller else 0.0


# ---------------- 实体取点 ----------------

def entity_points(entity) -> List[Tuple[float, float]]:
    """取实体的代表点，用于判断它属于哪张图纸。"""
    try:
        t = entity.dxftype()
        if t == "LINE":
            s, e = entity.dxf.start, entity.dxf.end
            return [(s[0], s[1]), ((s[0] + e[0]) / 2, (s[1] + e[1]) / 2), (e[0], e[1])]
        if t in ("CIRCLE", "ARC"):
            c = entity.dxf.center
            return [(c[0], c[1])]
        if t == "INSERT":
            p = entity.dxf.insert
            return [(p[0], p[1])]
        if t in ("TEXT", "MTEXT"):
            p = getattr(entity.dxf, "insert", None)
            return [(p[0], p[1])] if p else []
        if t in ("LWPOLYLINE", "POLYLINE"):
            return [(p[0], p[1]) for p in (entity.get_points() if hasattr(entity, "get_points") else [])]
        if t == "DIMENSION":
            p = getattr(entity.dxf, "defpoint", None)
            return [(p[0], p[1])] if p else []
    except Exception:
        return []
    return []


def entity_center(entity) -> Optional[Tuple[float, float]]:
    """代表点的均值；没有点则用外接框中心。"""
    pts = entity_points(entity)
    if pts:
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    try:
        box = ezdxf.bbox.extents([entity])
        if box.has_data:
            return ((box.extmin.x + box.extmax.x) / 2, (box.extmin.y + box.extmax.y) / 2)
    except Exception:
        pass
    return None


# ---------------- 图框识别 ----------------

def rect_of(entity) -> Optional[Tuple[float, float, float, float]]:
    """若实体是轴对齐矩形，返回 (x0, y0, w, h)，否则 None。"""
    try:
        if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
            return None
        pts = [(p[0], p[1]) for p in entity.get_points()]
        if len(pts) not in (4, 5):
            return None
        pts = pts[:4]
        xs = sorted({round(x) for x, _ in pts})
        ys = sorted({round(y) for _, y in pts})
        if len(xs) != 2 or len(ys) != 2:
            return None
        w, h = xs[1] - xs[0], ys[1] - ys[0]
        if w <= 0 or h <= 0:
            return None
        return (xs[0], ys[0], w, h)
    except Exception:
        return None


def block_frame_rect(entity) -> Optional[Tuple[float, float, float, float]]:
    """图框块的插入范围。"""
    try:
        if entity.dxftype() != "INSERT":
            return None
        name = (entity.dxf.name or "").upper()
        if not any(kw.upper() in name for kw in FRAME_BLOCK_KEYWORDS):
            return None
        box = ezdxf.bbox.extents([entity])
        if not box.has_data:
            return None
        return (box.extmin.x, box.extmin.y, box.extmax.x - box.extmin.x, box.extmax.y - box.extmin.y)
    except Exception:
        return None


def find_frames(doc) -> List[Region]:
    """识别图框。要求：够大、互不重叠（防止把图内的建筑轮廓当成图框）。"""
    msp = doc.modelspace()

    xs, ys = [], []
    for e in msp:
        for p in entity_points(e):
            xs.append(p[0]); ys.append(p[1])
    if not xs:
        return []
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    min_area = span_x * span_y * FRAME_MIN_AREA_RATIO
    min_side = min(span_x, span_y) * FRAME_MIN_SIDE_RATIO

    candidates: List[Tuple[float, float, float, float]] = []
    for e in msp:
        for rect in (rect_of(e), block_frame_rect(e)):
            if not rect:
                continue
            x0, y0, w, h = rect
            if w * h < min_area or min(w, h) < min_side:
                continue
            candidates.append(rect)

    # 大者优先；与已接受图框明显重叠的丢弃（图内的建筑轮廓会被这一步筛掉）
    candidates.sort(key=lambda r: r[2] * r[3], reverse=True)
    frames: List[Region] = []
    for x0, y0, w, h in candidates:
        region = Region(x0, y0, x0 + w, y0 + h)
        if any(region.overlaps(f) > 0.2 for f in frames):
            continue
        frames.append(region)
    # 按从左到右、从上到下排序，编号更符合阅读习惯
    frames.sort(key=lambda r: (round(r.y0, -3), r.x0))
    return frames


# ---------------- 空白带兜底 ----------------

def split_by_gaps(doc, gap: float, grid: int = 400) -> List[Region]:
    """没有图框时：按投影的空白列/行带递归切分。"""
    msp = doc.modelspace()
    points: List[Tuple[float, float]] = []
    for e in msp:
        points.extend(entity_points(e))
    if not points:
        return []

    def empty_bands(pts: Sequence[Tuple[float, float]], axis: int) -> List[Tuple[float, float]]:
        """返回该轴上宽度 >= gap 的空白带。"""
        lo = min(p[axis] for p in pts)
        hi = max(p[axis] for p in pts)
        if hi - lo <= gap:
            return []
        cell = (hi - lo) / grid
        occupied = [False] * grid
        for p in pts:
            occupied[min(grid - 1, int((p[axis] - lo) / cell))] = True
        bands: List[Tuple[float, float]] = []
        start = None
        for i, used in enumerate(occupied):
            if not used:
                if start is None:
                    start = i
            elif start is not None:
                if (i - start) * cell >= gap:
                    bands.append((lo + start * cell, lo + i * cell))
                start = None
        if start is not None and (grid - start) * cell >= gap:
            bands.append((lo + start * cell, hi))
        return bands

    def partition(pts, axis, bands):
        groups = []
        prev = min(p[axis] for p in pts)
        for a, b in bands:
            groups.append([p for p in pts if prev <= p[axis] < a])
            prev = b
        groups.append([p for p in pts if p[axis] >= prev])
        return [g for g in groups if g]

    def split(pts: List[Tuple[float, float]], depth: int = 0) -> List[List[Tuple[float, float]]]:
        if len(pts) < 2 or depth >= 6:
            return [pts]
        # 先按 x 找空白带，找不到再按 y
        for axis in (0, 1):
            bands = empty_bands(pts, axis)
            if not bands:
                continue
            out: List[List[Tuple[float, float]]] = []
            for group in partition(pts, axis, bands):
                out.extend(split(group, depth + 1))
            return out
        return [pts]

    regions: List[Region] = []
    for part in split(points):
        px = [p[0] for p in part]
        py = [p[1] for p in part]
        regions.append(Region(min(px), min(py), max(px), max(py), source="gap"))
    regions.sort(key=lambda r: (round(r.y0, -3), r.x0))
    return regions


# ---------------- 图名 ----------------

def region_title(region: Region, msp) -> str:
    """在区域内找图名：取"带图名关键字、字高最大"的那条文字。"""
    best = None
    best_score = -1.0
    margin = min(region.width, region.height) * 0.15
    for e in msp:
        try:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            pts = entity_points(e)
            if not pts or not region.contains(pts[0][0], pts[0][1], margin):
                continue
            text = (e.dxf.text if hasattr(e.dxf, "text") else str(getattr(e, "text", ""))).strip()
            if not text or len(text) > 30:
                continue
            if not any(kw in text for kw in TITLE_KEYWORDS):
                continue
            height = float(getattr(e.dxf, "height", 0) or 0)
            score = height * 1000 + len(text)
            if score > best_score:
                best, best_score = text, score
        except Exception:
            continue
    return best or ""


def safe_name(text: str, fallback: str) -> str:
    cleaned = _FILENAME_BAD_RE.sub("_", (text or "").strip())
    cleaned = cleaned.strip("_")
    return cleaned or fallback


# ---------------- 主流程 ----------------

def assign_entities(regions: List[Region], msp) -> int:
    """把实体分派到各区域，返回未归属的实体数。"""
    margin = min(r.width for r in regions) * 0.02 if regions else 0.0
    unassigned = 0
    for e in msp:
        center = entity_center(e)
        if center is None:
            unassigned += 1
            continue
        for r in regions:
            if r.contains(center[0], center[1], margin):
                r.entities.append(e)
                break
        else:
            unassigned += 1
    return unassigned


def export_region(source_doc, region: Region, out_path: Path) -> None:
    target = ezdxf.new(source_doc.dxfversion)
    importer = Importer(source_doc, target)
    importer.import_entities(region.entities, target.modelspace())
    importer.finalize()
    target.saveas(str(out_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="把全套图 DXF 按图框拆成单张图纸")
    parser.add_argument("dxf", help="含多张图纸的 DXF")
    parser.add_argument("--out", help="输出目录（默认：与源文件同级的 <文件名>_sheets）")
    parser.add_argument("--no-frame", action="store_true", help="不使用图框，强制按空白带拆分")
    parser.add_argument("--gap", type=float, default=6000.0,
                        help="空白带拆分时认定的图纸间空白宽度（图纸单位，默认 6000）")
    parser.add_argument("--min-entities", type=int, default=20, help="实体数少于此值的区域忽略（默认 20）")
    parser.add_argument("--dry-run", action="store_true", help="只列出拆分结果，不写文件")
    args = parser.parse_args()

    src = Path(args.dxf).expanduser()
    if not src.is_file():
        print(f"文件不存在：{src}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser() if args.out else src.parent / f"{src.stem}_sheets"

    print(f"读取 {src.name} ...")
    doc = ezdxf.readfile(str(src))
    msp = doc.modelspace()
    total = len(msp)
    print(f"  模型空间实体 {total} 个")

    regions: List[Region] = []
    if not args.no_frame:
        regions = find_frames(doc)
        print(f"  识别到图框 {len(regions)} 个")
    if not regions:
        print("  未识别到图框，改用空白带拆分")
        regions = split_by_gaps(doc, args.gap)
        print(f"  空白带拆分出 {len(regions)} 个区域")

    if not regions:
        print("没有任何区域可拆，退出。", file=sys.stderr)
        return 1

    unassigned = assign_entities(regions, msp)

    print(f"\n{'#':>3} {'图名':<26} {'实体数':>7} {'区域尺寸':>22}")
    print("-" * 66)
    kept: List[Region] = []
    for i, r in enumerate(regions, start=1):
        r.title = region_title(r, msp)
        size = f"{r.width:.0f} × {r.height:.0f}"
        flag = "" if len(r.entities) >= args.min_entities else "  (跳过：实体过少)"
        print(f"{i:>3} {(r.title or '(无图名)'):<26} {len(r.entities):>7} {size:>22}{flag}")
        if len(r.entities) >= args.min_entities:
            kept.append(r)

    print(f"\n未归属到任何区域的实体：{unassigned} 个")
    print(f"将输出 {len(kept)} 张图纸")

    if args.dry_run:
        print("\n--dry-run：只列结果，未写文件。")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    print()
    for i, r in enumerate(kept, start=1):
        name = safe_name(r.title, f"sheet_{i:02d}")
        path = out_dir / f"{i:02d}_{name}.dxf"
        export_region(doc, r, path)
        print(f"  写出 {path.name}（{len(r.entities)} 实体，图名：{r.title or '无'}）")

    print(f"\n完成，输出目录：{out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
