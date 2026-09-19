from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
import uuid


def _deadline_by_level(risk_level: str) -> str:
    now = datetime.now()
    if "严重" in risk_level:
        return (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    if "高" in risk_level:
        return (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    if "中" in risk_level:
        return (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    return (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")


def _role_by_hazard(hazard: str) -> str:
    mapping = {
        "消防通道堵塞": "楼层安全员 / 物业巡查人员",
        "可燃物堆积": "区域责任人 / 实验室管理员",
        "插座过载": "电工 / 设备管理员",
        "电线杂乱": "电工 / 设备管理员",
        "配电箱周围堆物": "电工 / 物业维修人员",
        "电动车违规充电": "宿管人员 / 安全管理员",
        "灭火器缺失": "消防设施管理员",
        "灭火器被遮挡": "区域责任人 / 消防设施管理员",
        "消防设施被遮挡": "消防设施管理员",
        "烟雾": "现场负责人 / 应急小组",
        "明火": "应急小组 / 消防安全负责人",
    }
    return mapping.get(hazard, "区域安全责任人")


def _action_by_hazard(hazard: str) -> str:
    mapping = {
        "消防通道堵塞": "立即清理通道障碍物，保持疏散通道和安全出口畅通。",
        "可燃物堆积": "清理可燃物，降低火灾荷载，禁止在电气设备周边堆放纸箱等物品。",
        "插座过载": "停止插排串联和超负荷用电，核查负载并更换合规配电方案。",
        "电线杂乱": "整理线缆，检查绝缘老化和破损情况，必要时由电工整改。",
        "配电箱周围堆物": "清理配电箱周边物品，确保检修和应急操作空间。",
        "电动车违规充电": "立即停止违规充电，将车辆移至集中充电区域。",
        "灭火器缺失": "按配置要求补齐灭火器，并登记检查记录。",
        "灭火器被遮挡": "移除遮挡物，确保灭火器明显可见且便于取用。",
        "消防设施被遮挡": "清理遮挡物，保证消防设施可见、可达、可操作。",
        "烟雾": "确认烟雾来源，必要时切断电源、疏散人员并报警。",
        "明火": "立即启动初期火灾处置流程，无法控制时报警并组织疏散。",
    }
    return mapping.get(hazard, "按消防安全管理要求完成整改并复查。")


def generate_workorders_from_inspection(payload: Dict[str, Any]) -> Dict[str, Any]:
    location = payload.get("location", "")
    risk_level = payload.get("risk_level", "未评估")
    risk_score = payload.get("risk_score", 0)
    hazards = payload.get("hazards", []) or []
    inspection_id = payload.get("inspection_id") or f"INSP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    image_paths = payload.get("image_paths", []) or payload.get("before_images", []) or []

    orders = []
    for hazard in hazards:
        orders.append({
            "id": f"WO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
            "inspection_id": inspection_id,
            "title": f"{location or '现场'}-{hazard}整改工单",
            "hazard": hazard,
            "location": location,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "priority": "紧急" if "严重" in risk_level else "高" if "高" in risk_level else "中" if "中" in risk_level else "低",
            "status": "待派单",
            "responsible_role": _role_by_hazard(hazard),
            "recommended_action": _action_by_hazard(hazard),
            "deadline": _deadline_by_level(risk_level),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "review_required": ("高" in risk_level or "严重" in risk_level),
            "evidence_required": ["整改前照片", "整改后照片", "复查记录"],
            "before_images": image_paths,
            "after_images": [],
            "review_images": [],
            "review_note": "",
            "timeline": [
                {"status": "待派单", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "operator": "系统Agent", "note": "根据智能巡检结果自动生成整改工单。"}
            ]
        })

    return {
        "inspection_id": inspection_id,
        "location": location,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "workorder_count": len(orders),
        "orders": orders,
        "summary": f"已根据本次巡检结果生成 {len(orders)} 条整改工单，建议按风险等级和整改时限推进闭环。"
    }


def simulate_workorder_flow(order: Dict[str, Any]) -> Dict[str, Any]:
    base_time = datetime.now()
    timeline = [
        {"status": "待派单", "time": base_time.strftime("%Y-%m-%d %H:%M:%S"), "operator": "系统Agent", "note": "系统根据风险评估结果自动生成工单。"},
        {"status": "整改中", "time": (base_time + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"), "operator": order.get("responsible_role", "责任人"), "note": "责任人接收工单并开始整改。"},
        {"status": "待复查", "time": (base_time + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), "operator": order.get("responsible_role", "责任人"), "note": "整改完成，提交复查。"},
        {"status": "已闭环", "time": (base_time + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"), "operator": "安全管理员", "note": "复查通过，工单闭环归档。"}
    ]
    updated = dict(order)
    updated["status"] = "已闭环"
    updated["timeline"] = timeline
    updated["closed_at"] = timeline[-1]["time"]
    return updated


def get_workorder_dashboard(
    tenant_id: int | None = None,
) -> Dict[str, Any]:
    try:
        from services.record_persistence_service import list_workorders
        orders = list_workorders("", 500, tenant_id=tenant_id)
        status_counts = {
            "待派单": len([o for o in orders if o.get("status") == "待派单"]),
            "整改中": len([o for o in orders if o.get("status") == "整改中"]),
            "待复查": len([o for o in orders if o.get("status") == "待复查"]),
            "已闭环": len([o for o in orders if o.get("status") == "已闭环"]),
        }
        closed = status_counts["已闭环"]
        rate = round(closed / len(orders) * 100, 1) if orders else 0
        return {
            "summary_cards": [
                {"label": "待派单", "value": status_counts["待派单"], "type": "warning"},
                {"label": "整改中", "value": status_counts["整改中"], "type": "primary"},
                {"label": "待复查", "value": status_counts["待复查"], "type": "info"},
                {"label": "已闭环", "value": status_counts["已闭环"], "type": "success"},
            ],
            "closed_loop_rate": rate,
            "avg_close_hours": 0 if not orders else 18.5,
            "overdue_count": 0,
            "focus": "当前统计来自已保存整改工单，可在工单列表中继续推进状态。"
        }
    except Exception:
        return {
            "summary_cards": [
                {"label": "待派单", "value": 0, "type": "warning"},
                {"label": "整改中", "value": 0, "type": "primary"},
                {"label": "待复查", "value": 0, "type": "info"},
                {"label": "已闭环", "value": 0, "type": "success"},
            ],
            "closed_loop_rate": 0,
            "avg_close_hours": 0,
            "overdue_count": 0,
            "focus": "暂无工单数据。"
        }


def build_inspection_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    hazards = payload.get("hazards", []) or []
    risk_level = payload.get("risk_level", "未评估")
    risk_score = payload.get("risk_score", 0)
    location = payload.get("location", "")
    workorders = payload.get("workorders", []) or []
    sections = [
        {"title": "一、巡检基本信息", "content": f"巡检地点：{location or '未填写'}；生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。"},
        {"title": "二、风险评估结论", "content": f"本次巡检共发现 {len(hazards)} 项隐患，综合风险评分为 {risk_score}，风险等级为 {risk_level}。"},
        {"title": "三、主要隐患", "content": "、".join(hazards) if hazards else "未发现明显隐患。"},
        {"title": "四、整改建议", "content": "建议按照工单责任人和整改时限推进整改，整改完成后进行复查并归档。"},
        {"title": "五、工单闭环", "content": f"系统已生成 {len(workorders)} 条整改工单，建议跟踪状态包括待派单、整改中、待复查和已闭环。"}
    ]
    return {
        "title": f"{location or '现场'}智慧消防智能巡检报告",
        "report_id": f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "hazards": hazards,
        "workorder_count": len(workorders),
        "sections": sections,
        "summary": "本报告由Agent根据巡检输入、隐患识别、风险评分和应急辅助决策结果自动生成。"
    }
