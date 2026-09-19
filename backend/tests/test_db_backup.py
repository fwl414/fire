"""数据库备份/恢复工具的回归测试（SQLite 路径，可离线执行）。

覆盖：备份产物与校验文件生成、sha256 校验、损坏检测、恢复覆盖与恢复前副本、
保留策略清理、不支持的数据库类型拒绝。
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db_backup


class TestDbBackup(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.db_path = root / "main.db"
        self.runtime_path = root / "runtime.db"
        self.backup_dir = root / "backups"

        self._create_sqlite(self.db_path, "inspection_records", 3)
        self._create_sqlite(self.runtime_path, "work_orders", 2)

        self._saved_env = {
            key: os.environ.get(key)
            for key in ("DATABASE_URL", "RUNTIME_DB_PATH", "BACKUP_DIR", "BACKUP_RETENTION_DAYS")
        }
        os.environ["DATABASE_URL"] = f"sqlite:///{self.db_path}"
        os.environ["RUNTIME_DB_PATH"] = str(self.runtime_path)
        os.environ["BACKUP_DIR"] = str(self.backup_dir)
        os.environ["BACKUP_RETENTION_DAYS"] = "14"

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    @staticmethod
    def _create_sqlite(path: Path, table: str, rows: int) -> None:
        with closing(sqlite3.connect(str(path))) as conn:
            conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)")
            conn.executemany(
                f"INSERT INTO {table} (name) VALUES (?)", [(f"row-{i}",) for i in range(rows)]
            )
            conn.commit()

    @staticmethod
    def _count(path: Path, table: str) -> int:
        with closing(sqlite3.connect(str(path))) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def _backup_files(self):
        return sorted(p for p in self.backup_dir.iterdir() if not p.name.endswith(".sha256"))

    def test_backup_creates_main_and_runtime_artifacts(self):
        self.assertEqual(db_backup.main(["backup"]), 0)

        files = self._backup_files()
        names = [p.name for p in files]
        self.assertTrue(any("sqlite" in n for n in names), f"应生成主库备份: {names}")
        self.assertTrue(any("runtime" in n for n in names), f"应生成运行时库备份: {names}")

        for path in files:
            checksum = path.with_suffix(path.suffix + ".sha256")
            self.assertTrue(checksum.exists(), f"缺少校验文件: {checksum.name}")
            self.assertIn(db_backup.sha256_of(path), checksum.read_text(encoding="utf-8"))

        main_backup = next(p for p in files if "sqlite" in p.name)
        self.assertEqual(self._count(main_backup, "inspection_records"), 3)

    def test_verify_passes_for_fresh_backup(self):
        db_backup.main(["backup"])
        main_backup = next(p for p in self._backup_files() if "sqlite" in p.name)
        self.assertEqual(db_backup.main(["verify", main_backup.name]), 0)

    def test_verify_detects_tampered_backup(self):
        db_backup.main(["backup"])
        main_backup = next(p for p in self._backup_files() if "sqlite" in p.name)

        with main_backup.open("ab") as handle:
            handle.write(b"tampered")

        self.assertEqual(db_backup.main(["verify", main_backup.name]), 1)
        self.assertEqual(db_backup.main(["restore", main_backup.name, "--yes"]), 1)

    def test_restore_recovers_data_and_keeps_safety_copy(self):
        db_backup.main(["backup"])
        main_backup = next(p for p in self._backup_files() if "sqlite" in p.name)

        # 破坏当前数据库：删表（备份里仍有该表）
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.execute("DROP TABLE inspection_records")
            conn.commit()

        self.assertEqual(db_backup.main(["restore", main_backup.name, "--yes"]), 0)
        self.assertEqual(self._count(self.db_path, "inspection_records"), 3)

        safety_copies = list(self.db_path.parent.glob("main.db.before_restore_*"))
        self.assertTrue(safety_copies, "恢复前应保留原库副本")

    def test_restore_requires_explicit_confirmation(self):
        db_backup.main(["backup"])
        main_backup = next(p for p in self._backup_files() if "sqlite" in p.name)
        self.assertEqual(db_backup.main(["restore", main_backup.name]), 2)

    def test_prune_removes_expired_backups(self):
        db_backup.main(["backup"])
        self.assertTrue(self._backup_files())

        os.environ["BACKUP_RETENTION_DAYS"] = "0"
        self.assertEqual(db_backup.main(["prune"]), 0)
        self.assertEqual(self._backup_files(), [], "过期备份应被清理")
        leftover_checksums = [p.name for p in self.backup_dir.iterdir() if p.name.endswith(".sha256")]
        self.assertEqual(leftover_checksums, [], "校验文件应随备份一起清理")

    def test_unsupported_database_type_is_rejected(self):
        os.environ["DATABASE_URL"] = "mysql://user:pass@localhost:3306/fire"
        self.assertEqual(db_backup.main(["backup"]), 2)

    def test_list_shows_existing_backups(self):
        db_backup.main(["backup"])
        self.assertEqual(db_backup.main(["list"]), 0)


if __name__ == "__main__":
    unittest.main()
