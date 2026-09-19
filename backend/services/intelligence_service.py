"""
智能分析服务
统一封装8大智能分析能力：
1. 告警深度分析
2. 巡检风险研判
3. 工单整改辅助
4. 设备故障诊断
5. 每日安全简报
6. 告警聚合分析
7. 知识经验沉淀
8. 数据自然语言查询
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
import json
import asyncio

from sqlalchemy.orm import Session

from database import AlertRecord, Building, Device, FaultTicket, InspectionRecord
from services.alert_agent_service import _estimate_risk_score, _get_alert_profile
from services.common_utils import local_day_bounds_utc, parse_date
from services.risk_engine import HAZARD_PROFILES, build_hazard_items, calculate_risk, canonical_hazard

# 工单闭环状态（与 routers/workorder.py 的状态机一致）
CLOSED_TICKET_STATUSES = ("已完成", "已关闭", "已闭环")
# 告警未处置状态
OPEN_ALERT_STATUSES = ("pending", "processing")


def _data_completeness(payload: Dict[str, Any], keys: Sequence[str]) -> float:
    """按关键字段的完整度给出 0.6~1.0 的值。

    规则/模板引擎没有「模型概率」这种东西，所以这里给的**不是概率**，而是输入信息够不够：
    关键字段齐全，结论背后的事实就多；字段缺失，结论只能靠兜底规则。以前这个字段是
    `random.random()`，同一个输入每次刷新都不一样的「置信度」没有任何意义。
    """
    if not keys:
        return 0.6
    provided = sum(1 for key in keys if payload.get(key) not in (None, "", [], {}))
    return round(0.6 + 0.4 * provided / len(keys), 2)


# ============================================================
# 1. 告警深度分析
# ============================================================

def analyze_alert_detail(
    alert_data: Dict[str, Any],
    similar_alerts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    告警详情深度分析
    生成更丰富的分析内容：风险评估、处置步骤、推理过程、法规依据

    风险分按严重程度做**确定性映射**（复用告警接入侧的 `_estimate_risk_score`，全系统一套口径），
    不再叠加随机扰动 —— 以前这里是 `random.randint(-5, 5)`，同一条告警每次刷新分数都不一样。
    「类似告警」也不再由这里编造，改由调用方传入本租户的真实历史告警。
    """
    alert_type = alert_data.get("alert_type", "")
    profile = _get_alert_profile(alert_type)
    
    severity = alert_data.get("severity", profile.get("severity", "medium"))
    building_name = alert_data.get("building_name", "")
    device_id = alert_data.get("device_id", "")
    alert_value = alert_data.get("alert_value", 0)
    alert_unit = alert_data.get("alert_unit", "")
    
    risk_score = _estimate_risk_score(severity)
    
    reasoning_steps = [
        {
            "step": 1,
            "title": "告警信号确认",
            "content": f"设备{device_id}上报{profile.get('name', alert_type)}告警，当前值{alert_value}{alert_unit}，超出正常阈值范围。",
            "confidence": 0.95,
        },
        {
            "step": 2,
            "title": "风险等级评估",
            "content": f"根据告警类型「{profile.get('category', '未知')}」、严重程度「{severity}」及所在位置「{building_name}」，综合评估风险等级为{profile.get('risk_level', '中风险')}。",
            "confidence": 0.88,
            "references": [
                "《建筑设计防火规范》GB 50016-2014",
                "《火灾自动报警系统设计规范》GB 50116-2013",
            ],
        },
        {
            "step": 3,
            "title": "可能原因推断",
            "content": f"结合设备类型和历史数据，最可能的原因是：{profile.get('possible_causes', ['未知'])[0]}。需现场进一步确认。",
            "confidence": 0.72,
        },
        {
            "step": 4,
            "title": "处置方案生成",
            "content": f"建议立即采取以下措施：{profile.get('immediate_actions', ['现场核查'])[0]}，并在{profile.get('deadline_hours', 24)}小时内完成处置。",
            "confidence": 0.85,
            "references": [
                "《消防设施操作员》国家职业技能标准",
                "单位内部应急预案",
            ],
        },
    ]
    
    disposal_steps = []
    for i, action in enumerate(profile.get("immediate_actions", [])):
        disposal_steps.append({
            "order": i + 1,
            "title": f"第{i+1}步：{action[:20]}...",
            "detail": action,
            "type": "immediate",
        })
    for i, step in enumerate(profile.get("investigation_steps", [])):
        disposal_steps.append({
            "order": len(disposal_steps) + 1,
            "title": f"排查步骤{i+1}：{step[:20]}...",
            "detail": step,
            "type": "investigation",
        })
    
    related_knowledge = [
        {
            "id": "KB001",
            "title": f"{profile.get('name', '告警')}处置指南",
            "type": "操作规程",
            "match": "95%",
        },
        {
            "id": "CASE023",
            "title": f"某大厦{profile.get('name', '告警')}处置案例",
            "type": "历史案例",
            "match": "82%",
        },
        {
            "id": "REG012",
            "title": "消防设施维护管理规定",
            "type": "法规标准",
            "match": "76%",
        },
    ]
    
    # 类似告警由调用方查真实历史（同类型、本租户），没有就给空列表 —— 以前这里用
    # random 造 id、楼层、原因、处置结果，等于凭空编出「历史告警」
    real_similar_alerts = list(similar_alerts or [])

    return {
        "risk_score": risk_score,
        "risk_level": profile.get("risk_level", "中风险"),
        "reasoning_steps": reasoning_steps,
        "disposal_steps": disposal_steps,
        "related_knowledge": related_knowledge,
        "similar_alerts": real_similar_alerts,
        "confidence": _data_completeness(
            {"device_id": device_id, "building_name": building_name,
             "alert_value": alert_value, "description": alert_data.get("description", "")},
            ("device_id", "building_name", "alert_value", "description"),
        ),
        "suggested_deadline": profile.get("deadline_hours", 24),
    }


