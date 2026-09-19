# 智慧消防管理系统

当前版本 V1.0.0。

面向智慧消防场景的多模态大模型 Agent 系统，支持消防隐患识别、风险评分、知识库问答、巡检报告生成、历史记录查询、工单整改和应急辅助决策。

## 技术栈

- 后端：Python 3.14、FastAPI、SQLAlchemy、Pydantic、SQLite
- 前端：Vue 3、Vite
- 移动端：Flutter
- 大模型：兼容智谱 AI、通义千问、OpenAI 等接口
- 视觉模型：可选，未配置时自动降级为文本规则分析

## 主要功能

- 智能巡检 Agent：文本 + 图片输入，结构化隐患识别、风险评分、整改建议、知识库引用、Agent 调用步骤
- 风险评估：隐患类型 + 风险类别 + 严重程度 + 分值 + 处置措施，支持多隐患叠加修正
- 消防 RAG 问答：知识库检索 + 文本大模型生成，返回引用来源与匹配关键词
- 巡检报告：文本 / Markdown / HTML 导出，支持打印与二维码验真
- 整改工单：高风险/严重风险自动生成工单，支持状态推进
- 硬件事件中心：硬件接入预留接口与事件展示
- 消防学习：题库、知识图谱、错题本、学习画像、答题反馈
- Dashboard：风险等级统计、高频隐患 TOP、设备数量、巡检记录
- 系统健康检查：API Key、文本模型、视觉模型、环境变量状态
- 评估与可解释：Agent Trace、工具调用记录、风险解释、识别证据链

## 目录结构

```text
fire_ai_agent_v1/
├── backend/
│   ├── data/
│   │   ├── fire_knowledge/      # 消防知识库 Markdown 文档
│   │   └── learning/            # 学习题库与课程数据
│   ├── routers/                 # 路由模块（预留，逐步拆分 main.py）
│   ├── services/                # 业务服务层
│   ├── static/                  # 前端构建产物
│   ├── uploads/                 # 上传文件
│   ├── main.py                  # FastAPI 入口
│   ├── database.py              # 数据库连接
│   ├── schemas.py               # Pydantic 模型
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/               # 页面组件
│   │   ├── router/              # 路由配置
│   │   ├── utils/               # 工具函数
│   │   ├── api.js               # 接口封装
│   │   ├── auth.js              # 鉴权
│   │   └── main.js              # 入口
│   └── vite.config.js
├── mobile_app/                  # Flutter 移动端
├── docs/                        # 文档
├── start_all.bat                # 一键启动
├── start_fast.bat               # 快速启动
├── stop_all.bat                 # 停止脚本
└── README.md
```

## 后端启动

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 前端启动

```powershell
cd frontend
yarn install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

## 一键启动脚本

| 脚本 | 作用 |
|---|---|
| `start_all.bat` | 首次运行：创建 Python 3.14 虚拟环境、安装后端与前端依赖、启动并打开浏览器 |
| `start_fast.bat` | 依赖已安装时的快速启动 |
| `stop_all.bat` | 停止 8000 和 5173 端口对应的后端/前端进程 |
| `start_mobile.bat` | 单独启动 Flutter 移动端 |
| `start_all.ps1` | PowerShell 版本一键启动脚本 |

注意事项：

1. 启动脚本必须放在项目根目录运行。
2. 请确保已安装 Python 3.14、Node.js、npm。
3. 启动后会弹出两个命令行窗口（后端 FastAPI 与前端 Vue），不要关闭。
4. 移动端 Flutter 需要模拟器或真机环境，未并入主启动脚本。

## 移动端协同

仓库里有两条移动端路径，**以 Web 移动端页面为准**：

### 1. Web 移动端页面（`/mobile-inspection`，本页可用、可测）

现场人员用的一页，移动优先布局（手机上铺满、桌面上居中成 480px 的一列），底部四个页签：

| 页签 | 内容 | 数据来源 |
| --- | --- | --- |
| 首页 | 待处理告警 / 可领取工单 / 我的在办 / 今日巡检 四个统计，以及可领取工单列表（一键领取）、待处理告警列表（标记已处置） | `GET /api/mobile/home` |
| 待办 | 我名下的工单 + 待处理告警合成一个列表 | `GET /api/mobile/tasks` |
| 上报 | 选建筑/设备 + 现场位置 + 描述 + 拍照，提交后当场给出风险分、等级、识别到的隐患与整改建议 | `POST /api/mobile/report` |
| 我的 | 当前登录人、角色、本租户设备数、在办工单数、退出登录 | `GET /api/mobile/home` |

### 2. 移动端协同接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/mobile/home` | 首页聚合（按租户 + 当前用户真实统计，含最近待办列表） |
| GET | `/api/mobile/tasks` | 我的待办：工单 + 告警合成一个列表 |
| POST | `/api/mobile/workorders/{order_id}/claim` | 领取工单：指派给自己并进入「处理中」，需 `workorders:update` |
| POST | `/api/mobile/report` | 现场上报（图片 + 描述），复用巡检 Agent 并落巡检记录，需 `inspection:run` |

- 告警处置与工单状态流转**沿用既有接口**（`POST /api/alerts/{id}/handle`、`POST /api/workorders/{id}/status`），移动端不另造一套
- 领取工单有明确语义：只有「待受理」且无人认领的工单能被领取；被别人领走或已闭环会返回原因，不会静默改指派
- 上报至少要给建筑/设备/位置之一；响应只回风险分、等级、隐患、建议与图片，不带完整的 Agent 轨迹与报告正文（手机没必要收几百 KB JSON）

### 3. Flutter App（`mobile_app/`）

一线人员用的原生 App，与 Web 移动页共用同一批 `/api/mobile/*` 接口。

```powershell
cd mobile_app
flutter pub get
# Android 模拟器用 10.0.2.2 访问本机后端；真机换成电脑局域网 IP
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# 静态分析与测试（本机已验证）
.\flutter_analyze.bat   # flutter analyze 的包装（本仓库路径含非 ASCII 字符，见下）；也可直接用 dart analyze
flutter test            # 25 passed（22 离线 + 3 真实后端联调）

# 打 release APK（需 JDK 17 + Android SDK；脚本自动设好环境变量）
.\build_apk.bat http://192.168.1.10:8000
# 产物 build/app/outputs/flutter-apk/：通用包 66.6MB；加 --split-per-abi 后单 ABI 约 20~27MB
```

已实现（数据全部来自真实接口，无写死内容）：

| 模块 | 内容 |
| --- | --- |
| 登录与令牌 | 登录页 + 自动注入 `Authorization: Bearer` + 401 自动用刷新令牌换新令牌并重放请求 + 令牌临近过期提前续期（剩余不足 60 分钟）+ 失效回登录页 |
| 首页 | 统计与概览来自 `/api/mobile/home`，待办列表来自 `/api/mobile/tasks`（最多 50 条）；快捷操作全部真实跳转（拍照巡检/新建工单/设备台账/消防问答） |
| 巡检 | 选设备 + 填位置 + 拍照 + 定位（定位失败不阻断上报）→ `/api/mobile/report`（复用巡检 Agent）→ 风险分/隐患/建议；**同时写入巡检档案**，Web「巡检档案」页可立即看到 |
| 工单 | 服务端状态筛选 + 分页 + 真实新建（`POST /api/workorders`）+ 领取（`/api/mobile/workorders/{id}/claim`）+ 状态流转（待受理/处理中/待复查/已完成/已关闭），6 个状态 Tab 齐备 |
| 告警 | `/api/alert/list` 真实列表 + 级别筛选 + 详情 + 「开始处置」/「填写处置结果结单」；WebSocket 推送到达时列表自动刷新 |
| 设备台账 | `/api/devices` 搜索 + 分页 + 设备详情（含最近告警） |
| 巡检记录 | `/api/records` 列表 + 详情（含 AI 报告正文，列表接口不返回 report） |
| 扫码巡检 | 扫设备二维码 → 按编号查设备 → 跳设备详情（`mobile_scanner`） |
| 消息通知 | `/api/notifications` 列表 + 全部已读 + 铃铛未读角标；`/ws/notifications` 实时推送（首帧发 token 鉴权，断线指数退避重连） |
| 消防问答 | `/api/qa/fire`（后端要求 Form 参数）对话式问答 |
| 我的 | 用户信息 `/api/auth/me`、统计 `/api/mobile/home`、修改密码、真实退出登录（后端拉黑令牌 + 清本地令牌） |

包名与打包：`com.fire.inspection.mobile`（`minSdk 24` / `targetSdk 36` / `compileSdk 36`），
release 用 `android/app/fire-release.jks` 签名（口令在 `android/key.properties`，两者均不入库，**请另行备份 keystore**）。
Android 已在 main manifest 声明 `INTERNET`/`ACCESS_NETWORK_STATE`/`CAMERA`/`ACCESS_FINE_LOCATION`/`ACCESS_COARSE_LOCATION`
（此前只在 debug manifest 里声明 `INTERNET`，**release 包会无法联网**）；
另通过 `res/xml/network_security_config.xml` 放开明文 HTTP（Android 9+ 默认禁止，不放开会连不上内网后端；
后端上 HTTPS 后把 `cleartextTrafficPermitted` 改成 `false` 即可收紧）。
图标为自绘消防主题（含 Android 8+ 自适应图标与启动闪屏），接口详见 [mobile_app/README.md](mobile_app/README.md)。

已知限制（如实记录）：

- 令牌存 `shared_preferences`，未接系统安全存储；对令牌敏感的场景建议换 `flutter_secure_storage`
- 后端 `/api/auth/refresh` 自身要求 access token 仍有效，因此只能「提前续期」，一旦过期就必须重新登录（后端契约决定）
- **未做真机/模拟器联调**：APK 已能构建并通过包信息与签名校验，但相机、扫码、定位、WebSocket 仍待真机验证
- Gradle 8.14 / AGP 8.11.1 / Kotlin 2.2.20 低于 Flutter 建议值（≥9.1 / ≥9.0.1 / ≥2.3.20），当前只是弃用预警
- `flutter analyze` 在本目录（路径含「副本」等非 ASCII 字符）下会崩：flutter 工具传给分析器的 LSP 报文长度对不上
  （`FormatException: Unexpected end of input ... LspByteStreamServerChannel._readMessage`）。仓库内提供
  `mobile_app/flutter_analyze.bat`（`mklink /J` 建 ASCII 目录联接后分析，源码不复制）绕过；也可直接用 `dart analyze`。
  `flutter test` / `flutter build web` 不受影响。治本方案是把仓库目录改成纯 ASCII 名

## Python 3.14 依赖说明

requirements.txt 采用适配 Python 3.14 的依赖范围：

```text
fastapi>=0.119.0
uvicorn>=0.35.0
pydantic>=2.12.0,<3.0.0
SQLAlchemy>=2.0.40
alembic>=1.13.0
psycopg[binary]>=3.2.0,<4.0.0
python-multipart>=0.0.20
python-dotenv>=1.1.0
httpx>=0.28.0
aiofiles>=24.1.0
qrcode[pil]>=7.4.2
PyJWT>=2.9.0,<3.0.0
paho-mqtt>=2.1.0
scikit-learn>=1.9.0
psutil>=7.0.0
ezdxf>=1.4.0
```

如果安装时出现 `pydantic-core` 编译问题，先升级 pip/setuptools/wheel，并避免固定老版本 pydantic-core。

`scikit-learn` 是风险预测模型（训练 + 推理）的依赖，会带上 numpy/scipy。1.9 起提供 Python 3.14 的 `cp314` wheel，
无需本地编译；生产镜像同样基于 `python:3.14-slim`，与本地开发、CI 用的是同一个 Python 版本。模型产物默认落在
`backend/artifacts/risk_model.json`（训练生成，已加进 .gitignore）；文件不存在时预测接口如实回报「尚未训练」，
不会给出编造分数。

`psutil` 是系统监控页（`/system-monitor`）采集真实主机指标的依赖（CPU / 内存 / 磁盘 / 网络 / 进程），
替代原先页面上的随机数模拟与写死常量；各平台都有预编译 wheel，不需要本地编译。

`ezdxf` 是 CAD 图纸解析的依赖（DXF 实体提取）。它是纯 Python 包，各平台都无需编译；
注意它**只读 DXF**，DWG 是 AutoCAD 的二进制格式，必须先转成 DXF（见「CAD 图纸导入」一节）。

