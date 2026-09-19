# 海康威视 ISAPI 对接接口文档（草案）

| 项 | 内容 |
| --- | --- |
| 文档状态 | **草案（Draft）**，待真机联调后定稿 |
| 适用范围 | 智慧消防系统 ↔ 海康威视摄像头 / NVR / 视频网关 |
| 对接方式 | ISAPI（HTTP + 摘要认证），我方作为客户端主动调用设备 |
| 实现位置 | `backend/services/video_platform/hikvision_adapter.py` |
| 平台侧入口 | `backend/routers/video.py`（`platform` 取值 `hikvision`） |
| 已验证程度 | 请求方法 / URL / 报文形状 / 错误判定已由自动化测试覆盖；**尚未与真实海康设备联调** |

> 本文档中的「我方平台接口」章节与代码逐项对应；「ISAPI 设备侧接口」章节描述的是
> 我方当前实际发出的请求，字段名取自代码中解析的节点，未在真机上确认的部分集中在第 9 节。

---

## 1. 接入前提

| 项 | 要求 |
| --- | --- |
| 网络 | 后端容器 / 主机需能直连设备 HTTP 端口（默认 80，HTTPS 常用 443） |
| 协议 | ISAPI over HTTP，默认使用 HTTP 摘要认证（Digest） |
| 账号 | 需具备**远程抓拍**与（如需云台）**云台控制**权限的账号，通常为 `admin` 或专用集成账号 |
| 端口 | 台账中 `host` + `port` 拼接，不接受带协议或路径的地址 |
| 时间 | 摘要认证的 nonce 由设备侧生成，不依赖两端时钟一致；仍建议保持 NTP 同步，便于日志比对与排障 |

---

## 2. 我方调用的 ISAPI 接口

所有请求统一：

```http
Authorization: <HTTP Digest>
User-Agent: python-httpx/<version>
```

超时：探测与云台为 `VIDEO_PROBE_TIMEOUT_SECONDS`（默认 10s），抓拍为 `VIDEO_SNAPSHOT_TIMEOUT_SECONDS`（默认 10s）。
TLS 校验由台账字段 `verify_tls` 控制（自签证书的设备建议保持关闭）。

通道号规则：台账字段 `channel_no` 为**通道序号**（从 `1` 开始），用于拼 URL 时按 ISAPI 约定补 `01`（主码流）：

| `channel_no` | 抓拍 URL 片段 |
| --- | --- |
| `1` | `/ISAPI/Streaming/channels/101/picture` |
| `2` | `/ISAPI/Streaming/channels/201/picture` |
| `16` | `/ISAPI/Streaming/channels/1601/picture` |

### 2.1 读取设备信息（探测）

```http
GET /ISAPI/System/deviceInfo
```

我方解析的节点（按本地名匹配，忽略命名空间）：

| 节点 | 用途 |
| --- | --- |
| `deviceName` | 设备名称；缺失时回落到台账中的通道名称 |
| `model` | 设备型号，回写台账 `device_model` |
| `firmwareVersion` | 固件版本，仅在探测响应中返回，不入库 |

判定规则：

- HTTP 非 200 → 通道置为 `offline`，`last_error` 记录原因
- HTTP 200 但 `statusCode` 存在且不等于 `1` → 置为 `offline`，记录 `statusString`
- 以上均通过 → `online`，并继续调用 2.2 枚举通道

### 2.2 枚举通道（附加信息）

```http
GET /ISAPI/Streaming/channels
```

遍历所有 `StreamingChannel` 节点，提取：

| 节点 | 含义 |
| --- | --- |
| `id` | 通道 ID，如 `101` |
| `channelName` | 通道名称 |
| `enabled` | 是否启用（字符串 `false` 视为停用，其余视为启用） |

> 通道枚举失败**不影响**在线判定，仅在探测响应中返回空数组。

### 2.3 抓拍

```http
GET /ISAPI/Streaming/channels/{channel_no}01/picture
```

- 期望返回：`200` + JPEG/PNG 图片二进制
- 我方会按魔数校验响应体，**非图片内容（如设备返回的 XML 报错）会被判定为失败**，不会把坏图透传给前端
- 响应成功后回写台账 `status=online`、`last_snapshot_at`

### 2.4 云台控制（连续移动）

```http
PUT /ISAPI/PTZCtrl/channels/{channel_no}/continuous
Content-Type: application/xml

<?xml version='1.0' encoding='utf-8'?>
<PTZData><pan>0</pan><tilt>50</tilt><zoom>0</zoom></PTZData>
```

