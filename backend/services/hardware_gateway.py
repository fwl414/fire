from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def get_hardware_overview() -> Dict[str, Any]:
    return {
        "positioning": "硬件接口为预留扩展能力，当前系统核心仍是Agent、RAG、风险评估和应急辅助决策。",
        "architecture": [
            {
                "layer": "感知层",
                "description": "烟雾传感器、温湿度传感器、电气火灾探测器、摄像头、手持巡检终端等。"
            },
            {
                "layer": "接入层",
                "description": "ESP32、边缘网关、HTTP/MQTT 数据上报接口、视频或图片上传接口。"
            },
            {
                "layer": "智能体层",
                "description": "智能模型 Agent 接收硬件事件、巡检文本和图片，完成隐患识别、RAG 检索和风险决策。"
            },
            {
                "layer": "应用层",
                "description": "Dashboard、智能巡检、消防问答、风险解释、工单闭环和应急辅助决策。"
            }
        ],
        "supported_interfaces": [
            {
                "name": "传感器数据上报",
                "method": "POST",
                "path": "/api/hardware/sensor-report",
                "description": "预留给烟感、温感、电气火灾探测器或边缘网关上报结构化数据。"
            },
            {
                "name": "硬件事件上报",
                "method": "POST",
                "path": "/api/hardware/event-report",
                "description": "预留给硬件网关上报异常事件，例如烟雾报警、温度异常、电流过载。"
            },
            {
                "name": "设备心跳",
                "method": "POST",
                "path": "/api/hardware/heartbeat",
                "description": "预留给硬件设备定期上报在线状态、电量和信号强度。"
            },
            {
                "name": "模拟硬件数据",
                "method": "GET",
                "path": "/api/hardware/mock/latest",
                "description": "用于测试展示，无需真实硬件即可查看接入效果。"
            }
        ]
    }


def get_supported_hardware_types() -> List[Dict[str, Any]]:
    return [
        {
            "type": "smoke_sensor",
            "name": "烟雾传感器",
            "data_fields": ["smoke_ppm", "alarm", "battery", "location"],
            "risk_mapping": "烟雾浓度异常可触发烟雾隐患和初期火情应急流程。"
        },
        {
            "type": "temperature_sensor",
            "name": "温湿度传感器",
            "data_fields": ["temperature", "humidity", "alarm", "location"],
            "risk_mapping": "温度异常可作为电气过热或火情的辅助证据。"
        },
        {
            "type": "electrical_fire_detector",
            "name": "电气火灾探测器",
            "data_fields": ["current", "voltage", "leakage_current", "temperature", "alarm"],
            "risk_mapping": "过流、漏电、线缆温度异常可映射为电气火灾风险。"
        },
        {
            "type": "camera",
            "name": "现场摄像头/巡检图片",
            "data_fields": ["image_url", "device_id", "location", "capture_time"],
            "risk_mapping": "图片进入视觉智能模型，用于识别通道堵塞、灭火器遮挡、可燃物堆积等。"
        },
        {
            "type": "gateway",
            "name": "ESP32/边缘网关",
            "data_fields": ["gateway_id", "online", "rssi", "device_count"],
            "risk_mapping": "负责汇聚多类传感器数据并统一上报给后端接口。"
        }
    ]


def get_mock_hardware_latest() -> Dict[str, Any]:
    return {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gateway": {
            "gateway_id": "GW-FIRE-001",
            "name": "实验室A区边缘网关",
            "online": True,
            "rssi": -58,
            "device_count": 4
        },
        "sensors": [
            {
                "device_id": "SMK-A-001",
                "type": "smoke_sensor",
                "name": "实验室A区烟雾传感器",
                "location": "实验室A区",
                "value": {"smoke_ppm": 18, "alarm": False, "battery": 92},
                "status": "normal",
                "risk_hint": "烟雾浓度正常。"
            },
            {
                "device_id": "TMP-A-002",
                "type": "temperature_sensor",
                "name": "配电箱温度探测器",
                "location": "实验室A区配电箱",
                "value": {"temperature": 41.5, "humidity": 46, "alarm": False},
                "status": "warning",
                "risk_hint": "温度偏高，建议结合电气隐患巡检。"
            },
            {
                "device_id": "ELE-A-003",
                "type": "electrical_fire_detector",
                "name": "电气火灾探测器",
                "location": "实验室A区配电箱",
                "value": {"current": 18.2, "voltage": 220, "leakage_current": 22, "temperature": 52.1, "alarm": True},
                "status": "alarm",
                "risk_hint": "检测到电气异常，可触发高风险巡检任务。"
            },
            {
                "device_id": "CAM-A-004",
                "type": "camera",
                "name": "实验室A区巡检摄像头",
                "location": "实验室A区门口",
                "value": {"image_url": "", "capture_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                "status": "online",
                "risk_hint": "可作为视觉智能模型输入来源。"
            }
        ],
        "agent_trigger_example": {
            "location": "实验室A区配电箱",
            "description": "电气火灾探测器上报漏电流和线缆温度异常，建议联动智能巡检 Agent 进行风险评估。",
            "suggested_hazards": ["插座过载", "电线杂乱", "配电箱周围堆物"],
            "suggested_action": "创建一次智能巡检任务，并结合 RAG 知识库生成处置建议。"
        }
    }


def sensor_report_payload_example() -> Dict[str, Any]:
    return {
        "device_id": "ELE-A-003",
        "device_type": "electrical_fire_detector",
        "location": "实验室A区配电箱",
        "timestamp": "2026-05-27 14:30:00",
        "data": {
            "current": 18.2,
            "voltage": 220,
            "leakage_current": 22,
            "temperature": 52.1,
            "alarm": True
        }
    }


def accept_sensor_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    device_type = payload.get("device_type", "")
    data = payload.get("data", {})
    risk_hints: List[str] = []

    if device_type == "smoke_sensor" and data.get("alarm"):
        risk_hints.append("烟雾报警，建议触发初期火情应急流程。")
    if device_type == "temperature_sensor" and float(data.get("temperature", 0) or 0) >= 50:
        risk_hints.append("温度异常，建议排查电气过热或火情。")
    if device_type == "electrical_fire_detector":
        if data.get("alarm"):
            risk_hints.append("电气火灾探测器报警，建议触发智能巡检 Agent。")
        if float(data.get("leakage_current", 0) or 0) >= 20:
            risk_hints.append("漏电流偏高，建议排查线路绝缘和用电负荷。")

    return {
        "accepted": True,
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "payload": payload,
        "risk_hints": risk_hints,
        "agent_integration": {
            "can_trigger_agent": bool(risk_hints),
            "recommended_next_step": "将硬件事件转化为智能巡检任务，进入智能模型 Agent 风险评估流程。"
        }
    }


def accept_hardware_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "accepted": True,
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": payload,
        "message": "硬件事件已接收。当前为预留接口，后续可接入消息队列、工单系统或 Agent 自动触发流程。"
    }


def accept_heartbeat(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "accepted": True,
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "heartbeat": payload,
        "status": "online" if payload.get("online", True) else "offline"
    }
