from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import (
    get_db, Floor, Building, Device, User, VideoChannel, AlertRecord as Alert,
    DeviceTelemetry, DutyShift, FaultTicket, InspectionRecord,
)

from services.auth_service import get_current_user, get_current_tenant_id, require_permission
from services.common_utils import (
    BIM_EXTENSIONS,
    CAD_EXTENSIONS,
    local_day_end_utc,
    local_day_start_utc,
    read_validated_upload,
)
from services.upload_archive_service import (
    delete_upload,
    find_upload,
    get_upload,
    list_uploads,
    resolve_upload_path,
    save_upload,
    upload_to_dict,
)
from services.cad_layer_rules import (
    classify_layer,
    convention_hint,
    device_type_by_block,
    device_type_by_layer,
)

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["建筑管理"])

# ============================================================
# 数据大屏聚合辅助
# ============================================================

# 已闭环的整改工单状态
CLOSED_TICKET_STATUSES = ("已完成", "已关闭", "closed", "done")
# 待处理（用于大屏待办）的工单状态
OPEN_TICKET_STATUSES = ("待受理", "处理中", "待复查")

# 设备状态的中文/英文写法在不同来源里不一致，这里统一归类
ONLINE_STATUSES = ("正常", "在线", "online")
OFFLINE_STATUSES = ("离线", "offline")
ABNORMAL_STATUSES = ("告警", "alarm", "故障", "预警", "warning")

# 「消防水源」相关设备的识别关键词
WATER_DEVICE_KEYWORDS = ("消火栓", "消防栓", "喷淋", "水泵", "水箱", "水源", "水压", "湿式报警")
# 「电气火灾」相关设备的识别关键词
ELECTRIC_DEVICE_KEYWORDS = ("电气", "配电", "电缆", "用电", "电流", "电压", "漏电", "电气火灾")

# 隐患文本 -> 隐患类别
HAZARD_CATEGORY_RULES = (
    ("消防设施", ("灭火器", "消火栓", "消防栓", "喷淋", "水泵", "消防设施", "应急照明", "疏散指示", "消防器材")),
    ("电气安全", ("电气", "电线", "线路", "漏电", "过载", "短路", "配电", "插座", "过热", "私拉")),
    ("通道堵塞", ("通道", "堵塞", "堆物", "堆放", "遮挡", "出口", "占用")),
    ("用火用气", ("明火", "吸烟", "燃气", "动火", "易燃", "可燃")),
    ("管理制度", ("制度", "台账", "记录", "培训", "演练", "责任", "档案")),
)
HAZARD_CATEGORY_COLORS = {
    "消防设施": "#3b82f6",
    "电气安全": "#f59e0b",
    "通道堵塞": "#ef4444",
    "用火用气": "#ec4899",
    "管理制度": "#8b5cf6",
    "其他": "#64748b",
}


def _parse_str_list(raw: Any) -> List[str]:
    """把可能是 JSON 文本/列表/单值的字段统一成字符串列表。"""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        items: Any = list(raw)
    else:
        try:
            items = json.loads(raw)
        except (TypeError, ValueError):
            items = [str(raw)]
    if not isinstance(items, list):
        items = [items]

    result: List[str] = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            for key in ("name", "hazard", "hazard_type", "type", "title"):
                if item.get(key):
                    result.append(str(item[key]))
                    break
    return result


def _hazard_category(name: str) -> str:
    text = str(name or "")
    for category, keywords in HAZARD_CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return "其他"


def _risk_color(score: float) -> str:
    if score >= 80:
        return "#ef4444"
    if score >= 60:
        return "#f97316"
    if score >= 40:
        return "#f59e0b"
    return "#22c55e"


def _match_device(device: Device, keywords) -> bool:
    text = f"{device.device_type or ''}{device.device_name or ''}{device.location or ''}"
    return any(keyword in text for keyword in keywords)


def _device_group_stats(
    db: Session,
    devices: List[Device],
    keywords,
    *,
    with_temperature: bool = False,
) -> Dict[str, Any]:
    """圈定一类设备并统计真实的在线/异常情况。

    注意：管网压力、水箱水位、剩余电流这类指标在 `DeviceTelemetry` 中**没有对应字段**，
    因此返回 None 由前端显示为「--」，不用编造的数字填充。
    """
    matched = [d for d in devices if _match_device(d, keywords)]
    stats: Dict[str, Any] = {
        "total": len(matched),
        "online": sum(1 for d in matched if (d.status or "") in ONLINE_STATUSES),
        "offline": sum(1 for d in matched if (d.status or "") in OFFLINE_STATUSES),
        "alarm": sum(1 for d in matched if (d.status or "") in ABNORMAL_STATUSES),
    }

    if with_temperature:
        ids = [d.id for d in matched]
        # 按时间升序覆盖，得到每个设备的最新一条遥测
        latest: Dict[int, float] = {}
        for device_id, temperature in (
            db.query(DeviceTelemetry.device_id, DeviceTelemetry.temperature)
            .filter(DeviceTelemetry.device_id.in_(ids))
            .order_by(DeviceTelemetry.created_at.asc())
            .all()
        ):
            if temperature is not None:
                latest[device_id] = temperature
        stats["maxTemp"] = round(max(latest.values()), 1) if latest else None

    return stats


def _current_duty_shift(db: Session, tenant_id: int, today) -> Optional[DutyShift]:
    """取当前时间点应当值班的班次；没有排班时返回 None。"""
    shifts = db.query(DutyShift).filter(DutyShift.tenant_id == tenant_id).all()
    if not shifts:
        return None

    today_shifts = [s for s in shifts if s.duty_date == today] or [s for s in shifts if s.duty_date is None]
    if not today_shifts:
        return None

    now_time = datetime.now().strftime("%H:%M")
    for shift in today_shifts:
        start = shift.start_time or ""
        end = shift.end_time or "23:59"
        if start <= end:
            if start <= now_time <= end:
                return shift
        elif now_time >= start or now_time <= end:  # 跨夜班次
            return shift
    return today_shifts[0]


# ============================================================
# 阶段一：建筑详情API
# ============================================================

