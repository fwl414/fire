"""运行时 SQLite 库的统一路径解析。

运行时库与主库（`DATABASE_URL`）相互独立，存放的是早期用 `sqlite3` 直连写入的档案类
业务表（巡检档案、整改工单、巡检报告、学习答题、RAG 知识条目等）。与主库不同，它是
一个裸 SQLite 文件，因此路径必须落在可写目录上，由 `RUNTIME_DB_PATH` 指定。

此前有 3 个模块把路径硬编码成 `backend/data/fire_agent_runtime.db`，完全忽略
`RUNTIME_DB_PATH`；容器里 `read_only: true`，该目录不可写，这些功能的写入会直接失败
（或把数据写到容器内看不见的位置，重启即丢）。全部改为从这里取路径。

注意：路径必须在**使用时**解析，不能在模块导入时固化成常量，否则进程启动后再设置
`RUNTIME_DB_PATH`（测试、多环境部署）不会生效。
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_DB = BACKEND_DIR / "data" / "fire_agent_runtime.db"


def runtime_db_path() -> Path:
    """返回运行时库路径：优先 `RUNTIME_DB_PATH`，未配置时回落到 backend/data。"""
    configured = (os.environ.get("RUNTIME_DB_PATH") or "").strip()
    return Path(configured) if configured else DEFAULT_RUNTIME_DB


def connect_runtime_db() -> sqlite3.Connection:
    """打开运行时库连接（row_factory=sqlite3.Row），并保证父目录存在。"""
    path = runtime_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
