from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import Device, DeviceTelemetry, InspectionRecord, FaultTicket


DEMO_DEVICES = [
    {
        "device_code": "FE-001",
        "device_name": "实验室A区灭火器",
        "device_type": "灭火器",
        "location": "实验室A区",
        "status": "正常",
        "responsible_person": "张老师",
        "remark": "V1.0.0 演示设备"
    },
    {
        "device_code": "HY-002",
        "device_name": "教学楼二层消火栓",
        "device_type": "消火栓",
        "location": "教学楼B区二楼",
        "status": "异常",
        "responsible_person": "李老师",
        "remark": "V1.0.0 演示设备"
    },
    {
        "device_code": "EL-003",
        "device_name": "机房配电箱",
        "device_type": "配电箱",
        "location": "机房C区",
        "status": "异常",
        "responsible_person": "王老师",
        "remark": "V1.0.0 演示设备"
    },
]


DEMO_RECORDS = [
    {
        "location": "实验室A区",
        "description": "消防通道堆放杂物，插排串联，旁边堆放纸箱，电线较为杂乱。",
        "hazards": ["消防通道堵塞", "插座过载", "可燃物堆积", "电线杂乱"],
        "risk_score": 86,
        "risk_level": "严重风险",
    },
    {
        "location": "教学楼B区二楼",
        "description": "消火栓被杂物遮挡，灭火器前方堆放物品。",
        "hazards": ["消防设施被遮挡", "灭火器被遮挡"],
        "risk_score": 45,
        "risk_level": "中风险",
    },
    {
        "location": "宿舍楼一层楼道",
        "description": "楼道内存在电动车违规充电，影响疏散通道。",
        "hazards": ["电动车违规充电", "消防通道堵塞"],
        "risk_score": 69,
        "risk_level": "高风险",
    },
    {
        "location": "机房C区",
        "description": "配电箱附近有焦糊味和少量烟雾，线路杂乱。",
        "hazards": ["烟雾", "配电箱周围堆物", "电线杂乱"],
        "risk_score": 92,
        "risk_level": "严重风险",
    },
    {
        "location": "办公区D区",
        "description": "灭火器配置正常，通道畅通，未发现明显隐患。",
        "hazards": [],
        "risk_score": 0,
        "risk_level": "低风险",
    },
]


def _safe_create(model_cls, data: dict):
    """
    只写入 SQLAlchemy 模型中真实存在的字段，避免版本迭代后字段不匹配导致 500。
    """
    columns = set(model_cls.__table__.columns.keys())
    safe_data = {k: v for k, v in data.items() if k in columns}
    return model_cls(**safe_data)


def _safe_set(obj, **kwargs):
    columns = set(obj.__table__.columns.keys())
    for k, v in kwargs.items():
        if k in columns:
            setattr(obj, k, v)


def _report(record):
    hazards = "、".join(record["hazards"]) if record["hazards"] else "未发现明显隐患"
    return f"""智慧消防风险评估与应急辅助决策报告

一、巡检概述
巡检地点：{record["location"]}
现场描述：{record["description"]}

二、隐患识别
{hazards}

三、风险评估
风险评分：{record["risk_score"]}
风险等级：{record["risk_level"]}

四、整改建议
请根据风险等级优先整改高风险隐患，完成后进行复查闭环。
"""


