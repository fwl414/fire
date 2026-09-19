"""最小化 SIP 报文解析与构造（GB28181 信令层）

只覆盖 GB28181 用到的部分：REGISTER / MESSAGE / INVITE / ACK / BYE / OPTIONS，
以及 SDP（用于 INVITE 指定 RTP 接收地址）与 Digest 认证。

设计取舍：GB28181 的信令是纯文本，报文体（应用数据单元）长度由 Content-Length 决定，
因此这里不做流式状态机，UDP 报一条解析一条；TCP 上按 Content-Length 切分（见 service.py）。
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CRLF = "\r\n"
LINE_END = b"\r\n\r\n"
SIP_VERSION = "SIP/2.0"

SIP_METHODS = ("REGISTER", "MESSAGE", "INVITE", "ACK", "BYE", "OPTIONS", "CANCEL", "INFO")


class SipParseError(ValueError):
    """SIP 报文格式错误。"""


@dataclass
class SipMessage:
    """一条 SIP 报文（请求或响应）。"""

    is_request: bool
    method: str = ""
    uri: str = ""
    status_code: int = 0
    reason: str = ""
    headers: List[Tuple[str, str]] = field(default_factory=list)
    body: bytes = b""
    source: Tuple[str, int] = ("", 0)
    raw: bytes = b""

    # ---- 头域读取 ----
    def get(self, name: str, default: str = "") -> str:
        lowered = name.lower()
        for key, value in self.headers:
            if key.lower() == lowered:
                return value
        return default

    def get_all(self, name: str) -> List[str]:
        lowered = name.lower()
        return [value for key, value in self.headers if key.lower() == lowered]

    @property
    def call_id(self) -> str:
        return self.get("Call-ID")

    @property
    def cseq(self) -> str:
        return self.get("CSeq")

    @property
    def cseq_number(self) -> int:
        parts = self.cseq.split()
        try:
            return int(parts[0])
        except (IndexError, ValueError):
            return 0

    @property
    def cseq_method(self) -> str:
        parts = self.cseq.split()
        return parts[1].upper() if len(parts) > 1 else ""

    @property
    def body_text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def header_text(self) -> str:
        first = f"{self.method} {self.uri} {SIP_VERSION}" if self.is_request else f"{SIP_VERSION} {self.status_code} {self.reason}"
        lines = [first] + [f"{key}: {value}" for key, value in self.headers]
        return CRLF.join(lines)


def parse_message(raw: bytes, source: Tuple[str, int] = ("", 0)) -> SipMessage:
    """解析一条 SIP 报文。"""
    if not raw:
        raise SipParseError("空报文")

    separator = LINE_END if LINE_END in raw else b"\n\n"
    head, _, body = raw.partition(separator)
    text = head.decode("utf-8", errors="replace").replace("\r\n", "\n")
    lines = [line for line in text.split("\n")]
    if not lines or not lines[0].strip():
        raise SipParseError("缺少起始行")

    start = lines[0].strip()
    message = SipMessage(is_request=True, body=body, source=source, raw=raw)

    if start.upper().startswith("SIP/"):
        parts = start.split(" ", 2)
        if len(parts) < 2:
            raise SipParseError(f"响应起始行非法：{start}")
        message.is_request = False
        try:
            message.status_code = int(parts[1])
        except ValueError as exc:
            raise SipParseError(f"状态码非法：{start}") from exc
        message.reason = parts[2] if len(parts) > 2 else ""
    else:
        parts = start.split(" ", 2)
        if len(parts) < 3 or not parts[2].upper().startswith("SIP/"):
            raise SipParseError(f"请求起始行非法：{start}")
        message.method = parts[0].upper()
        message.uri = parts[1]

    # 头域：支持折行续行（以空格/制表符开头）
    current_name: Optional[str] = None
    current_value: str = ""
    for line in lines[1:]:
        if not line.strip():
            continue
        if line[0] in (" ", "\t") and current_name:
            current_value += " " + line.strip()
            message.headers[-1] = (current_name, current_value)
            continue
        name, sep, value = line.partition(":")
        if not sep:
            continue
        current_name, current_value = name.strip(), value.strip()
        message.headers.append((current_name, current_value))

    return message


# ---------------- 构造 ----------------

def build_request(
    method: str,
    uri: str,
    headers: Dict[str, str],
    body: bytes = b"",
    *,
    content_type: str = "",
) -> bytes:
    lines = [f"{method} {uri} {SIP_VERSION}"]
    lines += [f"{key}: {value}" for key, value in headers.items()]
    if content_type:
        lines.append(f"Content-Type: {content_type}")
    lines.append(f"Content-Length: {len(body)}")
    return (CRLF.join(lines) + CRLF + CRLF).encode("utf-8") + body


def build_response(
    request: SipMessage,
    status_code: int,
    reason: str,
    body: bytes = b"",
    *,
    content_type: str = "",
    extra_headers: Optional[Dict[str, str]] = None,
    to_tag: str = "",
) -> bytes:
    """按请求生成响应：复制 Via / From / To / Call-ID / CSeq。"""
    lines = [f"{SIP_VERSION} {status_code} {reason}"]
    for value in request.get_all("Via") or [request.get("Via")]:
        if value:
            lines.append(f"Via: {value}")
    frm = request.get("From") or request.get("f")
    to = request.get("To") or request.get("t")
    if frm:
        lines.append(f"From: {frm}")
    if to:
        if to_tag and "tag=" not in to:
            to = add_uri_param(to, "tag", to_tag)
        lines.append(f"To: {to}")
    call_id = request.call_id
    if call_id:
        lines.append(f"Call-ID: {call_id}")
    cseq = request.cseq
    if cseq:
        lines.append(f"CSeq: {cseq}")
    for key, value in (extra_headers or {}).items():
        lines.append(f"{key}: {value}")
    if content_type:
        lines.append(f"Content-Type: {content_type}")
    lines.append(f"Content-Length: {len(body)}")
    return (CRLF.join(lines) + CRLF + CRLF).encode("utf-8") + body


REASONS = {
    100: "Trying",
    180: "Ringing",
    200: "OK",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    481: "Call/Transaction Does Not Exist",
    486: "Busy Here",
    488: "Not Acceptable Here",
    500: "Server Internal Error",
    501: "Not Implemented",
    503: "Service Unavailable",
}


def reason_of(status_code: int) -> str:
    return REASONS.get(status_code, "OK")


# ---------------- 地址与参数 ----------------

def add_uri_param(header_value: str, name: str, value: str) -> str:
    """给 From/To 头域补参数：`<sip:x@y>` → `<sip:x@y>;tag=abc`。"""
    if f"{name}=" in header_value:
        return header_value
    return f"{header_value};{name}={value}"


def extract_uri(header_value: str) -> str:
    """从 From/To 头域里取出 URI（尖括号内优先）。"""
    match = re.search(r"<([^>]+)>", header_value or "")
    if match:
        return match.group(1)
    return (header_value or "").split(";")[0].strip()


def extract_user(uri: str) -> str:
    """`sip:34020000001320000001@10.0.0.1:5060` → 34020000001320000001"""
    match = re.match(r"sips?:([^@;>]+)@?", uri or "")
    return match.group(1) if match else ""


def extract_tag(header_value: str) -> str:
    match = re.search(r"[;?]tag=([^;>\s]+)", header_value or "")
    return match.group(1) if match else ""


def new_tag() -> str:
    return hashlib.md5(os.urandom(16)).hexdigest()[:16]


def new_branch() -> str:
    return "z9hG4bK" + hashlib.md5(os.urandom(16)).hexdigest()[:16]


# ---------------- Digest 认证 ----------------

def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def parse_auth_params(value: str) -> Dict[str, str]:
    """解析 `Digest username="x", realm="y", ...`。"""
    text = (value or "").strip()
    if text.lower().startswith("digest"):
        text = text[len("digest"):]
    params: Dict[str, str] = {}
    for item in re.split(r",\s*", text):
        key, sep, val = item.partition("=")
        if not sep:
            continue
        params[key.strip().lower()] = val.strip().strip('"')
    return params


def build_authorization(
    username: str,
    password: str,
    realm: str,
    nonce: str,
    method: str,
    uri: str,
    *,
    qop: str = "",
    nc: str = "00000001",
    cnonce: str = "",
    algorithm: str = "MD5",
) -> str:
    """按 RFC 2617 计算 Digest 认证头（GB28181 设备侧回归时用）。"""
    ha1 = md5_hex(f"{username}:{realm}:{password}")
    ha2 = md5_hex(f"{method}:{uri}")
    if qop:
        response = md5_hex(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
        return (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", '
            f'qop={qop}, nc={nc}, cnonce="{cnonce}", response="{response}", algorithm={algorithm}'
        )
    response = md5_hex(f"{ha1}:{nonce}:{ha2}")
    return f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}", algorithm={algorithm}'


def verify_authorization(
    authorization: str,
    password: str,
    method: str,
    *,
    realm: str = "",
) -> bool:
    """校验 `Authorization` 头；口令为空或算法不支持时返回 False。"""
    params = parse_auth_params(authorization)
    if not params or not password:
        return False
    username = params.get("username", "")
    nonce = params.get("nonce", "")
    uri = params.get("uri", "")
    if not nonce or not uri:
        return False
    ha1 = md5_hex(f"{username}:{params.get('realm', realm)}:{password}")
    ha2 = md5_hex(f"{method}:{uri}")
    qop = params.get("qop", "")
    if qop:
        expected = md5_hex(
            f"{ha1}:{nonce}:{params.get('nc', '')}:{params.get('cnonce', '')}:{qop}:{ha2}"
        )
    else:
        expected = md5_hex(f"{ha1}:{nonce}:{ha2}")
    return params.get("response", "") == expected


def www_authenticate(realm: str, nonce: str) -> str:
    return f'Digest realm="{realm}", nonce="{nonce}", algorithm=MD5'


# ---------------- SDP ----------------

@dataclass
class SdpInfo:
    address: str = ""
    port: int = 0
    ssrc: str = ""
    media: str = "video"
    raw: str = ""


def build_sdp(address: str, port: int, ssrc: str, *, channel_uri: str = "", setup: str = "passive") -> str:
    """构造 INVITE 的 SDP：告诉设备把 RTP 推到 address:port（收流方为 ZLMediaKit）。"""
    session_id = str(int.from_bytes(os.urandom(4), "big"))
    lines = [
        "v=0",
        f"o={channel_uri.split('@')[0].replace('sip:', '') or '0'} 0 0 IN IP4 {address}",
        "s=Play",
        "c=IN IP4 " + address,
        "t=0 0",
        "m=video " + str(port) + " RTP/AVP 96 98 97",
        "a=recvonly",
        "a=rtpmap:96 PS/90000",
        "a=rtpmap:98 H264/90000",
        "a=rtpmap:97 MPEG4/90000",
        "a=setup:" + setup,
        "a=connection:new",
    ]
    if ssrc:
        lines.append(f"y={ssrc}")
    return CRLF.join(lines) + CRLF


def parse_sdp(text: str) -> SdpInfo:
    """解析设备应答的 SDP：取连接地址、媒体端口与 SSRC。"""
    info = SdpInfo(raw=text or "")
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "c":
            parts = value.split()
            if len(parts) >= 3:
                info.address = parts[2]
        elif key == "m":
            parts = value.split()
            if len(parts) >= 2:
                info.media = parts[0]
                try:
                    info.port = int(parts[1])
                except ValueError:
                    info.port = 0
        elif key == "y":
            info.ssrc = value.strip()
    return info


def split_stream(buffer: bytes) -> Tuple[List[bytes], bytes]:
    """从 TCP 字节流里切出完整的 SIP 报文（按 Content-Length 定长）。

    返回 (完整报文列表, 未凑齐的剩余字节)。SIP over TCP 没有帧头，只能靠
    「头域结束 + Content-Length」判断报文边界，因此半包必须保留到下一次读取。
    """
    messages: List[bytes] = []
    pos = 0
    while True:
        head_end = buffer.find(b"\r\n\r\n", pos)
        sep_len = 4
        if head_end < 0:
            head_end = buffer.find(b"\n\n", pos)
            sep_len = 2
        if head_end < 0:
            break
        head = buffer[pos:head_end].decode("utf-8", errors="replace")
        content_length = 0
        for line in head.splitlines():
            name, _, value = line.partition(":")
            if name.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError:
                    content_length = 0
        body_start = head_end + sep_len
        total = body_start + max(0, content_length)
        if len(buffer) < total:
            break
        messages.append(buffer[pos:total])
        pos = total
    return messages, buffer[pos:]