轴取值 = `方向符号 × 速度幅值`，速度幅值 = `speed × 10`（`speed` 取值 1–10，故幅值 10–100）：

| 平台动作 `action` | pan | tilt | zoom |
| --- | --- | --- | --- |
| `up` | 0 | +幅值 | 0 |
| `down` | 0 | −幅值 | 0 |
| `left` | −幅值 | 0 | 0 |
| `right` | +幅值 | 0 | 0 |
| `zoom_in` | 0 | 0 | +幅值 |
| `zoom_out` | 0 | 0 | −幅值 |
| `stop` | 0 | 0 | 0 |

判定规则：

- HTTP 非 200/201 → 失败
- HTTP 200 且响应体非空时，同样检查 `statusCode`（部分固件只返回状态码、不带响应体，此时直接视为成功）

---

## 3. 我方平台接口（供前端 / 实施人员调用）

统一返回格式（异常时由全局异常处理器输出）：

```json
{ "ok": false, "code": 400, "message": "设备地址只填主机名或 IP，不要带协议或路径", "data": null, "timestamp": "2026-09-16T04:00:00Z" }
```

### 3.1 接口清单

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/video/platforms` | 登录用户 | 平台能力清单与接入表单元数据 |
| GET | `/api/video/channels` | 登录用户 | 通道列表，支持 `keyword`、`enabled_only` |
| GET | `/api/video/channels/{id}` | 登录用户 | 通道详情 |
| POST | `/api/video/channels` | `devices:manage` | 新增通道 |
| PUT | `/api/video/channels/{id}` | `devices:manage` | 修改通道 |
| DELETE | `/api/video/channels/{id}` | `devices:manage` | 删除通道 |
| POST | `/api/video/channels/{id}/probe` | `devices:manage` | 真实连接设备读取信息并回写状态 |
| POST | `/api/video/channels/{id}/snapshot-token` | 登录用户 | 签发短时抓拍令牌 |
| GET | `/api/video/channels/{id}/snapshot` | 短时令牌 | 获取抓拍图 |
| POST | `/api/video/channels/{id}/ptz` | `devices:manage` | 云台控制 |
| GET | `/api/video/channels/{id}/stream-info` | `devices:manage` | 取流地址信息 |
| POST | `/api/video/channels/{id}/analyze` | `devices:manage` | 抓拍一帧做视觉识别 |

### 3.2 新增 / 修改通道

`POST /api/video/channels`，请求体：

```json
{
  "channel_code": "HIK-1F-DOOR",
  "channel_name": "一号楼一层大厅东门",
  "location": "一号楼 1 层",
  "platform": "hikvision",
  "protocol": "http",
  "host": "10.20.0.8",
  "port": 80,
  "channel_no": "1",
  "username": "admin",
  "password": "********",
  "rtsp_url": "rtsp://admin:pass@10.20.0.8:554/Streaming/Channels/101",
  "ptz_enabled": true,
  "verify_tls": false,
  "enabled": true,
  "device_id": 12,
  "building_id": 3,
  "remark": ""
}
```

字段说明与校验：

| 字段 | 必填 | 类型 | 校验 / 说明 |
| --- | --- | --- | --- |
| `channel_code` | 是 | string | 租户内唯一；重复返回 400「通道编码「x」已存在」 |
| `channel_name` | 否 | string | 展示名 |
| `location` | 否 | string | 位置 |
| `platform` | 否 | enum | `generic` / `hikvision` / `dahua` / `mock`，默认 `generic` |
| `protocol` | 否 | enum | `http` / `https`，默认 `http` |
| `host` | 是 | string | 只允许主机名或 IP，字符集 `[A-Za-z0-9._-]`；含 `://` 或 `/` 返回 400 |
| `port` | 否 | int | 1–65535；缺省按协议取 80/443 |
| `channel_no` | 否 | string | 必须为数字，默认 `1`（见第 2 节通道号规则） |
| `username` | 否 | string | 设备账号 |
| `password` | 否 | string | **缺省表示不修改；传空串表示清除**；落库前加密，任何接口不回传 |
| `snapshot_path` | 否 | string | 仅 `generic` 平台使用；只填路径（如 `/snap.jpg`），含 `://` 返回 400 |
| `rtsp_url` | 否 | string | 必须以 `rtsp://` 或 `rtsps://` 开头，否则 400；默认脱敏返回 |
| `ptz_enabled` | 否 | bool | `hikvision` / `dahua` / `mock` 支持；`generic` 传 `true` 返回 400 |
| `verify_tls` | 否 | bool | 仅 `protocol=https` 时生效 |
| `enabled` | 否 | bool | 停用后不再探测与抓拍，抓拍接口返回 400 |
| `device_id` / `building_id` | 否 | int | 关联设备台账与楼栋，可空 |

