"""
用户认证与权限服务
JWT认证 + RBAC角色权限控制
"""
from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import (
    get_db, User, Role,
    verify_password, hash_password,
    SessionLocal, LoginAttemptState, ensure_auth_state_tables,
)
from services.token_blacklist_service import is_blacklisted, add_token_from_payload, get_blacklist_stats
from services.metrics_service import incr
from services.login_log_service import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    record_login_attempt,
)

try:
    import jwt
except ImportError as exc:
    raise RuntimeError("缺少 PyJWT 依赖，认证服务无法启动") from exc

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12
REFRESH_TOKEN_EXPIRE_DAYS = 7

ENV = os.environ.get("ENV", "development").lower()
IS_PRODUCTION = ENV in ("production", "prod")

if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "生产环境必须设置 JWT_SECRET_KEY 环境变量！"
            "请使用至少32字节的随机字符串作为密钥。"
        )
    import warnings
    warnings.warn(
        "⚠️  安全警告：JWT_SECRET_KEY 环境变量未设置！"
        "生产环境必须设置强随机密钥，否则存在严重安全风险。"
        "当前为开发环境，将使用临时随机密钥（每次重启失效）。"
    )
    SECRET_KEY = "dev_" + os.urandom(32).hex()

security = HTTPBearer(auto_error=False)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15

_state_tables_ready = False


def _ensure_state_tables() -> None:
    global _state_tables_ready
    if not _state_tables_ready:
        ensure_auth_state_tables()
        _state_tables_ready = True


def _with_login_state_db(db: Optional[Session], fn):
    """优先复用请求会话，否则自建会话，保证登录锁定状态持久化。"""
    _ensure_state_tables()
    if db is not None:
        return fn(db)
    session = SessionLocal()
    try:
        return fn(session)
    finally:
        session.close()


def _check_login_lock(username: str, db: Optional[Session] = None) -> tuple[bool, int]:
    """检查账号是否被锁定，返回 (是否锁定, 剩余秒数)"""
    now = datetime.utcnow()
    key = (username or "").lower()

    def _check(session: Session) -> tuple[bool, int]:
        record = session.query(LoginAttemptState).filter(
            LoginAttemptState.username == key
        ).first()
        if not record or not record.lock_until:
            return False, 0
        if now < record.lock_until:
            return True, int((record.lock_until - now).total_seconds())
        session.delete(record)
        session.commit()
        return False, 0

    return _with_login_state_db(db, _check)


def _record_login_failure(username: str, db: Optional[Session] = None) -> tuple[int, bool, int]:
    """记录登录失败，返回 (失败次数, 是否锁定, 锁定剩余秒数)"""
    now = datetime.utcnow()
    key = (username or "").lower()

    def _record(session: Session) -> tuple[int, bool, int]:
        record = session.query(LoginAttemptState).filter(
            LoginAttemptState.username == key
        ).first()
        if not record:
            record = LoginAttemptState(username=key, fail_count=0)
            session.add(record)
        record.fail_count = (record.fail_count or 0) + 1
        record.last_failed_at = now
        record.updated_at = now
        locked = False
        remaining = 0
        if record.fail_count >= MAX_LOGIN_ATTEMPTS:
            record.lock_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
            locked = True
            remaining = LOGIN_LOCK_MINUTES * 60
        session.commit()
        incr("login_failed")
        if locked:
            incr("login_locked")
        return record.fail_count, locked, remaining

    return _with_login_state_db(db, _record)


def _clear_login_failures(username: str, db: Optional[Session] = None) -> None:
    """清除登录失败记录"""
    key = (username or "").lower()

    def _clear(session: Session) -> None:
        session.query(LoginAttemptState).filter(
            LoginAttemptState.username == key
        ).delete(synchronize_session=False)
        session.commit()

    _with_login_state_db(db, _clear)


def create_access_token(user: User, role: Optional[Role] = None) -> str:
    """创建访问令牌"""
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": role.role_code if role else "",
        "tenant_id": user.tenant_id or 0,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user: User) -> str:
    """创建刷新令牌"""
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "tenant_id": user.tenant_id or 0,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解析令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


