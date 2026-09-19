#!/usr/bin/env python
"""批量把 DWG 转成 DXF（调用 ODA File Converter）。

为什么需要这一步：系统的 CAD 解析用的是 `ezdxf`，它**只读 DXF**。
DWG 是 AutoCAD 的二进制格式，必须先用 ODA File Converter（免费）转成 DXF 才能导入。

用法：

    # 1) 先看计划：会转哪些目录、多少文件（不实际转换）
    python tools/dwg_batch_convert.py "F:/cad/图纸目录" --dry-run

    # 2) 实际转换：输出到同级的 <目录名>_dxf
    python tools/dwg_batch_convert.py "F:/cad/图纸目录"

    # 3) 指定 ODA 路径 / 输出目录 / DXF 版本
    python tools/dwg_batch_convert.py "F:/cad/图纸目录" \
        --oda "C:/Program Files/ODA/ODAFileConverter 25.4.0/ODAFileConverter.exe" \
        --out "F:/cad/dxf" --version ACAD2018

转换完成后，用 tools/dxf_layer_report.py 筛出真正能被解析的图纸：

    python tools/dxf_layer_report.py "F:/cad/图纸目录_dxf" --top 30 --detail

三个容易踩的坑，脚本里都处理了：

1. **必须保持目录结构**。图纸集合里大量文件重名（`厂房建筑图.dwg` 在多个子目录都有），
   如果让 ODA 递归后平铺到一个目录，同名文件会互相覆盖。所以这里按目录逐个调用，
   输出严格镜像输入的相对路径。
2. **ODA 启动器可能是异步的**。命令行退出不代表文件写完，所以退出后还要轮询输出目录，
   文件数稳定下来才算完成。
3. **中文路径**。ODA 是 Qt 程序，多数情况能处理，但个别版本会失败；脚本对失败目录
   给出明确提示（可以先把图纸复制到纯英文路径再转）。
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ODA File Converter 常见安装位置（不同版本装在不同子目录，取版本号最大的）
ODA_GLOBS = [
    r"C:\Program Files\ODA\*\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\*\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter.exe",
]

ODA_DOWNLOAD_HINT = (
    "未找到 ODA File Converter。请先从 https://www.opendesign.com/guestfiles/oda_file_converter "
    "下载安装（免费，需填邮箱），然后用 --oda 指定可执行文件路径，"
    "或把 ODAFileConverter.exe 所在目录加入 PATH。"
)

# 判断"转换结束"的轮询参数：连续两次采样文件数不变、且间隔达到该秒数即认为写完
SETTLE_SECONDS = 6
POLL_INTERVAL_SECONDS = 2


def find_oda(explicit: Optional[str]) -> Optional[Path]:
    """定位 ODAFileConverter.exe：显式指定 > PATH > 常见安装目录。"""
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None

    found = shutil.which("ODAFileConverter") or shutil.which("ODAFileConverter.exe")
    if found:
        return Path(found)

    matches: List[str] = []
    for pattern in ODA_GLOBS:
        matches.extend(glob.glob(pattern))
    if not matches:
        return None
    # 目录名里带版本号，倒序取第一个（字符串序对 25.x > 24.x 这类够用）
    return Path(sorted(matches, reverse=True)[0])


def collect_groups(input_dir: Path) -> Dict[Path, List[Path]]:
    """按"所在目录"分组收集 DWG，键是相对输入根目录的相对路径。"""
    groups: Dict[Path, List[Path]] = {}
    for dwg in sorted(input_dir.rglob("*")):
        if not dwg.is_file() or dwg.suffix.lower() != ".dwg":
            continue
        rel_dir = dwg.parent.relative_to(input_dir)
        groups.setdefault(rel_dir, []).append(dwg)
    return groups


def count_dxf(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.glob("*.dxf"))


def target_dxf_path(out_dir: Path, rel_dir: Path, dwg: Path) -> Path:
    """DWG 对应的输出路径：严格镜像输入的相对目录。

    图纸集合里大量文件重名（`厂房建筑图.dwg` 在多个子目录都有），
    如果输出平铺到一个目录，同名文件会互相覆盖、白转一遍。
    """
    return out_dir / rel_dir / f"{dwg.stem}.dxf"


def is_up_to_date(dxf: Path, dwg: Path, *, overwrite: bool) -> bool:
    """已转换且不比源文件旧就跳过，支持中断后续跑（增量）。"""
    if overwrite or not dxf.is_file():
        return False
    return dxf.stat().st_mtime >= dwg.stat().st_mtime


def wait_until_settled(directory: Path, deadline: float) -> int:
    """等 ODA 把文件写完：文件数连续 SETTLE_SECONDS 不变即认为结束。"""
    last_count = count_dxf(directory)
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        current = count_dxf(directory)
        if current != last_count:
            last_count = current
            stable_since = time.monotonic()
            continue
        if time.monotonic() - stable_since >= SETTLE_SECONDS:
            return current
    return count_dxf(directory)


def convert_group(
    oda: Path,
    src_dir: Path,
    dst_dir: Path,
    *,
    version: str,
    audit: bool,
    timeout: int,
) -> Tuple[bool, int, str]:
    """转换一个目录。返回 (是否成功, 生成的 DXF 数, 说明)。"""
    dst_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(oda),
        str(src_dir),
        str(dst_dir),
        version,
        "DXF",
        "0",                      # Recurse=0：我们自己按目录遍历，保证输出结构镜像
        "1" if audit else "0",    # Audit：让 ODA 顺带修复损坏文件
        "*.dwg",
    ]

    expected = len([p for p in src_dir.glob("*.dwg")])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, count_dxf(dst_dir), f"超时（>{timeout}s）"
    except OSError as exc:
        return False, 0, f"无法启动 ODA：{exc}"

    # 启动器可能立刻返回，实际转换在后台；等输出目录稳定下来
    deadline = time.monotonic() + timeout
    produced = wait_until_settled(dst_dir, deadline)

    if produced >= expected:
        return True, produced, ""

    # 数量不足：把 ODA 自己的输出带上，便于定位（中文路径、加密图纸等）
    stderr = (proc.stderr or "").strip().splitlines()
    stdout = (proc.stdout or "").strip().splitlines()
    detail = " | ".join((stderr or stdout)[-2:])[:200]
    return False, produced, f"预期 {expected} 个，实际 {produced} 个" + (f"；ODA 输出：{detail}" if detail else "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量把 DWG 转成 DXF（调用 ODA File Converter）",
    )
    parser.add_argument("input_dir", help="包含 DWG 的目录（递归扫描）")
    parser.add_argument("--out", help="输出目录（默认：输入目录同级的 <目录名>_dxf）")
    parser.add_argument("--oda", help="ODAFileConverter.exe 路径（默认自动探测）")
    parser.add_argument("--version", default="ACAD2018",
                        help="输出的 DXF 版本（ACAD2018/ACAD2013/ACAD2010/ACAD2007/ACAD2004/ACAD2000，默认 ACAD2018）")
    parser.add_argument("--audit", action="store_true", help="让 ODA 审计并修复损坏的图纸（较慢）")
    parser.add_argument("--timeout", type=int, default=900, help="单个目录的转换超时秒数（默认 900）")
    parser.add_argument("--overwrite", action="store_true", help="重新转换已存在且不比 DWG 旧的 DXF")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不实际转换")
    parser.add_argument("--yes", action="store_true", help="跳过执行前的确认")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser()
    if not input_dir.is_dir():
        print(f"输入目录不存在：{input_dir}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser() if args.out else input_dir.parent / f"{input_dir.name}_dxf"
    if out_dir.resolve() == input_dir.resolve():
        print("输出目录不能与输入目录相同（ODA 不允许，也会覆盖原图）。", file=sys.stderr)
        return 2
    if input_dir.resolve() in out_dir.resolve().parents or out_dir.resolve() in input_dir.resolve().parents:
        print(f"[警告] 输出目录位于输入目录内部，建议放到输入目录之外：{out_dir}")

    groups = collect_groups(input_dir)
    total_dwg = sum(len(v) for v in groups.values())
    if not total_dwg:
        print(f"{input_dir} 下没有找到 .dwg 文件。")
        return 0

    # 统计待转数量（增量：输出里已存在且不比 DWG 旧的算已转换）
    pending: List[Tuple[Path, List[Path]]] = []
    already = 0
    for rel_dir, files in sorted(groups.items()):
        todo = []
        for dwg in files:
            dxf = target_dxf_path(out_dir, rel_dir, dwg)
            if is_up_to_date(dxf, dwg, overwrite=args.overwrite):
                already += 1
                continue
            todo.append(dwg)
        if todo:
            pending.append((rel_dir, todo))

    print("=" * 88)
    print(f"输入目录：{input_dir}")
    print(f"输出目录：{out_dir}")
    print(f"DXF 版本：{args.version}    Audit：{'开' if args.audit else '关'}")
    print(f"共 {total_dwg} 个 DWG，分布在 {len(groups)} 个目录；"
          f"待转换 {sum(len(v) for _, v in pending)} 个，已存在跳过 {already} 个")
    print("=" * 88)

    if not pending:
        print("没有需要转换的文件。要强制重转请加 --overwrite。")
        return 0

    for rel_dir, files in pending[:20]:
        shown = ", ".join(p.name for p in files[:4])
        more = f" 等 {len(files)} 个" if len(files) > 4 else ""
        print(f"  {rel_dir if str(rel_dir) != '.' else '<根目录>'}: {shown}{more}")
    if len(pending) > 20:
        print(f"  …其余 {len(pending) - 20} 个目录")

    if args.dry_run:
        print("\n--dry-run：只列计划，未执行转换。")
        return 0

    oda = find_oda(args.oda)
    if not oda:
        print("\n" + ODA_DOWNLOAD_HINT, file=sys.stderr)
        return 2
    print(f"\nODA：{oda}")

    if not args.yes:
        try:
            answer = input("开始转换？这会调用 ODA 处理上述目录 [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("已取消。")
            return 0

    ok_dirs = 0
    failed: List[Tuple[Path, str]] = []
    produced_total = 0
    for index, (rel_dir, files) in enumerate(pending, start=1):
        src_dir = input_dir / rel_dir
        dst_dir = out_dir / rel_dir
        label = str(rel_dir) if str(rel_dir) != "." else "<根目录>"
        print(f"\n[{index}/{len(pending)}] {label}（{len(files)} 个 DWG）")
        ok, produced, message = convert_group(
            oda, src_dir, dst_dir,
            version=args.version, audit=args.audit, timeout=args.timeout,
        )
        produced_total += produced
        if ok:
            ok_dirs += 1
            print(f"    -> 生成 {produced} 个 DXF")
        else:
            failed.append((rel_dir, message))
            print(f"    -> 失败：{message}")

    print("\n" + "=" * 88)
    print(f"完成：{ok_dirs}/{len(pending)} 个目录成功，共生成 {produced_total} 个 DXF")
    if failed:
        print(f"\n失败 {len(failed)} 个目录：")
        for rel_dir, message in failed:
            print(f"  {rel_dir}: {message}")
        print(
            "\n若失败信息里是编码/路径相关报错，可把该目录的 DWG 复制到纯英文路径（如 C:\\cad_tmp）再转；"
            "\n若是加密或损坏图纸，可加 --audit 重试。"
        )
    print(f"\n下一步：python tools/dxf_layer_report.py \"{out_dir}\" --top 30 --detail")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
