from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, WebSocket, WebSocketDisconnect

from database import SessionLocal
from services.auth_service import authenticate_token, get_current_tenant_id, get_current_user
from services.websocket_service import (
    Client,
    bind_event_loop,
    get_active_connection_count,
    manager,
    send_system_notification,
)

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["WebSocket"])

# WebSocket 单独一个 router：HTTP router 上的依赖要的是 `Authorization` 头，
# 而握手阶段没有这个入口，改用「连上后首帧认证」（见 ws_notifications）。
ws_router = APIRouter(tags=["WebSocket"])

# 首帧认证时限：连上却不发认证帧的连接会被主动关闭，避免留下匿名空连接
AUTH_TIMEOUT_SECONDS = 10


@router.get("/api/ws/status")
def api_ws_status():
    return {
        "status": "running",
        "active_connections": get_active_connection_count(),
        "endpoint": "ws://localhost:8000/ws/notifications",
        "supported_channels": ["alert", "workorder", "system"],
        "auth": '连接后首帧发送 {"action": "auth", "token": "<access_token>"}',
    }


@router.post("/api/ws/test-broadcast")
def api_ws_test_broadcast(
    message: str = Form("测试消息"),
    message_type: str = Form("system"),
    tenant_id: int = Depends(get_current_tenant_id),
):
    send_system_notification(tenant_id, "测试通知", message, level="info")
    return {"ok": True, "message": "测试消息已发送"}


@ws_router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    """实时推送端点。

    握手阶段拿不到 HTTP 令牌，因此改成「连上后首帧认证」：
    `{"action": "auth", "token": "<access_token>"}`，通过后回 `{"type": "auth_ok"}`。
    user_id / tenant_id 只认令牌解析结果，客户端自报的一律忽略。
    """
    await websocket.accept()
    # 推送可能从同步路由或后台线程发起，需要跨线程投递到同一个事件循环
    bind_event_loop(asyncio.get_running_loop())

    client = await _authenticate(websocket)
    if client is None:
        return

    manager.add(client)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # 心跳：客户端定期发 ping，服务端回 pong（同时让 nginx 不会因空闲掐连接）
            if payload.get("action") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                }))
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(client)


async def _authenticate(websocket: WebSocket) -> Optional[Client]:
    """等首帧认证帧并校验令牌；失败时以 4401/4403 关闭连接并返回 None。"""
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await websocket.close(code=4401, reason="未在时限内完成认证")
        return None
    except WebSocketDisconnect:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    if payload.get("action") != "auth":
        await websocket.close(code=4401, reason="首帧必须是认证帧")
        return None

    db = SessionLocal()
    try:
        user = authenticate_token(str(payload.get("token") or ""), db)
        if user is None:
            await websocket.close(code=4401, reason="令牌无效或已过期")
            return None
        if not user.tenant_id:
            # 推送按租户下发，没有租户的连接没有任何可订阅的内容
            await websocket.close(code=4403, reason="账号未关联有效租户")
            return None

        await websocket.send_text(json.dumps({
            "type": "auth_ok",
            "data": {
                "user_id": user.id,
                "username": user.username,
                "tenant_id": user.tenant_id,
            },
        }, ensure_ascii=False))
        return Client(
            websocket=websocket,
            user_id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
        )
    finally:
        db.close()
