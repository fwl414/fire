"""登录日志：逐次记录登录成功与失败，供「登录日志」页面与安全审计查询。

与 `LoginAttemptState`（每个用户名一行的锁定计数）互不替代：
- `LoginAttemptState`：用于判定是否锁定，只关心「失败了几次」。
- `login_logs`：逐次明细，关心「谁、什么时候、从哪个 IP/设备、成功还是失败、为什么」。

设备/浏览器/归属地不落库，读取时从 `user_agent` 与 `ip_address` 推导，
避免解析规则升级后历史数据无法修正。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import LoginLog, User

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# 内网地址段（RFC1918 / 链路本地）。回环地址单独判为「本机」，见 describe_ip。
_PRIVATE_IP_PATTERNS = (
    re.compile(r"^10\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\."),
    re.compile(r"^169\.254\."),
)

_LOOPBACK_IP_PATTERNS = (
    re.compile(r"^127\."),
    re.compile(r"^0:0:0:0:0:0:0:1$"),
)

_OS_RULES = (
    (re.compile(r"Windows NT 11\.0"), "Windows 11"),
    (re.compile(r"Windows NT 10\.0"), "Windows 10"),
    (re.compile(r"Windows NT 6\.3"), "Windows 8.1"),
    (re.compile(r"Windows NT 6\.1"), "Windows 7"),
    (re.compile(r"Android"), "Android"),
    (re.compile(r"iPhone|iPad|iPod"), "iOS"),
    (re.compile(r"Mac OS X"), "macOS"),
    (re.compile(r"Linux"), "Linux"),
)

_BROWSER_RULES = (
    (re.compile(r"Edg(?:e|A|iOS)?/([\d.]+)"), "Edge"),
    (re.compile(r"OPR/([\d.]+)"), "Opera"),
    (re.compile(r"Firefox/([\d.]+)"), "Firefox"),
    (re.compile(r"Chrome/([\d.]+)"), "Chrome"),
    (re.compile(r"Version/([\d.]+).*Safari"), "Safari"),
    (re.compile(r"MSIE ([\d.]+)"), "IE"),
    (re.compile(r"Trident/.*rv:([\d.]+)"), "IE"),
)


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    """从 User-Agent 解析操作系统与浏览器，解析不出时返回空串（页面显示 —）。"""
    raw = user_agent or ""
    os_name = ""
    for pattern, name in _OS_RULES:
        if pattern.search(raw):
            os_name = name
            break

    browser = ""
    for pattern, name in _BROWSER_RULES:
        match = pattern.search(raw)
        if match:
            browser = f"{name} {match.group(1).split('.')[0]}" if match.groups() else name
            break

    return {"os": os_name, "browser": browser}


def describe_ip(ip: str) -> str:
    """IP 归属地。没有接入 IP 库，因此只对可判定的内网地址给出结论。"""
    raw = (ip or "").strip()
    if not raw:
        return ""
    if raw in ("::1", "localhost"):
        return "本机"
    for pattern in _LOOPBACK_IP_PATTERNS:
        if pattern.match(raw):
            return "本机"
    for pattern in _PRIVATE_IP_PATTERNS:
        if pattern.match(raw):
            return "内网"
    return ""


def record_login_attempt(
    db: Session,
    *,
    username: str,
    status: str,
    fail_reason: str = "",
    user: Optional[User] = None,
    ip: str = "",
    user_agent: str = "",
) -> None:
    """写入一条登录日志。日志写入失败不应把登录本身带崩。"""
    try:
        db.add(LoginLog(
            tenant_id=user.tenant_id if user else None,
            user_id=user.id if user else None,
            username=(username or "").strip(),
            real_name=(user.real_name or "") if user else "",
            ip_address=(ip or "")[:64],
            user_agent=(user_agent or "")[:512],
            status=status,
            fail_reason=fail_reason or "",
            login_at=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        db.rollback()


def serialize(row: LoginLog) -> Dict[str, Any]:
    parsed = parse_user_agent(row.user_agent or "")
    return {
        "id": row.id,
        "login_time": row.login_at.strftime("%Y-%m-%d %H:%M:%S") if row.login_at else "",
        "username": row.username or "",
        "real_name": row.real_name or "",
        "ip_address": row.ip_address or "",
        "location": describe_ip(row.ip_address or ""),
        "os": parsed["os"],
        "browser": parsed["browser"],
        "user_agent": row.user_agent or "",
        "status": row.status or STATUS_SUCCESS,
        "fail_reason": row.fail_reason or "",
    }


def list_login_logs(
    db: Session,
    *,
    tenant_id: Optional[int],
    username: str = "",
    status: str = "",
    ip_address: str = "",
    start: str = "",
    end: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """分页查询登录日志。

    租户隔离：已知用户的记录带 tenant_id；未知用户名的失败尝试 tenant_id 为空，
    这类「探测行为」对任何租户管理员都是安全信号，因此一并返回（不泄露其它租户的用户名）。
    """
    query = db.query(LoginLog)
    if tenant_id is not None:
        query = query.filter(
            (LoginLog.tenant_id == tenant_id) | (LoginLog.tenant_id.is_(None))
        )
    if username:
        query = query.filter(LoginLog.username.like(f"%{username}%"))
    if status:
        query = query.filter(LoginLog.status == status)
    if ip_address:
        query = query.filter(LoginLog.ip_address.like(f"%{ip_address}%"))
    start_at = _parse_bound(start)
    if start_at:
        query = query.filter(LoginLog.login_at >= start_at)
    end_at = _parse_bound(end, end_of_day=True)
    if end_at:
        query = query.filter(LoginLog.login_at <= end_at)

    total = query.count()
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 20)), 200)
    rows: List[LoginLog] = (
        query.order_by(LoginLog.login_at.desc(), LoginLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def _parse_bound(value: str, *, end_of_day: bool = False) -> Optional[datetime]:
    """支持 `YYYY-MM-DD` 与 `YYYY-MM-DD HH:MM:SS` 两种写法。"""
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d" and end_of_day:
            return parsed.replace(hour=23, minute=59, second=59)
        return parsed
    return None
