from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List
import uuid

from services.operation_log_service import add_operation_log
from services.runtime_db import connect_runtime_db


def _connect():
    conn = connect_runtime_db()
    _init_db(conn)
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str):
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


# 运行库工单的历史词表归一。
# 已删除的旧模块 services/v12_closed_loop_service.py（无路由引用、无生产调用方）当年往 work_orders
# 里写的是 待整改 / 整改中 / 已完成 / 已复查，而现在通用的是
# 待派单 / 整改中 / 待复查 / 已闭环（见 routers/workorder.py 的 RECTIFICATION_STATUSES）。
# 两套词表混在一张表里会让看板统计对不上、页面的状态筛选也匹配不到这些行。
# 写入方虽然删了，但其它部署的历史数据里可能还留着这些取值，所以这段归一保留（幂等，跑过一次后即空操作）。
# 映射按 v12 自己的阶段顺序取：待整改(第1阶段) ≡ 待派单，已完成(第3阶段) ≡ 待复查，已复查(第4阶段) ≡ 已闭环。
LEGACY_WORKORDER_STATUS_MAP = {
    "待整改": "待派单",
    "待处理": "待派单",
    "已完成": "待复查",
    "已复查": "已闭环",
}


def _normalize_legacy_workorder_status(conn: sqlite3.Connection) -> int:
    """把 work_orders 里的历史词表归一成现在通用的状态词。幂等，返回改动行数。"""
    changed = 0
    for legacy, current in LEGACY_WORKORDER_STATUS_MAP.items():
        cur = conn.execute("UPDATE work_orders SET status = ? WHERE status = ?", (current, legacy))
        changed += cur.rowcount or 0
    return changed


# 运行库里带 tenant_id 的表（该列是后加的，引入租户之前的存量数据全是 NULL）
RUNTIME_TENANT_TABLES = ("work_orders", "inspection_records", "inspection_reports")


def single_user_tenant_id() -> int | None:
    """主库里「有用户的租户」恰好只有一个时返回它，否则 None。

    运行库的 tenant_id 是后加的列，引入租户之前的存量数据全是 NULL。单租户部署下这些数据显然
    属于那唯一的租户，回填后读写都不必再依赖 NULL 兜底；多租户下无法判断归属，不做猜测
    （读取仍走 _tenant_scope 的 NULL 兜底）。

    以「有用户的租户」而非 tenants 表的行数为判断依据：本机 tenants 里还留着 4 个测试租户
    （审计隔离 / 任务隔离 / 管线隔离 / 系统监控测试），但真实用户只在 id=1。
    """
    try:
        from database import SessionLocal, User

        with SessionLocal() as db:
            ids = {row[0] for row in db.query(User.tenant_id).distinct().all() if row[0] is not None}
        return next(iter(ids)) if len(ids) == 1 else None
    except Exception:
        return None


