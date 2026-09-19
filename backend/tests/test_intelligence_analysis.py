"""智能分析里「AI 分析」的输出不再随机

改造前这些接口挂着「AI 分析」的名字，关键输出却是 `random` 出来的：

- 告警风险分 = 严重度映射 + `random.randint(-5, 5)`，同一条告警每次刷新分数都不同；
- 巡检隐患等级 = `random.choice(["high", "medium", "low"])`，隐患类别也是随机挑的；
- 总分 = `len(hazard_items) * 15 + random.randint(10, 30)`；
- 「类似告警」整块是编的：随机 id、随机楼层、随机原因、随机处置结果；
- 每日简报的告警数/各级数量/处置数/巡检数/隐患数/7 日趋势全是 `random.randint`，
  重点区域写死「1号办公楼 / 地下车库 / 消防水泵房」；
- 自然语言问答直接编数字：「今日共发生{random}起告警」「设备在线率{random}%」；
- 知识推荐内置 7 条写死的假条目（`KB001 烟感探测器工作原理与维护`…），接口又没传候选列表，
  于是不管问什么都返回同一批编出来的内容；
- 经验提取的处置要点与传进来的案例无关，`result="已处置"` 时还会无条件夸一句「响应及时」。

本文件固化改造后的行为：同样的输入给出同样的结果，所有统计数字来自真实表。
"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import (
    AlertRecord,
    Building,
    Device,
    FaultTicket,
    InspectionRecord,
    Role,
    SessionLocal,
    Tenant,
    User,
    hash_password,
    init_db,
)
from services.alert_agent_service import _estimate_risk_score
from services.auth_service import create_access_token
from services.common_utils import local_day_start_utc
from services.intelligence_service import (
    analyze_alert_detail,
    analyze_inspection_risk,
    answer_natural_language_query,
    diagnose_device_fault,
    extract_experience_from_case,
    generate_daily_brief,
    generate_rectification_plan,
    recommend_similar_knowledge,
)
from services.rag_admin_service import list_rag_entries
from services.risk_engine import calculate_risk

TENANT_CODE = "intelligence-tenant"
ADMIN_USER = "intelligence-admin"
PASSWORD = "Test#12345"
ADMIN_ROLE = "intelligence-admin-role"

ALERT_PAYLOAD = {
    "alert_id": "ALERT-CURRENT",
    "alert_type": "smoke_high",
    "alert_name": "烟雾浓度超标",
    "severity": "critical",
    "device_id": "DEV-1",
    "building_name": "综合楼A座",
    "alert_value": 88.0,
    "alert_unit": "%LEL",
    "description": "2层走廊烟感报警",
}


class TestAlertAnalysis(unittest.TestCase):

    def test_risk_score_is_deterministic_and_uses_the_shared_severity_mapping(self):
        """同一输入必须给出同一分数（改前有 random 抖动，跑两次就会不一样）。"""
        first = analyze_alert_detail(dict(ALERT_PAYLOAD))
        second = analyze_alert_detail(dict(ALERT_PAYLOAD))

        self.assertEqual(first["risk_score"], second["risk_score"])
        self.assertEqual(first["confidence"], second["confidence"])
        self.assertEqual(first["risk_score"], _estimate_risk_score("critical"))

        # 严重度不同，分数按同一套口径变化
        lower = analyze_alert_detail({**ALERT_PAYLOAD, "severity": "low"})
        self.assertLess(lower["risk_score"], first["risk_score"])

    def test_confidence_reflects_input_completeness(self):
        """置信度不是随机数，而是「输入信息够不够」：字段补齐后应更高。"""
        full = analyze_alert_detail(dict(ALERT_PAYLOAD))
        sparse = analyze_alert_detail({"severity": "critical"})
        self.assertGreater(full["confidence"], sparse["confidence"])
        self.assertLessEqual(full["confidence"], 1.0)

    def test_similar_alerts_are_passed_through_not_invented(self):
        """没有历史告警时必须是空列表，不能凭空造三条出来。"""
        empty = analyze_alert_detail(dict(ALERT_PAYLOAD))
        self.assertEqual(empty["similar_alerts"], [])

        real = [{"id": "AL-1", "time": "2031-03-01 08:00", "location": "2层", "result": "已处置"}]
        passed = analyze_alert_detail(dict(ALERT_PAYLOAD), similar_alerts=real)
        self.assertEqual(passed["similar_alerts"], real)


class TestInspectionAnalysis(unittest.TestCase):

    def test_hazard_level_and_type_come_from_the_rule_table(self):
        """隐患等级/类别/建议取自规则表：命中的是「消防通道堵塞」，就必须是高风险 + 疏散通道。"""
        payload = {
            "building_name": "综合楼A座",
            "content": "",
            "items": [
                {"id": "C1", "name": "消防通道堵塞", "status": "abnormal", "remark": "通道被货物占用"},
                {"id": "C2", "name": "灭火器压力正常", "status": "normal"},
            ],
        }
        result = analyze_inspection_risk(payload)

        hazard = result["hazard_items"][0]
        self.assertEqual(hazard["hazard_type"], "疏散通道")
        self.assertEqual(hazard["risk_level"], "high")
        self.assertIn("清理", hazard["suggestion"])
        self.assertEqual(hazard["matched_rule"], "消防通道堵塞")
        # 总分与规则引擎完全一致（不再按条数瞎凑）
        self.assertEqual(result["risk_score"], calculate_risk(["消防通道堵塞"])["risk_score"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["matched_rule_count"], 1)

    def test_same_input_gives_the_same_result(self):
        payload = {
            "building_name": "综合楼A座",
            "items": [
                {"name": "电气线路杂乱", "status": "abnormal"},
                {"name": "某个说不上来的问题", "status": "abnormal"},
            ],
        }
        first = analyze_inspection_risk(dict(payload))
        second = analyze_inspection_risk(dict(payload))
        self.assertEqual(first, second)
        # 命不中规则的走兜底档，命中率如实反映出来
        self.assertEqual(first["matched_rule_count"], 1)
        self.assertEqual(first["confidence"], 0.5)

    def test_assessment_does_not_invent_item_count(self):
        """没提交检查项清单时不能写「共检查10项」。"""
        result = analyze_inspection_risk({"content": "现场发现消防通道堵塞"})
        self.assertIn("未提交检查项清单", result["overall_assessment"])
        self.assertNotIn("共检查10项", result["overall_assessment"])


class TestSimilarAlertsFromDatabase(unittest.TestCase):
    """接口层：类似告警必须来自本租户真实历史记录。"""

    client = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.tenant_code == TENANT_CODE).first()
            if not tenant:
                tenant = Tenant(tenant_code=TENANT_CODE, tenant_name="智能分析测试租户", status="active")
                db.add(tenant)
                db.commit()
                db.refresh(tenant)
            cls.tenant_id = tenant.id

            role = db.query(Role).filter(Role.role_code == ADMIN_ROLE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=ADMIN_ROLE,
                    role_name=ADMIN_ROLE,
                    permissions=json.dumps(["*"]),
                )
                db.add(role)
                db.commit()
                db.refresh(role)

            user = db.query(User).filter(User.username == ADMIN_USER).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(
                    username=ADMIN_USER,
                    password_hash=hashed,
                    password_salt=salt,
                    tenant_id=cls.tenant_id,
                    role_id=role.id,
                    real_name=ADMIN_USER,
                    status="active",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.token = create_access_token(user)
        finally:
            db.close()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(AlertRecord).filter(AlertRecord.tenant_id == cls.tenant_id).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.username == ADMIN_USER).delete(synchronize_session=False)
            db.query(Role).filter(Role.role_code == ADMIN_ROLE).delete(synchronize_session=False)
            db.query(Tenant).filter(Tenant.tenant_code == TENANT_CODE).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(AlertRecord).filter(AlertRecord.tenant_id == self.tenant_id).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    def _analyze(self, payload=None):
        return self.client.post(
            "/api/intelligence/analyze-alert",
            json=payload or ALERT_PAYLOAD,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def _seed_alert(self, code, status, location, hour=8):
        db = SessionLocal()
        try:
            db.add(AlertRecord(
                tenant_id=self.tenant_id,
                alert_code=code,
                alert_type="smoke_high",
                severity="critical",
                status=status,
                location=location,
                created_at=datetime(2031, 3, 1, hour, 0),
            ))
            db.commit()
        finally:
            db.close()

    def test_similar_alerts_are_real_records(self):
        self._seed_alert("HIST-1", "resolved", "3层配电间", hour=8)
        self._seed_alert("HIST-2", "pending", "1层大厅", hour=9)

        resp = self._analyze()
        self.assertEqual(resp.status_code, 200, resp.text)
        similar = resp.json()["data"]["similar_alerts"]

        # 按时间倒序取最近的三条，且只给库里真有的记录
        self.assertEqual([item["id"] for item in similar], ["HIST-2", "HIST-1"])
        self.assertEqual(
            [item["result"] for item in similar], ["待处置", "已处置"]
        )
        self.assertEqual([item["location"] for item in similar], ["1层大厅", "3层配电间"])
        self.assertTrue(all(item["time"] == "2031-03-01 09:00" or item["time"] == "2031-03-01 08:00"
                            for item in similar))

    def test_current_alert_is_excluded_and_empty_history_gives_empty_list(self):
        self._seed_alert("ALERT-CURRENT", "pending", "2层走廊")
        resp = self._analyze()
        self.assertEqual(resp.json()["data"]["similar_alerts"], [])

    def test_other_tenant_alerts_are_not_leaked(self):
        db = SessionLocal()
        try:
            other = Tenant(tenant_code=f"{TENANT_CODE}-other", tenant_name="别的租户", status="active")
            db.add(other)
            db.commit()
            db.refresh(other)
            other_id = other.id
            db.add(AlertRecord(
                tenant_id=other_id,
                alert_code="OTHER-1",
                alert_type="smoke_high",
                severity="critical",
                status="resolved",
                location="别家的2层",
                created_at=__import__("datetime").datetime(2031, 3, 1, 8, 0),
            ))
            db.commit()
        finally:
            db.close()

        resp = self._analyze()
        self.assertEqual(resp.json()["data"]["similar_alerts"], [])

        db = SessionLocal()
        try:
            db.query(AlertRecord).filter(AlertRecord.tenant_id == other_id).delete(synchronize_session=False)
            db.query(Tenant).filter(Tenant.tenant_code == f"{TENANT_CODE}-other").delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()


class TestDailyBriefAndDataQuery(unittest.TestCase):
    """每日简报与自然语言问答：数字必须来自真实表，且只统计本租户。"""

    client = None
    query_tenant_code = "intelligence-brief-tenant"
    other_tenant_code = "intelligence-brief-tenant-b"
    query_user = "intelligence-brief-user"
    query_role = "intelligence-brief-role"
    other_user = "intelligence-brief-user-b"
    other_role = "intelligence-brief-role-b"

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.tenant_code == cls.query_tenant_code).first()
            if not tenant:
                tenant = Tenant(tenant_code=cls.query_tenant_code, tenant_name="简报测试租户",
                                status="active")
                db.add(tenant)
                db.commit()
                db.refresh(tenant)
            cls.tenant_id = tenant.id

            other = db.query(Tenant).filter(Tenant.tenant_code == cls.other_tenant_code).first()
            if not other:
                other = Tenant(tenant_code=cls.other_tenant_code, tenant_name="简报测试租户B",
                               status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
            cls.other_tenant_id = other.id

            role = db.query(Role).filter(Role.role_code == cls.query_role).first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code=cls.query_role,
                            role_name=cls.query_role, permissions=json.dumps(["*"]))
                db.add(role)
                db.commit()
                db.refresh(role)

            user = db.query(User).filter(User.username == cls.query_user).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(username=cls.query_user, password_hash=hashed, password_salt=salt,
                            tenant_id=cls.tenant_id, role_id=role.id, real_name=cls.query_user,
                            status="active")
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.token = create_access_token(user)

            # 另一个租户的账号：用于验证「拿不到本租户设备台账」时的降级行为
            other_role = db.query(Role).filter(Role.role_code == cls.other_role).first()
            if not other_role:
                other_role = Role(tenant_id=cls.other_tenant_id, role_code=cls.other_role,
                                  role_name=cls.other_role, permissions=json.dumps(["*"]))
                db.add(other_role)
                db.commit()
                db.refresh(other_role)
            other_user = db.query(User).filter(User.username == cls.other_user).first()
            if not other_user:
                hashed, salt = hash_password(PASSWORD)
                other_user = User(username=cls.other_user, password_hash=hashed, password_salt=salt,
                                  tenant_id=cls.other_tenant_id, role_id=other_role.id,
                                  real_name=cls.other_user, status="active")
                db.add(other_user)
                db.commit()
                db.refresh(other_user)
            cls.other_token = create_access_token(other_user)
        finally:
            db.close()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            for tenant_id in (cls.tenant_id, cls.other_tenant_id):
                cls._purge(db, tenant_id)
            db.query(User).filter(User.username.in_([cls.query_user, cls.other_user])).delete(
                synchronize_session=False
            )
            db.query(Role).filter(Role.role_code.in_([cls.query_role, cls.other_role])).delete(
                synchronize_session=False
            )
            db.query(Tenant).filter(
                Tenant.tenant_code.in_([cls.query_tenant_code, cls.other_tenant_code])
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _purge(db, tenant_id):
        for model in (InspectionRecord, AlertRecord, FaultTicket):
            db.query(model).filter(model.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Device).filter(Device.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Building).filter(Building.tenant_id == tenant_id).delete(synchronize_session=False)
        db.commit()

    def setUp(self):
        """昨天的 3 条告警 + 今天的 1 条；昨天 2 次巡检共 3 项隐患；3 台设备（1 台离线）。"""
        db = SessionLocal()
        try:
            self._purge(db, self.tenant_id)
            self._purge(db, self.other_tenant_id)

            building = Building(tenant_id=self.tenant_id, building_code="brief-bld-1",
                                building_name="简报测试楼")
            db.add(building)
            db.flush()
            self.building_id = building.id

            yesterday = local_day_start_utc(1)
            for index, (severity, status) in enumerate(
                [("critical", "resolved"), ("high", "pending"), ("medium", "pending")]
            ):
                db.add(AlertRecord(
                    tenant_id=self.tenant_id, alert_code=f"BRIEF-{index}",
                    alert_type="smoke_high", severity=severity, status=status,
                    building_id=building.id, building_name="简报测试楼",
                    created_at=yesterday + timedelta(hours=2 + index),
                ))
            db.add(AlertRecord(
                tenant_id=self.tenant_id, alert_code="BRIEF-TODAY", alert_type="temperature_high",
                severity="low", status="pending", building_id=building.id,
                building_name="简报测试楼", created_at=local_day_start_utc(0),
            ))

            db.add(InspectionRecord(
                tenant_id=self.tenant_id, device_id=None, location="简报测试楼2层",
                hazards=json.dumps(["消防通道堵塞"], ensure_ascii=False),
                risk_score=30, risk_level="中风险", created_at=yesterday + timedelta(hours=3),
            ))
            db.add(InspectionRecord(
                tenant_id=self.tenant_id, device_id=None, location="简报测试楼3层",
                hazards=json.dumps(["灭火器遮挡", "电气线路杂乱"], ensure_ascii=False),
                risk_score=48, risk_level="高风险", created_at=yesterday + timedelta(hours=4),
            ))

            for index, status in enumerate(["正常", "正常", "离线"]):
                db.add(Device(
                    tenant_id=self.tenant_id, device_code=f"BRIEF-DEV-{index}",
                    device_name=f"简报设备{index}", device_type="烟感探测器", status=status,
                    building_id=building.id,
                ))

            db.add(FaultTicket(
                tenant_id=self.tenant_id, title="逾期工单", status="处理中",
                building_id=building.id, building_name="简报测试楼",
                deadline=datetime.utcnow() - timedelta(days=2),
            ))

            # 别的租户：昨天的 5 条告警，用来验证隔离
            for index in range(5):
                db.add(AlertRecord(
                    tenant_id=self.other_tenant_id, alert_code=f"OTHER-BRIEF-{index}",
                    alert_type="smoke_high", severity="critical", status="pending",
                    building_name="别家的楼", created_at=yesterday + timedelta(hours=index),
                ))
            db.commit()
        finally:
            db.close()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # ---------------- 每日简报 ----------------

    def test_daily_brief_counts_come_from_the_database(self):
        db = SessionLocal()
        try:
            brief = generate_daily_brief(db, self.tenant_id)
        finally:
            db.close()

        stats = brief["alert_stats"]
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["critical"], 1)
        self.assertEqual(stats["high"], 1)
        self.assertEqual(stats["medium"], 1)
        self.assertEqual(stats["low"], 0)
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(brief["inspection_stats"]["inspection_count"], 2)
        self.assertEqual(brief["inspection_stats"]["hazard_found"], 3)
        self.assertEqual(brief["data_source"], "database")

        # 趋势是逐日真实值：最后一天（昨天）应为 3 条
        self.assertEqual(len(brief["alarm_trend"]), 7)
        self.assertEqual(brief["alarm_trend"][-1]["count"], 3)
        self.assertEqual(brief["alarm_trend"][-1]["critical"], 1)

        # 重点区域由真实数据推导，不再写死
        areas = [item["area"] for item in brief["today_focus"]]
        self.assertIn("简报测试楼", areas)
        self.assertNotIn("1号办公楼", areas)
        focus = next(item for item in brief["today_focus"] if item["area"] == "简报测试楼")
        # 同一区域既有告警又有逾期工单时，两条信息合并展示
        self.assertIn("告警", focus["reason"])
        self.assertIn("逾期", focus["reason"])
        self.assertEqual(focus["level"], "high")

    def test_daily_brief_is_deterministic(self):
        """同一天连查两次必须一致（改造前每次都是新的随机数）。"""
        db = SessionLocal()
        try:
            first = generate_daily_brief(db, self.tenant_id)
            second = generate_daily_brief(db, self.tenant_id)
        finally:
            db.close()
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(first["alert_stats"], second["alert_stats"])
        self.assertEqual(first["alarm_trend"], second["alarm_trend"])

    def test_daily_brief_for_an_empty_day_is_all_zeros(self):
        db = SessionLocal()
        try:
            brief = generate_daily_brief(db, self.tenant_id, "2020-01-01")
        finally:
            db.close()
        self.assertEqual(brief["date"], "2020-01-01")
        self.assertEqual(brief["alert_stats"]["total"], 0)
        self.assertEqual(brief["inspection_stats"]["inspection_count"], 0)
        self.assertEqual(brief["today_focus"], [])
        self.assertTrue(any(item["type"] == "success" for item in brief["key_highlights"]))

    def test_daily_brief_is_tenant_scoped(self):
        db = SessionLocal()
        try:
            other = generate_daily_brief(db, self.other_tenant_id)
        finally:
            db.close()
        self.assertEqual(other["alert_stats"]["total"], 5)

    # ---------------- 自然语言问答 ----------------

    def test_query_today_alerts_uses_real_counts(self):
        db = SessionLocal()
        try:
            result = answer_natural_language_query("今天有多少告警？", db, self.tenant_id)
        finally:
            db.close()
        self.assertEqual(result["result_data"]["today_count"], 1)
        self.assertIn("今日共发生1起告警", result["answer_text"])
        self.assertEqual(result["data_source"], "database")

    def test_query_is_deterministic(self):
        db = SessionLocal()
        try:
            first = answer_natural_language_query("当前设备在线率是多少？", db, self.tenant_id)
            second = answer_natural_language_query("当前设备在线率是多少？", db, self.tenant_id)
        finally:
            db.close()
        self.assertEqual(first["answer_text"], second["answer_text"])
        self.assertEqual(first["confidence"], second["confidence"])
        # 3 台设备里 2 台在线
        self.assertEqual(first["result_data"]["online_rate"], 66.7)
        self.assertEqual(first["result_data"]["offline"], 1)

    def test_query_top_alert_area_is_real(self):
        db = SessionLocal()
        try:
            result = answer_natural_language_query("哪个区域告警最多？", db, self.tenant_id)
        finally:
            db.close()
        self.assertEqual(result["result_data"]["top_building"], "简报测试楼")
        self.assertEqual(result["result_data"]["count"], 4)  # 昨天 3 条 + 今天 1 条
        self.assertNotIn("2号研发楼", result["answer_text"])

    def test_query_buildings_and_hazards(self):
        db = SessionLocal()
        try:
            buildings = answer_natural_language_query("系统有多少栋建筑？", db, self.tenant_id)
            hazards = answer_natural_language_query("当前有多少隐患？", db, self.tenant_id)
        finally:
            db.close()
        self.assertEqual(buildings["result_data"]["building_count"], 1)
        self.assertEqual(hazards["result_data"]["hazard_count"], 3)
        self.assertEqual(hazards["result_data"]["high_risk_count"], 1)

    def test_query_unknown_question_gives_guidance_not_numbers(self):
        db = SessionLocal()
        try:
            result = answer_natural_language_query("今天天气怎么样？", db, self.tenant_id)
        finally:
            db.close()
        self.assertEqual(result["answer_type"], "guidance")
        self.assertEqual(result["result_data"], {})
        self.assertEqual(result["confidence"], 0.5)

    def test_query_is_tenant_scoped(self):
        db = SessionLocal()
        try:
            result = answer_natural_language_query("今天有多少告警？", db, self.other_tenant_id)
        finally:
            db.close()
        # 别的租户只有昨天的告警
        self.assertEqual(result["result_data"]["today_count"], 0)

    # ---------------- 模板类置信度 ----------------

    def test_template_confidences_are_deterministic_and_reflect_inputs(self):
        full_input = {
            "hazard_type": "电气安全", "description": "配电箱周围堆放纸箱",
            "risk_level": "high", "building_name": "简报测试楼",
        }
        plan_a = generate_rectification_plan(full_input)
        plan_b = generate_rectification_plan(dict(full_input))
        self.assertEqual(plan_a["confidence"], plan_b["confidence"])
        self.assertGreater(plan_a["confidence"], generate_rectification_plan({})["confidence"])

        diagnose_a = diagnose_device_fault({"device_type": "烟感探测器", "device_name": "简报设备0",
                                            "status": "故障", "building_name": "简报测试楼"})
        diagnose_b = diagnose_device_fault({"device_type": "烟感探测器", "device_name": "简报设备0",
                                            "status": "故障", "building_name": "简报测试楼"})
        self.assertEqual(diagnose_a["confidence"], diagnose_b["confidence"])
        self.assertGreater(diagnose_a["confidence"], diagnose_device_fault({})["confidence"])

    # ---------------- 设备故障诊断的权重口径 ----------------

    def test_diagnosis_without_device_ledger_uses_knowledge_base_weights(self):
        """拿不到设备台账时：退回知识库先验权重，并如实标注来源，不假装是算出来的概率。"""
        result = diagnose_device_fault({"device_type": "烟感探测器", "status": "故障"})
        self.assertEqual(result["weight_basis"], "knowledge_base")
        self.assertIn("知识库经验", result["weight_note"])
        self.assertEqual(result["device_signals"], {})
        for cause in result["fault_causes"]:
            self.assertNotIn("probability", cause)
            self.assertEqual(cause["basis"], "knowledge_base")
            self.assertTrue(cause["evidence"][0].startswith("知识库经验："))
        # 权重降序，且 most_likely_cause 就是权重最高的那条
        weights = [cause["weight"] for cause in result["fault_causes"]]
        self.assertEqual(weights, sorted(weights, reverse=True))
        self.assertEqual(result["most_likely_cause"], result["fault_causes"][0]["cause"])

    def test_diagnosis_uses_real_device_data_when_available(self):
        """有台账时：老设备 + 超期未维保 + 长期未上报，会把对应原因的权重顶上来。"""
        db = SessionLocal()
        try:
            building = db.query(Building).filter(Building.tenant_id == self.tenant_id).first()
            device = Device(
                tenant_id=self.tenant_id, device_code="DIAG-OLD-1", device_name="老旧烟感",
                device_type="烟感探测器", status="故障", building_id=building.id,
                install_date=(datetime.now().date() - timedelta(days=int(365 * 9.5))),
                last_maintenance=(datetime.now().date() - timedelta(days=400)),
                next_maintenance=(datetime.now().date() - timedelta(days=30)),
                last_seen_at=datetime.utcnow() - timedelta(days=3),
            )
            db.add(device)
            db.commit()
            db.refresh(device)

            result = diagnose_device_fault(
                {"device_id": str(device.id), "device_type": "烟感探测器", "status": "故障"},
                device=device,
            )
        finally:
            db.close()

        self.assertEqual(result["weight_basis"], "device_data")
        self.assertIn("非故障概率", result["weight_note"])
        self.assertGreaterEqual(result["device_signals"]["ageYears"], 9)
        self.assertTrue(result["device_signals"]["maintenanceOverdue"])

        causes = {cause["cause"]: cause for cause in result["fault_causes"]}
        for name in ("设备老化", "维护不到位", "供电异常"):
            self.assertEqual(causes[name]["basis"], "device_data")
            self.assertTrue(causes[name]["evidence"])
        # 证据里是这台设备的真实数字，不是「设备已使用超过5年」这类凭空断言
        self.assertTrue(any("已投用" in item for item in causes["设备老化"]["evidence"]))
        self.assertTrue(any("距上次维保 400 天" in item for item in causes["维护不到位"]["evidence"]))
        self.assertTrue(any("已超过计划维保日期" in item for item in causes["维护不到位"]["evidence"]))
        self.assertTrue(any("未上报数据" in item for item in causes["供电异常"]["evidence"]))
        # 设备老化/维护不到位在知识库先验之上被抬高
        self.assertGreater(causes["设备老化"]["weight"], 0.35)
        self.assertGreater(causes["维护不到位"]["weight"], 0.15)

    def test_diagnose_endpoint_reads_device_from_the_database(self):
        db = SessionLocal()
        try:
            building = db.query(Building).filter(Building.tenant_id == self.tenant_id).first()
            device = Device(
                tenant_id=self.tenant_id, device_code="DIAG-OLD-2", device_name="接口诊断设备",
                device_type="烟感探测器", status="故障", building_id=building.id,
                install_date=(datetime.now().date() - timedelta(days=int(365 * 9))),
                next_maintenance=(datetime.now().date() - timedelta(days=10)),
            )
            db.add(device)
            db.commit()
            db.refresh(device)
            device_id = device.id
        finally:
            db.close()

        resp = self.client.post(
            "/api/intelligence/diagnose-device",
            json={"device_id": str(device_id), "device_type": "烟感探测器", "status": "故障"},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()["data"]
        self.assertEqual(data["weight_basis"], "device_data")
        self.assertGreaterEqual(data["device_signals"]["ageYears"], 8)

        # 别的租户拿同一个 device_id 取不到台账 → 退回知识库权重
        other = self.client.post(
            "/api/intelligence/diagnose-device",
            json={"device_id": str(device_id), "device_type": "烟感探测器", "status": "故障"},
            headers={"Authorization": f"Bearer {self.other_token}"},
        )
        self.assertEqual(other.status_code, 200, other.text)
        self.assertEqual(other.json()["data"]["weight_basis"], "knowledge_base")

    # ---------------- 接口层 ----------------

    def test_endpoints_require_login(self):
        for path in ("/api/intelligence/daily-brief", "/api/intelligence/query-data?question=今日告警"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_daily_brief_endpoint_returns_real_numbers(self):
        resp = self.client.get("/api/intelligence/daily-brief", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()["data"]
        self.assertEqual(body["alert_stats"]["total"], 3)
        self.assertEqual(body["date"], (datetime.now().date() - timedelta(days=1)).isoformat())

    def test_query_endpoint_returns_real_numbers(self):
        resp = self.client.get("/api/intelligence/query-data",
                               params={"question": "今天有多少告警？"}, headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["data"]["result_data"]["today_count"], 1)

    def test_recommend_knowledge_endpoint_reads_the_real_knowledge_base(self):
        resp = self.client.get("/api/intelligence/recommend-knowledge",
                               params={"query": "灭火器"}, headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()["data"]
        self.assertTrue(items, "内置知识库里有灭火器相关条目，不应返回空")

        # 返回的必须是知识库里真有的条目，而不是原来那批写死的假条目
        known_titles = {entry["title"] for entry in list_rag_entries(enabled="1")}
        returned_titles = {item["title"] for item in items}
        self.assertTrue(returned_titles <= known_titles, returned_titles - known_titles)
        self.assertTrue(any("灭火器" in title for title in returned_titles))
        for fake in ("烟感探测器工作原理与维护", "某商场电气火灾处置案例", "消防安全检查要点"):
            self.assertNotIn(fake, returned_titles)


class TestKnowledgeRecommendationAndExperience(unittest.TestCase):
    """知识推荐与经验提取：候选条目由调用方给，提取不出依据就返回空。"""

    def test_recommendation_returns_nothing_without_candidate_entries(self):
        # 以前不传 knowledge_list 会拿到 7 条写死的假条目，不管问什么都返回它们
        self.assertEqual(recommend_similar_knowledge("烟感故障", []), [])

    def test_recommendation_only_scores_the_entries_it_is_given(self):
        entries = [
            {"id": "RAG-A", "title": "烟感探测器异常", "keywords": "烟感,烟雾探测器,离线"},
            {"id": "RAG-B", "title": "灭火器巡检要点", "keywords": "灭火器，压力表"},
        ]
        result = recommend_similar_knowledge("烟感", entries)
        self.assertEqual([item["id"] for item in result], ["RAG-A"])
        self.assertGreater(result[0]["relevance_score"], 0)

    def test_recommendation_ignores_a_blank_query(self):
        self.assertEqual(recommend_similar_knowledge("   ", [{"id": "RAG-A", "title": "烟感"}]), [])

    def test_experience_extraction_returns_nothing_without_evidence(self):
        result = extract_experience_from_case({})
        self.assertEqual(result["experience_tags"], [])
        self.assertEqual(result["best_practices"], [])
        self.assertEqual(result["lessons_learned"], [])
        self.assertEqual(result["summary"], "案例信息不足，未提取到可归纳的经验")

    def test_experience_extraction_keeps_the_words_that_triggered_it(self):
        result = extract_experience_from_case({
            "alert_type": "电气火灾",
            "result": "误报",
            "process_description": "现场确认无火情属误报，已复位设备",
        })
        self.assertIn("误报识别", result["experience_tags"])
        self.assertIn("电气安全", result["experience_tags"])
        for practice in result["best_practices"]:
            self.assertTrue(practice["basis"].startswith("案例信息中出现「"), practice)
        self.assertEqual(result["lessons_learned"], ["电气火灾存在误报可能，需结合现场情况判断"])

    def test_experience_extraction_does_not_praise_the_case_out_of_nothing(self):
        # 以前只要 result="已处置" 就输出「处置流程规范，响应及时」，与案例内容无关
        result = extract_experience_from_case({"alert_type": "烟雾报警", "result": "已处置"})
        self.assertEqual(result["best_practices"], [])
        self.assertEqual(result["lessons_learned"], [])


if __name__ == "__main__":
    unittest.main()
