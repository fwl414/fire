from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from services.record_persistence_service import list_workorders, list_inspection_records
from services.hardware_event_service import list_hardware_events
from services.operation_log_service import list_operation_logs

READ_PATH = Path(__file__).resolve().parent.parent / 'data' / 'notification_read.json'


def _now() -> datetime:
    return datetime.now()


def _parse_time(text: str) -> datetime | None:
    if not text:
        return None
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
        try:
            return datetime.strptime(text[:len(fmt)], fmt)
        except Exception:
            continue
    return None


def _read_ids() -> set[str]:
    try:
        return set(json.loads(READ_PATH.read_text(encoding='utf-8')))
    except Exception:
        return set()


def _save_read_ids(ids: set[str]) -> None:
    READ_PATH.parent.mkdir(parents=True, exist_ok=True)
    READ_PATH.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding='utf-8')


def _notification(nid: str, title: str, content: str, level: str, source: str, link: str, created_at: str, category: str) -> Dict[str, Any]:
    level_text = {'danger': '高优先级', 'warning': '预警', 'success': '完成', 'info': '通知'}.get(level, '通知')
    return {
        'id': nid,
        'title': title,
        'content': content,
        'level': level,
        'level_text': level_text,
        'source': source,
        'link': link,
        'created_at': created_at or _now().strftime('%Y-%m-%d %H:%M:%S'),
        'category': category,
        'next_action': '查看并处理' if level in ['danger', 'warning'] else '查看详情',
        'state_snapshot': f'{source}｜{category}',
    }


def build_notifications(limit: int = 200, tenant_id: int | None = None) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    now = _now()

    for order in list_workorders('', 500, tenant_id=tenant_id):
        status = order.get('status', '')
        if status == '已闭环':
            continue
        deadline = _parse_time(order.get('deadline', ''))
        is_high = any(x in str(order.get('risk_level', '')) for x in ['高', '严重']) or order.get('priority') in ['高', '紧急']
        base = f"{order.get('location') or '现场'} · {order.get('hazard') or '整改事项'}"
        if deadline and deadline < now:
            items.append(_notification(
                f"overdue-{order.get('id')}", '整改工单已逾期',
                f"{base} 已超过整改时限，请立即复核责任人和整改进度。", 'danger', '整改工单', f"/workorders?order_id={order.get('id')}", order.get('updated_at') or order.get('created_at'), 'overdue'))
        elif deadline and deadline <= now + timedelta(hours=48):
            items.append(_notification(
                f"due-soon-{order.get('id')}", '整改工单即将逾期',
                f"{base} 将在 48 小时内到期，建议优先推进整改。", 'warning', '整改工单', f"/workorders?order_id={order.get('id')}", order.get('updated_at') or order.get('created_at'), 'due_soon'))
        elif is_high:
            items.append(_notification(
                f"high-order-{order.get('id')}", '高风险工单待处理',
                f"{base} 属于高风险或紧急事项，建议优先派单并跟踪复查。", 'danger', '整改工单', f"/workorders?order_id={order.get('id')}", order.get('updated_at') or order.get('created_at'), 'high_risk'))
        if status == '待复查':
            items.append(_notification(
                f"review-{order.get('id')}", '整改工单待复查',
                f"{base} 已提交整改，等待安全管理员现场复查。", 'warning', '复查提醒', f"/workorders?order_id={order.get('id')}", order.get('updated_at') or order.get('created_at'), 'review'))

    for event in list_hardware_events(limit=100, tenant_id=tenant_id):
        if event.get('status') == '已闭环':
            continue
        if any(x in str(event.get('risk_level', '')) for x in ['高', '严重']):
            items.append(_notification(
                f"hardware-{event.get('id')}", '硬件报警待处理',
                f"{event.get('location') or '现场'} 上报 {event.get('event_name') or '硬件事件'}，风险等级 {event.get('risk_level')}，建议进入巡检或工单闭环。",
                'danger', '硬件事件中心', f"/hardware?event_id={event.get('id')}", event.get('created_at'), 'hardware'))

    for record in list_inspection_records(100, tenant_id=tenant_id):
        if record.get('risk_level') in ['高风险', '严重风险'] and record.get('review_status') in ['待复查', '持续跟踪']:
            items.append(_notification(
                f"archive-{record.get('id')}", '高风险档案待复查',
                f"{record.get('location') or '现场'} 的巡检档案风险等级为 {record.get('risk_level')}，当前状态 {record.get('review_status')}。",
                'warning', '巡检档案', f"/records?record_id={record.get('id')}", record.get('updated_at') or record.get('created_at'), 'archive'))

    # 业务状态变化日志同步进入通知中心，形成“操作日志 → 通知 → 业务页面”的联动。
    for log in list_operation_logs(limit=60):
        if log.get('level') not in ['warning', 'danger', 'success']:
            continue
        items.append(_notification(
            f"log-notice-{log.get('id')}",
            log.get('title') or '业务状态更新',
            log.get('detail') or '系统业务状态发生变化。',
            'success' if log.get('level') == 'success' else log.get('level'),
            log.get('module') or '系统操作日志',
            log.get('link') or '/notifications',
            log.get('created_at'),
            'operation_log'
        ))

    def sort_key(item: Dict[str, Any]) -> tuple[int, str]:
        rank = {'danger': 0, 'warning': 1, 'info': 2, 'success': 3}.get(item.get('level'), 9)
        return (rank, item.get('created_at', ''))

    items = sorted(items, key=sort_key)[:limit]
    read_ids = _read_ids()
    for item in items:
        item['read'] = item['id'] in read_ids
    unread = len([i for i in items if not i['read']])
    return {
        'items': items,
        'summary': {
            'total': len(items),
            'unread': unread,
            'high_priority': len([i for i in items if i['level'] == 'danger']),
            'pending': len([i for i in items if i['category'] in ['overdue', 'due_soon', 'high_risk', 'review', 'hardware']]),
            'generated_at': _now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    }


def mark_all_notifications_read(tenant_id: int | None = None) -> Dict[str, Any]:
    data = build_notifications(limit=500, tenant_id=tenant_id)
    ids = {i['id'] for i in data['items']}
    _save_read_ids(ids)
    return {'message': 'all read', 'read_count': len(ids)}


def mark_notification_read(notification_id: str) -> Dict[str, Any]:
    """把单条通知标记为已读。

    通知本身是按业务数据实时拼出来的（没有独立表），已读状态统一存在
    data/notification_read.json 里，因此这里只追加一个 id。
    """
    nid = str(notification_id or '').strip()
    if not nid:
        return {'message': 'invalid id', 'updated': False}
    ids = _read_ids()
    ids.add(nid)
    _save_read_ids(ids)
    return {'message': 'read', 'id': nid, 'read_count': len(ids)}