@router.get("/api/buildings/{building_id}/detail")
def get_building_full_detail(
    building_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building = db.query(Building).filter(
        Building.id == building_id,
        Building.tenant_id == tenant_id,
    ).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    floors = db.query(Floor).filter(
        Floor.building_id == building_id,
        Floor.tenant_id == tenant_id,
    ).order_by(Floor.floor_number.asc()).all()

    floor_list = []
    total_devices = 0
    total_alarms = 0

    for floor in floors:
        devices = db.query(Device).filter(
            Device.floor_id == floor.id,
            Device.tenant_id == tenant_id,
        ).all()
        device_count = len(devices)
        device_ids = [d.id for d in devices]
        alarm_count = 0
        if device_ids:
            alarm_count = db.query(Alert).filter(
                Alert.building_id == building_id,
                Alert.device_id.in_(device_ids),
                Alert.tenant_id == tenant_id
            ).count()

        smoke_count = sum(1 for d in devices if "烟感" in d.device_type)
        hydrant_count = sum(1 for d in devices if "消火栓" in d.device_type or "消防栓" in d.device_type)

        floor_list.append({
            "id": floor.id,
            "name": floor.floor_name,
            "number": floor.floor_number,
            "status": floor.status or "normal",
            "deviceCount": device_count,
            "alarmCount": alarm_count,
            "smokeCount": smoke_count,
            "hydrantCount": hydrant_count,
            "floorPlanImage": floor.floor_plan_image or "",
        })
        total_devices += device_count
        total_alarms += alarm_count

    all_devices = db.query(Device).filter(
        Device.building_id == building_id,
        Device.tenant_id == tenant_id,
    ).all()
    normal_count = sum(1 for d in all_devices if d.status == "正常" or d.status == "online")
    offline_count = sum(1 for d in all_devices if d.status == "离线" or d.status == "offline")
    alarm_count_dev = sum(1 for d in all_devices if d.status == "告警" or d.status == "alarm" or d.status == "故障")

    recent_alarms = db.query(Alert).filter(
        Alert.building_id == building_id,
        Alert.tenant_id == tenant_id,
    ).order_by(Alert.created_at.desc()).limit(5).all()

    alarm_list = []
    for a in recent_alarms:
        level_map = {
            "critical": "critical",
            "high": "critical",
            "medium": "warning",
            "low": "info",
            "info": "info",
        }
        alarm_list.append({
            "id": a.id,
            "title": a.alert_type or a.device_name or "",
            "level": level_map.get(a.severity, "info"),
            "time": a.created_at.isoformat() if a.created_at else "",
            "location": a.location or "",
        })

    return {
        "building": {
            "id": building.id,
            "name": building.building_name,
            "address": building.address,
            "floors": len(floors),
            "deviceCount": total_devices,
            "alarmCount": total_alarms,
        },
        "floors": floor_list,
        "stats": {
            "total": total_devices,
            "normal": normal_count,
            "alarm": alarm_count_dev,
            "offline": offline_count,
        },
        "recentAlarms": alarm_list,
    }


@router.get("/api/floors/{floor_id}/devices")
def get_floor_devices(
    floor_id: int,
    keyword: str = "",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    query = db.query(Device).filter(Device.floor_id == floor_id, Device.tenant_id == tenant_id)
    if keyword:
        query = query.filter(
            (Device.device_name.like(f"%{keyword}%")) |
            (Device.device_code.like(f"%{keyword}%"))
        )
    devices = query.all()

    type_map = {
        "烟感探测器": "smoke",
        "烟感": "smoke",
        "温感探测器": "heat",
        "温感": "heat",
        "消火栓": "hydrant",
        "消防栓": "hydrant",
        "喷淋头": "sprinkler",
        "喷淋": "sprinkler",
        "手报按钮": "manual",
        "手动报警": "manual",
        "灭火器": "extinguisher",
    }

    status_map = {
        "正常": "normal",
        "在线": "normal",
        "online": "normal",
        "离线": "offline",
        "offline": "offline",
        "告警": "alarm",
        "alarm": "alarm",
        "故障": "alarm",
        "预警": "warning",
        "warning": "warning",
    }

    device_list = []
    for d in devices:
        dev_type = type_map.get(d.device_type, "other")
        status = status_map.get(d.status, "normal")
        device_list.append({
            "id": d.id,
            "code": d.device_code,
            "name": d.device_name,
            "type": dev_type,
            "typeLabel": d.device_type,
            "status": status,
            "x": d.floor_x or 50,
            "y": d.floor_y or 50,
            "installDate": d.install_date.isoformat() if d.install_date else "",
            "nextMaintenance": d.next_maintenance.isoformat() if d.next_maintenance else "",
            "location": d.location or "",
        })

    return {
        "floor": {
            "id": floor.id,
            "name": floor.floor_name,
            "number": floor.floor_number,
            "buildingId": floor.building_id,
            "floorPlanImage": floor.floor_plan_image or "",
        },
        "devices": device_list,
    }


@router.get("/api/devices/{device_id}/detail")
def get_device_full_detail(
    device_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id,
    ).first()
    if not device:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})

    building = db.query(Building).filter(
        Building.id == device.building_id,
        Building.tenant_id == tenant_id,
    ).first()
    floor = db.query(Floor).filter(
        Floor.id == device.floor_id,
        Floor.tenant_id == tenant_id,
    ).first()

    recent_alarms = db.query(Alert).filter(
        Alert.device_id == device_id,
        Alert.tenant_id == tenant_id,
    ).order_by(Alert.created_at.desc()).limit(10).all()

    alarm_list = [{
        "id": a.id,
        "title": a.title or a.alert_type or "",
        "level": a.level or "info",
        "time": a.created_at.isoformat() if a.created_at else "",
    } for a in recent_alarms]

    return {
        "device": {
            "id": device.id,
            "code": device.device_code,
            "name": device.device_name,
            "type": device.device_type,
            "status": device.status,
            "buildingId": device.building_id,
            "buildingName": building.building_name if building else "",
            "floorId": device.floor_id,
            "floorName": floor.floor_name if floor else "",
            "location": device.location or "",
            "floorX": device.floor_x or 0,
            "floorY": device.floor_y or 0,
            "installDate": device.install_date.isoformat() if device.install_date else "",
            "lastMaintenance": device.last_maintenance.isoformat() if device.last_maintenance else "",
            "nextMaintenance": device.next_maintenance.isoformat() if device.next_maintenance else "",
            "maintenanceCycle": "每月",
            "description": device.description or "",
        },
        "recentAlarms": alarm_list,
    }


# ============================================================
# 阶段二：DXF CAD图纸解析
# ============================================================

# ezdxf 只能读 DXF。DWG 是 AutoCAD 的二进制格式，先按文件头（AC10xx）拦下来并给出
# 转换指引，而不是让它进解析器抛一个用户看不懂的异常。
_DWG_MAGIC_PREFIX = b"AC10"
DWG_NOT_SUPPORTED_HINT = (
    "只支持 DXF 格式：DWG 是 AutoCAD 的二进制格式，解析库（ezdxf）读不了。"
    "请先用 ODA File Converter 等工具把 DWG 转换成 DXF 再上传。"
)
DXF_DEP_MISSING_HINT = (
    "服务端未安装 ezdxf，无法解析 DXF；请执行 pip install ezdxf 后重启服务。"
)
# 回传给前端的图层名上限：有的图纸上千个图层，全返回会让响应体过大
LAYER_NAME_LIMIT = 200


def _is_dwg_content(content: bytes) -> bool:
    """按文件头判断是不是 DWG：AutoCAD 各版本都以 AC10xx 开头（如 AC1015 = 2000）。"""
    return content[:4] == _DWG_MAGIC_PREFIX


