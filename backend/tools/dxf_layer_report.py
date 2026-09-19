#!/usr/bin/env python
"""批量查看 DXF 图纸的图层与构件，筛出适合做 CAD 导入测试的图纸。

回答的是一个很具体的问题：**一堆图纸里，哪些真的能被解析出建筑构件？**

`/api/cad/parse` 完全靠图层名识别墙、门、消防设备、房间，所以一张"看起来正常"
的建筑平面图未必解析得出来——图层名不匹配就什么都提不出来。这个脚本把每张图的
图层名与构件数摊开，再给一个可解析性判定，避免靠文件名猜。

用法：

    # 扫描目录（递归），看全部图纸的可解析性
    python tools/dxf_layer_report.py "F:/cad/某目录"

    # 只看墙段数 >= 50 的，取前 20 行，并导出 CSV
    python tools/dxf_layer_report.py "F:/cad/某目录" --min-walls 50 --top 20 --csv report.csv

    # 看某几类图层分别命中了什么（排查"为什么没解析出来"）
    python tools/dxf_layer_report.py "F:/cad/某目录" --detail

关于 DWG：ezdxf 读不了 DWG（AutoCAD 二进制格式），本脚本会把 .dwg 单独列出来
并标记"需先转 DXF"，不会去硬解析。可以用 ODA File Converter 批量转换后再跑本脚本。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# 让脚本能直接 import 后端模块（脚本位于 backend/tools/）
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.cad_layer_rules import (  # noqa: E402
    CATEGORY_LABELS,
    classify_layer,
    convention_hint,
    device_type_by_block,
)

# DWG 文件头（AutoCAD 各版本都是 AC10xx）
DWG_MAGIC_PREFIX = b"AC10"

GEOMETRY_TYPES = {"LINE", "CIRCLE", "INSERT", "LWPOLYLINE", "POLYLINE"}
TEXT_TYPES = {"TEXT", "MTEXT"}
# 解析器只收长度 <= 20 的文字当房间名，这里保持一致
MAX_ROOM_TEXT_LENGTH = 20


@dataclass
class DrawingReport:
    path: Path
    status: str = "ok"                 # ok / dwg / error
    message: str = ""
    layer_count: int = 0
    layers: List[str] = field(default_factory=list)
    entity_count: int = 0
    wall_segments: int = 0
    device_points: int = 0
    room_texts: int = 0
    door_segments: int = 0
    layers_by_category: Dict[str, List[str]] = field(default_factory=dict)
    device_types: Dict[str, int] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if self.status == "dwg":
            return "需先转 DXF"
        if self.status == "error":
            return f"解析失败：{self.message}"
        if self.wall_segments >= 50 and self.device_points >= 1:
            return "★★★ 推荐（墙线+设备）"
        if self.wall_segments >= 50:
            return "★★★ 推荐（墙线+房间）"
        if self.wall_segments >= 10:
            return "★★ 可测墙线"
        if self.wall_segments > 0:
            return "★ 构件很少"
        return "☆ 未命中图层约定"

    @property
    def rank(self) -> int:
        """排序用：数值越大越值得先测。"""
        if self.status != "ok":
            return -1
        score = 0
        if self.wall_segments >= 50:
            score += 100
        elif self.wall_segments >= 10:
            score += 50
        elif self.wall_segments > 0:
            score += 10
        if self.device_points:
            score += 30
        if self.room_texts:
            score += 10
        return score


def _is_dwg_file(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(4) == DWG_MAGIC_PREFIX
    except OSError:
        return False


def analyze_dxf(path: Path) -> DrawingReport:
    """读取一张 DXF，统计图层与可识别构件。"""
    report = DrawingReport(path=path)
    try:
        import ezdxf
    except ImportError:  # pragma: no cover - 依赖缺失时给出明确指引
        report.status = "error"
        report.message = "未安装 ezdxf，请先 pip install ezdxf"
        return report

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as exc:
        report.status = "error"
        report.message = str(exc)
        return report

    report.layers = [layer.dxf.name for layer in doc.layers]
    report.layer_count = len(report.layers)

    layers_by_category: Dict[str, List[str]] = {key: [] for key in CATEGORY_LABELS}
    for name in report.layers:
        for kind in classify_layer(name):
            layers_by_category[kind].append(name)
    report.layers_by_category = layers_by_category

    device_types: Dict[str, int] = {}
    try:
        for entity in doc.modelspace():
            try:
                etype = entity.dxftype()
                layer = entity.dxf.layer if hasattr(entity.dxf, "layer") else ""
                kinds = classify_layer(layer)
                report.entity_count += 1

                if etype == "LINE":
                    if "wall" in kinds:
                        report.wall_segments += 1
                    elif "door" in kinds:
                        report.door_segments += 1
                elif etype in ("LWPOLYLINE", "POLYLINE"):
                    if "wall" in kinds:
                        report.wall_segments += 1
                elif etype == "CIRCLE":
                    if "device" in kinds:
                        report.device_points += 1
                elif etype == "INSERT":
                    name = entity.dxf.name if hasattr(entity.dxf, "name") else ""
                    device_type = device_type_by_block(name)
                    if device_type:
                        report.device_points += 1
                        device_types[device_type] = device_types.get(device_type, 0) + 1
                elif etype in TEXT_TYPES:
                    text = ""
                    if hasattr(entity.dxf, "text"):
                        text = entity.dxf.text or ""
                    elif hasattr(entity, "text"):
                        text = str(entity.text or "")
                    if text and len(text.strip()) <= MAX_ROOM_TEXT_LENGTH:
                        report.room_texts += 1
            except Exception:
                # 单个实体读不了就跳过，与解析器的容错保持一致
                continue
    except Exception as exc:
        report.status = "error"
        report.message = str(exc)
        return report

    report.device_types = device_types
    return report


def _display_width(text: str) -> int:
    """中文按两格算，便于终端里对齐。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in str(text))


