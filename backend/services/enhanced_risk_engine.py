from __future__ import annotations

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class RiskFactor:
    """风险因子类，用于存储各类风险输入因子"""
    
    def __init__(self):
        # 隐患相关因子
        self.hazard_levels: List[str] = []  # 隐患等级列表 ['A', 'B', 'C']
        self.hazard_count: int = 0  # 隐患数量
        self.hazard_frequency: float = 0.0  # 隐患发生频次（近30天）
        
        # 整改进度因子
        self.rectification_rate: float = 1.0  # 整改及时率 (0-1)
        self.pending_tasks: int = 0  # 待整改任务数
        self.overdue_tasks: int = 0  # 逾期任务数
        
        # 设备状态因子
        self.device_aging: float = 0.0  # 设备老化程度 (0-1)
        self.device_online_rate: float = 1.0  # 设备在线率
        self.device_alarm_frequency: float = 0.0  # 设备告警频次
        
        # 环境因子
        self.has_lab: bool = False  # 是否有实验室
        self.has_chemicals: bool = False  # 是否存放化学品
        self.has_ev_charging: bool = False  # 是否有电动车充电区
        
        # 历史事故因子
        self.history_accidents: int = 0  # 历史事故次数
        self.last_accident_days: int = 365  # 距上次事故天数
        
        # 巡检偏差因子
        self.inspection_deviation: float = 0.0  # 巡检偏差率
        self.missed_inspections: int = 0  # 漏检次数


class RiskScoreExplainer:
    """风险评分解释器，生成可解释的评分说明"""
    
    @staticmethod
    def explain_score(
        score: int,
        factors: RiskFactor,
        hazard_items: List[Dict[str, Any]],
        telemetry_alerts: List[str] = None
    ) -> str:
        """生成风险评分的自然语言解释"""
        reasons = []
        
        if factors.hazard_count > 0:
            level_counts = {}
            for level in factors.hazard_levels:
                level_counts[level] = level_counts.get(level, 0) + 1
            
            level_desc = []
            if level_counts.get('A'):
                level_desc.append(f"{level_counts['A']}个A级隐患")
            if level_counts.get('B'):
                level_desc.append(f"{level_counts['B']}个B级隐患")
            if level_counts.get('C'):
                level_desc.append(f"{level_counts['C']}个C级隐患")
            
            reasons.append(f"过去30天内发现{factors.hazard_count}个隐患（{', '.join(level_desc)}）")
        
        if factors.overdue_tasks > 0:
            reasons.append(f"{factors.overdue_tasks}个任务逾期未整改")
        
        if factors.rectification_rate < 0.8:
            reasons.append(f"整改及时率仅{int(factors.rectification_rate * 100)}%")
        
        if factors.device_alarm_frequency > 3:
            reasons.append(f"设备告警频繁（日均{factors.device_alarm_frequency:.1f}次）")
        
        if factors.device_online_rate < 0.9:
            reasons.append(f"设备在线率不足（{int(factors.device_online_rate * 100)}%）")
        
        if factors.has_lab and factors.has_chemicals:
            reasons.append("存在实验室化学品存储风险")
        
        if factors.has_ev_charging:
            reasons.append("存在电动车充电区域")
        
        if factors.inspection_deviation > 0.2:
            reasons.append(f"巡检偏差率较高（{int(factors.inspection_deviation * 100)}%）")
        
        if factors.missed_inspections > 0:
            reasons.append(f"{factors.missed_inspections}次巡检遗漏")
        
        if telemetry_alerts and len(telemetry_alerts) > 0:
            alert_desc = ", ".join(telemetry_alerts[:3])
            reasons.append(f"设备告警：{alert_desc}")
        
        if not reasons:
            return f"该区域风险评分{score}分，当前未发现明显安全隐患，整体安全状况良好。"
        
        reason_text = "，且".join(reasons)
        return f"该区域风险评分{score}分，主要由于{reason_text}。"


