"""pytest 全局隔离：让测试会话独占一套库，不与本地开发服务共享。

背景（本次修复的竞态根因）：
默认 `DATABASE_URL` 是 `sqlite:///./fire_ai_agent.db`，与本地 `start_server.py`
起的开发服务是**同一个文件**。开发服务进程里常驻着后台任务 worker（每 2 秒轮询一次
队列），于是测试刚 `enqueue` 的任务会在断言前被开发服务的 worker 抢走并执行完，
表现为随机失败：

    AssertionError: 'running' != 'pending'
    AssertionError: 'fire_ai_background_tasks{status="pending"} 1' not found

只要两个进程共用一个库，任何「入队后立刻断言状态」的用例都无法稳定。同样的共享还
带来过更严重的副作用：测试的清理逻辑会删掉开发库里的真实上传记录与文件。

因此在任何业务模块被导入之前，这里把主库、运行时库以及两个落盘目录都改到临时目录，
让测试进程成为这套数据的唯一使用者。注意**不**关闭 `TASK_WORKER_ENABLED`：需要 worker
的用例（如 `TestWorkerLifecycle`）会在用例内部自己 `start_worker()`。

`REPORT_STORAGE_DIR` / `UPLOAD_STORAGE_DIR` 也要一起改：报表产物与上传文件走的是固定
目录（`backend/data/reports`、`backend/uploads`），即使库已隔离，测试生成的 csv 与
上传文件仍会堆到开发目录里。

仍有一处绕不过去：`services/agent_service.py` 的巡检图片落盘用的是相对路径
`Path("uploads")`，只跟进程 CWD 走、不认 `UPLOAD_STORAGE_DIR`。改它会影响
`result_json.image_paths` 的取值形式（相对路径 → 绝对路径）进而牵动前端展示，风险比收益大，
所以这里改为**会话结束时把本会话新落到共享 uploads 目录的巡检图片回收掉**。
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

# 必须 resolve()：Windows 上 gettempdir() 可能返回 8.3 短名（C:\Users\ADMINI~1\...），
# 而 upload_archive_service.storage_key() 会拿 UPLOAD_ROOT.resolve()（长名）去比对文件路径，
# 短名与长名对不上就会让 storage_key 返回 None，相关用例会失败。
_TMP_ROOT = (Path(tempfile.gettempdir()) / "fire_ai_agent_pytest").resolve()

# 每次会话从空库开始，避免上一轮的残留任务/用户串味
shutil.rmtree(_TMP_ROOT, ignore_errors=True)
_TMP_ROOT.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_ROOT / 'test_suite.db').as_posix()}"
os.environ["RUNTIME_DB_PATH"] = str(_TMP_ROOT / "test_suite_runtime.db")
os.environ["REPORT_STORAGE_DIR"] = str(_TMP_ROOT / "reports")
os.environ["UPLOAD_STORAGE_DIR"] = str(_TMP_ROOT / "uploads")
os.environ.setdefault("ENV", "development")

_DEV_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
_SESSION_STARTED_AT = time.time()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 - pytest 钩子签名固定
    """回收本会话落到开发 uploads 目录的巡检图片（见模块 docstring 的说明）。

    只删「会话开始之后新出现」且文件名符合测试生成规则的 `inspection_<32位hex>.png`，
    不动任何既有文件。
    """
    if not _DEV_UPLOAD_DIR.is_dir():
        return
    removed = 0
    for path in _DEV_UPLOAD_DIR.glob("inspection_*.png"):
        try:
            if path.stat().st_mtime >= _SESSION_STARTED_AT:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        print(f"\n[conftest] 已回收会话期间落到开发 uploads 目录的巡检图片 {removed} 个")
