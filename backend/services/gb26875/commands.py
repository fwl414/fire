"""GB/T 26875.3-2011 常量表：控制单元命令字节、应用数据单元类型标志、数据定义。

数值来源：GB/T 26875.3-2011《城市消防远程监控系统 第3部分：报警传输网络通信协议》
- 表2 控制单元命令字节定义
- 表3 类型标志定义
- 表4 系统类型定义
- 6.6 数据包结构（校验和算法、结束符等，见 frame.py）
- 8.2.1.1 建筑消防设施系统状态位定义（图6）
- 8.2.1.3 模拟量类型定义（表6）

真实消防主机常有厂商私有扩展（128~255 为自定义区间），接入时在
TYPE_LABELS / 状态位表里补即可，不需要改 frame.py 的编解码。
"""
from __future__ import annotations

from typing import Optional

# ---------------- 控制单元命令字节（表2） ----------------
COMMAND_RESERVED = 0x00
COMMAND_CONTROL = 0x01      # 控制命令：时间同步（监控中心 → 用户信息传输装置）
COMMAND_SEND_DATA = 0x02    # 发送数据：上传火灾报警与建筑消防设施运行状态
COMMAND_CONFIRM = 0x03      # 确认
COMMAND_REQUEST = 0x04      # 请求：查询信息
COMMAND_RESPONSE = 0x05     # 应答
COMMAND_DENY = 0x06         # 否认

COMMAND_LABELS = {
    COMMAND_RESERVED: "预留",
    COMMAND_CONTROL: "控制命令（时间同步）",
    COMMAND_SEND_DATA: "发送数据",
    COMMAND_CONFIRM: "确认",
    COMMAND_REQUEST: "请求",
    COMMAND_RESPONSE: "应答",
    COMMAND_DENY: "否认",
}


def command_label(value: int) -> str:
    return COMMAND_LABELS.get(value, f"用户自定义/预留（{value}）")


# ---------------- 应用数据单元类型标志（表3） ----------------
# 上行：建筑消防设施
TYPE_SYSTEM_STATUS = 1          # 上传建筑消防设施系统状态
TYPE_COMPONENT_STATUS = 2       # 上传建筑消防设施部件运行状态
TYPE_COMPONENT_ANALOG = 3       # 上传建筑消防设施部件模拟量值
TYPE_COMPONENT_OPERATION = 4    # 上传建筑消防设施操作信息
TYPE_COMPONENT_VERSION = 5      # 上传建筑消防设施软件版本
TYPE_SYSTEM_CONFIG = 6          # 上传建筑消防设施系统配置情况
TYPE_COMPONENT_CONFIG = 7       # 上传建筑消防设施部件配置情况
TYPE_SYSTEM_TIME = 8            # 上传建筑消防设施系统时间
# 上行：用户信息传输装置
TYPE_TRANSMITTER_STATUS = 21    # 上传用户信息传输装置运行状态
TYPE_TRANSMITTER_OPERATION = 24 # 上传用户信息传输装置操作信息
TYPE_TRANSMITTER_VERSION = 25   # 上传用户信息传输装置软件版本
TYPE_TRANSMITTER_CONFIG = 26    # 上传用户信息传输装置配置情况
TYPE_TRANSMITTER_TIME = 28      # 上传用户信息传输装置系统时间
# 下行：读命令与控制（61~68 读建筑消防设施，81~88 读传输装置，89~91 控制）
TYPE_READ_SYSTEM_STATUS = 61
TYPE_READ_COMPONENT_STATUS = 62
TYPE_READ_COMPONENT_ANALOG = 63
TYPE_READ_COMPONENT_OPERATION = 64
TYPE_READ_COMPONENT_VERSION = 65
TYPE_READ_SYSTEM_CONFIG = 66
TYPE_READ_COMPONENT_CONFIG = 67
TYPE_READ_SYSTEM_TIME = 68
TYPE_READ_TRANSMITTER_STATUS = 81
TYPE_READ_TRANSMITTER_OPERATION = 84
TYPE_READ_TRANSMITTER_VERSION = 85
TYPE_READ_TRANSMITTER_CONFIG = 86
TYPE_READ_TRANSMITTER_TIME = 88
TYPE_INIT_TRANSMITTER = 89      # 初始化用户信息传输装置
TYPE_SYNC_TRANSMITTER_TIME = 90 # 同步用户信息传输装置时钟
TYPE_INSPECT = 91               # 查岗命令