## 智能巡检调用逻辑

- 文本大模型：分析“现场描述”
- 视觉大模型：分析“现场图片”
- 只配置文本模型时，上传图片不会自动识别图片内容
- 要识别图片，必须启用包含 `vision_model` 的视觉模型配置

系统设置里的“接口测试成功”只代表该模型配置可用；智能巡检是否使用大模型，要看“文本大模型 API / 视觉大模型 API”的状态。

## 风险预测模型（scikit-learn）

改造前的「风险预测」是纯规则：查表求和（`services/risk_engine.py`）+ 加权线性缩放（`services/enhanced_risk_engine.py`），
没有训练、没有模型文件、没有特征工程；同一概念还存在三套互不一致的阈值（85/60/25、85/60/35、85/65/35）。
现在 `services/risk_model_service.py` 提供一个**真正用历史数据训练**的模型，回答一个能被验证的问题：

> 某栋建筑在**未来 7 天**内，会不会出现严重告警（`severity∈{critical, high}`）或告警升级（`escalated`）？

### 1. 样本、特征与标签

| 项目 | 做法 |
| --- | --- |
| 样本 | 每栋建筑 × 每个观测点（每周一个，默认取最近 8 周）= 建筑数 × 8 |
| 特征窗口 | 观测点前 7 天 |
| 标签窗口 | 观测点后 7 天 |
| 特征（12 个） | 近 7 天告警数 / 严重告警数 / 告警最大重复次数、未闭环工单数、逾期工单数、设备离线率、设备平均已投用年数、近 7 天巡检次数与巡检风险分均值、近 7 天最高温度、最低电量、距上次维保天数 |
| 标签 | 标签窗口内出现 `critical`/`high` 告警，或告警被升级（`escalated_at` 落在窗口内） |
| 训练 | `StandardScaler` + `LogisticRegression(L2, class_weight=balanced)`，**按时间切分**（前 70% 观测点训练、后 30% 回测），不能拿未来预测过去 |
| 落盘 | 标准化参数与系数导出为 `backend/artifacts/risk_model.json`（JSON，不是 pickle）：可审计，也不存在「加载模型 = 反序列化执行任意对象」的风险 |

### 2. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/risk/model` | 模型元信息：是否已训练、训练时间、特征清单、回测指标、标签定义、已知局限 |
| POST | `/api/risk/model/train` | 训练并落盘，返回回测指标；需要 `risk:model` 权限。样本不足或正负样本失衡时返回 400 并说明原因 |
| GET | `/api/risk/predictions` | 本租户全部建筑的预测结果（概率、预测等级、Top 因子贡献、特征实测值），按概率倒序 |
| GET | `/api/risk/prediction/{building_id}` | 单栋建筑的预测详情 |

### 3. 几条刻意的设计

- **没训练就不给分**：模型文件不存在（或特征定义与代码不一致）时，接口返回 `trained: false` 与明确说明，
  前端 `/building-risk` 也只显示「尚未训练」，不显示任何预测分数；不会退回到规则分冒充预测值
- **不「凑」模型**：样本 < 40 或正负两侧各 < 4 条时直接拒绝训练，并在返回里带上具体数量
- **阈值不自造**：温度、电量这类指标直接取原始极值交给模型学，不在代码里另立一套阈值
- **概率分档 ≠ 规则分数线**：`risk_band()` 的 70%/45%/20% 是**模型概率**口径，与规则引擎的 85/60/35 不是一回事，页面上两者并排展示（「预测概率」与「规则分（现行口径）」）
- **已知局限写进接口与页面**：设备/工单状态没有历史快照（历史样本用当前快照，偏保守）；标签是「严重告警/告警升级」这类可观测结果，
  **不等于真实火灾**（系统内没有事故结果表）；模型只在本租户数据上训练，样本量小时指标波动大

### 4. 顺带清掉的随机数（`services/intelligence_service.py`）

这个文件里凡是被当成「AI 分析结论」输出的数字，改造前不少是 `random` 出来的。现在全部改为
确定性结果或真实库统计，**同一个输入不再会给出两个不同答案**：

| 位置 | 改造前 | 现在 |
| --- | --- | --- |
| 告警风险分 | 严重度映射 + `random.randint(-5, 5)` | 复用告警接入侧的严重度映射（`_estimate_risk_score`），全系统一套口径 |
| 告警/方案/诊断的「置信度」 | `random.random()` | 按输入字段完整度计算（并注明这不是模型概率） |
| 巡检隐患等级 / 类别 / 建议 / 总分 | `random.choice` + `len(hazards) * 15 + random` | 走规则表（`services/risk_engine`），与巡检 Agent、批量巡检同源；置信度 = 规则命中率 |
| 「类似告警」 | 随机编 id / 楼层 / 原因 / 处置结果 | 查本租户同类型真实历史告警（`alert_records`），没有就空列表 + 占位文案 |
| 每日简报的全部统计 | 告警数、各级数量、处置数、巡检数、隐患数、7 日趋势全是 `random.randint`；重点区域写死「1号办公楼 / 地下车库 / 消防水泵房」 | 按「指定日期（默认昨天，本地时区）」查真实表；7 日趋势逐日统计；重点区域由「近 7 天告警最多的区域 + 该日之前已逾期的工单」推导，无数据则空列表 |
| 自然语言问答 | 「今日共发生{random}起告警」「设备在线率{random}%」「系统共管理 6 栋建筑」 | 每个分支都按本租户真实数据统计（告警/设备在线率/设备类型分布/隐患/建筑数），查不到就如实说没有；置信度改为数据覆盖度 |
| 知识推荐（`/recommend-knowledge`） | 内置 7 条写死的假条目（`KB001 烟感探测器工作原理与维护`…），接口调用时又没传候选列表，所以问什么都是这一批 | 候选条目取自运行时库 `rag_entries`（真实知识库），按标题与关键词打分排序；知识库读不到条目就返回空列表 |
| 经验提取的「最佳实践」 | 与传入案例无关的固定文案；`result="已处置"` 时还会无条件夸一句「响应及时」 | 由 `alert_type` / `result` / `process_description` 里实际出现的词命中规则表得到，每条带 `basis` 写明是哪个词触发的；一条都没命中就返回空列表 |

同时修掉了一个真实缺陷：`local_day_start_utc()` 用 `datetime.now() - datetime.utcnow()` 算时区偏移，
两次取时相减会带几微秒抖动，使「本地零点」变成一个带微秒的随机边界 —— 恰好落在零点（或跨天那一刻）
产生的记录会被算进前一天。现在偏移取整到秒，并新增 `local_day_bounds_utc(date)` 供「按某一天统计」使用。

> 设备故障诊断里「可能故障原因」的百分比：改造前是写死的模板值，却按「本次诊断概率」展示，
> 判断依据还会断言「设备已使用超过5年」「安装环境通风不良」这类我们并不知道的事实。
> 现在这个比例明确叫**参考权重**，来源分两种且在界面上标出：拿得到设备台账（`device_id` 属于本租户）时，
> 按投用年限 / 距上次维保天数 / 是否超期未维保 / 最近上报时间调整并归一化，依据里给出具体数字（标 `按设备数据`）；
> 拿不到台账时退回知识库先验权重，依据写成「知识库经验：…」（标 `知识库经验`）。弹窗同时列出用到的台账数据。
>
> 顺带修掉一个一直存在的缺陷：该弹窗**从来没有真正显示出内容** —— 前端把 `device_id` 当数字传，
> 而接口的 `device_id` 是字符串字段，Pydantic 不做 int→str 隐式转换，请求直接被 422 拒掉，
> 页面只弹出一个空壳（只取到 `res.data` 信封、置信度显示 NaN 也是同一处的问题）。

> 页面上还暴露并修掉了一个老 bug：`/daily-brief` 只取到了接口信封 `res.data`（真实数据在 `res.data.data`），
> 于是 `date`/`summary` 全是 undefined、统计项被页面的「补默认值」逻辑补成 0 —— 页面看着正常，其实一直显示全 0。

## 知识图谱

仓库里有两张用途不同的图谱，**不混在一张图里**：

| 图谱 | 数据来源 | 接口 |
| --- | --- | --- |
| 业务实体图谱 | 业务表现算（建筑/楼层/设备/告警/工单/巡检）+ 规则表的隐患类型 + 运行时库的知识条目 | `/api/kg/*` |
| 学习知识图谱 | 题库与课程 JSON（`backend/data/learning/`） | `GET /api/learning/knowledge-graph` |

### 1. 业务实体图谱的关系是怎么来的

| 实体 | 来源 | 关系（边） |
| --- | --- | --- |
| 建筑 | `buildings` | `contains` → 楼层 |
| 楼层 | `floors` | `locates` → 设备 |
| 设备 | `devices` | `triggers` → 告警、`creates` → 工单、`inspected_by` → 巡检记录 |
| 告警 | `alert_records` | `creates` → 工单（`workorder_id`） |
| 工单 | `fault_tickets` | 挂在建筑/设备下 |
| 巡检记录 | `inspection_records` | `found` → 隐患类型（解析 `hazards` JSON） |
| 隐患类型 | `services/risk_engine.HAZARD_PROFILES` + 巡检自由文本 | `documented_in` → 知识条目 |
| 知识条目 | 运行时库 `rag_entries` | 全局知识库，节点标 `isGlobal` |

**为什么不建节点表/边表**：实体就是业务表里的行，关系就是外键与既有字段。另建一套图存储等于把同一份事实存两遍，
业务写入还得同步，迟早不一致。这里改成查询时现算，图谱永远等于库里的真实状态。
代价是每次请求都要查库，因此对体量大的表做了上限（见下）。

### 2. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/kg/overview` | 各类型节点数、关系数、数据来源说明（含是否被上限截断） |
| GET | `/api/kg/graph` | 完整图谱，`alerts` / `workorders` / `inspections` 可调上限（默认各 200，最大 1000） |
| GET | `/api/kg/subgraph` | 以某实体为中心取 1~3 度邻居（前端点击/搜索下钻用） |
| GET | `/api/kg/search` | 按名称/编号模糊搜索实体 |

业务实体一律按 `tenant_id` 过滤；只有知识条目是全局的（`rag_entries` 不带租户），节点上有 `isGlobal` 标记。

### 3. 页面

- `/knowledge-graph`（知识库 → 知识图谱）：ECharts 力导向图。整图默认只取**最近 40 条**告警/工单/巡检，
  避免一上来渲染上千节点；支持按实体搜索下钻、1~3 度邻居、点击节点看属性与关联关系。
  节点上限被触及时页面会明确提示「已截断，可用搜索 + 下钻查看更多」
- `/learning` 的「知识图谱/RAG」页签：改造前只显示了 `node_count` / `edge_count` / `question_count` 三个数字，
  接口返回的 `nodes` / `edges` **从未画出来**；现在真的渲染力导向图（全部模块/知识点/课程节点 + 前 20 个题目节点），
  并给出「打开完整图谱」入口

> 踩过的坑：学习图谱的节点**存在重名**（同一知识点挂在多个模块下、等级名在不同方向下重复），
> 而 ECharts 的 graph 要求节点 `name` 全局唯一，重名会直接抛 `Graph nodes have duplicate name or id`，
> 结果是「容器有尺寸、里面却没有 canvas」——图静默不渲染。现在按出现顺序给重名节点加后缀，
> 并用数组下标作为稳定键（不依赖接口 id 是否唯一）。
> 另外该页签加了 `lazy`：图表要等页签真正显示再挂载，否则 ECharts 会按 0 尺寸初始化。

### 4. 已知限制

- 巡检记录若没有 `device_id`，就无法归属到设备/建筑，会变成孤点；`overview` 里的
  `unlinked_inspections` 如实给出这类记录的条数
- 隐患类型没有独立表：能对上规则表的用规则表类别，对不上的是巡检里的自由文本（节点上 `inRuleTable=false`）
- 知识条目按「隐患名出现在条目标题或关键词里」连边，属字符串匹配，不是语义匹配；每个隐患最多连 3 条
- 图谱是**查询时现算**、没有快照，因此历史时刻的图无法回放

## 主要接口