# ============================================================
# 2. 巡检风险研判
# ============================================================

def _match_hazard(text: str) -> Optional[str]:
    """从自由文本里找出规则表中已知的隐患名（先按别名精确匹配，再取最长的子串命中）。

    巡检提交上来的是一个检查项名字或一段描述，不是标准隐患名；这里只做**可解释**的
    字符串匹配，命不中就让规则表走兜底档，不猜、也不随机。
    """
    text = (text or "").strip()
    if not text:
        return None
    canonical = canonical_hazard(text)
    if canonical in HAZARD_PROFILES:
        return canonical
    hits = [name for name in HAZARD_PROFILES if name in text]
    return max(hits, key=len) if hits else None


def analyze_inspection_risk(inspection_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    巡检记录AI风险研判
    自动识别隐患、评估风险等级、生成整改建议

    隐患等级、类别、整改建议、总分全部来自规则表（`services/risk_engine`），
    与巡检 Agent、批量巡检用的是同一套口径。以前这里是 `random.choice(risk_levels)`、
    `len(hazard_items) * 15 + random.randint(10, 30)`：同一条巡检记录每次刷新，
    隐患等级和总分都在变。
    """
    content = inspection_data.get("content", "")
    items = inspection_data.get("items", [])
    building_name = inspection_data.get("building_name", "")
    inspector = inspection_data.get("inspector", "")

    level_map = {"严重风险": "high", "高风险": "high", "中风险": "medium", "低风险": "low"}

    hazard_items = []
    normal_items = []

    for i, item in enumerate(items):
        status = item.get("status", "normal")
        if status == "abnormal" or status == "hazard":
            name = item.get("name") or f"隐患项{i+1}"
            matched = _match_hazard(name) or _match_hazard(item.get("remark", ""))
            profile = build_hazard_items([matched or name])[0]
            hazard_items.append({
                "id": item.get("id", f"H{i+1}"),
                "name": name,
                "location": item.get("location", building_name),
                "risk_level": level_map.get(profile["risk_level"], "low"),
                "hazard_type": profile["category"],
                "description": item.get("remark") or profile["reason"],
                "suggestion": profile["measure"],
                "matched_rule": matched or "",
            })
        else:
            normal_items.append({
                "id": item.get("id", f"N{i+1}"),
                "name": item.get("name", f"检查项{i+1}"),
                "status": "normal",
            })

    if not hazard_items and content:
        if "异常" in content or "隐患" in content or "问题" in content:
            matched = _match_hazard(content)
            profile = build_hazard_items([matched or content])[0]
            hazard_items.append({
                "id": "H001",
                "name": matched or "巡检发现的隐患",
                "location": building_name,
                "risk_level": level_map.get(profile["risk_level"], "low"),
                "hazard_type": profile["category"],
                "description": content,
                "suggestion": profile["measure"],
                "matched_rule": matched or "",
            })

    risk_score = calculate_risk([h["matched_rule"] or h["name"] for h in hazard_items])["risk_score"]

    checked = len(items)
    checked_text = f"本次巡检共检查{checked}项" if checked else "本次巡检未提交检查项清单"
    overall_assessment = (
        f"{checked_text}，"
        f"发现隐患{len(hazard_items)}项，"
        f"其中高风险{sum(1 for h in hazard_items if h['risk_level']=='high')}项，"
        f"中风险{sum(1 for h in hazard_items if h['risk_level']=='medium')}项，"
        f"低风险{sum(1 for h in hazard_items if h['risk_level']=='low')}项。"
        f"综合风险评分为{risk_score}分，建议{'立即' if risk_score > 70 else '尽快'}安排整改。"
    )
    
    rectification_priority = []
    for h in sorted(hazard_items, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["risk_level"], 3)):
        rectification_priority.append({
            "hazard_id": h["id"],
            "name": h["name"],
            "priority": "紧急" if h["risk_level"] == "high" else ("高" if h["risk_level"] == "medium" else "中"),
            "deadline_days": 1 if h["risk_level"] == "high" else (7 if h["risk_level"] == "medium" else 30),
            "responsible": "安全管理员",
        })
    
    # 「置信度」在这里是**规则命中率**（有多少条隐患能对上规则表），不是模型概率：
    # 以前是 `random.random()`，同一个输入每次刷新都不一样
    matched_count = sum(1 for h in hazard_items if h["matched_rule"])
    confidence = round(matched_count / len(hazard_items), 2) if hazard_items else 1.0

    return {
        "risk_score": risk_score,
        "hazard_count": len(hazard_items),
        "normal_count": len(normal_items),
        "hazard_items": hazard_items,
        "overall_assessment": overall_assessment,
        "rectification_priority": rectification_priority,
        "confidence": confidence,
        "matched_rule_count": matched_count,
    }


# ============================================================
# 3. 工单整改辅助
# ============================================================

def generate_rectification_plan(workorder_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    自动生成整改方案
    包含整改步骤、验收标准、所需资源、注意事项
    """
    hazard_type = workorder_data.get("hazard_type", "消防设施")
    description = workorder_data.get("description", "")
    risk_level = workorder_data.get("risk_level", "medium")
    building_name = workorder_data.get("building_name", "")
    
    plan_templates = {
        "消防设施": {
            "steps": [
                "现场核实隐患情况，拍照留存证据",
                "制定详细整改方案，明确整改范围和标准",
                "安排专业维修人员进行设施维修或更换",
                "整改完成后进行功能测试，确保设备正常运行",
                "整理整改记录，申请复查验收",
            ],
            "acceptance": [
                "设备外观完好，无破损、锈蚀",
                "设备功能测试正常，各项指标符合标准",
                "安装位置正确，标识清晰完整",
                "相关记录齐全，符合档案管理要求",
            ],
            "resources": ["专业维修人员1名", "备品备件", "检测仪器"],
        },
        "电气安全": {
            "steps": [
                "断电并确认安全后进行现场检查",
                "检测绝缘电阻、接地电阻等参数",
                "对故障部件进行维修或更换",
                "恢复供电后进行带电测试",
                "连续观察24小时确认无异常",
            ],
            "acceptance": [
                "绝缘电阻符合规范要求",
                "设备运行温度在正常范围内",
                "无漏电、打火等异常现象",
                "电气连接牢固，无松动",
            ],
            "resources": ["电工1名", "检测仪表", "绝缘材料"],
        },
        "通道堵塞": {
            "steps": [
                "现场确认堵塞位置和堵塞物种类",
                "协调相关部门或人员清理通道",
                "设置临时警示标识",
                "清理后确认通道畅通",
                "建立长效管理机制，防止再次堵塞",
            ],
            "acceptance": [
                "疏散通道宽度符合规范要求",
                "通道内无杂物堆放",
                "应急照明和指示标志完好",
                "防火门启闭正常",
            ],
            "resources": ["保洁人员", "物业协调"],
        },
        "管理制度": {
            "steps": [
                "梳理现有制度，找出存在的问题",
                "对照法规标准修订完善制度",
                "组织相关人员培训学习",
                "制度发布并监督执行",
                "定期检查制度落实情况",
            ],
            "acceptance": [
                "制度内容符合法规要求",
                "相关人员培训到位",
                "制度发布并公示",
                "有监督执行机制",
            ],
            "resources": ["安全管理人员", "培训资料"],
        },
        "其他": {
            "steps": [
                "现场核实隐患详情",
                "制定针对性整改方案",
                "落实整改措施",
                "验证整改效果",
                "总结经验，完善预防措施",
            ],
            "acceptance": [
                "隐患已消除",
                "整改记录完整",
                "相关方确认验收",
            ],
            "resources": ["相关责任人员"],
        },
    }
    
    template = plan_templates.get(hazard_type, plan_templates["其他"])
    
    deadline_days_map = {"critical": 1, "high": 3, "medium": 7, "low": 30}
    deadline_days = deadline_days_map.get(risk_level, 7)
    
    return {
        "rectification_steps": [
            {"order": i + 1, "content": step, "duration": f"{max(1, deadline_days // len(template['steps']))}天"}
            for i, step in enumerate(template["steps"])
        ],
        "acceptance_criteria": template["acceptance"],
        "required_resources": template["resources"],
        "notes": [
            "整改过程中注意做好安全防护措施",
            "涉及动火作业需办理动火审批",
            "整改期间加强现场巡查",
            "整改完成后及时更新相关记录",
        ],
        "estimated_deadline_days": deadline_days,
        # 「置信度」= 输入信息完整度（这里走的是模板引擎，没有模型概率），不是随机数
        "confidence": _data_completeness(
            workorder_data, ("hazard_type", "description", "risk_level", "building_name")
        ),
    }


# ============================================================
# 4. 设备故障诊断
# ============================================================

# 故障原因模板：weight 是**知识库经验权重**（同类设备故障的常见程度），不是「本次故障是该原因的概率」。
# 拿得到设备台账时会用设备自身数据（投用年限、维保、最近上报）调整这些权重，并标注 basis。
_FAULT_CAUSE_TEMPLATES = [
    {
        "cause": "设备老化",
        "weight": 0.35,
        "description": "设备使用年限较长，内部元件老化导致故障",
        "knowledge": "同类设备随投用年限增长，元件老化引起的故障占比明显上升",
    },
    {
        "cause": "环境因素",
        "weight": 0.25,
        "description": "环境温湿度、灰尘等影响设备正常运行",
        "knowledge": "安装环境潮湿、积尘会加速元件失效",
    },
    {
        "cause": "供电异常",
        "weight": 0.2,
        "description": "电源电压不稳定或供电线路问题",
        "knowledge": "供电波动与接线松动是消防设备常见故障源",
    },
    {
        "cause": "维护不到位",
        "weight": 0.15,
        "description": "日常维护保养不及时，导致设备性能下降",
        "knowledge": "超过维保周期的设备故障率高于按周期维保的设备",
    },
    {
        "cause": "其他原因",
        "weight": 0.05,
        "description": "需进一步检测确定具体原因",
        "knowledge": "少数故障需现场检测才能定位",
    },
]


def _device_signals(device: Device) -> Dict[str, Any]:
    """从设备台账里取出可用于判断故障原因的真实信号。"""
    today = datetime.now().date()
    return {
        "ageYears": round((today - device.install_date).days / 365.0, 1) if device.install_date else None,
        "daysSinceMaintenance": (today - device.last_maintenance).days if device.last_maintenance else None,
        "maintenanceOverdue": bool(device.next_maintenance and device.next_maintenance < today),
        "daysSinceSeen": round((datetime.utcnow() - device.last_seen_at).total_seconds() / 86400, 1)
        if device.last_seen_at else None,
    }


def _cause_weight_adjustments(signals: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """按真实信号给出各原因的权重增减（确定性规则，命中哪条就记哪条证据）。"""
    adjustments: Dict[str, Dict[str, Any]] = {}

    age = signals.get("ageYears")
    since_maintenance = signals.get("daysSinceMaintenance")
    aging_delta, aging_evidence = 0.0, []
    if age is not None:
        if age >= 8:
            aging_delta += 0.25
        elif age >= 5:
            aging_delta += 0.15
        aging_evidence.append(f"已投用 {age} 年")
    if since_maintenance is not None and since_maintenance >= 365:
        aging_delta += 0.10
    if aging_evidence or aging_delta:
        adjustments["设备老化"] = {"delta": aging_delta, "evidence": aging_evidence}

    maintenance_delta, maintenance_evidence = 0.0, []
    if signals.get("maintenanceOverdue"):
        maintenance_delta += 0.25
        maintenance_evidence.append("已超过计划维保日期")
    if since_maintenance is not None:
        maintenance_evidence.append(f"距上次维保 {since_maintenance} 天")
        if since_maintenance >= 180:
            maintenance_delta += 0.15
    if maintenance_evidence:
        adjustments["维护不到位"] = {"delta": maintenance_delta, "evidence": maintenance_evidence}

    days_since_seen = signals.get("daysSinceSeen")
    if days_since_seen is not None and days_since_seen >= 1:
        adjustments["供电异常"] = {
            "delta": 0.15,
            "evidence": [f"设备已 {days_since_seen} 天未上报数据（可能断电或通讯中断）"],
        }
    return adjustments


def diagnose_device_fault(device_data: Dict[str, Any], device: Optional[Device] = None) -> Dict[str, Any]:
    """设备故障诊断

    **权重的口径**：`fault_causes[].weight` 是参考权重，不是「本次故障是该原因的概率」——
    系统里没有故障样本可供训练。它的来源分两种，每条原因都会用 `basis` 标明：

    - `basis="device_data"`：拿得到设备台账（`device_id` 属于本租户）时，用设备的真实属性
      （投用年限 / 距上次维保天数 / 是否超期未维保 / 最近上报时间）调整权重并归一化，
      `evidence` 里给出具体数字；
    - `basis="knowledge_base"`：拿不到台账时退回知识库先验权重，`evidence` 明确写成「知识库经验：…」。

    改造前这里有两个问题：百分比是写死的、却当作本次诊断的概率展示；`evidence` 还会断言
    「设备已使用超过5年」「安装环境通风不良」这类**我们并不知道的事实**。
    """
    device_type = device_data.get("device_type", "")
    status = device_data.get("status", "故障")
    device_name = device_data.get("device_name", device_type)

    signals = _device_signals(device) if device else {}
    adjustments = _cause_weight_adjustments(signals) if device else {}

    weights = {item["cause"]: item["weight"] for item in _FAULT_CAUSE_TEMPLATES}
    for cause, adjustment in adjustments.items():
        weights[cause] = weights.get(cause, 0) + adjustment["delta"]
    total = sum(weights.values()) or 1.0

    fault_causes = []
    for item in _FAULT_CAUSE_TEMPLATES:
        adjustment = adjustments.get(item["cause"])
        evidence = (adjustment or {}).get("evidence") or [f"知识库经验：{item['knowledge']}"]
        fault_causes.append({
            "cause": item["cause"],
            "weight": round(weights[item["cause"]] / total, 2),
            "description": item["description"],
            "evidence": evidence,
            "basis": "device_data" if adjustment else "knowledge_base",
        })
    fault_causes.sort(key=lambda item: item["weight"], reverse=True)

    repair_suggestions = [
        {
            "priority": 1,
            "action": "现场检查确认",
            "detail": "安排技术人员现场检查，确认故障现象和范围",
            "estimated_time": "30分钟",
        },
        {
            "priority": 2,
            "action": "清洁保养",
            "detail": "对设备进行清洁除尘，检查接线端子紧固情况",
            "estimated_time": "1小时",
        },
        {
            "priority": 3,
            "action": "功能测试",
            "detail": "逐项测试设备各项功能，定位故障模块",
            "estimated_time": "2小时",
        },
        {
            "priority": 4,
            "action": "维修更换",
            "detail": "对故障部件进行维修或更换备品备件",
            "estimated_time": "2-4小时",
        },
    ]

    maintenance_tips = [
        "建议每月进行一次设备巡检",
        "每季度进行一次全面功能测试",
        "保持设备安装环境清洁干燥",
        "建立设备维护档案，记录每次维修情况",
        "重要设备建议备有备品备件",
    ]
    if signals.get("maintenanceOverdue"):
        maintenance_tips.insert(0, "该设备已超过计划维保日期，请优先安排维保")

    return {
        "device_status": status,
        "device_signals": signals,
        "fault_causes": fault_causes,
        "most_likely_cause": fault_causes[0]["cause"],
        "weight_basis": "device_data" if adjustments else "knowledge_base",
        "weight_note": (
            "weight 为参考权重："
            + ("按该设备台账数据（投用年限 / 维保情况 / 最近上报）调整后归一化，非故障概率"
               if adjustments else "取自知识库经验，未接入设备台账，非故障概率")
        ),
        "repair_suggestions": repair_suggestions,
        "maintenance_tips": maintenance_tips,
        "estimated_repair_time": "2-4小时",
        # 「置信度」= 输入信息完整度（不是模型概率）
        "confidence": _data_completeness(
            device_data, ("device_type", "device_name", "status", "building_name")
        ),
    }


# ============================================================
# 5. 每日安全简报
# ============================================================

def _parse_hazard_names(raw: Any) -> List[str]:
    """解析巡检记录里 JSON 文本形态的隐患名（兼容 ["明火"] 与 [{name/type:...}] 两种形态）。"""
    try:
        items = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(items, list):
        return []
    names: List[str] = []
    for item in items:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("type") or item.get("name") or item.get("hazard_name") or "").strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


def _severity_bucket(severity: str) -> str:
    severity = (severity or "").lower()
    if severity in ("critical", "high", "medium", "low"):
        return severity
    return "low"


def generate_daily_brief(db: Session, tenant_id: int, date_str: Optional[str] = None) -> Dict[str, Any]:
    """每日安全简报（**全部来自真实表**）

    改造前：告警数、严重/高/中/低各级数量、处置数、巡检数、隐患数、7 日趋势全是 `random.randint`，
    「今日重点关注区域」还写死了「1号办公楼 / 地下车库 / 消防水泵房」。
    现在按「指定日期（默认昨天，本地时区）」统计该租户的真实数据；没有数据就如实显示 0 与空列表。

    口径说明：告警的「已处置 / 待处理」用的是**当前状态**，不是当日快照
    （库里只存当前状态，没有状态变更历史），因此跨天回看时该数字是「现在的状态」。
    """
    target = parse_date(date_str) or (datetime.now().date() - timedelta(days=1))
    day_start, day_end = local_day_bounds_utc(target)

    alerts = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.created_at >= day_start,
        AlertRecord.created_at < day_end,
        AlertRecord.merged_into_id.is_(None),
    ).all()

    buckets = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    resolved_count = 0
    for alert in alerts:
        buckets[_severity_bucket(alert.severity)] += 1
        if alert.status == "resolved":
            resolved_count += 1
    alert_count = len(alerts)
    pending_count = alert_count - resolved_count

    inspections = db.query(InspectionRecord).filter(
        InspectionRecord.tenant_id == tenant_id,
        InspectionRecord.created_at >= day_start,
        InspectionRecord.created_at < day_end,
    ).all()
    inspection_count = len(inspections)
    hazard_found = sum(len(_parse_hazard_names(record.hazards)) for record in inspections)

    summary_text = (
        f"（{target.isoformat()}）消防安全总体态势"
        f"{'较为严峻' if buckets['critical'] else '平稳'}。"
        f"共发生各类告警{alert_count}起，"
        f"其中严重告警{buckets['critical']}起、高级告警{buckets['high']}起、"
        f"中级告警{buckets['medium']}起、低级告警{buckets['low']}起。"
        f"已处置{resolved_count}起，处置率"
        f"{round(resolved_count / alert_count * 100, 1) if alert_count else 0}%（按当前状态统计）。"
        f"完成巡检{inspection_count}次，发现隐患{hazard_found}项。"
    )

    key_highlights = []
    if buckets["critical"] > 0:
        key_highlights.append({
            "type": "danger",
            "content": f"{target.isoformat()} 发生{buckets['critical']}起严重告警，需重点关注",
        })
    if pending_count > 3:
        key_highlights.append({
            "type": "warning",
            "content": f"当日告警中尚有{pending_count}起未处置，建议尽快处理",
        })
    if hazard_found > 5:
        key_highlights.append({
            "type": "warning",
            "content": f"当日巡检发现{hazard_found}项隐患，需加快整改",
        })
    if not key_highlights:
        key_highlights.append({
            "type": "success",
            "content": f"{target.isoformat()} 无严重告警，当日数据如上",
        })

    # 近 7 日趋势：逐日真实告警数（截止到目标日期）
    alarm_trend = []
    for offset in range(6, -1, -1):
        day = target - timedelta(days=offset)
        start, end = local_day_bounds_utc(day)
        rows = db.query(AlertRecord).filter(
            AlertRecord.tenant_id == tenant_id,
            AlertRecord.created_at >= start,
            AlertRecord.created_at < end,
            AlertRecord.merged_into_id.is_(None),
        ).all()
        alarm_trend.append({
            "date": day.strftime("%m/%d"),
            "count": len(rows),
            "critical": sum(1 for row in rows if _severity_bucket(row.severity) == "critical"),
        })

    today_focus = _build_daily_focus(db, tenant_id, target)

    return {
        "date": target.isoformat(),
        "summary": summary_text,
        "key_highlights": key_highlights,
        "alert_stats": {
            "total": alert_count,
            "critical": buckets["critical"],
            "high": buckets["high"],
            "medium": buckets["medium"],
            "low": buckets["low"],
            "resolved": resolved_count,
            "pending": pending_count,
        },
        "inspection_stats": {
            "inspection_count": inspection_count,
            "hazard_found": hazard_found,
        },
        "alarm_trend": alarm_trend,
        "today_focus": today_focus,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "database",
        "note": "告警的「已处置 / 待处理」为当前状态，非当日快照（库中未保存状态变更历史）",
    }