TYPE_LABELS = {
    TYPE_SYSTEM_STATUS: "建筑消防设施系统状态",
    TYPE_COMPONENT_STATUS: "建筑消防设施部件运行状态",
    TYPE_COMPONENT_ANALOG: "建筑消防设施部件模拟量值",
    TYPE_COMPONENT_OPERATION: "建筑消防设施操作信息",
    TYPE_COMPONENT_VERSION: "建筑消防设施软件版本",
    TYPE_SYSTEM_CONFIG: "建筑消防设施系统配置情况",
    TYPE_COMPONENT_CONFIG: "建筑消防设施部件配置情况",
    TYPE_SYSTEM_TIME: "建筑消防设施系统时间",
    TYPE_TRANSMITTER_STATUS: "用户信息传输装置运行状态",
    TYPE_TRANSMITTER_OPERATION: "用户信息传输装置操作信息",
    TYPE_TRANSMITTER_VERSION: "用户信息传输装置软件版本",
    TYPE_TRANSMITTER_CONFIG: "用户信息传输装置配置情况",
    TYPE_TRANSMITTER_TIME: "用户信息传输装置系统时间",
    TYPE_READ_SYSTEM_STATUS: "读建筑消防设施系统状态",
    TYPE_READ_COMPONENT_STATUS: "读建筑消防设施部件运行状态",
    TYPE_READ_COMPONENT_ANALOG: "读建筑消防设施部件模拟量值",
    TYPE_READ_COMPONENT_OPERATION: "读建筑消防设施操作信息",
    TYPE_READ_COMPONENT_VERSION: "读建筑消防设施软件版本",
    TYPE_READ_SYSTEM_CONFIG: "读建筑消防设施系统配置情况",
    TYPE_READ_COMPONENT_CONFIG: "读建筑消防设施部件配置情况",
    TYPE_READ_SYSTEM_TIME: "读建筑消防设施系统时间",
    TYPE_READ_TRANSMITTER_STATUS: "读用户信息传输装置运行状态",
    TYPE_READ_TRANSMITTER_OPERATION: "读用户信息传输装置操作信息记录",
    TYPE_READ_TRANSMITTER_VERSION: "读用户信息传输装置软件版本",
    TYPE_READ_TRANSMITTER_CONFIG: "传输装置配置情况",
    TYPE_READ_TRANSMITTER_TIME: "读用户信息传输装置系统时间",
    TYPE_INIT_TRANSMITTER: "初始化用户信息传输装置",
    TYPE_SYNC_TRANSMITTER_TIME: "同步用户信息传输装置时钟",
    TYPE_INSPECT: "查岗命令",
}

# 上行报文类型 → 接入落库类型（device_ingest_service.dispatch 的 kind）
INGEST_KIND_BY_TYPE = {
    TYPE_SYSTEM_STATUS: "event",
    TYPE_COMPONENT_STATUS: "event",
    TYPE_COMPONENT_ANALOG: "telemetry",
    TYPE_COMPONENT_OPERATION: "event",
    TYPE_TRANSMITTER_STATUS: "heartbeat",
    TYPE_TRANSMITTER_OPERATION: "event",
    TYPE_TRANSMITTER_VERSION: "heartbeat",
    TYPE_TRANSMITTER_CONFIG: "heartbeat",
    TYPE_TRANSMITTER_TIME: "heartbeat",
    TYPE_SYSTEM_TIME: "heartbeat",
}

# 视为「链路保活」的上行类型：收到即刷新设备在线状态与最后心跳时间
HEARTBEAT_TYPES = (
    TYPE_TRANSMITTER_STATUS,
    TYPE_TRANSMITTER_VERSION,
    TYPE_TRANSMITTER_CONFIG,
    TYPE_TRANSMITTER_TIME,
    TYPE_SYSTEM_TIME,
)

# 无信息体（信息对象数目为 0）的类型：确认/否认/同步时钟等命令包
BODYLESS_TYPES = (
    TYPE_INIT_TRANSMITTER,
    TYPE_SYNC_TRANSMITTER_TIME,
    TYPE_INSPECT,
)


def type_label(value: int) -> str:
    return TYPE_LABELS.get(value, f"预留/用户自定义（{value}）")


