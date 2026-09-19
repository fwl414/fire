"""业务实体图谱

图谱的全部内容都来自真实业务表（外加运行时库的知识条目），本文件固化四点：

- 实体 → 节点、外键/既有字段 → 边，且**跨表边不能因为读取顺序而丢失**
  （告警→工单这条边最容易踩：工单比告警后读，先连边就会指向一个还不存在的节点）
- 租户隔离：别的租户的建筑/设备/告警进不了本租户的图，查不存在的实体返回 404
- 巡检记录里的隐患（JSON 文本）要变成隐患类型节点，能对上规则表的标 `inRuleTable`
- 上限与截断要如实回报，而不是悄悄截断
"""
import json
import os
import sys
import tempfile
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
    Floor,
    InspectionRecord,
    Role,
    SessionLocal,
    Tenant,
    User,
    hash_password,
    init_db,
)
from services import entity_graph_service
from services.auth_service import create_access_token

TENANT_CODE = "kg-tenant"
OTHER_TENANT_CODE = "kg-tenant-other"
ADMIN_USER = "kg-admin"
PASSWORD = "Test#12345"
ADMIN_ROLE = "kg-admin-role"

HAZARD_IN_RULE_TABLE = "消防通道堵塞"
HAZARD_FREE_TEXT = "话说不上来的问题"