def seed_demo_data(db: Session):
    created_devices = 0
    created_records = 0
    created_tickets = 0

    device_map = {}

    for item in DEMO_DEVICES:
        device = db.query(Device).filter(Device.device_code == item["device_code"]).first()
        if not device:
            device = _safe_create(Device, item)
            db.add(device)
            db.flush()
            created_devices += 1
        device_map[item["location"]] = device

        # V1.0.0：同步生成设备遥测演示数据，避免设备数据表首次打开为空。
        # 电气/水系统指标（current/voltage/pressure/remaining_current）由
        # seed_telemetry_demo_data 统一补齐，不在此处重复填。
        if db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == device.id).count() < 3:
            base_samples = [
                {"temperature": 26.5, "smoke": 0.02, "co": 0.01, "battery": 95, "online": True},
                {"temperature": 36.8 if item["status"] == "异常" else 27.1, "smoke": 0.16 if item["status"] == "异常" else 0.03, "co": 0.04, "battery": 78, "online": True},
                {"temperature": 54.2 if item["device_type"] == "配电箱" else 29.4, "smoke": 0.51 if item["device_type"] == "配电箱" else 0.05, "co": 0.18 if item["device_type"] == "配电箱" else 0.02, "battery": 62, "online": item["status"] != "异常" or item["device_type"] != "消火栓"},
            ]
            for idx, sample in enumerate(base_samples):
                db.add(DeviceTelemetry(
                    device_id=device.id,
                    temperature=sample["temperature"],
                    smoke=sample["smoke"],
                    co=sample["co"],
                    battery=sample["battery"],
                    online=sample["online"],
                    created_at=datetime.utcnow() - timedelta(hours=idx)
                ))

    for i, item in enumerate(DEMO_RECORDS):
        exists = db.query(InspectionRecord).filter(
            InspectionRecord.location == item["location"],
            InspectionRecord.description == item["description"]
        ).first()
        if exists:
            continue

        device = device_map.get(item["location"])
        created_at = datetime.utcnow() - timedelta(days=len(DEMO_RECORDS) - i)
        report = _report(item)

        record_data = {
            "device_id": device.id if device else None,
            "device_code": device.device_code if device else "",
            "device_name": device.device_name if device else "",
            "location": item["location"],
            "description": item["description"],
            "image_path": "",
            "hazards": json.dumps(item["hazards"], ensure_ascii=False),
            "risk_score": item["risk_score"],
            "risk_level": item["risk_level"],
            "suggestion": "请按隐患类型制定整改措施，并由责任人复查确认。",
            "report": report,
            "agent_steps": json.dumps([
                "演示数据：接收巡检任务。",
                "演示数据：完成隐患识别。",
                "演示数据：完成风险评分。",
                "演示数据：生成巡检报告。"
            ], ensure_ascii=False),
            "used_vision_api": False,
            "used_text_model_api": True,
            "model_provider": "demo",
            "model_name": "demo-seed",
            "created_at": created_at,
        }

        record = _safe_create(InspectionRecord, record_data)
        db.add(record)
        db.flush()
        created_records += 1

        if item["risk_level"] in ["高风险", "严重风险"]:
            ticket_data = {
                "record_id": record.id,
                "device_id": device.id if device else None,
                "title": f"{item['risk_level']}演示整改工单",
                "description": f"隐患：{'、'.join(item['hazards'])}\n\n请尽快整改并复查。",
                "risk_level": item["risk_level"],
                "status": "待受理",
                "created_at": created_at,
            }
            ticket = _safe_create(FaultTicket, ticket_data)
            db.add(ticket)
            created_tickets += 1

    db.commit()

    return {
        "created_devices": created_devices,
        "created_records": created_records,
        "created_tickets": created_tickets,
        "total_devices": db.query(Device).count(),
        "total_records": db.query(InspectionRecord).count(),
        "total_tickets": db.query(FaultTicket).count(),
        "message": "Demo data is ready."
    }


# ---------------- V1.0.0 runtime closed-loop demo seeding ----------------

