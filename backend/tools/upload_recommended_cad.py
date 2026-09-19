#!/usr/bin/env python
"""把筛选出的推荐 DXF 图纸批量上传到智慧消防系统。

流程：
1. 用 admin 登录拿 token
2. 对每张推荐图纸：
   a. 在「综合办公楼A座」(building_id=1) 下创建一个楼层
   b. POST /api/cad/parse/{floor_id} 上传 DXF，得到墙/门/设备/房间
   c. POST /api/cad/import-devices/{floor_id} 把解析出的消防设备入库

用法：
    python tools/upload_recommended_cad.py
    python tools/upload_recommended_cad.py --base-url http://127.0.0.1:8000 --username admin --password 123456
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    print("缺少 requests 库，请先安装：pip install requests", file=sys.stderr)
    sys.exit(2)

# 推荐图纸（墙段 + 设备点都比较丰富）
RECOMMENDED_DXFS: List[Dict[str, str]] = [
    {
        "path": r"F:\cad\A14车间工厂办公建筑设计CAD图纸311套_dxf\某工厂建筑图.dxf",
        "floor_name": "某工厂建筑图",
        "description": "4128墙段 / 930设备点",
    },
    {
        "path": r"F:\cad\A14车间工厂办公建筑设计CAD图纸311套_dxf\奶粉厂设计图纸.dxf",
        "floor_name": "奶粉厂设计图纸",
        "description": "2177墙段 / 838设备点",
    },
    {
        "path": r"F:\cad\A14车间工厂办公建筑设计CAD图纸311套_dxf\某厂房办公大楼装饰施工图\123摆布平面.dxf",
        "floor_name": "123摆布平面",
        "description": "5221墙段 / 10931门窗 / 394设备点",
    },
    {
        "path": r"F:\cad\A14车间工厂办公建筑设计CAD图纸311套_dxf\水泥仓库.dxf",
        "floor_name": "水泥仓库",
        "description": "708墙段 / 655门窗 / 428设备点",
    },
]

BUILDING_ID = 1  # 综合办公楼A座（系统已有建筑）


def login(base_url: str, username: str, password: str) -> str:
    """登录并返回 access_token。"""
    resp = requests.post(
        f"{base_url}/api/auth/login",
        data={"username": username, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"登录响应里没有 token：{data}")
    return token


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_floor(base_url: str, token: str, building_id: int, floor_name: str, description: str, floor_number: int) -> int:
    """创建楼层，返回 floor_id。若同名楼层已存在则复用其 id。"""
    taken_numbers: List[int] = []
    list_resp = requests.get(
        f"{base_url}/api/buildings/{building_id}/detail",
        headers=auth_headers(token),
        timeout=15,
    )
    if list_resp.status_code == 200:
        for fl in list_resp.json().get("floors", []) or []:
            if fl.get("name") == floor_name:
                print(f"  楼层「{floor_name}」已存在，复用 floor_id={fl['id']}")
                return fl["id"]
            if isinstance(fl.get("number"), int):
                taken_numbers.append(fl["number"])

    # 楼层号已被占用就顺延到第一个空闲号，避免与既有楼层冲突
    candidate = floor_number
    while candidate in taken_numbers:
        candidate += 1

    create_resp = requests.post(
        f"{base_url}/api/floors",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "building_id": building_id,
            "floor_name": floor_name,
            "floor_number": candidate,
            "description": description,
        },
        timeout=15,
    )
    create_resp.raise_for_status()
    floor_id = create_resp.json()["floor"]["id"]
    print(f"  已创建楼层「{floor_name}」floor_id={floor_id}（楼层号 {candidate}）")
    return floor_id


def parse_cad(base_url: str, token: str, floor_id: int, dxf_path: Path) -> Dict[str, Any]:
    """上传 DXF 并解析，返回解析结果。"""
    with open(dxf_path, "rb") as fh:
        resp = requests.post(
            f"{base_url}/api/cad/parse/{floor_id}",
            headers=auth_headers(token),
            files={"file": (dxf_path.name, fh, "application/octet-stream")},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def purge_floor_devices(base_url: str, token: str, floor_id: int) -> int:
    """清空楼层上由 CAD 导入的设备（编码以 CAD- 开头），返回删除数量。"""
    resp = requests.get(
        f"{base_url}/api/floors/{floor_id}/devices",
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    devices = resp.json().get("devices", []) or []
    removed = 0
    for dev in devices:
        if not str(dev.get("code", "")).startswith("CAD-"):
            continue
        del_resp = requests.delete(
            f"{base_url}/api/devices/{dev['id']}",
            headers=auth_headers(token),
            timeout=30,
        )
        if del_resp.status_code < 400:
            removed += 1
    return removed


def import_devices(base_url: str, token: str, floor_id: int, devices: List[Dict[str, Any]]) -> int:
    """把解析出的设备批量入库，返回导入数量。"""
    if not devices:
        return 0
    resp = requests.post(
        f"{base_url}/api/cad/import-devices/{floor_id}",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json=devices,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("imported", 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="批量上传推荐 DXF 图纸到智慧消防系统")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--building-id", type=int, default=BUILDING_ID, help="建筑 id（默认 1 = 综合办公楼A座）")
    parser.add_argument("--skip-import", action="store_true", help="只上传解析，不导入设备")
    parser.add_argument("--purge", action="store_true", help="导入前先清空该楼层已导入的 CAD- 开头设备（重导用）")
    parser.add_argument("--dxf", action="append", default=[],
                        help="指定要导入的 DXF 路径（可重复）；不传则用内置推荐清单")
    args = parser.parse_args()

    building_id = args.building_id

    # --dxf 指定时按传入路径导入，楼层名取文件名
    if args.dxf:
        tasks = [{"path": p, "floor_name": Path(p).stem, "description": "外部导入"} for p in args.dxf]
    else:
        tasks = list(RECOMMENDED_DXFS)

    # 校验文件存在
    missing = [d["path"] for d in tasks if not Path(d["path"]).is_file()]
    if missing:
        print("以下图纸不存在，请先转换：", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 2

    print(f"登录 {args.base_url} ...")
    token = login(args.base_url, args.username, args.password)
    print(f"  登录成功，用户：{args.username}")

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(tasks, start=1):
        path = Path(item["path"])
        print(f"\n[{idx}/{len(tasks)}] {path.name}")
        try:
            floor_id = create_floor(
                args.base_url, token, building_id,
                floor_name=item["floor_name"],
                description=item["description"],
                floor_number=idx,
            )

            print(f"  上传并解析 DXF ...")
            parsed = parse_cad(args.base_url, token, floor_id, path)
            walls = len(parsed.get("walls", []))
            doors = len(parsed.get("doors", []))
            devices = parsed.get("devices", [])
            rooms = len(parsed.get("rooms", []))
            print(f"  解析结果：墙 {walls}  门 {doors}  设备 {len(devices)}  房间 {rooms}")

            purged = 0
            if args.purge:
                purged = purge_floor_devices(args.base_url, token, floor_id)
                print(f"  已清理旧设备 {purged} 个")

            imported = 0
            if not args.skip_import and devices:
                print(f"  导入 {len(devices)} 个设备到数据库 ...")
                imported = import_devices(args.base_url, token, floor_id, devices)
                print(f"  已导入 {imported} 个设备")

            results.append({
                "file": path.name,
                "floor_id": floor_id,
                "walls": walls,
                "doors": doors,
                "devices": len(devices),
                "rooms": rooms,
                "purged": purged,
                "imported": imported,
                "ok": True,
            })
        except Exception as exc:
            print(f"  失败：{exc}")
            results.append({"file": path.name, "ok": False, "error": str(exc)})

    print("\n" + "=" * 70)
    print("汇总：")
    print(f"{'图纸':<24} {'楼层':>6} {'墙段':>6} {'门窗':>6} {'设备':>6} {'清理':>6} {'导入':>6}")
    print("-" * 70)
    for r in results:
        if r["ok"]:
            print(f"{r['file']:<24} {r['floor_id']:>6} {r['walls']:>6} {r['doors']:>6} {r['devices']:>6} {r['purged']:>6} {r['imported']:>6}")
        else:
            print(f"{r['file']:<24} 失败：{r['error']}")

    ok_count = sum(1 for r in results if r["ok"])
    total_devices = sum(r["devices"] for r in results if r["ok"])
    total_imported = sum(r["imported"] for r in results if r["ok"])
    print(f"\n成功 {ok_count}/{len(results)}；解析出设备 {total_devices} 个，导入 {total_imported} 个")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
