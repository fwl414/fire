"""
用户与角色管理服务
用户CRUD、角色CRUD、权限配置
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database import User, Role, hash_password, verify_password


# ========== 角色管理 ==========

def list_roles(
    db: Session,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """角色列表（分页）"""
    query = db.query(Role)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (Role.role_name.like(like)) |
            (Role.role_code.like(like)) |
            (Role.description.like(like))
        )

    total = query.count()
    roles = (
        query.order_by(Role.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_role_to_dict(r) for r in roles],
    }


def get_role_all(db: Session) -> List[Dict[str, Any]]:
    """获取所有角色（用于下拉选择）"""
    roles = db.query(Role).order_by(Role.id.asc()).all()
    return [_role_to_dict(r) for r in roles]


def get_role_by_id(db: Session, role_id: int) -> Optional[Dict[str, Any]]:
    """根据ID获取角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    return _role_to_dict(role) if role else None


def get_role_by_code(db: Session, role_code: str) -> Optional[Dict[str, Any]]:
    """根据编码获取角色"""
    role = db.query(Role).filter(Role.role_code == role_code).first()
    return _role_to_dict(role) if role else None


def create_role(
    db: Session,
    role_code: str,
    role_name: str,
    description: str = "",
    permissions: List[str] = None,
    is_system: bool = False,
) -> Dict[str, Any]:
    """创建角色"""
    role_code = (role_code or "").strip()
    role_name = (role_name or "").strip()

    if not role_code:
        return {"ok": False, "message": "角色编码不能为空"}
    if not role_name:
        return {"ok": False, "message": "角色名称不能为空"}

    existing = db.query(Role).filter(Role.role_code == role_code).first()
    if existing:
        return {"ok": False, "message": f"角色编码 {role_code} 已存在"}

    role = Role(
        role_code=role_code,
        role_name=role_name,
        description=description or "",
        permissions=json.dumps(permissions or [], ensure_ascii=False),
        is_system=is_system,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"ok": True, "message": "角色创建成功", "role": _role_to_dict(role)}


def update_role(
    db: Session,
    role_id: int,
    role_name: str = None,
    description: str = None,
    permissions: List[str] = None,
) -> Dict[str, Any]:
    """更新角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return {"ok": False, "message": "角色不存在"}

    if role_name is not None:
        role.role_name = role_name.strip()
    if description is not None:
        role.description = description
    if permissions is not None:
        role.permissions = json.dumps(permissions, ensure_ascii=False)

    role.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(role)
    return {"ok": True, "message": "角色更新成功", "role": _role_to_dict(role)}


def delete_role(db: Session, role_id: int) -> Dict[str, Any]:
    """删除角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return {"ok": False, "message": "角色不存在"}

    if role.is_system:
        return {"ok": False, "message": "系统内置角色不可删除"}

    user_count = db.query(User).filter(User.role_id == role_id).count()
    if user_count > 0:
        return {"ok": False, "message": f"该角色下有 {user_count} 个用户，无法删除"}

    db.delete(role)
    db.commit()
    return {"ok": True, "message": "角色删除成功"}


def _role_to_dict(role: Role) -> Dict[str, Any]:
    try:
        permissions = json.loads(role.permissions or "[]")
    except Exception:
        permissions = []
    return {
        "id": role.id,
        "role_code": role.role_code,
        "role_name": role.role_name,
        "description": role.description or "",
        "permissions": permissions,
        "is_system": bool(role.is_system),
        "created_at": role.created_at.isoformat() if role.created_at else "",
        "updated_at": role.updated_at.isoformat() if role.updated_at else "",
    }


# ========== 用户管理 ==========

def list_users(
    db: Session,
    keyword: str = "",
    role_id: int = None,
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """用户列表（分页）"""
    query = db.query(User)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (User.username.like(like)) |
            (User.real_name.like(like)) |
            (User.email.like(like)) |
            (User.phone.like(like))
        )
    if role_id:
        query = query.filter(User.role_id == role_id)
    if status:
        query = query.filter(User.status == status)

    total = query.count()
    users = (
        query.order_by(User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    role_map = {}
    for u in users:
        if u.role_id and u.role_id not in role_map:
            r = db.query(Role).filter(Role.id == u.role_id).first()
            if r:
                role_map[u.role_id] = {"id": r.id, "role_code": r.role_code, "role_name": r.role_name}

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_user_to_dict(u, role_map.get(u.role_id)) for u in users],
    }


def get_user_by_id(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    """根据ID获取用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    role = None
    if user.role_id:
        r = db.query(Role).filter(Role.id == user.role_id).first()
        if r:
            role = {"id": r.id, "role_code": r.role_code, "role_name": r.role_name}
    return _user_to_dict(user, role)


def create_user(
    db: Session,
    username: str,
    password: str,
    real_name: str = "",
    email: str = "",
    phone: str = "",
    role_id: int = None,
    department: str = "",
    status: str = "active",
) -> Dict[str, Any]:
    """创建用户"""
    username = (username or "").strip()
    if not username:
        return {"ok": False, "message": "用户名不能为空"}
    if len(username) < 3:
        return {"ok": False, "message": "用户名长度不能少于3位"}
    if not password or len(password) < 6:
        return {"ok": False, "message": "密码长度不能少于6位"}

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return {"ok": False, "message": f"用户名 {username} 已存在"}

    if role_id:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return {"ok": False, "message": "指定的角色不存在"}

    hashed, salt = hash_password(password)
    user = User(
        username=username,
        password_hash=hashed,
        password_salt=salt,
        real_name=real_name or "",
        email=email or "",
        phone=phone or "",
        role_id=role_id,
        department=department or "",
        status=status or "active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "message": "用户创建成功", "user": _user_to_dict(user)}


def update_user(
    db: Session,
    user_id: int,
    real_name: str = None,
    email: str = None,
    phone: str = None,
    role_id: int = None,
    department: str = None,
    status: str = None,
) -> Dict[str, Any]:
    """更新用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "message": "用户不存在"}

    if real_name is not None:
        user.real_name = real_name
    if email is not None:
        user.email = email
    if phone is not None:
        user.phone = phone
    if role_id is not None:
        if role_id == 0 or role_id == "":
            user.role_id = None
        else:
            role = db.query(Role).filter(Role.id == role_id).first()
            if not role:
                return {"ok": False, "message": "指定的角色不存在"}
            user.role_id = role_id
    if department is not None:
        user.department = department
    if status is not None:
        user.status = status

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return {"ok": True, "message": "用户更新成功", "user": _user_to_dict(user)}


