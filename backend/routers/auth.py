from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from database import get_db, User
from services.auth_service import (
    change_password as auth_change_password,
    get_current_user,
    get_user_permissions,
    get_user_role,
    list_demo_accounts,
    login as auth_login,
    logout as auth_logout,
    refresh_token as auth_refresh_token,
    role_permissions,
    require_permission,
)

public_router = APIRouter(tags=["认证管理"])
router = APIRouter(dependencies=[Depends(get_current_user)], tags=["认证管理"])


@public_router.post("/api/auth/login")
async def api_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    result = auth_login(username, password, db, ip=ip, user_agent=user_agent)
    if not result.get("ok"):
        return JSONResponse(status_code=401, content=result)
    return result


@router.post("/api/auth/refresh")
def api_refresh_token(
    refresh_token: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = auth_refresh_token(refresh_token, db)
    if not result.get("ok"):
        return JSONResponse(status_code=401, content=result)
    return result


@router.post("/api/auth/logout")
def api_logout(request: Request, current_user: User = Depends(get_current_user)):
    token = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    return auth_logout(current_user, token)


@router.get("/api/auth/me")
def api_auth_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = get_user_role(current_user, db)
    permissions = get_user_permissions(current_user, db)
    return {
        "ok": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "real_name": current_user.real_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "department": current_user.department,
            "avatar": current_user.avatar,
            "role": role.role_code if role else "",
            "role_name": role.role_name if role else "",
            "permissions": permissions,
        }
    }


@router.post("/api/auth/change-password")
def api_change_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = auth_change_password(current_user, old_password, new_password, db)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/api/auth/demo-accounts")
def api_demo_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"accounts": list_demo_accounts(db)}


@router.get("/api/auth/role-permissions")
def api_role_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return role_permissions(db)