响应（`PUT` 同样返回该结构）：

```json
{
  "id": 7,
  "channel_code": "HIK-1F-DOOR",
  "channel_name": "一号楼一层大厅东门",
  "location": "一号楼 1 层",
  "platform": "hikvision",
  "platform_label": "海康威视 ISAPI",
  "capabilities": ["probe", "snapshot", "ptz", "stream_info"],
  "protocol": "http",
  "host": "10.20.0.8",
  "port": 80,
  "channel_no": "1",
  "username": "admin",
  "has_password": true,
  "snapshot_path": "",
  "rtsp_url": "rtsp://***:***@10.20.0.8:554/Streaming/Channels/101",
  "ptz_enabled": true,
  "ptz_supported": true,
  "verify_tls": false,
  "enabled": true,
  "status": "unknown",
  "device_model": "",
  "device_id": 12,
  "building_id": 3,
  "remark": "",
  "last_probe_at": "",
  "last_snapshot_at": "",
  "last_error": "",
  "snapshot_endpoint": "/api/video/channels/7/snapshot",
  "created_at": "2026-09-16T04:00:00",
  "updated_at": "2026-09-16T04:00:00"
}
```

> `password` / `password_cipher` 永不出现在任何响应中，仅有布尔量 `has_password`。

### 3.3 探测通道

`POST /api/video/channels/{id}/probe`

```json
{
  "channel_id": 7,
  "online": true,
  "status": "online",
  "device_name": "一号楼大厅",
  "device_model": "DS-2CD3T46",
  "firmware": "V5.7.3",
  "channels": [
    { "id": "101", "name": "Camera 01", "enabled": true },
    { "id": "102", "name": "Camera 02", "enabled": false }
  ],
  "message": "ISAPI 设备信息读取成功",
  "probed_at": "2026-09-16T04:00:00"
}
```

副作用：回写 `status` / `last_probe_at` / `last_error`，并在型号非空时更新 `device_model`。

### 3.4 抓拍图获取（两段式）

浏览器 `<img>` 无法携带 `Authorization` 头，因此使用短时令牌：

1. `POST /api/video/channels/{id}/snapshot-token`（需登录）→

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 3600,
  "snapshot_url": "/api/video/channels/7/snapshot?token=eyJhbGciOiJIUzI1NiIs..."
}
```

2. `GET /api/video/channels/{id}/snapshot?token=...`（令牌鉴权）→ `200` + 图片二进制

| 查询参数 | 说明 |
| --- | --- |
| `token` | **必填**，缺失返回 422 |
| `fresh` | 传 `true` 时跳过缓存强制向设备重新抓拍 |

响应头：

| 头 | 说明 |
| --- | --- |
| `Content-Type` | `image/jpeg` / `image/png` 等，按魔数判定 |
| `Cache-Control` | `private, max-age=<VIDEO_SNAPSHOT_CACHE_SECONDS>` |
| `X-Video-Channel` | 通道编码 |

令牌约束：与**通道 ID 绑定**，跨通道使用返回 401；类型标识为 `video_snapshot`；有效期 `VIDEO_SNAPSHOT_TOKEN_SECONDS`（默认 3600s）。

### 3.5 云台控制

`POST /api/video/channels/{id}/ptz`

```json
{ "action": "right", "speed": 5 }
```

- `action` ∈ `up` / `down` / `left` / `right` / `zoom_in` / `zoom_out` / `stop`
- `speed` 取 1–10（非数字返回 400）
- 通道 `ptz_enabled=false` 或平台不支持 → 400

### 3.6 取流信息

`GET /api/video/channels/{id}/stream-info?reveal=false`

```json
{
  "channel_id": 7,
  "rtsp_url": "rtsp://***:***@10.20.0.8:554/Streaming/Channels/101",
  "masked": true,
  "playable_in_browser": false,
  "note": "浏览器不能直接播放 RTSP。实时预览需部署流媒体网关（如 ZLMediaKit）转 HLS/FLV；当前版本使用抓拍图轮询提供准实时画面，取流地址可用于录像机或第三方平台的二次接入。"
}
```

`reveal=true` 返回完整地址（含账号密码），该参数需要 `devices:manage` 权限。

### 3.7 抓拍识别

`POST /api/video/channels/{id}/analyze`

请求：`{ "create_alert": true }`（`create_alert` 默认 `true`）

响应：

```json
{
  "channel_id": 7,
  "channel_code": "HIK-1F-DOOR",
  "upload_id": 31,
  "snapshot_url": "/api/files/31",
  "hazards": ["消防通道堵塞"],
  "description": "通道内堆放纸箱",
  "risk_reasons": ["影响疏散通道畅通"],
  "risk_score": 30,
  "risk_level": "高风险",
  "confidence": "low",
  "confidence_label": "低",
  "used_vision_api": false,
  "vision_error": "",
  "alert_id": 118,
  "alert_code": "AL-20260916-3F2A91BC",
  "dedup_action": "created",
  "review_required": true,
  "review_task_id": 9,
  "review_reason": "AI 结果置信度低：云端模型未生效或调用失败",
  "ticket_id": null
}
```

工单下发规则（与巡检链路共用同一道人工复核闸门）：

```text
识别到隐患 → 生成告警（自动去重 / 重复达标自动升级）
           → 置信度低 或 高风险/严重风险：落待复核任务（source=video），人工确认后才建单
           → 置信度高且非高风险：直接生成工单（ticket_id 非空）
