"""GB/T 26875.3-2011 数据包编解码（含 TCP 粘包/半包处理）

数据包结构（标准 6.6 表1）：

    启动符            '@@'                     2 字节，固定 0x40 0x40
    业务流水号         uint16                   2 字节，低字节在前
    协议版本号         主版本号 + 用户版本号      2 字节，主版本号固定 1
    时间标签           BCD 秒分时日月年          6 字节
    源地址             6 字节                   低字节在前
    目的地址           6 字节                   低字节在前
    应用数据单元长度    uint16                   2 字节，低字节在前，≤1024
    命令字节           1 字节
    应用数据单元       变长（≤1024 字节）
    校验和             1 字节                   第3~27字节 + 应用数据单元逐字节求和取低8位
    结束符            '##'                     2 字节，固定 0x23 0x23

应用数据单元（标准 7 图5）：类型标志(1) + 信息对象数目(1) + N ×（信息体 + 时间标签(6)）。
确认/否认等命令包的应用数据单元可为空。

地址与时间标签均为 BCD 编码；地址按「低字节在前」传输，即 12 位十进制地址
`340200000001` 在报文中以 `01 00 00 00 02 34` 顺序出现。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

# 信息体长度随类型不同（标准 8.2.1），多信息对象报文要靠它精确切分
from .commands import app_object_body_length

START_FLAG = b"\x40\x40"
END_FLAG = b"\x23\x23"
MAJOR_VERSION = 1

# 控制单元固定 25 字节：流水号2 + 版本2 + 时间6 + 源地址6 + 目的地址6 + 长度2 + 命令1
CONTROL_UNIT_LEN = 25
# 最短帧 = 启动符2 + 控制单元25 + 校验和1 + 结束符2（应用数据单元为空）
MIN_FRAME_LEN = 30
MAX_APP_DATA_LEN = 1024
ADDRESS_BYTES = 6
ADDRESS_DIGITS = ADDRESS_BYTES * 2
TIMESTAMP_BYTES = 6


class FrameError(ValueError):
    """数据包结构或内容不合法。"""


class ChecksumError(FrameError):
    """校验和不匹配。"""


@dataclass
class Frame:
    """一个完整的 GB/T 26875 数据包。"""

    command: int
    source_address: str
    dest_address: str
    app_data: bytes = b""
    seq: int = 0
    user_version: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def app_type(self) -> Optional[int]:
        """应用数据单元的类型标志；无应用数据单元时返回 None。"""
        return self.app_data[0] if self.app_data else None

    @property
    def app_objects(self) -> List["AppObject"]:
        """应用数据单元中的信息对象列表（解析失败返回空列表）。"""
        try:
            _, objects = parse_app_data(self.app_data)
        except FrameError:
            return []
        return objects


@dataclass
class AppObject:
    """应用数据单元中的一个信息对象。"""

    body: bytes
    timestamp: Optional[datetime] = None


# ---------------- 基础编码 ----------------

def checksum(payload: bytes) -> int:
    """算术校验和：逐字节求和后舍去 8 位以上的进位（即取低 8 位）。"""
    return sum(payload) & 0xFF


def encode_bcd(value: int, digits: int) -> bytes:
    """把非负整数按 BCD 编码为固定字节数（每字节存两位十进制数字，左补零）。"""
    text = str(int(value)).rjust(digits, "0")
    if len(text) > digits:
        raise FrameError(f"数值超出 BCD 位宽：{value}")
    # 每两个十进制作一个字节：'34' -> 0x34（高 4 位存十位、低 4 位存个位）
    return bytes(int(text[i:i + 2], 16) for i in range(0, digits, 2))


def decode_bcd(raw: bytes) -> int:
    """BCD 字节串 → 整数。"""
    total = 0
    for byte in raw:
        high, low = byte >> 4, byte & 0x0F
        if high > 9 or low > 9:
            raise FrameError(f"BCD 编码非法：0x{byte:02X}")
        total = total * 100 + high * 10 + low
    return total


def encode_address(address: str) -> bytes:
    """12 位十进制地址 → 6 字节 BCD（低字节在前）。"""
    text = "".join(ch for ch in str(address or "") if ch.isdigit())
    if not text:
        raise FrameError("设备地址不能为空")
    if len(text) > ADDRESS_DIGITS:
        raise FrameError(f"设备地址超过 {ADDRESS_DIGITS} 位：{address}")
    text = text.rjust(ADDRESS_DIGITS, "0")
    return bytes(reversed(encode_bcd(int(text), ADDRESS_DIGITS)))


def decode_address(raw: bytes) -> str:
    """6 字节 BCD（低字节在前）→ 12 位十进制地址字符串。"""
    if len(raw) != ADDRESS_BYTES:
        raise FrameError(f"地址字段长度必须为 {ADDRESS_BYTES} 字节")
    return str(decode_bcd(bytes(reversed(raw)))).rjust(ADDRESS_DIGITS, "0")


def encode_timestamp(moment: datetime) -> bytes:
    """时间标签：秒、分、时、日、月、年各 1 字节 BCD（年取两位）。"""
    return (
        encode_bcd(moment.second, 2)
        + encode_bcd(moment.minute, 2)
        + encode_bcd(moment.hour, 2)
        + encode_bcd(moment.day, 2)
        + encode_bcd(moment.month, 2)
        + encode_bcd(moment.year % 100, 2)
    )


def decode_timestamp(raw: bytes) -> datetime:
    if len(raw) != TIMESTAMP_BYTES:
        raise FrameError(f"时间标签长度必须为 {TIMESTAMP_BYTES} 字节")
    second = decode_bcd(raw[0:1])
    minute = decode_bcd(raw[1:2])
    hour = decode_bcd(raw[2:3])
    day = decode_bcd(raw[3:4])
    month = decode_bcd(raw[4:5])
    year = 2000 + decode_bcd(raw[5:6])
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise FrameError(f"时间标签取值非法：{exc}") from exc


# ---------------- 数据包编码 ----------------

def encode(
    command: int,
    source_address: str,
    dest_address: str,
    app_data: bytes = b"",
    *,
    seq: int = 0,
    user_version: int = 0,
    timestamp: Optional[datetime] = None,
) -> bytes:
    """构造一个完整数据包。"""
    app_data = app_data or b""
    if len(app_data) > MAX_APP_DATA_LEN:
        raise FrameError(f"应用数据单元超过 {MAX_APP_DATA_LEN} 字节上限")
    if not 0 <= int(command) <= 0xFF:
        raise FrameError("命令字节超出 0~255")

    control_unit = (
        int(seq).to_bytes(2, "little")
        + bytes([MAJOR_VERSION, int(user_version) & 0xFF])
        + encode_timestamp(timestamp or datetime.now())
        + encode_address(source_address)
        + encode_address(dest_address)
        + len(app_data).to_bytes(2, "little")
        + bytes([int(command)])
    )
    body = control_unit + app_data
    return START_FLAG + body + bytes([checksum(body)]) + END_FLAG


def encode_app_data(app_type: int, objects: Sequence[AppObject] = ()) -> bytes:
    """构造应用数据单元：类型标志 + 信息对象数目 + 各信息对象（信息体 + 时间标签）。"""
    if len(objects) > 0xFF:
        raise FrameError("信息对象数目超过 255")
    chunks = [bytes([int(app_type) & 0xFF, len(objects)])]
    for obj in objects:
        chunks.append(obj.body)
        chunks.append(encode_timestamp(obj.timestamp or datetime.now()))
    return b"".join(chunks)


def parse_app_data(app_data: bytes) -> Tuple[int, List[AppObject]]:
    """解析应用数据单元，返回 (类型标志, 信息对象列表)。

    一帧可携带多个信息对象（现场批量上传火警时如此）。优先按类型标志对应的信息体
    长度精确切分；类型未收录或为不定长时，退化为「所有信息对象等长」的切分方式；
    两者都对不上则判为格式错误，由调用方回「否认」。
    """
    if not app_data:
        return 0, []
    if len(app_data) < 2:
        raise FrameError("应用数据单元长度不足（至少需要类型标志与信息对象数目）")
    app_type = app_data[0]
    count = app_data[1]
    rest = app_data[2:]
    if count == 0:
        if rest:
            raise FrameError("信息对象数目为 0 但应用数据单元中仍有数据")
        return app_type, []

    body_len = app_object_body_length(app_type)
    if body_len == 0 or len(rest) == count * TIMESTAMP_BYTES:
        # 信息体为空的类型（时间/命令类）：每 6 字节时间标签就是一个信息对象
        return app_type, [
            AppObject(body=b"", timestamp=decode_timestamp(rest[i * TIMESTAMP_BYTES:(i + 1) * TIMESTAMP_BYTES]))
            for i in range(count)
        ]

    if body_len is not None and len(rest) == count * (body_len + TIMESTAMP_BYTES):
        return app_type, [
            AppObject(
                body=rest[i * (body_len + TIMESTAMP_BYTES):i * (body_len + TIMESTAMP_BYTES) + body_len],
                timestamp=decode_timestamp(
                    rest[i * (body_len + TIMESTAMP_BYTES) + body_len:(i + 1) * (body_len + TIMESTAMP_BYTES)]
                ),
            )
            for i in range(count)
        ]

    if len(rest) % count == 0:
        size = len(rest) // count
        if size > TIMESTAMP_BYTES:
            objects = []
            for i in range(count):
                chunk = rest[i * size:(i + 1) * size]
                objects.append(AppObject(body=chunk[:-TIMESTAMP_BYTES], timestamp=decode_timestamp(chunk[-TIMESTAMP_BYTES:])))
            return app_type, objects

    raise FrameError("应用数据单元格式无法解析（信息对象长度与类型不匹配）")


# ---------------- 数据包解码 ----------------

def decode(data: bytes) -> Frame:
    """解析单个完整数据包（数据必须恰好是一个包）。"""
    if len(data) < MIN_FRAME_LEN:
        raise FrameError(f"数据包长度不足 {MIN_FRAME_LEN} 字节")
    if not data.startswith(START_FLAG):
        raise FrameError("启动符非法（应为 0x40 0x40）")
    if not data.endswith(END_FLAG):
        raise FrameError("结束符非法（应为 0x23 0x23）")

    body = data[2:-3]
    app_len = int.from_bytes(body[22:24], "little")
    if app_len > MAX_APP_DATA_LEN:
        raise FrameError(f"应用数据单元长度超限：{app_len}")
    expected_total = 2 + CONTROL_UNIT_LEN + app_len + 1 + 2
    if len(data) != expected_total:
        raise FrameError(f"数据包长度与声明不符：声明 {expected_total} 字节，实际 {len(data)} 字节")

    received = data[-3]
    if received != checksum(body):
        raise ChecksumError(f"校验和错误：报文 0x{received:02X}，计算 0x{checksum(body):02X}")

    return Frame(
        command=body[24],
        source_address=decode_address(body[10:16]),
        dest_address=decode_address(body[16:22]),
        app_data=body[25:25 + app_len],
        seq=int.from_bytes(body[0:2], "little"),
        user_version=body[3],
        timestamp=decode_timestamp(body[4:10]),
    )


def decode_stream(buffer: bytes, *, max_frames: int = 100) -> Tuple[List[Frame], bytes, List[str]]:
    """从 TCP 字节流中切出尽可能多的数据包。

    返回 (完整数据包列表, 未构成完整包的剩余字节, 错误说明列表)。
    半包（长度不足）会保留在剩余字节中等待下一次读取；校验和错误或结束符错误的
    整包会被丢弃并记入错误列表，同时继续尝试解析后续字节，避免一个坏包卡死连接。
    """
    frames: List[Frame] = []
    errors: List[str] = []
    pos = 0
    end = len(buffer)

    while len(frames) < max_frames:
        if end - pos < MIN_FRAME_LEN:
            break
        start = buffer.find(START_FLAG, pos)
        if start < 0:
            # 没有启动符，整段都是噪声
            if pos < end:
                errors.append(f"丢弃 {end - pos} 字节无效数据（未找到启动符）")
            pos = end
            break
        if start > pos:
            errors.append(f"丢弃 {start - pos} 字节无效数据（启动符之前）")
        if end - start < MIN_FRAME_LEN:
            pos = start
            break

        app_len = int.from_bytes(buffer[start + 24:start + 26], "little")
        if app_len > MAX_APP_DATA_LEN:
            errors.append(f"应用数据单元长度超限：{app_len}")
            pos = start + len(START_FLAG)
            continue
        total = MIN_FRAME_LEN + app_len
        if end - start < total:
            # 半包：等待后续字节
            pos = start
            break

        chunk = buffer[start:start + total]
        try:
            frames.append(decode(chunk))
        except FrameError as exc:
            errors.append(str(exc))
        pos = start + total

    return frames, buffer[pos:], errors
