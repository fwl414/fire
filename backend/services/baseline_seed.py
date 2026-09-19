"""生产环境初始数据引导（baseline seed）

生产分支此前不播种任何数据：全新库建成后没有租户、没有角色、没有用户，
所有带 tenant_id 的查询都会落空，也没有人能登录。开发分支靠
`database.seed_data()` 建这些数据，但那一份同时写入了演示设备/演示模型配置，
不适合在生产直接复用。

这里只做「让系统可用」的最小初始化，全程幂等，重复启动不堆数据：

1. 默认租户（tenant_code=default）
2. 系统角色（复用 `database.SYSTEM_ROLES`，与开发环境同一份来源）
3. 首个管理员（仅当库中无任何用户，且设置了
   INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD 时创建；
   未设置则打印提示，引导执行 `create_admin.py`）

不写入任何演示业务数据（设备、工单、告警、模型配置等）。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

from sqlalchemy.orm import Session

from database import SYSTEM_ROLES, Role, Tenant, User, hash_password

DEFAULT_TENANT_CODE = "default"
DEFAULT_TENANT_NAME = "默认租户"
ADMIN_ROLE_CODE = "admin"


def ensure_default_tenant(db: Session) -> Dict[str, Any]:
    """确保存在默认租户，返回 (tenant_id, created)。"""
    tenant = db.query(Tenant).filter(Tenant.tenant_code == DEFAULT_TENANT_CODE).first()
    if tenant:
        return {"tenant_id": tenant.id, "created": False}

    tenant_name = (os.environ.get("INITIAL_TENANT_NAME") or "").strip() or DEFAULT_TENANT_NAME
    tenant = Tenant(
        tenant_code=DEFAULT_TENANT_CODE,
        tenant_name=tenant_name,
        contact_name="系统管理员",
        status="active",
        plan="enterprise",
    )
    db.add(tenant)
    db.flush()
    print(f"[seed] 已创建默认租户：{tenant_name}（id={tenant.id}）")
    return {"tenant_id": tenant.id, "created": True}


def ensure_system_roles(db: Session, tenant_id: int) -> Dict[str, Any]:
    """按 role_code 补齐系统角色（已存在的角色不做任何修改）。"""
    existing = {code for (code,) in db.query(Role.role_code).all()}
    created_codes = []
    for role_code, role_name, description, permissions in SYSTEM_ROLES:
        if role_code in existing:
            continue
        db.add(Role(
            tenant_id=tenant_id,
            role_code=role_code,
            role_name=role_name,
            description=description,
            permissions=json.dumps(permissions),
            is_system=True,
        ))
        created_codes.append(role_code)
    if created_codes:
        db.flush()
        print(f"[seed] 已创建系统角色：{'、'.join(created_codes)}")
    return {"created": created_codes}


def _validate_admin_password(password: str) -> None:
    """与 create_admin.py 同一套口令要求；延迟导入避免脚本模块影响启动路径。"""
    from create_admin import validate_password

    validate_password(password)


def ensure_initial_admin(db: Session, tenant_id: int) -> Dict[str, Any]:
    """无任何用户时，按环境变量创建首个管理员。"""
    if db.query(User).count() > 0:
        return {"created": False, "reason": "库中已有用户，跳过"}

    username = (os.environ.get("INITIAL_ADMIN_USERNAME") or "").strip()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD") or ""
    if not username or not password:
        print(
            "[seed][warn] 库中没有任何用户，且未设置 INITIAL_ADMIN_USERNAME / "
            "INITIAL_ADMIN_PASSWORD；请执行 "
            "python create_admin.py --username <账号> --password <口令> 创建首个管理员",
            file=sys.stderr,
        )
        return {"created": False, "reason": "未配置初始管理员环境变量"}

    try:
        _validate_admin_password(password)
    except ValueError as exc:
        print(f"[seed][warn] INITIAL_ADMIN_PASSWORD 不符合口令要求：{exc}", file=sys.stderr)
        return {"created": False, "reason": f"口令不符合要求：{exc}"}

    role = db.query(Role).filter(Role.role_code == ADMIN_ROLE_CODE).first()
    password_hash, salt = hash_password(password)
    user = User(
        username=username,
        password_hash=password_hash,
        password_salt=salt,
        real_name=(os.environ.get("INITIAL_ADMIN_REAL_NAME") or "").strip() or "系统管理员",
        role_id=role.id if role else None,
        status="active",
        tenant_id=tenant_id,
    )
    db.add(user)
    db.flush()
    print(f"[seed] 已创建初始管理员：{username}（id={user.id}），请尽快在系统中修改为专属口令", file=sys.stderr)
    return {"created": True, "username": username, "user_id": user.id}


def run_if_empty(db: Session) -> Dict[str, Any]:
    """幂等引导初始数据。可重复调用，已存在的数据不会被改写。"""
    tenant = ensure_default_tenant(db)
    roles = ensure_system_roles(db, tenant["tenant_id"])
    admin = ensure_initial_admin(db, tenant["tenant_id"])
    db.commit()
    return {
        "tenant_id": tenant["tenant_id"],
        "tenant_created": tenant["created"],
        "roles_created": roles["created"],
        "admin": admin,
    }
