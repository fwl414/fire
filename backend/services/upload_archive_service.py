"""上传文件归档服务

统一负责上传内容的"落盘 + 登记 + 受控下载"：
- 文件按类别存放于 uploads/ 下，目录不对外静态暴露
- 每次上传登记一条 uploaded_files 记录（含 sha256 指纹与归属租户）
- 下载一律经 /api/files/{id} 做租户校验
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import UploadedFile
from services import storage_service
from services.common_utils import random_upload_name

BACKEND_DIR = Path(__file__).resolve().parent.parent

# 上传存储根目录，默认 backend/uploads，可用环境变量挂载独立数据卷
UPLOAD_ROOT = Path(os.environ.get("UPLOAD_STORAGE_DIR") or (BACKEND_DIR / "uploads"))

# 类别 -> 子目录
CATEGORY_DIRS = {
    "floor_plan": "floor_plans",
    "cad": "cad",
    "bim": "bim",
    "inspection": "inspection",
    "model_test": "model_test",
    "video_snapshot": "video_snapshots",
}

# 类别 -> 默认前缀
CATEGORY_PREFIXES = {
    "floor_plan": "floor",
    "cad": "cad",
    "bim": "bim",
    "inspection": "inspection",
    "model_test": "model_test",
    "video_snapshot": "video",
}


def category_dir(category: str) -> Path:
    sub = CATEGORY_DIRS.get(category, "misc")
    path = UPLOAD_ROOT / sub
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(
    db: Session,
    *,
    tenant_id: Optional[int],
    category: str,
    content: bytes,
    ext: str,
    media_type: str = "",
    original_name: str = "",
    owner_id: Optional[int] = None,
    owner_name: str = "",
    filename: Optional[str] = None,
) -> UploadedFile:
    """把上传内容写入受控目录并登记，返回登记记录。

    落盘统一走 `storage_service`：未配置对象存储时就是纯本地写入；
    配置了 S3 时本地照写（视觉识别等链路需要本地路径）并额外镜像到对象存储。
    """
    stored_name = filename or random_upload_name(CATEGORY_PREFIXES.get(category, "file"), ext)
    key = f"{category}/{Path(stored_name).name}"
    target = storage_service.put(key, content)

    record = UploadedFile(
        tenant_id=tenant_id,
        category=category,
        filename=target.name,
        original_name=Path(original_name or stored_name).name,
        file_path=str(target),
        media_type=media_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        owner_id=owner_id,
        owner_name=owner_name or "",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_upload(db: Session, tenant_id: Optional[int], upload_id: int) -> Optional[UploadedFile]:
    return db.query(UploadedFile).filter(
        UploadedFile.id == upload_id,
        UploadedFile.tenant_id == tenant_id,
    ).first()


def find_upload(
    db: Session,
    tenant_id: Optional[int],
    category: str,
    filename: str,
) -> Optional[UploadedFile]:
    """按类别+存储文件名查找（用于兼容旧的 /api/uploads 链接）。"""
    return db.query(UploadedFile).filter(
        UploadedFile.tenant_id == tenant_id,
        UploadedFile.category == category,
        UploadedFile.filename == Path(filename or "").name,
    ).order_by(UploadedFile.created_at.desc()).first()


def list_uploads(
    db: Session,
    tenant_id: Optional[int],
    category: Optional[str] = None,
    limit: int = 50,
) -> List[UploadedFile]:
    query = db.query(UploadedFile).filter(UploadedFile.tenant_id == tenant_id)
    if category:
        query = query.filter(UploadedFile.category == category)
    return query.order_by(UploadedFile.created_at.desc()).limit(max(1, min(limit, 200))).all()


def storage_key(upload: UploadedFile) -> Optional[str]:
    """由 `file_path` 推导出相对上传根目录的存储键。

    存储键是跨实例稳定标识：多实例部署时各实例的上传根目录可能指向不同卷，
    但键相同，因此可从对象存储取回。历史数据若已是相对路径也直接接受。
    """
    if not upload.file_path:
        return None
    raw = str(upload.file_path).replace("\\", "/")
    root = UPLOAD_ROOT.resolve().as_posix().rstrip("/")
    if raw.startswith(root + "/"):
        return raw[len(root) + 1:]
    if raw.startswith("/") or ":" in raw:
        return None
    return raw.lstrip("/")


def resolve_upload_path(upload: UploadedFile) -> Optional[Path]:
    """解析文件路径，并确保仍位于上传根目录内。

    本地命中直接返回；本地缺失（例如请求被负载均衡到另一个实例）时从对象存储取回。
    """
    key = storage_key(upload)
    if key:
        materialized = storage_service.materialize(key)
        if materialized is not None:
            return materialized

    if not upload.file_path:
        return None
    root = UPLOAD_ROOT.resolve()
    path = Path(upload.file_path).resolve()
    if root != path and root not in path.parents:
        return None
    return path if path.is_file() else None


def delete_upload(db: Session, tenant_id: Optional[int], upload_id: int) -> bool:
    upload = get_upload(db, tenant_id, upload_id)
    if not upload:
        return False
    key = storage_key(upload)
    if key:
        storage_service.delete(key)
    else:
        path = resolve_upload_path(upload)
        if path:
            try:
                path.unlink()
            except OSError:
                pass
    db.delete(upload)
    db.commit()
    return True


def upload_to_dict(upload: UploadedFile, include_path: bool = False) -> Dict[str, Any]:
    data = {
        "id": upload.id,
        "category": upload.category,
        "filename": upload.filename,
        "original_name": upload.original_name or "",
        "media_type": upload.media_type or "",
        "size_bytes": upload.size_bytes,
        "sha256": upload.sha256,
        "owner_name": upload.owner_name or "",
        "created_at": upload.created_at.isoformat() if upload.created_at else "",
        "download_url": f"/api/files/{upload.id}",
    }
    if include_path:
        data["file_path"] = upload.file_path
    return data