def _build_daily_focus(db: Session, tenant_id: int, target: date) -> List[Dict[str, Any]]:
    """重点关注区域：由真实数据推导（近 7 天告警最多的区域 + 在该日之前就已逾期的工单）。

    没有数据就返回空列表，不再写死「1号办公楼 / 地下车库」。
    逾期工单限定在「目标日结束前就已逾期」，这样看历史某天的简报时，
    不会把今天才逾期的工单算进去。
    """
    window_start, _ = local_day_bounds_utc(target - timedelta(days=6))
    _, window_end = local_day_bounds_utc(target)
    recent_alerts = db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.created_at >= window_start,
        AlertRecord.created_at < window_end,
        AlertRecord.merged_into_id.is_(None),
    ).all()

    alert_stats: Dict[str, Dict[str, int]] = {}
    for alert in recent_alerts:
        name = alert.building_name or alert.location or "未标注区域"
        item = alert_stats.setdefault(name, {"total": 0, "critical": 0, "pending": 0})
        item["total"] += 1
        if _severity_bucket(alert.severity) == "critical":
            item["critical"] += 1
        if alert.status != "resolved":
            item["pending"] += 1

    focus: List[Dict[str, Any]] = []
    for name, item in sorted(alert_stats.items(), key=lambda kv: kv[1]["total"], reverse=True)[:3]:
        focus.append({
            "area": name,
            "reason": f"近 7 天告警{item['total']}起（严重{item['critical']}起，未处置{item['pending']}起）",
            "level": "high" if item["critical"] else "medium",
        })

    overdue = db.query(FaultTicket).filter(
        FaultTicket.tenant_id == tenant_id,
        FaultTicket.deadline.isnot(None),
        FaultTicket.deadline < window_end,
        FaultTicket.status.notin_(CLOSED_TICKET_STATUSES),
    ).all()
    overdue_stats: Dict[str, int] = {}
    for ticket in overdue:
        name = ticket.building_name or ticket.location or "未标注区域"
        overdue_stats[name] = overdue_stats.get(name, 0) + 1

    # 与已有条目合并，而不是丢掉：同一个区域既有告警又有逾期工单时，两条信息都要留下
    for name, count in sorted(overdue_stats.items(), key=lambda kv: kv[1], reverse=True)[:2]:
        existing = next((item for item in focus if item["area"] == name), None)
        if existing:
            existing["reason"] += f"；另有{count} 张工单已逾期未闭环"
            existing["level"] = "high"
        else:
            focus.append({
                "area": name,
                "reason": f"{count} 张工单已逾期未闭环，需现场复查",
                "level": "high",
            })
    return focus


