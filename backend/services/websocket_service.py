"""
WebSocket 实时推送服务

设计要点：
- **先认证再收消息**：连接建立后必须首帧发 `{"action": "auth", "token": "..."}`，
  `user_id` / `tenant_id` 一律由令牌解析，不接受客户端自报，否则任何人都能订阅别人的数据。
- **按租户隔离**：消息只发给事件所属租户的连接（告警、工单、系统通知都是租户内数据）。
- **单进程内存态**：连接表存在本进程内存里。多副本部署时，A 副本产生的告警推不到连在
  B 副本上的浏览器，需引入 Redis pub/sub（本期未做，见 README「已知限制」）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger("fire_ai_agent")


@dataclass(eq=False)
class Client:
    """一条已认证的连接。

    `eq=False`：按对象身份入集合，不依赖 WebSocket 对象的相等/哈希语义。
    """

    websocket: WebSocket
    user_id: int
    username: str
    tenant_id: int


class ConnectionManager:
    """按租户维护 WebSocket 连接。"""

    def __init__(self) -> None:
        self._clients: Dict[int, Set[Client]] = {}

    def add(self, client: Client) -> None:
        self._clients.setdefault(client.tenant_id, set()).add(client)
        logger.info(
            "WebSocket 连接建立: tenant_id=%s user=%s 当前连接数=%s",
            client.tenant_id,
            client.username,
            self.active_connection_count(),
        )

    def remove(self, client: Client) -> None:
        clients = self._clients.get(client.tenant_id)
        if not clients:
            return
        clients.discard(client)
        if not clients:
            del self._clients[client.tenant_id]
        logger.info("WebSocket 连接断开: tenant_id=%s user=%s", client.tenant_id, client.username)

    def active_connection_count(self) -> int:
        return sum(len(clients) for clients in self._clients.values())

    async def send_to_tenant(self, tenant_id: int, message: Dict[str, Any]) -> None:
        """发给某租户的全部连接；发送失败的连接顺手摘除，等客户端重连。"""
        text = json.dumps(message, ensure_ascii=False)
        for client in list(self._clients.get(tenant_id, ())):
            try:
                await client.websocket.send_text(text)
            except Exception as exc:
                logger.warning("WebSocket 推送失败，移除连接: user=%s (%s)", client.username, exc)
                self.remove(client)


manager = ConnectionManager()

# 主事件循环：推送往往从同步路由（FastAPI 线程池）或后台任务线程发起，
# 需要 `run_coroutine_threadsafe` 跨线程投递，因此连接建立时把循环记下来。
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def bind_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """记录当前事件循环。

    放在连接建立时记录，这样「有连接」和「能推送」天然同时成立（没有订阅者时不必记）。
    生产环境里所有连接都跑在同一个主循环上，重复记录等同于无操作。
    """
    global _event_loop
    _event_loop = loop


def notify_tenant(tenant_id: Optional[int], message: Dict[str, Any]) -> None:
    """把消息推给某个租户的全部连接。可在同步上下文调用。

    没有任何连接（或事件循环尚未就绪）时直接跳过：没有订阅者的推送没有意义。
    """
    if not tenant_id:
        return
    loop = _event_loop
    if loop is None or loop.is_closed():
        logger.debug("暂无可用事件循环，跳过 WebSocket 推送: %s", message.get("type"))
        return
    future = asyncio.run_coroutine_threadsafe(manager.send_to_tenant(tenant_id, message), loop)
    # 不等待结果，但要把异常取出来，否则会以「Future exception was never retrieved」形式散落
    future.add_done_callback(_log_push_failure)


def _log_push_failure(future: Any) -> None:
    if future.cancelled():
        return
    exc = future.exception()
    if exc is not None:
        logger.warning("WebSocket 推送异常: %s", exc)


def send_alert_notification(tenant_id: Optional[int], alert: Dict[str, Any]) -> None:
    """告警事件（只发给告警所属租户）。"""
    notify_tenant(tenant_id, {
        "type": "alert",
        "timestamp": datetime.utcnow().isoformat(),
        "data": alert,
    })


def send_workorder_notification(tenant_id: Optional[int], workorder: Dict[str, Any]) -> None:
    """工单事件（只发给工单所属租户）。"""
    notify_tenant(tenant_id, {
        "type": "workorder",
        "timestamp": datetime.utcnow().isoformat(),
        "data": workorder,
    })


def send_system_notification(
    tenant_id: Optional[int],
    title: str,
    content: str,
    level: str = "info",
) -> None:
    """系统通知（只发给指定租户）。"""
    notify_tenant(tenant_id, {
        "type": "system",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"title": title, "content": content, "level": level},
    })


def get_active_connection_count() -> int:
    """获取活跃连接数"""
    return manager.active_connection_count()
