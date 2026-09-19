"""GB/T 26875 消防主机接入路由

接入服务本身（TCP 5016）由 services/gb26875 的常驻服务提供，这里只做台账管理与
下行命令下发，权限与设备接入保持一致（devices:manage）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Device, GB26875Device, User, get_db
from services.auth_service import get_current_tenant_id, get_current_user, require_permission
from services.gb26875 import auth, commands as cmd, service

router = APIRouter(tags=["GB26875 消防主机接入"])


def _owned(db: Session, device_id: int, tenant_id: int) -> GB26875Device:
    row = db.query(GB26875Device).filter(
        GB26875Device.id == device_id,
        GB26875Device.tenant_id == tenant_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="接入设备不存在")
    return row


def _view(db: Session, row: GB26875Device) -> Dict[str, Any]:
    view = auth.device_view(row)
    view["device_system_type_label"] = cmd.system_type_label(row.device_system_type or 0)
    linked: Optional[Device] = None
    if row.device_code:
        linked = db.query(Device).filter(Device.device_code == row.device_code).first()
    view["device_name"] = linked.device_name if linked else ""
    return view


@router.get("/api/gb26875/devices")
def api_list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """已登记的 GB 26875 接入设备目录（口令一律不回传明文）。"""
    rows = (
        db.query(GB26875Device)
        .filter(GB26875Device.tenant_id == tenant_id)
        .order_by(GB26875Device.id.asc())
        .all()
    )
    return {"items": [_view(db, row) for row in rows], "total": len(rows)}


@router.post("/api/gb26875/devices")
def api_create_device(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """登记一台接入的消防主机（用户信息传输装置）。"""
    raw_address = str(payload.get("gb_address") or "").strip()
    try:
        address = auth.normalize_address(raw_address)
    except auth.GB26875AuthError as exc:
        raise HTTPException(status_code=400, detail=exc.message)

    exists = db.query(GB26875Device).filter(GB26875Device.gb_address == address).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"该地址已登记：{address}")

    system_type = payload.get("device_system_type")
    try:
        system_type = int(system_type) if system_type not in (None, "") else 0
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="设备系统类型必须是 0~255 的整数")
    if not 0 <= system_type <= 255:
        raise HTTPException(status_code=400, detail="设备系统类型必须是 0~255 的整数")

    row = GB26875Device(
        tenant_id=tenant_id,
        device_code=str(payload.get("device_code") or "").strip(),
        gb_address=address,
        device_system_type=system_type,
        enabled=bool(payload.get("enabled", True)),
        remark=str(payload.get("remark") or ""),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "接入设备已登记", "device": _view(db, row)}


@router.post("/api/gb26875/devices/{device_id}/credentials")
def api_issue_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """签发（或轮换）设备用户名/口令；明文仅本次返回，之后只能重新签发。"""
    row = _owned(db, device_id, tenant_id)
    username, password = auth.issue_credentials(db, row)
    return {
        "message": "凭证已签发，请立即在消防主机侧录入，口令不会再次展示",
        "device": _view(db, row),
        "username": username,
        "password": password,
    }


@router.delete("/api/gb26875/devices/{device_id}/credentials")
def api_revoke_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """撤销口令校验，回到仅按国标地址放行的模式。"""
    row = _owned(db, device_id, tenant_id)
    auth.revoke_credentials(db, row)
    return {"message": "已撤销凭证，该地址仅做白名单校验", "device": _view(db, row)}


@router.post("/api/gb26875/devices/{device_id}/toggle")
def api_toggle_device(
    device_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """启用或停用该地址的接入（停用后报文一律否认）。"""
    row = _owned(db, device_id, tenant_id)
    row.enabled = bool(payload.get("enabled", True))
    db.commit()
    db.refresh(row)
    return {"message": "接入状态已更新", "device": _view(db, row)}


@router.post("/api/gb26875/devices/{device_id}/sync-time")
def api_sync_time(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("devices:manage")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """向该设备下发时间同步（控制命令），并等待设备确认。"""
    row = _owned(db, device_id, tenant_id)
    result = service.sync_device_time(row.gb_address)
    return {"device": _view(db, row), **result}


@router.get("/api/gb26875/status")
def api_status(
    current_user: User = Depends(get_current_user),
):
    """接入服务运行状态：监听端口、当前连接、累计收发与最后错误。"""
    return service.service_status()