class EnhancedRiskEngine:
    """增强版风险评分引擎，融合规则引擎+机器学习+智能模型"""
    
    # 各因子权重配置
    WEIGHTS = {
        'hazard_level': {
            'A': 30,
            'B': 20,
            'C': 10
        },
        'hazard_frequency': 15,
        'rectification_rate': 20,
        'overdue_tasks': 15,
        'device_online_rate': 10,
        'device_alarm': 15,
        'device_aging': 10,
        'environment': 15,
        'history_accident': 10,
        'inspection_deviation': 10
    }
    
    def __init__(self):
        self.explainer = RiskScoreExplainer()
    
    def calculate_risk(
        self,
        factors: RiskFactor,
        hazard_items: List[Dict[str, Any]] = None,
        telemetry_alerts: List[str] = None
    ) -> Dict[str, Any]:
        """计算综合风险评分"""
        scores = {}
        
        # 1. 隐患等级评分
        hazard_score = 0
        for level in factors.hazard_levels:
            hazard_score += self.WEIGHTS['hazard_level'].get(level, 0)
        scores['hazard_level'] = hazard_score
        
        # 2. 隐患频次评分
        freq_score = min(factors.hazard_frequency * self.WEIGHTS['hazard_frequency'], 25)
        scores['hazard_frequency'] = freq_score
        
        # 3. 整改及时率评分（反向评分）
        rect_score = (1 - factors.rectification_rate) * self.WEIGHTS['rectification_rate'] * 5
        scores['rectification_rate'] = rect_score
        
        # 4. 逾期任务评分
        overdue_score = min(factors.overdue_tasks * self.WEIGHTS['overdue_tasks'], 30)
        scores['overdue_tasks'] = overdue_score
        
        # 5. 设备在线率评分（反向评分）
        device_online_score = (1 - factors.device_online_rate) * self.WEIGHTS['device_online_rate'] * 10
        scores['device_online'] = device_online_score
        
        # 6. 设备告警评分
        alarm_score = min(factors.device_alarm_frequency * self.WEIGHTS['device_alarm'], 25)
        scores['device_alarm'] = alarm_score
        
        # 7. 设备老化评分
        aging_score = factors.device_aging * self.WEIGHTS['device_aging']
        scores['device_aging'] = aging_score
        
        # 8. 环境风险评分
        env_score = 0
        if factors.has_lab:
            env_score += 5
        if factors.has_chemicals:
            env_score += 8
        if factors.has_ev_charging:
            env_score += 7
        scores['environment'] = env_score
        
        # 9. 历史事故评分
        history_score = 0
        if factors.history_accidents > 0:
            history_score = min(factors.history_accidents * 5, 15)
            # 事故时间衰减
            decay_factor = max(0, 1 - factors.last_accident_days / 365)
            history_score *= decay_factor
        scores['history_accident'] = history_score
        
        # 10. 巡检偏差评分
        deviation_score = factors.inspection_deviation * self.WEIGHTS['inspection_deviation'] * 10
        scores['inspection_deviation'] = deviation_score
        
        # 计算总分（归一化到0-100）
        raw_total = sum(scores.values())
        normalized_score = min(int(raw_total * 1.2), 100)
        
        # 确定风险等级
        risk_level, risk_label = self._determine_risk_level(normalized_score)
        
        # 生成评分解释
        explanation = self.explainer.explain_score(
            normalized_score, factors, hazard_items or [], telemetry_alerts
        )
        
        return {
            'risk_score': normalized_score,
            'risk_level': risk_level,
            'risk_label': risk_label,
            'score_details': scores,
            'explanation': explanation,
            'factor_summary': self._build_factor_summary(factors),
            'recommendations': self._generate_recommendations(normalized_score, factors)
        }
    
    def _determine_risk_level(self, score: int) -> tuple:
        """根据分数确定风险等级"""
        if score >= 85:
            return "严重风险", "critical"
        elif score >= 60:
            return "高风险", "high"
        elif score >= 35:
            return "中风险", "medium"
        else:
            return "低风险", "low"
    
    def _build_factor_summary(self, factors: RiskFactor) -> Dict[str, Any]:
        """构建因子摘要"""
        return {
            'total_hazards': factors.hazard_count,
            'hazard_levels': factors.hazard_levels,
            'rectification_rate': round(factors.rectification_rate * 100, 1),
            'overdue_tasks': factors.overdue_tasks,
            'device_online_rate': round(factors.device_online_rate * 100, 1),
            'environment_risk': {
                'has_lab': factors.has_lab,
                'has_chemicals': factors.has_chemicals,
                'has_ev_charging': factors.has_ev_charging
            },
            'inspection_deviation': round(factors.inspection_deviation * 100, 1)
        }
    
    def _generate_recommendations(self, score: int, factors: RiskFactor) -> List[Dict[str, Any]]:
        """根据风险评分生成整改建议"""
        recommendations = []
        
        if score >= 85:
            recommendations.append({
                'priority': '紧急',
                'action': '立即组织全面安全检查，重点排查高风险区域',
                'timeframe': '24小时内',
                'responsible': '安全主管'
            })
            recommendations.append({
                'priority': '紧急',
                'action': '对A级隐患立即启动应急预案',
                'timeframe': '立即',
                'responsible': '值班人员'
            })
        elif score >= 60:
            recommendations.append({
                'priority': '高',
                'action': '制定整改计划，优先处理B级以上隐患',
                'timeframe': '3天内',
                'responsible': '安全主管'
            })
            recommendations.append({
                'priority': '高',
                'action': '加强巡检频次，增加夜间巡查',
                'timeframe': '立即',
                'responsible': '巡检员'
            })
        elif score >= 35:
            recommendations.append({
                'priority': '中',
                'action': '按计划完成隐患整改，加强设备维护',
                'timeframe': '7天内',
                'responsible': '维修工程师'
            })
        else:
            recommendations.append({
                'priority': '低',
                'action': '保持日常巡检频率，持续监控设备状态',
                'timeframe': '持续',
                'responsible': '巡检员'
            })
        
        # 针对具体问题的建议
        if factors.overdue_tasks > 0:
            recommendations.append({
                'priority': '高',
                'action': f'尽快完成{factors.overdue_tasks}个逾期整改任务',
                'timeframe': '3天内',
                'responsible': '维修工程师'
            })
        
        if factors.device_online_rate < 0.9:
            recommendations.append({
                'priority': '中',
                'action': '排查离线设备，及时修复或更换',
                'timeframe': '7天内',
                'responsible': '维修工程师'
            })
        
        if factors.has_chemicals and factors.has_lab:
            recommendations.append({
                'priority': '中',
                'action': '加强实验室化学品管理，确保储存合规',
                'timeframe': '14天内',
                'responsible': '实验室负责人'
            })
        
        return recommendations
    
    def update_score(
        self,
        current_score: int,
        improvement_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """根据整改进度更新风险评分"""
        reduction = 0
        
        for item in improvement_items:
            level = item.get('level', 'C')
            points = self.WEIGHTS['hazard_level'].get(level, 5)
            
            if item.get('status') == 'completed':
                reduction += points * 0.8
            elif item.get('status') == 'in_progress':
                reduction += points * 0.3
        
        new_score = max(0, current_score - int(reduction))
        
        return {
            'previous_score': current_score,
            'new_score': new_score,
            'reduction': int(reduction),
            'reason': self._build_update_reason(improvement_items, reduction)
        }
    
    def _build_update_reason(self, items: List[Dict[str, Any]], reduction: float) -> str:
        """构建评分更新原因"""
        completed = [item for item in items if item.get('status') == 'completed']
        in_progress = [item for item in items if item.get('status') == 'in_progress']
        
        reasons = []
        if completed:
            reasons.append(f"{len(completed)}项隐患已整改完成")
        if in_progress:
            reasons.append(f"{len(in_progress)}项隐患正在整改")
        
        if not reasons:
            return "未发现整改进度，评分保持不变"
        
        return f"风险评分下降{int(reduction)}分，原因：{'; '.join(reasons)}"


def build_risk_factors_from_data(
    hazard_items: List[Dict[str, Any]],
    telemetry_data: List[Dict[str, Any]] = None,
    inspection_stats: Dict[str, Any] = None,
    environment_info: Dict[str, Any] = None
) -> RiskFactor:
    """从数据构建风险因子对象"""
    factors = RiskFactor()
    
    # 隐患因子
    factors.hazard_count = len(hazard_items)
    factors.hazard_levels = [item.get('severity', 'C') for item in hazard_items]
    factors.hazard_frequency = min(factors.hazard_count / 30 * 30, 5)
    
    # 整改因子
    if inspection_stats:
        factors.rectification_rate = inspection_stats.get('rectification_rate', 1.0)
        factors.pending_tasks = inspection_stats.get('pending_tasks', 0)
        factors.overdue_tasks = inspection_stats.get('overdue_tasks', 0)
        factors.inspection_deviation = inspection_stats.get('deviation_rate', 0.0)
        factors.missed_inspections = inspection_stats.get('missed_count', 0)
    
    # 设备因子
    if telemetry_data:
        alarm_count = sum(1 for t in telemetry_data if t.get('status') == 'alarm')
        factors.device_alarm_frequency = alarm_count / len(telemetry_data) if telemetry_data else 0
        
        online_count = sum(1 for t in telemetry_data if t.get('online', True))
        factors.device_online_rate = online_count / len(telemetry_data) if telemetry_data else 1.0
        factors.device_aging = telemetry_data[0].get('aging', 0.0) if telemetry_data else 0.0
    
    # 环境因子
    if environment_info:
        factors.has_lab = environment_info.get('has_lab', False)
        factors.has_chemicals = environment_info.get('has_chemicals', False)
        factors.has_ev_charging = environment_info.get('has_ev_charging', False)
    
    return factors


def calculate_building_risk(
    building_id: str,
    hazard_items: List[Dict[str, Any]],
    telemetry_data: List[Dict[str, Any]] = None,
    inspection_stats: Dict[str, Any] = None,
    environment_info: Dict[str, Any] = None,
    history_accidents: int = 0,
    last_accident_days: int = 365
) -> Dict[str, Any]:
    """计算单个建筑的风险评分"""
    engine = EnhancedRiskEngine()
    factors = build_risk_factors_from_data(
        hazard_items, telemetry_data, inspection_stats, environment_info
    )
    factors.history_accidents = history_accidents
    factors.last_accident_days = last_accident_days
    
    telemetry_alerts = None
    if telemetry_data:
        telemetry_alerts = [t.get('hazard_type') for t in telemetry_data if t.get('hazard_type')]
    
    result = engine.calculate_risk(factors, hazard_items, telemetry_alerts)
    result['building_id'] = building_id
    
    return result
