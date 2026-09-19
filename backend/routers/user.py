from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db


from services.user_management_service import (create_role, create_user, delete_role, delete_user, get_all_permissions, get_role_all, get_role_by_id, get_user_by_id, list_roles, list_users, reset_user_password, toggle_user_status, update_role, update_user)


from database import User
from services.auth_service import get_current_user, require_permission

router = APIRouter(dependencies=[Depends(get_current_user)])

# ---------------- 角色管理 API（需 system:roles 权限）----------------

@router.get("/api/system/roles")
def api_list_roles(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_permission("system:roles")),
    db: Session = Depends(get_db),
):
    return list_roles(db, keyword=keyword, page=page, page_size=page_size)


@router.get("/api/system/roles/all")
def api_get_roles_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"items": get_role_all(db)}


@router.get("/api/system/roles/{role_id}")
def api_get_role(
    role_id: int,
    current_user: User = Depends(require_permission("system:roles")),
    db: Session = Depends(get_db),
):
    role = get_role_by_id(db, role_id)
    if not role:
        return JSONResponse(status_code=404, content={"message": "角色不存在"})
    return {"role": role}


@router.post("/api/system/roles")
def api_create_role(
    role_code: str = Form(...),
    role_name: str = Form(...),
    description: str = Form(""),
    permissions: str = Form("[]"),
    current_user: User = Depends(require_permission("system:roles")),
    db: Session = Depends(get_db),
):
    try:
        perm_list = json.loads(permissions)
    except Exception:
        perm_list = []
    result = create_role(db, role_code=role_code, role_name=role_name,
                         description=description, permissions=perm_list)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/system/roles/{role_id}")
def api_update_role(
    role_id: int,
    role_name: str = Form(None),
    description: str = Form(None),
    permissions: str = Form(None),
    current_user: User = Depends(require_permission("system:roles")),
    db: Session = Depends(get_db),
):
    perm_list = None
    if permissions is not None:
        try:
            perm_list = json.loads(permissions)
        except Exception:
            perm_list = []
    result = update_role(db, role_id, role_name=role_name,
                         description=description, permissions=perm_list)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/api/system/roles/{role_id}")
def api_delete_role(
    role_id: int,
    current_user: User = Depends(require_permission("system:roles")),
    db: Session = Depends(get_db),
):
    result = delete_role(db, role_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/api/system/permissions")
def api_get_permissions(
    current_user: User = Depends(get_current_user),
):
    return {"groups": get_all_permissions()}


# ---------------- 用户管理 API（需 system:users 权限）----------------

@router.get("/api/system/users")
def api_list_users(
    keyword: str = "",
    role_id: int = 0,
    status: str = "",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    return list_users(db, keyword=keyword, role_id=role_id or None,
                      status=status, page=page, page_size=page_size)


@router.get("/api/system/users/{user_id}")
def api_get_user(
    user_id: int,
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if not user:
        return JSONResponse(status_code=404, content={"message": "用户不存在"})
    return {"user": user}


@router.post("/api/system/users")
def api_create_user(
    username: str = Form(...),
    password: str = Form(...),
    real_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    role_id: int = Form(0),
    department: str = Form(""),
    status: str = Form("active"),
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    result = create_user(db, username=username, password=password,
                         real_name=real_name, email=email, phone=phone,
                         role_id=role_id or None, department=department, status=status)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.put("/api/system/users/{user_id}")
def api_update_user(
    user_id: int,
    real_name: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    role_id: int = Form(None),
    department: str = Form(None),
    status: str = Form(None),
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    result = update_user(db, user_id, real_name=real_name, email=email,
                         phone=phone, role_id=role_id, department=department, status=status)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/api/system/users/{user_id}/reset-password")
def api_reset_password(
    user_id: int,
    new_password: str = Form(...),
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    result = reset_user_password(db, user_id, new_password)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/api/system/users/{user_id}/toggle-status")
def api_toggle_user_status(
    user_id: int,
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    result = toggle_user_status(db, user_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/api/system/users/{user_id}")
def api_delete_user(
    user_id: int,
    current_user: User = Depends(require_permission("system:users")),
    db: Session = Depends(get_db),
):
    result = delete_user(db, user_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


# ---------------- 业务数据 CRUD API（数据库持久化） ----------------

# ===== 设备管理 =====