@router.post("/api/cad/parse/{floor_id}")
async def parse_cad_drawing(
    floor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    content, ext = await read_validated_upload(file, CAD_EXTENSIONS, label="CAD图纸")

    if _is_dwg_content(content):
        raise HTTPException(status_code=400, detail=DWG_NOT_SUPPORTED_HINT)

    record = save_upload(
        db,
        tenant_id=tenant_id,
        category="cad",
        content=content,
        ext=ext,
        media_type="application/octet-stream",
        original_name=file.filename or "",
        owner_id=current_user.id,
        owner_name=current_user.real_name or current_user.username,
    )
    resolved = resolve_upload_path(record)
    if not resolved:
        raise HTTPException(status_code=500, detail="CAD 文件落盘失败")
    save_path = str(resolved)

    # 空楼层上导入图纸 = 这张图纸定义了该楼层，记下来源以便日后整单撤销；
    # 已经标记为"导入创建"的楼层，重导时把来源刷新到最新一次上传；
    # 往手工创建的、已有设备的楼层追加图纸则不抢占来源，否则删图会误删已有楼层。
    has_devices = db.query(Device).filter(
        Device.floor_id == floor.id,
        Device.tenant_id == tenant_id,
    ).first() is not None
    if floor.source_upload_id or not has_devices:
        floor.source_upload_id = record.id
        db.commit()

    walls = []
    devices = []
    doors = []
    rooms = []
    texts = []
    wall_thickness = 240

    try:
        import ezdxf
        doc = ezdxf.readfile(save_path)
        msp = doc.modelspace()

        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')

        layer_names = {layer.dxf.name for layer in doc.layers}

        for entity in msp:
            try:
                if entity.dxftype() == 'LINE':
                    start = entity.dxf.start
                    end = entity.dxf.end
                    layer = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ''
                    kinds = classify_layer(layer)

                    min_x = min(min_x, start[0], end[0])
                    max_x = max(max_x, start[0], end[0])
                    min_y = min(min_y, start[1], end[1])
                    max_y = max(max_y, start[1], end[1])

                    if 'wall' in kinds:
                        walls.append({
                            "x1": start[0], "y1": start[1],
                            "x2": end[0], "y2": end[1],
                            "type": "wall",
                            "thickness": 240
                        })
                    elif 'door' in kinds:
                        doors.append({
                            "x1": start[0], "y1": start[1],
                            "x2": end[0], "y2": end[1],
                        })
                    elif 'axis' not in kinds:
                        walls.append({
                            "x1": start[0], "y1": start[1],
                            "x2": end[0], "y2": end[1],
                            "type": "line"
                        })

                elif entity.dxftype() == 'CIRCLE':
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    layer = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ''
                    kinds = classify_layer(layer)

                    min_x = min(min_x, center[0] - radius)
                    max_x = max(max_x, center[0] + radius)
                    min_y = min(min_y, center[1] - radius)
                    max_y = max(max_y, center[1] + radius)

                    if 'device' in kinds:
                        dev_type = device_type_by_layer(layer) or "smoke"

                        devices.append({
                            "x": center[0],
                            "y": center[1],
                            "radius": radius,
                            "type": dev_type,
                            "layer": layer,
                        })

                elif entity.dxftype() == 'INSERT':
                    name = entity.dxf.name.upper() if hasattr(entity.dxf, 'name') else ''
                    insert_point = entity.dxf.insert if hasattr(entity.dxf, 'insert') else None
                    if not insert_point:
                        continue

                    min_x = min(min_x, insert_point[0])
                    max_x = max(max_x, insert_point[0])
                    min_y = min(min_y, insert_point[1])
                    max_y = max(max_y, insert_point[1])

                    dev_type = device_type_by_block(name)
                    if dev_type:
                        devices.append({
                            "x": insert_point[0],
                            "y": insert_point[1],
                            "type": dev_type,
                            "block": name,
                        })

                elif entity.dxftype() == 'TEXT' or entity.dxftype() == 'MTEXT':
                    text_content = ""
                    tx, ty = 0, 0
                    text_height = 2.5
                    if hasattr(entity.dxf, 'text'):
                        text_content = entity.dxf.text
                    if hasattr(entity, 'text'):
                        text_content = str(entity.text)
                    if hasattr(entity.dxf, 'insert'):
                        tx = entity.dxf.insert[0]
                        ty = entity.dxf.insert[1]
                    if hasattr(entity.dxf, 'height'):
                        text_height = entity.dxf.height

                    if text_content and len(text_content) <= 20:
                        texts.append({
                            "text": text_content,
                            "x": tx,
                            "y": ty,
                            "height": text_height,
                        })

                    min_x = min(min_x, tx)
                    max_x = max(max_x, tx)
                    min_y = min(min_y, ty)
                    max_y = max(max_y, ty)

                elif entity.dxftype() == 'LWPOLYLINE' or entity.dxftype() == 'POLYLINE':
                    points = list(entity.get_points() if hasattr(entity, 'get_points') else [])
                    layer = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ''
                    if points and len(points) >= 4:
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        min_x = min(min_x, min(xs))
                        max_x = max(max_x, max(xs))
                        min_y = min(min_y, min(ys))
                        max_y = max(max_y, max(ys))

                        is_wall_poly = 'wall' in classify_layer(layer)
                        if is_wall_poly:
                            for i in range(len(points)):
                                p1 = points[i]
                                p2 = points[(i + 1) % len(points)]
                                walls.append({
                                    "x1": p1[0], "y1": p1[1],
                                    "x2": p2[0], "y2": p2[1],
                                    "type": "wall",
                                    "thickness": 240
                                })
                        elif len(points) >= 4:
                            area = abs(max(xs) - min(xs)) * abs(max(ys) - min(ys))
                            room_name = ""
                            cx = (max(xs) + min(xs)) / 2
                            cy = (max(ys) + min(ys)) / 2
                            for t in texts:
                                dx = abs(t["x"] - cx)
                                dy = abs(t["y"] - cy)
                                if dx < (max(xs) - min(xs)) / 2 and dy < (max(ys) - min(ys)) / 2:
                                    room_name = t["text"]
                                    break
                            rooms.append({
                                "points": points,
                                "area": area,
                                "name": room_name,
                                "x": min(xs),
                                "y": min(ys),
                                "w": max(xs) - min(xs),
                                "h": max(ys) - min(ys),
                            })
            except Exception:
                continue

        # 归一化基准优先取墙线外接框：图纸里常有远离主体的游离实体（散落文字、
        # 图框外的零星线条），按全图外接框归一化会把真正的建筑内容压成一小块。
        if walls:
            wall_xs = [v for w in walls for v in (w["x1"], w["x2"])]
            wall_ys = [v for w in walls for v in (w["y1"], w["y2"])]
            base_min_x, base_max_x = min(wall_xs), max(wall_xs)
            base_min_y, base_max_y = min(wall_ys), max(wall_ys)
        else:
            base_min_x, base_max_x = min_x, max_x
            base_min_y, base_max_y = min_y, max_y

        width = base_max_x - base_min_x if base_max_x > base_min_x else 100
        height = base_max_y - base_min_y if base_max_y > base_min_y else 100

        normalized_walls = []
        for w in walls:
            normalized_walls.append({
                "x1": (w["x1"] - base_min_x) / width * 100,
                "y1": (w["y1"] - base_min_y) / height * 100,
                "x2": (w["x2"] - base_min_x) / width * 100,
                "y2": (w["y2"] - base_min_y) / height * 100,
                "type": w["type"]
            })

        normalized_devices = []
        for i, d in enumerate(devices):
            normalized_devices.append({
                "id": f"cad_dev_{i}",
                "x": (d["x"] - base_min_x) / width * 100,
                "y": (d["y"] - base_min_y) / height * 100,
                "type": d["type"],
            })

        normalized_rooms = []
        for r in rooms:
            norm_points = [
                {"x": (p[0] - base_min_x) / width * 100, "y": (p[1] - base_min_y) / height * 100}
                for p in r.get("points", [])
            ]
            normalized_rooms.append({"points": norm_points, "area": r.get("area", 0)})

        normalized_doors = []
        for d in doors:
            normalized_doors.append({
                "x1": (d.get("x1", 0) - base_min_x) / width * 100,
                "y1": (d.get("y1", 0) - base_min_y) / height * 100,
                "x2": (d.get("x2", 0) - base_min_x) / width * 100,
                "y2": (d.get("y2", 0) - base_min_y) / height * 100,
            })

        result = {
            "success": True,
            "fileName": file.filename,
            "stats": {
                "wallCount": len(walls),
                "doorCount": len(doors),
                "deviceCount": len(devices),
                "roomCount": len(rooms),
                "width": width,
                "height": height,
            },
            "walls": normalized_walls,
            "doors": normalized_doors,
            "devices": normalized_devices,
            "rooms": normalized_rooms,
            # 图层名一并回传：解析完全依赖图层命名，识别不出东西时用户能直接看到
            # "这张图的图层到底叫什么"，不必去翻原图
            "layers": sorted(layer_names)[:LAYER_NAME_LIMIT],
            "layerCount": len(layer_names),
        }

    except ImportError as exc:
        # 缺依赖是服务端的问题，不是用户传错了文件
        raise HTTPException(status_code=503, detail=DXF_DEP_MISSING_HINT) from exc
    except Exception as exc:
        # 解析不了就如实报错。以前这里会返回一份固定的假平面图并标 success，
        # 界面照样画出来、还能把假设备写进设备表——那比报错糟得多。
        raise HTTPException(status_code=400, detail=f"DXF 解析失败：{exc}") from exc

    if not (result["walls"] or result["rooms"] or result["devices"] or result["doors"]):
        raise HTTPException(
            status_code=422,
            detail=(
                "这张图纸没有解析出任何墙体、门窗、设备或房间，可能是空图，"
                "或者几何都在外部参照（xref）里。解析按图层名识别——"
                f"{convention_hint()}。"
                "可先用 backend/tools/dxf_layer_report.py 检查该图的图层名。"
            ),
        )

    return result


@router.post("/api/cad/import-devices/{floor_id}")
def import_cad_devices(
    floor_id: int,
    devices_data: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})

    type_name_map = {
        "smoke": "烟感探测器",
        "heat": "温感探测器",
        "hydrant": "消火栓",
        "sprinkler": "喷淋头",
        "manual": "手报按钮",
        "extinguisher": "灭火器",
    }

    imported = 0
    for i, dev_data in enumerate(devices_data):
        dev_type = dev_data.get("type", "smoke")
        dev_code = f"CAD-{dev_type.upper()}-{floor_id:02d}-{i+1:03d}"
        dev_name = f"{type_name_map.get(dev_type, '消防设备')}{i+1}"

        device = Device(
            tenant_id=tenant_id,
            device_code=dev_code,
            device_name=dev_name,
            device_type=type_name_map.get(dev_type, "消防设备"),
            building_id=floor.building_id,
            floor_id=floor_id,
            floor_x=float(dev_data.get("x", 50)),
            floor_y=float(dev_data.get("y", 50)),
            status="正常",
        )
        db.add(device)
        imported += 1

    db.commit()

    return {
        "message": "导入成功",
        "imported": imported,
    }


