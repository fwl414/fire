"""风险评分接口：入参必须真的进入评分逻辑

回归背景：`routers/risk.py` 里用了 `json.loads`，但整个文件没有 `import json`，
而这几行被包在 `except Exception` 中 —— `NameError` 被静默吞掉后，隐患 / 遥测 /
巡检 / 环境参数统统被替换成空值，接口按「什么都还没有」算出 0 分，既不报错也不落日志。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import Role, SessionLocal, Tenant, User, hash_password, init_db
from services.auth_service import create_access_token

TENANT_CODE = "risk-api-test-tenant"
USERNAME = "risk-api-tester"
PASSWORD = "Test#12345"
ROLE_CODE = "risk-api-test-role"
ENDPOINT = "/api/risk/enhanced/calculate"


class TestRiskApiAcceptsFactors(unittest.TestCase):

    client = None
    token = ""
    created = {}

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.tenant_code == TENANT_CODE).first()
            if not tenant:
                tenant = Tenant(tenant_code=TENANT_CODE, tenant_name="风险接口测试租户", status="active")
                db.add(tenant)
                db.commit()
                db.refresh(tenant)
                cls.created["tenant"] = tenant.id

            role = db.query(Role).filter(Role.role_code == ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=tenant.id,
                    role_code=ROLE_CODE,
                    role_name="风险接口测试角色",
                    permissions=json.dumps(["*"]),
                )
                db.add(role)
                db.commit()
                db.refresh(role)
                cls.created["role"] = role.id

            user = db.query(User).filter(User.username == USERNAME).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(
                    username=USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name=USERNAME,
                    role_id=role.id,
                    status="active",
                    tenant_id=tenant.id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                cls.created["user"] = user.id

            cls.token = create_access_token(user)
        finally:
            db.close()

        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            if cls.created.get("user"):
                db.query(User).filter(User.id == cls.created["user"]).delete(synchronize_session=False)
            if cls.created.get("role"):
                db.query(Role).filter(Role.id == cls.created["role"]).delete(synchronize_session=False)
            if cls.created.get("tenant"):
                db.query(Tenant).filter(Tenant.id == cls.created["tenant"]).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _calculate(self, **form):
        payload = {"building_id": "risk-api-test-building", **form}
        resp = self.client.post(
            ENDPOINT,
            data=payload,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def test_hazard_items_reach_the_scoring_engine(self):
        """两条 A 级隐患必须计入隐患等级分（被吞掉时这里是 0）。"""
        body = self._calculate(hazard_items=json.dumps([{"severity": "A"}, {"severity": "A"}]))

        self.assertEqual(body["score_details"]["hazard_level"], 60, body)
        self.assertGreater(body["risk_score"], 0, body)

    def test_telemetry_and_environment_reach_the_scoring_engine(self):
        """遥测与环境参数同样不能被静默丢弃。"""
        body = self._calculate(
            telemetry_data=json.dumps([
                {"status": "alarm", "online": True},
                {"status": "normal", "online": False},
            ]),
            environment_info=json.dumps({"has_chemicals": True}),
        )

        self.assertGreater(body["score_details"]["device_alarm"], 0, body)
        self.assertGreater(body["score_details"]["device_online"], 0, body)
        self.assertEqual(body["score_details"]["environment"], 8, body)

    def test_malformed_json_falls_back_to_empty_instead_of_failing(self):
        """容错仍然保留，但只针对「格式坏掉」的入参，而不是正常入参。"""
        body = self._calculate(hazard_items="这不是 JSON")

        self.assertEqual(body["score_details"]["hazard_level"], 0, body)
        self.assertEqual(body["risk_score"], 0, body)


if __name__ == "__main__":
    unittest.main()