def authenticate_token(token: str, db: Session) -> Optional[User]:
    """用访问令牌换用户；令牌无效 / 已撤销 / 账号被停用时返回 None。

    `get_current_user` 依赖 HTTP 的 `Authorization` 头做依赖注入，WebSocket 握手拿不到这个入口，
    因此把「令牌 → 用户」的校验单独抽出来给 WebSocket 用。
    """
    payload = decode_token(token or "")
    if not payload:
        return None
    if is_blacklisted(token):
        return None
    user = db.query(User).filter(User.id == int(payload.get("sub", 0))).first()
    if user is None or user.status != "active":
        return None
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户（用于接口依赖注入）"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已被撤销",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """可选获取当前用户（公开接口也可以用）"""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def get_user_role(user: User, db: Session) -> Optional[Role]:
    """获取用户角色"""
    if not user.role_id:
        return None
    return db.query(Role).filter(Role.id == user.role_id).first()


def get_user_permissions(user: User, db: Session) -> List[str]:
    """获取用户权限列表"""
    role = get_user_role(user, db)
    if not role:
        return []
    try:
        return json.loads(role.permissions or "[]")
    except Exception:
        return []


def has_permission(user: User, db: Session, permission: str) -> bool:
    """检查用户是否有指定权限"""
    permissions = get_user_permissions(user, db)
    if "*" in permissions:
        return True
    return permission in permissions


def require_permission(permission: str):
    """权限检查依赖生成器"""
    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        if not has_permission(current_user, db, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission}",
            )
        return current_user
    return _check


def require_role(role_code: str):
    """角色检查依赖生成器"""
    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        role = get_user_role(current_user, db)
        if not role or role.role_code != role_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要角色: {role_code}",
            )
        return current_user
    return _check


def get_tenant_id(user: User) -> Optional[int]:
    """获取用户所属租户ID"""
    return getattr(user, "tenant_id", None)


def get_current_tenant_id(
    current_user: User = Depends(get_current_user),
) -> int:
    tenant_id = get_tenant_id(current_user)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户未关联有效租户",
        )
    return tenant_id


def require_tenant_access():
    """
    依赖注入：确保用户有租户上下文。
    对于多租户环境，所有业务接口应使用此依赖确保租户隔离。
    """
    def _check(current_user: User = Depends(get_current_user)) -> int:
        tenant_id = get_tenant_id(current_user)
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户未关联租户，无法访问",
            )
        return tenant_id
    return _check