# ============================================================
# 历史导入图纸的查看与撤销
# ============================================================

def _match_imported_floor(
    db: Session,
    tenant_id: int,
    building_id: int,
    upload,
) -> Optional[Floor]:
    """找出某次 CAD 上传对应的楼层。

    优先用来源字段；历史数据没有该字段，退回按文件名匹配——导入时楼层名取自
    DXF 文件名（不含扩展名），所以两边能对上。
    """
    floor = db.query(Floor).filter(
        Floor.source_upload_id == upload.id,
        Floor.tenant_id == tenant_id,
        Floor.building_id == building_id,
    ).first()
    if floor:
        return floor

    stem = Path(upload.original_name or upload.filename or "").stem
    if not stem:
        return None
    return db.query(Floor).filter(
        Floor.floor_name == stem,
        Floor.tenant_id == tenant_id,
        Floor.building_id == building_id,
    ).first()


@router.get("/api/buildings/{building_id}/imported-drawings")
def list_imported_drawings(
    building_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """历史导入的 CAD 图纸清单，并标出各自关联的楼层与设备数。"""
    building = db.query(Building).filter(
        Building.id == building_id, Building.tenant_id == tenant_id
    ).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    items = []
    for upload in list_uploads(db, tenant_id, category="cad", limit=limit):
        floor = _match_imported_floor(db, tenant_id, building_id, upload)
        device_count = 0
        if floor:
            device_count = db.query(Device).filter(
                Device.floor_id == floor.id,
                Device.tenant_id == tenant_id,
            ).count()
        items.append({
            **upload_to_dict(upload),
            "floor_id": floor.id if floor else None,
            "floor_name": floor.floor_name if floor else "",
            "device_count": device_count,
        })

    return {
        "building": {"id": building.id, "name": building.building_name},
        "total": len(items),
        "items": items,
    }


@router.delete("/api/buildings/{building_id}/imported-drawings/{upload_id}")
def delete_imported_drawing(
    building_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """撤销一次图纸导入：删除上传文件、对应楼层及其上的设备。

    楼层上可能还有手工添加的设备，一并删除——所以前端确认框会先把设备数列出来。
    """
    upload = get_upload(db, tenant_id, upload_id)
    if not upload or upload.category != "cad":
        return JSONResponse(status_code=404, content={"message": "图纸不存在"})

    floor = _match_imported_floor(db, tenant_id, building_id, upload)
    removed_devices = 0
    removed_floor = ""
    if floor:
        devices = db.query(Device).filter(
            Device.floor_id == floor.id,
            Device.tenant_id == tenant_id,
        ).all()
        removed_devices = len(devices)
        for device in devices:
            db.delete(device)
        removed_floor = floor.floor_name
        db.delete(floor)
        db.commit()

    delete_upload(db, tenant_id, upload_id)

    return {
        "message": "已删除",
        "removed_floor": removed_floor,
        "removed_devices": removed_devices,
    }


# ============================================================
# 阶段三：BIM / IFC 模型 + 室内导航
# ============================================================

@router.get("/api/uploads/{category}/{filename}")
def download_upload(
    category: str,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """兼容旧链接的下载入口：仍按租户校验上传归属后才能读取。"""
    if category not in {"cad", "bim"} or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="文件不存在")

    upload = find_upload(db, tenant_id, category, filename)
    if not upload:
        raise HTTPException(status_code=404, detail="文件不存在")

    file_path = resolve_upload_path(upload)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, media_type=upload.media_type or "application/octet-stream")


@router.post("/api/bim/upload/{building_id}")
async def upload_bim_model(
    building_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building = db.query(Building).filter(Building.id == building_id, Building.tenant_id == tenant_id).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    content, ext = await read_validated_upload(file, BIM_EXTENSIONS, label="BIM模型")

    record = save_upload(
        db,
        tenant_id=tenant_id,
        category="bim",
        content=content,
        ext=ext,
        media_type="application/octet-stream",
        original_name=file.filename or "",
        owner_id=current_user.id,
        owner_name=current_user.real_name or current_user.username,
    )

    model_url = f"/api/files/{record.id}"

    return {
        "message": "上传成功",
        "modelUrl": model_url,
        "fileId": record.id,
        "fileName": file.filename,
        "fileSize": len(content),
        "format": ext.lstrip("."),
        "note": "模型解析中，可在前端直接加载查看"
    }


@router.get("/api/buildings/{building_id}/navigation")
def get_indoor_navigation(
    building_id: int,
    start_floor: int = 1,
    start_x: float = 10.0,
    start_y: float = 10.0,
    end_floor: int = 1,
    end_x: float = 80.0,
    end_y: float = 80.0,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building = db.query(Building).filter(Building.id == building_id, Building.tenant_id == tenant_id).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    path = calculate_evacuation_path(
        start_floor, start_x, start_y,
        end_floor, end_x, end_y
    )

    exits = [
        {"id": 1, "name": "正门", "floor": 1, "x": 5, "y": 50, "width": 2, "capacity": 50},
        {"id": 2, "name": "后门", "floor": 1, "x": 95, "y": 50, "width": 2, "capacity": 30},
        {"id": 3, "name": "消防通道A", "floor": 1, "x": 25, "y": 5, "width": 1.5, "capacity": 20},
        {"id": 4, "name": "消防通道B", "floor": 1, "x": 75, "y": 95, "width": 1.5, "capacity": 20},
    ]

    hazards = [
        {"id": 1, "name": "着火点", "type": "fire", "floor": 1, "x": 55, "y": 45, "radius": 15},
        {"id": 2, "name": "烟雾区", "type": "smoke", "floor": 1, "x": 50, "y": 50, "radius": 25},
    ]

    return {
        "path": path,
        "exits": exits,
        "hazards": hazards,
        "distance": path.get("distance", 0),
        "estimatedTime": path.get("estimatedTime", 0),
    }


def calculate_evacuation_path(
    start_floor: int, start_x: float, start_y: float,
    end_floor: int, end_x: float, end_y: float,
) -> Dict[str, Any]:
    waypoints = []

    waypoints.append({"floor": start_floor, "x": start_x, "y": start_y, "type": "start"})

    if start_floor != end_floor:
        stair_x = 50.0
        stair_y = 50.0
        waypoints.append({"floor": start_floor, "x": stair_x, "y": stair_y, "type": "stair"})
        waypoints.append({"floor": end_floor, "x": stair_x, "y": stair_y, "type": "stair"})

    waypoints.append({"floor": end_floor, "x": end_x, "y": end_y, "type": "end"})

    total_dist = 0.0
    for i in range(len(waypoints) - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        if p1["floor"] == p2["floor"]:
            dx = p2["x"] - p1["x"]
            dy = p2["y"] - p1["y"]
            total_dist += math.sqrt(dx * dx + dy * dy)
        else:
            total_dist += 5.0

    avg_speed = 1.5
    estimated_time = total_dist / avg_speed

    return {
        "waypoints": waypoints,
        "distance": round(total_dist, 2),
        "estimatedTime": round(estimated_time, 1),
    }


@router.get("/api/buildings/{building_id}/evacuation-plan")
def get_evacuation_plan(
    building_id: int,
    floor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building = db.query(Building).filter(Building.id == building_id, Building.tenant_id == tenant_id).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})

    assembly_points = [
        {"id": 1, "name": "东广场集合点", "x": 100, "y": 50, "capacity": 200, "description": "建筑东侧广场"},
        {"id": 2, "name": "西操场集合点", "x": -10, "y": 50, "capacity": 300, "description": "西侧操场安全区域"},
        {"id": 3, "name": "南停车场集合点", "x": 50, "y": 100, "capacity": 150, "description": "南侧露天停车场"},
    ]

    evacuation_routes = [
        {
            "id": 1,
            "name": "东侧疏散路线",
            "floor": 1,
            "path": [
                {"x": 20, "y": 20}, {"x": 20, "y": 50}, {"x": 5, "y": 50}
            ],
            "exitId": 1,
            "assemblyId": 1,
            "estimatedTime": 3,
        },
        {
            "id": 2,
            "name": "西侧疏散路线",
            "floor": 1,
            "path": [
                {"x": 80, "y": 20}, {"x": 80, "y": 50}, {"x": 95, "y": 50}
            ],
            "exitId": 2,
            "assemblyId": 2,
            "estimatedTime": 3,
        },
        {
            "id": 3,
            "name": "南侧疏散路线",
            "floor": 1,
            "path": [
                {"x": 25, "y": 80}, {"x": 25, "y": 95}
            ],
            "exitId": 3,
            "assemblyId": 3,
            "estimatedTime": 2.5,
        },
    ]

    danger_zones = [
        {"id": 1, "name": "配电室", "x": 15, "y": 75, "radius": 10, "level": "high"},
        {"id": 2, "name": "化学品仓库", "x": 85, "y": 25, "radius": 8, "level": "critical"},
    ]

    return {
        "buildingId": building_id,
        "assemblyPoints": assembly_points,
        "evacuationRoutes": evacuation_routes,
        "dangerZones": danger_zones,
    }


# ============================================================
# 全局统计 & Dashboard API
# ============================================================

@router.get("/api/overview/stats")
def get_overview_stats(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    total_buildings = db.query(Building).filter(Building.tenant_id == tenant_id).count()
    total_floors = db.query(Floor).filter(Floor.tenant_id == tenant_id).count()
    total_devices = db.query(Device).filter(Device.tenant_id == tenant_id).count()

    normal_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "正常") | (Device.status == "在线") | (Device.status == "online")
    ).count()
    offline_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "离线") | (Device.status == "offline")
    ).count()
    alarm_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "告警") | (Device.status == "alarm") | (Device.status == "故障")
    ).count()
    warning_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "预警") | (Device.status == "warning") | (Device.status == "待维保")
    ).count()

    device_type_stats = {}
    all_devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
    type_name_map = {
        "烟感探测器": "smoke",
        "烟感": "smoke",
        "温感探测器": "heat",
        "温感": "heat",
        "消火栓": "hydrant",
        "消防栓": "hydrant",
        "喷淋头": "sprinkler",
        "喷淋": "sprinkler",
        "手报按钮": "manual",
        "手动报警": "manual",
        "灭火器": "extinguisher",
    }
    for d in all_devices:
        t = type_name_map.get(d.device_type, "other")
        device_type_stats[t] = device_type_stats.get(t, 0) + 1

    total_alarms = db.query(Alert).filter(Alert.tenant_id == tenant_id).count()

    recent_alarms = db.query(Alert).filter(
        Alert.tenant_id == tenant_id
    ).order_by(Alert.created_at.desc()).limit(10).all()
    alarm_list = []
    level_map = {
        "critical": "danger",
        "high": "danger",
        "medium": "warning",
        "low": "info",
        "info": "info",
    }
    for a in recent_alarms:
        building = db.query(Building).filter(Building.id == a.building_id, Building.tenant_id == tenant_id).first()
        alarm_list.append({
            "id": a.id,
            "type": a.alert_type or "设备告警",
            "level": level_map.get(a.severity, "warning"),
            "content": a.description or "",
            "location": f"{building.building_name if building else ''} {a.location or ''}".strip(),
            "time": a.created_at.strftime("%H:%M:%S") if a.created_at else "",
        })

    buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()
    building_list = []
    for b in buildings:
        b_devices = db.query(Device).filter(Device.building_id == b.id, Device.tenant_id == tenant_id).count()
        b_alarms = db.query(Alert).filter(Alert.building_id == b.id, Alert.tenant_id == tenant_id).count()
        building_list.append({
            "id": b.id,
            "name": b.building_name,
            "floors": b.floors,
            "deviceCount": b_devices,
            "alarmCount": b_alarms,
            "status": "normal" if b_alarms == 0 else "warning",
            # 与 screen-data 保持一致：Building 上没有 x_coord/y_coord 字段，
            # 之前那两行恒为 0，属误导性字段，不再下发
        })

    return {
        "buildings": {
            "total": total_buildings,
            "floors": total_floors,
            "list": building_list,
        },
        "devices": {
            "total": total_devices,
            "normal": normal_count,
            "warning": warning_count,
            "fault": offline_count + alarm_count,
            "alarm": alarm_count,
            "byType": device_type_stats,
        },
        "alarms": {
            "total": total_alarms,
            "recent": alarm_list,
        },
    }


