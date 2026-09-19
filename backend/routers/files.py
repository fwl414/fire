"""受控文件下载路由

所有上传内容（楼层平面图、CAD、BIM、模型测试图）统一通过本路由访问，
按租户校验归属，不再通过静态目录匿名暴露。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import User, get_db
from services.auth_service import get_current_tenant_id, get_current_user
from services.upload_archive_service import (
    delete_upload,
    get_upload,
    list_uploads,
    resolve_upload_path,
    upload_to_dict,
)

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["文件下载"])


@router.get("/api/files")
def api_list_files(
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """已上传文件清单（按租户隔离）。"""
    rows = list_uploads(db, tenant_id, category=category, limit=limit)
    return {"total": len(rows), "items": [upload_to_dict(row) for row in rows]}


@router.get("/api/files/{upload_id}")
def api_download_file(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """受控下载：校验租户归属后返回文件内容。"""
    upload = get_upload(db, tenant_id, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="文件不存在")

    path = resolve_upload_path(upload)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在或已被清理")

    return FileResponse(
        path,
        media_type=upload.media_type or "application/octet-stream",
        filename=upload.original_name or upload.filename,
    )


@router.delete("/api/files/{upload_id}")
def api_delete_file(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """删除上传文件（同时清理磁盘文件）。"""
    if not delete_upload(db, tenant_id, upload_id):
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"message": "删除成功", "id": upload_id}