class _GraphFixture(unittest.TestCase):
    """造一条完整链路：建筑 → 楼层 → 设备 → 告警 → 工单，另有设备上的巡检记录。"""

    @classmethod
    def setUpClass(cls):
        init_db()
        # 知识条目在运行时库里，用临时库保证「有没有连上知识节点」这件事是确定的
        cls.runtime_dir = tempfile.TemporaryDirectory()
        cls._old_runtime_env = os.environ.get("RUNTIME_DB_PATH")
        os.environ["RUNTIME_DB_PATH"] = os.path.join(cls.runtime_dir.name, "runtime.db")
        cls._seed_runtime_knowledge()

        cls.db = SessionLocal()
        cls.tenant_id = cls._ensure_tenant(cls.db, TENANT_CODE, "图谱测试租户").id
        cls.other_tenant_id = cls._ensure_tenant(cls.db, OTHER_TENANT_CODE, "图谱测试租户B").id
        cls._seed_business(cls.db, cls.tenant_id, prefix="A")
        cls._seed_business(cls.db, cls.other_tenant_id, prefix="B")

    @classmethod
    def tearDownClass(cls):
        for tenant_id in (cls.tenant_id, cls.other_tenant_id):
            cls._purge(cls.db, tenant_id)
            cls.db.query(Tenant).filter(Tenant.id == tenant_id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        if cls._old_runtime_env is None:
            os.environ.pop("RUNTIME_DB_PATH", None)
        else:
            os.environ["RUNTIME_DB_PATH"] = cls._old_runtime_env
        cls.runtime_dir.cleanup()

    @classmethod
    def _seed_runtime_knowledge(cls):
        from services.runtime_db import connect_runtime_db

        conn = connect_runtime_db()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS rag_entries (id TEXT PRIMARY KEY, title TEXT, category TEXT,"
                " content TEXT, keywords TEXT, source TEXT, enabled INTEGER, created_at TEXT, updated_at TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO rag_entries VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                ("RAG-TEST", "疏散通道管理要求", "疏散通道", "通道不得占用",
                 f"{HAZARD_IN_RULE_TABLE},通道,疏散", "测试来源", "2031-01-01 00:00:00", "2031-01-01 00:00:00"),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def _ensure_tenant(cls, db, code, name):
        tenant = db.query(Tenant).filter(Tenant.tenant_code == code).first()
        if not tenant:
            tenant = Tenant(tenant_code=code, tenant_name=name, status="active")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return tenant

    @classmethod
    def _purge(cls, db, tenant_id):
        for model in (InspectionRecord, AlertRecord, FaultTicket):
            db.query(model).filter(model.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Device).filter(Device.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Floor).filter(Floor.tenant_id == tenant_id).delete(synchronize_session=False)
        db.query(Building).filter(Building.tenant_id == tenant_id).delete(synchronize_session=False)
        db.commit()

    @classmethod
    def _seed_business(cls, db, tenant_id, prefix):
        cls._purge(db, tenant_id)
        building = Building(
            tenant_id=tenant_id, building_code=f"{prefix}-BLD-1", building_name=f"{prefix}座综合楼",
            floors=3, area=1000.0, risk_score=66, risk_level="高风险",
        )
        db.add(building)
        db.flush()
        floor = Floor(tenant_id=tenant_id, building_id=building.id, floor_name=f"{prefix}座2层", floor_number=2)
        db.add(floor)
        db.flush()
        device = Device(
            tenant_id=tenant_id, device_code=f"{prefix}-DEV-1", device_name=f"{prefix}烟感01",
            device_type="烟感探测器", status="正常", building_id=building.id, floor_id=floor.id,
        )
        db.add(device)
        db.flush()
        ticket = FaultTicket(
            tenant_id=tenant_id, building_id=building.id, device_id=device.id,
            title=f"{prefix}座烟感异常处置", status="待受理", risk_level="高风险",
        )
        db.add(ticket)
        db.flush()
        alert = AlertRecord(
            tenant_id=tenant_id, alert_code=f"{prefix}-ALERT-1", device_id=device.id,
            building_id=building.id, building_name=building.building_name,
            alert_type="smoke_high", severity="critical", status="pending",
            workorder_id=ticket.id, repeat_count=2, created_at=datetime.utcnow(),
        )
        db.add(alert)
        db.add(InspectionRecord(
            tenant_id=tenant_id, device_id=device.id, device_name=device.device_name,
            location=f"{prefix}座2层", risk_score=30, risk_level="中风险",
            hazards=json.dumps([HAZARD_IN_RULE_TABLE, HAZARD_FREE_TEXT], ensure_ascii=False),
            created_at=datetime.utcnow(),
        ))
        db.commit()

        fixture = {"building": building.id, "floor": floor.id, "device": device.id,
                   "ticket": ticket.id, "alert": alert.id}
        if prefix == "A":
            cls.ids = fixture
        else:
            cls.other_ids = fixture


class TestEntityGraphService(_GraphFixture):

    def _node_ids(self, graph):
        return {node["id"] for node in graph["nodes"]}

    def _edge_set(self, graph):
        return {(edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]}

    def test_entities_and_relations_come_from_business_tables(self):
        graph = entity_graph_service.build_graph(self.db, self.tenant_id)
        nodes = self._node_ids(graph)
        edges = self._edge_set(graph)

        for expected in (
            f"building:{self.ids['building']}",
            f"floor:{self.ids['floor']}",
            f"device:{self.ids['device']}",
            f"alert:{self.ids['alert']}",
            f"workorder:{self.ids['ticket']}",
        ):
            self.assertIn(expected, nodes)

        # 跨表边一条都不能少：告警→工单这条尤其容易因为读取顺序被丢掉
        self.assertIn((f"building:{self.ids['building']}", "contains", f"floor:{self.ids['floor']}"), edges)
        self.assertIn((f"floor:{self.ids['floor']}", "locates", f"device:{self.ids['device']}"), edges)
        self.assertIn((f"device:{self.ids['device']}", "triggers", f"alert:{self.ids['alert']}"), edges)
        self.assertIn((f"alert:{self.ids['alert']}", "creates", f"workorder:{self.ids['ticket']}"), edges)

        building_node = next(n for n in graph["nodes"] if n["id"] == f"building:{self.ids['building']}")
        self.assertEqual(building_node["label"], "A座综合楼")
        self.assertEqual(building_node["riskLevel"], "高风险")

    def test_inspection_hazards_become_hazard_nodes_and_link_to_knowledge(self):
        graph = entity_graph_service.build_graph(self.db, self.tenant_id)
        edges = self._edge_set(graph)
        hazard_nodes = {node["id"]: node for node in graph["nodes"] if node["type"] == "hazard"}

        self.assertIn(f"hazard:{HAZARD_IN_RULE_TABLE}", hazard_nodes)
        self.assertIn(f"hazard:{HAZARD_FREE_TEXT}", hazard_nodes)
        # 能对上规则表的标出类别与基础分；对不上的是自由文本，不硬塞类别
        self.assertTrue(hazard_nodes[f"hazard:{HAZARD_IN_RULE_TABLE}"]["inRuleTable"])
        self.assertEqual(hazard_nodes[f"hazard:{HAZARD_IN_RULE_TABLE}"]["category"], "疏散通道")
        self.assertFalse(hazard_nodes[f"hazard:{HAZARD_FREE_TEXT}"]["inRuleTable"])

        inspection_id = next(
            node["id"] for node in graph["nodes"] if node["type"] == "inspection"
        )
        self.assertIn((inspection_id, "found", f"hazard:{HAZARD_IN_RULE_TABLE}"), edges)
        # 知识条目按「隐患名出现在标题或关键词里」连边（这条来自测试临时运行时库）
        self.assertIn((f"hazard:{HAZARD_IN_RULE_TABLE}", "documented_in", "knowledge:RAG-TEST"), edges)
        self.assertGreaterEqual(graph["knowledge_edges"], 1)

    def test_other_tenants_entities_are_not_in_the_graph(self):
        graph = entity_graph_service.build_graph(self.db, self.tenant_id)
        nodes = self._node_ids(graph)
        self.assertNotIn(f"building:{self.other_ids['building']}", nodes)
        self.assertNotIn(f"alert:{self.other_ids['alert']}", nodes)

    def test_subgraph_expands_with_depth(self):
        depth_one = entity_graph_service.subgraph(
            self.db, self.tenant_id, "building", str(self.ids["building"]), depth=1
        )
        depth_three = entity_graph_service.subgraph(
            self.db, self.tenant_id, "building", str(self.ids["building"]), depth=3
        )
        self.assertTrue(depth_one["found"])
        self.assertEqual(depth_one["center"]["id"], f"building:{self.ids['building']}")

        one_ids = {node["id"] for node in depth_one["nodes"]}
        three_ids = {node["id"] for node in depth_three["nodes"]}
        self.assertIn(f"floor:{self.ids['floor']}", one_ids)
        self.assertNotIn(f"alert:{self.ids['alert']}", one_ids)
        self.assertIn(f"device:{self.ids['device']}", three_ids)
        self.assertIn(f"alert:{self.ids['alert']}", three_ids)
        # 子图里的边必须两端都在子图内
        for edge in depth_one["edges"]:
            self.assertIn(edge["source"], one_ids)
            self.assertIn(edge["target"], one_ids)

    def test_unknown_entity_reports_not_found(self):
        result = entity_graph_service.subgraph(
            self.db, self.other_tenant_id, "building", str(self.ids["building"]), depth=1
        )
        self.assertFalse(result["found"])
        self.assertEqual(result["nodes"], [])

    def test_limits_are_reported_as_truncation(self):
        graph = entity_graph_service.build_graph(self.db, self.tenant_id, {"alerts": 1, "workorders": 1})
        self.assertTrue(graph["truncated"]["alerts"])
        self.assertEqual(len([n for n in graph["nodes"] if n["type"] == "alert"]), 1)

    def test_overview_counts_and_sources(self):
        overview = entity_graph_service.overview(self.db, self.tenant_id)
        self.assertEqual(overview["node_counts"]["building"], 1)
        self.assertEqual(overview["node_counts"]["device"], 1)
        self.assertGreaterEqual(overview["edge_count"], 5)
        self.assertTrue(any("知识条目" in item for item in overview["sources"]))

    def test_search_finds_entities_by_name(self):
        result = entity_graph_service.search(self.db, self.tenant_id, "A座综合楼")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["type"], "building")
        self.assertEqual(entity_graph_service.search(self.db, self.tenant_id, "")["items"], [])