# ============================================================
# 设备管理 CRUD
# ============================================================

def _map_status_to_cn(status: str) -> str:
    status_map = {
        "normal": "正常",
        "online": "正常",
        "warning": "预警",
        "alarm": "告警",
        "fault": "故障",
        "offline": "离线",
    }
    return status_map.get(status, status or "正常")


@router.post("/api/devices")
def create_device(
    device_data: Dict[str, Any],
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    building_id = device_data.get("building_id") or device_data.get("buildingId")
    floor_id = device_data.get("floor_id") or device_data.get("floorId")
    
    if not building_id or not floor_id:
        return JSONResponse(status_code=400, content={"message": "建筑和楼层必填"})
    
    building = db.query(Building).filter(Building.id == building_id, Building.tenant_id == tenant_id).first()
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.tenant_id == tenant_id).first()
    if not building:
        return JSONResponse(status_code=404, content={"message": "建筑不存在"})
    if not floor:
        return JSONResponse(status_code=404, content={"message": "楼层不存在"})
    
    raw_status = device_data.get("status") or "正常"
    status = _map_status_to_cn(raw_status)
    
    device = Device(
        tenant_id=tenant_id,
        device_code=device_data.get("code") or device_data.get("device_code") or "",
        device_name=device_data.get("name") or device_data.get("device_name") or "",
        device_type=device_data.get("typeLabel") or device_data.get("device_type") or "烟感探测器",
        building_id=building_id,
        floor_id=floor_id,
        floor_x=float(device_data.get("x") or device_data.get("floor_x") or 50),
        floor_y=float(device_data.get("y") or device_data.get("floor_y") or 50),
        status=status,
        location=device_data.get("location") or "",
        description=device_data.get("description") or "",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    return {"message": "创建设备成功", "device": {"id": device.id}}


@router.put("/api/devices/{device_id}")
def update_device(
    device_id: int,
    device_data: Dict[str, Any],
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == tenant_id).first()
    if not device:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})
    
    if "name" in device_data or "device_name" in device_data:
        device.device_name = device_data.get("name") or device_data.get("device_name") or device.device_name
    if "code" in device_data or "device_code" in device_data:
        device.device_code = device_data.get("code") or device_data.get("device_code") or device.device_code
    if "typeLabel" in device_data or "device_type" in device_data:
        device.device_type = device_data.get("typeLabel") or device_data.get("device_type") or device.device_type
    if "status" in device_data:
        device.status = _map_status_to_cn(device_data["status"])
    if "x" in device_data or "floor_x" in device_data:
        device.floor_x = float(device_data.get("x") or device_data.get("floor_x") or device.floor_x or 0)
    if "y" in device_data or "floor_y" in device_data:
        device.floor_y = float(device_data.get("y") or device_data.get("floor_y") or device.floor_y or 0)
    if "location" in device_data:
        device.location = device_data["location"]
    if "description" in device_data:
        device.description = device_data["description"]
    
    db.commit()
    
    return {"message": "更新设备成功"}


