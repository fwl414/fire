"""数据库备份与恢复工具

支持 PostgreSQL（生产）与 SQLite（开发/运行库），提供一致的备份、校验、恢复与保留策略。

用法：
    python db_backup.py backup                       # 备份主库（并自动附带运行时 SQLite 库）
    python db_backup.py list                         # 列出已有备份
    python db_backup.py verify <备份文件>            # 校验备份完整性（含 sha256 校验）
    python db_backup.py restore <备份文件> --yes     # 恢复（必须显式确认）
    python db_backup.py prune                        # 仅执行保留策略清理

环境变量：
    DATABASE_URL            主库连接串（默认读取 backend/.env）
    RUNTIME_DB_PATH         运行时 SQLite 库路径（默认 backend/data/fire_agent_runtime.db）
    BACKUP_DIR              备份目录（默认 backend/backups）
    BACKUP_RETENTION_DAYS   备份保留天数（默认 14）

生产环境建议：
    1. 由 cron 每日执行 `python db_backup.py backup`，并把 BACKUP_DIR 挂载到独立数据卷
    2. 定期执行 `verify` 与 `restore` 演练，确保备份可用
    3. PostgreSQL 依赖 pg_dump / pg_restore 客户端（容器内可通过安装 postgresql-client 获得）
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_BACKUP_DIR = BACKEND_DIR / "backups"

# 运行时库路径解析与业务侧共用同一实现：备份必须落在应用真正写入的那个文件上。
# 脚本可被直接执行（sys.path[0] 未必是 backend/），因此这里显式补一次。
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from services.runtime_db import runtime_db_path  # noqa: E402


def _load_env() -> None:
    """加载 backend/.env，便于直接执行脚本。"""
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        return
    except ImportError:
        pass
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./fire_ai_agent.db")


def is_postgres(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres")


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def sqlite_path(url: str) -> Path:
    raw = url.split("sqlite:///", 1)[-1]
    path = Path(raw)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


def backup_dir() -> Path:
    directory = Path(os.environ.get("BACKUP_DIR") or DEFAULT_BACKUP_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def retention_days() -> int:
    try:
        return int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))
    except ValueError:
        return 14


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path: Path) -> Path:
    checksum_file = path.with_suffix(path.suffix + ".sha256")
    checksum_file.write_text(f"{sha256_of(path)}  {path.name}\n", encoding="utf-8")
    return checksum_file


def verify_checksum(path: Path) -> bool:
    checksum_file = path.with_suffix(path.suffix + ".sha256")
    if not checksum_file.exists():
        print(f"[warn] 未找到校验文件 {checksum_file.name}，跳过 sha256 校验")
        return True
    expected = checksum_file.read_text(encoding="utf-8").split()[0]
    actual = sha256_of(path)
    if expected != actual:
        print(f"[error] sha256 不匹配：期望 {expected}，实际 {actual}")
        return False
    print(f"[ok] sha256 校验通过：{path.name}")
    return True


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_postgres(url: str, target: Path) -> None:
    if not shutil.which("pg_dump"):
        raise RuntimeError("未找到 pg_dump，请先安装 postgresql-client")
    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file", str(target),
        "--dbname", url,
    ]
    print(f"[info] 执行 pg_dump -> {target.name}")
    subprocess.run(cmd, check=True)


def backup_sqlite(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"SQLite 数据库不存在：{source}")
    # 使用 SQLite 在线备份 API，避免直接复制导致的不一致快照
    # 注意：必须显式关闭连接，with Connection 只处理事务不释放文件句柄
    with closing(sqlite3.connect(str(source))) as src, closing(sqlite3.connect(str(target))) as dst:
        src.backup(dst)
    print(f"[info] SQLite 在线备份完成 -> {target.name}")


def verify_postgres(path: Path) -> bool:
    if not shutil.which("pg_restore"):
        print("[error] 未找到 pg_restore，无法校验备份")
        return False
    result = subprocess.run(
        ["pg_restore", "--list", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[error] pg_restore 校验失败：{result.stderr.strip()}")
        return False
    entries = len([line for line in result.stdout.splitlines() if line and not line.startswith(";")])
    print(f"[ok] 备份可读，包含 {entries} 个对象")
    return True


def verify_sqlite(path: Path) -> bool:
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        print(f"[error] SQLite 校验失败：{exc}")
        return False
    if not result or result[0] != "ok":
        print(f"[error] integrity_check 未通过：{result}")
        return False
    print("[ok] SQLite integrity_check 通过")
    return True


def cmd_backup(args: argparse.Namespace) -> int:
    url = args.database_url or database_url()
    stamp = _timestamp()
    directory = backup_dir()
    created = []

    if is_postgres(url):
        target = directory / f"fire_ai_agent_pg_{stamp}.dump"
        backup_postgres(url, target)
        created.append(target)
    elif is_sqlite(url):
        target = directory / f"fire_ai_agent_sqlite_{stamp}.db"
        backup_sqlite(sqlite_path(url), target)
        created.append(target)
    else:
        print(f"[error] 暂不支持的数据库类型：{url}")
        return 2

    # 运行时 SQLite 库（巡检记录/工单）与主库分离，需一并备份。
    # 路径解析必须与业务侧一致，否则会备到一份应用并不写入的文件。
    runtime = runtime_db_path()
    if runtime.exists():
        runtime_target = directory / f"fire_agent_runtime_{stamp}.db"
        backup_sqlite(runtime, runtime_target)
        created.append(runtime_target)

    for path in created:
        write_checksum(path)
        print(f"[ok] 备份完成：{path}（{path.stat().st_size} bytes）")

    prune_backups(directory)
    return 0


def prune_backups(directory: Optional[Path] = None) -> int:
    directory = directory or backup_dir()
    keep_days = retention_days()
    cutoff = time.time() - timedelta(days=keep_days).total_seconds()
    removed = 0
    for path in directory.iterdir():
        if not path.is_file() or path.name.endswith(".sha256"):
            continue
        if path.stat().st_mtime < cutoff:
            path.unlink()
            checksum = path.with_suffix(path.suffix + ".sha256")
            if checksum.exists():
                checksum.unlink()
            removed += 1
            print(f"[info] 清理过期备份：{path.name}")
    print(f"[info] 保留策略：{keep_days} 天，本次清理 {removed} 个文件")
    return removed


def cmd_list(args: argparse.Namespace) -> int:
    directory = backup_dir()
    files = sorted(
        [p for p in directory.iterdir() if p.is_file() and not p.name.endswith(".sha256")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        print(f"[info] 备份目录为空：{directory}")
        return 0
    print(f"备份目录：{directory}")
    for path in files:
        created = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {created}  {path.stat().st_size:>12} bytes  {path.name}")
    return 0


def _find_backup(name: str) -> Path:
    candidate = Path(name)
    if candidate.is_file():
        return candidate
    candidate = backup_dir() / name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"备份文件不存在：{name}")


def cmd_verify(args: argparse.Namespace) -> int:
    path = _find_backup(args.file)
    print(f"[info] 校验备份：{path}")
    if not verify_checksum(path):
        return 1
    if path.suffix == ".dump" or path.name.endswith(".dump"):
        ok = verify_postgres(path)
    else:
        ok = verify_sqlite(path)
    return 0 if ok else 1


def cmd_restore(args: argparse.Namespace) -> int:
    if not args.yes:
        print("[error] 恢复会覆盖现有数据，请加 --yes 显式确认")
        return 2

    path = _find_backup(args.file)
    if not verify_checksum(path):
        print("[error] 校验失败，已中止恢复")
        return 1

    url = args.target or database_url()

    if is_postgres(url):
        if path.name.endswith(".db"):
            print("[error] 目标为 PostgreSQL，但所选备份是 SQLite 文件")
            return 2
        if not shutil.which("pg_restore"):
            print("[error] 未找到 pg_restore，请先安装 postgresql-client")
            return 2
        cmd = [
            "pg_restore",
            "--clean", "--if-exists",
            "--no-owner", "--no-privileges",
            "--dbname", url,
            str(path),
        ]
        print(f"[info] 执行 pg_restore 到 {url.split('@')[-1]}")
        result = subprocess.run(cmd, text=True)
        # pg_restore 在清理不存在的对象时会返回告警码，仅非致命
        if result.returncode not in (0, 1):
            print(f"[error] 恢复失败，退出码 {result.returncode}")
            return 1
        print("[ok] PostgreSQL 恢复完成，请执行应用侧健康检查")
        return 0

    if is_sqlite(url):
        target_path = sqlite_path(url)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            safety = target_path.with_suffix(target_path.suffix + f".before_restore_{_timestamp()}")
            shutil.copy2(target_path, safety)
            print(f"[info] 已保留恢复前副本：{safety}")
        shutil.copy2(path, target_path)
        print(f"[ok] SQLite 恢复完成：{target_path}")
        return 0

    print(f"[error] 暂不支持的数据库类型：{url}")
    return 2


def cmd_prune(args: argparse.Namespace) -> int:
    prune_backups()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智慧消防系统数据库备份与恢复工具")
    parser.add_argument("--database-url", help="覆盖 DATABASE_URL")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("backup", help="备份数据库").set_defaults(func=cmd_backup)
    sub.add_parser("list", help="列出已有备份").set_defaults(func=cmd_list)
    sub.add_parser("prune", help="按保留策略清理备份").set_defaults(func=cmd_prune)

    verify = sub.add_parser("verify", help="校验备份完整性")
    verify.add_argument("file", help="备份文件名或路径")
    verify.set_defaults(func=cmd_verify)

    restore = sub.add_parser("restore", help="从备份恢复")
    restore.add_argument("file", help="备份文件名或路径")
    restore.add_argument("--yes", action="store_true", help="确认覆盖现有数据")
    restore.add_argument("--target", help="目标数据库连接串（默认使用 DATABASE_URL）")
    restore.set_defaults(func=cmd_restore)

    return parser


def main(argv=None) -> int:
    _load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, FileNotFoundError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"[error] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