```

未识别到隐患或 `create_alert=false` 时，`alert_id` / `review_task_id` / `ticket_id` 均为 `null`。
待复核任务可在 `GET /api/ai-review/tasks?status=pending` 查看。

### 3.8 错误码

| HTTP | 触发场景 | 典型 `message` |
| --- | --- | --- |
| 400 | 字段校验失败 | 「设备地址只填主机名或 IP……」「抓拍路径只填路径（如 /snap.jpg）……」「取流地址必须以 rtsp:// 开头」「通道号必须是数字」「不支持的视频平台「x」」 |
| 400 | 配置缺失 | 「未配置抓拍路径（snapshot_path），无法获取画面」「该视频通道已停用」「该通道未启用云台控制，请先在台账中开启」「通用 HTTP 快照 / RTSP 适配器暂不支持云台控制」 |
| 400 | 凭证解密失败 | 「凭证密文校验失败，VIDEO_CREDENTIAL_KEY 可能已更换」 |
| 401 | 令牌无效 / 过期 / 跨通道 | 「抓拍令牌无效或已过期」「抓拍令牌与通道不匹配」 |
| 401 | 未登录 | 「未提供认证令牌」 |
| 403 | 权限不足 | 「缺少权限: devices:manage」 |
| 404 | 通道不存在或不属于当前租户 | 「视频通道不存在」 |
| 422 | 抓拍接口缺少 `token` 参数 | FastAPI 参数校验错误 |
| 502 | 设备侧问题（默认） | 「无法连接 10.20.0.8:80（ConnectError）」「设备拒绝访问，请检查账号密码或权限」「设备返回 404，接口地址或通道号可能不正确」「设备返回错误状态：Invalid Operation」「抓拍返回的不是图片内容：……」 |

---

## 4. 前端接入方式

当前版本采用**抓拍图轮询**：

```js
// 1) 取令牌（携带 JWT）
const { token } = await videoSnapshotToken(channelId)
// 2) <img> 直接引用，定期更换 _t 触发刷新
img.src = `/api/video/channels/${channelId}/snapshot?token=${token}&_t=${Date.now()}`
```

- 默认轮询间隔 5 秒（前端 `POLL_SECONDS`）
- 令牌每 30 分钟续签一次（后端有效期 1 小时）
- 后端对同一通道做 TTL 缓存（`VIDEO_SNAPSHOT_CACHE_SECONDS`，默认 3s），多个浏览器同时观看只按缓存周期回源设备一次
- 图片加载失败（`onerror`）时前端降级为占位并标记离线，不展示坏图

---

## 5. 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VIDEO_CREDENTIAL_KEY` | 空 | 摄像头凭证加密密钥；生产必须显式配置，留空回退 `JWT_SECRET_KEY` |
| `VIDEO_PROBE_TIMEOUT_SECONDS` | 10 | 探测与云台下发超时 |
| `VIDEO_SNAPSHOT_TIMEOUT_SECONDS` | 10 | 抓拍超时 |
| `VIDEO_SNAPSHOT_CACHE_SECONDS` | 3 | 抓拍图进程内缓存时长 |
| `VIDEO_SNAPSHOT_TOKEN_SECONDS` | 3600 | 抓拍令牌有效期（秒） |

---

