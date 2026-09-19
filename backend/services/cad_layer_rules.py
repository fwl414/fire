"""CAD 图层名约定

DXF 里没有"这是墙、那是门"的语义，只能靠图层名（以及块名）来识别。
这份约定同时被两处使用：

- `routers/building_detail.py` 的 `/api/cad/parse` 解析器
- `tools/dxf_layer_report.py` 图纸筛选脚本

所以抽到独立模块，避免两边各写一份——否则脚本筛出来"可解析"的图纸
与实际解析结果会对不上。这里只放常量与纯函数，不引入任何项目依赖，
方便脚本单独调用。
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set, Tuple

# 图层名关键词：只要图层名里包含其中任意一个，就归入该类别。
# 英文关键词统一按大写比较，中文按原样比较（大小写转换不影响中文）。
LAYER_WALL_KEYWORDS: Tuple[str, ...] = ("WALL", "墙", "墙体", "WALLS")
LAYER_AXIS_KEYWORDS: Tuple[str, ...] = ("AXIS", "轴网", "轴线")
LAYER_DOOR_KEYWORDS: Tuple[str, ...] = ("DOOR", "门", "门窗")
LAYER_DEVICE_KEYWORDS: Tuple[str, ...] = (
    "DEVICE", "设备", "消防", "FIRE", "SMOKE", "烟感", "喷淋", "SPRINKLE",
)
LAYER_TEXT_KEYWORDS: Tuple[str, ...] = ("TEXT", "文字", "标注", "房间", "ROOM")

# 设备块名（INSERT 实体）→ 设备类型
BLOCK_DEVICE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "smoke": ("烟感", "SMOKE"),
    "sprinkler": ("喷淋", "SPRINKLE"),
    "hydrant": ("消火", "HYDRANT"),
    "manual": ("手报", "MANUAL"),
    "extinguisher": ("灭火器", "EXTING"),
}

# 图层名 → 设备类型（CIRCLE 实体按图层判类型）
CIRCLE_DEVICE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "sprinkler": ("喷淋", "SPRINKLE"),
    "heat": ("温感", "HEAT"),
    "hydrant": ("消火", "HYDRANT"),
    "manual": ("手报", "MANUAL"),
    "extinguisher": ("灭火器", "EXTING"),
}

CATEGORY_LABELS: Dict[str, str] = {
    "wall": "墙体",
    "axis": "轴线",
    "door": "门窗",
    "device": "消防设备",
    "text": "文字/房间",
}

# 拼音首字母缩写码 -> (类别, 设备类型)。
# 国内施工图大量用缩写命名（XF=消防、XHS=消火栓、PL=喷淋、PT=喷头），
# 这类码只有 2-4 个字母，**不能按"包含"判断**——`PT` 会命中 `POINT`、`PTEXT`，
# `PL` 会命中 `PLOT`，必然误报。所以先按分隔符切成整段码，再做精确比对。
CODE_TOKENS: Dict[str, Tuple[str, str]] = {
    "XF": ("device", "hydrant"),      # 消防
    "XHS": ("device", "hydrant"),     # 消火栓
    "PL": ("device", "sprinkler"),    # 喷淋
    "PT": ("device", "sprinkler"),    # 喷头
}

_CODE_SPLIT_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")


def code_tokens(name: str) -> List[str]:
    """把图层名/块名切成整段代码，用于和缩写码精确比对。

    `P_XF_GJ` -> ['P', 'XF', 'GJ']；`_XHS2` -> ['XHS']（去掉结尾序号）；
    `0喷淋` -> ['喷淋']。
    """
    tokens: List[str] = []
    for raw in _CODE_SPLIT_RE.split((name or "").upper()):
        token = raw.strip("0123456789")
        if token:
            tokens.append(token)
    return tokens


def code_token_match(name: str) -> str:
    """返回命中的缩写码对应的设备类型，没命中返回空串。"""
    for token in code_tokens(name):
        hit = CODE_TOKENS.get(token)
        if hit:
            return hit[1]
    return ""


def matches(name: str, keywords: Iterable[str]) -> bool:
    """名字里是否包含任一关键词（英文不区分大小写）。"""
    text = (name or "").upper()
    return any(str(kw).upper() in text for kw in keywords)


def classify_layer(layer_name: str) -> Set[str]:
    """返回图层名命中的类别集合，取值见 CATEGORY_LABELS 的键。"""
    hit: Set[str] = set()
    if matches(layer_name, LAYER_WALL_KEYWORDS):
        hit.add("wall")
    if matches(layer_name, LAYER_AXIS_KEYWORDS):
        hit.add("axis")
    if matches(layer_name, LAYER_DOOR_KEYWORDS):
        hit.add("door")
    if matches(layer_name, LAYER_DEVICE_KEYWORDS):
        hit.add("device")
    if matches(layer_name, LAYER_TEXT_KEYWORDS):
        hit.add("text")
    for token in code_tokens(layer_name):
        entry = CODE_TOKENS.get(token)
        if entry:
            hit.add(entry[0])
    return hit


def device_type_by_block(block_name: str) -> str:
    """按块名判设备类型，认不出返回空串。"""
    for device_type, keywords in BLOCK_DEVICE_KEYWORDS.items():
        if matches(block_name, keywords):
            return device_type
    return code_token_match(block_name)


def device_type_by_layer(layer_name: str) -> str:
    """按图层名判设备类型，认不出返回空串。"""
    for device_type, keywords in CIRCLE_DEVICE_KEYWORDS.items():
        if matches(layer_name, keywords):
            return device_type
    return code_token_match(layer_name)


def convention_hint() -> str:
    """给用户看的图层命名约定说明。"""
    groups = [
        ("墙体", LAYER_WALL_KEYWORDS),
        ("门窗", LAYER_DOOR_KEYWORDS),
        ("消防设备", LAYER_DEVICE_KEYWORDS),
        ("房间文字", LAYER_TEXT_KEYWORDS),
    ]
    text = "；".join(f"{label}：{'/'.join(kws)}" for label, kws in groups)
    codes = "、".join(f"{code}({name})" for code, (_, name) in CODE_TOKENS.items())
    return text + f"；缩写码（按整段比对）：{codes}"