# ---------------- 系统类型（表4） ----------------
SYSTEM_TYPES = {
    0: "通用",
    1: "火灾报警系统",
    10: "消防联动控制器",
    11: "消火栓系统",
    12: "自动喷水灭火系统",
    13: "气体灭火系统",
    14: "水喷雾灭火系统（泵启动方式）",
    15: "水喷雾灭火系统（压力容器启动方式）",
    16: "泡沫灭火系统",
    17: "干粉灭火系统",
    18: "防烟排烟系统",
    19: "防火门及卷帘系统",
    20: "消防电梯",
    21: "消防应急广播",
    22: "消防应急照明和疏散指示系统",
    23: "消防电源",
    24: "消防电话",
}


def system_type_label(value: int) -> str:
    return SYSTEM_TYPES.get(value, f"预留/用户自定义（{value}）")


# ---------------- 建筑消防设施系统状态位（图6，2 字节低字节在前） ----------------
SYSTEM_STATUS_BITS = {
    0: "正常运行",
    1: "火警",
    2: "故障",
    3: "屏蔽",
    4: "监管",
    5: "启动",
    6: "反馈",
    7: "延时状态",
    8: "主电故障",
    9: "备电故障",
    10: "总线故障",
    11: "手动状态",
    12: "配置改变",
    13: "复位",
}

# 状态位 → 事件类型（device_ingest_service.ingest_event 的 event_type）
# 只映射能直接对应到告警语义的位，其余位作为上下文透传，不生成告警。
STATUS_BIT_EVENT_TYPES = {
    1: "fire",
    2: "fault",
    3: "shield",
    4: "supervise",
    8: "main_power_fault",
    9: "backup_power_fault",
    10: "bus_fault",
}

# 告警严重度（事件类型 → severity）
EVENT_SEVERITIES = {
    "fire": "critical",
    "fault": "high",
    "supervise": "medium",
    "shield": "low",
    "main_power_fault": "medium",
    "backup_power_fault": "medium",
    "bus_fault": "medium",
}


def decode_status_bits(status: int) -> list:
    """把 2 字节状态位图解析成中文状态名列表（按位序号升序）。"""
    return [label for bit, label in sorted(SYSTEM_STATUS_BITS.items()) if status >> bit & 0x01]


def status_events(status: int) -> list:
    """状态位图 → 事件类型列表（仅返回能对应告警语义的位）。"""
    return [
        event_type
        for bit, event_type in sorted(STATUS_BIT_EVENT_TYPES.items())
        if status >> bit & 0x01
    ]


# ---------------- 模拟量类型（表6） ----------------
# 表6 中标准已定义的取值；1~5 未在标准正文中给出确定含义，故不臆造，
# 统一按 analog_<类型值> 处理（仍然入遥测/告警上下文，只是没有中文名）。
ANALOG_TYPE_LABELS = {
    6: "气体浓度",
    7: "时间",
    8: "电压",
    9: "电流",
    10: "流量",
}

ANALOG_TYPE_UNITS = {
    6: "%LEL",
    7: "s",
    8: "V",
    9: "A",
    10: "L/s",
}

# 模拟量类型 → 本项目遥测指标名（device_ingest_service.METRIC_ALIASES 的键）
ANALOG_TYPE_METRICS = {
    8: "voltage",
    9: "current",
}


def analog_metric(analog_type: int) -> str:
    return ANALOG_TYPE_METRICS.get(analog_type, f"analog_{analog_type}")


# ---------------- 信息体长度（8.2.1，用于多信息对象报文的切分） ----------------
# 一帧可以携带多个信息对象（现场批量上传火警时如此），类型标志决定每个信息体长度。
# 取 None 表示该类型为不定长（配置说明类字符串），此时按等长切分兜底。
APP_OBJECT_BODY_LENGTHS = {
    TYPE_SYSTEM_STATUS: 4,
    TYPE_COMPONENT_STATUS: 40,
    TYPE_COMPONENT_ANALOG: 10,
    TYPE_COMPONENT_OPERATION: 4,
    TYPE_COMPONENT_VERSION: 4,
    TYPE_COMPONENT_CONFIG: 38,
    TYPE_TRANSMITTER_STATUS: 1,
    TYPE_TRANSMITTER_OPERATION: 2,
    TYPE_TRANSMITTER_VERSION: 2,
}


def app_object_body_length(app_type: int) -> Optional[int]:
    return APP_OBJECT_BODY_LENGTHS.get(app_type)