def reset_user_password(db: Session, user_id: int, new_password: str) -> Dict[str, Any]:
    """重置用户密码"""
    if not new_password or len(new_password) < 6:
        return {"ok": False, "message": "密码长度不能少于6位"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "message": "用户不存在"}

    hashed, salt = hash_password(new_password)
    user.password_hash = hashed
    user.password_salt = salt
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": "密码重置成功"}


def delete_user(db: Session, user_id: int) -> Dict[str, Any]:
    """删除用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "message": "用户不存在"}

    if user.username == "admin":
        return {"ok": False, "message": "管理员账号不可删除"}

    db.delete(user)
    db.commit()
    return {"ok": True, "message": "用户删除成功"}


def toggle_user_status(db: Session, user_id: int) -> Dict[str, Any]:
    """切换用户启用/禁用状态"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "message": "用户不存在"}

    if user.username == "admin":
        return {"ok": False, "message": "管理员账号不可禁用"}

    user.status = "inactive" if user.status == "active" else "active"
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": f"用户已{'禁用' if user.status == 'inactive' else '启用'}", "status": user.status}


def _user_to_dict(user: User, role: Dict[str, Any] = None) -> Dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name or "",
        "email": user.email or "",
        "phone": user.phone or "",
        "role_id": user.role_id,
        "role_code": role.get("role_code", "") if role else "",
        "role_name": role.get("role_name", "") if role else "",
        "department": user.department or "",
        "avatar": user.avatar or "",
        "status": user.status or "active",
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else "",
        "last_login_ip": user.last_login_ip or "",
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "updated_at": user.updated_at.isoformat() if user.updated_at else "",
    }


# ========== 权限清单 ==========

ALL_PERMISSIONS = [
    {"group": "仪表盘", "items": [
        {"code": "dashboard:view", "name": "查看仪表盘"},
    ]},
    {"group": "设备管理", "items": [
        {"code": "devices:view", "name": "查看设备"},
        {"code": "devices:manage", "name": "管理设备（增删改）"},
    ]},
    {"group": "巡检管理", "items": [
        {"code": "inspection:run", "name": "发起智能巡检"},
        {"code": "inspection:manage", "name": "管理巡检任务"},
    ]},
    {"group": "巡检档案", "items": [
        {"code": "records:view", "name": "查看巡检档案"},
        {"code": "records:manage", "name": "管理巡检档案"},
    ]},
    {"group": "工单管理", "items": [
        {"code": "workorders:view", "name": "查看工单"},
        {"code": "workorders:create", "name": "创建工单"},
        {"code": "workorders:update", "name": "更新工单状态"},
        {"code": "workorders:manage", "name": "管理全部工单"},
    ]},
    {"group": "风险态势", "items": [
        {"code": "building:view", "name": "查看建筑风险"},
        {"code": "risk:manage", "name": "管理风险配置"},
        {"code": "risk:model", "name": "训练风险预测模型"},
    ]},
    {"group": "设备告警", "items": [
        {"code": "alerts:view", "name": "查看告警"},
        {"code": "alerts:manage", "name": "处理告警"},
    ]},
    {"group": "知识库", "items": [
        {"code": "qa:use", "name": "使用知识问答"},
        {"code": "knowledge:manage", "name": "管理知识库"},
    ]},
    {"group": "报表中心", "items": [
        {"code": "report:view", "name": "查看报表"},
        {"code": "report:export", "name": "导出报表"},
    ]},
    {"group": "批量巡检", "items": [
        {"code": "batch:view", "name": "查看批量任务"},
        {"code": "batch:create", "name": "创建批量任务"},
    ]},
    {"group": "值班管理", "items": [
        {"code": "duty:manage", "name": "管理排班（排班、值班记录、交接班）"},
    ]},
    {"group": "培训管理", "items": [
        {"code": "training:view", "name": "查看培训（计划、考试、档案）"},
        {"code": "training:manage", "name": "管理培训（新建、编辑、删除）"},
    ]},
    {"group": "决策日志", "items": [
        {"code": "decision:view", "name": "查看决策日志"},
    ]},
    {"group": "操作日志", "items": [
        {"code": "logs:view", "name": "查看操作日志"},
    ]},
    {"group": "系统管理", "items": [
        {"code": "system:users", "name": "用户管理"},
        {"code": "system:roles", "name": "角色管理"},
        {"code": "system:settings", "name": "系统设置"},
        {"code": "system:tasks", "name": "任务中心运维（取消/重试/查看 worker 状态）"},
    ]},
]


def get_all_permissions() -> List[Dict[str, Any]]:
    """获取所有权限项清单"""
    return ALL_PERMISSIONS