```text
GET  /api/system/check                 # 系统自检
GET  /api/system/llm-status            # 大模型调用状态
POST /api/demo/seed                    # 生成演示数据
POST /api/inspection/analyze           # 智能巡检分析
GET  /api/rag/overview                 # RAG 知识库概览
POST /api/qa/ask                       # 消防问答
GET  /api/inspection-archives          # 巡检档案
POST /api/workorders/generate          # 生成整改工单（写入运行库 work_orders）
GET  /api/workorders/rectification     # 整改工单列表（运行库，支持 status 过滤）
GET  /api/workorders/rectification/dashboard   # 整改工单看板（待派单/整改中/待复查/已闭环 + 闭环率）
GET  /api/workorders/rectification/{id}        # 整改工单详情（含证据链与流转时间线）
POST /api/workorders/rectification/{id}/status # 推进整改工单状态（取值须在整改工单状态机内）
POST /api/reports/inspection           # 生成巡检报告
GET  /api/hardware/overview            # 硬件接口概览
GET  /api/learning/overview            # 学习模块概览
POST /api/device-ingest/telemetry      # 设备遥测上报（设备签名认证）
GET  /api/device-ingest/protocol       # 设备接入协议说明
GET  /api/telemetry/latest             # 按设备类型取某指标的最新值 + 阈值（电气/水系统页面用）
GET  /api/training/stats               # 培训概览（课程数、已培训人数、考试场次、通过率）
GET  /api/training/plans               # 培训计划列表（读写见「消防培训」一节）
GET  /api/training/records/export      # 培训档案导出 CSV
```

完整接口列表见 `http://127.0.0.1:8000/docs`。

## 设备接入协议与设备身份认证

设备通过 **设备密钥 + HMAC-SHA256 签名** 接入，不依赖用户 JWT，支持 HTTP 直连与 MQTT 两条通道。
两条通道共用同一签名公式，完整机器可读协议见 `GET /api/device-ingest/protocol`。

### 1. 凭证签发

```text
POST   /api/devices/{device_id}/credentials    # 签发/轮换密钥（devices:manage），明文仅返回一次
GET    /api/devices/{device_id}/credentials    # 查看状态（密钥脱敏）
DELETE /api/devices/{device_id}/credentials    # 吊销密钥并关闭接入
POST   /api/devices/{device_id}/ingest-toggle  # 启用/禁用接入（不影响已有凭证）
```

### 2. 签名规则

```text
base      = "{device_code}\n{timestamp}\n{nonce}\n{sha256(payload_bytes)}"
signature = HMAC_SHA256(device_secret, base)        # 十六进制小写
```

- `payload_bytes`：HTTP 为**请求体原始字节**；MQTT 为 `data` 字段的规范 JSON
  （`json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`）
- `timestamp`：Unix 秒级时间戳，服务端允许偏移 ±300 秒（`DEVICE_SIGN_MAX_SKEW_SECONDS`）
- `nonce`：每次请求必须唯一，保留期内重复即判定为重放（`DEVICE_NONCE_RETENTION_MINUTES`，默认 15 分钟）

### 3. HTTP 通道

```text
POST /api/device-ingest/telemetry   # 遥测上报
POST /api/device-ingest/event       # 事件上报
POST /api/device-ingest/heartbeat   # 心跳
```

请求头：`X-Device-Code`、`X-Device-Timestamp`、`X-Device-Nonce`、`X-Device-Signature`；请求体为业务数据 JSON。

```json
{"smoke": 1.6, "temperature": 30, "battery_level": 90}
```

### 4. MQTT 通道

```text
主题：{MQTT_TOPIC_PREFIX}/{tenant_id}/{device_code}/{kind}
kind：telemetry | event | heartbeat
前缀：默认 fire，由 MQTT_TOPIC_PREFIX 配置

消息体（JSON 信封）：
{"timestamp": 1710000000, "nonce": "...", "signature": "...", "data": {...}}
```

启用方式：`MQTT_ENABLED=true`，并配置 `MQTT_BROKER_HOST/PORT`、`MQTT_USERNAME/PASSWORD`、`MQTT_USE_TLS`。
未安装 `paho-mqtt` 或未启用时后端不订阅，不影响其他功能；运行状态见 `GET /api/device-ingest/stats`。

### 5. 指标与事件

| 指标 key | 单位 | 正常范围 | 别名 |
|---|---|---|---|
| smoke | mg/m³ | 0 ~ 0.3 | smoke |
| temperature | °C | 0 ~ 45 | temperature / temp |
| current | A | 0 ~ 20 | current |
| voltage | V | 200 ~ 240 | voltage |
| pressure | MPa | 0.3 ~ 0.6 | pressure |
| remaining_current | mA | 0 ~ 300 | remaining_current / leakage |
| battery_level | % | 30 ~ 100 | battery / battery_level |

事件类型：`fire`、`smoke`、`temperature`、`fault`、`offline`、`manual`。

> 以上 7 个指标都会写入 `device_telemetry` 时序表（并各自参与阈值判定）。
> 其中 `current` / `voltage` / `pressure` / `remaining_current` 四列是后补齐的，
> 此前硬件上报了但表里没有对应列，只进告警上下文——详见「遥测扩展：电气与水系统」。

### 6. 接入后的处理链路

```text
设备上报 → 签名/时间戳/nonce 校验 → 写入遥测表 → 阈值判定
        → 生成告警（自动去重、重复次数达标自动升级）
        → 自动生成整改工单 → 整改 → 复查 → 复查通过自动关闭告警
```

`POST /api/device-ingest/simulate` 可在跳过签名的前提下，以指定设备身份模拟一次上报，便于联调与验收。

> 说明：`/api/hardware/sensor-report`、`/api/hardware/event-report`、`/api/hardware/heartbeat` 为早期预留的展示型接口，不落库；真实设备接入请使用上文的 `/api/device-ingest/*` 或 MQTT 通道。

## 视频平台接入

> 海康 ISAPI 的对接规格、报文样例、错误码与排障手册见 [`docs/hikvision_isapi_integration.md`](docs/hikvision_isapi_integration.md)（草案）。

### 1. 支持的平台

适配器统一放在 `backend/services/video_platform/`，换厂商只需新增一个适配器文件并在 `registry.py` 注册。

| platform | 说明 | 能力 |
| --- | --- | --- |
| `generic` | 通用 HTTP 抓拍接口（有的设备叫 snapshot/snap 接口） | 探测、抓拍 |
| `hikvision` | 海康威视 ISAPI（摘要认证） | 探测、通道枚举、抓拍、云台 |
| `dahua` | 大华 HTTP CGI（摘要认证） | 探测、抓拍、云台 |
| `mock` | 本地模拟设备，不发起网络请求，返回合成抓拍图 | 探测、抓拍、云台 |

云台方向取值是按通用固件实现的；部分海康固件对 `pan/tilt/zoom` 的取值范围要求不同，
现场若方向不生效，需按设备手册调整 `hikvision_adapter.py` 中的取值。

### 2. 通道台账

摄像头 / NVR 通道统一记在 `video_channels` 表，关键点：

- **凭证加密**：登录密码用 `VIDEO_CREDENTIAL_KEY` 派生的密钥加密后落库，任何接口都不回传明文，
  只返回 `has_password`。更换密钥后旧密文无法解密，需重新录入。
  生产环境必须显式配置该变量（留空会回退 `JWT_SECRET_KEY`，两者都没有则拒绝保存凭证）；
  开发环境若都没有，会自动生成 `backend/.video_credential_key` 以便本地重启后仍可解密。
- **抓拍地址只填路径**：`snapshot_path` 只接受 `/snap.jpg` 这类路径，由 `host + port + path` 拼接，
  不接受完整 URL，避免把本系统当作访问任意地址的跳板。
- **取流地址**：`rtsp_url` 仅做登记与二次接入（录像机 / 第三方平台），接口默认脱敏为 `***:***@`。

### 3. 接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/video/platforms` | 登录用户 | 平台能力清单与接入表单所需字段 |
| `GET /api/video/channels` | 登录用户 | 通道列表（按租户隔离，密码脱敏） |
| `POST /api/video/channels` | `devices:manage` | 新增通道 |
| `PUT /api/video/channels/{id}` | `devices:manage` | 修改通道（`password` 缺省表示不改，传空串表示清除） |
| `DELETE /api/video/channels/{id}` | `devices:manage` | 删除通道 |
| `POST /api/video/channels/{id}/probe` | `devices:manage` | 真实连接设备读取信息，回写在线状态 |
| `POST /api/video/channels/{id}/snapshot-token` | 登录用户 | 签发短时抓拍令牌（默认 1 小时） |
| `GET /api/video/channels/{id}/snapshot?token=` | 短时令牌 | 返回抓拍图，进程内 TTL 缓存 |
| `POST /api/video/channels/{id}/ptz` | `devices:manage` | 云台控制（up/down/left/right/zoom_in/zoom_out/stop） |
| `GET /api/video/channels/{id}/stream-info` | `devices:manage` | 取流信息（`reveal=true` 才返回完整地址） |
| `POST /api/video/channels/{id}/analyze` | `devices:manage` | 抓拍一帧做视觉识别，识别到隐患则生成告警 |
| `POST /api/video/channels/{id}/recordings/search` | 登录用户 | 按时间段检索录像片段；平台不支持时返回 `supported=false` |

### 4. 画面获取方式与限制

浏览器**不能直接播放 RTSP**。当前版本采用**抓拍图轮询**：前端每 5 秒刷新一次受控抓拍地址
（`<img>` 无法携带请求头，因此走短时令牌）。后端对同一通道做了短时缓存，多个浏览器同时观看
也只会按缓存周期回源设备一次。

如需真正的实时预览，需要部署流媒体网关（如 ZLMediaKit）把 RTSP 转成 HLS/FLV，并引入前端
播放器依赖；这一步尚未实施，接口中的 `playable_in_browser` 会如实返回 `false`。

### 5. 抓拍识别与告警闭环

`POST /api/video/channels/{id}/analyze` 的链路：

```text
抓拍一帧 → 归档到 uploads（video_snapshot）→ 视觉模型识别隐患 → 风险评分
        → 生成告警（自动去重、重复达标自动升级）
        → 是否自动开工单由「人工复核闸门」判定：
            置信度低 / 高风险 → 落一条待复核任务（source=video），人工确认后才建单
            置信度高且非高风险 → 直接生成工单
```

抓拍原图可在 `GET /api/files/{upload_id}` 受控下载，复核任务在 `GET /api/ai-review/tasks` 查看。

### 6. 录像回放与告警联动

页面的「录像回放」不再是演示数据：检索按平台真实能力实现（`services/video_platform/*`）。

| 平台 | 录像检索 |
| --- | --- |
| 海康威视 ISAPI | 已实现，走 `POST /ISAPI/ContentMgmt/search`，片段起止时间与取流地址直接来自设备 |
| 通用 HTTP / 大华 CGI / 本地模拟 | 未实现，返回 `supported=false` 并说明原因 |

区分「没有录像」和「查不了」是刻意的：设备回 `NO MATCH` 时返回空列表并提示「该时间段设备里没有录像」，
平台无此能力时返回 `supported=false` 并提示「未实现录像检索」——两者在界面上的表现不同，
不会让人把「查不了」误读成「没有录像」。

取流地址通常是 RTSP，浏览器播放不了（接口固定返回 `playable_in_browser=false`），
页面提供的是「复制取流地址」：交给支持 RTSP 的播放器或流媒体网关使用。

「告警联动」页签读的是本租户真实告警（`GET /api/alert/list`）。告警记录里没有摄像头字段，
关联靠**设备**这一层（`video_channels.device_id` == `alert_records.device_id`）；
关联不上就显示「未关联」，不去编一个摄像头名。告警类型与处置状态的中文文案由后端统一给出
（`alert_type_label` / `status_label`），不再由各页面各写一套映射。

## 系统监控（真实主机指标）

`/system-monitor` 改造前是整块演示数据：CPU / 内存 / 网络由 `Math.random()` 每 3 秒改写一次，
趋势曲线也是随机数滚出来的；峰值/均值、数据库连接数（42/200）、QPS、TPS、缓存命中率、
接口调用量、进程列表全是写死的常量，页面上标注的「每 5 秒刷新」同样是假的。

现在所有数字来自真实采集（`services/system_metrics_service.py`，依赖 `psutil`）：

