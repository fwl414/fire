"""数据大屏接口测试

背景：改造前 `/api/dashboard/screen-data` 有 6 处写死常量（隐患总数 48、整改率 78、
管网压力 0.45、水箱水位 82、值班人员「张建国（班长）」、今日事件 5 条、巡检完成率 92、
培训合格率 96）。本测试的核心目的就是**守住"不再有假数据"**：

- 有数据时，各项数值必须与真实记录逐一对上
- 没有数据时，各项必须为 0/空，而不是原来的常量
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
    DeviceTelemetry,
    DutyShift,
    FaultTicket,
    InspectionRecord,
    Role,
    SessionLocal,
    Tenant,
    User,
    VideoChannel,
    hash_password,
    init_db,
)
from services.common_utils import local_day_start_utc

TENANT_CODE = "screen-test-tenant"
EMPTY_TENANT_CODE = "screen-empty-tenant"
USERNAME = "data-screen-tester"
PASSWORD = "Test#12345"
ROLE_CODE = "screen-test-admin"

# 改造前写死的常量，出现即视为回归
LEGACY_FAKE_VALUES = {
    "hazard_total": 48,
    "hazard_rate": 78,
    "tank_level": 82,
    "training_rate": 96,
    "inspection_rate": 92,
}
LEGACY_FAKE_INDICATORS = {"巡检完成率", "培训合格率"}
LEGACY_FAKE_PERSONS = ["张建国（班长）", "李明华"]


class TestDataScreenData(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None
    empty_headers = {}
    empty_tenant_id = None
    building_high_id = None
    building_low_id = None
    created = {}

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = cls._ensure_tenant(db, TENANT_CODE, "大屏测试租户")
            cls.empty_tenant_id = cls._ensure_tenant(db, EMPTY_TENANT_CODE, "大屏空数据租户")

            role = db.query(Role).filter(Role.role_code == ROLE_CODE).first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code=ROLE_CODE,
                            role_name="大屏测试管理员", permissions=json.dumps(["*"]))
                db.add(role)
                db.commit()
                db.refresh(role)
                cls.created["role"] = role.id

            cls._ensure_user(db, USERNAME, cls.tenant_id, role.id, "大屏测试员")
            cls._ensure_user(db, "data-screen-empty", cls.empty_tenant_id, role.id, "空数据测试员")

            cls._seed_screen_data(db)
        finally:
            db.close()

        cls.client = TestClient(main.app)
        cls.headers = cls._login(USERNAME)
        cls.empty_headers = cls._login("data-screen-empty")

    @classmethod
    def _ensure_tenant(cls, db, code, name):
        tenant = db.query(Tenant).filter(Tenant.tenant_code == code).first()
        if not tenant:
            tenant = Tenant(tenant_code=code, tenant_name=name, status="active")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return tenant.id

    @classmethod
    def _ensure_user(cls, db, username, tenant_id, role_id, real_name):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            hashed, salt = hash_password(PASSWORD)
            user = User(username=username, password_hash=hashed, password_salt=salt,
                        real_name=real_name, role_id=role_id, status="active", tenant_id=tenant_id)
            db.add(user)
            db.commit()
            db.refresh(user)
            cls.created[f"user:{username}"] = user.id
        return user

    @classmethod
    def _login(cls, username):
        resp = cls.client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
        assert resp.status_code == 200, f"登录失败({username}): {resp.text}"
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def _seed_screen_data(cls, db):
        tenant_id = cls.tenant_id

        high = Building(tenant_id=tenant_id, building_code="SCREEN-A", building_name="高风险楼",
                        building_type="科研楼", floors=6, risk_score=85, risk_level="高风险")
        low = Building(tenant_id=tenant_id, building_code="SCREEN-B", building_name="低风险楼",
                       building_type="办公楼", floors=3, risk_score=30, risk_level="低风险")
        db.add_all([high, low])
        db.commit()
        db.refresh(high)
        db.refresh(low)
        cls.building_high_id = high.id
        cls.building_low_id = low.id
        cls.created["buildings"] = [high.id, low.id]

        devices = [
            Device(tenant_id=tenant_id, device_code="SC-HYD-1", device_name="东侧消火栓",
                   device_type="消火栓", location="高风险楼1层", status="正常",
                   building_id=high.id),
            Device(tenant_id=tenant_id, device_code="SC-HYD-2", device_name="西侧消火栓",
                   device_type="消火栓", location="高风险楼2层", status="离线",
                   building_id=high.id),
            Device(tenant_id=tenant_id, device_code="SC-PUMP-1", device_name="消防水泵",
                   device_type="消防水泵", location="高风险楼B1", status="正常",
                   building_id=high.id),
            Device(tenant_id=tenant_id, device_code="SC-ELEC-1", device_name="电气火灾探测器",
                   device_type="电气火灾监控", location="高风险楼3层", status="正常",
                   building_id=high.id),
            Device(tenant_id=tenant_id, device_code="SC-ELEC-2", device_name="配电箱监测",
                   device_type="配电箱", location="高风险楼4层", status="告警",
                   building_id=low.id),
            Device(tenant_id=tenant_id, device_code="SC-SMOKE-1", device_name="烟感探测器",
                   device_type="烟感探测器", location="低风险楼1层", status="正常",
                   building_id=low.id),
        ]
        db.add_all(devices)
        db.commit()
        for device in devices:
            db.refresh(device)
        cls.created["devices"] = [d.id for d in devices]

        # 电气设备的温度遥测：每台设备保留两条，接口必须取最新一条
        elec_ids = [d.id for d in devices if "电气" in d.device_type or "配电" in d.device_type]
        now = datetime.utcnow()

        # 「今日事件」「今日告警」按**本地日**过滤，而 `now - 几小时` 在本地 00:00-0X:00
        # 之间会落到本地昨天，让「今日」相关断言在凌晨无故变空。
        day_start = local_day_start_utc()

        def today_at(*, hours=0, minutes=0):
            """把种子时间放进本地今天，且不晚于当前时刻。"""
            candidate = now - timedelta(hours=hours, minutes=minutes)
            if candidate > day_start:
                return candidate
            # 凌晨跑测试时退回到「本地零点与当前时刻的中点」：既落在今天之内，
            # 也不会正好压在窗口边界上（`local_day_start_utc()` 的微秒位每次调用都略有不同）
            return day_start + (now - day_start) / 2

        db.add_all([
            DeviceTelemetry(tenant_id=tenant_id, device_id=elec_ids[0], temperature=41.0,
                            created_at=now - timedelta(hours=2)),
            DeviceTelemetry(tenant_id=tenant_id, device_id=elec_ids[0], temperature=63.5,
                            created_at=now - timedelta(minutes=5)),
            DeviceTelemetry(tenant_id=tenant_id, device_id=elec_ids[1], temperature=52.0,
                            created_at=now - timedelta(minutes=10)),
        ])

        # 四条隐患：灭火器过期/消火栓被遮挡 -> 消防设施；消防通道堵塞 -> 通道堵塞；电气线路老化 -> 电气安全
        db.add_all([
            InspectionRecord(tenant_id=tenant_id, device_id=devices[0].id, device_name="东侧消火栓",
                             location="高风险楼1层",
                             hazards=json.dumps(["消防通道堵塞", "灭火器过期", "电气线路老化"], ensure_ascii=False),
                             risk_score=70, risk_level="高风险", created_at=today_at(hours=3)),
            InspectionRecord(tenant_id=tenant_id, device_id=devices[1].id, device_name="西侧消火栓",
                             location="高风险楼2层",
                             hazards=json.dumps(["消火栓被遮挡"], ensure_ascii=False),
                             risk_score=40, risk_level="中风险", created_at=today_at(hours=1)),
        ])

        # 3 张工单：2 张已闭环 -> 整改率 66.7%
        db.add_all([
            FaultTicket(tenant_id=tenant_id, building_id=high.id, building_name="高风险楼",
                        title="消防通道堵塞整改", status="已完成", priority="高",
                        created_at=today_at(hours=4)),
            FaultTicket(tenant_id=tenant_id, building_id=high.id, building_name="高风险楼",
                        title="灭火器更换", status="已关闭", priority="中",
                        created_at=today_at(hours=5)),
            FaultTicket(tenant_id=tenant_id, building_id=low.id, building_name="低风险楼",
                        title="配电箱温度异常处理", status="处理中", priority="高",
                        created_at=today_at(minutes=30)),
        ])

        # 今日告警：1 条已处置 + 1 条待处置 -> 告警处置率 50%
        db.add_all([
            AlertRecord(tenant_id=tenant_id, alert_code="SC-AL-1", building_id=high.id,
                        building_name="高风险楼", location="3层", alert_type="烟雾浓度超限",
                        severity="critical", status="resolved", created_at=today_at(hours=2)),
            AlertRecord(tenant_id=tenant_id, alert_code="SC-AL-2", building_id=low.id,
                        building_name="低风险楼", location="1层", alert_type="温度偏高",
                        severity="low", status="pending", created_at=today_at(minutes=20)),
        ])

        # 视频通道：2 个启用（其中 1 个在线）+ 1 个停用（不计入在线率） -> 视频在线率 50%
        db.add_all([
            VideoChannel(tenant_id=tenant_id, channel_code="SC-CAM-1", channel_name="大厅",
                         platform="mock", host="127.0.0.1", enabled=True, status="online"),
            VideoChannel(tenant_id=tenant_id, channel_code="SC-CAM-2", channel_name="楼梯间",
                         platform="mock", host="127.0.0.1", enabled=True, status="offline"),
            VideoChannel(tenant_id=tenant_id, channel_code="SC-CAM-3", channel_name="停用通道",
                         platform="mock", host="127.0.0.1", enabled=False, status="offline"),
        ])

        # 真实排班：白班 08:00-20:00，覆盖绝大多数测试运行时间
        db.add(DutyShift(tenant_id=tenant_id, shift_name="白班", shift_type="day",
                         start_time="00:00", end_time="23:59", duty_date=datetime.now().date(),
                         persons=json.dumps(["张建国", "李明华"], ensure_ascii=False), status="active"))
        db.commit()

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            for model in (AlertRecord, FaultTicket, InspectionRecord, VideoChannel, DutyShift):
                db.query(model).filter(model.tenant_id.in_([cls.tenant_id, cls.empty_tenant_id])).delete(
                    synchronize_session=False
                )
            device_ids = cls.created.get("devices") or []
            if device_ids:
                db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id.in_(device_ids)).delete(
                    synchronize_session=False
                )
            db.query(Device).filter(Device.tenant_id.in_([cls.tenant_id, cls.empty_tenant_id])).delete(
                synchronize_session=False
            )
            db.query(Building).filter(Building.tenant_id.in_([cls.tenant_id, cls.empty_tenant_id])).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.username.in_([USERNAME, "data-screen-empty"])).delete(
                synchronize_session=False
            )
            if cls.created.get("role"):
                db.query(Role).filter(Role.id == cls.created["role"]).delete(synchronize_session=False)
            db.query(Tenant).filter(Tenant.tenant_code.in_([TENANT_CODE, EMPTY_TENANT_CODE])).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    def _screen(self, headers=None):
        resp = self.client.get("/api/dashboard/screen-data", headers=headers or self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    # ---------------- 真实数据必须对得上 ----------------

    def test_devices_section_matches_records(self):
        body = self._screen()["devices"]
        self.assertEqual(body["total"], 6)
        self.assertEqual(body["online"], 4, "正常状态设备数")
        self.assertEqual(body["offline"], 1)
        self.assertEqual(body["alarm"], 1)
        # 类型分布必须覆盖全部设备，且比例基于最大项归一
        self.assertEqual(sum(item["count"] for item in body["types"]), 6)
        self.assertIn("其他设备", {item["name"] for item in body["types"]})
        for item in body["types"]:
            self.assertGreaterEqual(item["percent"], 0)
            self.assertLessEqual(item["percent"], 100)

    def test_hazards_come_from_inspection_records(self):
        hazards = self._screen()["hazards"]
        self.assertEqual(hazards["total"], 4, "隐患条数应等于巡检记录中抽取出的隐患条目总数")
        self.assertEqual(hazards["ticketTotal"], 3)
        self.assertEqual(hazards["ticketClosed"], 2)
        self.assertEqual(hazards["rate"], 66.7, "整改率来自工单闭环比例")

        counts = {item["name"]: item["count"] for item in hazards["types"]}
        self.assertEqual(counts, {"消防设施": 2, "通道堵塞": 1, "电气安全": 1})
        self.assertNotEqual(hazards["total"], LEGACY_FAKE_VALUES["hazard_total"])
        self.assertNotEqual(hazards["rate"], LEGACY_FAKE_VALUES["hazard_rate"])

    def test_water_system_reports_real_device_status(self):
        water = self._screen()["waterSystem"]
        self.assertEqual(water["total"], 3, "消火栓 x2 + 消防水泵 x1")
        self.assertEqual(water["online"], 2)
        self.assertEqual(water["offline"], 1)
        self.assertEqual(water["runningPumps"], 1)
        # 没有数据源的指标必须为 None，不能编造
        self.assertIsNone(water["pressure"])
        self.assertIsNone(water["tankLevel"])
        self.assertNotEqual(water["tankLevel"], LEGACY_FAKE_VALUES["tank_level"])

    def test_electric_system_uses_latest_telemetry(self):
        electric = self._screen()["electricSystem"]
        self.assertEqual(electric["total"], 2)
        self.assertEqual(electric["online"], 1)
        self.assertEqual(electric["alarm"], 1)
        self.assertEqual(electric["warningCircuits"], 1)
        self.assertEqual(electric["maxTemp"], 63.5, "应取每台设备最新一条遥测中的最高温度")
        self.assertIsNone(electric["maxLeakage"], "剩余电流无数据源，必须为 None")

    def test_duty_info_comes_from_shift_table(self):
        duty = self._screen()["dutyInfo"]
        self.assertTrue(duty["hasDuty"])
        self.assertEqual(duty["shift"], "白班值班中")
        self.assertEqual(duty["persons"], ["张建国", "李明华"])
        self.assertNotEqual(duty["persons"], LEGACY_FAKE_PERSONS)

    def test_indicators_are_four_real_metrics(self):
        indicators = self._screen()["indicators"]
        names = [item["name"] for item in indicators]
        self.assertEqual(names, ["设备在线率", "隐患整改率", "告警处置率", "视频在线率"])
        for fake in LEGACY_FAKE_INDICATORS:
            self.assertNotIn(fake, names, f"「{fake}」没有真实数据源，不应再出现在大屏上")

        values = {item["name"]: item["value"] for item in indicators}
        self.assertEqual(values["设备在线率"], 66.7)
        self.assertEqual(values["隐患整改率"], 66.7)
        self.assertEqual(values["告警处置率"], 50.0)
        self.assertEqual(values["视频在线率"], 50.0)

    def test_todos_and_risk_rank_are_real(self):
        body = self._screen()
        todos = body["todos"]
        self.assertEqual(len(todos), 1, "只有 1 张未闭环工单")
        self.assertEqual(todos[0]["status"], "处理中")
        self.assertEqual(todos[0]["title"], "配电箱温度异常处理")
        self.assertEqual(todos[0]["level"], "high", "优先级为「高」的工单应标记为 high")

        rank = body["riskRank"]
        self.assertEqual([item["name"] for item in rank], ["高风险楼", "低风险楼"])
        self.assertEqual(rank[0]["value"], 85.0)
        self.assertEqual(rank[0]["color"], "#ef4444")

    def test_today_events_merge_real_records(self):
        events = self._screen()["todayEvents"]
        self.assertTrue(events, "今日有告警/巡检/工单，事件列表不应为空")
        types = {item["type"] for item in events}
        self.assertIn("alarm", types)
        self.assertIn("inspection", types)
        self.assertIn("maintenance", types)
        for item in events:
            self.assertNotIn("烟感报警，已派单处置", item["title"], "不应再返回写死的示例事件")
            self.assertRegex(item["time"], r"^\d{2}:\d{2}$")

    def test_buildings_carry_real_aggregates(self):
        body = self._screen()["buildings"]
        self.assertEqual(body["total"], 2)
        by_name = {item["name"]: item for item in body["list"]}
        high = by_name["高风险楼"]
        self.assertEqual(high["deviceCount"], 4)
        self.assertEqual(high["alarmCount"], 1)
        self.assertEqual(high["status"], "alarm", "存在 critical 告警的建筑状态应为 alarm")
        self.assertEqual(high["riskScore"], 85.0)

        low = by_name["低风险楼"]
        self.assertEqual(low["deviceCount"], 2)
        self.assertEqual(low["status"], "warning", "仅有低危告警时状态为 warning")

    def test_buildings_carry_geometry_for_screen_scene(self):
        """3D 场景/热力图按建筑台账渲染，必须拿到真实几何字段而不是前端硬编码。"""
        body = self._screen()["buildings"]
        for item in body["list"]:
            self.assertIn("latitude", item)
            self.assertIn("longitude", item)
            self.assertIn("type", item)
            self.assertIn("floors", item)
            self.assertIn("area", item)
            # x_coord/y_coord 在 Building 模型上并不存在，之前恒为 0，属误导性字段
            self.assertNotIn("x", item, "不应再下发恒为 0 的 x")
            self.assertNotIn("y", item, "不应再下发恒为 0 的 y")

        by_name = {item["name"]: item for item in body["list"]}
        self.assertEqual(by_name["高风险楼"]["floors"], 6)
        self.assertEqual(by_name["高风险楼"]["type"], "科研楼")
        self.assertEqual(by_name["低风险楼"]["floors"], 3)

    def test_overview_stats_no_longer_emits_fake_coordinates(self):
        """同源问题：`/api/overview/stats` 也曾下发恒为 0 的 x / y。"""
        resp = self.client.get("/api/overview/stats", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        for item in resp.json()["buildings"]["list"]:
            self.assertNotIn("x", item, "不应再下发恒为 0 的 x")
            self.assertNotIn("y", item, "不应再下发恒为 0 的 y")

    def test_video_list_from_channel_ledger(self):
        videos = self._screen()["videoList"]
        self.assertEqual(len(videos), 2, "只返回启用的通道（停用通道不展示）")
        names = {item["name"] for item in videos}
        self.assertEqual(names, {"大厅", "楼梯间"})
        online = {item["name"]: item["online"] for item in videos}
        self.assertTrue(online["大厅"])
        self.assertFalse(online["楼梯间"])

    def test_screen_payload_has_no_unused_or_duplicated_fields(self):
        """审计发现的冗余下发字段：前端从未消费，已停止下发。

        `maxTemperature` 与 `maxTemp` 同值（同一份数据两个名字）、`lastReportAt`
        前端从不读取，这类字段看着像有数据实则无人使用，只会误导后续接入方。
        """
        body = self._screen()
        self.assertNotIn("warning", body["devices"], "大屏只用 total / online / offline")
        self.assertNotIn("lastReportAt", body["waterSystem"])
        self.assertNotIn("lastReportAt", body["electricSystem"])
        self.assertEqual(body["electricSystem"]["maxTemp"], 63.5, "真实值只保留一个字段名")
        self.assertNotIn("maxTemperature", body["electricSystem"])
        self.assertNotIn("shiftName", body["dutyInfo"])
        for channel in body["videoList"]:
            self.assertNotIn("location", channel)
        for item in body["riskRank"]:
            self.assertNotIn("level", item)

    def test_today_window_is_a_local_day_boundary(self):
        """回归守卫：「今日」窗口边界必须换算到 UTC。

        改造前拿本地零点直接和 UTC 存的时间列比较，UTC+8 下「今日」从本地 08:00 才开始，
        本地 00:00-08:00 产生的告警不算今日。这里塞入一条「本地今天 00:01」的告警，
        它在旧实现下必定被漏掉，因此本用例在任意运行时刻都能检出该回归。
        """
        boundary = local_day_start_utc()
        before = self._screen()["alarms"]["stats"]["today"]

        db = SessionLocal()
        try:
            db.add_all([
                AlertRecord(tenant_id=self.tenant_id, alert_code="SC-TZ-0001",
                            building_id=self.building_high_id, building_name="高风险楼",
                            location="1层", alert_type="凌晨告警", severity="low",
                            status="pending", created_at=boundary + timedelta(minutes=1)),
                AlertRecord(tenant_id=self.tenant_id, alert_code="SC-TZ-0002",
                            building_id=self.building_high_id, building_name="高风险楼",
                            location="1层", alert_type="昨夜告警", severity="low",
                            status="pending", created_at=boundary - timedelta(minutes=1)),
            ])
            db.commit()
        finally:
            db.close()

        try:
            body = self._screen()
            self.assertEqual(
                body["alarms"]["stats"]["today"] - before, 1,
                "本地今天 00:01 的告警必须计入今日，本地昨天 23:59 的不应计入",
            )
            # 趋势的「今日」桶与今日告警数同口径，必须一致
            buckets = [item for item in body["alarms"]["trend"] if item["date"] == "今日"]
            self.assertEqual(len(buckets), 1)
            self.assertEqual(buckets[0]["count"], body["alarms"]["stats"]["today"])
        finally:
            db = SessionLocal()
            try:
                db.query(AlertRecord).filter(
                    AlertRecord.alert_code.in_(["SC-TZ-0001", "SC-TZ-0002"])
                ).delete(synchronize_session=False)
                db.commit()
            finally:
                db.close()

    def test_realtime_alarm_relative_time_is_not_timezone_shifted(self):
        """回归守卫：「X分钟前」要用 UTC 比较。

        改造前是本地时间减 UTC 的 `created_at`，相差一个时区偏移，
        刚产生的告警会显示成「8小时前」（UTC+8）。
        """
        db = SessionLocal()
        try:
            db.add(AlertRecord(tenant_id=self.tenant_id, alert_code="SC-TZ-0003",
                               building_id=self.building_high_id, building_name="高风险楼",
                               location="1层", alert_type="刚发生告警", severity="high",
                               status="pending", created_at=datetime.utcnow()))
            db.commit()
        finally:
            db.close()

        try:
            fresh = [
                item for item in self._screen()["alarms"]["realtime"]
                if item["title"] == "刚发生告警"
            ]
            self.assertTrue(fresh, "刚写入的告警应出现在实时告警里")
            self.assertEqual(fresh[0]["time"], "刚刚", "刚产生的告警不应显示成若干小时前")
        finally:
            db = SessionLocal()
            try:
                db.query(AlertRecord).filter(
                    AlertRecord.alert_code == "SC-TZ-0003"
                ).delete(synchronize_session=False)
                db.commit()
            finally:
                db.close()

    # ---------------- 没有数据时必须为空，而不是常量 ----------------

    def test_empty_tenant_returns_zeros_not_constants(self):
        body = self._screen(self.empty_headers)
        self.assertEqual(body["hazards"]["total"], 0)
        self.assertEqual(body["hazards"]["rate"], 0.0)
        self.assertEqual(body["hazards"]["types"], [])
        self.assertFalse(body["dutyInfo"]["hasDuty"])
        self.assertEqual(body["dutyInfo"]["persons"], [])
        self.assertEqual(body["todayEvents"], [])
        self.assertEqual(body["todos"], [])
        self.assertEqual(body["riskRank"], [])
        self.assertEqual(body["waterSystem"]["total"], 0)
        self.assertEqual(body["videoList"], [])
        for item in body["indicators"]:
            self.assertEqual(item["value"], 0.0, f"{item['name']} 无数据时应为 0")

    # ---------------- 租户隔离 ----------------

    def test_tenant_isolation(self):
        mine = self._screen()
        other = self._screen(self.empty_headers)
        self.assertEqual(mine["devices"]["total"], 6)
        self.assertEqual(other["devices"]["total"], 0)
        self.assertEqual(other["buildings"]["total"], 0)
        mine_ids = {item["id"] for item in mine["todos"]}
        other_ids = {item["id"] for item in other["todos"]}
        self.assertTrue(mine_ids)
        self.assertEqual(other_ids, set())

    def test_endpoint_requires_authentication(self):
        self.assertEqual(self.client.get("/api/dashboard/screen-data").status_code, 401)


if __name__ == "__main__":
    unittest.main()