@router.delete("/api/devices/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    device = db.query(Device).filter(Device.id == device_id, Device.tenant_id == tenant_id).first()
    if not device:
        return JSONResponse(status_code=404, content={"message": "设备不存在"})
    
    db.delete(device)
    db.commit()
    
    return {"message": "删除设备成功"}


@router.get("/api/alerts/list")
def get_alert_list(
    page: int = 1,
    page_size: int = 20,
    building_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(Alert).filter(Alert.tenant_id == tenant_id)
    if building_id:
        query = query.filter(Alert.building_id == building_id)
    
    total = query.count()
    alerts = query.order_by(Alert.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    level_map = {
        "critical": "danger",
        "high": "danger",
        "medium": "warning",
        "low": "info",
        "info": "info",
    }
    
    alert_list = []
    for a in alerts:
        building = db.query(Building).filter(Building.id == a.building_id, Building.tenant_id == tenant_id).first()
        device = db.query(Device).filter(Device.id == a.device_id, Device.tenant_id == tenant_id).first()
        alert_list.append({
            "id": a.id,
            "alertType": a.alert_type or "",
            "level": level_map.get(a.severity, "warning"),
            "description": a.description or "",
            "buildingName": building.building_name if building else "",
            "deviceName": device.device_name if device else "",
            "location": a.location or "",
            "status": a.status or "未处理",
            "createdAt": a.created_at.isoformat() if a.created_at else "",
        })
    
    return {
        "items": alert_list,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


# ============================================================
# 数据大屏 API
# ============================================================

@router.get("/api/dashboard/screen-data")
def get_data_screen_data(db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)):
    total_devices = db.query(Device).filter(Device.tenant_id == tenant_id).count()
    normal_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "正常") | (Device.status == "在线") | (Device.status == "online")
    ).count()
    offline_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "离线") | (Device.status == "offline")
    ).count()
    alarm_count = db.query(Device).filter(
        Device.tenant_id == tenant_id,
        (Device.status == "告警") | (Device.status == "alarm") | (Device.status == "故障")
    ).count()

    type_name_map = {
        "烟感探测器": "smoke",
        "烟感": "smoke",
        "温感探测器": "heat",
        "温感": "heat",
        "消火栓": "hydrant",
        "消防栓": "hydrant",
        "喷淋头": "sprinkler",
        "喷淋": "sprinkler",
        "手报按钮": "manual",
        "手动报警": "manual",
        "灭火器": "extinguisher",
    }
    type_label_map = {v: k for k, v in type_name_map.items()}
    device_type_stats = {}
    all_devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
    for d in all_devices:
        t = type_name_map.get(d.device_type, "other")
        device_type_stats[t] = device_type_stats.get(t, 0) + 1
    
    device_types_list = []
    type_colors = {
        "smoke": "#3b82f6",
        "heat": "#22c55e",
        "hydrant": "#06b6d4",
        "sprinkler": "#8b5cf6",
        "manual": "#f59e0b",
        "extinguisher": "#ef4444",
        "other": "#64748b",
    }
    max_type_count = max(device_type_stats.values()) if device_type_stats else 1
    for t, count in device_type_stats.items():
        device_types_list.append({
            "name": type_label_map.get(t, "其他设备"),
            "count": count,
            "percent": round(count / max_type_count * 100, 1),
            "color": type_colors.get(t, "#64748b"),
        })
    device_types_list.sort(key=lambda x: -x["count"])

    total_alarms = db.query(Alert).filter(Alert.tenant_id == tenant_id).count()
    critical_count = db.query(Alert).filter(
        Alert.tenant_id == tenant_id,
        (Alert.severity == "critical") | (Alert.severity == "high")
    ).count()
    high_count = db.query(Alert).filter(Alert.tenant_id == tenant_id, Alert.severity == "high").count()
    medium_count = db.query(Alert).filter(Alert.tenant_id == tenant_id, Alert.severity == "medium").count()
    low_count = db.query(Alert).filter(
        Alert.tenant_id == tenant_id,
        (Alert.severity == "low") | (Alert.severity == "info")
    ).count()

    from datetime import timedelta
    today = datetime.now().date()
    alarm_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        # `created_at` 落库为无时区 UTC，窗口边界必须换算到同一基准：
        # 直接用本地零点会让「今日」从本地 08:00（UTC+8）才开始，凌晨的告警被漏掉
        day_start = local_day_start_utc(i)
        day_end = local_day_end_utc(i)
        day_count = db.query(Alert).filter(
            Alert.tenant_id == tenant_id,
            Alert.created_at >= day_start,
            Alert.created_at <= day_end,
        ).count()
        date_str = day.strftime("%m/%d") if i > 0 else "今日"
        alarm_trend.append({
            "date": date_str,
            "count": day_count,
            "percent": 0,
        })
    max_trend_count = max(a["count"] for a in alarm_trend) if alarm_trend else 1
    for a in alarm_trend:
        a["percent"] = round(a["count"] / max_trend_count * 100, 1) if max_trend_count > 0 else 0

    today_start = local_day_start_utc()
    today_end = local_day_end_utc()
    today_alarm_count = db.query(Alert).filter(
        Alert.tenant_id == tenant_id,
        Alert.created_at >= today_start,
        Alert.created_at <= today_end,
    ).count()

    recent_alarms = db.query(Alert).filter(
        Alert.tenant_id == tenant_id
    ).order_by(Alert.created_at.desc()).limit(10).all()
    level_screen_map = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "info": "low",
    }
    level_text_map = {
        "critical": "严重",
        "high": "高危",
        "medium": "中危",
        "low": "低危",
    }
    realtime_alarms = []
    for idx, a in enumerate(recent_alarms):
        building = db.query(Building).filter(Building.id == a.building_id, Building.tenant_id == tenant_id).first()
        level = level_screen_map.get(a.severity, "medium")
        # 与 created_at 同为无时区 UTC 才能相减：用本地时间会让刚产生的告警显示成「8小时前」
        now = datetime.utcnow()
        time_diff = now - a.created_at if a.created_at else now - now
        time_str = "刚刚"
        if time_diff.total_seconds() > 60:
            minutes = int(time_diff.total_seconds() // 60)
            time_str = f"{minutes}分钟前"
        if time_diff.total_seconds() > 3600:
            hours = int(time_diff.total_seconds() // 3600)
            time_str = f"{hours}小时前"
        realtime_alarms.append({
            "id": a.id,
            "title": a.alert_type or a.description or "设备告警",
            "location": f"{building.building_name if building else ''} {a.location or ''}".strip(),
            "time": time_str,
            "level": level,
            "levelText": level_text_map.get(level, "中危"),
        })

    total_buildings = db.query(Building).filter(Building.tenant_id == tenant_id).count()
    buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()

    # 一次分组查询取回各建筑的设备数/告警数/严重告警数，避免逐栋建筑发查询（大屏 30 秒轮询一次）
    device_by_building = {
        key: int(count)
        for key, count in db.query(Device.building_id, func.count(Device.id))
        .filter(Device.tenant_id == tenant_id, Device.building_id.isnot(None))
        .group_by(Device.building_id)
        .all()
    }
    alarm_by_building = {
        key: int(count)
        for key, count in db.query(Alert.building_id, func.count(Alert.id))
        .filter(Alert.tenant_id == tenant_id, Alert.building_id.isnot(None))
        .group_by(Alert.building_id)
        .all()
    }
    severe_by_building = {
        key: int(count)
        for key, count in db.query(Alert.building_id, func.count(Alert.id))
        .filter(
            Alert.tenant_id == tenant_id,
            Alert.building_id.isnot(None),
            Alert.severity.in_(("critical", "high")),
        )
        .group_by(Alert.building_id)
        .all()
    }

    building_list = []
    for b in buildings:
        b_alarms = alarm_by_building.get(b.id, 0)
        status = "normal"
        if severe_by_building.get(b.id, 0) > 0:
            status = "alarm"
        elif b_alarms > 0:
            status = "warning"
        building_list.append({
            "id": b.id,
            "name": b.building_name,
            # 经纬度供大屏 3D 场景/热力图推算相对布局，不存在的 x_coord/y_coord 不再下发
            "latitude": b.latitude or 0.0,
            "longitude": b.longitude or 0.0,
            "type": b.building_type or "office",
            "floors": b.floors or 1,
            "area": round(b.area or 0.0, 1),
            "deviceCount": device_by_building.get(b.id, 0),
            "alarmCount": b_alarms,
            "riskScore": round(b.risk_score or 0, 1),
            "riskLevel": b.risk_level or "",
            "status": status,
        })

    # ---------------- 隐患治理（真实：巡检记录中抽取的隐患 + 工单闭环率） ----------------
    hazard_total = 0
    hazard_counter: Dict[str, int] = {}
    for (raw_hazards,) in db.query(InspectionRecord.hazards).filter(
        InspectionRecord.tenant_id == tenant_id
    ).all():
        for name in _parse_str_list(raw_hazards):
            hazard_total += 1
            category = _hazard_category(name)
            hazard_counter[category] = hazard_counter.get(category, 0) + 1

    hazard_types = [
        {"name": name, "count": count, "color": HAZARD_CATEGORY_COLORS.get(name, "#64748b")}
        for name, count in sorted(hazard_counter.items(), key=lambda kv: -kv[1])
    ]

    ticket_total = db.query(FaultTicket).filter(FaultTicket.tenant_id == tenant_id).count()
    ticket_closed = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == tenant_id,
        FaultTicket.status.in_(CLOSED_TICKET_STATUSES),
    ).count()
    hazard_rate = round(ticket_closed / ticket_total * 100, 1) if ticket_total else 0.0

    # ---------------- 消防水源 / 电气火灾（真实设备状态与遥测） ----------------
    water_stats = _device_group_stats(db, all_devices, WATER_DEVICE_KEYWORDS)
    water_system = {
        **water_stats,
        "runningPumps": sum(
            1 for d in all_devices
            if "泵" in f"{d.device_type or ''}{d.device_name or ''}" and (d.status or "") in ONLINE_STATUSES
        ),
        # 无数据源，前端显示为「--」，不填充编造数值
        "pressure": None,
        "tankLevel": None,
    }

    electric_stats = _device_group_stats(db, all_devices, ELECTRIC_DEVICE_KEYWORDS, with_temperature=True)
    electric_system = {
        **electric_stats,
        "warningCircuits": electric_stats["alarm"],
        "maxLeakage": None,
    }

    # ---------------- 值班信息（真实排班） ----------------
    duty_shift = _current_duty_shift(db, tenant_id, today)
    duty_info = {
        "hasDuty": bool(duty_shift),
        "shift": f"{duty_shift.shift_name}值班中" if duty_shift else "当前无排班",
        "period": f"{duty_shift.start_time}-{duty_shift.end_time}" if duty_shift else "",
        "persons": _parse_str_list(duty_shift.persons) if duty_shift else [],
    }

    # ---------------- 重点区域视频（真实通道台账） ----------------
    video_rows = db.query(VideoChannel).filter(
        VideoChannel.tenant_id == tenant_id,
        VideoChannel.enabled == True,  # noqa: E712 - SQLAlchemy 需要显式比较
    ).order_by(VideoChannel.channel_code.asc()).limit(6).all()
    video_list = [
        {
            "id": row.id,
            "name": row.channel_name or row.channel_code,
            "online": row.status == "online",
        }
        for row in video_rows
    ]
    enabled_video_total = db.query(VideoChannel).filter(
        VideoChannel.tenant_id == tenant_id,
        VideoChannel.enabled == True,  # noqa: E712
    ).count()
    enabled_video_online = db.query(VideoChannel).filter(
        VideoChannel.tenant_id == tenant_id,
        VideoChannel.enabled == True,  # noqa: E712
        VideoChannel.status == "online",
    ).count()

    # ---------------- 今日事件（真实：今日告警 / 巡检 / 工单合并后按时间倒序） ----------------
    events: List[Dict[str, Any]] = []
    for row in db.query(Alert).filter(
        Alert.tenant_id == tenant_id,
        Alert.created_at >= today_start,
        Alert.created_at <= today_end,
    ).order_by(Alert.created_at.desc()).limit(6).all():
        title = row.alert_type or row.description or "设备告警"
        events.append({
            "id": f"alert-{row.id}",
            "title": f"{title}（{row.location}）" if row.location else title,
            "time": row.created_at.strftime("%H:%M") if row.created_at else "",
            "type": "alarm",
            "_ts": row.created_at,
        })
    for row in db.query(InspectionRecord).filter(
        InspectionRecord.tenant_id == tenant_id,
        InspectionRecord.created_at >= today_start,
        InspectionRecord.created_at <= today_end,
    ).order_by(InspectionRecord.created_at.desc()).limit(6).all():
        events.append({
            "id": f"inspection-{row.id}",
            "title": f"完成巡检：{row.device_name or row.location or '巡检点'}",
            "time": row.created_at.strftime("%H:%M") if row.created_at else "",
            "type": "inspection",
            "_ts": row.created_at,
        })
    for row in db.query(FaultTicket).filter(
        FaultTicket.tenant_id == tenant_id,
        FaultTicket.created_at >= today_start,
        FaultTicket.created_at <= today_end,
    ).order_by(FaultTicket.created_at.desc()).limit(6).all():
        events.append({
            "id": f"ticket-{row.id}",
            "title": f"整改工单：{row.title or '隐患整改'}（{row.status or '待受理'}）",
            "time": row.created_at.strftime("%H:%M") if row.created_at else "",
            "type": "maintenance",
            "_ts": row.created_at,
        })
    events.sort(key=lambda item: item["_ts"] or datetime.min, reverse=True)
    today_events = [
        {key: value for key, value in event.items() if key != "_ts"} for event in events[:8]
    ]

    # ---------------- 待办事项（真实：未闭环的整改工单） ----------------
    todos = [
        {
            "id": row.id,
            "title": row.title or "隐患整改",
            "status": row.status or "",
            "level": "high" if (row.priority or "") in ("紧急", "高", "high", "urgent") else "normal",
            "location": row.building_name or "",
            "deadline": row.deadline.strftime("%m-%d") if row.deadline else "",
        }
        for row in db.query(FaultTicket).filter(
            FaultTicket.tenant_id == tenant_id,
            FaultTicket.status.in_(OPEN_TICKET_STATUSES),
        ).order_by(FaultTicket.created_at.desc()).limit(5).all()
    ]

    # ---------------- 风险排名（真实：按建筑风险评分排序） ----------------
    risk_rank = [
        {
            "id": b.id,
            "name": b.building_name,
            "value": round(b.risk_score or 0, 1),
            "color": _risk_color(b.risk_score or 0),
        }
        for b in sorted(buildings, key=lambda item: -(item.risk_score or 0))[:5]
    ]

    # ---------------- 运行指标（四项全部来自真实统计） ----------------
    online_rate = round(normal_count / total_devices * 100, 1) if total_devices > 0 else 0.0
    alert_resolved = db.query(Alert).filter(
        Alert.tenant_id == tenant_id,
        Alert.status.in_(("resolved", "merged")),
    ).count()
    alert_resolve_rate = round(alert_resolved / total_alarms * 100, 1) if total_alarms else 0.0
    video_online_rate = (
        round(enabled_video_online / enabled_video_total * 100, 1) if enabled_video_total else 0.0
    )

    def _indicator(name: str, value: float, *, threshold: float = 80.0) -> Dict[str, Any]:
        return {
            "name": name,
            "value": value,
            "unit": "%",
            "percent": value,
            "status": "good" if value >= threshold else "warning",
        }

    indicators = [
        _indicator("设备在线率", online_rate, threshold=90.0),
        _indicator("隐患整改率", hazard_rate, threshold=80.0),
        _indicator("告警处置率", alert_resolve_rate, threshold=80.0),
        _indicator("视频在线率", video_online_rate, threshold=90.0),
    ]

    return {
        "devices": {
            "total": total_devices,
            "online": normal_count,
            "offline": offline_count,
            "alarm": alarm_count,
            "types": device_types_list,
        },
        "alarms": {
            "stats": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "today": today_alarm_count,
            },
            "trend": alarm_trend,
            "realtime": realtime_alarms,
        },
        "buildings": {
            "total": total_buildings,
            "list": building_list,
        },
        "hazards": {
            "total": hazard_total,
            "rate": hazard_rate,
            "types": hazard_types,
            "ticketTotal": ticket_total,
            "ticketClosed": ticket_closed,
        },
        "waterSystem": water_system,
        "electricSystem": electric_system,
        "dutyInfo": duty_info,
        "videoList": video_list,
        "todayEvents": today_events,
        "indicators": indicators,
        "todos": todos,
        "riskRank": risk_rank,
    }
