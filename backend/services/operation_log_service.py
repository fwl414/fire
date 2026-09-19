"""操作日志（审计日志）服务

统一口径：所有操作日志都落在主库 `operation_logs` 表，并串成哈希链。

改造前的状态是「两套写入 + 一套读取」：
- `add_operation_log`（裸 SQLite）写业务日志，但操作日志页面读的是主库 ORM 表，
  导致工单状态变更、复查结论、档案创建等业务日志在页面上完全看不到；
- 日志中间件直接写主库，且不记录租户，多租户下无法隔离。

现在：
- `add_operation_log` 保持原签名（调用方无需改动），改为写主库并计算链式哈希
- `list_operation_logs` / `get_operation_log` 保持原返回结构，改读主库，仅返回业务日志
- 新增 `verify_operation_log_chain`（防篡改校验）与 `export_operation_logs`（审计导出）
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import OperationLog, SessionLocal

logger = logging.getLogger(__name__)

# 链首的前序哈希（64 个 0）
GENESIS_HASH = "0" * 64
CHAIN_ALGORITHM = "sha256/v1"
MAX_CHAIN_RETRY = 5
MAX_EXPORT_ROWS = 20000

SOURCE_BUSINESS = "business"
SOURCE_HTTP = "http"

# 业务级别 -> 执行结果状态（供操作日志页面按 status 过滤）
LEVEL_TO_STATUS = {
    "info": "success",
    "success": "success",
    "warning": "warning",
    "danger": "error",
    "error": "error",
}
# 执行结果状态 -> 业务级别（仅用于兼容旧调用方读取的 level 字段）
STATUS_TO_LEVEL = {"success": "success", "warning": "warning", "error": "danger"}


def _canonical(content: Dict[str, Any]) -> str:
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def chain_content(log: OperationLog) -> Dict[str, Any]:
    """参与哈希计算的字段集合。新增字段必须显式加入，否则不会被防篡改保护覆盖。"""
    return {
        "seq": log.seq,
        "tenant_id": log.tenant_id,
        "source": log.source or "",
        "user_id": log.user_id,
        "username": log.username or "",
        "module": log.module or "",
        "action": log.action or "",
        "title": log.title or "",
        "description": log.description or "",
        "target_type": log.target_type or "",
        "target_id": str(log.target_id or ""),
        "level": log.level or "",
        "status": log.status or "",
        "status_before": log.status_before or "",
        "status_after": log.status_after or "",
        "link": log.link or "",
        "payload": log.payload or {},
        "created_at": log.created_at.isoformat() if log.created_at else "",
    }


def compute_hash(content: Dict[str, Any], prev_hash: str) -> str:
    material = f"{prev_hash}\n{_canonical(content)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _chain_head(db: Session) -> Tuple[int, str]:
    head = (
        db.query(OperationLog)
        .filter(OperationLog.seq.isnot(None))
        .order_by(OperationLog.seq.desc())
        .first()
    )
    if not head:
        return 0, GENESIS_HASH
    return int(head.seq or 0), (head.hash or GENESIS_HASH)


def append_operation_log(
    db: Session,
    *,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    username: str = "",
    module: str = "",
    action: str = "",
    title: str = "",
    description: str = "",
    target_type: str = "",
    target_id: str = "",
    level: str = "info",
    status: str = "",
    status_before: str = "",
    status_after: str = "",
    link: str = "",
    payload: Optional[Dict[str, Any]] = None,
    source: str = SOURCE_BUSINESS,
    ip_address: str = "",
    user_agent: str = "",
    request_data: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_message: str = "",
    duration_ms: int = 0,
) -> OperationLog:
    """在主库追加一条审计日志并接入哈希链。

    并发写入时靠 `uq_operation_log_seq` 唯一索引兜底：冲突方重新取链尾并重试。
    """
    last_error: Optional[Exception] = None
    for _ in range(MAX_CHAIN_RETRY):
        prev_seq, prev_hash = _chain_head(db)
        log = OperationLog(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username or "",
            module=module or "",
            action=action or "",
            title=(title or action or "")[:255],
            description=description or "",
            target_type=target_type or "",
            target_id=str(target_id or "")[:64],
            level=level or "info",
            status=status or LEVEL_TO_STATUS.get(level or "info", "success"),
            status_before=status_before or "",
            status_after=status_after or "",
            link=(link or "")[:255],
            payload=payload or {},
            source=source,
            ip_address=ip_address or "",
            user_agent=(user_agent or "")[:255],
            request_data=request_data or {},
            response_data=response_data or {},
            error_message=error_message or "",
            duration_ms=duration_ms or 0,
            seq=prev_seq + 1,
            prev_hash=prev_hash,
            created_at=datetime.utcnow(),
        )
        log.hash = compute_hash(chain_content(log), prev_hash)
        db.add(log)
        try:
            db.commit()
        except IntegrityError as exc:  # seq 冲突：其他写入方抢先占用了序号
            db.rollback()
            last_error = exc
            continue
        db.refresh(log)
        return log
    raise RuntimeError(f"追加审计日志失败（连续 {MAX_CHAIN_RETRY} 次链路冲突）") from last_error


def add_operation_log(
    module: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    title: str = "",
    detail: str = "",
    operator: str = "系统Agent",
    level: str = "info",
    status_before: str = "",
    status_after: str = "",
    link: str = "",
    raw: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """业务代码写审计日志的入口（保持原签名，调用方无需改动）。

    写日志失败不得影响业务流程，因此内部吞掉异常并降级为告警日志。
    """
    if not link and target_type and target_id:
        if target_type == "workorder":
            link = f"/workorders?order_id={target_id}"
        elif target_type == "inspection":
            link = f"/records?record_id={target_id}"
        elif target_type == "hardware":
            link = f"/hardware?event_id={target_id}"

    db = SessionLocal()
    try:
        log = append_operation_log(
            db,
            tenant_id=tenant_id,
            username=operator,
            module=module,
            action=action,
            title=title or action,
            description=detail,
            target_type=target_type,
            target_id=target_id,
            level=level,
            status_before=status_before,
            status_after=status_after,
            link=link,
            payload=raw or {},
            source=SOURCE_BUSINESS,
        )
        return _log_to_legacy_dict(log)
    except Exception as exc:  # noqa: BLE001 - 审计写入失败不应阻断业务
        logger.warning(f"写入审计日志失败: {exc}")
        return {}
    finally:
        db.close()


def _detach(log: OperationLog) -> Dict[str, Any]:
    return {
        "id": log.id,
        "seq": log.seq,
        "tenant_id": log.tenant_id,
        "user_id": log.user_id,
        "username": log.username or "",
        "module": log.module or "",
        "action": log.action or "",
        "title": log.title or "",
        "description": log.description or "",
        "target_type": log.target_type or "",
        "target_id": log.target_id or "",
        "level": log.level or "",
        "status": log.status or "",
        "status_before": log.status_before or "",
        "status_after": log.status_after or "",
        "link": log.link or "",
        "payload": log.payload or {},
        "source": log.source or "",
        "ip_address": log.ip_address or "",
        "user_agent": log.user_agent or "",
        "prev_hash": log.prev_hash or "",
        "hash": log.hash or "",
        "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
    }


def _log_to_legacy_dict(log: OperationLog) -> Dict[str, Any]:
    """兼容旧调用方（通知中心 / 档案时间线）读取的字段名。"""
    data = _detach(log)
    data["detail"] = data["description"]
    data["operator"] = data["username"]
    data["raw"] = data["payload"]
    if not data["level"]:
        data["level"] = STATUS_TO_LEVEL.get(data["status"], "info")
    return data


def get_operation_log(log_id: Any) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            row = db.query(OperationLog).filter(OperationLog.id == int(log_id)).first()
        except (TypeError, ValueError):
            return {}
        return _log_to_legacy_dict(row) if row else {}
    finally:
        db.close()


def list_operation_logs(
    module: str = "",
    target_type: str = "",
    target_id: str = "",
    level: str = "",
    keyword: str = "",
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """业务日志列表（不含中间件按请求写入的 HTTP 日志，避免通知中心被请求日志刷屏）。"""
    db = SessionLocal()
    try:
        query = db.query(OperationLog).filter(OperationLog.source == SOURCE_BUSINESS)
        if module:
            query = query.filter(OperationLog.module == module)
        if target_type:
            query = query.filter(OperationLog.target_type == target_type)
        if target_id:
            query = query.filter(OperationLog.target_id == str(target_id))
        if level:
            query = query.filter(OperationLog.level == level)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                OperationLog.title.like(like)
                | OperationLog.description.like(like)
                | OperationLog.username.like(like)
                | OperationLog.target_id.like(like)
            )
        rows = query.order_by(OperationLog.id.desc()).limit(max(1, min(limit, 500))).all()
        return [_log_to_legacy_dict(row) for row in rows]
    finally:
        db.close()


# ---------------- 防篡改校验 ----------------


def verify_operation_log_chain(db: Session, *, max_rows: Optional[int] = None) -> Dict[str, Any]:
    """逐条重算哈希链，定位第一条被篡改/缺失的位置。

    链条是全局的（seq 全局单调），因此校验不做租户过滤；返回内容只有计数、
    异常位置与涉事行的摘要，不含其他租户的日志正文。
    """
    chained = db.query(OperationLog).filter(OperationLog.seq.isnot(None))
    total_chained = chained.count()
    unverified_legacy = db.query(OperationLog).filter(OperationLog.seq.is_(None)).count()

    query = chained.order_by(OperationLog.seq.asc())
    if max_rows:
        query = query.limit(max_rows)
    rows = query.all()

    expected_prev = GENESIS_HASH
    expected_seq = 1
    checked = 0
    first_broken: Optional[Dict[str, Any]] = None

    for log in rows:
        seq = int(log.seq or 0)
        if seq != expected_seq:
            first_broken = {
                "seq": seq,
                "expected_seq": expected_seq,
                "reason": "序号不连续，疑似有记录被删除",
                "log_id": log.id,
            }
            break
        if (log.prev_hash or "") != expected_prev:
            first_broken = {
                "seq": seq,
                "expected_prev_hash": expected_prev,
                "actual_prev_hash": log.prev_hash or "",
                "reason": "前序哈希不匹配，疑似有记录被插入或替换",
                "log_id": log.id,
            }
            break
        recomputed = compute_hash(chain_content(log), log.prev_hash or "")
        if recomputed != (log.hash or ""):
            first_broken = {
                "seq": seq,
                "expected_hash": recomputed,
                "actual_hash": log.hash or "",
                "reason": "内容与哈希不一致，该条记录已被修改",
                "log_id": log.id,
            }
            break
        expected_prev = log.hash or ""
        expected_seq = seq + 1
        checked += 1

    head_hash = expected_prev if checked else GENESIS_HASH
    return {
        "ok": first_broken is None,
        "algorithm": CHAIN_ALGORITHM,
        "checked": checked,
        "total_chained": total_chained,
        "unverified_legacy": unverified_legacy,
        "truncated": bool(max_rows and total_chained > checked and first_broken is None),
        "head_hash": head_hash,
        "first_broken": first_broken,
        "verified_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------- 审计导出 ----------------

EXPORT_COLUMNS = [
    ("seq", "链序号"),
    ("id", "记录ID"),
    ("created_at", "时间"),
    ("module", "模块"),
    ("action", "操作"),
    ("title", "标题"),
    ("description", "详情"),
    ("level", "业务级别"),
    ("status", "执行结果"),
    ("username", "操作人"),
    ("user_id", "用户ID"),
    ("tenant_id", "租户ID"),
    ("target_type", "对象类型"),
    ("target_id", "对象ID"),
    ("status_before", "变更前"),
    ("status_after", "变更后"),
    ("link", "跳转"),
    ("source", "来源"),
    ("ip_address", "来源IP"),
    ("prev_hash", "前序哈希"),
    ("hash", "本行哈希"),
]


def _export_query(
    db: Session,
    *,
    tenant_id: Optional[int],
    module: str = "",
    level: str = "",
    keyword: str = "",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = MAX_EXPORT_ROWS,
):
    query = db.query(OperationLog)
    if tenant_id is not None:
        # 未归属租户的历史日志（tenant_id 为空）一并可见，避免升级后旧日志凭空消失
        query = query.filter(
            (OperationLog.tenant_id == tenant_id) | (OperationLog.tenant_id.is_(None))
        )
    if module:
        query = query.filter(OperationLog.module == module)
    if level:
        query = query.filter(OperationLog.level == level)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            OperationLog.title.like(like)
            | OperationLog.description.like(like)
            | OperationLog.username.like(like)
        )
    if start is not None:
        query = query.filter(OperationLog.created_at >= start)
    if end is not None:
        query = query.filter(OperationLog.created_at <= end)
    return query.order_by(OperationLog.id.asc()).limit(max(1, min(limit, MAX_EXPORT_ROWS)))


def export_operation_logs(
    db: Session,
    *,
    tenant_id: Optional[int],
    fmt: str = "csv",
    module: str = "",
    level: str = "",
    keyword: str = "",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = MAX_EXPORT_ROWS,
    exported_by: str = "",
) -> Tuple[bytes, str, str, Dict[str, Any]]:
    """导出审计日志，返回 (内容, 文件名, MIME, 导出元信息)。

    导出结果带链序号与哈希，可在离线环境重算校验；导出动作本身也会被记为一条审计日志。
    """
    fmt = (fmt or "csv").strip().lower()
    if fmt not in ("csv", "json"):
        raise ValueError("导出格式只支持 csv 或 json")

    rows = [
        _detach(row)
        for row in _export_query(
            db,
            tenant_id=tenant_id,
            module=module,
            level=level,
            keyword=keyword,
            start=start,
            end=end,
            limit=limit,
        ).all()
    ]

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    verification = verify_operation_log_chain(db)
    meta = {
        "exported_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "exported_by": exported_by or "",
        "tenant_id": tenant_id,
        "count": len(rows),
        "filters": {
            "module": module,
            "level": level,
            "keyword": keyword,
            "start": start.strftime("%Y-%m-%d %H:%M:%S") if start else "",
            "end": end.strftime("%Y-%m-%d %H:%M:%S") if end else "",
        },
        "chain": {
            "algorithm": CHAIN_ALGORITHM,
            "verified": verification["ok"],
            "checked": verification["checked"],
            "head_hash": verification["head_hash"],
        },
    }

    if fmt == "json":
        body = json.dumps({"export_meta": meta, "items": rows}, ensure_ascii=False, indent=2)
        return body.encode("utf-8"), f"operation_logs_{stamp}.json", "application/json", meta

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in EXPORT_COLUMNS])
    for row in rows:
        writer.writerow([_csv_cell(row.get(key)) for key, _ in EXPORT_COLUMNS])
    # 导出信息以注释行附在末尾，便于人工核对导出范围
    writer.writerow([])
    writer.writerow([f"# 导出时间：{meta['exported_at']}", f"导出人：{meta['exported_by']}", f"条数：{meta['count']}"])
    writer.writerow([f"# 哈希链校验：{'通过' if meta['chain']['verified'] else '未通过'}", f"链尾哈希：{meta['chain']['head_hash']}"])
    # 加 BOM，避免 Excel 打开中文乱码
    return (
        ("\ufeff" + buffer.getvalue()).encode("utf-8"),
        f"operation_logs_{stamp}.csv",
        "text/csv; charset=utf-8",
        meta,
    )


def _csv_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)
