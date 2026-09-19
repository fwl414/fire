from __future__ import annotations

import hashlib
from typing import Any, Dict

from services.record_persistence_service import list_inspection_records, get_inspection_record


def _hash_report(record: Dict[str, Any]) -> str:
    text = '|'.join([
        str(record.get('id', '')),
        str(record.get('report_no', '')),
        str(record.get('location', '')),
        str(record.get('risk_level', '')),
        str(record.get('created_at', '')),
    ])
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16].upper()


def build_verify_url(report_no: str, base_url: str = '') -> str:
    prefix = (base_url or '').rstrip('/')
    return f"{prefix}/report-verify/{report_no}"


def verify_report(report_no: str) -> Dict[str, Any]:
    for item in list_inspection_records(limit=500):
        if item.get('report_no') == report_no or item.get('id') == report_no:
            record = get_inspection_record(item.get('id'))
            orders = record.get('workorders', []) or []
            closed = len([o for o in orders if o.get('status') == '已闭环'])
            return {
                'valid': True,
                'message': '该报告真实有效，由智慧消防 Agent 系统生成，可用于巡检归档和整改闭环追溯。',
                'report_no': record.get('report_no') or record.get('id'),
                'record_id': record.get('id'),
                'location': record.get('location'),
                'created_at': record.get('created_at'),
                'risk_level': record.get('risk_level'),
                'risk_score': record.get('risk_score'),
                'closed_loop_status': f"{closed}/{len(orders)} 工单已闭环" if orders else '暂无关联工单',
                'review_status': record.get('review_status'),
                'report_hash': _hash_report(record),
            }
    return {
        'valid': False,
        'report_no': report_no,
        'message': '未查询到该报告，请核验报告编号或二维码来源。',
    }