def seed_runtime_demo_data() -> dict:
    """Seed the runtime SQLite tables used by Records / WorkOrders / Dashboard.

    The SQLAlchemy demo seed above writes the legacy ORM tables. V1.0.0 also fills
    the runtime persistence tables because the product pages read from them.
    """
    from services.record_persistence_service import save_inspection_record, list_inspection_records, list_workorders
    from services.workorder_service import generate_workorders_from_inspection, build_inspection_report, simulate_workorder_flow

    created = 0
    closed = 0
    for idx, item in enumerate(DEMO_RECORDS, start=1):
        record_id = f"DEMO-INSPECTION-{idx:03d}"
        workorders = generate_workorders_from_inspection({
            "inspection_id": record_id,
            "location": item["location"],
            "hazards": item["hazards"],
            "risk_level": item["risk_level"],
            "risk_score": item["risk_score"],
        }).get("orders", [])

        # 让演示数据中包含已闭环样本，Dashboard 和工单闭环率不再全为 0。
        if idx == 2 and workorders:
            workorders[0] = simulate_workorder_flow(workorders[0])
            closed += 1

        report = build_inspection_report({
            "location": item["location"],
            "hazards": item["hazards"],
            "risk_level": item["risk_level"],
            "risk_score": item["risk_score"],
            "workorders": workorders,
        })

        save_inspection_record({
            "id": record_id,
            "location": item["location"],
            "description": item["description"],
            "hazards": item["hazards"],
            "risk_level": item["risk_level"],
            "risk_score": item["risk_score"],
            "result": {
                "source": "v12_8_3_demo_seed",
                "image_paths": [f"uploads/demo_scene_{idx:02d}.jpg"] if idx <= 3 else [],
                "agent_summary": "演示数据已形成：隐患识别 → 风险评分 → 整改工单 → 巡检报告 → 档案归档。",
                "hazard_results": [
                    {
                        "hazard_name": h,
                        "risk_level": item["risk_level"],
                        "category": "消防巡检",
                        "evidence": f"现场描述与演示场景中识别到：{h}。",
                        "possible_consequence": "可能影响人员疏散、初期灭火或消防救援通行。",
                        "suggestion": "建议立即/限期整改，并在系统中完成复查闭环。",
                        "need_immediate_fix": item["risk_level"] in ["高风险", "严重风险"],
                    } for h in item["hazards"]
                ],
                "rag_reference_cards": [
                    {
                        "id": f"demo_ref_{idx}_1",
                        "title": "消防通道与疏散通道管理要求",
                        "category": "疏散通道",
                        "similarity": 92,
                        "summary": "疏散通道、安全出口和消防车通道应保持畅通，不得堆放杂物或设置障碍物。",
                        "source": "系统消防知识库",
                        "content_preview": "通道保持畅通是单位消防安全巡查和整改闭环的重要内容。",
                    },
                    {
                        "id": f"demo_ref_{idx}_2",
                        "title": "消防隐患整改闭环要求",
                        "category": "巡检标准",
                        "similarity": 88,
                        "summary": "发现隐患后应明确责任人、整改措施、整改期限和复查要求。",
                        "source": "系统消防知识库",
                        "content_preview": "整改闭环应覆盖发现、派单、整改、复查、归档全过程。",
                    },
                ],
                "agent_steps": [
                    "任务理解：读取现场描述与演示场景。",
                    "隐患识别：抽取消防通道、可燃物、电气等典型隐患。",
                    "风险评分：根据隐患严重度计算综合风险。",
                    "RAG依据：匹配消防安全管理与整改闭环要求。",
                    "闭环生成：生成整改工单、巡检报告和档案记录。",
                ],
            },
            "learning_recommendations": {
                "topics": ["消防通道管理", "电气火灾预防", "消防设施巡查"],
                "message": "建议结合隐患类型学习对应消防知识点。",
            },
            "workorders": workorders,
            "report": report,
        })
        created += 1

    return {
        "created_or_updated_runtime_records": created,
        "closed_demo_orders": closed,
        "total_runtime_records": len(list_inspection_records(500)),
        "total_runtime_workorders": len(list_workorders("", 500)),
    }


def seed_hardware_demo_data() -> dict:
    from services.hardware_event_service import create_hardware_event, list_hardware_events

    samples = [
        {
            "id": "DEMO-HW-001",
            "event_type": "smoke_alarm",
            "location": "机房B区",
            "device_id": "SMK-001",
            "device_name": "机房烟感",
            "description": "烟感设备上报烟雾浓度异常，疑似初期火情。",
            "risk_level": "高风险",
            "risk_score": 78,
            "status": "待处理",
        },
        {
            "id": "DEMO-HW-002",
            "event_type": "electrical_alarm",
            "location": "实验室A区",
            "device_id": "ELE-002",
            "device_name": "电气火灾探测器",
            "description": "探测到插排过载、线路温升和可燃物靠近。",
            "risk_level": "高风险",
            "risk_score": 82,
            "status": "处理中",
        },
        {
            "id": "DEMO-HW-003",
            "event_type": "camera_snapshot",
            "location": "教学楼三层",
            "device_id": "CAM-003",
            "device_name": "走廊摄像头",
            "description": "画面显示灭火器被杂物遮挡，走廊存在临时堆物。",
            "risk_level": "中风险",
            "risk_score": 48,
            "status": "已闭环",
        },
    ]
    for item in samples:
        create_hardware_event(item)
    return {
        "created_or_updated_hardware_events": len(samples),
        "total_hardware_events": len(list_hardware_events(limit=500)),
    }