| 页面区块 | 真实来源 |
| --- | --- |
| 统计卡（CPU / 内存 / 磁盘 / 网络） | `GET /api/system/host`：psutil 实时采样 |
| 服务状态 | `GET /api/system/health`：真实检查后端服务、运行数据库、业务闭环数据、设备与旧表、RAG 知识库、消防题库、智能模型配置 |
| 性能监控（趋势 / 峰值 / 均值 / 进程排行） | `GET /api/system/host` 的采样点 + `GET /api/system/processes` |
| 数据库状态 | `GET /api/system/database`：连通性、库大小、连接池、各表行数（dbstat 可用时附表大小） |
| 接口监控 | `GET /api/system/api-stats`：`MetricsMiddleware` 在每个真实请求上累加的计数与耗时 |

几条刻意的设计：

- **CPU 与网络速率要两次采样**：均按两次调用之间的差值计算，首次访问没有基准值就返回 `null`，
  界面显示「--」——不编一个看起来合理的数字。
- **不提供的就不显示**：SQLite 没有 QPS / TPS / 缓存命中率，接口在 `unsupported_metrics` 里明确列出，
  页面用一条说明替代原来的三个假数字。
- **进程 CPU 按单核计**：多线程进程会超过 100%，接口返回 `cpu_basis` 说明口径，进度条按 100% 截断显示；
  Windows 的空闲进程（pid 0）不参与排行，否则它会一直霸榜。
- **趋势不做持久化**：采样点存在进程内存里（最多 120 个），进程重启后重新累积，
  页面文案写的就是「服务启动以来的真实采样」。

> 顺带修掉的假数据：通知中心在请求失败时会塞回 2024-01-15 的 3 条演示通知
> （页面看着有未读，其实一条都没取到），「全部已读」失败时也照样弹「已标记为全部已读」。
> 现在通知失败即呈现空态、标记失败不再假报成功。

## 遥测扩展：电气与水系统

`/electrical-fire`（电气火灾监测）与 `/water-monitor`（消防水源监测）改造前各有一整页
2024-01-15 的写死数据：8 个配电回路、8 个测温点、8 条三相电流、8 台消火栓、
4 座水箱水池、6 台水泵，以及配套的告警列表；两个页面都**没有 `onMounted`、没有任何接口调用**。

根因不在前端——是时序表缺列。设备的 HTTP/MQTT 接入通道早就认识这 4 个指标
（`METRIC_ALIASES`），阈值规则也早就定义好了（`telemetry_analyzer.TELEMETRY_RULES`），
但 `DeviceTelemetry` 表当时只有 `temperature/smoke/co/battery/online` 五列，
`TELEMETRY_COLUMNS` 里没有它们的映射，于是这些值**只进了告警上下文、不入时序表**。

| 层 | 改造前 | 改造后 |
| --- | --- | --- |
| 表结构 | 5 个值列 | 加 `current` / `voltage` / `pressure` / `remaining_current`（全部 nullable，老数据保持 null） |
| 迁移 | — | `alembic/versions/a1b2c3d4e5f6_*`：`batch_alter_table` 加列，downgrade 可干净回退 |
| 摄取 | 4 个指标丢进告警上下文 | `TELEMETRY_COLUMNS` 补齐映射，`ingest_telemetry()` 原样写入 |
| 查询 | 只有按租户列最近 100 条 | 新增 `GET /api/telemetry/latest`（按设备类型取每台设备该指标的最新值 + 阈值规则） |
| 前端 | 24–32 条写死数据 | 两个页面改为 `onMounted` 调真实接口，告警页签复用 `/api/alert/list` |

`GET /api/telemetry/latest?device_type=配电箱&metric=remaining_current` 的返回：

```json
{
  "metric": "remaining_current",
  "unit": "mA",
  "thresholds": { "normal_range": [0, 300], "warning_threshold": 500, "alarm_threshold": 1000 },
  "items": [
    { "device_id": 7, "device_name": "1号办公楼总配电箱", "value": 12.5, "status": "normal",
      "warning_threshold": 500, "alarm_threshold": 1000, "normal_min": 0, "normal_max": 300,
      "update_time": "2026-09-17T14:03:11" }
  ]
}
```

几条刻意的设计：

- **从未上报就是离线，不编数**：设备没有该指标的样本时返回 `value: null` + `status: "offline"`，
  页面显示「--」和「从未上报」，而不是给一个看起来合理的读数。
- **状态由后端阈值规则判定**：接口直接返回 `normal/warning/alarm`（内部调 `analyze_telemetry_single`），
  前端只做配色，不重复实现一套阈值比较。
- **三相电流没有拆成 A/B/C 三列**：硬件上报的是单值 `current`，表里也就一列。
  电流页签因此展示「电流 / 电压 / 阈值 / 状态」，原来的三相电流与负载率（需要额定电流，后端没有）不再出现。
- **水箱水位与水泵工况保持空态**：这两个页面里最像「真实数据」的部分其实后端完全没有——
  水位、进出口压力、流量、电机电流都不在 `TELEMETRY_RULES` 的指标体系内，也没有对应列。
  页面改为一条说明「暂未接入遥测上报通道」，而不是继续显示 4 座水箱、6 台水泵。
- **演示点位单独收口**：`services/demo_seed.py` 的 `TELEMETRY_DEMO_DEVICES` 一处定义
  9 台配电箱/消火栓点位，`seed_telemetry_demo_data()` 幂等补齐样本（重复启动不堆数据）。
  该函数由启动种子 `database.seed_data()` 调用——`seed_demo_data()` 只在手动调
  `POST /api/demo/seed` 时执行，启动路径并不经过它，所以不能只改那一处。
  演示取值落在真实阈值区间内，「异常」档故意越界（如 `remaining_current 620 > warning 500`），
  用来验证阈值判定链路确实生效。

> 顺带修掉的错别字：`database.py` 的启动种子把消火栓的设备类型写成「消防栓」，
> 与知识库、题库里的术语不一致，已统一为「消火栓」。

## 消防培训（培训计划 / 考试考核 / 培训档案）

`/fire-training` 改造前四个页签全是写死的演示数组：8 门课程、6 个培训计划、4 场考试、
8 条培训档案，日期都停在 2024-01。后端此前**一张培训相关的表都没有**——学习模块只有
答题流水 `learning_attempts`（运行库里的裸表），那是在线练习记录，不是培训档案。

| 页签 | 数据来源 |
| --- | --- |
| 培训课程 | 复用学习模块的课程（`GET /api/learning/courses`，只读） |
| 培训计划 | 新表 `training_plans`：`GET/POST /api/training/plans`、`PUT/DELETE /api/training/plans/{id}` |
| 考试考核 | 新表 `training_exams`：`GET/POST /api/training/exams`、`PUT/DELETE /api/training/exams/{id}` |
| 培训档案 | 新表 `training_records`：`GET/POST /api/training/records`、`PUT/DELETE /api/training/records/{id}`；导出 `GET /api/training/records/export` |

概览卡片由 `GET /api/training/stats` 提供（课程数来自学习模块，其余四项来自培训表）。

几条刻意的设计：

- **聚合值一律现算**：考试的参考人数 / 平均分 / 及格率、计划的「实际参训人数」都从
  `training_records` 聚合，不落冗余列——否则档案一改，场次统计就和档案对不上。
- **没成绩 ≠ 0 分**：`exam_score` 为 null 表示还没考，不计入参考人数与及格率；
  一条成绩都没有时接口返回 `avg_score: null` / `pass_rate: null`，页面显示「--」。
- **合格判定在后端**：及格线取自关联考试（`training_exams.pass_score`，缺省 60），
  接口直接返回 `is_passed` 与 `result_label`（合格 / 不合格 / **未考试**），前端只管配色。
- **不给悬空引用**：档案引用计划/考试时校验同租户存在；计划或场次下还有档案时不允许删除，
  而是提示「请先调整档案再删除」。
- **课程不在此新建**：课程内容由学习模块统一维护，本页只读展示，所以没有「新建课程」按钮。
- **导出带 BOM**：`GET /api/training/records/export` 按当前筛选条件导出**全部**档案
  （不只是当前页），开头写 UTF-8 BOM，Excel 直接打开不乱码。

权限：读 `training:view`、写 `training:manage`。两个权限码已加入权限清单，可在角色管理里授权；
管理员角色是 `*`，默认即有。存量库不需要额外补权限（目标角色已覆盖）。

初始数据：空表时种入 4 个计划 / 3 场考试 / 8 条档案（`services/training_service.py` 的
`seed_training_demo_data`，由启动种子调用）。档案真实关联到计划与考试上，所以计划实际人数、
考试统计都是自洽的；档案里特意覆盖了合格、不合格、尚未考试三种情形。

> E2E 只验证导出接口的 CSV 契约（表头 / BOM / Content-Disposition），**不在浏览器里点导出按钮**：
> Chromium 的 blob 下载会留下未消费的下载任务，让 Playwright 在 worker 收尾时抛
> `TargetClosedError`，污染整个用例的退出码。

## CAD 图纸导入（DXF）

`/building-detail/:id` 的「上传CAD图纸」把建筑平面图解析成墙体/门窗/消防设备/房间，
识别出的设备可批量导入设备表（`POST /api/cad/import-devices/{floor_id}`）。

**只支持 DXF，不支持 DWG。** 解析用 `ezdxf`，它读不了 DWG（AutoCAD 的二进制格式）。
传 DWG 会按文件头（`AC10xx`）识别出来并直接返回转换指引，不会拿去硬解析：

> 只支持 DXF 格式：DWG 是 AutoCAD 的二进制格式，解析库（ezdxf）读不了。
> 请先用 ODA File Converter 等工具把 DWG 转换成 DXF 再上传。

**解析靠图层名**——没有图层约定就什么都识别不出来：

| 构件 | 命中的图层名关键词 |
| --- | --- |
| 墙体 | `WALL` / `墙` / `墙体` / `WALLS` |
| 轴线 | `AXIS` / `轴网` / `轴线` |
| 门窗 | `DOOR` / `门` / `门窗` |
| 消防设备 | `DEVICE` / `设备` / `消防` / `FIRE` / `SMOKE` / `烟感` / `喷淋` / `SPRINKLE` |
| 房间文字 | `TEXT` / `文字` / `标注` / `房间` / `ROOM` |

设备还能按**块名**识别（`烟感`/`喷淋`/`消火`/`手报`/`灭火器`），半径小于 10 的圆也按设备处理。
这份约定集中在 `services/cad_layer_rules.py`，解析器与下面的筛选脚本共用同一份。

解析接口的响应里带着 `layers`（图层名列表）与 `layerCount`，页面直接摊开展示：
识别不出构件时，用户能立刻看出是不是图层命名没匹配上，而不必去翻原图。

**失败就是失败**。改造前这里在 `except` 里返回一份固定的假平面图并标 `success: True`，
前端照样画出来、还能把 20 个假设备写进设备表。现在：

| 情况 | 行为 |
| --- | --- |
| 传的是 DWG | 400，附转换指引 |
| DXF 解析报错 | 400，附真实异常信息 |
| 没解析出任何构件 | 422，说明可能是空图、或几何都在外部参照（xref）里 |
| 服务端缺 `ezdxf` | 503，提示装依赖（不再返回假图兜底） |

### 转换 DWG → DXF：`tools/dwg_batch_convert.py`

系统的解析只吃 DXF，所以拿到 DWG 图纸集合（比如一整包 300+ 套施工图）第一步是批量转换。
这个脚本封装 [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)：

```bash
cd backend
# 先看计划，不实际转换
python tools/dwg_batch_convert.py "F:/cad/图纸目录" --dry-run
# 实际转换，输出到同级的 <目录名>_dxf
python tools/dwg_batch_convert.py "F:/cad/图纸目录"
# ODA 没装在默认位置时显式指定
python tools/dwg_batch_convert.py "F:/cad/图纸目录" \
    --oda "C:/Program Files/ODA/ODAFileConverter 25.4.0/ODAFileConverter.exe"
```

脚本自动探测 ODA 安装路径（扫 `Program Files\ODA\*`，取版本号最大的），转换前打印计划并要求确认
（`--yes` 跳过），支持 `--version`（默认 ACAD2018）、`--audit`（让 ODA 修复损坏图纸）、
`--overwrite`、`--timeout`。

三个容易踩的坑，脚本都处理了：