def _backfill_runtime_tenant_id(conn: sqlite3.Connection) -> int:
    """给运行库的历史数据回填 tenant_id。幂等，返回回填行数。"""
    pending = sum(
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL").fetchone()[0]
        for table in RUNTIME_TENANT_TABLES
    )
    if not pending:
        return 0
    tenant_id = single_user_tenant_id()
    if tenant_id is None:
        print("[运行库] 存在 tenant_id 为空的历史数据，但主库租户不唯一，跳过回填（读取仍走 NULL 兜底）")
        return 0
    changed = 0
    for table in RUNTIME_TENANT_TABLES:
        cur = conn.execute(f"UPDATE {table} SET tenant_id = ? WHERE tenant_id IS NULL", (tenant_id,))
        changed += cur.rowcount or 0
    return changed


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inspection_records (
        id TEXT PRIMARY KEY,
        tenant_id INTEGER,
        location TEXT,
        description TEXT,
        risk_level TEXT,
        risk_score REAL,
        hazards_json TEXT,
        result_json TEXT,
        learning_json TEXT,
        report_json TEXT,
        created_at TEXT
    )
    """)
    # V1.0.0 档案增强字段，使用 ALTER 兼容旧运行库。
    _add_column_if_missing(conn, "inspection_records", "archive_status", "TEXT DEFAULT '已归档'")
    _add_column_if_missing(conn, "inspection_records", "review_status", "TEXT DEFAULT '待复查'")
    _add_column_if_missing(conn, "inspection_records", "inspector", "TEXT DEFAULT '安全管理员'")
    _add_column_if_missing(conn, "inspection_records", "report_no", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "inspection_records", "image_paths_json", "TEXT DEFAULT '[]'")
    _add_column_if_missing(conn, "inspection_records", "tags_json", "TEXT DEFAULT '[]'")
    _add_column_if_missing(conn, "inspection_records", "updated_at", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "inspection_records", "tenant_id", "INTEGER")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS work_orders (
        id TEXT PRIMARY KEY,
        tenant_id INTEGER,
        inspection_id TEXT,
        title TEXT,
        hazard TEXT,
        location TEXT,
        risk_level TEXT,
        risk_score REAL,
        priority TEXT,
        status TEXT,
        responsible_role TEXT,
        recommended_action TEXT,
        deadline TEXT,
        timeline_json TEXT,
        raw_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    _add_column_if_missing(conn, "work_orders", "tenant_id", "INTEGER")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inspection_reports (
        id TEXT PRIMARY KEY,
        tenant_id INTEGER,
        inspection_id TEXT,
        title TEXT,
        report_json TEXT,
        created_at TEXT
    )
    """)
    _add_column_if_missing(conn, "inspection_reports", "tenant_id", "INTEGER")

    migrated = _normalize_legacy_workorder_status(conn)
    if migrated:
        print(f"[运行库] 整改工单历史状态已归一 {migrated} 行 → {LEGACY_WORKORDER_STATUS_MAP}")

    backfilled = _backfill_runtime_tenant_id(conn)
    if backfilled:
        print(f"[运行库] 历史数据已回填 tenant_id：{backfilled} 行")

    conn.commit()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _loads(text: str, default: Any):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _safe_get(row: sqlite3.Row, key: str, default: Any = "") -> Any:
    try:
        return row[key]
    except Exception:
        return default


def _tenant_scope(tenant_id: int | None, joint: str = "AND") -> str:
    """拼运行库的租户过滤条件。

    `tenant_id` 是后加的列：引入租户之前写入的运行库数据该列全是 NULL
    （实测本机运行库 344 条整改工单、17 条巡检档案、49 份报告全是 NULL）。
    只按 `tenant_id = ?` 过滤会把这些存量数据全部滤掉，页面看着像没数据 —— 例如
    「整改工单」页的看板恒为 0、列表为空，「巡检档案」页只剩新建的记录。
    因此这里把 NULL 视为归属当前租户（单租户部署下的历史数据）。

    调用方仍然只绑定一个 tenant_id 参数，SQL 里也仍然只有一个 `?`。
    """
    if tenant_id is None:
        return ""
    return f" {joint} (tenant_id = ? OR tenant_id IS NULL)"


def _risk_priority(risk_level: str) -> str:
    if risk_level in ["严重风险", "高风险"]:
        return "建议立即整改"
    if risk_level == "中风险":
        return "建议限期整改"
    return "建议持续观察"


def _default_review_status(risk_level: str, orders: List[Dict[str, Any]] | None = None) -> str:
    orders = orders or []
    if orders and all(o.get("status") == "已闭环" for o in orders):
        return "已复查"
    if risk_level in ["严重风险", "高风险"]:
        return "待复查"
    if risk_level == "中风险":
        return "持续跟踪"
    return "已通过"


def _extract_image_paths(payload: Dict[str, Any]) -> List[str]:
    result = payload.get("result", {}) or {}
    candidates: List[Any] = []
    candidates.extend(payload.get("image_paths", []) or [])
    candidates.extend(result.get("image_paths", []) or [])
    for key in ["image_path", "uploaded_image", "evidence_image"]:
        if payload.get(key):
            candidates.append(payload.get(key))
        if result.get(key):
            candidates.append(result.get(key))
    seen: List[str] = []
    for item in candidates:
        if not item:
            continue
        text = str(item)
        if text not in seen:
            seen.append(text)
    return seen


