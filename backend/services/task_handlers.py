"""后台任务处理器

按 `task_type` 注册；worker 启动时 import 本模块即完成注册。
处理器可以是同步函数（worker 会放到线程里执行，同步 DB / 文件 IO 不阻塞事件循环），
也可以是协程函数（用于需要 await 的场景）。

约定：处理器返回的 dict 会作为任务的 `result` 落库；抛出异常即任务失败并记录原因。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from services.alert_notify_service import TASK_TYPE_ALERT_NOTIFY
from services.task_queue_service import TaskContext, register_handler

logger = logging.getLogger(__name__)

TASK_TYPE_BATCH_INSPECTION = "batch_inspection"
TASK_TYPE_REPORT_EXPORT = "report_export"
TASK_TYPE_DEVICE_MESSAGE = "device_message"


# ---------------- 批量巡检 ----------------


def _suggestion(risk_level: str, hazards: List[str]) -> str:
    if risk_level in ("高风险", "严重风险"):
        joined = "、".join(hazards) if hazards else "重点部位"
        return f"发现 {len(hazards)} 项隐患，建议立即整改，重点关注：{joined}。"
    if risk_level == "中风险":
        return f"发现 {len(hazards)} 项隐患，建议 3 日内完成整改。"
    if hazards:
        return "发现轻微隐患，建议纳入日常维护计划。"
    return "未发现明显隐患，继续保持。"


@register_handler(TASK_TYPE_BATCH_INSPECTION)
def run_batch_inspection(ctx: TaskContext) -> Dict[str, Any]:
    """逐点位做隐患识别与风险评分。

    使用规则引擎对每个巡检点的描述做真实抽取与评分（不调用大模型，避免批量任务产生
    不可控的调用成本）；结果汇总在任务 `result` 里。
    """
    from services.risk_engine import calculate_risk
    from services.text_analyzer import analyze_text

    items = ctx.payload.get("inspection_items") or []
    building_name = ctx.payload.get("building_name") or ""
    inspector = ctx.payload.get("inspector") or "系统自动巡检"
    total = len(items)

    ctx.report(done=0, total=total, message=f"开始巡检 {total} 个点位")

    results: List[Dict[str, Any]] = []
    high = medium = low = 0

    for index, item in enumerate(items, start=1):
        if ctx.canceled():
            logger.info(f"批量巡检任务 {ctx.task_id} 已被取消，提前结束")
            return {
                "building_name": building_name,
                "total_count": total,
                "completed_count": len(results),
                "canceled": True,
                "results": results,
            }

        description = str(item.get("description") or item.get("location") or "")
        hazards = list(analyze_text(description).get("hazards") or [])
        risk = calculate_risk(hazards)
        risk_level = risk.get("risk_level", "低风险")

        if risk_level in ("高风险", "严重风险"):
            high += 1
        elif risk_level == "中风险":
            medium += 1
        else:
            low += 1

        results.append({
            "item_id": item.get("id"),
            "location": item.get("location"),
            "device_id": item.get("device_id"),
            "device_name": item.get("device_name"),
            "risk_level": risk_level,
            "risk_score": risk.get("risk_score", 0),
            "hazards": hazards,
            "hazard_count": len(hazards),
            "description": f"{building_name}-{item.get('location') or ''}巡检完成",
            "inspector": inspector,
            "inspected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "suggestion": _suggestion(risk_level, hazards),
        })

        ctx.report(
            done=index,
            total=total,
            message=f"已完成 {index}/{total}：{item.get('location') or ''}",
            extra={
                "completed_count": index,
                "total_count": total,
                "high_risk_count": high,
                "medium_risk_count": medium,
                "low_risk_count": low,
                "current_item": item.get("location") or "",
            },
        )

    return {
        "building_name": building_name,
        "total_count": total,
        "completed_count": len(results),
        "high_risk_count": high,
        "medium_risk_count": medium,
        "low_risk_count": low,
        "current_item": "",
        "results": results,
    }


# ---------------- 报表导出 ----------------


@register_handler(TASK_TYPE_REPORT_EXPORT)
def run_report_export(ctx: TaskContext) -> Dict[str, Any]:
    """异步生成报表并归档；返回产物 ID 供前端下载。

    报表统计在 `period=year` 时会串行发出数百条 count 查询，放在请求里会让前端长时间等待，
    因此改为后台任务，前端按 task_id 轮询进度。
    """
    from database import SessionLocal
    from services.report_export_service import export_report

    tenant_id = ctx.tenant_id
    payload = {
        "report_type": ctx.payload.get("report_type") or "inspection",
        "period": ctx.payload.get("period") or "month",
        "format": ctx.payload.get("format") or "xlsx",
        "start_date": ctx.payload.get("start_date") or "",
        "end_date": ctx.payload.get("end_date") or "",
    }

    ctx.report(done=0, total=3, message="正在统计报表数据")
    db = SessionLocal()
    try:
        result = export_report(
            db,
            tenant_id=tenant_id,
            payload=payload,
            user_id=ctx.payload.get("user_id"),
            user_name=ctx.created_by_name,
        )
        ctx.report(done=3, total=3, message="报表已生成并归档")
        return {
            "artifact_id": result.artifact.id,
            "filename": result.filename,
            "media_type": result.media_type,
            "report_type": payload["report_type"],
            "period": payload["period"],
            "format": payload["format"],
            "size_bytes": len(result.content),
        }
    finally:
        db.close()


# ---------------- 设备消息处理（MQTT 削峰后的业务处理） ----------------


@register_handler(TASK_TYPE_DEVICE_MESSAGE)
def run_device_message(ctx: TaskContext) -> Dict[str, Any]:
    """处理收件箱里的一条设备消息。

    - 已处理过的消息直接跳过（幂等）
    - 可恢复的错误抛回任务队列重试；最后一次仍失败则标记为死信
    - 设备不存在、消息类型不支持等不可恢复错误直接进死信，不做无意义重试
    """
    from database import Device, SessionLocal
    from services import device_message_service as inbox
    from services.device_ingest_service import dispatch

    message_id = str(ctx.payload.get("message_id") or "")
    if not message_id:
        raise ValueError("设备消息任务缺少 message_id")

    db = SessionLocal()
    try:
        row = inbox.get_by_message_id(db, message_id)
        if not row:
            return {"skipped": True, "reason": "消息记录不存在"}

        if row.status == inbox.STATUS_PROCESSED:
            return {"message_id": message_id, "skipped": True, "reason": "消息已处理（幂等跳过）"}

        inbox.mark_processing(db, row.id)

        device = None
        if row.device_id:
            device = db.query(Device).filter(Device.id == row.device_id).first()
        if device is None:
            device = db.query(Device).filter(
                Device.device_code == row.device_code,
                Device.tenant_id == row.tenant_id,
            ).first()
        if device is None:
            error = f"设备不存在：{row.device_code}"
            inbox.mark_failed(db, row.id, error, dead=True)
            logger.error(f"设备消息 {message_id} 进入死信：{error}")
            return {"message_id": message_id, "failed": True, "dead": True, "error": error}

        try:
            result = dispatch(db, device, row.kind, row.payload or {}, source=row.source or "mqtt")
        except ValueError as exc:
            # 消息类型不支持属于不可恢复错误，重试没有意义
            inbox.mark_failed(db, row.id, str(exc), dead=True)
            logger.error(f"设备消息 {message_id} 进入死信：{exc}")
            return {"message_id": message_id, "failed": True, "dead": True, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            dead = ctx.is_last_attempt
            inbox.mark_failed(db, row.id, error, dead=dead)
            if dead:
                logger.error(f"设备消息 {message_id} 已重试 {ctx.attempts} 次仍失败，进入死信：{error}")
                return {"message_id": message_id, "failed": True, "dead": True, "error": error}
            logger.warning(f"设备消息 {message_id} 第 {ctx.attempts} 次处理失败，将重试：{error}")
            raise

        alert_id = result.get("alert_id") if isinstance(result, dict) else None
        inbox.mark_processed(db, row.id, alert_id=alert_id)
        ctx.report(done=1, total=1, message=f"设备消息 {row.kind} 处理完成")
        return {
            "message_id": message_id,
            "device_code": row.device_code,
            "kind": row.kind,
            "alert_id": alert_id,
        }
    finally:
        db.close()


# ---------------- 告警外部通知（Webhook / 企业微信 / 钉钉 / 邮件） ----------------


@register_handler(TASK_TYPE_ALERT_NOTIFY)
def run_alert_notify(ctx: TaskContext) -> Dict[str, Any]:
    """把一条告警投递到某个外部通道。

    - 已成功投递过则幂等跳过（同一告警同通道只发一次，台账上有唯一约束兜底）
    - 通道被删除/停用、告警记录不存在属不可恢复错误，直接标记失败不再重试
    - 网络或对端报错则抛回队列重试，最后一次仍失败即记录为最终失败
    """
    from database import SessionLocal
    from services import alert_notify_service as notify

    delivery_id = ctx.payload.get("delivery_id")
    if not delivery_id:
        raise ValueError("告警通知任务缺少 delivery_id")

    db = SessionLocal()
    try:
        try:
            result = notify.deliver(db, int(delivery_id))
        except notify.NotificationSendError as exc:
            if ctx.is_last_attempt:
                logger.error(f"告警通知投递 {delivery_id} 已重试 {ctx.attempts} 次仍失败：{exc}")
                return {"delivery_id": delivery_id, "failed": True, "dead": True, "error": str(exc)}
            logger.warning(f"告警通知投递 {delivery_id} 第 {ctx.attempts} 次失败，将重试：{exc}")
            raise
        ctx.report(done=1, total=1, message="告警通知已发送")
        return {"delivery_id": delivery_id, **result}
    finally:
        db.close()