| 坑 | 处理方式 |
| --- | --- |
| **重名文件互相覆盖**：图纸集合里 `厂房建筑图.dwg` 这类名字在多个子目录都出现，ODA 递归后若平铺到同一目录就会覆盖 | 按"所在目录"分组逐个调用，输出严格镜像输入的相对路径 |
| **ODA 启动器可能是异步的**：命令行退出不代表文件写完，立刻统计会漏文件 | 退出后继续轮询输出目录，文件数稳定一段时间才算完成，并与该目录的 DWG 数比对 |
| **中文路径**：ODA 是 Qt 程序，个别版本对中文路径会失败 | 失败目录单独列出并打印 ODA 的输出，提示可复制到纯英文路径（如 `C:\cad_tmp`）重试 |

转换支持**中断续跑**：已存在且不比源 DWG 旧的 DXF 会被跳过，重跑不会白费前面的时间。
完成后直接接上图的筛选脚本。
（`tests/test_dwg_batch_convert.py` 守着输出路径镜像、增量跳过、等待写完这三处逻辑。）

### 挑图纸：`tools/dxf_layer_report.py`

一批图纸里哪些真的能被解析出来？别靠文件名猜，直接扫：

```bash
cd backend
python tools/dxf_layer_report.py "D:/图纸目录" --detail
python tools/dxf_layer_report.py "D:/图纸目录" --min-walls 50 --top 20 --csv report.csv
```

输出每张图的图层数、墙段、门窗、设备点、房间文字，并按可解析性给判定：

| 判定 | 含义 |
| --- | --- |
| ★★★ 推荐（墙线+设备） | 墙段 ≥ 50 且有消防设备点，能验证完整链路 |
| ★★★ 推荐（墙线+房间） | 墙段 ≥ 50，能验证墙与房间 |
| ★★ 可测墙线 | 墙段 ≥ 10 |
| ★ 构件很少 | 墙段 > 0，多半是详图或局部图 |
| ☆ 未命中图层约定 | 一个墙段都没有：非建筑平面图，或图层名不匹配 |

`.dwg` 会被单独列出并标记「需先转 DXF」，脚本不会去硬解析；`--detail` 会打印每张图命中的
图层名与识别到的设备类型，用来排查「为什么没解析出来」。判定与实际解析结果一致这一点有测试守着
（`tests/test_cad_parse.py::TestLayerReportTool`）。

## 数据大屏

大屏（`/dashboard`）所有数值、名称、点位均来自 `GET /api/dashboard/screen-data`，页面不做任何常量兜底：接口失败时只提示「数据加载失败」并保留上一次成功的数据，绝不编造数字。首次加载（尚未拿到过任何一次数据）时盖加载遮罩，30 秒轮询刷新则不再盖，以免大屏周期性闪动；各列表面板无数据时显示占位文案而不是留白；页脚「数据更新时间」取自最近一次成功加载（没成功过则为 `--`），不跟着秒针跳。

### 1. 数据来源对照

| 区块 | 数据来源 |
| --- | --- |
| 顶部状态 | `indicators` 中的设备在线率、当日告警数 |
| 设备运行概览 / 告警统计 / 告警趋势 | `devices`、`alarms` |
| 隐患治理（含整改率） | 巡检记录 `hazards` 字段抽取 + 工单闭环率 |
| 建筑分布、风险排名 | `buildings.list`（含真实 `riskScore`、`riskLevel`、`deviceCount`、`alarmCount`、`status`） |
| 消防水源 / 电气火灾 | 按设备类型关键字匹配真实设备在线/告警状态；无对应数据源的管网压力、水箱水位、剩余电流返回 `null`，页面显示 `--` |
| 值班信息 | 当前时段排班 `DutyShift` |
| 3D 场景 / 热力图 / 设备分布 | 见下节 |
| 今日事件 | 当日告警 + 巡检记录 + 整改工单合并倒序 |
| 待办事项 | 未闭环工单 `FaultTicket` |
| 重点区域视频 | 通道台账 `videoList` + `GET /api/video/channels/{id}/snapshot?token=` 抓拍图（令牌由 `POST .../snapshot-token` 签发，`<img>` 无法携带请求头） |

### 2. 3D 场景与热力图的坐标规则

三个视图（3D GIS 地图、热力图、设备分布）共用同一份建筑台账：

- **位置**：由建筑真实 `latitude` / `longitude` 换算到场景与画布坐标，规则如下：
  - 经纬度**都**为 0 的建筑视为「未定位」；中心点与缩放比例**只由已定位的建筑**决定
  - 经度按 `cos(纬度)` 折算成与纬度同量纲后再参与换算，否则园区会被横向拉伸
  - 最远的已定位建筑映射到场景半径 55；未定位的建筑按序号等距环形排布（同半径），
    不会与已定位的建筑挤在一起
  - 建筑的位置、数量、体量都是确定性的（同一份数据每次渲染位置一致）；
    场景里的窗灯明暗与呼吸动画用到随机数，但那只是观感装饰
- **体量**：楼层高度取 `Building.floors`，占地取 `Building.area`。
- **颜色**：按建筑真实状态着色（正常 / 预警 / 告警），GIS 图例由同一份调色板生成，
  不会与画面出现色差。建筑没有「离线」态，因此图例也不列该状态。楼顶航障灯用的是同一状态色
  （亮度高一档），不再一律红灯——否则每栋楼看起来都在报警。
- **告警标记**：仅在该建筑 `alarmCount > 0` 时出现，数量与实际告警数对应。
- **设备光点**：数量取该建筑真实 `deviceCount`；颜色取 `devices.types[].color`，
  与「设备分布」二维视图、左侧「设备运行概览」的类型色同源。

> 历史缺陷：改造前中心点与缩放比例把**未定位建筑的 (0,0)** 也算进去，导致园区被压成一团、
> 两栋真实建筑完全重叠（实测 A、B 都落在同一个点），而未定位的建筑反而占了画面主位；
> 同时经纬度混在一个数组里取最大偏差，纬度方向被压扁。已修正。

### 3. 时间口径（全局约定，不限于大屏）

数据库里的时间列（`created_at` / `login_at` 等）落库为**无时区的 `datetime.utcnow()`**，
而「今日」「X分钟前」是**用户本地时区**的概念。跨这两种口径做比较必须显式换算，
否则在 UTC+8 下会整体偏移 8 小时。

| 场景 | 统一做法 |
| --- | --- |
| 「今日 / 近 N 日」窗口 | `services/common_utils` 的 `local_day_start_utc(days_ago)` / `local_day_end_utc(days_ago)` |
| 相对时间（「刚刚 / X分钟前 / X小时前」） | 直接拿 `datetime.utcnow()` 减 `created_at` |
| 客户端传入的时间戳 | `services.telemetry_analyzer.parse_timestamp_utc()`：解析成无时区 UTC，无法解析时返回 `None`（降级为「未提供」，不报错） |

> 历史缺陷（均已修正，并有回归用例）：
> - 大屏「今日告警」拿本地零点直接比 UTC 列 → 从本地 08:00 才开始，凌晨的告警被漏掉（`tests/test_data_screen.py`）
> - 大屏「X分钟前」用本地时间相减 → 刚发生的告警显示成「8小时前」（同上）
> - 遥测接口直接 `fromisoformat` 客户端时间戳 → 带时区时比较抛 `TypeError`、缺失或非法时抛 `ValueError`，
>   `/api/telemetry/analyze-history`、`/api/telemetry/analyze-single`、`/api/multimodal/interpret-alert`
>   三个接口都会返回 500（`tests/test_telemetry_analyzer.py`）

### 4. 已知限制

- 设备光点在建筑内部按确定性算法排布，**不是楼层平面图上的真实坐标**；光点**数量**取真实 `deviceCount`，但颜色只是按设备类型循环取用，**不代表某个光点真的属于该类型设备**。大屏是园区级视图；要在建筑内部按 `Device.floor_x/floor_y` 精确定位，需接入楼层平面图页面（`FloorPlan`）的数据 —— 现有数据链是「建筑 → 楼层 → 平面图」逐级取，没有批量接口，`screen-data` 里也不含楼层坐标，属独立的一期改造。
- 单个建筑未录经纬度时，该建筑按序号环形示意排布（体量、颜色、告警仍为真实数据）。
- 3D 场景按建筑台账指纹（id/状态/设备数/告警数/体量）判断是否重建，台账不变时不重建，以免 30 秒轮询把用户旋转好的视角复位。
- 右侧列表与 3D 场景都可下钻：实时告警 → 告警中心；待办 → `/workorders?order_id=`；风险排名、3D 里的建筑 → `/building-detail/:id`；今日事件按类型分流到告警中心 / `/records?record_id=` / `/workorders?order_id=`；视频 → 视频监控。下钻前会用路由守卫同一套规则校验权限，无权限时只提示，不会把人甩到「无访问权限」页。
- 重点区域视频卡展示的是**抓拍图轮询**（10 秒一帧，令牌 30 分钟续签），不是视频流；通道离线或抓拍失败时如实降级为占位并标「离线」，不显示坏图。
- 大屏的实时性来自 WebSocket 推送（见下节「实时推送」）：收到 `alert` 事件立即刷新一次；30 秒轮询仍在跑，作为推送链路异常时的兜底，因此最坏延迟 30 秒。

## 实时推送（WebSocket）

端点 `WS /ws/notifications`：开发环境经 vite 的 `/ws` 代理、生产经 nginx 的 `location /ws/` 转发到后端。

### 1. 握手与鉴权

HTTP 路由可以用 `Authorization` 头做依赖注入，WebSocket 握手没有这个入口，因此改为**连上后首帧认证**：

```json
客户端 → {"action": "auth", "token": "<access_token>"}
服务端 → {"type": "auth_ok", "data": {"user_id": 1, "username": "admin", "tenant_id": 1}}
```

- `user_id` / `tenant_id` **只认令牌解析结果**，客户端自报的一律忽略
- 令牌无效 / 已撤销 / 账号停用 → `4401` 关闭；账号未关联租户 → `4403`；10 秒内没发认证帧 → `4401` 关闭（不留匿名空连接）
- 客户端收到 `44xx` 不再重连（重连也不会成功），其它断开按 1s→30s 退避重连；每 25 秒发一次 `{"action": "ping"}` 心跳（nginx 默认 60 秒无数据就掐连接）

> 历史缺陷：改造前端点是 `/ws/notifications/{user_id}`，`user_id` 由 URL 自报且握手不做任何令牌校验，
> 而 nginx 已把 `/ws/` 反代到后端 —— 等于对外开放了一个可按任意身份连接的匿名端点。

### 2. 推送范围与时机

- **按租户隔离**：`notify_tenant(tenant_id, message)` 只发给该租户的连接
- **时机**：新告警创建时推一次 `alert` 事件（设备接入链路 `alert_lifecycle_service.ingest_alert` 与手工建单 `business_crud_service.create_alert` 都会推）；同一条告警在归并窗口内被重复上报**不推**，只有升级（`escalated`）时再推一次——否则高频重复上报会把大屏刷爆
- 事件类型：`alert`（告警）、`workorder`（工单）、`system`（系统通知，`POST /api/ws/test-broadcast` 可手工触发一条）

> 历史缺陷：改造前 `broadcast()` 遍历所有连接全量下发，A 租户的告警会推给 B 租户；
> 且触发推送用的是 `asyncio.create_task`，而调用它的接口是同步 `def`（跑在线程池里），
> 会抛 `RuntimeError: no running event loop` —— 推送其实一次都没发出去过。
> 现在推送统一经 `notify_tenant()` 用 `run_coroutine_threadsafe` 投递到连接所在的事件循环。

### 3. 前端接入

- `frontend/src/utils/websocket.js` 是全局单例，由 `App.vue` 在登录后建立连接、登出或卸载时断开
- 页面只订阅事件：通知铃铛与数据大屏都订阅 `alert`，大屏收到后立即刷新一次

### 4. 已知限制

- 连接表是**单进程内存态**：多副本部署时，A 副本产生的告警推不到连在 B 副本上的浏览器，需要引入 Redis pub/sub（本期未做；单机 Docker Compose 部署不受影响）。

## 值班室（排班 / 值班记录 / 交接班）

页面 `/duty-room` 的四个页签（值班记录 / 交接班记录 / 值班排班 / 值班人员）都来自真实数据，没有写死的演示内容。

