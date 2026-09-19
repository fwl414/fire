"""值班排班写接口

排班此前只有只读接口：排班表、值班记录、交接班都只能看不能改，前端「新增排班 / 保存 /
交接班」全是假动作。本文件固化补齐后的写入行为与校验规则：

- 写操作需要 `duty:manage` 权限；
- 同一天不能有两个同名班次；同一个人同一天不能被排进两个班次（跨天不冲突）；
- 日期与时间格式必须合法；
- 更新是局部更新，未提交的字段（含 persons 里的 id/role）不能被抹掉；
- 跨租户按「不存在」处理：既改不动别人的排班，也不泄露其存在性。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

import main
from database import DutyHandover, DutyRecord, DutyShift, Role, SessionLocal, Tenant, User, hash_password, init_db
from services.auth_service import create_access_token

TENANT_A_CODE = "duty-test-tenant-a"
TENANT_B_CODE = "duty-test-tenant-b"
ADMIN_USER = "duty-test-admin"
VIEWER_USER = "duty-test-viewer"
OTHER_TENANT_USER = "duty-test-other"
PASSWORD = "Test#12345"
ADMIN_ROLE = "duty-test-admin-role"
VIEWER_ROLE = "duty-test-viewer-role"
SHIFT_DATE = "2031-05-06"
NEXT_DAY = "2031-05-07"


class TestDutyScheduleWrite(unittest.TestCase):

    client = None
    tenant_a_id = None
    tenant_b_id = None
    token_admin = ""
    token_viewer = ""
    token_other_tenant = ""
    created = {}

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_a_id = cls._ensure_tenant(db, TENANT_A_CODE, "排班测试租户A")
            cls.tenant_b_id = cls._ensure_tenant(db, TENANT_B_CODE, "排班测试租户B")
            admin_role = cls._ensure_role(db, ADMIN_ROLE, cls.tenant_a_id, ["*"])
            viewer_role = cls._ensure_role(
                db, VIEWER_ROLE, cls.tenant_a_id, ["dashboard:view"]
            )
            admin = cls._ensure_user(db, ADMIN_USER, cls.tenant_a_id, admin_role.id)
            viewer = cls._ensure_user(db, VIEWER_USER, cls.tenant_a_id, viewer_role.id)
            other = cls._ensure_user(db, OTHER_TENANT_USER, cls.tenant_b_id, admin_role.id)
            cls.token_admin = create_access_token(admin)
            cls.token_viewer = create_access_token(viewer)
            cls.token_other_tenant = create_access_token(other)
        finally:
            db.close()

        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            tenant_ids = [cls.tenant_a_id, cls.tenant_b_id]
            for model in (DutyShift, DutyRecord, DutyHandover):
                db.query(model).filter(model.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
            db.query(User).filter(
                User.username.in_([ADMIN_USER, VIEWER_USER, OTHER_TENANT_USER])
            ).delete(synchronize_session=False)
            db.query(Role).filter(Role.role_code.in_([ADMIN_ROLE, VIEWER_ROLE])).delete(
                synchronize_session=False
            )
            db.query(Tenant).filter(Tenant.tenant_code.in_([TENANT_A_CODE, TENANT_B_CODE])).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

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
                real_name=username,
                role_id=role_id,
                status="active",
                tenant_id=tenant_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(DutyShift).filter(DutyShift.tenant_id == self.tenant_a_id).delete(
                synchronize_session=False
            )
            db.query(DutyRecord).filter(DutyRecord.tenant_id == self.tenant_a_id).delete(
                synchronize_session=False
            )
            db.query(DutyHandover).filter(DutyHandover.tenant_id == self.tenant_a_id).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()

    # ---------------- 工具 ----------------

    def _post(self, path, payload, token=None):
        return self.client.post(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {token or self.token_admin}"},
        )

    def _put(self, path, payload, token=None):
        return self.client.put(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {token or self.token_admin}"},
        )

    def _delete(self, path, token=None):
        return self.client.delete(
            path, headers={"Authorization": f"Bearer {token or self.token_admin}"}
        )

    def _get(self, path, token=None):
        return self.client.get(
            path, headers={"Authorization": f"Bearer {token or self.token_admin}"}
        )

    def _create_shift(self, **overrides):
        payload = {
            "shift_name": "白班",
            "shift_type": "day",
            "start_time": "08:00",
            "end_time": "20:00",
            "duty_date": SHIFT_DATE,
            "persons": [{"id": 1, "name": "张建国", "role": "值班员"}],
        }
        payload.update(overrides)
        resp = self._post("/api/duty/shifts", payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["shift"]

    def _list_shifts(self, duty_date=SHIFT_DATE):
        resp = self._get(f"/api/duty/shifts?date={duty_date}")
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    # ---------------- 权限 ----------------

    def test_write_requires_duty_manage_permission(self):
        """没有 duty:manage 的账号不能排班（读接口仍然可用）。"""
        resp = self._post("/api/duty/shifts", {"shift_name": "白班", "duty_date": SHIFT_DATE},
                          token=self.token_viewer)
        self.assertEqual(resp.status_code, 403, resp.text)

        self.assertEqual(self._get("/api/duty/shifts", token=self.token_viewer).status_code, 200)

    # ---------------- 排班 ----------------

    def test_created_shift_is_persisted_and_listed(self):
        created = self._create_shift()

        self.assertGreater(created["id"], 0)
        self.assertEqual(created["shiftName"], "白班")
        # persons 必须原样保留库里的结构（前端按 p.name / p.role 取值）
        self.assertEqual(created["persons"], [{"id": 1, "name": "张建国", "role": "值班员"}])

        listed = self._list_shifts()
        self.assertEqual([s["id"] for s in listed], [created["id"]])
        self.assertEqual(listed[0]["startTime"], "08:00")
        self.assertEqual(listed[0]["persons"], created["persons"])

    def test_string_persons_are_kept_as_strings(self):
        """历史数据里 persons 也可能是纯姓名数组，不能被强行升级成对象。"""
        created = self._create_shift(shift_name="夜班", persons=["李四"])

        self.assertEqual(created["persons"], ["李四"])
        self.assertEqual(self._list_shifts()[0]["persons"], ["李四"])

    def test_shift_list_supports_date_range(self):
        """周视图按区间取数：区间外的班次不能出现，格式不对则忽略该边界。

        此前只能按单日 `date=` 筛，前端周视图只好把班次表整个拉下来自己筛，
        或者干脆写死一周的演示数据。
        """
        inside = self._create_shift()
        self._create_shift(duty_date="2031-05-04")
        after = self._create_shift(duty_date="2031-05-12")

        resp = self._get("/api/duty/shifts?start_date=2031-05-05&end_date=2031-05-11")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual([s["id"] for s in resp.json()], [inside["id"]])

        # 只给一端也能用
        resp = self._get("/api/duty/shifts?start_date=2031-05-07")
        self.assertEqual([s["id"] for s in resp.json()], [after["id"]])

        # 格式不对就忽略该边界，不因为一个参数把整页打成报错
        resp = self._get("/api/duty/shifts?start_date=不是日期")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()), 3)

    def test_same_shift_name_on_same_day_is_rejected(self):
        self._create_shift()

        resp = self._post("/api/duty/shifts", {
            "shift_name": "白班", "duty_date": SHIFT_DATE, "persons": ["李四"],
        })
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("已存在班次", resp.json()["message"])

        # 换一天就不冲突
        self._create_shift(duty_date=NEXT_DAY)

    def test_same_person_cannot_be_scheduled_twice_on_one_day(self):
        self._create_shift(persons=["张建国"])

        conflict = self._post("/api/duty/shifts", {
            "shift_name": "夜班", "duty_date": SHIFT_DATE, "persons": [{"name": "张建国"}],
        })
        self.assertEqual(conflict.status_code, 400, conflict.text)
        self.assertIn("重复排班", conflict.json()["message"])

        # 换人就行
        self._create_shift(shift_name="夜班", start_time="20:00", end_time="08:00", persons=["李四"])
        # 同一个人排到另一天也行
        self._create_shift(shift_name="夜班", duty_date=NEXT_DAY, persons=["张建国"])

    def test_invalid_date_and_time_are_rejected(self):
        bad_date = self._post("/api/duty/shifts", {"shift_name": "白班", "duty_date": "2031/05/06"})
        self.assertEqual(bad_date.status_code, 400, bad_date.text)
        self.assertIn("YYYY-MM-DD", bad_date.json()["message"])

        bad_time = self._post("/api/duty/shifts", {
            "shift_name": "白班", "duty_date": SHIFT_DATE, "start_time": "25:00",
        })
        self.assertEqual(bad_time.status_code, 400, bad_time.text)
        self.assertIn("HH:MM", bad_time.json()["message"])

        empty_name = self._post("/api/duty/shifts", {"shift_name": "  ", "duty_date": SHIFT_DATE})
        self.assertEqual(empty_name.status_code, 400, empty_name.text)
        self.assertIn("班次名称", empty_name.json()["message"])

    def test_update_keeps_fields_that_were_not_submitted(self):
        created = self._create_shift()

        resp = self._put(f"/api/duty/shifts/{created['id']}", {"status": "inactive"})
        self.assertEqual(resp.status_code, 200, resp.text)

        db = SessionLocal()
        try:
            shift = db.query(DutyShift).filter(DutyShift.id == created["id"]).one()
            self.assertEqual(shift.status, "inactive")
            # persons 未提交时必须原样保留（含 id / role），不能被压成纯姓名
            self.assertEqual(json.loads(shift.persons), [{"id": 1, "name": "张建国", "role": "值班员"}])
            self.assertEqual(shift.shift_name, "白班")
        finally:
            db.close()

    def test_update_rejects_conflicts_with_other_shifts(self):
        first = self._create_shift(persons=["张建国"])
        self._create_shift(shift_name="夜班", persons=["李四"])

        resp = self._put(f"/api/duty/shifts/{first['id']}", {"shift_name": "夜班"})
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("已存在班次", resp.json()["message"])

        # 改成自己原来的名字不算冲突
        same = self._put(f"/api/duty/shifts/{first['id']}", {"shift_name": "白班", "status": "active"})
        self.assertEqual(same.status_code, 200, same.text)

    def test_delete_removes_the_shift(self):
        created = self._create_shift()

        resp = self._delete(f"/api/duty/shifts/{created['id']}")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._list_shifts(), [])

        self.assertEqual(self._delete(f"/api/duty/shifts/{created['id']}").status_code, 404)

    def test_other_tenant_cannot_touch_the_shift(self):
        created = self._create_shift()

        update = self._put(
            f"/api/duty/shifts/{created['id']}", {"shift_name": "被改掉的班次"},
            token=self.token_other_tenant,
        )
        delete = self._delete(f"/api/duty/shifts/{created['id']}", token=self.token_other_tenant)
        self.assertEqual(update.status_code, 404, update.text)
        self.assertEqual(delete.status_code, 404, delete.text)

        listed = self._list_shifts()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["shiftName"], "白班")

    # ---------------- 值班记录 ----------------

    def test_duty_record_roundtrip(self):
        shift = self._create_shift()

        created = self._post("/api/duty/records", {
            "record_date": SHIFT_DATE,
            "shift_id": shift["id"],
            "duty_person": "张建国",
            "weather": "晴",
            "alarm_count": 3,
            "handled_count": 2,
            "content": "夜间巡检正常",
        })
        self.assertEqual(created.status_code, 200, created.text)
        record = created.json()["record"]
        self.assertEqual(record["shiftName"], "白班", "未传班次名时按所选排班回填")
        self.assertEqual(record["alarmCount"], 3)

        listed = self._get("/api/duty/records").json()
        self.assertEqual([r["id"] for r in listed["list"]], [record["id"]])

        updated = self._put(f"/api/duty/records/{record['id']}", {"handled_count": 3})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["record"]["handledCount"], 3)

        self.assertEqual(self._delete(f"/api/duty/records/{record['id']}").status_code, 200)
        self.assertEqual(self._get("/api/duty/records").json()["total"], 0)

    def test_record_list_supports_date_range(self):
        """日期区间筛选必须真的过滤（前端那个日期范围控件此前是死的）。"""
        self._post("/api/duty/records", {"record_date": SHIFT_DATE, "duty_person": "张建国"})
        self._post("/api/duty/records", {"record_date": NEXT_DAY, "duty_person": "李明华"})
        self.assertEqual(self._get("/api/duty/records").json()["total"], 2)

        only_next = self._get(f"/api/duty/records?start_date={NEXT_DAY}").json()
        self.assertEqual(only_next["total"], 1)
        self.assertEqual(only_next["list"][0]["dutyPerson"], "李明华")

        until_first = self._get(f"/api/duty/records?end_date={SHIFT_DATE}").json()
        self.assertEqual(until_first["total"], 1)
        self.assertEqual(until_first["list"][0]["dutyPerson"], "张建国")

    def test_duty_record_requires_date_and_person(self):
        no_date = self._post("/api/duty/records", {"duty_person": "张建国"})
        self.assertEqual(no_date.status_code, 400, no_date.text)

        no_person = self._post("/api/duty/records", {"record_date": SHIFT_DATE, "duty_person": " "})
        self.assertEqual(no_person.status_code, 400, no_person.text)
        self.assertIn("值班人员", no_person.json()["message"])

    # ---------------- 交接班 ----------------

    def test_handover_roundtrip(self):
        created = self._post("/api/duty/handovers", {
            "from_person": "张建国",
            "to_person": "李明华",
            "pending_matters": "配电室温度偏高，需复查",
        })
        self.assertEqual(created.status_code, 200, created.text)
        handover = created.json()["handover"]
        self.assertEqual(handover["fromPerson"], "张建国")

        listed = self._get("/api/duty/handovers").json()
        self.assertEqual([h["id"] for h in listed["list"]], [handover["id"]])
        self.assertEqual(listed["list"][0]["pendingMatters"], "配电室温度偏高，需复查")
        self.assertEqual(self._delete(f"/api/duty/handovers/{handover['id']}").status_code, 200)
        self.assertEqual(self._get("/api/duty/handovers").json()["total"], 0)

    def test_handover_list_shows_the_shift_name(self):
        """交接班表只存 shift_id，列表要能显示班次名（此前前端这一列恒为空）。"""
        shift = self._create_shift()

        created = self._post("/api/duty/handovers", {
            "shift_id": shift["id"], "from_person": "张建国", "to_person": "李明华",
        })
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["handover"]["shiftName"], "白班")

        listed = self._get("/api/duty/handovers").json()["list"]
        self.assertEqual(listed[0]["shiftName"], "白班")

    def test_handover_requires_both_persons(self):
        resp = self._post("/api/duty/handovers", {"from_person": "张建国"})
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("交班人", resp.json()["message"])


if __name__ == "__main__":
    unittest.main()