## 6. 排障手册

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 探测返回「设备拒绝访问，请检查账号密码或权限」 | 账号密码错误 / 账号无远程抓拍权限 | 用设备 Web 或 ISAPI 测试工具验证同一账号 |
| 探测返回「无法连接 host:port（ConnectError）」 | 网络不通、端口不对、设备未开 HTTP | 从后端主机 `telnet host port` 验证 |
| 探测返回「设备返回内容不是合法 XML」 | 端口指向了非 ISAPI 服务，或中间有 Portal 认证 | 用浏览器直接访问 `http://host/ISAPI/System/deviceInfo` 确认 |
| 探测正常但抓拍失败 | `channel_no` 与设备实际通道号不符 | 用 2.2 返回的通道 `id` 反推：`101` → `channel_no=1` |
| 抓拍返回 404 | 设备不支持 `/ISAPI/Streaming/channels/{n}01/picture` | 改用 `generic` 平台并配置设备的抓拍路径 |
| 云台方向不生效 / 报 Invalid Operation | 固件对 pan/tilt/zoom 取值区间要求不同（0~100 或 −100~100） | 见第 9 节开放问题 1 |
| 云台一直动不停 | `stop` 未下发 | 前端在松开按钮或超时后需下发 `stop` |
| 抓拍图不显示但接口 200 | 返回内容非图片（如 XML 报错） | 查看 `last_error` 与后端日志，会记录返回内容片段 |

---

## 7. 安全设计说明

- 设备密码使用 `VIDEO_CREDENTIAL_KEY` 派生密钥加密落库，接口只返回 `has_password`
- 抓拍地址只接受路径、不接受完整 URL，由 `host + port + path` 拼接，避免将本系统作为访问任意地址的跳板
- 抓拍图接口不使用用户 JWT，改用与通道绑定的短时令牌，避免长期令牌出现在 URL、日志与浏览器历史中
- 取流地址默认脱敏为 `***:***@xxx`，查看完整地址需要 `devices:manage` 权限
- 台账所有查询按 `tenant_id` 隔离，跨租户访问返回 404

---

## 8. 自动化测试覆盖

`backend/tests/test_video_platform.py` 中与海康相关的用例：

| 用例 | 验证内容 |
| --- | --- |
| `test_probe_reads_device_info_and_channels` | 请求路径为 `/ISAPI/System/deviceInfo` 与 `/ISAPI/Streaming/channels`，正确解析型号、固件、通道列表与 `enabled` |
| `test_probe_reports_offline_on_auth_failure` | 401 时判定离线并给出账号密码提示 |
| `test_snapshot_requests_picture_endpoint` | 抓拍确实请求 `/ISAPI/Streaming/channels/101/picture` |
| `test_snapshot_rejects_non_image_body` | 200 + XML 报错被拦截 |
| `test_ptz_sends_put_with_direction_payload` | 方法为 `PUT`、路径为 `/ISAPI/PTZCtrl/channels/1/continuous`、报文含 `<tilt>50</tilt>` |
| `test_ptz_reports_device_error_status` | `ResponseStatus.statusCode=4` 被识别为失败 |

运行：`cd backend && python -m unittest tests.test_video_platform -v`

> 以上测试使用 `httpx.MockTransport` 断言**我方发出的报文形状**，不等价于真机验证。

---

## 9. 待真机确认的开放问题（草案定稿前需闭环）

1. **云台轴取值区间**：当前按「−100 ~ 100」下发（`up` → `tilt=+50`）。部分固件只接受 `0 ~ 100`，
   需确认目标固件取值范围；若不支持负值，需改为对每个方向分别下发对应正向指令。
2. **云台停止语义**：当前 `stop` 通过下发全 0 的 `PTZData` 实现，需确认该固件是否支持，
   以及是否需要额外的 `stop` 接口。
3. **抓拍通道 URL 规范**：`{channel_no}01` 对应主码流，子码流应为 `{channel_no}02`；
   是否需要支持按码流选择（影响带宽与画质）待确认。
4. **NVR 场景**：多通道 NVR 下 `deviceInfo` 返回的是 NVR 本体信息，通道列表中的 `id` 与
   台账 `channel_no` 的对应关系需在真机上核对。
5. **错误判定完备性**：除 `ResponseStatus` 外，是否存在其他错误返回形式（如直接返回 HTML 错误页）。
6. **HTTPS / 自签证书**：设备启用 HTTPS 后的证书校验策略，以及是否影响摘要认证。
7. **长连接与并发**：当前每次调用新建 HTTP 客户端；高频抓拍（多通道 × 短轮询）下是否需要连接复用。
8. **鉴权方式**：摘要认证是否满足所有型号；是否存在只支持 Basic 或 Web Session 的固件。
9. **录像检索与回放**：本次未实现（`/ISAPI/ContentMgmt/search` 等），需另行设计与确认。

---

## 10. 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v0.1 | 2026-09-16 | 草案初稿，依据 `hikvision_adapter.py` 当前实现整理 |