def _extract_tags(hazards: List[Any], result: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for h in hazards or []:
        text = h if isinstance(h, str) else h.get("hazard_name") or h.get("type") or h.get("name")
        if text and text not in tags:
            tags.append(str(text))
    for item in result.get("hazard_results", []) or result.get("hazard_items", []) or []:
        for key in ["category", "risk_level", "hazard_name", "type"]:
            text = item.get(key)
            if text and text not in tags:
                tags.append(str(text))
    return tags[:12]


def _row_to_workorder(row) -> Dict[str, Any]:
    raw = _loads(row["raw_json"], {})
    raw.update({
        "id": row["id"],
        "inspection_id": row["inspection_id"],
        "title": row["title"],
        "hazard": row["hazard"],
        "location": row["location"],
        "risk_level": row["risk_level"],
        "risk_score": row["risk_score"],
        "priority": row["priority"],
        "status": row["status"],
        "responsible_role": row["responsible_role"],
        "recommended_action": row["recommended_action"],
        "deadline": row["deadline"],
        "timeline": _loads(row["timeline_json"], []),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    })
    return raw


def save_inspection_record(payload: Dict[str, Any], tenant_id: int | None = None) -> Dict[str, Any]:
    record_id = payload.get("id") or f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}"
    created_at = payload.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    location = payload.get("location", "")
    description = payload.get("description", "")
    hazards = payload.get("hazards", []) or []
    risk_level = payload.get("risk_level", "未评估")
    risk_score = payload.get("risk_score", 0)
    result = payload.get("result", {}) or {}
    learning = payload.get("learning_recommendations", {}) or {}
    report = payload.get("report", {}) or {}
    workorders = payload.get("workorders", []) or []
    report_no = payload.get("report_no") or report.get("report_no") or f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"
    inspector = payload.get("inspector") or "安全管理员"
    archive_status = payload.get("archive_status") or "已归档"
    review_status = payload.get("review_status") or _default_review_status(risk_level, workorders)
    image_paths = _extract_image_paths(payload)
    tags = _extract_tags(hazards, result)

    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO inspection_records
            (id, tenant_id, location, description, risk_level, risk_score, hazards_json, result_json, learning_json, report_json,
             created_at, archive_status, review_status, inspector, report_no, image_paths_json, tags_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                tenant_id,
                location,
                description,
                risk_level,
                float(risk_score or 0),
                _dumps(hazards),
                _dumps(result),
                _dumps(learning),
                _dumps(report),
                created_at,
                archive_status,
                review_status,
                inspector,
                report_no,
                _dumps(image_paths),
                _dumps(tags),
                updated_at,
            ),
        )

        if report:
            report_id = report.get("report_id") or report_no
            conn.execute(
                """
                INSERT OR REPLACE INTO inspection_reports
                (id, tenant_id, inspection_id, title, report_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (report_id, tenant_id, record_id, report.get("title", "巡检报告"), _dumps(report), created_at),
            )

        for order in workorders:
            order_id = order.get("id") or f"WO-{str(uuid.uuid4())[:8].upper()}"
            raw = dict(order)
            raw["inspection_id"] = record_id
            timeline = raw.get("timeline", [])
            conn.execute(
                """
                INSERT OR REPLACE INTO work_orders
                (id, tenant_id, inspection_id, title, hazard, location, risk_level, risk_score, priority, status,
                 responsible_role, recommended_action, deadline, timeline_json, raw_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    tenant_id,
                    record_id,
                    raw.get("title", ""),
                    raw.get("hazard", ""),
                    raw.get("location", location),
                    raw.get("risk_level", risk_level),
                    float(raw.get("risk_score", risk_score) or 0),
                    raw.get("priority", _risk_priority(risk_level)),
                    raw.get("status", "待派单"),
                    raw.get("responsible_role", ""),
                    raw.get("recommended_action", ""),
                    raw.get("deadline", ""),
                    _dumps(timeline),
                    _dumps(raw),
                    raw.get("created_at", created_at),
                    updated_at,
                ),
            )
        conn.commit()

    try:
        add_operation_log(
            module="巡检档案",
            action="create_inspection_archive",
            target_type="inspection",
            target_id=record_id,
            title="创建巡检档案",
            detail=f"{location or '现场'} 已归档，风险等级 {risk_level}，报告编号 {report_no}。",
            operator=inspector or "系统Agent",
            level="warning" if risk_level in ["高风险", "严重风险"] else "info",
            status_after=review_status,
            link=f"/records?record_id={record_id}",
            raw={"report_no": report_no, "risk_level": risk_level, "DEMO": bool(payload.get("demo"))},
        )
        if workorders:
            add_operation_log(
                module="整改工单",
                action="create_workorders",
                target_type="inspection",
                target_id=record_id,
                title="生成整改工单",
                detail=f"根据巡检档案自动生成 {len(workorders)} 条整改工单。",
                operator="系统Agent",
                level="warning" if risk_level in ["高风险", "严重风险"] else "info",
                status_after="待派单",
                link=f"/records?record_id={record_id}",
                raw={"workorder_count": len(workorders), "DEMO": bool(payload.get("demo"))},
            )
    except Exception:
        pass

    return {
        "id": record_id,
        "record_id": record_id,
        "report_no": report_no,
        "created_at": created_at,
        "archive_status": archive_status,
        "review_status": review_status,
        "workorder_count": len(workorders),
        "report_id": report.get("report_id", report_no),
        "message": "本次巡检结果已保存并归档，可在巡检档案中查看。",
    }


