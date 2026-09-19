from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import get_db

from services.report_verify_service import verify_report


from services.auth_service import get_current_user

router = APIRouter(tags=["报告验证"])

@router.get("/api/reports/verify/{report_no}")
def api_verify_report(report_no: str):
    return verify_report(report_no)


@router.get("/api/reports/verify-qr/{report_no}")
def api_report_verify_qr(report_no: str, request: Request):
    verify_url = str(request.base_url).rstrip("/") + f"/report-verify/{report_no}"
    try:
        import io
        import qrcode
        img = qrcode.make(verify_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception:
        svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><rect width='240' height='240' fill='white'/><text x='16' y='110' font-size='14'>QR 依赖未安装</text><text x='16' y='138' font-size='12'>{report_no}</text></svg>"
        return Response(content=svg, media_type="image/svg+xml")