### 1. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/duty/stats` | 当班人数、在岗状态等统计 |
| GET | `/api/duty/shifts` | 排班列表，支持 `date`（单日）与 `start_date` / `end_date`（周视图按区间取数）；日期格式不对则忽略该边界。排序为值班日期倒序、开始时间正序、id 正序（并列时也要有确定顺序，否则页面取「当前班次」会随机命中旧数据） |
| POST / PUT / DELETE | `/api/duty/shifts`、`/api/duty/shifts/{id}` | 排班增改删 |
| GET | `/api/duty/records` | 值班记录分页，支持 `start_date` / `end_date` |
| POST / PUT / DELETE | `/api/duty/records`、`/api/duty/records/{id}` | 值班记录增改删 |
| GET | `/api/duty/handovers` | 交接班分页，响应里带 `shiftName` |
| POST / DELETE | `/api/duty/handovers`、`/api/duty/handovers/{id}` | 交接班增删 |

除 `stats` 外，写接口一律要求 `duty:manage` 权限，并按 `tenant_id` 隔离（跨租户操作返回 404 而不是 403，避免探测出别家 id）。

### 2. 字段与表结构的对应关系

写入前统一由 `services/duty_schedule_service.py` 校验，前端的列、对话框字段与库表一一对应：

- `duty_shifts.persons` 历史上有 `["张三"]` 与 `[{id,name,role}]` 两种形态，序列化**原样返回**，压成姓名列表会让页面按 `p.name` 取值的地方变成空白
- `duty_handovers` 只存 `shift_id`，班次名由列表接口**一次性批量查出**后补上，不额外建冗余列
- 排班冲突（同日同名班次、同日同一人重复排班）在服务层拒绝；时间 `8:00` 会规范化为 `08:00`

> 历史缺陷：这两个对话框的「保存」只弹一句「成功」、不发任何请求；表格里的列也对不上库里的字段——记录的「类型」恒为「日常值班」、「状态」拿设备状态冒充，交接班的「班次」恒为空、「当班接警」恒为 0。现已改为真实调用，并删掉没有对应列可写的输入项。
> 新增值班记录时，班次默认落在页面正在显示的「当前值班信息」上；值班人下拉的候选来自当前班次的真实排班人员。

### 3. 值班人员是「推」出来的，不是人员主数据

后端**没有人员表**（没有技能、证书、在岗状态这些字段），因此：

- 「值班人员」页签是只读视图：把今天及以后各排班 `persons` 里的人按姓名归并，每张卡片列出该人的值班日期、班次与时段，当前时段的人标「值班中」。证书编号、联系电话、入职日期这些库里没有的信息不再显示，也不再摆「添加值班人员 / 查看详情 / 排班」这类没有落点的按钮
- 交接班对话框的「接班人」候选同样取自**历史排班中出现过的人**，并允许直接输入名单外的人（`allow-create`），不再用一份写死的人名表

要变成可维护的人员台账（录入技能、证书、在岗状态并按人排班），需要新建人员/班组主数据表，属独立的一期改造。

### 4. 周排班表

「值班排班」页签是一张**周一 ~ 周日**的真实排班表：

- 周次由周选择器决定，归一化到该周的周一后按 `start_date` / `end_date` 取数，页面上会显示当前区间（如 `2026-09-14 ~ 2026-09-20`）；今天那一列有底色，便于定位
- 行按「班次名 + 时段」聚合（同一周里同名同时段的班次合成一行），单元格放当天该班次的人，本周没有任何排班时显示占位文案而不是空表
- 「新增排班」走真实的 `POST /api/duty/shifts`：填班次名称、类型、日期、时段与值班人员；面板默认排到当前正在看的那一周（今天不在该周时取该周周一），保存后自动跳到该班次所在的那一周并刷新「当前值班信息」
- 表单校验规则由后端统一把关（同日同名班次、同一人同日重复排班会被拒绝并提示原因）

> 历史缺陷：这张表此前是前端写死的两行（白班 / 夜班）加七个写死的日期（2024-01-15 那一周），人名也是常量；「新增排班」按钮没有 handler，点了没有任何反应。

## 审计日志（操作日志）

### 1. 统一存储与防篡改

所有操作日志统一落在主库 `operation_logs` 表，并串成**哈希链**：

```text
hash = SHA256( prev_hash + "\n" + 规范化JSON(seq, tenant_id, source, user_id, username,
        module, action, title, description, target_type, target_id, level, status,
        status_before, status_after, link, payload, created_at) )
```

- 首条的 `prev_hash` 为 64 个 0；每条记录的 `seq` 全局单调递增
- 规范化 JSON 使用 `sort_keys=True` + 紧凑分隔符，保证重算结果稳定
- 任何对历史记录的**修改、删除或插入**都会导致后续链条校验失败，并定位到具体 `seq`
- 并发写入靠唯一索引 `uq_operation_log_seq` 兜底，冲突方重新取链尾并重试

改造前系统里是「两套写入 + 一套读取」：业务代码写裸 SQLite、日志中间件写主库、页面只读主库，
导致工单状态变更、复查结论、档案创建等业务日志在页面上完全看不到。现已统一为单一存储。

### 2. 接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/system/operation-logs` | `logs:view` | 分页列表，支持 `module`/`level`/`source`/`username`/`keyword` 过滤 |
| `GET /api/system/operation-logs/dashboard` | `logs:view` | 页面指标卡与模块/操作分布；含 `status_changed_count`（写入了 `status_before`/`status_after` 的记录）与 `today_login_users`（今日登录成功的去重账号数） |
| `GET /api/system/operation-logs/verify` | `logs:view` | 重算哈希链，返回 `ok`、已校验条数、链尾哈希与首个异常位置 |
| `GET /api/system/operation-logs/export` | `logs:view` | 审计导出，`format=csv\|json`，支持模块/级别/关键字/时间范围过滤 |

**校验结果字段**：`checked`（进入链的条数）、`unverified_legacy`（历史遗留、未接入链的条数）、
`head_hash`（链尾哈希）、`first_broken`（首个异常：序号不连续 / 前序哈希不匹配 / 内容与哈希不一致）。

导出的 CSV 带 UTF-8 BOM（Excel 直接打开不乱码），列包含 `链序号`、`前序哈希`、`本行哈希`，
可在离线环境用同样的算法重算校验；JSON 导出额外带 `export_meta`（导出人、时间、条数、链校验结果）。

**导出行为本身也会被记入审计日志**（`module=操作日志, action=export, level=warning`），
避免「导出动作无迹可查」。

### 3. 租户隔离

列表、看板与导出均按 `tenant_id` 过滤；`tenant_id` 为空的历史日志视为「未归属租户」一并可见，
避免升级后旧日志凭空消失。校验接口作用于全局链，因此不做租户过滤，返回内容也只有计数与
异常位置摘要，不含其他租户的日志正文。

### 4. 已知限制

- 升级前已写入的日志没有 `seq`，无法纳入哈希链，会在校验结果中计入 `unverified_legacy`
- 登录日志存在独立的 `login_logs` 表（见「登录日志」），**不进哈希链**：它记录的是
  登录前的事件，此时还拿不到可信的用户身份，与「谁做了什么」的审计链口径不同

## 登录日志

### 1. 与审计日志的分工

| | `operation_logs`（审计日志） | `login_logs`（登录日志） |
| --- | --- | --- |
| 记录对象 | 登录后的业务与系统操作 | 每一次登录尝试（成功与失败都记） |
| 防篡改 | 哈希链（`seq` + `prev_hash`） | 无（登录前无法确认身份） |
| 与锁定计数的关系 | — | 逐次明细；锁定判定仍用 `login_attempt_states` 的聚合计数 |

改造前该标签页是一组写死的 2024-01 演示数据。现在登录成功、密码错误、用户不存在、
账号已禁用都会各写一行，页面展示的条数与后端一致。

### 2. 接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/system/login-logs` | 分页查询，支持 `username`（模糊）、`status`、`ip_address`、`start`/`end` |

设备、浏览器、IP 归属地**不落库**，读取时从 `user_agent` 与 `ip_address` 推导，
解析规则升级后历史数据自动跟着变。归属地只对可判定的内网/回环地址给出「内网」「本机」，
公网地址留空（未接入 IP 库，不做无依据的判断）。

### 3. 权限与租户隔离

- 与审计日志共用 `logs:view` 权限
- 已知用户的记录带 `tenant_id`，按租户隔离
- **未知用户名的失败尝试 `tenant_id` 为空，对所有租户管理员可见**——这是跨租户的
  账号探测信号，隐藏它反而会掩盖攻击；由于此时用户名并不存在，不会泄露其它租户的账号

## 后台任务队列

### 1. 为什么需要它

批量巡检此前是**进程内字典 + 同步端点里调 `asyncio.create_task`**：没有运行中的事件循环，
后台协程根本起不来（`RuntimeError: no running event loop`，接口直接 500）；任务与进度只存在内存，
重启即丢；无任务时还会凭空造出 3 条演示任务掩盖问题。报表导出则在请求里同步跑完，
`period=year` 时会串行发出 300+ 条 count 查询，前端长时间等待。

现在统一走 `background_tasks` 表 + 进程内 worker。

### 2. 队列语义

| 机制 | 说明 |
| --- | --- |
| 持久化 | 任务落库，进程重启后 `pending` 任务继续被领取 |
| 抢占式领取 | `UPDATE ... WHERE id=? AND status='pending'`，按影响行数判定是否抢到；SQLite / PostgreSQL 通用，多实例共用一个队列不会重复执行 |
| 租约 | 运行中的任务持有 `lease_expires_at`，worker 每 60 秒续租；worker 崩溃后租约过期即被回收 |
| 回收策略 | 租约过期且未达 `max_attempts` → 重新排队；已达上限 → 标记失败并记录原因 |
| 进度 | `progress` / `done_items` / `total_items` / `progress_message`，`result` 里可放运行中也要展示的中间结果 |
| 取消 | 置为 `canceled`；处理器在循环中通过 `ctx.canceled()` 感知并提前退出，且不会被成功收尾覆盖 |
| 执行隔离 | 同步处理器在线程池执行，同步 SQLAlchemy 与文件 IO 不阻塞事件循环 |

### 3. 已接入的任务类型

| task_type | 触发入口 | 说明 |
| --- | --- | --- |
| `batch_inspection` | `POST /api/batch-inspection/create` | 逐点位做规则引擎隐患抽取与风险评分，结果汇总在任务 `result` |
| `report_export` | `POST /api/reports/export/tasks` | 异步生成报表并归档，完成后用 `artifact_id` 走受控下载 |

新增任务类型只需写一个处理器并用 `@register_handler("xxx")` 注册（见 `services/task_handlers.py`），
worker 启动时会自动加载。

### 4. 接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/tasks` | 登录用户 | 任务列表，支持 `status`/`task_type`/`keyword` |
| `GET /api/tasks/{task_id}` | 登录用户 | 任务详情（含 payload 与 result） |
| `GET /api/tasks/types` | 登录用户 | 已注册的任务类型（排查"任务没人执行"） |
| `GET /api/tasks/stats` | `system:tasks` | 任务分布与 worker 运行状态 |
| `POST /api/tasks/{task_id}/cancel` | `system:tasks` | 取消任务 |
| `POST /api/tasks/{task_id}/retry` | `system:tasks` | 失败任务重新入队 |

批量巡检的四个接口走独立权限码：

| 接口 | 权限 |
| --- | --- |
| `POST /api/batch-inspection/create` | `batch:create` |
| `GET /api/batch-inspection/list` | `batch:view` |
| `GET /api/batch-inspection/{task_id}` | `batch:view` |
| `GET /api/batch-inspection/{task_id}/progress` | `batch:view` |

`batch:view` / `batch:create` 此前只存在于权限清单里，既没有接口校验也没有授予角色，
**任何登录用户都能创建批量巡检任务**。现在：接口按权限码拦截；`inspector` 角色默认持有
两个权限码；前端「巡检计划」菜单与「新建任务」按钮同权限码联动。存量库的角色权限由
`database.SYSTEM_ROLE_PERMISSION_PATCHES` 在启动时幂等补齐（角色种子受
`Role.count() == 0` 守卫，存量库不会重跑，必须单独下发）。

