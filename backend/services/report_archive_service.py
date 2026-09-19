"""报表产物归档服务

统一负责报表的"生成后保存"与"受控下载"：
- 文件按租户分目录落盘，路径与代码目录隔离
- 每次生成登记一条 report_artifacts 记录（含 sha256 指纹）
- 下载一律走租户校验，不暴露静态目录
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import ReportArtifact

# 报表存储根目录，默认位于后端目录下，可用环境变量覆盖（如挂载独立数据卷）
REPORT_STORAGE_DIR = Path(
    os.environ.get("REPORT_STORAGE_DIR")
    or (Path(__file__).resolve().parent.parent / "data" / "reports")
)


def _tenant_dir(tenant_id: Optional[int]) -> Path:
    bucket = f"tenant_{tenant_id}" if tenant_id is not None else "tenant_shared"
    return REPORT_STORAGE_DIR / bucket


def _safe_filename(name: str) -> str:
    """只保留文件名部分，避免任何路径穿越。"""
    return Path(name or "report").name.replace("..", "_")


def generate_report_no(report_type: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"RPT-{report_type.upper()[:8]}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def archive_report(
    db: Session,
    *,
    tenant_id: Optional[int],
    report_type: str,
    report_format: str,
    title: str,
    filename: str,
    content: bytes,
    media_type: str,
    params: Optional[Dict[str, Any]] = None,
    generated_by: Optional[int] = None,
    generated_by_name: str = "",
) -> ReportArtifact:
    """把报表内容落盘并登记，返回登记记录。"""
    report_no = generate_report_no(report_type)
    safe_name = _safe_filename(filename)
    target_dir = _tenant_dir(tenant_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / f"{report_no}_{safe_name}"
    target.write_bytes(content)

    artifact = ReportArtifact(
        tenant_id=tenant_id,
        report_no=report_no,
        report_type=report_type,
        report_format=report_format,
        title=title or safe_name,
        filename=safe_name,
        file_path=str(target),
        media_type=media_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        params_json=json.dumps(params or {}, ensure_ascii=False),
        generated_by=generated_by,
        generated_by_name=generated_by_name or "",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def list_artifacts(
    db: Session,
    tenant_id: Optional[int],
    report_type: Optional[str] = None,
    limit: int = 50,
) -> List[ReportArtifact]:
    query = db.query(ReportArtifact).filter(ReportArtifact.tenant_id == tenant_id)
    if report_type:
        query = query.filter(ReportArtifact.report_type == report_type)
    return query.order_by(ReportArtifact.created_at.desc()).limit(max(1, min(limit, 200))).all()


def get_artifact(db: Session, tenant_id: Optional[int], artifact_id: int) -> Optional[ReportArtifact]:
    """按ID获取报表产物，带租户校验。"""
    return db.query(ReportArtifact).filter(
        ReportArtifact.id == artifact_id,
        ReportArtifact.tenant_id == tenant_id,
    ).first()


def resolve_artifact_path(artifact: ReportArtifact) -> Optional[Path]:
    """解析报表文件路径，并确保仍位于存储目录内。"""
    if not artifact.file_path:
        return None
    root = REPORT_STORAGE_DIR.resolve()
    path = Path(artifact.file_path).resolve()
    if root != path and root not in path.parents:
        return None
    return path if path.is_file() else None


def delete_artifact(db: Session, tenant_id: Optional[int], artifact_id: int) -> bool:
    """删除报表产物（同时清理磁盘文件）。"""
    artifact = get_artifact(db, tenant_id, artifact_id)
    if not artifact:
        return False
    path = resolve_artifact_path(artifact)
    if path:
        try:
            path.unlink()
        except OSError:
            pass
    db.delete(artifact)
    db.commit()
    return True


def artifact_to_dict(artifact: ReportArtifact, include_path: bool = False) -> Dict[str, Any]:
    data = {
        "id": artifact.id,
        "report_no": artifact.report_no,
        "report_type": artifact.report_type,
        "format": artifact.report_format,
        "title": artifact.title,
        "filename": artifact.filename,
        "media_type": artifact.media_type,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "generated_by_name": artifact.generated_by_name or "",
        "created_at": artifact.created_at.isoformat() if artifact.created_at else "",
        "download_url": f"/api/reports/artifacts/{artifact.id}/download",
    }
    if include_path:
        data["file_path"] = artifact.file_path
    try:
        data["params"] = json.loads(artifact.params_json or "{}")
    except Exception:
        data["params"] = {}
    return data