# 电气火灾监测 / 消防水源监测两个页面依赖的演示点位。
# 这是「演示点位」而不是编造业务数据：取值落在 telemetry_analyzer.TELEMETRY_RULES
# 的真实阈值区间内，状态由后端规则判定，前端不参与编数。
# 「异常」状态的设备给一个会触发预警/告警的值，用来验证阈值链路。
TELEMETRY_DEMO_DEVICES = [
    {"device_code": "ELE-DIST-001", "device_name": "1号办公楼总配电箱", "device_type": "配电箱",
     "location": "1号办公楼 1层配电室", "status": "正常"},
    {"device_code": "ELE-DIST-002", "device_name": "1号办公楼照明回路配电箱", "device_type": "配电箱",
     "location": "1号办公楼 2层西侧", "status": "正常"},
    {"device_code": "ELE-DIST-003", "device_name": "2号研发楼机房配电箱", "device_type": "配电箱",
     "location": "2号研发楼 3层机房", "status": "异常"},
    {"device_code": "ELE-DIST-004", "device_name": "3号宿舍楼动力配电箱", "device_type": "配电箱",
     "location": "3号宿舍楼 地下一层", "status": "正常"},
    {"device_code": "HYD-XHS-001", "device_name": "1号办公楼1层消火栓", "device_type": "消火栓",
     "location": "1号办公楼 1层东侧", "status": "正常"},
    {"device_code": "HYD-XHS-002", "device_name": "1号办公楼5层消火栓", "device_type": "消火栓",
     "location": "1号办公楼 5层西侧", "status": "正常"},
    {"device_code": "HYD-XHS-003", "device_name": "2号研发楼2层消火栓", "device_type": "消火栓",
     "location": "2号研发楼 2层南侧", "status": "异常"},
    {"device_code": "HYD-XHS-004", "device_name": "3号宿舍楼地下一层消火栓", "device_type": "消火栓",
     "location": "3号宿舍楼 地下一层", "status": "正常"},
    {"device_code": "HYD-XHS-005", "device_name": "地下车库B1区消火栓", "device_type": "消火栓",
     "location": "地下车库 B1区", "status": "正常"},
]

# 每类设备上报的指标取值。正常档落在 normal_range 内；
# 异常档故意越界（remaining_current 620 > warning 500、current 27.5 > warning 25、
# pressure 0.18 <= alarm_threshold_low 0.2），用来验证阈值判定确实生效。
TELEMETRY_DEMO_VALUES = {
    "配电箱": {
        "正常": {"remaining_current": 12.5, "current": 18.2, "voltage": 220.5},
        "异常": {"remaining_current": 620.0, "current": 27.5, "voltage": 218.5},
    },
    "消火栓": {
        "正常": {"pressure": 0.45},
        "异常": {"pressure": 0.18},
    },
}


def seed_telemetry_demo_data(db: Session, tenant_id):
    """幂等地为配电箱/消火栓补齐电气与水系统遥测样本。

    - 演示点位按 device_code 幂等创建，不改动既有设备
    - 仅在设备缺该指标样本时才写入，重复启动不会堆数据
    - 只写 DeviceTelemetry 里真实存在的列（列映射取自 device_ingest_service，
      避免两处各维护一份导致漂移）
    """
    from services.device_ingest_service import TELEMETRY_COLUMNS

    created_devices = 0
    created_samples = 0

    # ① 幂等创建演示点位
    for item in TELEMETRY_DEMO_DEVICES:
        exists = db.query(Device).filter(Device.device_code == item["device_code"]).first()
        if exists:
            continue
        device = _safe_create(Device, {**item, "tenant_id": tenant_id})
        db.add(device)
        db.flush()
        created_devices += 1

    # ② 为所有配电箱/消火栓（含启动种子里的那几台）补齐缺的指标样本
    for device_type, value_sets in TELEMETRY_DEMO_VALUES.items():
        devices = db.query(Device).filter(Device.device_type == device_type).all()
        for device in devices:
            values = value_sets.get(device.status) or value_sets["正常"]
            for metric, value in values.items():
                column = TELEMETRY_COLUMNS.get(metric)
                if not column:
                    continue
                already = (
                    db.query(DeviceTelemetry)
                    .filter(
                        DeviceTelemetry.device_id == device.id,
                        getattr(DeviceTelemetry, column).isnot(None),
                    )
                    .first()
                )
                if already:
                    continue
                db.add(DeviceTelemetry(
                    tenant_id=device.tenant_id,
                    device_id=device.id,
                    online=True,
                    created_at=datetime.utcnow(),
                    **{column: value},
                ))
                created_samples += 1

    db.commit()
    return {"created_devices": created_devices, "created_samples": created_samples}