### 5. 配置与监控

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TASK_WORKER_ENABLED` | true | 是否启动进程内 worker |
| `TASK_WORKER_POLL_SECONDS` | 2 | 空闲轮询间隔 |
| `TASK_WORKER_HEARTBEAT_SECONDS` | 60 | 续租间隔（需小于 900 秒租约） |
| `TASK_WORKER_RECOVER_SECONDS` | 60 | 回收租约过期任务的检查间隔 |

`/metrics` 暴露 `fire_ai_background_tasks{status=...}`、`fire_ai_task_worker_running`、
`fire_ai_task_worker_failed_total`。

> worker 在 `main.py` 的 lifespan 内启动，关停放在 `try/finally` 中，保证异常退出时也能停止
> MQTT 接入与后台 worker。**不要**从同步端点里调用 `asyncio.create_task`——这正是修复前的故障原因。

## 设备消息队列（收件箱）

### 1. 改造前后的差别

改造前设备消息在 MQTT 回调里**同步处理**：处理失败只打一行日志，既不重试也无从追溯；
也没有端到端幂等键——设备重发只能靠 nonce 防重放，换一个 nonce 就会重复产生告警与工单。

现在 MQTT 回调只做两件事：**验签**（不能让未验签的数据落库）与**落收件箱**，
业务处理交给后台任务队列。这样就有了削峰、重试、死信与完整追溯。

### 2. 两层幂等

| 层级 | 机制 | 拦截的场景 |
| --- | --- | --- |
| 第一层 | `device_request_nonces` 唯一约束 | 同一信封（同 nonce）重复投递 = 重放，直接拒绝 |
| 第二层 | `device_messages(tenant_id, message_id)` 唯一约束 | 设备换了新 nonce 重发同一条业务消息，只处理一次 |

`message_id` 优先取设备提供的值；未提供时用 `{device_code}:{nonce}`，再退化为内容哈希。

### 3. 状态与死信

`pending → processing → processed`，失败记为 `failed` 并按任务队列策略重试，
超过 `DEVICE_MESSAGE_MAX_ATTEMPTS` 后进入 `dead`（死信）。

不可恢复错误（设备不存在、消息类型不支持）直接进死信，不做无意义重试。

### 4. 接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/device-messages` | `devices:manage` | 消息列表，`status=dead` 查死信 |
| `GET /api/device-messages/stats` | `devices:manage` | 各状态数量，用于判断积压与死信 |
| `POST /api/device-messages/{id}/replay` | `devices:manage` | 人工重放失败/死信消息 |

> HTTP 直连接口仍保持同步返回（设备需要立即知道结果），收件箱目前只覆盖 MQTT 通道。

## 对象存储

### 1. 为什么需要

上传文件此前只落本地磁盘，多实例部署时 A 实例写入的文件在 B 实例上读不到。

### 2. 策略：本地优先 + 对象存储镜像

| 操作 | 行为 |
| --- | --- |
| 写入 | **始终写本地**（视觉识别等链路需要本地路径），同时镜像到 S3 |
| 读取 | 本地命中直接返回；本地缺失则从 S3 拉回本地再返回 |
| 删除 | 本地与 S3 同时删除 |

未配置对象存储时行为与原来完全一致（纯本地）。

存储键由 `file_path` 相对上传根目录推导，跨实例稳定；历史数据仍是绝对路径，继续兼容。

### 3. 配置

```bash
STORAGE_BACKEND=s3
S3_ENDPOINT=http://minio:9000
S3_BUCKET=fire-ai
S3_REGION=cn-north-1
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_PREFIX=fire-ai
S3_PATH_STYLE=true       # MinIO 等自建端点通常需要 path-style
S3_VERIFY_TLS=true
```

使用标准 **SigV4 签名**（`AWS4-HMAC-SHA256`），只依赖 httpx 与标准库，不引入 boto3；
兼容 MinIO / 阿里云 OSS / 腾讯云 COS 等支持 S3 协议的端点。

> 验证程度：签名算法与请求形状已由自动化测试断言（规范化请求、signedHeaders、
> 签名长度与 payload 哈希），**尚未与真实 MinIO 桶联调**。

## 多实例部署与水平扩展

### 1. 使用方式

```bash
# 单主机多副本：共享卷即可，无需对象存储
docker compose -f deploy/docker-compose.scale.yml --env-file .env up -d --build
docker compose -f deploy/docker-compose.scale.yml --env-file .env up -d --scale backend=3

# 验证负载均衡是否生效（instance_id 应在副本间轮换）
for i in 1 2 3 4; do curl -s http://127.0.0.1/health | grep instance_id; done
```

多副本的 nginx 配置见 `deploy/nginx.scale.conf`：用 Docker 内嵌 DNS
（`resolver 127.0.0.11`）动态解析 service 名，新扩出的副本会被自动纳入轮询。

### 2. 已经具备的共享能力

| 能力 | 实现方式 |
| --- | --- |
| 后台任务不重复执行 | `UPDATE ... WHERE status='pending'` 按影响行数抢占，SQLite/PG 通用 |
| 登录失败锁定、令牌黑名单 | 数据库持久化（见之前的改造） |
| 启动期播种、数据库迁移只做一次 | `runtime_locks` 跨实例互斥锁，持有者崩溃后按 TTL 接管 |
| 建表/迁移并发安全 | 迁移对"表已存在"类错误重试，并识别「另一实例已完成」 |
| 上传文件跨实例可读 | 对象存储镜像 + 本地缺失回源 |
| 设备消息不重复消费 | MQTT 共享订阅组；未配置时由收件箱幂等兜底 |

### 3. 仍是「每实例独立」的部分

| 项 | 影响 | 建议 |
| --- | --- | --- |
| Prometheus 指标 | 每个副本各有一份计数 | 按副本分别抓取，或改用 `sum by (job)` 聚合 |
| 限流计数 | 每副本独立计数，实际额度是 N 倍 | 需要全局限流时改为共享存储计数 |
| 视频抓拍缓存 | 每副本各自缓存，回源次数 ×N | 影响有限，可接受 |
| WebSocket 通知 | 连接固定在某副本，其他副本产生的通知不会跨实例广播 | 需要跨实例推送时增加 sticky 路由，或后续补通知轮询 |

### 4. 跨主机部署的前置条件

- **上传/报表**：必须启用对象存储（各主机卷不共享）
- **运行时库**：`RUNTIME_DB_PATH` 指向的裸 SQLite 存储（巡检档案、工单闭环、学习答题、
  RAG 条目等）目前**只支持单主机共享卷**。路径解析已统一到
  `services/runtime_db.py` 一处，跨主机部署时把它指向共享存储即可；
  彻底跨主机仍需把这些表迁到主库 —— 这是当前明确的遗留项

## 数据库结构迁移（Alembic）

表结构**唯一来源是 Alembic 迁移**，不再依赖启动时的 `Base.metadata.create_all()`
（后者只能保证「全新库结构正确」，已有库加列改索引仍需手工 DDL）。

### 1. 三种库形态

| 形态 | 判定 | 启动时行为 |
| --- | --- | --- |
| 全新库 | 一张业务表都没有 | `alembic upgrade head`，由基线迁移建出全部表 |
| 存量库 | 有业务表但没有 `alembic_version` | 先 `stamp` 到基线版本（不重建表、不动数据），之后按迁移升级 |
| 已接入 | 有 `alembic_version` | 版本落后就 `upgrade head` |

启动时自动迁移受 `DB_AUTO_MIGRATE` 控制（默认 `true`）。多实例部署时由
`runtime_locks` 互斥，没抢到锁的实例会等前者把版本推到 head 再继续启动，
避免「A 在改表、B 已经开始按新结构读写」；迁移失败直接中止启动，
不让应用带着不确定的结构运行。

### 2. 常用命令

```bash
cd backend

# 结构已改（database.py 加了模型/字段）后生成迁移，务必人工过一遍
alembic revision --autogenerate -m "add xxx"

# 手动升级 / 回退 / 查看当前版本
alembic upgrade head
alembic downgrade -1
alembic current
```

发布脚本 `scripts/release.sh` 在构建镜像后、切换流量前会检查 `DB_AUTO_MIGRATE`：
为 `false` 时用新镜像执行 `alembic upgrade head`，失败即中止发布（旧版本仍在运行）。

### 3. 存量库的注意点

基线版本（`alembic/versions/*_init_schema.py`）与当时的模型完全等价，因此存量库
`stamp` 到基线是安全的。但「等价」是个假设：如果某个存量库的结构与当前模型有偏差，
`stamp` 之后需要补一条迁移来对齐。开发用 SQLite 库还有
`database._migrate_sqlite_columns()` 兜底补列，生产库没有这层兜底。

## 生产部署、发布回滚与监控告警

### 1. 环境要求与前置

- 单机 Docker Compose + PostgreSQL 16（生产模式下后端会拒绝 SQLite）
- 必填环境变量：`DATABASE_URL`、`JWT_SECRET_KEY`（≥32 位）、`METRICS_TOKEN`、`POSTGRES_PASSWORD`
- 数据库驱动为 **psycopg 3**，连接串须使用 `postgresql+psycopg://`（不是 `psycopg2`）
- 构建镜像需能访问镜像仓库；若网络受限，请为 Docker 配置镜像加速或 HTTPS 代理后再执行

```bash
cp .env.example .env        # 填写上述必填项
# 生成密钥：python -c "import secrets;print(secrets.token_urlsafe(48))"
```

### 2. 首次部署

```bash
docker compose build
docker compose up -d
docker compose ps                       # 三个服务应均为 healthy/running
curl -f http://127.0.0.1/health         # 存活探针
curl -f http://127.0.0.1/ready          # 就绪探针（含数据库连通性）
```

**创建初始管理员（必做）**：生产模式不生成任何演示账号，全新数据库没有任何用户，
不执行本步骤将无人可登录：

```bash
docker compose exec backend python create_admin.py --username admin --password 'YourStrongPass123'
docker compose exec backend python db_backup.py backup     # 建议同时做一次基线备份
```

`create_admin.py` 会校验密码强度（≥8 位且含字母与数字），账号已存在时默认拒绝重建，
如需重置密码请追加 `--reset-password`。

后端容器为**只读根文件系统**，可写数据通过命名卷挂载：上传文件、报表产物、运行时库、备份目录分别对应
`uploads_data` / `reports_data` / `runtime_data` / `backups_data`，均由 `UPLOAD_STORAGE_DIR`、
`REPORT_STORAGE_DIR`、`RUNTIME_DB_PATH`、`BACKUP_DIR` 指向 `/var/lib/fire-ai/` 下。

### 3. staging 环境

与生产同镜像、独立端口与数据库，用于上线前验收：

```bash
cp .env.staging.example .env.staging
# 按需修改 CONTAINER_PREFIX（默认 fire_ai_staging，避免与生产容器同名）
docker compose -f docker-compose.yml -f docker-compose.staging.yml \
    --env-file .env.staging -p fire_staging up -d --build
curl -f http://127.0.0.1:8080/ready
docker compose -f docker-compose.yml -f docker-compose.staging.yml --env-file .env.staging -p fire_staging \
    exec backend python create_admin.py --username stagingadmin --password 'StagingPass123'
```

### 4. 发布与回滚

```bash
./scripts/release.sh v1.0.0     # 备份 → 构建带版本镜像 → 滚动更新 → 健康检查 → 失败自动回滚
./scripts/rollback.sh           # 回滚到上一个版本
./scripts/rollback.sh v0.9.0    # 回滚到指定版本
STAGING=1 ./scripts/release.sh  # 发布 staging
```

发布流程会：① 校验 `.env` 与 Docker 可用性；② 对数据库做**发布前备份**（失败即中止，避免无备份发布）；
③ 记录当前版本到 `.release_state` 供回滚；④ 以版本号构建镜像；⑤ 更新容器并等待 `/ready`；
⑥ 健康检查未通过时**自动回滚**到上一版本并输出后端日志。

回滚注意：脚本只切换应用镜像。若某次发布包含**不可逆的数据结构变更**，需同时恢复数据库：

```bash
docker compose exec backend python db_backup.py list
docker compose exec backend python db_backup.py restore <备份文件> --yes
```

### 5. 数据库备份与恢复

```bash
docker compose exec backend python db_backup.py backup          # 备份主库 + 运行时库，生成 sha256
docker compose exec backend python db_backup.py verify <文件>   # 校验完整性
docker compose exec backend python db_backup.py prune           # 按 BACKUP_RETENTION_DAYS 清理
```