class TenantScopedQuery:
    """
    租户范围查询助手：自动为查询添加 tenant_id 过滤。
    用法示例：
        tq = TenantScopedQuery(tenant_id)
        buildings = tq.filter(db.query(Building)).all()
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def filter(self, query):
        """为查询添加租户过滤"""
        model = query.column_descriptions[0]["type"] if query.column_descriptions else None
        if model and hasattr(model, "tenant_id"):
            return query.filter(model.tenant_id == self.tenant_id)
        return query

    def get_or_404(self, db: Session, model, obj_id: int):
        """按ID获取对象，带租户校验，不存在则抛出404"""
        q = db.query(model).filter(model.id == obj_id)
        if hasattr(model, "tenant_id"):
            q = q.filter(model.tenant_id == self.tenant_id)
        obj = q.first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="记录不存在或无权限访问",
            )
        return obj


def login(username: str, password: str, db: Session, ip: str = "", user_agent: str = "") -> Dict[str, Any]:
    """用户登录

    每条成功/失败结果都写一条 `login_logs`，「登录日志」页面据此展示；
    设备、浏览器、归属地在读取时由 `user_agent` / `ip` 推导，不在写入侧固化。
    """
    username = (username or "").strip()
    if not username or not password:
        return {"ok": False, "message": "用户名和密码不能为空"}

    def _failed(message: str, reason: str, user: Optional[User] = None) -> Dict[str, Any]:
        record_login_attempt(
            db, username=username, status=STATUS_FAILED, fail_reason=reason,
            user=user, ip=ip, user_agent=user_agent,
        )
        return {"ok": False, "message": message}

    locked, remaining = _check_login_lock(username, db)
    if locked:
        mins = remaining // 60 + (1 if remaining % 60 > 0 else 0)
        return _failed(f"登录失败次数过多，账号已被锁定，请{mins}分钟后再试", "账号已锁定")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        fail_count, locked, remaining = _record_login_failure(username, db)
        if locked:
            return _failed(
                f"登录失败次数过多，账号已被锁定，请{LOGIN_LOCK_MINUTES}分钟后再试", "用户不存在"
            )
        left = MAX_LOGIN_ATTEMPTS - fail_count
        return _failed(f"用户名或密码错误，还可尝试{left}次", "用户不存在")

    if user.status != "active":
        return _failed("账号已被禁用", "账号已禁用", user=user)

    if not verify_password(password, user.password_hash, user.password_salt):
        fail_count, locked, remaining = _record_login_failure(username, db)
        if locked:
            return _failed(
                f"登录失败次数过多，账号已被锁定，请{LOGIN_LOCK_MINUTES}分钟后再试", "密码错误", user=user
            )
        left = MAX_LOGIN_ATTEMPTS - fail_count
        return _failed(f"用户名或密码错误，还可尝试{left}次", "密码错误", user=user)

    _clear_login_failures(username, db)

    role = get_user_role(user, db)
    access_token = create_access_token(user, role)
    refresh_token = create_refresh_token(user)

    user.last_login_at = datetime.utcnow()
    user.last_login_ip = ip
    db.commit()

    record_login_attempt(
        db, username=username, status=STATUS_SUCCESS,
        user=user, ip=ip, user_agent=user_agent,
    )

    permissions = get_user_permissions(user, db)

    return {
        "ok": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "email": user.email,
            "phone": user.phone,
            "department": user.department,
            "avatar": user.avatar,
            "role": role.role_code if role else "",
            "role_name": role.role_name if role else "",
            "permissions": permissions,
        },
        "message": "登录成功"
    }


def refresh_token(refresh_token_str: str, db: Session) -> Dict[str, Any]:
    """刷新访问令牌"""
    payload = decode_token(refresh_token_str)
    if not payload or payload.get("type") != "refresh":
        return {"ok": False, "message": "刷新令牌无效"}

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()

    if not user or user.status != "active":
        return {"ok": False, "message": "用户不存在或已禁用"}

    role = get_user_role(user, db)
    new_access_token = create_access_token(user, role)

    return {
        "ok": True,
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "message": "令牌刷新成功"
    }


def logout(user: User, token: str = "") -> Dict[str, Any]:
    """用户登出，将Token加入黑名单"""
    if token:
        payload = decode_token(token)
        if payload:
            add_token_from_payload(token, payload)
    return {"ok": True, "message": "登出成功"}


def change_password(user: User, old_password: str, new_password: str, db: Session) -> Dict[str, Any]:
    """修改密码"""
    if not verify_password(old_password, user.password_hash, user.password_salt):
        return {"ok": False, "message": "原密码错误"}

    if len(new_password) < 8:
        return {"ok": False, "message": "新密码长度不能少于8位"}
    if not any(c.isupper() for c in new_password) and not any(c.islower() for c in new_password):
        return {"ok": False, "message": "密码需包含大小写字母"}
    if not any(c.isdigit() for c in new_password):
        return {"ok": False, "message": "密码需包含数字"}

    hashed, salt = hash_password(new_password)
    user.password_hash = hashed
    user.password_salt = salt
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"ok": True, "message": "密码修改成功"}


def list_demo_accounts(db: Session) -> List[Dict[str, Any]]:
    """获取演示账号列表"""
    users = db.query(User).all()
    result = []
    for u in users:
        role = get_user_role(u, db)
        result.append({
            "username": u.username,
            "password_hint": "联系管理员获取",
            "role": role.role_code if role else "",
            "role_name": role.role_name if role else "",
            "description": role.description if role else "",
        })
    return result


def role_permissions(db: Session) -> Dict[str, Any]:
    """获取角色权限配置"""
    roles = db.query(Role).all()
    return {
        "roles": [
            {
                "role": r.role_code,
                "name": r.role_name,
                "scope": r.description,
                "permissions": json.loads(r.permissions or "[]"),
            }
            for r in roles
        ],
        "note": "基于RBAC的服务端权限控制，所有API接口均有权限校验。"
    }
