"""数据库迁移（Alembic）测试

覆盖：
- 全新库：`upgrade` 建出全部表，且与模型元数据完全一致（不漏表、不多表）
- 版本记录：迁移后 `alembic_version` 落在 head，且重复执行幂等
- 存量库：有业务表但没有 `alembic_version` 时只打基线标记，不重建表、不动数据
- 基线迁移存在：加了模型却忘记生成迁移会在此立刻失败
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import Base
from services import db_migration_service as migration


def _patch_to(url: str, engine) -> list:
    return [
        mock.patch.object(migration, "DATABASE_URL", url),
        mock.patch.object(migration, "engine", engine),
    ]


class TestMigrationFreshDatabase(unittest.TestCase):
    """全新库必须由基线迁移一次建全——否则新装环境起不来。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fresh.db"
        self.url = f"sqlite:///{self.path}"
        self.engine = create_engine(self.url)
        self._patches = _patch_to(self.url, self.engine)
        for patch in self._patches:
            patch.start()

    def tearDown(self):
        for patch in self._patches:
            patch.stop()
        self.engine.dispose()
        self._tmp.cleanup()

    def test_upgrade_creates_every_model_table(self):
        result = migration.run_migrations()
        self.assertTrue(result["upgraded"], result)
        self.assertIsNone(result["from"], "全新库迁移前不应有版本")

        created = set(inspect(self.engine).get_table_names())
        expected = set(Base.metadata.tables.keys())
        self.assertEqual(expected - created, set(), "模型里的表没有被迁移创建")
        self.assertEqual(created - expected - {migration.VERSION_TABLE}, set(), "迁移多建了表")

    def test_version_is_recorded_at_head(self):
        migration.run_migrations()
        self.assertEqual(migration.current_revision(), migration.head_revision())

    def test_second_run_is_noop(self):
        migration.run_migrations()
        again = migration.run_migrations()
        self.assertFalse(again["upgraded"])
        self.assertFalse(again["stamped"])
        self.assertEqual(again["from"], again["head"])

    def test_indexes_are_created(self):
        """关键索引不能在迁移里漏掉（哈希链依赖 seq 的索引）。"""
        migration.run_migrations()
        with self.engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'"))
            }
        self.assertIn("ix_operation_logs_seq", names)
        self.assertIn("ix_login_logs_login_at", names)


class TestMigrationExistingDatabase(unittest.TestCase):
    """存量库（结构由 create_all 建立）必须只打标记，绝不能重建。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "existing.db"
        self.url = f"sqlite:///{self.path}"
        self.engine = create_engine(self.url)

        # 模拟历史上 create_all 建出的库，并放一行数据确认迁移不会把它清掉
        Base.metadata.create_all(bind=self.engine)
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO tenants (tenant_code, tenant_name, status) "
                "VALUES ('legacy', '存量租户', 'active')"
            ))

        self._patches = _patch_to(self.url, self.engine)
        for patch in self._patches:
            patch.start()

    def tearDown(self):
        for patch in self._patches:
            patch.stop()
        self.engine.dispose()
        self._tmp.cleanup()

    def _tenant_count(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM tenants")).scalar()

    def test_existing_database_is_stamped_not_recreated(self):
        before = set(inspect(self.engine).get_table_names())
        result = migration.run_migrations()

        self.assertTrue(result["stamped"], result)
        self.assertFalse(result["upgraded"], "存量库不应再执行建表")
        self.assertEqual(result["from"], result["head"])

        after = set(inspect(self.engine).get_table_names())
        self.assertEqual(after, before | {migration.VERSION_TABLE})
        self.assertEqual(self._tenant_count(), 1, "迁移不应动数据")

    def test_second_run_is_noop(self):
        migration.run_migrations()
        again = migration.run_migrations()
        self.assertFalse(again["upgraded"])
        self.assertFalse(again["stamped"])
        self.assertEqual(self._tenant_count(), 1)

    def test_migrate_on_startup_stamps_existing_database(self):
        """走启动入口也要做出同样的判断。"""
        result = migration.migrate_on_startup()
        self.assertTrue(result["stamped"], result)
        self.assertEqual(migration.current_revision(), migration.head_revision())


class TestMigrationSwitches(unittest.TestCase):

    def test_auto_migrate_can_be_disabled(self):
        for value in ("false", "FALSE", "0", "no", "off"):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"DB_AUTO_MIGRATE": value}):
                    self.assertFalse(migration.auto_migrate_enabled())

    def test_auto_migrate_defaults_to_enabled(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DB_AUTO_MIGRATE", None)
            self.assertTrue(migration.auto_migrate_enabled())

    def test_disabled_switch_skips_migration(self):
        with mock.patch.dict(os.environ, {"DB_AUTO_MIGRATE": "false"}):
            with mock.patch.object(migration, "run_migrations") as spy:
                self.assertIsNone(migration.migrate_on_startup())
                spy.assert_not_called()


class TestBaselineRevision(unittest.TestCase):

    def test_baseline_is_the_only_root_revision(self):
        """基线必须存在且是唯一根节点，否则升级链断了。"""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(migration.alembic_config())
        heads = script.get_heads()
        self.assertEqual(len(heads), 1, f"迁移链应只有一个 head，实际 {heads}")

        bases = script.get_bases()
        self.assertEqual(len(bases), 1, f"迁移链应只有一个根，实际 {bases}")


if __name__ == "__main__":
    unittest.main()