def _pad(text: str, width: int) -> str:
    text = str(text)
    return text + " " * max(0, width - _display_width(text))


def collect(targets: List[Path]) -> List[DrawingReport]:
    """展开目录/文件，产出每张图纸的报告。"""
    files: List[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(
                p for p in sorted(target.rglob("*"))
                if p.is_file() and p.suffix.lower() in (".dxf", ".dwg")
            )
        elif target.is_file():
            files.append(target)
        else:
            print(f"[跳过] 路径不存在：{target}", file=sys.stderr)

    reports: List[DrawingReport] = []
    total = len(files)
    for idx, path in enumerate(files, start=1):
        suffix = path.suffix.lower()
        if suffix == ".dwg" or _is_dwg_file(path):
            reports.append(DrawingReport(path=path, status="dwg"))
        else:
            print(f"\r正在解析 {idx}/{total} …", end="", file=sys.stderr)
            reports.append(analyze_dxf(path))
    if total:
        print("\r" + " " * 40 + "\r", end="", file=sys.stderr)
    return reports


def print_report(reports: List[DrawingReport], top: int, detail: bool) -> None:
    usable = [r for r in reports if r.status == "ok" and r.rank > 0]
    dwg = [r for r in reports if r.status == "dwg"]
    failed = [r for r in reports if r.status == "error"]

    print()
    print("=" * 100)
    print(f"共扫描 {len(reports)} 个文件：可解析 {len(usable)} 个，DWG 待转换 {len(dwg)} 个，解析失败 {len(failed)} 个")
    print("图层命名约定：" + convention_hint())
    print("=" * 100)

    usable.sort(key=lambda r: (r.rank, r.wall_segments), reverse=True)
    rows = usable[:top] if top else usable

    if rows:
        header = (
            _pad("图纸", 52) + _pad("图层", 6) + _pad("墙段", 8)
            + _pad("门窗", 6) + _pad("设备", 6) + _pad("房间文字", 10) + "判定"
        )
        print(header)
        print("-" * 100)
        for r in rows:
            name = r.path.name
            if _display_width(name) > 50:
                name = name[:24] + "…" + r.path.suffix
            print(
                _pad(name, 52)
                + _pad(r.layer_count, 6)
                + _pad(r.wall_segments, 8)
                + _pad(r.door_segments, 6)
                + _pad(r.device_points, 6)
                + _pad(r.room_texts, 10)
                + r.verdict
            )

    if detail:
        print()
        print("--- 命中的图层明细（前 10 张） ---")
        for r in rows[:10]:
            print()
            print(f"[{r.path.name}]  {r.path.parent}")
            for key, label in CATEGORY_LABELS.items():
                names = r.layers_by_category.get(key) or []
                if names:
                    shown = "、".join(names[:8]) + ("…" if len(names) > 8 else "")
                    print(f"  {label}：{shown}")
            if r.device_types:
                detail_text = "、".join(f"{k}×{v}" for k, v in r.device_types.items())
                print(f"  识别到的设备类型：{detail_text}")

    if dwg:
        print()
        print(f"--- 需先转 DXF 的 DWG（{len(dwg)} 个，只列前 10 个）---")
        for r in dwg[:10]:
            print(f"  {r.path}")
        if len(dwg) > 10:
            print(f"  …其余 {len(dwg) - 10} 个")
        print("  转换可用 ODA File Converter（免费、支持批量）。")

    if failed:
        print()
        print(f"--- 解析失败（{len(failed)} 个，只列前 10 个）---")
        for r in failed[:10]:
            print(f"  {r.path.name}: {r.message}")


def write_csv(reports: List[DrawingReport], csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "文件", "目录", "状态", "图层数", "实体数", "墙段", "门窗段",
            "设备点", "房间文字", "判定", "说明",
        ])
        for r in sorted(reports, key=lambda x: x.rank, reverse=True):
            writer.writerow([
                r.path.name, str(r.path.parent), r.status, r.layer_count,
                r.entity_count, r.wall_segments, r.door_segments,
                r.device_points, r.room_texts, r.verdict, r.message,
            ])
    print(f"\nCSV 已写入：{csv_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量查看 DXF 图层与构件，筛出能用于 CAD 导入测试的图纸",
    )
    parser.add_argument("paths", nargs="+", help="要扫描的目录或 DXF/DWG 文件")
    parser.add_argument("--top", type=int, default=0, help="只显示前 N 行（0 = 全部）")
    parser.add_argument("--min-walls", type=int, default=0, help="只显示墙段数 >= N 的图纸")
    parser.add_argument("--csv", help="把完整结果写入 CSV（Excel 可直接打开）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出，便于程序处理")
    parser.add_argument("--detail", action="store_true", help="打印命中的图层明细，便于排查")
    args = parser.parse_args()

    targets = [Path(p) for p in args.paths]
    reports = collect(targets)

    if args.min_walls:
        reports = [
            r for r in reports
            if r.status != "ok" or r.wall_segments >= args.min_walls
        ]

    if args.json:
        payload = [
            {
                "file": str(r.path),
                "status": r.status,
                "layerCount": r.layer_count,
                "entityCount": r.entity_count,
                "wallSegments": r.wall_segments,
                "doorSegments": r.door_segments,
                "devicePoints": r.device_points,
                "roomTexts": r.room_texts,
                "verdict": r.verdict,
                "message": r.message,
                "layersByCategory": r.layers_by_category,
            }
            for r in sorted(reports, key=lambda x: x.rank, reverse=True)
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_report(reports, top=args.top, detail=args.detail)

    if args.csv:
        write_csv(reports, Path(args.csv))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
