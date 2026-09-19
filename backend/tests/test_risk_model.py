"""风险预测模型（scikit-learn）

改造前「风险预测」只有规则算分，没有任何模型。本文件固化模型侧的四条关键行为：

- **没训练就不给分**：模型不存在时预测接口如实回报「未训练」，不返回编造的概率；
- **真的学到东西**：用带真实时间关系的数据训练后，回测 AUC 明显高于随机，
  且「观测窗口内告警多的建筑」预测概率高于「一直安静的建筑的」——这条能判别
  特征与标签是否接错（接错时两组概率会一样）；
- **不乱用错位的模型**：模型文件里的特征定义与当前代码不一致时按「未训练」处理；
- **样本不足就拒绝训练**，不「凑」一个模型出来。

训练样本按「建筑 × 观测点」构造：观测点前 7 天是特征窗口、后 7 天是标签窗口，
所以造数必须把告警放在正确的时间点，否则标签就是错的，测试也就失去意义。
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AlertRecord,
    Building,
    Role,
    SessionLocal,
    Tenant,
    User,
    hash_password,
    init_db,
)
from services import risk_model_service
from services.auth_service import create_access_token

SERVICE_TENANT_CODE = "risk-model-tenant"
API_TENANT_CODE = "risk-model-api-tenant"
SMALL_TENANT_CODE = "risk-model-small-tenant"
ADMIN_USER = "risk-model-admin"
VIEWER_USER = "risk-model-viewer"
PASSWORD = "Test#12345"
ADMIN_ROLE = "risk-model-admin-role"
VIEWER_ROLE = "risk-model-viewer-role"

# 固定「现在」，让观测点、特征窗口、标签窗口都是确定的
NOW = datetime(2031, 3, 10, 12, 0)
RISKY_BUILDINGS = 4
CALM_BUILDINGS = 4
EXPECTED_SAMPLES = (RISKY_BUILDINGS + CALM_BUILDINGS) * risk_model_service.DEFAULT_OBSERVATIONS


# ---------------------------------------------------------------- 造数与清理助手

def ensure_tenant(db, code: str, name: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.tenant_code == code).first()
    if not tenant:
        tenant = Tenant(tenant_code=code, tenant_name=name, status="active")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def purge_tenant(db, tenant_id: int) -> None:
    db.query(AlertRecord).filter(AlertRecord.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(Building).filter(Building.tenant_id == tenant_id).delete(synchronize_session=False)
    db.commit()


def seed_buildings_and_alerts(db, tenant_id: int, now: datetime = None):
    """造出「观测窗口里有告警 → 未来 7 天出现严重告警」这一可学的关系。

    - 有风险建筑：每个观测点的特征窗口里放 2 条中危告警；标签窗口正中放 1 条危重告警
    - 安静建筑：一条告警都没有

    默认按**真实当前时间**造数（接口层测试走的是真实 now，造数必须对齐，否则标签全是 0）；
    服务层测试可以传固定的 now，让观测点、窗口都确定。

    造数前先清一次该租户的建筑与告警：上一轮跑挂在中途时不会留下 building_code 冲突。
    """
    purge_tenant(db, tenant_id)
    now = now or datetime.utcnow()
    risky_ids, calm_ids = [], []
    for index in range(RISKY_BUILDINGS + CALM_BUILDINGS):
        building = Building(
            tenant_id=tenant_id,
            building_code=f"{tenant_id}-RM-{index}",
            building_name=f"风险模型楼{index}",
            floors=3,
            area=1200.0,
        )
        db.add(building)
        db.flush()
        (risky_ids if index < RISKY_BUILDINGS else calm_ids).append(building.id)

    for point in risk_model_service.observation_points(now):
        for order, building_id in enumerate(risky_ids):
            for offset in (1, 2):
                db.add(AlertRecord(
                    tenant_id=tenant_id,
                    alert_code=f"{tenant_id}-{building_id}-{point.date()}-M{offset}",
                    building_id=building_id,
                    alert_type="smoke_high",
                    severity="medium",
                    status="pending",
                    created_at=point - timedelta(days=3, hours=12) + timedelta(minutes=offset),
                ))
            # 标签窗口正中的危重告警：让「未来 7 天」的标签为 1
            db.add(AlertRecord(
                tenant_id=tenant_id,
                alert_code=f"{tenant_id}-{building_id}-{point.date()}-C",
                building_id=building_id,
                alert_type="smoke_high",
                severity="critical",
                status="pending",
                created_at=point + timedelta(days=3, hours=12) + timedelta(minutes=order),
            ))
    db.commit()
    return risky_ids, calm_ids


class _ModelPathMixin:
    """模型产物写到临时目录，别污染仓库里的 artifacts/。"""

    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.model_path = os.path.join(self.tmpdir.name, "risk_model.json")
        patcher = mock.patch.object(risk_model_service, "MODEL_PATH", self.model_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmpdir.cleanup)


# ---------------------------------------------------------------- 服务层

class TestRiskModelService(_ModelPathMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.db = SessionLocal()
        cls.tenant_id = ensure_tenant(cls.db, SERVICE_TENANT_CODE, "风险模型测试租户").id
        cls.risky_ids, cls.calm_ids = seed_buildings_and_alerts(cls.db, cls.tenant_id, now=NOW)

    @classmethod
    def tearDownClass(cls):
        purge_tenant(cls.db, cls.tenant_id)
        cls.db.query(Tenant).filter(Tenant.tenant_code == SERVICE_TENANT_CODE).delete(
            synchronize_session=False
        )
        cls.db.commit()
        cls.db.close()

    def test_prediction_without_training_reports_untrained(self):
        info = risk_model_service.model_info()
        self.assertFalse(info["trained"])
        self.assertIn("尚未训练", info["message"])

        result = risk_model_service.predict_buildings(self.db, self.tenant_id, now=NOW)
        self.assertFalse(result["trained"])
        self.assertEqual(result["items"], [])

    def test_training_learns_the_signal_and_beats_random(self):
        result = risk_model_service.train_model(self.db, self.tenant_id, now=NOW)
        self.assertTrue(result["ok"], result.get("message"))

        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["roc_auc"], 0.8)
        self.assertEqual(metrics["positives"] + metrics["negatives"], EXPECTED_SAMPLES)
        self.assertGreater(metrics["test_samples"], 0)

        artifact = risk_model_service.load_model()
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact["feature_names"], risk_model_service.FEATURE_NAMES)
        self.assertEqual(artifact["tenant_id"], self.tenant_id)
        self.assertIn("未来 7 天", artifact["label_definition"])

    def test_risky_buildings_score_higher_than_calm_ones(self):
        """判别性用例：告警多的建筑概率必须高于一直安静的（特征/标签接错时两者会一样）。"""
        risk_model_service.train_model(self.db, self.tenant_id, now=NOW)

        predictions = risk_model_service.predict_buildings(self.db, self.tenant_id, now=NOW)
        self.assertTrue(predictions["trained"])
        by_building = {item["buildingId"]: item for item in predictions["items"]}
        self.assertEqual(len(by_building), RISKY_BUILDINGS + CALM_BUILDINGS)

        lowest_risky = min(by_building[bid]["probability"] for bid in self.risky_ids)
        highest_calm = max(by_building[bid]["probability"] for bid in self.calm_ids)
        self.assertGreater(
            lowest_risky, highest_calm,
            f"有风险建筑的最低概率 {lowest_risky} 应高于安静建筑的最高概率 {highest_calm}",
        )
        # 概率高的排前面
        probabilities = [item["probability"] for item in predictions["items"]]
        self.assertEqual(probabilities, sorted(probabilities, reverse=True))

    def test_explanation_uses_real_feature_values(self):
        risk_model_service.train_model(self.db, self.tenant_id, now=NOW)
        predictions = risk_model_service.predict_buildings(
            self.db, self.tenant_id, building_ids=[self.risky_ids[0]], now=NOW
        )
        item = predictions["items"][0]
        # 观测窗口里应有 3 条告警（2 条中危 + 1 条危重），且必须体现在原始特征里
        self.assertEqual(item["features"]["alerts_7d"], 3)
        self.assertEqual(item["features"]["severe_alerts_7d"], 1)

        factors = {factor["name"]: factor for factor in item["topFactors"]}
        self.assertIn("alerts_7d", factors)
        self.assertEqual(factors["alerts_7d"]["value"], item["features"]["alerts_7d"])
        self.assertNotEqual(factors["alerts_7d"]["contribution"], 0)

    def test_training_refuses_when_samples_are_insufficient(self):
        small = ensure_tenant(self.db, SMALL_TENANT_CODE, "样本不足租户")
        self.db.add(Building(tenant_id=small.id, building_code="small-1", building_name="样本不足楼"))
        self.db.commit()

        result = risk_model_service.train_model(self.db, small.id, observations=2, now=NOW)
        self.assertFalse(result["ok"])
        self.assertIn(result["reason"], ("样本不足", "正负样本失衡"))
        self.assertFalse(os.path.exists(self.model_path))
        self.assertFalse(risk_model_service.model_info()["trained"])

        purge_tenant(self.db, small.id)
        self.db.query(Tenant).filter(Tenant.tenant_code == SMALL_TENANT_CODE).delete(
            synchronize_session=False
        )
        self.db.commit()

    def test_model_with_stale_feature_definition_is_treated_as_untrained(self):
        risk_model_service.train_model(self.db, self.tenant_id, now=NOW)
        with open(self.model_path, "r", encoding="utf-8") as handle:
            artifact = json.load(handle)
        artifact["feature_names"] = artifact["feature_names"][:-1] + ["brand_new_feature"]
        with open(self.model_path, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, ensure_ascii=False)

        self.assertFalse(risk_model_service.model_info()["trained"])
        self.assertFalse(
            risk_model_service.predict_buildings(self.db, self.tenant_id, now=NOW)["trained"]
        )

    def test_predictions_are_tenant_scoped(self):
        """本租户的模型不该去给别的租户的建筑打分。"""
        risk_model_service.train_model(self.db, self.tenant_id, now=NOW)
        other = ensure_tenant(self.db, "risk-model-other-tenant", "别的租户")
        result = risk_model_service.predict_buildings(self.db, other.id, now=NOW)
        self.assertEqual(result["items"], [])
        self.db.query(Tenant).filter(Tenant.tenant_code == "risk-model-other-tenant").delete(
            synchronize_session=False
        )
        self.db.commit()


# ---------------------------------------------------------------- 接口层

class TestRiskModelApi(_ModelPathMixin, unittest.TestCase):
    """权限、未训练时的回应、训练后的接口形态。"""

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = ensure_tenant(db, API_TENANT_CODE, "风险模型接口租户").id
            # 不传 now：接口走的是真实当前时间，造数必须对齐同一个时间口径
            seed_buildings_and_alerts(db, cls.tenant_id)
            admin_role = cls._ensure_role(db, ADMIN_ROLE, cls.tenant_id, ["*"])
            viewer_role = cls._ensure_role(db, VIEWER_ROLE, cls.tenant_id, ["dashboard:view"])
            admin = cls._ensure_user(db, ADMIN_USER, cls.tenant_id, admin_role.id)
            viewer = cls._ensure_user(db, VIEWER_USER, cls.tenant_id, viewer_role.id)
            cls.token_admin = create_access_token(admin)
            cls.token_viewer = create_access_token(viewer)
        finally:
            db.close()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            purge_tenant(db, cls.tenant_id)
            db.query(User).filter(User.username.in_([ADMIN_USER, VIEWER_USER])).delete(
                synchronize_session=False
            )
            db.query(Role).filter(Role.role_code.in_([ADMIN_ROLE, VIEWER_ROLE])).delete(
                synchronize_session=False
            )
            db.query(Tenant).filter(Tenant.tenant_code == API_TENANT_CODE).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    @classmethod
    def _ensure_role(cls, db, code, tenant_id, permissions):
        role = db.query(Role).filter(Role.role_code == code).first()
        if not role:
            role = Role(
                tenant_id=tenant_id,
                role_code=code,
                role_name=code,
                permissions=json.dumps(permissions),
            )
            db.add(role)
            db.commit()
            db.refresh(role)
        return role

    @classmethod
    def _ensure_user(cls, db, username, tenant_id, role_id):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            hashed, salt = hash_password(PASSWORD)
            user = User(
                username=username,
                password_hash=hashed,
                password_salt=salt,
                tenant_id=tenant_id,
                role_id=role_id,
                real_name=username,
                status="active",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_training_requires_risk_model_permission(self):
        resp = self.client.post("/api/risk/model/train", headers=self._headers(self.token_viewer))
        self.assertEqual(resp.status_code, 403, resp.text)
        # 只读的模型信息接口只要登录
        self.assertEqual(
            self.client.get("/api/risk/model", headers=self._headers(self.token_viewer)).status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/risk/predictions", headers=self._headers(self.token_viewer)).status_code, 200
        )

    def test_predictions_endpoint_is_honest_before_training(self):
        resp = self.client.get("/api/risk/predictions", headers=self._headers(self.token_admin))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(body["trained"])
        self.assertEqual(body["items"], [])
        self.assertIn("尚未训练", body["message"])

    def test_training_reports_reason_when_samples_are_insufficient(self):
        resp = self.client.post(
            "/api/risk/model/train?observations=2", headers=self._headers(self.token_admin)
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("样本", resp.json()["message"])

    def test_trained_model_is_served_through_the_api(self):
        trained = self.client.post("/api/risk/model/train", headers=self._headers(self.token_admin))
        self.assertEqual(trained.status_code, 200, trained.text)

        body = self.client.get("/api/risk/predictions", headers=self._headers(self.token_admin)).json()
        self.assertTrue(body["trained"])
        self.assertTrue(body["items"])
        self.assertIn("probability", body["items"][0])
        self.assertIn("roc_auc", body["metrics"])
        self.assertEqual(len(body["items"]), RISKY_BUILDINGS + CALM_BUILDINGS)
        self.assertTrue(body["items"][0]["topFactors"])

        building_id = body["items"][0]["buildingId"]
        single = self.client.get(
            f"/api/risk/prediction/{building_id}", headers=self._headers(self.token_admin)
        )
        self.assertEqual(single.status_code, 200, single.text)
        self.assertEqual(single.json()["buildingId"], building_id)
        self.assertTrue(single.json()["topFactors"])

        info = self.client.get("/api/risk/model", headers=self._headers(self.token_admin)).json()
        self.assertTrue(info["trained"])
        self.assertEqual(len(info["features"]), len(risk_model_service.FEATURE_NAMES))

    def test_unknown_building_returns_404(self):
        self.client.post("/api/risk/model/train", headers=self._headers(self.token_admin))
        resp = self.client.get("/api/risk/prediction/99999999", headers=self._headers(self.token_admin))
        self.assertEqual(resp.status_code, 404, resp.text)


if __name__ == "__main__":
    unittest.main()
