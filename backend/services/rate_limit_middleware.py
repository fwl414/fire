"""
请求限流中间件
基于IP和用户的双重限流
支持自定义限流规则
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    """请求限流中间件"""

    def __init__(
        self,
        app,
        ip_limit: int = 1000,
        ip_window: int = 60,
        user_limit: int = 500,
        user_window: int = 60,
        exempt_paths: List[str] = None,
    ):
        super().__init__(app)
        self.ip_limit = ip_limit
        self.ip_window = ip_window
        self.user_limit = user_limit
        self.user_window = user_window
        self.exempt_paths = exempt_paths or []
        self._ip_requests: Dict[str, List[float]] = {}
        self._user_requests: Dict[str, List[float]] = {}

    def _clean_expired(self, requests: Dict[str, List[float]], window: int):
        """清理过期的请求记录"""
        now = time.time()
        to_remove = []
        for key, timestamps in requests.items():
            requests[key] = [t for t in timestamps if now - t < window]
            if not requests[key]:
                to_remove.append(key)
        for key in to_remove:
            requests.pop(key, None)

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return x_real_ip.strip()
        return request.client.host if request.client else "unknown"

    def _get_user_id(self, request: Request) -> str:
        """从Token中提取用户ID"""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[7:]
                if len(token) > 10:
                    return token[:32]
            except Exception:
                pass
        return ""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return await call_next(request)

        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)

        now = time.time()

        self._clean_expired(self._ip_requests, self.ip_window)
        self._clean_expired(self._user_requests, self.user_window)

        ip_requests = self._ip_requests.setdefault(client_ip, [])
        if len(ip_requests) >= self.ip_limit:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": self.ip_window,
                },
            )
        ip_requests.append(now)

        if user_id:
            user_requests = self._user_requests.setdefault(user_id, [])
            if len(user_requests) >= self.user_limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "message": "请求过于频繁，请稍后再试",
                        "retry_after": self.user_window,
                    },
                )
            user_requests.append(now)

        response = await call_next(request)

        remaining_ip = self.ip_limit - len(ip_requests)
        response.headers["X-RateLimit-Remaining-IP"] = str(remaining_ip)
        response.headers["X-RateLimit-Limit-IP"] = str(self.ip_limit)

        if user_id:
            remaining_user = self.user_limit - len(self._user_requests.get(user_id, []))
            response.headers["X-RateLimit-Remaining-User"] = str(remaining_user)
            response.headers["X-RateLimit-Limit-User"] = str(self.user_limit)

        return response