class TestEntityGraphApi(_GraphFixture):
    """接口层：鉴权、404、以及路由确实挂上了。"""

    client = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        db = SessionLocal()
        try:
            role = db.query(Role).filter(Role.role_code == ADMIN_ROLE).first()
            if not role:
                role = Role(tenant_id=cls.tenant_id, role_code=ADMIN_ROLE, role_name=ADMIN_ROLE,
                            permissions=json.dumps(["*"]))
                db.add(role)
                db.commit()
                db.refresh(role)
            user = db.query(User).filter(User.username == ADMIN_USER).first()
            if not user:
                hashed, salt = hash_password(PASSWORD)
                user = User(username=ADMIN_USER, password_hash=hashed, password_salt=salt,
                            tenant_id=cls.tenant_id, role_id=role.id, real_name=ADMIN_USER, status="active")
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
            db.query(User).filter(User.username == ADMIN_USER).delete(synchronize_session=False)
            db.query(Role).filter(Role.role_code == ADMIN_ROLE).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
        super().tearDownClass()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_endpoints_require_login(self):
        for path in ("/api/kg/overview", "/api/kg/graph", "/api/kg/search?keyword=x"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_overview_and_graph(self):
        overview = self.client.get("/api/kg/overview", headers=self._headers())
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertGreaterEqual(overview.json()["node_count"], 5)

        graph = self.client.get("/api/kg/graph?alerts=5", headers=self._headers())
        self.assertEqual(graph.status_code, 200, graph.text)
        body = graph.json()
        self.assertTrue(body["nodes"])
        self.assertIn("relation_labels", body)

    def test_subgraph_endpoint_reports_missing_entity(self):
        resp = self.client.get(
            "/api/kg/subgraph?entity_type=building&entity_id=99999999", headers=self._headers()
        )
        self.assertEqual(resp.status_code, 404, resp.text)
        self.assertFalse(resp.json()["found"])

    def test_search_endpoint(self):
        resp = self.client.get("/api/kg/search?keyword=烟感", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["items"][0]["type"], "device")


if __name__ == "__main__":
    unittest.main()