建议在宿主机配置定时任务（每日 02:00 备份，备份目录挂载到独立磁盘）：

```cron
0 2 * * * cd /opt/fire_ai_agent && docker compose exec -T backend python db_backup.py backup >> /var/log/fire_backup.log 2>&1
```

### 6. 监控、告警与日志

- `GET /metrics`：Prometheus 文本格式指标（HTTP 计数/耗时、业务事件、MQTT 状态、数据库就绪、备份时效、
  大模型调用量/token/成本与熔断状态、待人工复核数量）。
  生产环境需携带 `METRICS_TOKEN`，且 nginx 已对该路径 `deny`，仅内网可抓取
- `GET /ready`：就绪探针；`GET /health`：存活探针（两者经 nginx 暴露，供外部负载均衡使用）
- 启动监控栈（Prometheus + Alertmanager + Grafana，默认仅监听本机回环）：

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.monitoring.yml up -d
# Prometheus http://127.0.0.1:9090 · Alertmanager http://127.0.0.1:9093 · Grafana http://127.0.0.1:3000
```

告警规则见 `deploy/prometheus/alert_rules.yml`，覆盖：

| 类别 | 规则 |
| --- | --- |
| 可用性 | 后端不可抓取、数据库不可用 |
| 错误与性能 | 5xx 错误率 > 5%、平均响应 > 2s |
| 安全 | 登录失败突增、多账号被锁定 |
| 业务闭环 | 出现自动升级告警、告警产生但未生成工单 |
| 设备接入 | MQTT 断开、消息被大量拒绝、长时间无设备数据 |
| 备份 | 备份超过 36 小时未更新、无任何备份 |
| AI 治理 | 模型供应商被熔断、近 24 小时调用失败偏多、AI 复核任务积压 |

告警接收地址通过 `ALERT_WEBHOOK_URL` 注入（Alertmanager 配置中的占位符在容器启动时替换）。

日志：后端在 `LOG_FILE` 输出 JSON 结构化日志（含请求 ID、状态码、耗时），容器日志驱动为
`json-file` 并配置了大小轮转；如需集中采集，可将驱动替换为 `fluentd`/`gelf` 接入 ELK 或 Loki。

### 7. AI 调用治理与人工复核

**调用韧性**（`services/llm_resilience.py`）

- 超时、网络异常、限流不再把 500 抛给前端，而是返回结构化失败结果，由业务层按既有逻辑降级
- 408/409/425/429/5xx 按指数退避自动重试；4xx 参数类错误快速失败
- 按供应商（`provider:base_url`）维度熔断：连续失败达阈值后直接拒绝，冷却后放行一次试探

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_TIMEOUT_SECONDS` | 60 | 文本模型调用超时 |
| `LLM_VISION_TIMEOUT_SECONDS` | 90 | 视觉模型调用超时 |
| `LLM_MAX_RETRIES` | 2 | 可重试错误的重试次数 |
| `LLM_RETRY_BASE_DELAY` | 0.5 | 退避基数（秒），第 n 次等待 `base * 2^n` |
| `LLM_BREAKER_FAILURE_THRESHOLD` | 5 | 熔断触发所需连续失败次数 |
| `LLM_BREAKER_RESET_SECONDS` | 60 | 熔断后的冷却时间 |

**用量与成本**（`services/llm_pricing.py`、`services/llm_usage_service.py`）

- 每次调用（成功/失败/被熔断）落一条 `llm_call_logs`，含 token、耗时、重试次数、错误原因
- 成本按单价表折算；未配置单价的模型记为「未计价」，不臆测金额。可通过 `LLM_PRICING_JSON` 覆盖：

```bash
LLM_PRICING_JSON='{"gpt-4o-mini": {"input": 0.00015, "output": 0.0006}}'
```

- 调用归因：`LlmCallContextMiddleware` 从请求令牌解析租户/用户写入上下文，统计可按租户隔离

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/settings/llm-usage?days=30` | admin | 调用量/token/成本汇总（按模型、日期、用途） |
| `GET /api/settings/llm-calls?limit=50&status=failed` | admin | 最近调用明细，用于排障与超额核查 |
| `GET /api/settings/llm-governance` | admin | 当前生效的超时/重试/熔断参数与熔断器状态 |

**人工复核**（`services/ai_review_service.py`）

AI 巡检结论在「生成工单」前增加人工闸门，避免本地兜底的假结果自动流入处置流程：

- 触发条件：置信度低（云端模型未生效或调用失败）、置信度中（仅单一模态由云端模型产出）、
  或风险等级为高风险/严重风险
- 触发后：巡检记录照常落库作为证据，**不自动生成工单**，改为落一条 `ai_review_tasks` 待复核任务
- 复核通过才生成工单（`source=AI复核`，状态「待受理」）；驳回仅留痕

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/ai-review/tasks?status=pending` | 登录用户 | 待复核队列（按租户隔离） |
| `GET /api/ai-review/summary` | 登录用户 | 待复核/已通过/已驳回计数 |
| `POST /api/ai-review/tasks/{id}/approve` | `workorders:create` | 复核通过并生成工单；重复处理返回 409 |
| `POST /api/ai-review/tasks/{id}/reject` | `workorders:update` | 复核驳回，不生成工单 |

### 8. 已知限制

- 表结构已由 Alembic 版本化（见「数据库结构迁移」）；存量库 `stamp` 到基线的前提是
  「其结构与当时的模型等价」，若实际有偏差需补一条迁移对齐
- **多实例部署**已支持单主机多副本（见「多实例部署与水平扩展」）；跨主机部署需先解决
  `RUNTIME_DB_PATH` 指向的裸 SQLite 存储（巡检档案、工单闭环等）以及启用对象存储
- 「值班人员」没有人员主数据表，是按排班推导出来的只读视图（见「值班室」一节）

## CI/CD 流水线（GitHub Actions）

一条工作流 `.github/workflows/ci-cd.yml` 覆盖「校验 → 镜像可构建 → 发布 → 回滚」，不再依赖纯人工执行脚本。

| 触发 | 行为 |
| --- | --- |
| push / pull_request | 后端全量 pytest、结构一致性（模型与 Alembic 迁移必须一致）、前端构建、移动端 `flutter analyze --fatal-infos` + `flutter test`、生产镜像可构建 |
| pull_request / 手动 action=ci | 额外跑前端 E2E（Playwright 自动拉起后端与前端）与移动端 release APK 构建（产物上传为 `mobile-apk`） |
| push tag `v*` | 同「校验」全部作业（发布产物由部署主机上的 `scripts/release.sh` 生成，不进镜像仓库） |
| 手动 `action=deploy` | SSH 到部署主机：`git fetch --tags` → `checkout <tag>` → `./scripts/release.sh <tag>` |
| 手动 `action=rollback` | SSH 到部署主机：`./scripts/rollback.sh [tag]`（留空即回上一版本） |

发布任务需要在仓库里配置 Secrets：`DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_SSH_KEY`、`DEPLOY_PATH`
（部署主机上本仓库的绝对路径，该主机需已装 git 与 docker）。缺任一项会在守卫步骤直接失败并提示，
不会执行一半。

设计取舍：

- **镜像在部署主机上构建**，与既有 `scripts/release.sh` 流程一致（备份 → 构建 → 迁移 → 切换 → 健康检查 → 失败自动回滚），
  CI 只做「能不能构建」的校验，避免引入镜像仓库凭据与拉流权限
- E2E 需要同时具备后端依赖与浏览器，耗时较长，因此只在 PR 与手动触发时跑
- 移动端 `analyze + test` 每次 push 都跑；APK 构建较慢，与 E2E 同一策略，只在 PR 与手动触发时跑
- 前端依赖统一用 `yarn --frozen-lockfile`（`package.json` 的 `packageManager` 字段即为 yarn），锁文件不会被 CI 改写

本地复现同一套校验：

```bash
cd backend && python -m pytest tests/ -q
cd frontend && yarn install --frozen-lockfile --ignore-engines && npm run build
cd mobile_app && flutter pub get && flutter analyze --fatal-infos && flutter test
docker build -t fire-ai-agent-backend:local .
```

## 告警外部通知通道（邮件 / 企业微信 / 钉钉 / Webhook）

站内通知（WebSocket 实时推送 + 顶部铃铛 + 通知中心）只对「正在看系统的人」有效。
本功能把告警推到外部通道，让值班人员不在电脑前也能收到：

```
告警产生 / 升级（alert_lifecycle_service.ingest_alert）
    → 按「通道启用 + 级别阈值 + 告警类型」匹配通道
    → 写一条 notification_deliveries 台账 + 投递后台任务
    → worker 执行发送 → 成功/失败落台账，失败按次数重试
```

### 1. 支持的通道与字段

| 类型 | 关键字段 | 说明 |
| --- | --- | --- |
| 通用 Webhook | `url`、`secret`（可选） | JSON POST；配置 `secret` 后附 `X-Signature: sha256=<HMAC-SHA256>` |
| 企业微信群机器人 | `url` | 群机器人 Webhook 地址（含 key，按密钥加密落库） |
| 钉钉群机器人 | `url`、`secret`（安全设置=加签时） | 加签参数（`timestamp`/`sign`）由后端计算 |
| 邮件 | `smtp_host`、`smtp_port`、`smtp_user`、`password`、`sender`、`recipients`、`use_ssl` | 465 走 SSL，587 走 STARTTLS；口令加密落库 |

### 2. 匹配规则

- 通道 `enabled=false` 不参与匹配
- 告警级别需 **≥** 通道的 `min_severity`（low < medium < high < critical，默认 high）
- 通道配置了 `alert_types` 时只推这些类型；留空表示不限
- **同一告警在同一通道上只发一次**（`(alert_code, channel_id)` 唯一约束）；
  告警升级时若上次发送失败，允许复用该记录重发，避免「升级了却没人收到」

### 3. 密钥处理

群机器人 Webhook 地址与 SMTP 口令用 `video_credential_cipher` 对称加密落库，
接口只回 `******` 与「是否已配置」；更新通道时密钥字段留空或传掩码表示**保持原值**，
不需要为了改个名字重新粘贴密钥。

### 4. 接口（全部要求 admin）

| 接口 | 说明 |
| --- | --- |
| `GET /api/settings/notification-channels` | 通道列表 + 表单元数据（类型/字段/可选级别）+ 总开关状态 |
| `POST /api/settings/notification-channels` | 新增通道 |
| `PUT /api/settings/notification-channels/{id}` | 更新通道（密钥留空=不改） |
| `POST /api/settings/notification-channels/{id}/toggle` | 启用 / 停用 |
| `POST /api/settings/notification-channels/{id}/test` | 立即发一条测试消息，验证配置是否真的可达 |
| `GET /api/settings/notification-deliveries?channel_id=&alert_code=&limit=` | 投递台账（排查「告警产生了但没收到通知」） |
| `DELETE /api/settings/notification-channels/{id}` | 删除通道（投递台账保留） |

页面入口：`消息中心（/notifications）→ 通知设置`。

### 5. 配置项

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `ALERT_NOTIFY_ENABLED` | true | 总开关；关掉后不再投递（已入队的记录仍会发送） |
| `ALERT_NOTIFY_TIMEOUT_SECONDS` | 10 | 单次发送超时 |
| `ALERT_NOTIFY_MAX_ATTEMPTS` | 3 | 失败重试次数，由后台任务队列执行，超过后记为最终失败 |

### 6. 失败怎么排查

1. 通道列表的「最近发送」列会显示最近一次成功时间与最近一次错误
2. 点通道的「记录」查投递台账：状态（待发送/成功/失败）、尝试次数、对端返回摘要或错误原因
3. 通道的「测试」按钮可绕过告警链路直接验证配置（例如机器人被移出群、token 失效都会立刻报出来）
4. 任务队列页（`/tasks`）里任务类型为 `alert_notify` 的记录可看到重试与死信情况

### 7. 已知限制

- **短信通道未实现**，需要短信服务商凭据，按需再接（现有通道表结构可直接扩展新类型）
- 通知失败不会影响告警入库：`enqueue_alert_notifications` 吞掉异常并记日志，告警本身已在库里
- 站内通知的已读状态是全局一份文件（`backend/data/notification_read.json`），不区分租户与用户，属既有实现

