from html import escape


def generate_device_code(prefix: str, building: str, floor: str, serial: int) -> str:
    type_map = {"灭火器": "EXT", "消防栓": "HYD", "配电箱": "ELE", "烟感探测器": "SEN", "报警按钮": "BTN"}
    p = type_map.get(prefix, "DEV")
    return f"{p}-0101-0001-{floor.replace('F','').zfill(2)}-{serial:06d}"


def svg_code_card(device_code: str, title: str = "消防设备码") -> str:
    # 零依赖演示版标签，不是真实二维码；比赛演示可用于表达一物一码概念。
    code = escape(device_code)
    title = escape(title)
    blocks = []
    seed = sum(ord(c) for c in device_code)
    for y in range(10):
        row = []
        for x in range(10):
            bit = ((seed + x * 17 + y * 31 + x * y) % 5) in {0, 2}
            if x in {0,1,8,9} and y in {0,1,8,9}: bit = True
            if bit:
                row.append(f'<rect x="{20+x*12}" y="{50+y*12}" width="10" height="10" fill="#111827"/>')
        blocks.extend(row)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="220" height="230" viewBox="0 0 220 230">
<rect width="220" height="230" rx="16" fill="#ffffff" stroke="#d1d5db"/>
<text x="110" y="28" text-anchor="middle" font-size="16" font-family="Arial" font-weight="700" fill="#111827">{title}</text>
{''.join(blocks)}
<text x="110" y="196" text-anchor="middle" font-size="12" font-family="Arial" fill="#374151">{code}</text>
<text x="110" y="215" text-anchor="middle" font-size="10" font-family="Arial" fill="#6b7280">扫码巡检 · 一物一码 · 智慧消防</text>
</svg>"""
