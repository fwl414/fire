"""建筑风险预测模型（scikit-learn）

改造前：「风险预测」是纯规则 —— 查表求和（`services/risk_engine.py`）+ 加权线性缩放
（`services/enhanced_risk_engine.py`），没有训练、没有模型文件、没有特征工程；
`/api/intelligence/analyze-*` 更是用 `random` 扰动出风险分。

现在用真实业务数据训练一个**可解释**的逻辑回归，回答一个能被验证的问题：

    某栋建筑在未来 7 天内，会不会出现严重告警（severity=critical/high）或告警升级？

- 样本：每栋建筑 × 每个观测点；观测窗口 = 观测点前 7 天，标签窗口 = 观测点后 7 天
- 特征：12 个，全部来自真实表（告警 / 工单 / 设备 / 巡检 / 遥测 / 维保）。
  温度、电量这类指标直接用原始极值，**不自造阈值** —— 阈值交给模型自己学
- 训练：StandardScaler + LogisticRegression(L2)，按时间切分回测（不能拿未来预测过去）
- 落盘：把标准化参数与系数导出为 JSON（不是 pickle）：可审计，也不存在
  「加载模型 = 反序列化执行任意对象」的风险
- 未训练时：预测接口如实回报「模型尚未训练」，不返回任何编造分数

已知局限（同样写在接口返回里，不藏着）：

1. 设备状态、工单状态没有历史快照，历史样本里只能用**当前快照**，会让历史样本偏保守
2. 样本完全来自本租户自身数据；样本量或正负分布不达标时直接拒绝训练，不「凑一个模型」
3. 标签是「严重告警 / 告警升级」这类可观测结果，不等于真实火灾——系统里没有事故结果表
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from database import AlertRecord, Building, Device, DeviceTelemetry, FaultTicket, InspectionRecord
from services.common_utils import logger

# 模型产物目录（生成物，不入库，见 .gitignore）
ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "risk_model.json")

WINDOW_DAYS = 7
DEFAULT_OBSERVATIONS = 8  # 每栋建筑取最近 N 个观测点（每周一个）
MIN_SAMPLES = 40
MIN_POSITIVE_SAMPLES = 4
MIN_NEGATIVE_SAMPLES = 4
TRAIN_RATIO = 0.7

# 严重告警：设备接入侧把 smoke+alarm 定为 critical，temperature+alarm 定为 high
SEVERE_SEVERITIES = ("critical", "high")
# 工单闭环状态（见 routers/workorder.py 的状态机）
CLOSED_TICKET_STATUSES = ("已完成", "已关闭", "已闭环")
OFFLINE_DEVICE_STATUSES = ("离线", "offline")

# (字段名, 中文名)。顺序即特征向量顺序，改动必须同时重训模型。
FEATURES: List[Tuple[str, str]] = [
    ("alerts_7d", "近 7 天告警数"),
    ("severe_alerts_7d", "近 7 天严重告警数"),
    ("max_repeat_7d", "告警最大重复次数"),
    ("open_tickets", "未闭环工单数"),
    ("overdue_tickets", "逾期未闭环工单数"),
    ("offline_device_ratio", "设备离线率"),
    ("device_avg_age_years", "设备平均已投用年数"),
    ("inspections_7d", "近 7 天巡检次数"),
    ("avg_inspection_risk_7d", "近 7 天巡检风险分均值"),
    ("max_temperature_7d", "近 7 天最高温度"),
    ("min_battery_7d", "近 7 天最低电量"),
    ("days_since_maintenance", "距上次维保天数"),
]
FEATURE_NAMES: List[str] = [name for name, _ in FEATURES]
FEATURE_LABELS: Dict[str, str] = dict(FEATURES)

LABEL_DEFINITION = (
    f"未来 {WINDOW_DAYS} 天内该建筑出现 severity∈{list(SEVERE_SEVERITIES)} 的告警，"
    "或已有告警被升级（escalated）"
)


# ---------------------------------------------------------------- 特征构建

class _BuildingHistory:
    """把一个租户在观测区间内的原始记录一次性读出来，之后在内存里按建筑/时间窗切。

    逐建筑、逐观测点去查库会变成 N×M 次查询；这里只读一次，切窗在 Python 里做。
    """

    def __init__(self, db: Session, tenant_id: int, start: datetime, end: datetime):
        devices = db.query(Device).filter(Device.tenant_id == tenant_id).all()
        self.devices_by_building: Dict[int, List[Device]] = {}
        self.device_building: Dict[int, int] = {}
        for device in devices:
            if not device.building_id:
                continue
            self.devices_by_building.setdefault(device.building_id, []).append(device)
            self.device_building[device.id] = device.building_id

        self.alerts = db.query(AlertRecord).filter(
            AlertRecord.tenant_id == tenant_id,
            AlertRecord.created_at >= start,
            AlertRecord.created_at <= end,
        ).all()

        # 工单/设备没有历史快照：用「创建时间落在区间内」的工单 + 当前状态（见模块 docstring 局限 1）
        self.tickets = db.query(FaultTicket).filter(
            FaultTicket.tenant_id == tenant_id,
            FaultTicket.created_at <= end,
        ).all()

        inspections = db.query(InspectionRecord).filter(
            InspectionRecord.tenant_id == tenant_id,
            InspectionRecord.created_at >= start,
            InspectionRecord.created_at <= end,
        ).all()
        self.inspections_by_building: Dict[int, List[InspectionRecord]] = {}
        for record in inspections:
            building_id = self.device_building.get(record.device_id)
            if building_id:
                self.inspections_by_building.setdefault(building_id, []).append(record)

        telemetry = db.query(DeviceTelemetry).filter(
            DeviceTelemetry.tenant_id == tenant_id,
            DeviceTelemetry.created_at >= start,
            DeviceTelemetry.created_at <= end,
        ).all()
        self.telemetry_by_building: Dict[int, List[DeviceTelemetry]] = {}
        for row in telemetry:
            building_id = self.device_building.get(row.device_id)
            if building_id:
                self.telemetry_by_building.setdefault(building_id, []).append(row)

    def features(self, building_id: int, observed_at: datetime) -> List[float]:
        """观测点当天的特征值：窗口为 (observed_at - 7d, observed_at]。"""
        window_start = observed_at - timedelta(days=WINDOW_DAYS)
        in_window = lambda ts: ts is not None and window_start < ts <= observed_at  # noqa: E731

        alerts = [a for a in self.alerts if a.building_id == building_id and in_window(a.created_at)]
        severe = [a for a in alerts if (a.severity or "").lower() in SEVERE_SEVERITIES]
        max_repeat = max((a.repeat_count or 1 for a in alerts), default=0)

        open_tickets = [
            t for t in self.tickets
            if t.building_id == building_id and t.status not in CLOSED_TICKET_STATUSES
        ]
        overdue = [t for t in open_tickets if t.deadline and t.deadline < observed_at]

        devices = self.devices_by_building.get(building_id, [])
        offline = [d for d in devices if d.status in OFFLINE_DEVICE_STATUSES]
        ages = [
            (observed_at.date() - d.install_date).days / 365.0
            for d in devices if d.install_date
        ]
        since_maintenance = [
            (observed_at.date() - d.last_maintenance).days
            for d in devices if d.last_maintenance
        ]

        inspections = self.inspections_by_building.get(building_id, [])
        risk_scores = [r.risk_score or 0 for r in inspections]

        telemetry = self.telemetry_by_building.get(building_id, [])
        temperatures = [t.temperature for t in telemetry if t.temperature is not None]
        batteries = [t.battery for t in telemetry if t.battery is not None]

        return [
            float(len(alerts)),
            float(len(severe)),
            float(max_repeat),
            float(len(open_tickets)),
            float(len(overdue)),
            (len(offline) / len(devices)) if devices else 0.0,
            (sum(ages) / len(ages)) if ages else 0.0,
            float(len(inspections)),
            (sum(risk_scores) / len(risk_scores)) if risk_scores else 0.0,
            max(temperatures) if temperatures else 0.0,
            min(batteries) if batteries else 0.0,
            (sum(since_maintenance) / len(since_maintenance)) if since_maintenance else 0.0,
        ]

    def label(self, building_id: int, observed_at: datetime) -> int:
        """标签窗口 = (observed_at, observed_at + 7d]：出现严重告警或被升级过即 1。"""
        label_end = observed_at + timedelta(days=WINDOW_DAYS)
        for alert in self.alerts:
            if alert.building_id != building_id:
                continue
            created = alert.created_at
            if created and observed_at < created <= label_end:
                if (alert.severity or "").lower() in SEVERE_SEVERITIES:
                    return 1
            escalated_at = alert.escalated_at
            if escalated_at and observed_at < escalated_at <= label_end:
                return 1
        return 0


def observation_points(now: Optional[datetime] = None, count: int = DEFAULT_OBSERVATIONS) -> List[datetime]:
    """最近 N 个观测点：从今天零点往前每 7 天一个（含今天）。"""
    now = now or datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return [today - timedelta(days=WINDOW_DAYS * index) for index in range(count)]


def build_dataset(
    db: Session,
    tenant_id: int,
    observations: int = DEFAULT_OBSERVATIONS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """构造监督学习数据集。

    返回 `{features, labels, sample_keys, observation_times, label_definition, skipped}`，
    其中 `sample_keys` 是 `(building_id, iso_time)`，用于排错与按时间切分。
    """
    now = now or datetime.utcnow()
    points = observation_points(now, observations)
    earliest = min(points) - timedelta(days=WINDOW_DAYS)
    latest = max(points) + timedelta(days=WINDOW_DAYS)

    history = _BuildingHistory(db, tenant_id, earliest, latest)
    buildings = db.query(Building).filter(Building.tenant_id == tenant_id).all()

    rows: List[List[float]] = []
    labels: List[int] = []
    keys: List[Tuple[int, str]] = []
    for observed_at in points:
        for building in buildings:
            rows.append(history.features(building.id, observed_at))
            labels.append(history.label(building.id, observed_at))
            keys.append((building.id, observed_at.isoformat()))

    return {
        "features": rows,
        "labels": labels,
        "sample_keys": keys,
        "observation_times": [p.isoformat() for p in points],
        "label_definition": LABEL_DEFINITION,
        "building_count": len(buildings),
        "feature_names": list(FEATURE_NAMES),
    }


# ---------------------------------------------------------------- 训练

def train_model(
    db: Session,
    tenant_id: int,
    observations: int = DEFAULT_OBSERVATIONS,
    now: Optional[datetime] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """训练并（默认）落盘。样本不足时返回 `{"ok": False, "reason": ...}`，不产出模型。"""
    dataset = build_dataset(db, tenant_id, observations=observations, now=now)
    labels = dataset["labels"]
    positives = sum(labels)
    negatives = len(labels) - positives

    if len(labels) < MIN_SAMPLES:
        return {
            "ok": False,
            "reason": "样本不足",
            "message": (
                f"只有 {len(labels)} 条样本（需要至少 {MIN_SAMPLES} 条：建筑数 × 观测点数），"
                "先积累告警与巡检数据再训练"
            ),
            "sample_count": len(labels),
        }
    if positives < MIN_POSITIVE_SAMPLES or negatives < MIN_NEGATIVE_SAMPLES:
        return {
            "ok": False,
            "reason": "正负样本失衡",
            "message": (
                f"正样本 {positives} 条、负样本 {negatives} 条，两侧都至少需要 "
                f"{MIN_POSITIVE_SAMPLES} 条，否则模型只会学会输出多数类"
            ),
            "sample_count": len(labels),
            "positives": positives,
        }

    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    X = np.asarray(dataset["features"], dtype=float)
    y = np.asarray(labels, dtype=int)

    # 按时间切分：前 70% 观测点训练、后 30% 回测，避免「用未来预测过去」
    times = [key[1] for key in dataset["sample_keys"]]
    order = sorted(range(len(times)), key=lambda i: times[i])
    split = max(1, int(len(order) * TRAIN_RATIO))
    train_idx, test_idx = order[:split], order[split:]
    if not train_idx or not test_idx:
        return {"ok": False, "reason": "样本不足", "message": "样本无法切分出回测集"}

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced")),
    ])
    pipeline.fit(X[train_idx], y[train_idx])

    probabilities = pipeline.predict_proba(X[test_idx])[:, 1]
    y_test = y[test_idx]
    predicted = (probabilities >= 0.5).astype(int)
    metrics = {
        "test_samples": int(len(test_idx)),
        "train_samples": int(len(train_idx)),
        "positives": int(positives),
        "negatives": int(negatives),
        "test_positives": int(y_test.sum()),
        "roc_auc": float(roc_auc_score(y_test, probabilities)) if len(set(y_test.tolist())) > 1 else None,
        "accuracy": float(accuracy_score(y_test, predicted)),
        "precision": float(precision_score(y_test, predicted, zero_division=0)),
        "recall": float(recall_score(y_test, predicted, zero_division=0)),
        "brier": float(brier_score_loss(y_test, probabilities)),
        "base_rate": float(y.mean()),
    }

    scaler = pipeline.named_steps["scaler"]
    classifier = pipeline.named_steps["clf"]
    artifact = {
        "feature_names": list(FEATURE_NAMES),
        "feature_labels": dict(FEATURE_LABELS),
        "mean": [float(v) for v in scaler.mean_],
        "scale": [float(v) for v in scaler.scale_],
        "coef": [float(v) for v in classifier.coef_[0]],
        "intercept": float(classifier.intercept_[0]),
        "trained_at": (now or datetime.utcnow()).isoformat(),
        "tenant_id": int(tenant_id),
        "label_definition": LABEL_DEFINITION,
        "window_days": WINDOW_DAYS,
        "metrics": metrics,
        "limitations": _LIMITATIONS,
        "sklearn_version": _sklearn_version(),
    }
    if persist:
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        with open(MODEL_PATH, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2)
        logger.info("风险预测模型已训练：样本 %s 条，AUC=%s", len(labels), metrics["roc_auc"])

    return {"ok": True, "message": "模型已训练并保存", "metrics": metrics, "model": artifact}


_LIMITATIONS = [
    "设备状态、工单状态没有历史快照，历史样本用的是当前快照，历史样本偏保守",
    "标签是「严重告警 / 告警升级」这类可观测结果，不等于真实火灾（系统内没有事故结果表）",
    "模型只在本租户数据上训练，样本量小的时候指标波动大，看指标时请同时看样本量",
]


def _sklearn_version() -> str:
    try:
        import sklearn
        return sklearn.__version__
    except ImportError:  # pragma: no cover - 依赖缺失时不影响其它功能
        return ""


# ---------------------------------------------------------------- 推理

def load_model() -> Optional[Dict[str, Any]]:
    """读取落盘的模型；未训练或文件损坏时返回 None（调用方如实回报「未训练」）。"""
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "r", encoding="utf-8") as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("风险预测模型文件无法读取：%s", exc)
        return None
    if artifact.get("feature_names") != FEATURE_NAMES:
        # 特征定义改过但模型没重训：宁可报「未训练」，也不要用错位的系数算出假分
        logger.warning("风险预测模型的特征定义与当前代码不一致，需要重新训练")
        return None
    return artifact


def model_info() -> Dict[str, Any]:
    """模型元信息，供页面展示「到底有没有模型」。"""
    artifact = load_model()
    if not artifact:
        return {
            "trained": False,
            "features": [{"name": name, "label": FEATURE_LABELS[name]} for name in FEATURE_NAMES],
            "label_definition": LABEL_DEFINITION,
            "window_days": WINDOW_DAYS,
            "limitations": _LIMITATIONS,
            "message": "模型尚未训练：请先调用 POST /api/risk/model/train（需要 risk:model 权限）",
        }
    return {
        "trained": True,
        "trained_at": artifact.get("trained_at"),
        "features": [{"name": name, "label": FEATURE_LABELS[name]} for name in FEATURE_NAMES],
        "coefficients": dict(zip(artifact["feature_names"], artifact["coef"])),
        "label_definition": artifact.get("label_definition"),
        "window_days": artifact.get("window_days"),
        "metrics": artifact.get("metrics", {}),
        "limitations": artifact.get("limitations", _LIMITATIONS),
        "sklearn_version": artifact.get("sklearn_version", ""),
    }


def _sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def predict(artifact: Dict[str, Any], features: Sequence[float]) -> Dict[str, Any]:
    """用导出系数做推理（等价于标准化 + 线性 + sigmoid），并给出每个特征的贡献。"""
    contributions = []
    logit = artifact["intercept"]
    for name, value, mean, scale, coef in zip(
        artifact["feature_names"], features, artifact["mean"], artifact["scale"], artifact["coef"]
    ):
        safe_scale = scale if scale else 1.0
        standardized = (float(value) - mean) / safe_scale
        contribution = coef * standardized
        logit += contribution
        contributions.append({
            "name": name,
            "label": FEATURE_LABELS.get(name, name),
            "value": round(float(value), 4),
            "contribution": round(contribution, 4),
        })

    probability = _sigmoid(logit)
    contributions.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return {
        "probability": round(probability, 4),
        "logit": round(logit, 4),
        "top_factors": contributions[:5],
    }


def risk_band(probability: float) -> str:
    """把概率映射成展示用的等级（阈值是**模型概率**口径，与规则引擎的分数线不是一回事）。"""
    if probability >= 0.7:
        return "严重风险"
    if probability >= 0.45:
        return "高风险"
    if probability >= 0.2:
        return "中风险"
    return "低风险"


def predict_buildings(
    db: Session,
    tenant_id: int,
    building_ids: Optional[Sequence[int]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """当前时点对建筑做未来 7 天预测。模型未训练时如实回报。"""
    artifact = load_model()
    if not artifact:
        return {"trained": False, "message": model_info()["message"], "items": []}

    now = now or datetime.utcnow()
    query = db.query(Building).filter(Building.tenant_id == tenant_id)
    if building_ids:
        query = query.filter(Building.id.in_(list(building_ids)))
    buildings = query.all()

    history = _BuildingHistory(db, tenant_id, now - timedelta(days=WINDOW_DAYS), now)
    items = []
    for building in buildings:
        features = history.features(building.id, now)
        result = predict(artifact, features)
        items.append({
            "buildingId": building.id,
            "buildingName": building.building_name,
            "buildingCode": building.building_code,
            "ruleScore": building.risk_score,
            "ruleLevel": building.risk_level,
            "probability": result["probability"],
            "predictedLevel": risk_band(result["probability"]),
            "topFactors": result["top_factors"],
            "features": dict(zip(FEATURE_NAMES, [round(v, 4) for v in features])),
        })

    items.sort(key=lambda item: item["probability"], reverse=True)
    return {
        "trained": True,
        "trained_at": artifact.get("trained_at"),
        "window_days": artifact.get("window_days", WINDOW_DAYS),
        "label_definition": artifact.get("label_definition"),
        "metrics": artifact.get("metrics", {}),
        "limitations": artifact.get("limitations", _LIMITATIONS),
        "observed_at": now.isoformat(),
        "items": items,
    }