def list_inspection_records(limit: int = 100, tenant_id: int | None = None) -> List[Dict[str, Any]]:
    with _connect() as conn:
        where = _tenant_scope(tenant_id, "WHERE")
        params = (tenant_id, limit) if tenant_id is not None else (limit,)
        rows = conn.execute(
            f"""
            SELECT *
            FROM inspection_records
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    result = []
    for row in rows:
        hazards = _loads(row["hazards_json"], [])
        tags = _loads(_safe_get(row, "tags_json", "[]"), [])
        result.append({
            "id": row["id"],
            "record_no": row["id"],
            "report_no": _safe_get(row, "report_no", ""),
            "location": row["location"],
            "description": row["description"],
            "risk_level": row["risk_level"],
            "risk_score": row["risk_score"],
            "hazards": hazards,
            "hazard_count": len(hazards),
            "tags": tags,
            "archive_status": _safe_get(row, "archive_status", "已归档"),
            "review_status": _safe_get(row, "review_status", "待复查"),
            "inspector": _safe_get(row, "inspector", "安全管理员"),
            "image_count": len(_loads(_safe_get(row, "image_paths_json", "[]"), [])),
            "created_at": row["created_at"],
            "updated_at": _safe_get(row, "updated_at", row["created_at"]),
        })
    return result


def get_inspection_record(record_id: str, tenant_id: int | None = None) -> Dict[str, Any]:
    with _connect() as conn:
        record_where = _tenant_scope(tenant_id)
        record_params = (record_id, tenant_id) if tenant_id is not None else (record_id,)
        row = conn.execute(f"SELECT * FROM inspection_records WHERE id = ?{record_where}", record_params).fetchone()
        if not row:
            return {}

        order_where = _tenant_scope(tenant_id)
        order_params = (record_id, tenant_id) if tenant_id is not None else (record_id,)
        orders = conn.execute(
            f"SELECT * FROM work_orders WHERE inspection_id = ?{order_where} ORDER BY created_at ASC",
            order_params,
        ).fetchall()

    order_list = [_row_to_workorder(o) for o in orders]
    hazards = _loads(row["hazards_json"], [])
    result = _loads(row["result_json"], {})
    report = _loads(row["report_json"], {})
    image_paths = _loads(_safe_get(row, "image_paths_json", "[]"), [])

    return {
        "id": row["id"],
        "record_no": row["id"],
        "report_no": _safe_get(row, "report_no", ""),
        "location": row["location"],
        "description": row["description"],
        "risk_level": row["risk_level"],
        "risk_score": row["risk_score"],
        "hazards": hazards,
        "result": result,
        "learning_recommendations": _loads(row["learning_json"], {}),
        "report": report,
        "workorders": order_list,
        "archive_status": _safe_get(row, "archive_status", "已归档"),
        "review_status": _safe_get(row, "review_status", _default_review_status(row["risk_level"], order_list)),
        "inspector": _safe_get(row, "inspector", "安全管理员"),
        "image_paths": image_paths,
        "tags": _loads(_safe_get(row, "tags_json", "[]"), []),
        "created_at": row["created_at"],
        "updated_at": _safe_get(row, "updated_at", row["created_at"]),
    }


def list_workorders(status: str = "", limit: int = 200, tenant_id: int | None = None) -> List[Dict[str, Any]]:
    with _connect() as conn:
        tenant_clause = _tenant_scope(tenant_id)
        if status:
            params = (status, tenant_id, limit) if tenant_id is not None else (status, limit)
            rows = conn.execute(
                f"SELECT * FROM work_orders WHERE status = ?{tenant_clause} ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        else:
            params = (tenant_id, limit) if tenant_id is not None else (limit,)
            rows = conn.execute(
                f"SELECT * FROM work_orders WHERE 1 = 1{tenant_clause} ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
    return [_row_to_workorder(r) for r in rows]


def get_workorder(order_id: str, tenant_id: int | None = None) -> Dict[str, Any]:
    with _connect() as conn:
        where = _tenant_scope(tenant_id)
        params = (order_id, tenant_id) if tenant_id is not None else (order_id,)
        row = conn.execute(f"SELECT * FROM work_orders WHERE id = ?{where}", params).fetchone()
    return _row_to_workorder(row) if row else {}


def update_workorder_status(order_id: str, status: str, operator: str = "安全管理员", note: str = "", tenant_id: int | None = None) -> Dict[str, Any]:
    order = get_workorder(order_id, tenant_id=tenant_id)
    if not order:
        return {}

    timeline = order.get("timeline", [])
    timeline.append({
        "status": status,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operator": operator or "安全管理员",
        "note": note or f"工单状态更新为：{status}",
    })

    status_before = order.get("status", "")
    raw = dict(order)
    raw["status"] = status
    raw["timeline"] = timeline
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _connect() as conn:
        conn.execute(
            """
            UPDATE work_orders
            SET status = ?, timeline_json = ?, raw_json = ?, updated_at = ?
            WHERE id = ?""" + _tenant_scope(tenant_id)
            , (status, _dumps(timeline), _dumps(raw), updated_at, order_id) + ((tenant_id,) if tenant_id is not None else ()),
        )
        # 如果该巡检所有工单已闭环，同步更新档案复查状态。
        inspection_id = order.get("inspection_id")
        if inspection_id:
            relation_clause = _tenant_scope(tenant_id)
            relation_params = (inspection_id, tenant_id) if tenant_id is not None else (inspection_id,)
            rows = conn.execute(f"SELECT status FROM work_orders WHERE inspection_id = ?{relation_clause}", relation_params).fetchall()
            if rows and all(r["status"] == "已闭环" for r in rows):
                record_params = ("已复查", updated_at, inspection_id, tenant_id) if tenant_id is not None else ("已复查", updated_at, inspection_id)
                conn.execute(
                    "UPDATE inspection_records SET review_status = ?, updated_at = ? WHERE id = ?" + _tenant_scope(tenant_id),
                    record_params,
                )
        conn.commit()

    try:
        level = "success" if status == "已闭环" else "warning" if status == "待复查" else "info"
        add_operation_log(
            module="整改工单",
            action="update_workorder_status",
            target_type="workorder",
            target_id=order_id,
            title="整改工单状态更新",
            detail=f"{order.get('hazard') or order.get('title')}：{status_before} → {status}。{note or ''}",
            operator=operator or "安全管理员",
            level=level,
            status_before=status_before,
            status_after=status,
            link=f"/workorders?order_id={order_id}",
            raw={"inspection_id": order.get("inspection_id"), "hazard": order.get("hazard")},
        )
    except Exception:
        pass

    return get_workorder(order_id, tenant_id=tenant_id)


def submit_workorder_review(order_id: str, reviewer: str = '安全管理员', result: str = '通过', note: str = '', review_images: List[str] | None = None, auto_close: bool = True, tenant_id: int | None = None) -> Dict[str, Any]:
    """提交复查结论。通过时可自动闭环，不通过时退回整改中。"""
    order = get_workorder(order_id, tenant_id=tenant_id)
    if not order:
        return {}
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status_before = order.get('status', '')
    passed = result in ['通过', '复查通过', '已通过', 'pass', True]
    status_after = '已闭环' if passed and auto_close else '整改中'
    timeline = order.get('timeline', []) or []
    timeline.append({
        'status': '复查通过' if passed else '复查不通过',
        'time': now,
        'operator': reviewer or '安全管理员',
        'note': note or ('现场复查通过，隐患已消除。' if passed else '复查未通过，退回继续整改。'),
    })
    order['status'] = status_after
    order['timeline'] = timeline
    order['review_result'] = '通过' if passed else '不通过'
    order['review_note'] = note or order.get('review_note', '')
    order['reviewer'] = reviewer or '安全管理员'
    order['reviewed_at'] = now
    if review_images is not None:
        order['review_images'] = review_images
    with _connect() as conn:
        conn.execute(
            """
            UPDATE work_orders
            SET status = ?, timeline_json = ?, raw_json = ?, updated_at = ?
            WHERE id = ?""" + _tenant_scope(tenant_id)
            , (status_after, _dumps(timeline), _dumps(order), now, order_id) + ((tenant_id,) if tenant_id is not None else ()),
        )
        inspection_id = order.get('inspection_id')
        if inspection_id:
            relation_clause = _tenant_scope(tenant_id)
            relation_params = (inspection_id, tenant_id) if tenant_id is not None else (inspection_id,)
            rows = conn.execute(f'SELECT status FROM work_orders WHERE inspection_id = ?{relation_clause}', relation_params).fetchall()
            record_clause = _tenant_scope(tenant_id)
            record_suffix = (tenant_id,) if tenant_id is not None else ()
            if rows and all(r['status'] == '已闭环' for r in rows):
                conn.execute('UPDATE inspection_records SET review_status = ?, updated_at = ? WHERE id = ?' + record_clause, ('已复查', now, inspection_id) + record_suffix)
            elif not passed:
                conn.execute('UPDATE inspection_records SET review_status = ?, updated_at = ? WHERE id = ?' + record_clause, ('持续跟踪', now, inspection_id) + record_suffix)
        conn.commit()
    try:
        add_operation_log(
            module='整改复查',
            action='submit_workorder_review',
            target_type='workorder',
            target_id=order_id,
            title='提交整改复查结论',
            detail=f"{order.get('hazard') or order.get('title')} 复查{('通过' if passed else '不通过')}：{note or '无补充说明'}",
            operator=reviewer or '安全管理员',
            level='success' if passed else 'warning',
            status_before=status_before,
            status_after=status_after,
            link=f'/workorders?order_id={order_id}',
            raw={'inspection_id': order.get('inspection_id'), 'review_result': '通过' if passed else '不通过'},
        )
    except Exception:
        pass
    return get_workorder(order_id, tenant_id=tenant_id)


def export_report_text(record_id: str, tenant_id: int | None = None) -> Dict[str, Any]:
    record = get_inspection_record(record_id, tenant_id=tenant_id)
    if not record:
        return {"content": "", "filename": ""}

    report = record.get("report", {})
    result = record.get("result", {}) or {}
    refs = result.get("rag_reference_cards", []) or result.get("rag_references", []) or []
    hazard_details = result.get("hazard_results", []) or result.get("hazard_items", []) or []

    lines = [
        f"# {report.get('title') or record.get('location', '现场') + '智慧消防智能巡检报告'}",
        "",
        f"报告编号：{record.get('report_no') or record.get('id')}",
        f"档案编号：{record.get('id')}",
        f"生成时间：{report.get('generated_at') or record.get('created_at')}",
        f"巡检地点：{record.get('location')}",
        f"巡检人员：{record.get('inspector')}",
        f"风险等级：{record.get('risk_level')}",
        f"风险评分：{record.get('risk_score')}",
        f"档案状态：{record.get('archive_status')}；复查状态：{record.get('review_status')}",
        "",
        "## 一、巡检基本信息",
        record.get("description") or "未填写",
        "",
        "## 二、图片证据",
        "\n".join([f"- {p}" for p in record.get("image_paths", [])]) or "未上传图片证据或未记录图片路径。",
        "",
        "## 三、主要隐患",
        "、".join(record.get("hazards", [])) or "未发现明显隐患",
        "",
        "## 四、隐患明细与整改建议",
    ]

    if hazard_details:
        for i, h in enumerate(hazard_details, start=1):
            lines.append(
                f"{i}. {h.get('hazard_name') or h.get('type')}｜{h.get('risk_level') or h.get('severity')}\n"
                f"   依据：{h.get('evidence') or h.get('reason', '')}\n"
                f"   后果：{h.get('possible_consequence', '可能影响疏散、灭火或应急处置。')}\n"
                f"   建议：{h.get('suggestion') or h.get('measure', '建议现场复核并整改。')}"
            )
    else:
        lines.append("无结构化隐患明细。")

    lines.extend(["", "## 五、RAG 引用依据"])
    if refs:
        for i, r in enumerate(refs, start=1):
            title = r.get("title") or r.get("source") or f"引用{i}"
            category = r.get("category", "消防知识")
            similarity = r.get("similarity") or r.get("score") or ""
            summary = r.get("summary") or r.get("content") or r.get("content_preview") or ""
            lines.append(f"{i}. {title}｜{category}｜相似度：{similarity}\n   {summary}")
    else:
        lines.append("暂无引用依据。")

    lines.extend(["", "## 六、整改工单与闭环"])
    for order in record.get("workorders", []):
        lines.append(
            f"- {order.get('hazard')}：{order.get('status')}；责任角色：{order.get('responsible_role')}；整改时限：{order.get('deadline')}；建议：{order.get('recommended_action')}"
        )
    if not record.get("workorders"):
        lines.append("暂无整改工单。")

    lines.extend(["", "## 七、复查建议", "整改完成后，应由消防安全管理员进行现场复查，核验隐患是否消除，并在系统中更新闭环状态。"])

    return {
        "filename": f"{record_id}_enhanced_inspection_report.md",
        "content": "\n".join(lines),
    }


def get_record_dashboard(tenant_id: int | None = None) -> Dict[str, Any]:
    records = list_inspection_records(500, tenant_id=tenant_id)
    orders = list_workorders("", 500, tenant_id=tenant_id)
    closed = len([o for o in orders if o.get("status") == "已闭环"])
    high = len([r for r in records if r.get("risk_level") in ["高风险", "严重风险"]])
    report_ready = len([r for r in records if r.get("report_no")])
    hazard_counter: Counter[str] = Counter()
    for r in records:
        hazard_counter.update(r.get("hazards", []))
    return {
        "inspection_count": len(records),
        "workorder_count": len(orders),
        "closed_workorder_count": closed,
        "closed_loop_rate": round(closed / len(orders) * 100, 1) if orders else 0,
        "high_risk_count": high,
        "report_ready_count": report_ready,
        "report_coverage_rate": round(report_ready / len(records) * 100, 1) if records else 0,
        "top_hazards": [{"name": k, "count": v} for k, v in hazard_counter.most_common(8)],
        "latest_records": records[:5],
    }


def update_workorder_evidence(order_id: str, before_images: List[str] | None = None, after_images: List[str] | None = None, review_images: List[str] | None = None, review_note: str = '', operator: str = '安全管理员', tenant_id: int | None = None) -> Dict[str, Any]:
    """保存整改前后图片证据链。图片字段使用路径/URL/说明文本，适合演示环境和后续真实上传扩展。"""
    order = get_workorder(order_id, tenant_id=tenant_id)
    if not order:
        return {}
    timeline = order.get('timeline', []) or []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if before_images is not None:
        order['before_images'] = before_images
    if after_images is not None:
        order['after_images'] = after_images
    if review_images is not None:
        order['review_images'] = review_images
    order['review_note'] = review_note or order.get('review_note', '')
    order['evidence_updated_at'] = now
    timeline.append({
        'status': '证据更新',
        'time': now,
        'operator': operator or '安全管理员',
        'note': review_note or '更新整改前后图片证据链。',
    })
    order['timeline'] = timeline
    with _connect() as conn:
        conn.execute(
            """
            UPDATE work_orders
            SET timeline_json = ?, raw_json = ?, updated_at = ?
            WHERE id = ?""" + _tenant_scope(tenant_id)
            , (_dumps(timeline), _dumps(order), now, order_id) + ((tenant_id,) if tenant_id is not None else ()),
        )
        conn.commit()
    try:
        add_operation_log(
            module='整改工单',
            action='update_workorder_evidence',
            target_type='workorder',
            target_id=order_id,
            title='更新整改图片证据链',
            detail=review_note or '更新整改前/整改后/复查图片证据。',
            operator=operator or '安全管理员',
            level='info',
            status_after=order.get('status', ''),
            link=f'/workorders?order_id={order_id}',
            raw={'before_count': len(order.get('before_images', [])), 'after_count': len(order.get('after_images', [])), 'review_count': len(order.get('review_images', []))},
        )
    except Exception:
        pass
    return get_workorder(order_id, tenant_id=tenant_id)
