"""
值班排班服务

此前值班只有只读接口：排班表、值班记录、交接班都只能看不能改，前端「新增排班 / 保存 /
交接班」全是假动作。这里补齐写入能力，并做基本校验：

- 排班必须给日期与班次名，时间格式为 HH:MM；
- 同一租户、同一天不允许出现两个同名班次；
- 同一人在同一天不允许被排进两个班次（跨天不冲突）；
- 写入一律限定在本租户内，别人的记录按「不存在」处理，不泄露其存在性。
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import DutyHandover, DutyRecord, DutyShift
# 日期解析统一走 common_utils（各模块同一实现，避免同一个入参在不同接口表现不一致）
from services.common_utils import parse_date

SHIFT_STATUSES = ("active", "inactive")
DEFAULT_SHIFT_STATUS = "active"
# 班次时间接受 "8:00" / "08:00" 这类写法，统一规范化成 HH:MM
_TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")
_PERSON_NAME_KEYS = ("name", "real_name", "realName", "username")


def _fail(message: str, *, not_found: bool = False) -> Dict[str, Any]:
    return {"ok": False, "message": message, "not_found": not_found}


def _pick(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """同时接受前端常见的 snake_case 与 camelCase 字段名。"""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _parse_time(raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    matched = _TIME_PATTERN.match(raw.strip())
    if not matched:
        return None
    hour, minute = int(matched.group(1)), int(matched.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def person_names(raw: Any) -> List[str]:
    """从排班人员字段里取人名。

    历史数据里 `persons` 既可能是 `["张三"]`，也可能是 `[{"id":1,"name":"张三"}]`，
    两种都要能取到名字，否则冲突校验会漏。
    """
    items = raw
    if isinstance(items, str):
        text = items.strip()
        if not text:
            return []
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            items = [part.strip() for part in text.split(",")]
    if not isinstance(items, list):
        return []

    names: List[str] = []
    for item in items:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = ""
            for key in _PERSON_NAME_KEYS:
                if item.get(key):
                    name = str(item[key]).strip()
                    break
        else:
            name = ""
        if name:
            names.append(name)
    return names


def _dump_json_list(raw: Any) -> str:
    """统一按 JSON 文本落库；传字符串时按 JSON 或逗号分隔解析。"""
    if raw is None:
        return "[]"
    items = raw
    if isinstance(items, str):
        text = items.strip()
        if not text:
            return "[]"
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            items = [part.strip() for part in text.split(",") if part.strip()]
    if not isinstance(items, list):
        return "[]"
    return json.dumps(items, ensure_ascii=False)


def _parse_count(raw: Any, default: int = 0) -> int:
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def shift_to_dict(shift: DutyShift) -> Dict[str, Any]:
    """排班序列化。

    `persons` 原样返回库里存的结构：历史数据既有 `["张三"]` 也有 `[{id,name,role}]`，
    而值班室页面按 `p.name` 取值，压成姓名列表会让「交班人」「值班人」变空。
    """
    try:
        persons = json.loads(shift.persons or "[]")
    except json.JSONDecodeError:
        persons = []
    return {
        "id": shift.id,
        "shiftName": shift.shift_name,
        "shiftType": shift.shift_type,
        "startTime": shift.start_time,
        "endTime": shift.end_time,
        "dutyDate": shift.duty_date.isoformat() if shift.duty_date else None,
        "persons": persons,
        "status": shift.status,
        "remark": shift.remark,
    }


def record_to_dict(record: DutyRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "recordDate": record.record_date.isoformat() if record.record_date else None,
        "shiftId": record.shift_id,
        "shiftName": record.shift_name,
        "dutyPerson": record.duty_person,
        "weather": record.weather,
        "alarmCount": record.alarm_count,
        "handledCount": record.handled_count,
        "inspectionCount": record.inspection_count,
        "abnormalCount": record.abnormal_count,
        "equipmentStatus": record.equipment_status,
        "content": record.content,
        "createdAt": record.created_at.isoformat() if record.created_at else None,
    }


def handover_to_dict(handover: DutyHandover, shift_name: str = "") -> Dict[str, Any]:
    """交接班序列化。

    表里只存了 `shift_id`，班次名由调用方查一次批量补上（不额外建冗余列）。
    """
    return {
        "id": handover.id,
        "handoverTime": handover.handover_time.isoformat() if handover.handover_time else None,
        "shiftId": handover.shift_id,
        "shiftName": shift_name,
        "fromPerson": handover.from_person,
        "toPerson": handover.to_person,
        "pendingMatters": handover.pending_matters,
        "equipmentStatus": handover.equipment_status,
        "status": handover.status,
        "remark": handover.remark,
        "handoverItems": json.loads(handover.handover_items or "[]"),
    }


def _validate_shift_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """校验排班入参，返回规范化后的字段；不合法时返回 {"ok": False, ...}。"""
    shift_name = str(_pick(data, "shift_name", "shiftName", default="") or "").strip()
    if not shift_name:
        return _fail("班次名称不能为空")

    duty_date = parse_date(_pick(data, "duty_date", "dutyDate"))
    if duty_date is None:
        return _fail("排班日期不能为空，且格式需为 YYYY-MM-DD")

    start_time = _parse_time(_pick(data, "start_time", "startTime", default="08:00"))
    end_time = _parse_time(_pick(data, "end_time", "endTime", default="20:00"))
    if start_time is None or end_time is None:
        return _fail("班次时间格式需为 HH:MM")

    status = str(_pick(data, "status", default=DEFAULT_SHIFT_STATUS) or DEFAULT_SHIFT_STATUS)
    if status not in SHIFT_STATUSES:
        return _fail(f"班次状态只能是 {' / '.join(SHIFT_STATUSES)}")

    return {
        "ok": True,
        "shift_name": shift_name,
        "shift_type": str(_pick(data, "shift_type", "shiftType", default="day") or "day"),
        "start_time": start_time,
        "end_time": end_time,
        "duty_date": duty_date,
        "persons": _pick(data, "persons", default=[]),
        "status": status,
        "remark": str(_pick(data, "remark", default="") or ""),
    }


def _find_shift(db: Session, tenant_id: int, shift_id: int) -> Optional[DutyShift]:
    return db.query(DutyShift).filter(
        DutyShift.id == shift_id, DutyShift.tenant_id == tenant_id
    ).first()


def _check_shift_conflicts(
    db: Session,
    tenant_id: int,
    *,
    duty_date: date,
    shift_name: str,
    names: List[str],
    exclude_id: Optional[int] = None,
) -> Optional[str]:
    """返回冲突说明；没有冲突时返回 None。"""
    same_day = db.query(DutyShift).filter(
        DutyShift.tenant_id == tenant_id,
        DutyShift.duty_date == duty_date,
    ).all()

    for existing in same_day:
        if exclude_id is not None and existing.id == exclude_id:
            continue
        if existing.shift_name == shift_name:
            return f"{duty_date.isoformat()} 已存在班次「{shift_name}」"

    if names:
        for existing in same_day:
            if exclude_id is not None and existing.id == exclude_id:
                continue
            repeated = sorted(set(names) & set(person_names(existing.persons)))
            if repeated:
                return (
                    f"{duty_date.isoformat()} 的「{existing.shift_name}」已排班："
                    f"{'、'.join(repeated)}，同一天不能重复排班"
                )
    return None


def create_shift(db: Session, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _validate_shift_payload(data)
    if not payload.get("ok"):
        return payload

    names = person_names(payload["persons"])
    conflict = _check_shift_conflicts(
        db,
        tenant_id,
        duty_date=payload["duty_date"],
        shift_name=payload["shift_name"],
        names=names,
    )
    if conflict:
        return _fail(conflict)

    shift = DutyShift(
        tenant_id=tenant_id,
        shift_name=payload["shift_name"],
        shift_type=payload["shift_type"],
        start_time=payload["start_time"],
        end_time=payload["end_time"],
        duty_date=payload["duty_date"],
        persons=_dump_json_list(payload["persons"]),
        status=payload["status"],
        remark=payload["remark"],
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return {"ok": True, "message": "排班已创建", "shift": shift_to_dict(shift)}


def update_shift(db: Session, tenant_id: int, shift_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    shift = _find_shift(db, tenant_id, shift_id)
    if not shift:
        return _fail("排班不存在", not_found=True)

    # 局部更新：没传的字段保持原值，再整体校验一次。
    # `persons` 未传时保留原始 JSON 文本，避免把 [{id,name,role}] 压成纯姓名列表。
    merged = {
        "shift_name": _pick(data, "shift_name", "shiftName", default=shift.shift_name),
        "shift_type": _pick(data, "shift_type", "shiftType", default=shift.shift_type),
        "start_time": _pick(data, "start_time", "startTime", default=shift.start_time),
        "end_time": _pick(data, "end_time", "endTime", default=shift.end_time),
        "duty_date": _pick(data, "duty_date", "dutyDate", default=shift.duty_date),
        "status": _pick(data, "status", default=shift.status),
        "persons": data["persons"] if "persons" in data else shift.persons,
        "remark": _pick(data, "remark", default=shift.remark),
    }

    payload = _validate_shift_payload(merged)
    if not payload.get("ok"):
        return payload

    names = person_names(payload["persons"])
    conflict = _check_shift_conflicts(
        db,
        tenant_id,
        duty_date=payload["duty_date"],
        shift_name=payload["shift_name"],
        names=names,
        exclude_id=shift_id,
    )
    if conflict:
        return _fail(conflict)

    shift.shift_name = payload["shift_name"]
    shift.shift_type = payload["shift_type"]
    shift.start_time = payload["start_time"]
    shift.end_time = payload["end_time"]
    shift.duty_date = payload["duty_date"]
    shift.persons = _dump_json_list(payload["persons"])
    shift.status = payload["status"]
    shift.remark = payload["remark"]
    shift.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(shift)
    return {"ok": True, "message": "排班已更新", "shift": shift_to_dict(shift)}


def delete_shift(db: Session, tenant_id: int, shift_id: int) -> Dict[str, Any]:
    shift = _find_shift(db, tenant_id, shift_id)
    if not shift:
        return _fail("排班不存在", not_found=True)
    db.delete(shift)
    db.commit()
    return {"ok": True, "message": "排班已删除"}


def create_record(db: Session, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    record_date = parse_date(_pick(data, "record_date", "recordDate"))
    if record_date is None:
        return _fail("值班日期不能为空，且格式需为 YYYY-MM-DD")

    duty_person = str(_pick(data, "duty_person", "dutyPerson", default="") or "").strip()
    if not duty_person:
        return _fail("值班人员不能为空")

    shift_id = _pick(data, "shift_id", "shiftId")
    shift_name = str(_pick(data, "shift_name", "shiftName", default="") or "")
    if shift_id:
        shift = _find_shift(db, tenant_id, int(shift_id))
        if not shift:
            return _fail("所选排班不存在", not_found=True)
        shift_name = shift_name or shift.shift_name

    record = DutyRecord(
        tenant_id=tenant_id,
        record_date=record_date,
        shift_id=int(shift_id) if shift_id else None,
        shift_name=shift_name,
        duty_person=duty_person,
        weather=str(_pick(data, "weather", default="") or ""),
        alarm_count=_parse_count(_pick(data, "alarm_count", "alarmCount")),
        handled_count=_parse_count(_pick(data, "handled_count", "handledCount")),
        inspection_count=_parse_count(_pick(data, "inspection_count", "inspectionCount")),
        abnormal_count=_parse_count(_pick(data, "abnormal_count", "abnormalCount")),
        equipment_status=str(_pick(data, "equipment_status", "equipmentStatus", default="normal") or "normal"),
        content=str(_pick(data, "content", default="") or ""),
        remark=str(_pick(data, "remark", default="") or ""),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "message": "值班记录已保存", "record": record_to_dict(record)}


def update_record(db: Session, tenant_id: int, record_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    record = db.query(DutyRecord).filter(
        DutyRecord.id == record_id, DutyRecord.tenant_id == tenant_id
    ).first()
    if not record:
        return _fail("值班记录不存在", not_found=True)

    if any(key in data for key in ("record_date", "recordDate")):
        record_date = parse_date(_pick(data, "record_date", "recordDate"))
        if record_date is None:
            return _fail("值班日期不能为空，且格式需为 YYYY-MM-DD")
        record.record_date = record_date
    if any(key in data for key in ("duty_person", "dutyPerson")):
        duty_person = str(_pick(data, "duty_person", "dutyPerson", default="") or "").strip()
        if not duty_person:
            return _fail("值班人员不能为空")
        record.duty_person = duty_person

    field_map = {
        "shift_name": ("shift_name", "shiftName"),
        "weather": ("weather",),
        "equipment_status": ("equipment_status", "equipmentStatus"),
        "content": ("content",),
        "remark": ("remark",),
    }
    for column, keys in field_map.items():
        if any(key in data for key in keys):
            setattr(record, column, str(_pick(data, *keys, default="") or ""))

    count_map = {
        "alarm_count": ("alarm_count", "alarmCount"),
        "handled_count": ("handled_count", "handledCount"),
        "inspection_count": ("inspection_count", "inspectionCount"),
        "abnormal_count": ("abnormal_count", "abnormalCount"),
    }
    for column, keys in count_map.items():
        if any(key in data for key in keys):
            setattr(record, column, _parse_count(_pick(data, *keys)))

    if any(key in data for key in ("shift_id", "shiftId")):
        shift_id = _pick(data, "shift_id", "shiftId")
        if shift_id:
            shift = _find_shift(db, tenant_id, int(shift_id))
            if not shift:
                return _fail("所选排班不存在", not_found=True)
            record.shift_id = int(shift_id)
            record.shift_name = shift.shift_name
        else:
            record.shift_id = None

    db.commit()
    db.refresh(record)
    return {"ok": True, "message": "值班记录已更新", "record": record_to_dict(record)}


def delete_record(db: Session, tenant_id: int, record_id: int) -> Dict[str, Any]:
    record = db.query(DutyRecord).filter(
        DutyRecord.id == record_id, DutyRecord.tenant_id == tenant_id
    ).first()
    if not record:
        return _fail("值班记录不存在", not_found=True)
    db.delete(record)
    db.commit()
    return {"ok": True, "message": "值班记录已删除"}


def create_handover(db: Session, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    from_person = str(_pick(data, "from_person", "fromPerson", default="") or "").strip()
    to_person = str(_pick(data, "to_person", "toPerson", default="") or "").strip()
    if not from_person or not to_person:
        return _fail("交班人与接班人都不能为空")

    shift_id = _pick(data, "shift_id", "shiftId")
    shift = _find_shift(db, tenant_id, int(shift_id)) if shift_id else None
    if shift_id and not shift:
        return _fail("所选排班不存在", not_found=True)

    handover_time = _pick(data, "handover_time", "handoverTime")
    parsed_time = None
    if handover_time:
        try:
            parsed_time = datetime.fromisoformat(str(handover_time).replace("Z", "+00:00"))
            if parsed_time.tzinfo is not None:
                parsed_time = parsed_time.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            return _fail("交接时间格式不正确")

    handover = DutyHandover(
        tenant_id=tenant_id,
        handover_time=parsed_time or datetime.utcnow(),
        shift_id=int(shift_id) if shift_id else None,
        from_person=from_person,
        to_person=to_person,
        handover_items=_dump_json_list(_pick(data, "handover_items", "handoverItems", default=[])),
        pending_matters=str(_pick(data, "pending_matters", "pendingMatters", default="") or ""),
        equipment_status=str(_pick(data, "equipment_status", "equipmentStatus", default="normal") or "normal"),
        status=str(_pick(data, "status", default="completed") or "completed"),
        remark=str(_pick(data, "remark", default="") or ""),
    )
    db.add(handover)
    db.commit()
    db.refresh(handover)
    return {
        "ok": True,
        "message": "交接班已记录",
        "handover": handover_to_dict(handover, shift.shift_name if shift else ""),
    }


def delete_handover(db: Session, tenant_id: int, handover_id: int) -> Dict[str, Any]:
    handover = db.query(DutyHandover).filter(
        DutyHandover.id == handover_id, DutyHandover.tenant_id == tenant_id
    ).first()
    if not handover:
        return _fail("交接班记录不存在", not_found=True)
    db.delete(handover)
    db.commit()
    return {"ok": True, "message": "交接班记录已删除"}
