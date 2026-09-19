"""数据库结构迁移（Alembic）。

在此之前，表结构只有一个来源：启动时的 `Base.metadata.create_all()`。
它只能保证「全新库结构正确」，**已有库的变更没有任何版本化机制**——
生产环境加一列、改一个索引都得手工执行 DDL。这里把 Alembic 接成唯一的结构来源。

三种库形态：

1. 全新库（没有任何业务表）：执行 `upgrade head`，由基线迁移建出全部表。
2. 存量库（有业务表但没有 `alembic_version`）：结构是历史上 `create_all` 建的，
   先 `stamp` 到基线版本，避免重复建表；之后按迁移升级。
3. 已接入 Alembic 的库：当前版本落后就 `upgrade head`。

并发：`upgrade` 的「检查 + 建表」不是原子的，多实例同时启动时一方会报
"table xxx already exists"。这与 `create_all` 时代是同一个问题，沿用当时的做法——
对「已存在」类错误重试，并在重试期间发现另一个实例已把版本推到 head 时直接放行。
存量库还有 `runtime_locks` 可用，此时会真正互斥，其余实例等它做完再启动。
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError

from database import Base, DATABASE_URL, engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"
VERSION_TABLE = "alembic_version"

# 等待其他实例完成迁移的上限（秒）
MIGRATION_WAIT_SECONDS = 180
# 并发建表冲突的重试次数与间隔
UPGRADE_ATTEMPTS = 10
UPGRADE_RETRY_DELAY = 0.5

logger = logging.getLogger(__name__)

# 允许应用启动时自动迁移。设为 false 时完全不动结构，
# 由发布流程显式执行 `alembic upgrade head`。
AUTO_MIGRATE_DISABLED_VALUES = ("false", "0", "no", "off")


def auto_migrate_enabled() -> bool:
    return os.environ.get("DB_AUTO_MIGRATE", "true").strip().lower() not in AUTO_MIGRATE_DISABLED_VALUES


def alembic_config() -> Config:
    """构造 Alembic 配置。用绝对路径，保证不受进程工作目录影响。"""
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    # env.py 优先读这个属性，保证「配置里指定的库」就是「实际迁移的库」
    cfg.attributes["sqlalchemy_url"] = DATABASE_URL
    return cfg


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(bind: Optional[Engine] = None) -> Optional[str]:
    """读取数据库中记录的迁移版本；未接入 Alembic 时返回 None。"""
    target = bind or engine
    with target.connect() as conn:
        if VERSION_TABLE not in set(inspect(conn).get_table_names()):
            return None
        row = conn.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchone()
    return row[0] if row else None


def table_names(bind: Optional[Engine] = None) -> set:
    target = bind or engine
    with target.connect() as conn:
        return set(inspect(conn).get_table_names())


def looks_like_existing_install(existing: set) -> bool:
    """是否已经有业务表（即结构是历史上 create_all 建出来的存量库）。"""
    return bool(existing & set(Base.metadata.tables.keys()))


def _is_already_exists_error(exc: Exception) -> bool:
    text_ = str(getattr(exc, "orig", exc)).lower()
    return "already exists" in text_ or "duplicate table" in text_


def _upgrade_tolerating_concurrent_startup(cfg: Config, head: str) -> None:
    """执行 `upgrade head`，容忍多实例并发建表。"""
    last_error: Optional[Exception] = None
    for _ in range(max(1, UPGRADE_ATTEMPTS)):
        try:
            command.upgrade(cfg, head)
            return
        except (OperationalError, ProgrammingError) as exc:
            if not _is_already_exists_error(exc):
                raise
            last_error = exc
            if current_revision() == head:
                # 另一个实例已经建完并打上版本，本次视为完成
                logger.info("数据库迁移已由其他实例完成")
                return
            time.sleep(UPGRADE_RETRY_DELAY)
    if last_error:
        raise last_error


def run_migrations() -> Dict[str, Any]:
    """把数据库结构推到最新版本。返回本次实际发生了什么，便于日志与测试。"""
    cfg = alembic_config()
    head = head_revision()
    existing = table_names()

    result: Dict[str, Any] = {
        "head": head,
        "stamped": False,
        "upgraded": False,
        "from": current_revision(),
    }

    if VERSION_TABLE not in existing:
        if looks_like_existing_install(existing):
            # 存量库：结构已在，只需打上基线标记，否则会重复建表而失败
            command.stamp(cfg, head)
            result["stamped"] = True
            result["from"] = head
            return result

        _upgrade_tolerating_concurrent_startup(cfg, head)
        result["upgraded"] = True
        result["from"] = None
        result["to"] = head
        return result

    if result["from"] != head:
        _upgrade_tolerating_concurrent_startup(cfg, head)
        result["upgraded"] = True
        result["to"] = head
    return result


def _wait_until_at_head(deadline_seconds: int = MIGRATION_WAIT_SECONDS) -> None:
    """其他实例正在迁移时，等它把版本推到 head 再继续启动。"""
    head = head_revision()
    for _ in range(max(1, deadline_seconds)):
        if current_revision() == head:
            return
        time.sleep(1)
    raise RuntimeError(
        f"等待其他实例完成数据库迁移超时（{deadline_seconds}s），当前版本仍不是 {head}"
    )


def _report(result: Dict[str, Any]) -> None:
    if result.get("stamped"):
        logger.warning(
            "存量库已标记为基线版本 %s：结构此前由 create_all 建立，"
            "若与当前模型有偏差，需补一条迁移对齐",
            result["head"],
        )
    elif result.get("upgraded"):
        print(
            f"[migrate] 数据库结构已更新：{result.get('from') or '全新库'} → {result['to']}",
            file=sys.stderr,
        )


def migrate_on_startup() -> Optional[Dict[str, Any]]:
    """启动期迁移入口。

    - 全新库：还没有 `runtime_locks` 可用来加锁，直接 upgrade，靠重试兜住并发建表。
    - 存量库：表已在，用 `runtime_locks` 互斥；没抢到锁的实例等前者做完再继续，
      避免「A 在改表、B 已经开始按新结构读写」。
    - 迁移失败直接抛错，不让应用带着不确定的结构启动。
    """
    if not auto_migrate_enabled():
        logger.info("DB_AUTO_MIGRATE 已关闭，跳过启动期迁移")
        return None

    if not looks_like_existing_install(table_names()):
        result = run_migrations()
        _report(result)
        return result

    from services.runtime_lock_service import exclusive

    with exclusive("db_migration", ttl_seconds=600) as acquired:
        if not acquired:
            logger.info("其他实例正在执行数据库迁移，等待其完成")
            _wait_until_at_head()
            return None
        result = run_migrations()
        _report(result)
        return result
