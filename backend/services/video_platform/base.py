"""视频平台适配器基类与公共数据结构

适配器负责把「某厂商/某协议怎么取设备信息、怎么抓拍、怎么控制云台」这件事封装起来，
上层 video_service 只跟 VideoChannelConfig / ProbeResult 打交道，换厂商只需新增一个适配器文件。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

# 统一云台动作
PTZ_ACTIONS = ("up", "down", "left", "right", "zoom_in", "zoom_out", "stop")

# 抓拍内容嗅探用到的魔数
_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
)


class VideoPlatformError(RuntimeError):
    """平台调用失败：连不上、鉴权失败、返回内容不是图片、协议不支持等。

    `status_code` 让上层可以区分"配置不对"（400）与"设备侧故障"（502），
    默认按上游设备故障处理。
    """

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class VideoChannelConfig:
    """适配器所需的通道配置（密码已解密，只在内存中存在）。"""

    id: Optional[int] = None
    channel_code: str = ""
    channel_name: str = ""
    location: str = ""
    platform: str = "generic"
    protocol: str = "http"
    host: str = ""
    port: int = 80
    channel_no: str = "1"
    username: str = ""
    password: str = ""
    snapshot_path: str = ""
    rtsp_url: str = ""
    ptz_enabled: bool = False
    verify_tls: bool = False

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def has_credentials(self) -> bool:
        return bool(self.username or self.password)


@dataclass
class ProbeResult:
    """探测结果：既用于更新台账状态，也用于返回给前端展示。"""

    online: bool
    device_name: str = ""
    device_model: str = ""
    firmware: str = ""
    channels: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""


def detect_image_type(data: bytes) -> Optional[str]:
    """按魔数判断图片类型；不是图片返回 None。"""
    for magic, mime in _IMAGE_MAGIC:
        if data.startswith(magic):
            return mime
    return None


def ensure_image(data: bytes, *, what: str = "抓拍") -> str:
    """校验响应确实是图片并返回 MIME 类型。

    部分设备在出错时会返回 200 + XML/HTML，若直接透传给前端会得到一张坏图，
    这里统一拦下来转成可读的失败原因。
    """
    if not data:
        raise VideoPlatformError(f"{what}内容为空")
    mime = detect_image_type(data)
    if not mime:
        preview = data[:120].decode("utf-8", errors="ignore").replace("\n", " ").strip()
        raise VideoPlatformError(f"{what}返回的不是图片内容：{preview}")
    return mime


class VideoPlatformAdapter(abc.ABC):
    """视频平台适配器基类。"""

    platform = "generic"
    label = "通用"

    def __init__(
        self,
        config: VideoChannelConfig,
        *,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 10.0,
    ):
        self.config = config
        self.timeout = timeout
        # 允许注入客户端（测试时可传入 httpx.MockTransport 构造的客户端）
        self._external_client = client

    # ---------------- 供子类复用的工具 ----------------

    def auth(self) -> Optional[httpx.Auth]:
        """返回 httpx 认证对象；默认使用摘要认证（海康/大华均支持）。"""
        if not self.config.has_credentials:
            return None
        return httpx.DigestAuth(self.config.username, self.config.password)

    def basic_auth(self) -> Optional[httpx.Auth]:
        if not self.config.has_credentials:
            return None
        return httpx.BasicAuth(self.config.username, self.config.password)

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            verify=self.config.verify_tls,
            follow_redirects=False,
        )

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """发起请求，把网络层异常统一转成 VideoPlatformError。"""
        if not self.config.host:
            raise VideoPlatformError("未配置设备地址", status_code=400)

        kwargs.setdefault("auth", self.auth())
        owns_client = self._external_client is None
        client = self._external_client or self._make_client()
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise VideoPlatformError(
                f"无法连接 {self.config.host}:{self.config.port}（{type(exc).__name__}）"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()
        return response

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("GET", f"{self.config.base_url}{path}", **kwargs)

    @staticmethod
    def _status_hint(response: httpx.Response) -> str:
        if response.status_code in (401, 403):
            return "设备拒绝访问，请检查账号密码或权限"
        if response.status_code == 404:
            return "设备返回 404，接口地址或通道号可能不正确"
        return f"设备返回 HTTP {response.status_code}"

    # ---------------- 子类需要实现的协议能力 ----------------

    @abc.abstractmethod
    async def probe(self) -> ProbeResult:
        """探测设备可达性与基本信息。"""

    @abc.abstractmethod
    async def snapshot(self) -> bytes:
        """获取一张抓拍图（返回原始字节）。"""

    async def ptz(self, action: str, speed: int = 5) -> Dict[str, Any]:
        """云台控制；默认不支持。"""
        raise VideoPlatformError(f"{self.label} 适配器不支持云台控制", status_code=400)

    async def query_recordings(self, start: str, end: str, *, limit: int = 100) -> Dict[str, Any]:
        """检索某个时间段的录像片段。

        默认返回 `supported=False`，**不是**返回一个空列表 —— 空列表会被读成
        「这段时间没有录像」，而真实情况可能是这个平台根本没有录像检索能力，
        两者必须能区分开，界面据 supported 决定是显示空态还是显示「平台未提供」。
        """
        return {
            "supported": False,
            "items": [],
            "message": f"{self.label} 适配器未实现录像检索（录像清单需由录像机 / NVR 提供）",
        }

    def stream_info(self) -> Dict[str, Any]:
        """取流地址信息。浏览器无法直接播放 RTSP，这里如实说明。"""
        rtsp = self.config.rtsp_url or ""
        return {
            "rtsp_url": rtsp,
            "playable_in_browser": False,
            "note": (
                "浏览器不能直接播放 RTSP，实时预览需接入流媒体网关（如 ZLMediaKit）转 HLS/FLV；"
                "当前环境使用抓拍图轮询实现准实时画面。"
            ),
        }
