"""运行时库路径统一的回归测试。

背景：运行时库（裸 SQLite）此前有 3 个模块把路径硬编码成
`backend/data/fire_agent_runtime.db`，完全忽略 `RUNTIME_DB_PATH`。容器里根文件系统
`read_only: true`，该目录不可写，这些功能的写入会直接失败或落到容器内看不见的位置。
本文件确保所有运行时库写入方都走 `RUNTIME_DB_PATH`。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.runtime_db import DEFAULT_RUNTIME_DB, runtime_db_path


class TestRuntimeDbPath(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "nested" / "runtime.db"
        self._saved = os.environ.get("RUNTIME_DB_PATH")
        os.environ["RUNTIME_DB_PATH"] = str(self.path)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("RUNTIME_DB_PATH", None)
        else:
            os.environ["RUNTIME_DB_PATH"] = self._saved
        self._tmp.cleanup()

    def test_path_follows_env_at_call_time(self):
        """路径必须在调用时解析：进程启动后再设置环境变量也要生效。"""
        self.assertEqual(runtime_db_path(), self.path)
        other = Path(self._tmp.name) / "another.db"
        os.environ["RUNTIME_DB_PATH"] = str(other)
        self.assertEqual(runtime_db_path(), other)

    def test_blank_env_falls_back_to_default(self):
        os.environ["RUNTIME_DB_PATH"] = "   "
        self.assertEqual(runtime_db_path(), DEFAULT_RUNTIME_DB)

    def test_missing_env_falls_back_to_default(self):
        os.environ.pop("RUNTIME_DB_PATH", None)
        self.assertEqual(runtime_db_path(), DEFAULT_RUNTIME_DB)

    def test_all_runtime_writers_use_the_same_file(self):
        """回归守卫：改造前 learning / rag 硬编码 backend/data，忽略环境变量。"""
        from services import (
            learning_profile_service,
            rag_admin_service,
            record_persistence_service,
        )

        writers = {
            "record_persistence_service": record_persistence_service._connect,
            "learning_profile_service": learning_profile_service._connect,
            "rag_admin_service": rag_admin_service._connect,
        }

        expected = self.path.resolve()
        for name, connect in writers.items():
            with self.subTest(module=name):
                conn = connect()
                try:
                    actual = Path(
                        conn.execute("PRAGMA database_list").fetchone()[2]
                    ).resolve()
                finally:
                    conn.close()
                self.assertEqual(actual, expected, f"{name} 未使用 RUNTIME_DB_PATH")
                self.assertTrue(actual.exists(), f"{name} 未创建运行时库文件")

    def test_backup_uses_the_same_path_as_writers(self):
        """备份必须落在应用真正写入的那个文件上，否则等于没备。"""
        import db_backup

        self.assertEqual(db_backup.runtime_db_path(), self.path)


if __name__ == "__main__":
    unittest.main()