# ============================================================
# 6. 智能告警聚合分析
# ============================================================

def analyze_alert_correlation(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    智能告警聚合分析
    判断多个告警是否存在关联，识别连锁反应
    """
    if len(alerts) < 2:
        return {
            "correlation_found": False,
            "groups": [],
            "summary": "告警数量不足，未发现明显关联",
        }
    
    building_groups = {}
    for alert in alerts:
        building = alert.get("building_name", "未知")
        if building not in building_groups:
            building_groups[building] = []
        building_groups[building].append(alert)
    
    correlated_groups = []
    for building, building_alerts in building_groups.items():
        if len(building_alerts) >= 2:
            types = [a.get("alert_name", "") for a in building_alerts]
            
            is_correlated = len(building_alerts) >= 2
            correlation_type = "independent"
            correlation_reason = ""
            risk_level = "medium"
            
            smoke_types = ["烟雾", "smoke", "烟感", "火灾"]
            temp_types = ["温度", "temperature", "温感", "过热"]
            
            has_smoke = any(any(t in s for t in smoke_types) for s in types)
            has_temp = any(any(t in s for t in temp_types) for s in types)
            
            if has_smoke and has_temp:
                correlation_type = "fire_suspected"
                correlation_reason = "同一区域同时出现烟雾和温度异常告警，疑似火灾征兆，需立即核实！"
                risk_level = "critical"
            elif len(building_alerts) >= 3:
                correlation_type = "clustered"
                correlation_reason = f"同一区域短时间内出现{len(building_alerts)}起告警，可能存在系统性问题"
                risk_level = "high"
            else:
                correlation_type = "proximity"
                correlation_reason = "同一区域出现多起告警，建议综合排查"
                risk_level = "medium"
            
            correlated_groups.append({
                "group_id": f"GROUP_{len(correlated_groups)+1:03d}",
                "building": building,
                "alerts": building_alerts,
                "alert_count": len(building_alerts),
                "correlation_type": correlation_type,
                "correlation_reason": correlation_reason,
                "risk_level": risk_level,
                "suggested_action": (
                    "立即安排人员现场核查确认情况" if risk_level == "critical"
                    else "优先安排人员综合排查"
                ),
            })
    
    if correlated_groups:
        summary = f"共发现{len(correlated_groups)}组关联告警，其中"
        critical_groups = sum(1 for g in correlated_groups if g["risk_level"] == "critical")
        high_groups = sum(1 for g in correlated_groups if g["risk_level"] == "high")
        if critical_groups:
            summary += f"{critical_groups}组疑似火灾征兆，"
        if high_groups:
            summary += f"{high_groups}组告警集中，"
        summary += "建议优先处理。"
    else:
        summary = "未发现明显关联的告警组，各告警相对独立。"
    
    return {
        "correlation_found": len(correlated_groups) > 0,
        "groups": correlated_groups,
        "total_groups": len(correlated_groups),
        "summary": summary,
    }


# ============================================================
# 7. 知识经验沉淀
# ============================================================

# 从案例信息里能识别出的处置要点：命中哪条就输出哪条，并把触发它的原词写进依据。
# 一条都命中不了就返回空 —— 以前这里无条件给一条「接到告警后第一时间现场核实…」，
# 无论传进来的是什么案例都是同一句，那不是从案例里提取的经验。
_EXPERIENCE_RULES = [
    {
        "keywords": ("误报", "假警"),
        "tag": "误报识别",
        "title": "误报甄别要点",
        "content": "确认现场无火情后，先复核探测器灵敏度与环境干扰源，再决定清洁、调整阈值或更换探头。",
    },
    {
        "keywords": ("维修", "更换", "替换"),
        "tag": "设备维修",
        "title": "设备维修要点",
        "content": "维修或更换部件后应复测设备功能、确认不再重复告警，再走闭环。",
    },
    {
        "keywords": ("电气", "线路", "短路", "过载", "配电"),
        "tag": "电气安全",
        "title": "电气隐患排查要点",
        "content": "电气类隐患由专业人员排查线路，断电后再处置，整改完成后复查绝缘与负载情况。",
    },
    {
        "keywords": ("疏散", "通道", "堵塞", "占用"),
        "tag": "疏散通道",
        "title": "疏散通道整改要点",
        "content": "清空堵塞物后需确认通道净宽与安全出口可用，并明确日常巡查责任人防止复发。",
    },
]


def extract_experience_from_case(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """从处置案例中自动提取经验知识。

    只输出**有输入依据**的内容：处置要点由 `alert_type` / `result` / `process_description`
    里实际出现的词命中规则表得到，`basis` 写明是哪个词触发的；一条都没命中就返回空列表。
    """
    alert_type = case_data.get("alert_type", "")
    result = case_data.get("result", "")
    process_description = case_data.get("process_description", "")
    basis_text = f"{alert_type} {result} {process_description}"

    experience_tags = []
    best_practices = []
    for rule in _EXPERIENCE_RULES:
        hit = next((word for word in rule["keywords"] if word in basis_text), "")
        if not hit:
            continue
        experience_tags.append(rule["tag"])
        best_practices.append({
            "title": rule["title"],
            "content": rule["content"],
            "applicable": alert_type,
            "basis": f"案例信息中出现「{hit}」",
        })

    lessons = []
    if result == "误报":
        lessons.append(f"{alert_type}存在误报可能，需结合现场情况判断")

    return {
        "experience_id": f"EXP{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "source_case": case_data.get("id", ""),
        "experience_tags": experience_tags,
        "lessons_learned": lessons,
        "best_practices": best_practices,
        "summary": (
            f"从{alert_type}处置案例中提取的经验知识"
            if experience_tags or lessons
            else "案例信息不足，未提取到可归纳的经验"
        ),
        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def recommend_similar_knowledge(query: str, knowledge_list: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按查询内容给知识条目打分排序（只负责排序，不自己造条目）。

    改造前这个函数内置了 7 条写死的假条目（`KB001 烟感探测器工作原理与维护` 之类），
    而接口调用时又没传 `knowledge_list`，于是不管问什么都返回同一批编出来的内容。
    现在条目必须由调用方从真实知识库（运行时库 `rag_entries`）取，取不到就返回空列表。
    """
    query_lower = (query or "").strip().lower()
    if not query_lower:
        return []

    scored = []
    for item in knowledge_list:
        score = 0
        if query_lower in str(item.get("title") or "").lower():
            score += 50
        # 真实知识条目的关键词存在 keywords 字段（逗号/顿号分隔的文本）
        for keyword in _entry_keywords(item):
            keyword_lower = keyword.lower()
            if keyword_lower in query_lower or query_lower in keyword_lower:
                score += 30
        if score > 0:
            scored.append({**item, "relevance_score": score})

    scored.sort(key=lambda x: -x["relevance_score"])
    return scored[:5]


def _entry_keywords(item: Dict[str, Any]) -> List[str]:
    """拆出知识条目的关键词（`keywords` 是「电气火灾,切断电源」这类文本）。"""
    raw = str(item.get("keywords") or "")
    for separator in ("，", "、", "；", ";"):
        raw = raw.replace(separator, ",")
    return [part.strip() for part in raw.split(",") if part.strip()]


# ============================================================
# 8. 数据自然语言查询
# ============================================================

def answer_natural_language_query(question: str, db: Session, tenant_id: int) -> Dict[str, Any]:
    """自然语言数据查询（**答案全部来自真实库**）

    改造前这里每个分支都是 `random.randint`：`今日共发生{count}起告警`、
    `设备在线率{random}%`、`系统累计告警{random}起`……换个说法问同一个问题，答案就变了。
    现在每个分支都按本租户真实数据统计；查不到就如实说「没有数据」，不再编一个数字。

    `confidence` 是**数据覆盖度**（问题命中的统计项是否都取到了数据），不是模型概率。
    """
    question_lower = (question or "").lower()
    result_data: Dict[str, Any] = {}
    chart_type = None
    coverage = 0  # 命中的统计项数，用于给出数据覆盖度而不是随机置信度

    if "告警" in question_lower or "报警" in question_lower:
        if "今天" in question_lower or "今日" in question_lower:
            start, end = local_day_bounds_utc(datetime.now().date())
            rows = _alerts_between(db, tenant_id, start, end)
            critical = sum(1 for row in rows if _severity_bucket(row.severity) == "critical")
            high = sum(1 for row in rows if _severity_bucket(row.severity) == "high")
            pending = sum(1 for row in rows if row.status in OPEN_ALERT_STATUSES)
            answer_text = (
                f"今日共发生{len(rows)}起告警，其中严重告警{critical}起、高级告警{high}起，"
                f"当前未处置{pending}起。"
            )
            result_data = {"today_count": len(rows), "critical": critical,
                           "high": high, "pending": pending}
            coverage = 1
        elif "本周" in question_lower:
            today = datetime.now().date()
            # 「近 7 天」= (today-6 .. today)，「前 7 天」= (today-13 .. today-7)
            this_start = local_day_bounds_utc(today - timedelta(days=6))[0]
            this_end = local_day_bounds_utc(today)[1]
            last_start = local_day_bounds_utc(today - timedelta(days=13))[0]
            last_end = local_day_bounds_utc(today - timedelta(days=7))[1]
            this_week = _alerts_between(db, tenant_id, this_start, this_end)
            last_week = _alerts_between(db, tenant_id, last_start, last_end)
            change = len(this_week) - len(last_week)
            direction = "上升" if change > 0 else ("下降" if change < 0 else "持平")
            rate = round(abs(change) / len(last_week) * 100, 1) if last_week else None
            answer_text = (
                f"近 7 天共发生{len(this_week)}起告警，"
                f"前 7 天为{len(last_week)}起，环比{direction}"
                f"{f'{rate}%' if rate is not None else '（前 7 天无数据，无法计算比例）'}。"
            )
            result_data = {"week_count": len(this_week), "last_week_count": len(last_week)}
            coverage = 1
        elif "最多" in question_lower:
            start = local_day_bounds_utc(datetime.now().date() - timedelta(days=29))[0]
            rows = _alerts_between(db, tenant_id, start, datetime.utcnow())
            stats: Dict[str, int] = {}
            for row in rows:
                name = row.building_name or row.location or "未标注区域"
                stats[name] = stats.get(name, 0) + 1
            if stats:
                top_name, top_count = max(stats.items(), key=lambda kv: kv[1])
                answer_text = (
                    f"近 30 天告警最多的区域是{top_name}，共{top_count}起"
                    f"（统计范围：本租户全部告警）。"
                )
                result_data = {"top_building": top_name, "count": top_count}
                chart_type = "bar"
                coverage = 1
            else:
                answer_text = "近 30 天本租户没有告警记录。"
                result_data = {"top_building": None, "count": 0}
        else:
            rows = db.query(AlertRecord).filter(
                AlertRecord.tenant_id == tenant_id, AlertRecord.merged_into_id.is_(None)
            ).all()
            resolved = sum(1 for row in rows if row.status == "resolved")
            answer_text = (
                f"本租户累计告警{len(rows)}起，其中已处置{resolved}起，"
                f"处置率{round(resolved / len(rows) * 100, 1) if rows else 0}%。"
            )
            result_data = {"total": len(rows), "resolved": resolved}
            chart_type = "pie"
            coverage = 1

    elif "设备" in question_lower:
        devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
        if "在线" in question_lower:
            online = [d for d in devices if (d.status or "") in ("正常", "在线", "online")]
            offline = [d for d in devices if (d.status or "") in ("离线", "offline")]
            rate = round(len(online) / len(devices) * 100, 1) if devices else 0
            answer_text = (
                f"当前设备在线率{rate}%，共{len(online)}台在线、{len(offline)}台离线"
                f"（设备总数{len(devices)}台）。"
            )
            result_data = {"online_rate": rate, "online": len(online),
                           "offline": len(offline), "total": len(devices)}
            coverage = 1
        elif "类型" in question_lower or "种类" in question_lower:
            stats: Dict[str, int] = {}
            for device in devices:
                name = device.device_type or "未分类"
                stats[name] = stats.get(name, 0) + 1
            if stats:
                top = sorted(stats.items(), key=lambda kv: kv[1], reverse=True)[:5]
                answer_text = "设备类型分布：" + "、".join(f"{name} {count}台" for name, count in top) + "。"
                result_data = {"types": dict(top)}
                chart_type = "pie"
                coverage = 1
            else:
                answer_text = "本租户还没有接入设备。"
                result_data = {"types": {}}
        else:
            answer_text = f"本租户共接入{len(devices)}台设备。"
            result_data = {"total": len(devices)}
            coverage = 1

    elif "隐患" in question_lower or "风险" in question_lower:
        start = local_day_bounds_utc(datetime.now().date() - timedelta(days=29))[0]
        records = db.query(InspectionRecord).filter(
            InspectionRecord.tenant_id == tenant_id,
            InspectionRecord.created_at >= start,
        ).all()
        hazard_names: List[str] = []
        for record in records:
            hazard_names.extend(_parse_hazard_names(record.hazards))
        high_risk = [r for r in records if (r.risk_level or "") in ("高风险", "严重风险")]
        answer_text = (
            f"近 30 天共 {len(records)} 次巡检、发现 {len(hazard_names)} 项隐患，"
            f"其中高风险及以上巡检记录 {len(high_risk)} 条。"
        )
        result_data = {"hazard_count": len(hazard_names),
                       "inspection_count": len(records), "high_risk_count": len(high_risk)}
        chart_type = "bar"
        coverage = 1

    elif "建筑" in question_lower or "楼" in question_lower:
        buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()
        names = [b.building_name for b in buildings[:5]]
        answer_text = (
            f"本租户共管理{len(buildings)}栋建筑"
            + (f"，包括{('、'.join(names))}等。" if names else "。")
        )
        result_data = {"building_count": len(buildings)}
        coverage = 1

    else:
        answer_text = "我可以为您查询告警统计、设备状态、隐患情况、建筑信息等数据。请告诉我您想了解什么？"
        coverage = 0

    related_questions = [
        "今日告警有多少？",
        "哪个区域告警最多？",
        "设备在线率是多少？",
        "当前有多少隐患？",
    ]

    return {
        "question": question,
        "answer_type": "guidance" if coverage == 0 else "statistics",
        "answer_text": answer_text,
        "result_data": result_data,
        "chart_type": chart_type,
        "related_questions": related_questions,
        # 数据覆盖度：这一问涉及的统计项是否都从库里取到了数据（不是模型概率）
        "confidence": 1.0 if coverage else 0.5,
        "data_source": "database",
    }


def _alerts_between(db: Session, tenant_id: int, start: datetime, end: datetime) -> List[AlertRecord]:
    """取区间内本租户未合并的告警（闭开区间 [start, end)）。"""
    return db.query(AlertRecord).filter(
        AlertRecord.tenant_id == tenant_id,
        AlertRecord.created_at >= start,
        AlertRecord.created_at < end,
        AlertRecord.merged_into_id.is_(None),
    ).all()
