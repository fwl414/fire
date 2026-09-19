# 整站测试报告（全功能 · 全界面）

- 执行日期：2026-09-18
- 执行方式：后端 pytest 全量 + 前端 Playwright 全量 E2E + 逐页界面跑测与截图
- 被测对象：`fire_ai_agent_v1 - 副本`（FastAPI 后端 + Vue 3 前端）
- 结论：**通过**。59 个路由全部可达、无 JS 报错；前端 41 条 E2E 全绿；后端 538 条全绿（连续 30 轮无失败）。过程中发现并修复 3 个真实问题。

---

## 1. 环境与执行命令

| 项 | 值 |
| --- | --- |
| 后端 | FastAPI + SQLAlchemy + SQLite（主库）+ 独立运行时库 `fire_agent_runtime.db` |
| 前端 | Vue 3 + Element Plus + Vite 5 |
| E2E | Playwright（Chromium 129.0.6668.29 / build v1134，本机已安装） |
| 测试账号 | `admin` / `123456`（DEMO_MODE 演示数据） |

E2E 会自动拉起独立后端（`127.0.0.1:8010`，`e2e_test.db`，`DEMO_MODE=true`）与前端（`127.0.0.1:5273`），不影响本机正在运行的实例。

```powershell
# 后端全量单测
# tests/conftest.py 已把主库与运行时库重定向到临时目录（见 3.1），
# 因此测试不会读写本地开发库，也不受本地开发服务进程影响
cd "fire_ai_agent\fire_ai_agent_v1 - 副本\backend"
python -m pytest tests/ -q --tb=line

# 前端生产构建
cd "fire_ai_agent\fire_ai_agent_v1 - 副本\frontend"
npm run build

# 前端全量 E2E
# 注意：本机 node_modules/.bin 下没有生成 playwright 软链（npm 安装曾被中断），
# 所以 `npx playwright test` / `npm run test:e2e` 会报 "playwright 不是内部或外部命令"，
# 直接指定 CLI 入口即可：
cd "fire_ai_agent\fire_ai_agent_v1 - 副本\frontend"
node node_modules/@playwright/test/cli.js test --reporter=list
```

---

## 2. 结果汇总

| 测试项 | 结果 | 明细 |
| --- | --- | --- |
| 前端生产构建 | 通过 | 无编译错误 |
| 后端全量 pytest | **538 通过 / 0 失败** | 538 项 + 28 subtests，30s（隔离测试库后连续 18 轮全绿） |
| 前端全量 E2E | 41 通过 / 0 失败 | 18 个 spec，3.2m（修复后复跑） |
| 路由可达性 | 59/59 通过 | 无重定向、无 `pageerror`、无 console error |
| 界面逐页截图 | 76 张 | 覆盖全部菜单模块、参数页、弹窗与异常态 |
| 关键交互断言 | 通过 | 登录校验、错误提示、弹窗居中 |
| 智能巡检完整流程 | 通过 | 8 步分析链路 + 结果 8 页签 + 归档 + 报表打印 + 报告验真 |

---

## 3. 后端单测明细

`tests/` 共 37 个测试文件。与本轮改动相关的用例：

| 用例 | 条数 | 覆盖内容 |
| --- | --- | --- |
| `test_cad_parse.py::TestPinyinLayerCodes` | 3 | 缩写码分词与去序号后缀；消防图层/块名命中；`PT` 不误命中 `POINT` 等无关名 |
| `test_cad_parse.py`（补充） | 1 | 非设备图层上的小圆不再被误判 |
| `test_dxf_split_sheets.py` | 4 类 / 7 条 | 矩形识别与拒绝、图框查找去重、实体唯一归属、标题与文件名清洗、导出仅含本图实体 |
| `test_imported_drawings.py` | 5 | 空楼层导入记录来源；已有设备楼层不覆盖来源；老数据按文件名回填；删除联动清理楼层/设备/文件；删除不存在返回 404 |
| `test_upload_download.py`（修正） | — | `tearDownClass` 改为按 id 精确删除，避免误删真实租户的上传记录与目录 |
| `test_report_archive.py` 等档案类 | 全绿 | **本轮修复的归档写入缺陷已由此覆盖并验证** |

### 3.1 竞态问题：根因与修复（已解决）

**失败表象**（修复前在不同轮次随机出现）：

```
FAILED tests/test_task_queue.py::TestTaskApi::test_report_async_export_enqueues_task
AssertionError: 'running' != 'pending'

FAILED tests/test_task_queue.py::TestTaskApi::test_metrics_expose_queue_state
AssertionError: 'fire_ai_background_tasks{status="pending"} 1' not found
```

**定位过程**：这两条用例都是「入队后立刻断言任务为 pending」。单独跑必过、全量跑随机挂，说明有别的进程在动任务。写探针复现后拿到关键证据：

```
T+0s  task_status = pending   worker_task=None  stats={running:false, processed:0, failed:0}
T+1s  task_status = success   worker_task=None  stats={running:false, processed:0, failed:0}
```

测试进程内**没有**任何 worker 在跑（`_worker_task=None`、计数器全 0），任务却在 1 秒内从 `pending` 直接变成 `success`。随后在生产进程列表里找到元凶：

```
PID 35360  python start_server.py        ← 本地开发服务一直在跑
```

**根因**：`backend/.env` 里 `DATABASE_URL=sqlite:///./fire_ai_agent.db`，本地开发服务与 pytest **共用同一个库文件**。开发服务进程内常驻后台任务 worker（每 2 秒轮询一次队列），于是测试刚 `enqueue` 的任务会在断言之前被开发服务的 worker 抢走执行掉。只要两个进程共用一个库，任何「入队后断言状态」的用例都不可能稳定。

同一个共享库还带来过更严重的副作用：测试的清理逻辑会删掉开发库里的真实上传记录与文件（见 `test_upload_download.py` 的修正记录）。

**修复**：新增 `backend/tests/conftest.py`，在任何业务模块被导入之前把测试会话的库重定向到临时目录，让测试进程成为这套库的唯一使用者：

```python
_TMP_ROOT = Path(tempfile.gettempdir()) / "fire_ai_agent_pytest"
shutil.rmtree(_TMP_ROOT, ignore_errors=True)      # 每轮从空库开始
_TMP_ROOT.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_ROOT / 'test_suite.db').as_posix()}"
os.environ["RUNTIME_DB_PATH"] = str(_TMP_ROOT / "test_suite_runtime.db")
os.environ.setdefault("ENV", "development")
```

说明：

- 只改测试基础设施，**未改动任何生产代码**。生产侧 `claim_next()` 本身是并发安全的（用 `UPDATE ... WHERE status='pending'` 的影响行数判定归属，多 worker/多实例不会重复执行），不存在需要修的竞态。
- 刻意**不**设置 `TASK_WORKER_ENABLED=false`：`TestWorkerLifecycle` 需要自己 `start_worker()`，关掉会让它失去意义。
- 附带收益：测试不再读写开发库，`fire_ai_agent.db` 与开发服务的运行时库不再被测试污染；全套耗时也从 161s 降到 30s（空库索引更小）。

**验证**：修复后连续跑 18 轮全量 pytest 与 12 轮 `tests/test_task_queue.py`，**共 30 轮全部通过**，无一次失败。

---

## 4. 前端 E2E 明细（41 条全部通过）

| spec | 条数 | 用例 |
| --- | --- | --- |
| `auth.spec.js` | 4 | 未登录跳转登录页；密码错误停留且不写令牌；正确登录进入首页；退出清理令牌回登录页 |
| `pages.spec.js` | 2 | 核心页面可打开且无失败接口请求；楼层平面图走受控地址（不再走 `/static`） |
| `data-screen.spec.js` | 8 | 真实统计无假数据；接口失败提示；加载遮罩；空数据占位；列表下钻；3D 场景悬停与下钻；视频抓拍真图；抓拍失败降级 |
| `api-closed-loop.spec.js` | 3 | 告警→工单→整改→复查闭环；报表生成落盘与受控下载；上传内容与报表不得匿名下载 |
| `cad-upload.spec.js` | 1 | 上传 DXF 能解析出构件，DWG 被明确挡下并提示转换 |
| `task-queue.spec.js` | 3 | 批量巡检入队并执行完成；报表异步导出并产出可下载产物；任务中心暴露 worker 状态 |
| `duty-room.spec.js` | 2 | 交接班与值班记录落库且列字段一致；新增排班落库并出现在对应周 |
| `fire-training.spec.js` | 2 | 四个页签接真实接口；新建/编辑/删除培训计划并导出档案 |
| `electrical-water.spec.js` | 2 | 电气火灾三个页签接真实遥测；水系统消火栓接真实压力、未接入项如实显示 |
| `knowledge-graph.spec.js` | 2 | 业务实体图来自接口并可下钻；学习图谱节点与关系渲染 |
| `video-platform.spec.js` | 2 | 通道台账→探测→抓拍→页面轮询；告警联动与录像回放接真实数据 |
| `realtime-push.spec.js` | 3 | 无效令牌被拒（4401）；按令牌身份回话；新告警推送后大屏立即刷新 |
| `audit-log.spec.js` | 2 | 审计日志展示真实记录并可校验完整性、导出；登录日志展示真实登录记录 |
| `system-monitor.spec.js` | 1 | 页面数字来自真实采集（非随机数或写死演示数据） |
| `risk-prediction.spec.js` | 1 | 展示真实模型状态，未训练不给分数 |
| `device-diagnose.spec.js` | 1 | 诊断弹窗展示真实内容，权重标明来源 |
| `daily-brief.spec.js` | 1 | 简报数字等于接口真实统计，重点区域由数据推导 |
| `mobile-collab.spec.js` | 1 | 首页数字来自接口，可领取工单并现场上报 |

---

## 5. 路由可达性核查

对 59 条非登录路由逐条访问，记录最终地址、页面标题与首屏文本长度，并监听 `pageerror` / `console.error`：

- **重定向：0 条**（无权限回落、无空白兜底跳转）
- **JS 报错：0 条**（`PAGE_ERRORS {}`）
- **标题与内容：59 条全部与菜单语义一致**

---

## 6. 全界面逐页跑测与截图

以下为按左侧菜单模块组织的实测截图。每张图均为登录 `admin` 后在真实数据下渲染。

### 6.1 登录与入口

登录页加载正常；空表单提交触发必填校验；密码错误给出明确提示并停留登录页；退出登录弹窗居中、层级与配色正常。

![登录页](assets/test-report/01-login.png)
![空表单必填校验](assets/test-report/00-a-login-required.png)
![密码错误提示](assets/test-report/00-b-login-error.png)
![退出登录弹窗](assets/test-report/00-c-logout-dialog.png)

无权限提示页（`/no-access`）：

![无权限页](assets/test-report/60-no-access.png)

### 6.2 数据大屏

深色驾驶舱：顶部指标、设备运行概览、告警统计与 7 日趋势、3D GIS 场景（建筑可悬停下钻）、实时告警、待办事项、消防水源/电气火灾/值班信息卡。顶部 `ElMessage` 提示居中显示，验证 Element Plus 基础样式已生效。

![数据大屏](assets/test-report/02-dashboard.png)

### 6.3 设备监测

| 页面 | 截图 |
| --- | --- |
| 设备总览（12 台设备、6 类统计、筛选与列表） | ![设备管理](assets/test-report/03-devices.png) |
| 物联网设备接入 | ![物联网设备](assets/test-report/04-iot-device.png) |
| 消防水源监测 | ![消防水源](assets/test-report/05-water-monitor.png) |
| 电气火灾监测 | ![电气火灾](assets/test-report/06-electrical-fire.png) |
| 设备数据表（实时数据） | ![设备数据](assets/test-report/07-device-data.png) |

### 6.4 报警中心

| 页面 | 截图 |
| --- | --- |
| 设备告警中心（统计卡、状态页签、批量确认/派单、列表） | ![告警中心](assets/test-report/08-alert-center.png) |
| 视频监控 | ![视频监控](assets/test-report/09-video-monitor.png) |
| 故障闭环（报警记录） | ![故障闭环](assets/test-report/10-faults.png) |

### 6.5 消防控制室

值班管理：交接班、值班记录、排班表。

![消防控制室](assets/test-report/11-duty-room.png)

### 6.6 重点单位

消防重点单位管理：单位台账、风险分级、监督检查页签。

![重点单位](assets/test-report/12-key-unit-management.png)

### 6.7 隐患治理

| 页面 | 截图 |
| --- | --- |
| 隐患排查治理（风险分级管控 + 隐患台账） | ![隐患排查](assets/test-report/13-hazard-management.png) |
| 整改工单 | ![整改工单](assets/test-report/14-workorders.png) |

### 6.8 网格化管理

网格区域、网格员、隐患上报页签。

![网格化管理](assets/test-report/15-grid-management.png)

### 6.9 巡检管理（含智能辅助巡检完整流程）

**① 巡检计划 / 批量巡检任务**

![批量巡检任务](assets/test-report/16-batch-inspection.png)

**② 巡检管理首页**：统计卡（12 计划 / 8 已完成 / 23 发现隐患 / 7 待整改）+ 巡检计划列表。

![巡检管理](assets/test-report/17-inspection.png)

**③ 智能辅助巡检 —— 填写现场描述**

![巡检输入](assets/test-report/17-b-inspection-input.png)

**④ 点击「开始分析」后的动态分析进度**：任务理解 → 图像识别 → 风险提取 → 知识库检索 → 规划校验 → 风险评分 → 整改建议 → 报告生成，8 步全部「已完成」，并给出总体风险等级/评分/发现隐患/巡检记录同步数。

![分析结果](assets/test-report/17-d-inspection-result.png)

**⑤ 结果工作台 8 个页签**

| 页签 | 内容 | 截图 |
| --- | --- | --- |
| 风险总览 | 风险结论、判定理由、评分明细、优先整改项 | ![风险总览](assets/test-report/17-d-inspection-result.png) |
| 隐患识别 | 4 条隐患（名称/等级/分类/识别依据/可能后果/整改建议） | ![隐患识别](assets/test-report/17-e-inspection-hazards.png) |
| 知识库引用依据 | RAG 命中的知识条目与匹配度 | ![知识库引用](assets/test-report/17-f-inspection-rag.png) |
| 分析决策链 | Agent 推理链路 | ![分析决策链](assets/test-report/17-g-inspection-chain.png) |
| 工具中心 | 本次调用的工具与参数 | ![工具中心](assets/test-report/17-h-inspection-tools.png) |
| 整改工单 | 自动生成的派单与闭环动作 | ![整改工单](assets/test-report/17-i-inspection-orders.png) |
| 巡检报告 | 结构化报告正文 | ![巡检报告](assets/test-report/17-j-inspection-report.png) |
| 技术细节 | 分析追踪、原始 JSON | ![技术细节](assets/test-report/17-k-inspection-tech.png) |

**⑥ 生成/同步记录**：点击后写入巡检档案（图示为修复归档写入缺陷后的成功状态）。

![同步记录](assets/test-report/17-l-inspection-saved.png)

**⑦ 巡检报告与档案**：统计卡（1 档案 / 1 报告 / 1 高风险 / 闭环率）+ 档案列表（报告编号、地点、风险等级、评分、详情/派单/验真）。

![巡检档案](assets/test-report/18-records.png)

### 6.10 维保管理

| 页面 | 截图 |
| --- | --- |
| 维保管理总览 | ![维保管理](assets/test-report/19-maintenance.png) |
| 消防设施检测管理 | ![设施检测](assets/test-report/20-facility-inspection.png) |

### 6.11 重点部位

重点部位管理：部位台账与风险分级。

![重点部位](assets/test-report/21-key-areas.png)

### 6.12 应急指挥

| 页面 | 截图 |
| --- | --- |
| 应急指挥（预案/疏散路线/应急资源） | ![应急指挥](assets/test-report/22-emergency-command.png) |
| 微型消防站 | ![微型消防站](assets/test-report/23-mini-fire-station.png) |

### 6.13 建筑管理

| 页面 | 截图 |
| --- | --- |
| 建筑火灾风险预测（未训练时不给分数） | ![建筑风险](assets/test-report/24-building-risk.png) |
| 楼层平面图管理 | ![楼层平面图](assets/test-report/25-floor-plan.png) |
| 建筑详情：楼层导航、3D 预览、本层设备、设备统计 | ![建筑详情](assets/test-report/26-building-detail.png) |
| 历史导入图纸弹窗（含删除入口） | ![历史导入](assets/test-report/26-b-building-detail-imported.png) |
| 上传 CAD 图纸弹窗（DXF/DWG 类型校验说明） | ![上传CAD](assets/test-report/26-c-building-detail-upload.png) |

### 6.14 消防评估

![消防安全评估](assets/test-report/26-fire-assessment.png)

### 6.15 事故管理

![火灾事故管理](assets/test-report/27-fire-accident.png)

### 6.16 数据统计与报表闭环

| 页面 | 截图 |
| --- | --- |
| 统计报表中心 | ![统计报表](assets/test-report/28-report-center.png) |
| 巡检报告打印页（完整七节：基本信息/现场图片/综合风险/隐患明细/知识库依据/工单闭环/验真说明 + 二维码） | ![报告打印](assets/test-report/61-report-print.png) |
| 报告验真页（验真通过、档案编号、风险等级、闭环状态、报告摘要哈希） | ![报告验真](assets/test-report/62-report-verify.png) |

### 6.17 消防档案

![消防档案](assets/test-report/29-fire-archives.png)

### 6.18 消防培训

四个页签（培训课程/培训计划/考试考核/培训档案）均接真实接口。

![消防培训](assets/test-report/30-fire-training.png)

### 6.19 消防宣传

![消防宣传](assets/test-report/31-fire-promotion.png)

### 6.20 移动端协同

![移动端协同](assets/test-report/32-mobile-inspection.png)

### 6.21 智能分析

| 页面 | 截图 |
| --- | --- |
| 每日安全简报 | ![每日简报](assets/test-report/33-daily-brief.png) |
| 智能问答 | ![智能问答](assets/test-report/34-qa.png) |
| 多模态风险分析 | ![多模态分析](assets/test-report/35-multimodal.png) |
| 分析能力展示 | ![分析能力](assets/test-report/36-agent-lab.png) |
| 分析日志 | ![分析日志](assets/test-report/37-decision-logs.png) |

### 6.22 知识库

| 页面 | 截图 |
| --- | --- |
| 消防知识库（全文与条目） | ![知识库](assets/test-report/38-knowledge.png) |
| 知识图谱（业务实体图与学习图谱） | ![知识图谱](assets/test-report/39-knowledge-graph.png) |
| 消防学习 | ![消防学习](assets/test-report/40-learning.png) |
| 刷题中心 | ![刷题中心](assets/test-report/53-learning-app.png) |

### 6.23 系统管理

| 页面 | 截图 |
| --- | --- |
| 组织架构管理 | ![组织架构](assets/test-report/41-org-management.png) |
| 用户管理 | ![用户管理](assets/test-report/42-user-management.png) |
| 角色与权限管理 | ![角色权限](assets/test-report/43-role-management.png) |
| 数据字典管理 | ![数据字典](assets/test-report/44-dict-management.png) |
| 系统公告管理 | ![系统公告](assets/test-report/45-system-announcement.png) |
| 操作日志审计（含完整性校验） | ![操作日志](assets/test-report/46-operation-logs.png) |
| 系统监控中心 | ![系统监控](assets/test-report/47-system-monitor.png) |
| 系统设置 | ![系统设置](assets/test-report/48-settings.png) |

### 6.24 其他入口

| 页面 | 截图 |
| --- | --- |
| 系统通知中心 | ![通知中心](assets/test-report/49-notifications.png) |
| 消息通知中心 | ![消息中心](assets/test-report/50-message-center.png) |
| 个人中心 | ![个人中心](assets/test-report/51-profile.png) |
| GIS 地图总览 | ![GIS地图](assets/test-report/52-gis-map.png) |
| 实验评估 | ![实验评估](assets/test-report/54-evaluation.png) |
| 系统状态 | ![系统状态](assets/test-report/55-system-health.png) |
| 硬件事件中心 | ![硬件事件](assets/test-report/56-hardware.png) |
| 遥测数据 | ![遥测数据](assets/test-report/57-telemetry.png) |
| 项目展示（隐藏路由） | ![项目展示](assets/test-report/58-defense.png) |
| 系统能力说明（隐藏路由） | ![系统能力](assets/test-report/59-competition.png) |

---

## 7. 本轮发现并修复的缺陷

### 7.1 智能辅助巡检：点「开始分析」后整页空白（前端）

- **现象**：在「智能辅助巡检」页填写描述后点击开始分析，分析完成提示出现，但整个 tab 内容区（输入表单 + 分析进度 + 结果工作台）全部消失，页面只剩侧边栏与页签条。
- **定位**：浏览器实测 `.tab-content` 元素数为 0、`#app` 文本仅 276 字符，说明三个顶层分支全部未命中。`runAgent()` 中写的是 `activeTab.value = "overview"`，而 `activeTab` 是外层「巡检计划/隐患台账/智能辅助巡检」的开关，`"overview"` 是结果区 `el-tabs`（`resultTab`）的页签名。
- **修复**：改为 `resultTab.value = "overview"`（`frontend/src/views/Inspection.vue`）。
- **验证**：修复后完整跑通分析流程并截取结果页与 8 个结果页签（见 6.9）。

### 7.2 巡检档案无法归档：点击「生成/同步记录」报服务器错误（后端）

- **现象**：`/records` 巡检档案恒为 0 条；点击「生成/同步记录」弹出「服务器内部错误：19 values for 18 columns」；连带报告打印页、报告验真页无数据可展示。
- **定位**：`save_inspection_record()` 的 `INSERT` 列出 18 个字段名、18 个值，但 `VALUES` 里写了 **19 个 `?` 占位符**，SQLite 直接拒绝执行，档案永远不会落库。
- **修复**：把占位符数量改为 18（`backend/services/record_persistence_service.py`）。
- **验证**：修复后同一条巡检数据成功归档 —— 巡检档案出现 1 条记录，报告编号 `RPT-20260918034935-E5C8`，报告打印页完整渲染七节内容，报告验真页显示「验真通过」（见 6.16）。

### 7.3 后端测试竞态：测试库与本地开发服务共用同一个 SQLite 文件

- **现象**：`tests/test_task_queue.py` 中两条「入队后断言 pending」的用例在不同轮次随机失败，报 `'running' != 'pending'` / `'...pending"} 1' not found`；单跑必过。
- **定位**：探针显示测试进程内没有任何 worker 在运行（`_worker_task=None`、计数器全 0），任务却在 1 秒内从 `pending` 变 `success`；进程列表里找到一直在跑的本地开发服务 `python start_server.py`（PID 35360），它与 pytest 共用 `backend/fire_ai_agent.db`，其常驻 worker 每 2 秒轮询队列，把测试刚入队的任务抢走执行。
- **修复**：新增 `backend/tests/conftest.py`，在业务模块导入前把 `DATABASE_URL` 与 `RUNTIME_DB_PATH` 重定向到临时目录，测试会话独占一套库（详见 3.1）。未改动生产代码——`claim_next()` 本身已是并发安全的。
- **验证**：连续 18 轮全量 + 12 轮队列文件，30 轮全部通过；全套耗时 161s → 30s。

---

## 8. 遗留问题

| 级别 | 问题 | 说明与建议 |
| --- | --- | --- |
| 中 | 数据大屏右列「实时告警」列表与「待办事项」面板存在视觉重叠 | 已用「启用/禁用项目全局样式」A/B 对比确认前后一致，属既有布局问题，建议单独调整 `DataScreen.vue` 右列高度分配 |
| 中 | 告警中心列表区横向溢出，「处理」列被「操作」列遮挡 | 同样经 A/B 确认是既有问题，建议调整 `AlertCenter.vue` 表格列宽或将操作列固定 |
| 低 | 未纳入自动化的检查项 | 移动端 App 原生工程、真实大模型外呼（当前 DEMO_MODE 走本地兜底）仍需人工验证 |
| 低 | `node_modules/.bin` 缺少 playwright 软链 | 因此 `npx playwright test` 与 `npm run test:e2e` 会报「不是内部或外部命令」。重跑一次 `npm install` 生成软链即可；当前请用第 1 节的 `node node_modules/@playwright/test/cli.js test` |
| 低 | 档案写入缺陷的回归用例 | 已由 `test_report_archive.py` 覆盖通过；建议再补一条「占位符/字段数一致」的守护用例，避免同类问题复发 |

---

## 9. 结论

- **功能面**：59 个路由全部可达且渲染正常，无重定向、无 JS 报错；核心业务闭环（告警→工单→整改→复查、巡检→归档→报表→验真、CAD→解析→楼层→设备点位）端到端可用。
- **自动化**：前端 41 条 E2E 全绿；后端 538 条全绿且连续 30 轮无失败（含 18 轮全量）。
- **视觉面**：全局样式正式引入后无副作用；弹窗居中与可读性、登录错误提示等上一轮反馈项均已修复并断言验证。
- **本轮净收益**：修复 3 个真实问题 —— ①巡检分析后页面空白；②巡检档案无法归档；③后端测试竞态（测试库与本地开发服务共用同一 SQLite 文件）。前两个此前会让对应功能完全不可用，第三个让后端全量测试长期存在随机失败。

---

## 10. 开发库残留数据清理（收尾）

测试期间（本次会话 03:00–04:30）在开发库里留下了数据，已按下表清理。清理前已整库备份。

| 位置 | 清理内容 | 数量 |
| --- | --- | --- |
| 主库 `fire_ai_agent.db` · `report_artifacts` | 测试窗口内生成的报表产物记录 | 5 条 |
| 主库 `fire_ai_agent.db` · `runtime_locks` | `unit-test-snapshot`（`test_device_pipeline.py` 的锁） | 1 条 |
| 主库 `fire_ai_agent.db` · `users` | `system-metrics-user`（`test_system_metrics.py` 的测试账号） | 1 条 |
| 运行时库 `fire_agent_runtime.db` | 我手工跑的「3号宿舍楼地下二层消火栓区域」巡检档案：`inspection_records` 1 条、`inspection_reports` 1 条、`work_orders` 4 条 | 6 条 |
| `data/reports/tenant_shared/` | 测试生成、开发库无引用的报表 csv | 34 个 |
| `uploads/` | 测试生成、开发库无引用的巡检图片 | 27 个 |

清理后复核：主库报告产物 45 条 / 用户 4 个（均为种子账号）/ 后台任务 0 / 运行时锁 0；运行时库无 09-18 的巡检记录与工单。

**刻意未动**（并说明原因）：

- `operation_logs`：哈希链审计日志，删行会破坏 `seq/prev_hash/hash` 完整性校验，`/api/system/operation-logs/verify` 会报错。
- `login_logs`：审计日志，保留。
- `device_telemetry` / `risk_update_records` / `device_request_nonces` 等：无法可靠区分种子数据与测试残留，且均为业务表数据，不贸然删。
- 历史演示数据（`DEMO-INSPECTION-001~005`、`REC-V12-*`、`v128_*`、内置 RAG 条目等）：是应用自带的演示/种子内容，不是测试残留。
- `e2e_test.db`：E2E 专用库，非开发库，每次运行自行重建。

**防止再次污染**：`tests/conftest.py` 已把 `REPORT_STORAGE_DIR`、`UPLOAD_STORAGE_DIR` 一并重定向到临时目录，并在会话结束时回收本会话新落到共享 `uploads` 目录的巡检图片（`services/agent_service.py` 的图片落盘用的是相对路径，不认该环境变量）。连续两轮全量测试验证：均为 538 通过，且开发目录文件数保持 87 → 87，不再新增。

**备份位置**：`backend/data/_cleanup_backup_20260918_041937/`（含 `fire_ai_agent.db` 与 `fire_agent_runtime.db`），确认无误后可自行删除。

---

## 11. 生产化 P0 缺口补齐（2026-09-19）

上一轮交付的是「开发态可用」；本节记录补齐 4 个生产化 P0 缺口后的实现、配置与验证结果。
AI API Key 由使用方在系统设置里自行配置，不在本轮范围内。

### 11.1 实施项清单

| 项 | 内容 | 关键落点 |
| --- | --- | --- |
| P0-1 HTTPS | nginx 增加 443 + TLS1.2/1.3 + HSTS，80 只做 ACME 校验与 301 跳转 | `nginx.conf`、`docker-compose.yml`、`deploy/certbot/README.md` |
| P0-2 初始数据 | 生产分支补齐「租户 / 系统角色 / 首个管理员」幂等引导 | `backend/services/baseline_seed.py`、`backend/main.py` |
| P0-3 GB 26875 | 消防主机（用户信息传输装置）TCP 接入：帧编解码、身份校验、上行落库与下行时间同步 | `backend/services/gb26875/`、`backend/routers/gb26875.py`、`gb26875_devices` 表 |
| P0-4 GB28181 | 视频接入：最小化 SIP UAS（UDP+TCP）、目录/云台/点播停流、ZLMediaKit 媒体分发、前端国标页签 | `backend/services/gb28181/`、`backend/routers/gb28181.py`、`frontend/src/components/VideoPlayer.vue`、`VideoMonitor.vue` |
| 附带修复 | `floors.source_upload_id` 自基线起就缺迁移，生产全新库会缺列 | 迁移 `d4e5f6a7b8c9` |

数据库结构变更全部走 Alembic（本项目结构唯一来源），本轮新增 3 条迁移：

| 迁移 | 内容 |
| --- | --- |
| `c3d4e5f6a7b8` | 新增 `gb26875_devices` 表 |
| `d4e5f6a7b8c9` | 补 `floors.source_upload_id`（幂等，开发库已补过不会重复加列） |
| `e5f6a7b8c9d0` | `video_channels` 增加 `gb_device_id` / `parent_gb_id` / `manufacturer` / `sip_register_at` |

### 11.2 GB 26875 消防主机接入

协议依据 GB/T 26875.3-2011：启动符 `0x40 0x40`、控制单元（业务流水号 / 协议版本 / 时间标签 / 源地址 / 目的地址 / 应用数据单元长度 / 命令字节）、应用数据单元、校验和（第 3~27 字节与应用数据单元逐字节求和取低 8 位）、结束符 `0x23 0x23`。

- 上行：注册/配置（类型 26，可携带 `USER=x;PWD=y`）→ 校验地址与口令；运行状态/时间（类型 21/8/28）→ 心跳；系统状态/部件状态/操作信息（类型 1/2/4）→ 按状态位生成告警与工单；模拟量（类型 3）→ 写遥测并做阈值判定
- 所有上行统一走 `device_ingest_service.dispatch`，与 HTTP / MQTT 通道共用「落库 → 告警 → 工单」链路
- 下行：确认(3) / 否认(6) / 应答(5) / 控制命令(1，时间同步)
- 未登记的国标地址、已停用设备、口令不匹配的报文一律回「否认」，不落任何业务数据
- 台账未映射到设备档案时按国标地址自动补建 `devices` 记录（火警不能因漏配映射而丢失）

配置项（`backend/.env` / 根 `.env`）：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `GB26875_ENABLED` | false | 置 true 才启动 TCP 接入服务 |
| `GB26875_LISTEN_HOST` / `GB26875_LISTEN_PORT` | 127.0.0.1 / 5016 | 生产容器内为 0.0.0.0:5016，compose 已映射 |
| `GB26875_CENTER_ADDRESS` | 000000000000 | 监控中心自身 12 位国标地址，需与主机侧登记一致 |

接口：`GET /api/gb26875/devices`、`POST /api/gb26875/devices`、`POST|DELETE /api/gb26875/devices/{id}/credentials`、`POST /api/gb26875/devices/{id}/toggle`、`POST /api/gb26875/devices/{id}/sync-time`、`GET /api/gb26875/status`。

### 11.3 GB28181 视频接入

架构：SIP 信令由后端自己实现（文本协议，UDP + TCP 双栈），媒体流交给 ZLMediaKit 收流并转 HLS / HTTP-FLV / WebRTC，前端直接播放流媒体地址 —— 自研 RTP 转发与转码工程量过大且不必要。

- 信令：REGISTER（Digest 认证，401 → 带凭证重注册）、MESSAGE（Catalog / DeviceInfo / DeviceStatus / Alarm / Keepalive）、INVITE + ACK、BYE、OPTIONS
- 台账：复用 `video_channels` 一张表表达「设备 → 通道」树（`platform='gb28181'`，`parent_gb_id` 为空即设备节点），型号复用既有 `device_model` 列
- 点播：`openRtpServer` 取收流端口 → INVITE 携带 SDP（指向 ZLMediaKit）→ 设备回 200 OK → 回 ACK → 返回 HLS/FLV/WebRTC 地址；停流发 BYE 并关流
- 云台：MESSAGE/DeviceControl 下发 PTZCmd（`A5 0F 01 <指令码> <水平> <垂直> <缩放> <校验和>`）；厂商位序不同可直接传 `ptz_cmd` 原始指令码覆盖

配置项：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `GB28181_ENABLED` | false | 置 true 启动 SIP 服务（监听 5060 UDP+TCP） |
| `GB28181_SIP_SERVER_ID` / `GB28181_SIP_DOMAIN` | 34020000002000000001 / 3402000000 | 平台国标编码与域，需与设备侧登记一致 |
| `GB28181_SIP_PASSWORD` | 空 | 设备侧登记的平台口令；留空则不校验 Digest |
| `GB28181_SIP_ADVERTISE_HOST` | 空 | 平台在 Via/Contact 中声明的地址（容器部署填宿主机 IP） |
| `GB28181_MEDIA_API_BASE` | 空 | ZLMediaKit API 地址，如 `http://zlmediakit:80/index/api` |
| `GB28181_MEDIA_SECRET` | 空 | 与 ZLMediaKit `config.ini` 的 `[api]secret` 一致 |
| `GB28181_MEDIA_HTTP_HOST` / `GB28181_MEDIA_HTTP_PORT` | 空 / 8081 | 前端可访问的媒体服务器地址（拼播放 URL） |
| `GB28181_MEDIA_RTP_HOST` | 空 | **设备**可推流到的地址（必须填设备能访问的 IP，不能填容器名） |
| `GB28181_RTP_PORT_RANGE` | 10000,10500 | 收流端口段，需与 compose 端口映射一致 |

接口：`GET /api/gb28181/devices`、`GET /api/gb28181/devices/{id}/channels`、`POST /api/gb28181/devices/{id}/refresh-catalog`、`POST /api/gb28181/channels/{id}/play|stop|ptz`、`GET /api/gb28181/channels/{id}/stream-info`、`GET /api/gb28181/status`。

前端：`视频监控` 页新增「国标视频」页签 —— 左侧设备/通道列表（含在线状态与目录刷新），右侧 2×2 实时画面（`VideoPlayer.vue` 按地址后缀自动选 HLS / HTTP-FLV，两个库按需动态加载）、悬浮云台方向键与关闭按钮。

### 11.4 HTTPS 证书放置路径

| 容器内路径 | 宿主机路径 | 说明 |
| --- | --- | --- |
| `/etc/nginx/certs/fullchain.pem` | `./certs/fullchain.pem` | 站点证书 + 中间 CA |
| `/etc/nginx/certs/privkey.pem` | `./certs/privkey.pem` | 私钥（无口令 PEM） |
| `/var/www/certbot` | `./certs/www` | Let's Encrypt http-01 校验目录 |

两个证书文件缺任意一个，`frontend` 容器都不会启动。获取与续期流程（Let's Encrypt webroot 与商业 CA 两种路径）见 `deploy/certbot/README.md`；`certs/` 已加入 `.gitignore`，私钥不入库。

### 11.5 ZLMediaKit 部署位置与端口

容器 `zlmediakit`（镜像默认 `zlmediakit/zlmediakit:master`，可用 `ZLMEDIAKIT_IMAGE` 覆盖），与 `backend` 同处 `fire_ai_network`：

| 端口 | 用途 |
| --- | --- |
| 554 | RTSP |
| 1935 | RTMP |
| 8081 → 容器 80 | HTTP API + HLS/FLV（前端播放地址走这里） |
| 8000/udp | WebRTC |
| 10000-10500/udp | GB28181 RTP 收流（与 `GB28181_RTP_PORT_RANGE` 一致） |

信令端口 5060（UDP+TCP）在 `backend` 容器，不在 ZLMediaKit。`[api]secret` 需与后端 `GB28181_MEDIA_SECRET` 一致；若镜像不支持用环境变量覆盖配置，请在挂载的 `config.ini` 中修改。

### 11.6 真实设备联调流程（待设备到位）

1. **消防主机（GB 26875）**：`GB26875_ENABLED=true` → `POST /api/gb26875/devices` 登记主机国标地址（需要口令则调用 credentials 签发并在主机侧录入）→ 主机指向服务器 5016 端口 → `GET /api/gb26875/status` 看 `connections`/`received`，`GET /health` 看 `gb26875` 段
2. **摄像机 / NVR（GB28181）**：`GB28181_ENABLED=true` 并部署 ZLMediaKit → 设备侧填写平台 IP、SIP 端口 5060、平台编码、口令 → `GET /api/gb28181/status` 出现已注册设备 → 「国标视频」页签点「刷新目录」 → 选择通道「播放」
3. 记录项：设备厂商/型号/固件、协议扩展点（私有命令字、信息体长度差异）、PTZ 位序、RTP 推流是否可达

以上三步需要真实设备，本轮未执行。

### 11.7 本轮验证结果

| 验证项 | 结果 |
| --- | --- |
| 新增单测 | `test_baseline_seed.py` 4 条、`test_gb26875_frame.py` 28 条、`test_gb28181_sip_parse.py` + `test_gb28181_catalog_parse.py` 共 26 条，58 条全绿 |
| 后端全量回归 | `python -m pytest tests/ -q`：**596 passed**（原 538 + 新增 58），无失败 |
| 结构一致性 | `alembic check` 在 head 上报告 `No new upgrade operations detected`（模型与迁移一致） |
| 全新库建表 | 指向空库执行迁移：baseline → `e5f6a7b8c9d0` 全部成功 |
| 存量库升级 | 复制开发库（版本 `b2c3d4e5f6a7`）执行迁移：升级到 `e5f6a7b8c9d0`，`gb26875_devices` 与 `video_channels` 新列均已生成 |
| 前端构建 | `npm run build` 通过；`flv.js`/`hls.js` 被拆成独立 chunk（154 kB / 590 kB），未进主包 |
| 前端 E2E | `E2E_CHANNEL=msedge npm run test:e2e`：**39 passed + 2 flaky**（审计日志、数据大屏下钻两条为时序敏感用例，重试后通过；均不涉及本次改动页面） |
| 锁文件一致性 | `yarn install --frozen-lockfile` 输出 `Already up-to-date`（锁文件完整且与 node_modules 一致），执行后锁文件哈希不变 |
| 健康检查字段 | `/health` 新增 `gb26875`、`gb28181` 两段运行状态 |
| 接口验收（临时库） | 临时库启动应用 → 管理员登录 → `/health` = healthy（含两段新状态）→ `/api/gb26875/devices`、`/api/gb26875/status`、`/api/gb26875/devices`（登记地址）、`/api/gb28181/devices`、`/api/gb28181/status` 全部 200 |
| 真实设备联调 | 未执行（见 11.6，需要设备或模拟器） |

### 11.8 前端包管理器统一为 yarn（锁文件清理）

本机 npm 10 在安装收尾阶段稳定报 `Exit handler never called!`（换缓存目录、换 npm 10.9.2、加 `--ignore-scripts` 均复现），过程中会把 `node_modules` 装坏，`.bin` 软链也生成不出来；`yarn` 的默认源 `registry.yarnpkg.com` 在本机解析到不可达地址。为避免两套锁文件长期并存、以及 npm 反复装坏依赖，本次统一如下：

- **只保留 `frontend/yarn.lock`**，删除 `package-lock.json` 与临时备份 `yarn.lock.bak`（`package.json` 里的 `packageManager` 字段本就声明 `yarn@1.22.22`）
- 安装入口统一改为 yarn：`README.md`、`start_all.bat`、`start_all.ps1`、`playwright.config.js` 的注释（`npm run dev/build/test:e2e` 保持不变，`npm run` 不需要锁文件）
- 本机重装依赖的完整命令（含源与引擎忽略开关，仅本机环境需要）：
  `yarn install --registry https://registry.npmjs.org --ignore-engines`
  —— `--ignore-engines` 是因为 `@vueuse/core@15`（`unplugin-*` 的传递依赖）要求 node ≥22，而本机为 node 20.15.1；升级 Node 后可去掉
- 注意：无法访问 `registry.npmjs.org` 的内网环境请改用自有镜像源（`--registry <镜像地址>`），不要把源写死进脚本

### 11.9 本轮遗留问题

| 级别 | 问题 | 说明与建议 |
| --- | --- | --- |
| 中 | 存量库「先 stamp 到 head」会跳过新增 DDL | `services/db_migration_service.run_migrations()` 对「有业务表但无 `alembic_version`」的库直接 `stamp head`，这类库不会被应用本轮新增的表/列。本仓库的开发库均已有 `alembic_version`，不受影响；若存在更早的历史部署库，升级前需人工确认或先手工补 DDL |
| 中 | 未用真实设备/模拟器验证 GB 协议 | 帧结构、状态位、PTZ 指令码均按国标实现并有单测覆盖，但厂商私有扩展（128~255 自定义命令、信息体长度差异）需联调时再补 |
| 低 | GB28181 设备发起的 INVITE（语音对讲）未实现 | 收到该请求时明确回 `488 Not Acceptable Here`，不做静默丢弃 |
| 低 | ZLMediaKit 镜像 tag 未在本机验证 | 默认 `zlmediakit/zlmediakit:master`，`docker compose pull` 失败时用 `ZLMEDIAKIT_IMAGE` 换私有仓库或 `zlmediakit/zlmediakit-master:latest` |
| 低 | 依赖版本漂移 | 用 yarn 重装是全新解析，部分包升到 `^` 范围内最新版（如 `@playwright/test`），因此 E2E 需改用本机 Edge（`E2E_CHANNEL=msedge`）或先执行 `npx playwright install chromium` |
| 低 | 本机 npm 安装不可用 | 若需恢复 npm 生态，建议升级 Node 到 20.19+ 后重试；在那之前不要执行 `npm install`，否则会重新生成 `package-lock.json` 并可能再次装坏 `node_modules` |

---

## 12. P1 缺口补齐：CI/CD 流水线与告警外部通知（2026-09-19）

P0 解决「能不能上线」；本节解决「上线后能不能稳定迭代」与「告警能不能真的叫到人」两件事。

### 12.1 实施项清单

| 项 | 内容 | 关键落点 |
| --- | --- | --- |
| CI/CD 流水线 | 一条工作流覆盖「校验 → 镜像可构建 → 发布 → 回滚」，把手工发版纳入流水线 | `.github/workflows/ci-cd.yml` |
| 告警外部通知 | 告警产生/升级后按级别与类型匹配通道，推送到邮件 / 企业微信 / 钉钉 / 通用 Webhook，失败重试并留投递台账 | `backend/services/alert_notify_service.py`、`backend/routers/notification_channels.py`、`notification_channels`/`notification_deliveries` 表、`frontend/src/views/MessageCenter.vue` |

新增 1 条迁移：`f6a7b8c9d0e1`（`notification_channels` + `notification_deliveries`）。

### 12.2 CI/CD 流水线

`.github/workflows/ci-cd.yml` 的作业与触发：

| 作业 | 触发 | 内容 |
| --- | --- | --- |
| `backend-test` | push / PR / 手动 | 全量 pytest；另有「结构一致性」步骤：空库跑迁移 + `alembic check`，**模型与迁移不一致即失败** |
| `frontend-build` | push / PR / 手动 | `yarn install --frozen-lockfile` + `npm run build`，并上传 dist 产物 |
| `mobile-analyze-test` | push / PR / 手动 | `flutter pub get` + `flutter analyze --fatal-infos` + `flutter test`（离线用例；真实后端冒烟在后端未启动时自动跳过） |
| `mobile-apk` | PR / 手动 action=ci | `flutter build apk --release`，产物上传为 `mobile-apk`（依赖 `mobile-analyze-test`） |
| `docker-build` | push / PR / 手动 | 构建生产镜像（不推送），保证 Dockerfile 可构建 |
| `e2e` | PR / 手动 action=ci | Playwright 全套（自动拉起后端与前端） |
| `deploy` | 手动 action=deploy | SSH 到部署主机：checkout tag → `scripts/release.sh <tag>`（脚本自带备份、迁移、健康检查与失败回滚） |
| `rollback` | 手动 action=rollback | SSH 到部署主机执行 `scripts/rollback.sh [tag]` |

设计取舍：镜像仍在部署主机上构建（沿用既有 `release.sh` 流程），CI 只做「能不能构建」的校验，
避免引入镜像仓库凭据；E2E 依赖两套环境且耗时，只在 PR 与手动触发时跑；发布/回滚是手动入口，
且缺 Secrets 时守卫步骤直接失败，不会执行一半。

### 12.3 告警外部通知通道

链路（与站内推送并行，互不影响）：

```
ingest_alert 产生/升级告警
  → 匹配「通道启用 + 级别 ≥ min_severity + 告警类型在允许列表」
  → 写 notification_deliveries（(alert_code, channel_id) 唯一 = 幂等键）
  → 入队后台任务 → worker 发送 → 成功/失败落台账，失败按次数重试
```

| 通道 | 关键字段 | 密钥字段 |
| --- | --- | --- |
| 通用 Webhook | url、secret（可选，附 `X-Signature: sha256=`） | secret |
| 企业微信机器人 | url | url |
| 钉钉机器人 | url、secret（加签） | url、secret |
| 邮件 | smtp_host/port/user、password、sender、recipients、use_ssl | password |

密钥字段用 `video_credential_cipher` 加密落库，接口只回掩码；更新时留空或传掩码表示保持原值。

配置项：`ALERT_NOTIFY_ENABLED`（默认 true）、`ALERT_NOTIFY_TIMEOUT_SECONDS`（10）、`ALERT_NOTIFY_MAX_ATTEMPTS`（3）。

接口（全部 admin）：通道增删改查 + `toggle` + `test`（立即发测试消息）+ `GET /api/settings/notification-deliveries`（投递台账）。
页面入口：消息中心 → 通知设置（原先的「站内信/短信/邮件」三列开关是纯前端 mock，已替换为真实的通道管理）。

三条刻意的设计：

1. **通知失败不得影响告警入库**：`enqueue_alert_notifications` 吞掉全部异常并记日志，告警本身已经落库
2. **同一告警同通道只发一次**：唯一约束做端到端幂等；仅在告警升级且上次发送失败时才复用记录重发
3. **不可恢复错误不浪费重试**：通道被删除/停用、告警不存在直接标记失败；网络与对端报错才交给队列重试

### 12.4 本轮验证结果

| 验证项 | 结果 |
| --- | --- |
| 新增单测 | `tests/test_alert_notify.py` **17 条**：密钥加密与脱敏、字段校验、级别/类型/启用匹配、入队幂等、全局开关、发送成功与失败、不可恢复分支、errcode 识别、SMTP 失败包装、处理器重试与死信、`ingest_alert` 接线，全绿 |
| 后端全量回归 | `python -m pytest tests/ -q`：**613 passed**（P0 后 596 + 17），无失败 |
| 结构一致性 | `alembic check` 无差异；全新库与存量库（`b2c3d4e5f6a7`）均可升级到 `f6a7b8c9d0e1` |
| 前端构建 | `npm run build` 通过 |
| 接口验收（临时库） | 管理员登录 → 通道元数据（4 类型 + 4 级别）→ 建通道（密钥加密、响应回掩码）→ 列表掩码与 ready → 更新（传掩码保持不变）→ 停用 → 测试不可达地址返回 409 且通道 `last_error` 被记录 → 投递台账接口 → 删除，全部符合预期 |
| CI 工作流 | YAML 结构已校验（6 个作业）；**未在真实 GitHub 环境跑过**（当前目录不是 git 仓库，见遗留问题） |
| 镜像 Python 版本对齐 | `Dockerfile` 基础镜像由 `python:3.11-slim` 改为 `python:3.14-slim`，与 `backend/pyproject.toml`（`requires-python >=3.14`）、本地开发环境、CI 统一；已逐个核对 requirements 中的原生依赖均有 **cp314 的 Linux wheel**（scikit-learn 1.9.1 / numpy 2.5.3 / scipy 1.18.1 / Pillow 12.3.0 / psutil 7.2.2 / psycopg-binary 3.3.6 / pydantic-core 2.46.5），镜像内不需要源码编译 |
| 生产镜像实际构建与启动 | 本机 `docker build` **成功**（耗时约 7.5 分钟，全部依赖走 cp314 wheel，日志中无源码编译）。镜像内校验：`python -V` = Python 3.14.7、原生库版本与 Windows 本地完全一致、`import main` 成功注册 52 条路由。启动冒烟：`docker run -p 18000:8000` → 启动迁移从 `b2c3d4e5f6a7` 升到 `f6a7b8c9d0e1` → `GET /health` 返回 `status=healthy`（`database=ok`、`worker.running=true`，含 `gb26875`/`gb28181` 状态块）。镜像体积 1.25GB（含 gcc/g++ 构建层与科学计算栈） |

### 12.5 本轮遗留问题

| 级别 | 问题 | 说明与建议 |
| --- | --- | --- |
| 中 | ~~流水线尚未在 GitHub 上实跑~~ **已关闭** | 仓库已推到 `github.com/fwl414/fire` 并实跑多轮，6 个校验作业全绿（见 13.11）。仅 `deploy`/`rollback` 仍未实跑 —— 需配置四个 Secrets（`DEPLOY_HOST/DEPLOY_USER/DEPLOY_SSH_KEY/DEPLOY_PATH`）并有可用部署主机 |
| 低 | 本机拉取 Docker Hub 不通，构建需走镜像源 | 本机直连 `registry-1.docker.io` 超时（Docker Desktop 未配 HTTPS 代理），构建基础镜像时改用 `docker.m.daocloud.io/library/python:3.14-slim` 拉取后 `docker tag` 成 `python:3.14-slim` 才成功。**部署主机若同样访问不了 Docker Hub，需先配置 registry-mirrors 或预拉基础镜像**，否则 `docker compose build` 会在第一步失败 |
| 低 | 短信通知通道未实现 | 需要短信服务商凭据；现有通道表结构与前端表单是「按类型渲染字段」的，新增类型只需在 `CHANNEL_TYPES` 里加一段配置 + 一个发送函数 |
| 低 | 通知功能未加 E2E 用例 | 已做接口级验收与 17 条单测；若要在浏览器里回归「新增通道 → 测试 → 删除」链路，可补一条 `e2e/notification-channel.spec.js` |
| 低 | 站内通知已读状态仍是全局文件 | `backend/data/notification_read.json` 不分租户/用户，属既有实现，未在本轮改动 |

---

## 13. 移动端（Flutter App）改造完成（2026-09-19）

### 13.1 背景与结论

改造前 `mobile_app/` 只是骨架，且带着几个**阻断级**问题：

- **没有登录与令牌**：后端是 `HTTPBearer`，App 请求从不带 `Authorization` → 除登录外全部 401
- **响应解析协议不匹配**：`api_service.dart` 写死读 `data['data']`，而后端业务接口返回的是裸 dict / 裸 list → 即便鉴权通过也全部抛异常
- **接口对不上**：用 `PATCH /api/faults/{id}/status`（后端是 `PUT` + Form）、问答发 JSON（后端要 Form）、`/api/devices` 与 `/api/records` 被当数组强转
- **假数据与假操作**：告警页整页 6 条写死数据且不调任何接口；工单「新建」只弹提示不落库；「我的」统计写死、菜单点了只弹「点击了 xxx」、退出登录不调后端也不清令牌
- 9 个页面里 4 个不可达（设备/故障/问答/记录）；专为移动端设计的 `/api/mobile/*` 一个都没调
- Android release manifest 缺 `INTERNET` 权限 → release 包无法联网；唯一的 widget_test 断言的 3 个文案在 UI 里根本不存在
- 从未真正构建过（无 `.dart_tool`/`build`/`local.properties`）

本轮把基础设施与页面全部打通：**登录鉴权 → 统一请求底座 → 真实接口 → 页面真实数据**。

### 13.2 实施项

| 项 | 内容 |
| --- | --- |
| HTTP 底座 | `lib/services/api_client.dart`：Bearer 自动注入、401 自动用刷新令牌换新令牌并重放原请求、20s 超时、后端错误文案提取（`detail`/`message`）、响应解包（裸 dict / 裸 list / `{items,total}` / `{ok,code,data}` 四种形态） |
| 令牌策略 | 令牌存 `shared_preferences`；解析 JWT `exp`，剩余不足 60 分钟时提前续期；彻底失效时清令牌并经全局导航 key 回登录页 |
| 登录与鉴权门 | `lib/pages/login_page.dart` + `lib/main.dart` 的 `AuthGate`：启动读令牌 → 续期 → 拉 `/api/auth/me` → 进主界面或登录页 |
| 接口对齐 | 登录/刷新/改密/问答改 Form；工单流转改用 `POST /api/workorders/{id}/status`；`/api/records`、`/api/devices`、`/api/alert/list` 按真实结构解析 |
| 接入 `/api/mobile/*` | `home`（首页概览与待办）、`tasks`、`workorders/{id}/claim`（领取工单）、`report`（现场上报，复用巡检 Agent） |
| 页面真实化 | 首页（原 4 个空 `onTap` + 两块写死列表）、告警页（原整页假数据）、工单（原客户端中文过滤 + 假新建）、我的（原写死统计 + 空菜单 + 假退出）全部改为真实接口 |
| 新增页面 | 4 个详情页（告警/工单/设备/巡检记录）+ 设备台账 + 巡检记录 + 消防问答 + 消息通知 + 扫码 + 新建工单；删除与工单页重复的 `faults_page.dart` |
| 实时通知 | `lib/services/ws_service.dart` 接 `/ws/notifications`（首帧 `{"action":"auth","token":...}`、30s 心跳、指数退避重连）；告警推送到达时列表自动刷新 + 铃铛未读角标更新 |
| 扫码与定位 | `mobile_scanner` 扫设备二维码 → 按编号查设备 → 跳详情；`geolocator` 在上报时取经纬度（失败降级不阻断上报） |
| Android 配置 | main manifest 补 `INTERNET`/`ACCESS_NETWORK_STATE`/`CAMERA`/`ACCESS_FINE_LOCATION`/`ACCESS_COARSE_LOCATION`；应用名改为「智慧消防巡检」 |
| 工具链 | 本机安装 Flutter 3.47.5（Dart 3.13.4）到 `F:\flutter` |
| 补齐 lint 依赖 | `pubspec.yaml` 补 `flutter_lints`（`analysis_options.yaml` 早已 include `package:flutter_lints/flutter.yaml`，但依赖从未声明，导致整套推荐规则实际未生效） |

### 13.3 验证结果

| 验证项 | 结果 |
| --- | --- |
| 静态分析 | `dart analyze`（整个包，含 flutter_lints 全套规则）→ **No issues found**。`flutter analyze` 因路径含非 ASCII 字符会崩（见 13.4），经 `mobile_app/flutter_analyze.bat`（ASCII 目录联接）验证同样 **No issues found! (ran in 4.6s)** |
| 单元 + Widget 测试 | `flutter test` → **25 passed**（22 条离线 + 3 条真实后端联调）。离线部分覆盖：响应解析 6 例（裸数组/裸对象/分页结构/包装体拆包/中文 UTF-8/错误文案）、鉴权 5 例（Bearer 注入、登录不带令牌、401 清令牌并回调、401 刷新后重放且第二次带新令牌、刷新失败不重试）、提前续期 3 例（未临近不刷、临近则刷、非 JWT 不误判）、页面 6 例（登录页渲染、空表单校验且不发请求、登录成功保存令牌并跳转、登录失败显示后端原因、首页渲染真实数据、接口失败显示错误态与重试）、时间格式化 1 例（UTC→本地） |
| 真实后端联调 | `flutter test test/live_api_smoke_test.dart`（需后端跑在 `127.0.0.1:8000`，未启动则整组跳过）→ **3 passed**。链路：登录（Form 参数）→ `/api/auth/me` → `/api/mobile/home`（实测：待处理告警 3、设备 1792）→ `/api/mobile/tasks` → 告警列表+详情（`AL-20260915-C74D2C15`）→ 工单列表 → 设备台账+详情（“喷淋头404”）→ 巡检记录 → 通知与未读数 → 登出且本地令牌被清；另验证未登录访问业务接口返回 401、错误密码抛出后端提示文案 |
| 整包编译 | `flutter build web` → **Built build/web**（22.9s 全量编译通过，产物与日志已清理） |
| Android 出包 | `flutter build apk --release` → **Built app-release.apk（66.6MB）**；加 `--split-per-abi` → arm64-v8a 24.4MB / armeabi-v7a 20.4MB / x86_64 26.8MB。详见 13.6 |
| APK 校验 | `aapt2 dump badging`：包名 `com.fire.inspection.mobile`、label「智慧消防巡检」、targetSdk 36、5 项权限齐全、native-code 三 ABI；`apksigner verify`：v2 签名方案通过，签名者 `CN=Fire Inspection Mobile, ...`（SHA-256 `b232e0a7163d39457f29624d55ba67068e35cc9abcfbeff6692fca5075dae29d`） |
| 真机/模拟器联调 | **未执行**：无移动设备（可用设备为 Windows/Chrome/Edge）；相机、扫码、定位、WebSocket 仍待真机验证 |

### 13.4 工具链与本机限制

- Flutter 3.47.5 / Dart 3.13.4 装在 `F:\flutter`（未写入系统 PATH，用前需 `$env:Path = "F:\flutter\bin;" + $env:Path`）
- `flutter analyze` 在本仓库路径（含「副本」等非 ASCII 字符）下会崩：flutter 工具与分析器之间的 LSP 报文
  长度与实际字节数对不上，分析器以 `FormatException: Unexpected end of input ... LspByteStreamServerChannel._readMessage` 退出。
  已在纯 ASCII 路径下对照验证（同一份代码 `No issues found`），确认诱因就是路径字符集。
  绕过方案已进仓库：`mobile_app/flutter_analyze.bat`（`mklink /J` 建 ASCII 目录联接后分析，**源码不复制、目录不改名**，
  联接位置可用 `FLUTTER_ASCII_LINK` 覆盖）；`dart analyze`（不走 LSP）与 `flutter test`、`flutter build web` 均不受影响。
  治本方案是把仓库目录改成纯 ASCII 名
- Android 工具链已装齐（见 13.6）：JDK Temurin 17.0.20.1 在 `F:\jdk\jdk17`，Android SDK 在 `F:\android-sdk`
  （platform-tools 37.0.1 + build-tools 36.0.0 + platform android-36），`JAVA_HOME`/`ANDROID_HOME`/`ANDROID_SDK_ROOT` 已写入用户环境变量
- 构建期网络：Gradle 分发下载出现过一次 `java.net.ConnectException: Connection timed out`，
  Flutter 自动重试后成功并缓存到 `~/.gradle/wrapper/dists`；Apache Maven 中央仓与 `dl.google.com` 本次直连正常，
  Docker Hub 直连不通的老问题依旧（需走 `docker.m.daocloud.io`）

### 13.5 遗留问题

| 级别 | 问题 | 说明与建议 |
| --- | --- | --- |
| 中 | 未做真机/模拟器联调 | 现有断言只到「解析、鉴权、页面渲染」层面；相机、扫码、定位、WebSocket 需要真机验证（权限弹窗、前后台切换、弱网重连） |
| 低 | 令牌存 SharedPreferences | 未接系统安全存储；对令牌敏感的场景建议换 `flutter_secure_storage` |
| 低 | 巡检照片只能显示文件名 | 后端没有对外的巡检图片下载接口（`image_path` 是服务端本地路径），App 内只做文字说明；要在手机上回看照片需后端补受控下载接口 |
| 低 | 依赖为全新解析 | 新增 `web_socket_channel`/`mobile_scanner`/`geolocator` 后 `pubspec.lock` 整体更新（67 个包变动），建议真机跑通后再定版 |
| 低 | APK 已与系统版本对齐 | 全项目版本统一为 `1.0.0`（APK `1.0.0+1`、`VERSION` `V1.0.0`、`pyproject.toml`/`package.json` `1.0.0`），后续发版只需递增 `pubspec.yaml` 的 `+N` |
| 中 | Web 工单页与工单状态机不匹配 | 已在 13.9 修复：`WorkOrders.vue` 回到了它本来的「整改工单」域（运行库 `work_orders`），并新增 `/api/workorders/rectification*` 路由 |
| 低 | Gradle / AGP / Kotlin 版本偏低 | Flutter 提示建议 Gradle ≥9.1、AGP ≥9.0.1、Kotlin ≥2.3.20（现为 8.14 / 8.11.1 / 2.2.20）。当前只是弃用预警、不影响出包，三件套升级是破坏性改动，需单独验证 |

### 13.6 Android APK 化（2026-09-19 追加）

#### 背景

13.1 解决的是「App 跑不起来」，这一轮补齐的是「能作为 APK 交付」。此前该工程连 Android 工具链都没有，
且带着三个只有出包时才会暴露的阻断问题：

| 问题 | 后果 |
| --- | --- |
| main manifest 少 `networkSecurityConfig` | Android 9（API 28）起默认禁明文流量，release 包完全连不上 HTTP 后端 |
| `signingConfig = debug` | release 包用调试密钥签名，无法分发，换机器就装不上 |
| `applicationId = com.example.fire_ai_agent_mobile` | `com.example` 前缀会被应用商店拒收 |

#### 环境

| 组件 | 版本 | 路径 | 来源 |
| --- | --- | --- | --- |
| JDK | Temurin 17.0.20.1 | `F:\jdk\jdk17` | 清华 Adoptium 镜像（官方 `api.adoptium.net` 不可达） |
| Android cmdline-tools | 19.0 | `F:\android-sdk\cmdline-tools\latest` | dl.google.com 官方包 |
| platform-tools | 37.0.1 | `F:\android-sdk\platform-tools` | `sdkmanager` |
| build-tools | 36.0.0、35.0.0 | `F:\android-sdk\build-tools` | `sdkmanager` |
| platform | android-36 | `F:\android-sdk\platforms\android-36` | `sdkmanager` |

`flutter doctor` 的 Android toolchain 项已全绿（`All Android licenses accepted`）。

#### 工程改造

| 项 | 改动 |
| --- | --- |
| 包名 | `com.example.fire_ai_agent_mobile` → `com.fire.inspection.mobile`（与后端 Java 包 `com.fire.inspection` 同一命名空间）；`namespace`、`applicationId` 与 `MainActivity.kt` 的包声明及所在目录同步调整 |
| 签名 | 新增 `android/app/fire-release.jks`（RSA 2048 / 有效期 10000 天 / 别名 `fire-release`），口令写在 `android/key.properties`；`build.gradle.kts` 读该文件配置 `signingConfigs.release`，文件缺失时回退 debug 签名。两者都已进 `.gitignore` |
| 明文流量 | 新增 `res/xml/network_security_config.xml`（`cleartextTrafficPermitted="true"`），manifest 经 `android:networkSecurityConfig` 引用；后端上 HTTPS 后改一个布尔值即可整体收紧 |
| 备份 | `android:allowBackup="false"` + `android:fullBackupContent="false"`：令牌存在 SharedPreferences，避免随 adb backup / 云备份被导出 |
| 图标 | 程序化生成消防主题图标（红色渐变圆角底 + 橙黄火焰），覆盖 mdpi~xxxhdpi 五档，`ic_launcher.png` 与 `ic_launcher_round.png` 各一套；另配 `mipmap-anydpi-v26/` 自适应图标（`drawable/ic_launcher_foreground.xml` 火焰矢量、`drawable/ic_launcher_background.xml` 渐变底）；启动闪屏 `launch_background.xml` 复用同一前景，消除冷启动白屏 |
| 构建脚本 | 新增 `mobile_app/build_apk.bat`：自动设 `JAVA_HOME`/`ANDROID_HOME`、走 ASCII 目录联接规避非 ASCII 路径，`API_BASE_URL` 作为首个参数经 `--dart-define` 编译进包 |

#### 产物与校验

| 产物 | 体积 | 说明 |
| --- | --- | --- |
| `app-release.apk` | 66.6 MB | 通用包（arm64-v8a + armeabi-v7a + x86_64） |
| `app-arm64-v8a-release.apk` | 24.4 MB | 现场分发推荐 |
| `app-armeabi-v7a-release.apk` | 20.4 MB | 老旧 32 位机型 |
| `app-x86_64-release.apk` | 26.8 MB | 模拟器 |

- 首次 `assembleRelease` 364.2s（含 Gradle 8.14 分发下载与依赖解析），增量构建 23.6s
- `aapt2 dump badging`：`package name='com.fire.inspection.mobile' versionCode='1' versionName='1.0.0'`、
  `application-label:'智慧消防巡检'`、`compileSdkVersion='36'`、`targetSdkVersion:'36'`，
  权限 `INTERNET` / `ACCESS_NETWORK_STATE` / `CAMERA` / `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` 齐全，
  `native-code: 'arm64-v8a' 'armeabi-v7a' 'x86_64'`
- `apksigner verify`：`Verified using v2 scheme: true`，
  Signer `CN=Fire Inspection Mobile, OU=Fire AI Agent, O=Fire Inspection, L=Beijing, ST=Beijing, C=CN`，RSA 2048
- 体积构成：三份 `libflutter.so`（13.1 / 11.7 / 8.6 MB）+ 三份 `libapp.so`（6.8 / 6.4 / 6.2 MB）+
  三份 `libbarhopper_v3.so`（MLKit 条码，5.9 / 4.9 / 3.2 MB，来自 `mobile_scanner`），
  因此按 ABI 拆包可省掉约 2/3 体积
- 分 ABI 包的 `versionCode` 是 `2001`，通用包是 `1`，同一设备混装会被系统判为降级而拒绝安装
- 构建过程仅有一条 Gradle wrapper 分发下载的瞬时超时（Flutter 自动重试后成功），无 NDK 缺失导致的符号剥离告警

### 13.7 版本号统一、多平台包名与移动端接入 CI（2026-09-19 追加）

#### 13.7.1 版本号统一为 1.0.0

原系统版本 `V12.8.3` 作废，全项目统一到与 APK 一致的 `1.0.0`：

| 位置 | 原值 | 现值 |
| --- | --- | --- |
| 根目录 `VERSION` | `V12.8.3` | `V1.0.0` |
| `backend/pyproject.toml` | `12.8.3` | `1.0.0` |
| `backend/main.py`（FastAPI `version=`） | `12.8.3` | `1.0.0` |
| `frontend/package.json` | `12.8.3` | `1.0.0` |
| `mobile_app/pubspec.yaml` | `1.0.0+1` | 不变（本就是基准；`+1` 为 versionCode） |

另替换了 16 处后端接口返回与文档中的版本串（`/health`、`/api/system/routes`、`/api/system/core-check`、
`/api/inspection/agent-steps`、`/api/demo/seed` 提示语、巡检档案报告页脚、竞赛总览、答辩演示流程、健康自检文案、
`routers/README.md`、`P0_AUDIT_REPORT.md` 等）。前端不写死版本，UI 上的版本号取自接口
（`/api/product/*`、`/api/competition/overview`），因此自动跟随。

未改动（属协议常量，与产品版本无关）：GB 26875 的 `MAJOR_VERSION` / `TYPE_*_VERSION`、GB28181 的 `SIP_VERSION`、
XML `version="1.0"` 声明、Alembic 的 `alembic_version` 表名与 `VERSION_TABLE` 常量、CI 的 `PYTHON_VERSION` / `NODE_VERSION`。

未改动（属既有 API 路径与数据库表名，改名会破坏运行库与调用方）：`routers/v128_runtime_hotfix.py` 的模块名、
路由前缀 `/api/v128`、运行库表 `v128_inspection_records` / `v128_workorders` / `v128_devices` /
`v128_device_telemetry` / `v128_hardware_events` / `v128_qa_citation_logs`，以及响应里的 `source: "v128"`。
该模块内的**展示文案**（OpenAPI tag、演示数据提示语、自检 detail、日志前缀）已随版本一起改为 `V1.0.0`。

> 后续更正：该模块随后在 13.9 被整体删除（它从未注册到 `main.py`，`/api/v128` 本就不可达），
> 上面这段「保留」的决定已失效，仅作为当时的记录保留。

> 已知残留：`backend/main.py.bak` 是历史备份快照，其中仍是旧版本串，未改动（不属于运行代码）。

#### 13.7.2 多平台包名统一

Android 之外，iOS / macOS / Linux / Windows 的标识也统一到 `com.fire.inspection.mobile`：

| 平台 | 文件 | 改动 |
| --- | --- | --- |
| iOS | `ios/Runner.xcodeproj/project.pbxproj` | Debug/Release/Profile 三处 `PRODUCT_BUNDLE_IDENTIFIER` 及三处 `...RunnerTests`，由 `com.example.fireAiAgentMobile[.RunnerTests]` 改为 `com.fire.inspection.mobile[.RunnerTests]` |
| iOS | `ios/Runner/Info.plist` | `CFBundleDisplayName` 由自动生成的 `Fire Ai Agent Mobile` 改为「智慧消防巡检」 |
| macOS | `macos/Runner/Configs/AppInfo.xcconfig` | `PRODUCT_BUNDLE_IDENTIFIER` 改名；`PRODUCT_COPYRIGHT` 中的 `com.example` 改为 `com.fire.inspection` |
| macOS | `macos/Runner.xcodeproj/project.pbxproj` | 三处 `...RunnerTests` 标识同步 |
| Linux | `linux/CMakeLists.txt` | `APPLICATION_ID` 由 `com.example.fire_ai_agent_mobile` 改为 `com.fire.inspection.mobile` |
| Linux | `linux/runner/my_application.cc` | 窗口标题由 `fire_ai_agent_mobile` 改为「智慧消防巡检」 |
| Windows | `windows/runner/Runner.rc` | `CompanyName`、`LegalCopyright` 中的 `com.example` 改为 `com.fire.inspection`（该资源块是 1252 代码页，故不放中文） |

保留未改：macOS `PRODUCT_NAME`、Windows `ProductName` / `OriginalFilename`、Linux `BINARY_NAME`，以及
Dart 包名 `fire_ai_agent_mobile`（在 `pubspec.yaml` 与所有 `import 'package:fire_ai_agent_mobile/...'` 中，
改名等于全量重写导入路径，与平台包名无关，风险大于收益）。

#### 13.7.3 移动端接入 CI

`.github/workflows/ci-cd.yml` 新增两个作业（完整作业表见 12.2）：

| 作业 | 触发 | 内容 |
| --- | --- | --- |
| `mobile-analyze-test` | push / PR / 手动 | Flutter 3.47.5 + `flutter pub get` + `flutter analyze --fatal-infos` + `flutter test` |
| `mobile-apk` | PR / 手动 action=ci | JDK 17 + `flutter build apk --release`，APK 上传为 `mobile-apk` 产物；`needs: [mobile-analyze-test]` |

- `API_BASE_URL` 取仓库变量 `vars.API_BASE_URL`，未配置时退回 `http://10.0.2.2:8000`；CI 里的构建只为验证「能不能出包」，
  正式分发包仍走 `mobile_app/build_apk.bat <真实后端地址>`
- `test/live_api_smoke_test.dart` 在后端未启动时自动跳过，CI 中不会误报失败
- 本机回归：`flutter analyze` → `No issues found! (ran in 5.7s)`；`flutter test` → **25 passed**

### 13.8 移动端 ↔ Web 端联动打通（2026-09-19 追加）

#### 背景

13.1–13.7 完成后，做了一次「移动端与 Web 端能否互见」的核查。结论是**部分联动**：
工单、告警、设备、统计、WebSocket 推送这几条线是通的（同一张表 / 同一租户广播），
但**巡检记录**这条线断了，另有**工单状态机取值不一致**导致自动生成的工单无法流转。

#### 断点 1：巡检记录分两套存储，互不可见

| 存储 | 写入方 | 读取方 |
| --- | --- | --- |
| 主库 `inspection_records`（SQLAlchemy 模型） | `run_inspection_agent`（`services/agent_service.py:457-476`） | `/api/records`（`routers/inspection.py:139-146`）→ 移动端记录页、首页统计 |
| 运行库 `inspection_records`（`record_persistence_service`） | `POST /api/records/save-inspection` | `/api/inspection-archives*` → Web「巡检档案 / 报告打印 / 复查」 |

Web 巡检页走的是**两步**：`POST /api/inspection/analyze`（写主库）+ `POST /api/records/save-inspection`
（写运行库，`frontend/src/views/Inspection.vue:630,648`）。移动端此前**只做了第一步**，
因此现场上报在 Web 巡检档案里看不到，反之 Web 巡检页保存的记录移动端也看不到。

**修复**：在 `routers/mobile.py` 的 `/api/mobile/report` 中补齐第二步 —— 新增
`_mirror_report_to_archive()`，把 Agent 结果同步写入运行库。要点：

- 档案 id 由主库记录 id 派生（`REC-M-<record_id>`），配合 `save_inspection_record` 的
  `INSERT OR REPLACE` 保证幂等，重复提交不会产生重复档案
- 运行库的报告字段要求是对象，而 Agent 产出的是纯文本报告，包一层
  `{"title", "content", "source": "mobile"}`；`hazards`、`hazard_results`、`agent_steps`、
  `image_paths` 一并带过去，档案详情与报告打印才有内容
- 档案是二次落库，失败**不应让已完成的现场上报整体失败**，因此单独 try/except 并打日志；
  响应新增 `archiveId` 字段（失败时为空串）

#### 断点 2：工单状态机取值不一致

`run_inspection_agent` 自动建单时把状态写成「待处理」，但工单状态机只认
**待受理 / 处理中 / 待复查 / 已完成 / 已关闭**（`routers/workorder.py:392`）。后果：

- 移动端「可领取」只认「待受理」（`services/mobile_collab_service.py:26`）→ 这类工单**领不了**
- 移动端工单 Tab 只有 全部/待受理/处理中/已完成 → 这类工单**不在任何 Tab 里**
- `/api/workorders/dashboard` 的 `pending` 统计的是「待受理」（`routers/workorder.py:92`）→ **恒为 0**

**修复**（写入端统一为「待受理」，并处理历史遗留）：

| 位置 | 改动 |
| --- | --- |
| `services/agent_service.py:522` | 自动建单状态 `待处理` → `待受理` |
| `services/business_crud_service.py:491` | `create_workorder` 默认状态 `待处理` → `待受理` |
| `services/demo_seed.py:201` | 演示整改工单状态 `待处理` → `待受理` |
| `services/mobile_collab_service.py:26` | 历史遗留：「待处理」与「待受理」等价，一并视为可领取，避免老库里的工单卡死 |
| `routers/gis.py:187` | 「待处理工单数」改为「未闭环工单数」（原统计的字面值已不存在） |
| `frontend/src/views/Faults.vue:13` | 页面按钮 `待处理` → `待受理`（该接口不校验取值，会写进非法状态） |

**未改动**（同名但不同域）：`hardware_event_service` / `internal_demo_service` 里的「待处理」属于**硬件事件**状态，
与工单状态机无关。（`v12_closed_loop_service` 与 `v128_runtime_hotfix` 当时也在此列，二者随后均已在 13.9 删除。）

#### 移动端补齐

| 项 | 改动 |
| --- | --- |
| 工单 Tab | `mobile_app/lib/pages/workorders_page.dart`：4 个 Tab → 6 个（全部/待受理/处理中/待复查/已完成/已关闭），并置 `isScrollable: true` 防窄屏挤压 |
| 首页待办 | `mobile_app/lib/pages/dashboard_page.dart`：待办列表改用专为此设计的 `/api/mobile/tasks`（最多 50 条，此前 `/api/mobile/home` 每类只给 5 条且该接口无人调用）；因 `tasks` 只返回「已指派给我」的工单，可领取工单仍从 `home` 取，避免漏掉待认领的活 |
| 测试 | `test/widget_test.dart` 的假后端补 `/api/mobile/tasks` 路由，首页用例同时覆盖新链路 |

#### 验证

用**隔离环境**实测（复制主库与运行库到临时目录，`DATABASE_URL` / `RUNTIME_DB_PATH` 均指向临时文件，
跑完删除，开发库零污染）：

| 步骤 | 结果 |
| --- | --- |
| `POST /api/mobile/report`（现场上报，高风险） | HTTP 200，`recordId=1`、`archiveId=REC-M-1` |
| `GET /api/records`（移动端记录页读的主库） | 命中本次上报，`location`/`risk_level` 正确 |
| `GET /api/inspection-archives`（Web 巡检档案读的运行库） | **出现 `REC-M-1`**，来源标记移动端；详情可读（含 hazards/image_paths/learning_recommendations 等） |
| `POST /api/workorders`（新建工单） | 直查库：`(1, '待受理', ...)` —— 不再是「待处理」 |
| `GET /api/mobile/home` → `claimableWorkorders` | 该工单**出现在可领取列表** |
| `POST /api/mobile/workorders/1/claim` | 200「已领取，工单已进入处理中」 |
| `POST /api/workorders/1/status`（待复查 → 已完成） | 均 200；详情最终 `已完成`，`assignee_name=系统管理员` |
| `POST /api/workorders/1/status` 传 `待处理` | **HTTP 400 被拒**（非法状态不再能写入） |
| `GET /api/workorders/dashboard` | `pending=1`（修复前因状态写错而恒为 0） |
| `GET /api/mobile/tasks` | 返回 3 条待处理告警 |

回归：

- 后端全量 `pytest tests/ -q` → **613 passed**
- 移动端 `flutter analyze` → **No issues found!**；`flutter test` → **25 passed**

#### 核查中发现的相关问题

`frontend/src/views/WorkOrders.vue`（Web「整改工单」页）当时也是坏的（统计卡片恒为 0、「推进」按钮 400、
关键字段全空），根因与本节同源 —— 页面读的是**整改工单**（运行库）却接到了**故障工单**（主库）的接口。
已在 **13.9** 一并修复。

### 13.9 Web「整改工单」页修复（2026-09-19 追加）

#### 背景：系统里有两套工单

| | 故障工单 | 整改工单 |
| --- | --- | --- |
| 存储 | 主库 `fault_tickets`（SQLAlchemy `FaultTicket`） | 运行库 `work_orders`（`record_persistence_service`） |
| 来源 | 告警处置、巡检高风险自动建单、移动端领取、`POST /api/workorders` | 巡检页 `POST /api/workorders/generate`、`POST /api/records/save-inspection` |
| 状态机 | 待受理 → 处理中 → 待复查 → 已完成 → 已关闭 | 待派单 → 整改中 → 待复查 → 已闭环 |
| 谁在用 | Web「故障闭环」页（`/api/faults`）、移动端、`/api/workorders/*` | Web「整改工单」页、巡检档案的「整改工单与复查」小节 |
| 证据链 | 无相应字段 | `before_images` / `after_images` / `review_images` / `review_note` 存在 `raw_json` |

`WorkOrders.vue` 的**字段全是整改工单那一套**（`hazard` / `responsible_role` / `recommended_action` /
`timeline` / `before_images` / `after_images`，统计卡片标签是 待派单 / 整改中 / 待复查 / 已闭环），
但 `routers/workorder.py` 后来把 `/api/workorders`（列表 / 详情 / 状态 / 看板）切到了主库 `FaultTicket`，
只留下 `/evidence`、`/review` 还是运行库。于是四处对不上：

| 现象 | 原因 |
| --- | --- |
| 四个统计卡片恒为 0 | 页面读 `dashboard.summary_cards`，而 `/api/workorders/dashboard` 返回的是 `pending/processing/...` |
| `hazard` / `recommended_action` / `responsible_role` 全空 | 列表来自主库 `FaultTicket`，没有这些字段 |
| 「推进」按钮 400 | 页面发 待派单→整改中→待复查→已闭环，主库接口只认 待受理/处理中/待复查/已完成/已关闭 |
| 详情里证据链 / 复查 404 | 这两个接口按运行库字符串 id 查，而详情给出的是主库整数 id |

佐证：`routers/workorder.py` 里 `list_workorders`、`get_workorder_dashboard` 一直是 **import 了但没使用**，
正是这次半途切换留下的痕迹。

#### 改动

后端（`routers/workorder.py`）新增一组整改工单路由，**不动主库那一套**：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/workorders/rectification` | 列表（支持 `status` 过滤） |
| GET | `/api/workorders/rectification/dashboard` | 看板：待派单 / 整改中 / 待复查 / 已闭环 + 闭环率 |
| GET | `/api/workorders/rectification/{order_id}` | 详情（含 timeline 与证据链字段） |
| POST | `/api/workorders/rectification/{order_id}/status` | 推进状态，**取值必须在整改工单状态机内，否则 400** |

- 这些静态路径**必须声明在 `/api/workorders/{order_id}` 之前**，否则会被它按路径参数吃掉
  （已按此顺序插入，并在代码里写了注释）
- 状态校验是新加的：原 `update_workorder_status` 不校验，会写进谁都不认的中间状态

前端（`frontend/src/views/WorkOrders.vue`）**只改 4 个请求地址**（列表 / 看板 / 详情 / 推进状态）。
模板、统计卡片、状态词、证据链与复查逻辑一行未动 —— 因为它们本来就是照运行库的数据结构写的。

#### 副产物：运行库历史数据因 `tenant_id` 为 NULL 而整体不可见

接完路由后列表依然是空的。查库发现运行库的历史数据 `tenant_id` 全是 NULL：

```
work_orders          tenant_id: (None, 344)
inspection_records   tenant_id: (None, 17)
inspection_reports   tenant_id: (None, 49)
```

`tenant_id` 是后加的列（`_add_column_if_missing` 只加列、不回填），而所有读取都按 `tenant_id = ?` 过滤，
这批存量数据被整体滤掉 —— 这也是「巡检档案」页此前只剩新建记录的原因。

修复（`services/record_persistence_service.py`）：新增 `_tenant_scope()`，把运行库读取路径的租户条件统一改成
`(tenant_id = ? OR tenant_id IS NULL)`，共替换 **13 处**（整改工单列表 / 详情 / 状态 / 复查 / 证据链、
巡检记录列表 / 详情等）。调用方仍然只绑定一个 `tenant_id` 参数，SQL 里也仍然只有一个 `?`，参数个数不变。

> 取舍：把 NULL 视为归属当前租户，适用于本系统这种单租户部署（主库里只有一个租户 id=1）。
> 将来真要跑多租户，应改为一次性回填 `tenant_id`，而不是读时兜底。

#### 验证（隔离环境，跑完删除，开发库零污染）

| 步骤 | 结果 |
| --- | --- |
| `GET /api/workorders/rectification/dashboard` | 待派单 **297** / 整改中 0 / 待复查 0 / 已闭环 **31**，闭环率 9.0% |
| `GET /api/workorders/rectification?limit=5` | 返回 5 条，`hazard` / `responsible_role` / `recommended_action` / `deadline` / `timeline` / `before_images` 均有值 |
| `status=待派单` 过滤 | 只返回待派单 |
| `GET /api/workorders/rectification/{id}` | 200；不存在的 id → 404 |
| `POST .../{id}/status` 传 `整改中` | 200，timeline 追加一条（operator=admin） |
| `POST .../{id}/status` 传 `待处理` | **400**，提示有效值为 待派单, 整改中, 待复查, 已闭环 |
| `POST /api/workorders/{id}/evidence` | 200，`before_images` 写入成功 |
| 主库那套 | `/api/workorders`（`{total,page,page_size,items}`）、`/api/workorders/dashboard`（`pending/...`）、`/api/faults` 均未受影响 |
| 路由优先级 | `/api/workorders/rectification` 返回列表而非 422（未被 `{order_id}` 吃掉）；`/api/workorders` 老路径仍可用 |

回归：

- 后端全量 `pytest tests/ -q` → **613 passed**（含被改动的共享服务 `record_persistence_service` 相关用例）
- 前端 `npm run build` → **✓ built in 18.96s**

#### 运行库工单词表归一（2026-09-19 追加）

接完路由后看板是 待派单 297 / 整改中 0 / 待复查 0 / 已闭环 31 = 328，但列表有 344 条 —— 差的 16 条
状态是「待整改」。查来源：`services/v12_closed_loop_service.py` 往**同一张** `work_orders` 表里写的是
v12 词表（待整改 / 整改中 / 已完成 / 已复查），它经 `_normalize_status()` 做映射，方向恰好是
「现在通用词 → v12 词」。该模块现已无任何路由引用（只有测试引用它），属历史遗留的孤儿模块，
因此脏数据只需清洗一次，不会再有新数据进来。

修复（`services/record_persistence_service.py`）：新增 `LEGACY_WORKORDER_STATUS_MAP` 与
`_normalize_legacy_workorder_status()`，在 `_init_db()` 里做一次幂等归一。`_init_db()` 每次
`_connect()` 都会跑，所以其它部署下次启动会自动纠偏：

| v12 历史值 | 归一为 | 依据 |
| --- | --- | --- |
| 待整改 | 待派单 | v12 第 1 阶段 ≡ 现在第 1 阶段（v12 的 `_normalize_status` 也正是把 待派单 映射成 待整改） |
| 待处理 | 待派单 | 同上 |
| 已完成 | 待复查 | v12 第 3 阶段（整改完成、待复查）≡ 现在第 3 阶段 |
| 已复查 | 已闭环 | v12 第 4 阶段 ≡ 现在第 4 阶段 |

实测（开发库 `backend/data/fire_agent_runtime.db`）：

```
归一前    : 已闭环 31 / 待整改 16 / 待派单 297   合计 344
归一后    : 已闭环 31 / 待派单 313              合计 344（行数不变）
幂等复查  : 第二次调用改动 0 行
看板      : 待派单 313 / 整改中 0 / 待复查 0 / 已闭环 31 → 313 + 31 = 344，与列表完全对齐
```

#### 运行库 `tenant_id` 回填（2026-09-19 追加）

上一步的 NULL 兜底只是让存量数据「看得见」，数据本身仍然没有租户归属，这里做一次性回填。

回填目标怎么定：**不能看 `tenants` 表的行数** —— 本机 `tenants` 里有 **5 个**租户，后 4 个是测试残留
（审计隔离 / 任务隔离 / 管线隔离 / 系统监控测试），真实用户只在 id=1。因此改用
**「有用户的租户是否唯一」**：主库 `users.tenant_id` 去重后恰好一个 → 回填到它；否则不猜，跳过。

修复（`services/record_persistence_service.py`）：新增 `RUNTIME_TENANT_TABLES`、
`_single_user_tenant_id()`、`_backfill_runtime_tenant_id()`，与词表归一一起挂在 `_init_db()` 里，
同样幂等、同样在其它部署下次启动时自动生效。

实测（开发库 `backend/data/fire_agent_runtime.db`）：

```
回填前    : work_orders (NULL,344) / inspection_records (NULL,17) / inspection_reports (NULL,49)
判定的租户: 1
回填      : 410 行
回填后    : work_orders (1,344) / inspection_records (1,17) / inspection_reports (1,49)
幂等复查  : 第二次调用 0 行
```

回填后的读取校验：

| 读取 | 结果 |
| --- | --- |
| `list_workorders(tenant_id=1)` | 344 |
| `list_workorders(tenant_id=2)` | **0** —— 租户隔离真实生效，不再靠 NULL 兜底互相泄露 |
| `list_workorders(tenant_id=None)` | 344（内部跨租户统计用） |
| `list_inspection_records(tenant_id=1)` | 17 |
| `list_archives(tenant_id=1)` | **17** —— 「巡检档案」页不再只剩新建记录 |
| 整改工单看板 | 待派单 313 / 整改中 0 / 待复查 0 / 已闭环 31，闭环率 9.0% |

> `_tenant_scope()` 的 NULL 兜底**保留不动**：运行库里还有个孤儿写入方
> （`v12_closed_loop_service.create_workorder` 的 INSERT 不含 `tenant_id`）会写出 NULL 行，
> 兜底能避免这类行在任何页面都消失。等所有写入方都带上 `tenant_id` 后，才适合改成严格隔离。

#### `v12_closed_loop_service` 写入补上 `tenant_id`（2026-09-19 追加）

上一节把「孤儿模块会写 NULL 租户」列为遗留，这轮补上。

改动（`services/v12_closed_loop_service.py`）：

| 位置 | 改动 |
| --- | --- |
| `create_workorder` | INSERT 列名加 `tenant_id`，值由新增的 `_resolve_tenant_id()` 解析 |
| `create_workorders_from_inspection` | 把 `tenant_id` 透传给每一条 `create_workorder` |
| `seed_v12_demo_if_empty` | 循环前解析一次租户；并修掉一处**已经跑不起来**的插入 |

`_resolve_tenant_id(payload)` 取值顺序：调用方传的 `payload["tenant_id"]` → 退回
`record_persistence_service.single_user_tenant_id()`（即上一节那套「有用户的唯一租户」判定，
`_single_user_tenant_id` 因此改名为公开的 `single_user_tenant_id`）。这样即使将来接线时忘了传租户，
也不会再写出 NULL 行。

**顺带修掉的另一个坑**：播种函数里 `INSERT OR REPLACE INTO inspection_records VALUES (?, …×10)` 是
**定位插入**，而 `inspection_records` 现在是 **18 列**（后加过档案字段与 `tenant_id`），这条语句早就
插不进去了 —— 也就是说该模块在当前 schema 下**根本跑不起来**，一直没人发现是因为它没有路由引用。
已改成显式列名并带上 `tenant_id`。

实测（在副本上跑，未碰开发库）：

| 场景 | 结果 |
| --- | --- |
| `create_workorder` 不带 `tenant_id` | 落到 `tenant_id=1`（原来会写成 NULL） |
| `create_workorder` 显式传 `tenant_id=1` | 落到 1 |
| `seed_v12_demo_if_empty(force=True)` | 生成 7 条记录 + **16 条整改工单，全部 `tenant_id=1`，NULL 行 0** |

> 意外的印证：force 播种产生的工单数恰好是 **16**，与之前从开发库里发现的 16 条「待整改」完全吻合，
> 证实那批脏数据就是这个播种函数留下的。

#### 删除 `v12_closed_loop_service`（2026-09-19 追加）

上一节补完 `tenant_id` 后做了删除影响面评估，结论是**可以安全删除**，本轮执行（方案：删模块 + 改测试 + **表与数据都保留**）。

评估结论与证据：

| 维度 | 结论 |
| --- | --- |
| 生产代码依赖 | **0** —— `backend/main.py:256-349` 的注册列表里没有它，没有任何 router / service 导入，25 个公开函数全部只被模块内部调用；前端 `frontend/src`、移动端 `mobile_app/lib`、`e2e/` 检索 `v12` 均无相关命中 |
| HTTP 可达性 | 无任何路由能到达（不存在 `/api/v12` 前缀） |
| 独有数据表 | `hardware_events_v12`(7 行) / `knowledge_entries_v12`(8 行) / `qa_reference_traces_v12`(0 行)，除本模块外全仓库零读写 |
| 共享表 | 它也会 `CREATE TABLE IF NOT EXISTS inspection_records / work_orders`，但这两张表由 `record_persistence_service` 同样负责创建，删除不影响那 344 条工单 / 17 条档案 |
| 测试依赖 | 仅 `tests/test_runtime_db.py` 的一个用例（借其私有 `_connect` 做运行时库路径回归） |
| 运维 / 部署依赖 | `scripts/` / `deploy/` / `docker-compose*` / `Dockerfile` / CI / 根目录脚本全部零命中 |

改动：

| 文件 | 改动 |
| --- | --- |
| `backend/services/v12_closed_loop_service.py` | 删除（约 860 行） |
| `backend/tests/test_runtime_db.py` | `writers` 字典去掉 v12 一项，docstring 同步 |
| `backend/P0_AUDIT_REPORT.md` | 从「直接 sqlite3 调用」清单里去掉；余下正好 7 项，与文中「至少7个」一致 |
| `backend/services/record_persistence_service.py` | 词表归一的注释改为「已删除的旧模块」，并说明这段归一为何保留 |

按方案保留未动：

- 3 张 `*_v12` 表与其中 15 行数据 —— 不 `DROP`（不可逆且无收益）
- 共享表里由它播种出的历史数据：`REC-V12-001..007`（7 条档案，`created_at` 为 2026-05-28）与那批工单
  （已归一到「待派单」）—— 它们现在已是合法演示数据，删掉反而会让巡检档案看着像丢了数据
- `LEGACY_WORKORDER_STATUS_MAP` / `_normalize_legacy_workorder_status()` —— 写入方虽已删除，
  但其它部署的历史库里可能仍有 待整改 / 已完成 / 已复查 等旧取值，保留这段幂等归一

#### 删除 `v128_runtime_hotfix`（2026-09-19 追加）

上一条遗留就是它，同一流程再走一遍。

评估（与 v12 同类，逐项已核实）：

| 维度 | 结论 |
| --- | --- |
| HTTP 可达性 | **不可达** —— `main.py` 全文检索 `v128` 零命中（既没 import 也没 `include_router`）；并用 `app.openapi()` 实证：350 条路径里**没有任何 `/api/v128`** |
| 生产代码依赖 | **0** —— 没有任何 router / service 导入它（它本身是个 router 文件） |
| 独有数据表 | 6 张 `v128_*`：`v128_devices`(6) / `v128_device_telemetry`(42) / `v128_hardware_events`(5) / `v128_inspection_records`(5) / `v128_workorders`(5) / `v128_qa_citation_logs`(0) |
| 对共享表的写入 | **无** —— 全文检索其 INSERT / UPDATE / DELETE 全部落在 `v128_*` 上；对 `inspection_records`(:277)、`fault_tickets`(:321)、`model_configs`(:569) 只有读 |
| 文档依赖 | `docs/test_report.md` 早前把它当可用接口写了（`/api/v128`），与实际不符 |

改动：

| 文件 | 改动 |
| --- | --- |
| `backend/routers/v128_runtime_hotfix.py` | 删除（694 行） |
| `backend/tests/test_runtime_db.py` | `writers` 去掉 v128 一项；并删掉专测它的用例 `test_v128_no_longer_guesses_database_file`（该用例整个围绕它，模块没了无从断言） |
| `backend/P0_AUDIT_REPORT.md` | 从「直接 sqlite3 调用」清单去掉，计数由「至少7个」改回「至少6个」 |

按与 v12 相同的方案保留未动：6 张 `v128_*` 表与其 63 行数据不 `DROP`。

#### 清理无归属的 9 张历史表（2026-09-19 追加）

上一条遗留收尾：两个模块删完后，这 9 张表在全仓库已无任何代码引用（按表名检索零命中），确认无用后清理。

**先备份再删** —— 用项目自带的 `db_backup.py`（它会把主库与运行库一起备份并写 sha256）：

```
python db_backup.py backup
  → backups/fire_ai_agent_sqlite_20260919_214855.db   (7,675,904 bytes)
  → backups/fire_agent_runtime_20260919_214855.db     (1,363,968 bytes)
```

删除前先只读校验备份：`integrity_check = ok`，9 张表齐全、共 **78 行**（逐表与删除前一致，见下表）。
删除脚本先断言 9 张表都存在再 `DROP`，避免误删。

| 项 | 前 | 后 |
| --- | --- | --- |
| 运行库表数 | 16 | **7** |
| 被删表 | — | `hardware_events_v12` / `knowledge_entries_v12` / `qa_reference_traces_v12` / `v128_devices` / `v128_device_telemetry` / `v128_hardware_events` / `v128_inspection_records` / `v128_workorders` / `v128_qa_citation_logs` |
| 保留表 | — | `inspection_records` / `work_orders` / `inspection_reports` / `learning_attempts` / `rag_entries` / `hardware_events` / `operation_logs` |
| 共享表数据 | 344 / 17 / 49 | **344 / 17 / 49（未变）** |

顺带清掉了两个已删模块残留在 `__pycache__` 里的 `.pyc`。

> 备份保留在 `backend/backups/`（默认保留 14 天，由 `db_backup.py prune` 管理）。
> 万一要回滚：`python db_backup.py restore <备份文件> --yes` 即可把运行库恢复到删除前的状态。

#### 已知遗留

本轮 v12 / v128 相关的遗留已全部处理完毕。

### 13.10 Android 模拟器联调：相机 / 扫码 / 定位 / WebSocket（2026-09-19 追加）

APK 打出来了、CI 也接上了，但「装到设备上到底能不能用」此前只有后端契约层面的单测。
这一轮用 Android 模拟器把四条硬件相关的链路真机式跑通。

#### 联调环境

| 项 | 值 |
| --- | --- |
| 模拟器 | Android Emulator 37.1.11 + AVD `fire_api36`（Android 16 / API 36 / `google_apis` x86_64） |
| 加速 | WHPX（Windows Hypervisor Platform），`emulator -accel-check` 返回 `accel: 0` |
| AVD 配置 | Pixel 8 机型 1080x2400 / `hw.ramSize=4096` / `dataPartition 8G` / 相机 `hw.camera.back=virtualscene` |
| App | `app-x86_64-release.apk`（`com.fire.inspection.mobile` versionName 1.0.0），`API_BASE_URL` 编译为 `http://10.0.2.2:8000` |
| 后端 | `python -m uvicorn main:app --host 0.0.0.0 --port 8000`（全局解释器 `D:\Python\python314\python.exe`） |

#### 结论一览

| 项 | 结果 | 关键证据 |
| --- | --- | --- |
| WebSocket | **通过** | 连接后首帧 `auth` 成功（后端日志 `WebSocket 连接建立: tenant_id=1 user=admin`）；切后台断开后**自动重连**（22:16:41 断 → 22:18:24 重连；22:23:55 断 → 22:25:59 重连；22:29:23 断 → 22:30:06 重连），走的是 `ws_service.dart` 的指数退避 |
| 相机 | **通过** | 权限弹窗（标题「智慧消防巡检」）→ 取景 → 拍照 → 缩略图挂到表单（`70-emu-04` ~ `70-emu-07`） |
| 定位 | **通过**（需先开 GMS Location Accuracy） | 提交后主库 `inspection_records.id=5` 落库 `description = 'emulator smoke test\n【定位】39.909300,116.397498'`（`70-emu-19`） |
| 扫码 | **通过** | 识别二维码 `HYD-B-001` → 跳「设备详情 · B区室内消防栓」（`70-emu-23`） |

其余顺带验证：登录 admin → `/api/auth/me` → `/api/mobile/home`（3 告警 / 1792 设备）→ `/api/alert/list` →
`/api/workorders` → `/api/devices` → `/api/notifications/summary` 全部 200；表单必填校验提示
「请选择设备或填写现场位置」正常。

#### 定位：卡在 Google Play Services 的「Location Accuracy」

定位是四条里唯一一开始不通过的，排查过程值得留档。

现象：提交巡检上报后端往返仅 **0.26s**（远小于 `_readPosition()` 的 10s 超时），`description` 里没有
`【定位】` 前缀 —— 说明 `getCurrentPosition()` 是**立即抛异常**后被 `catch (_) → null` 降级掉的，不是超时。
`dumpsys location` 里 `com.fire.inspection` 零命中，各 provider 的 `ProviderRequest[OFF]`。

中间试过但**不是**根因的两条路：

| 尝试 | 结果 |
| --- | --- |
| `adb emu geo fix 116.397 39.909` 注入坐标 | `last location=null` —— 无监听者时坐标被直接丢弃，不能用来判断 App 好坏 |
| `cmd location providers add-test-provider` | `SecurityException: android from uid 2000 not allowed to perform MOCK_LOCATION` |

真正线索在 logcat：提交瞬间弹出了
`com.google.android.gms/com.google.android.location.settings.LocationSettingsCheckerActivity`。
即 GMS 在**「Improve Location Accuracy」未开启**时拒绝对外提供位置（首次权限弹窗里选了「No thanks」）。

修复动作（不改代码）：

1. `adb shell am start -n com.google.android.gms/.location.settings.LocationAccuracyNonwearableActivity`
   （该 activity 用 `pm resolve-activity -a com.google.android.gms.location.settings.LOCATION_ACCURACY` 查到；
   系统设置里的「位置」页只有说明文字、没有开关，开关在 GMS 这个页面里）
2. 打开 `Improve Location Accuracy`（`70-emu-16` → `70-emu-17`）
3. `adb emu geo fix 116.3975 39.9093`（参数顺序是**经度 纬度**），之后 App 内提交

结果：`dumpsys location` 中 `gps` 与 `fused` 都拿到 `39.909300,116.397498`，巡检上报落库带上定位前缀。

> 这是模拟器环境问题，不是 App 缺陷：真机上只要系统定位与 GMS Location Accuracy 正常，
> `_readPosition()` 就能取到坐标；取不到时按设计降级为无定位上报，不阻断提交。

#### 扫码：模拟器里怎么让相机「看到」二维码

`mobile_scanner` 走的是相机实时帧，模拟器默认给的是虚拟场景，里面没有二维码可扫。踩了两个坑：

| 坑 | 真相 |
| --- | --- |
| 替换 `emulator/resources/poster.png` 无效 | `poster.png` 是 `Toren1BD.posters` 里的**墙面海报**，不在默认取景范围内；默认视野里那块大屏的贴图在 `Toren1BD.mtl` 里叫 **`TV`**，SDK 根本没带这个文件，所以一直渲染成「棋盘 + 绿块」的缺图占位 |
| 用 `-virtualscene-poster wall=<file>` 也绕不开取景 | 还是得先把镜头转过去 |

**最终方案**：`emulator -help-all` 里有一条 `-camera-back imagefile:<filename>`，直接让后置相机渲染一张图片：

```powershell
emulator -avd fire_api36 -gpu auto -no-snapshot-load -no-boot-anim `
  -camera-back imagefile:F:\android-sdk\emulator\resources\qr_device.png
```

二维码内容用后端 `devices` 表里真实存在的 `device_code`（`HYD-B-001`，`qrcode[pil]` 生成）。
一个细节：App 的相机预览对图片做了放大裁切，**居中放单个二维码会被裁掉右半**；改成在 1600x1200
画布上平铺 20 个 290px 二维码后就稳定识别了。

端到端证据（后端日志）：

```
GET /api/devices?page=1&page_size=5&keyword=HYD-B-001  → 200
GET /api/devices/2/detail                              → 200
```

界面随之跳到「设备详情 · B区室内消防栓」（设备编号 `HYD-B-001`），即 `scan_page.dart` 里
「命中 `device_code` 精确比对 → `pushReplacementNamed('/device-detail')`」这条路径走通。

#### 巡检上报的数据落库（两条链路都到位）

| 存储 | 记录 | 内容 |
| --- | --- | --- |
| 主库 `inspection_records` | `id=5` | `location='Building A'`、`description='emulator smoke test\n【定位】39.909300,116.397498'`、风险分 50 / 高风险 |
| 运行库 `inspection_reports` | `RPT-20260919222612-C65C` | `inspection_id='REC-M-5'`、`tenant_id=1`、`source='mobile'`，报告正文含同一串定位 |

这正是 13.8 的「移动端 → Web 巡检档案」镜像链路（`_mirror_report_to_archive`）在真实设备上的复验。

#### 清理

模拟器侧为联调做的改动**已全部还原**（`emulator/resources` 下 `poster.png`、`Toren1BD.posters` 恢复原样，
临时的 `TV*` / `qr_device.png` 已删除），只保留 AVD 本身；项目侧无代码改动。
截图归档在 `docs/assets/test-report/70-emu-01..23-*.png`（调试过程中的中间截图已删除）。

#### 遗留（本轮未处理）

- `start_fast.bat` 引用的 `.venv` 在本机不存在，本轮统一用全局解释器；脚本本身未改
- Gradle 8.14 / AGP 8.11.1 / Kotlin 2.2.20 低于 Flutter 当前建议值，能出包但会有升级提示
- `flutter run` 在 ASCII 联接目录（`F:\mob_ascii`）下偶发 Kotlin 编译守护进程崩溃
  （`e: Daemon compilation failed: null`），本轮改用已构建好的 release APK 绕过，未根治

### 13.11 GitHub 流水线首次实跑（2026-09-19 追加）

12.5 的遗留「流水线尚未在 GitHub 上实跑」到此关闭：把仓库推上 GitHub，真跑了一次。

#### 仓库与首次推送

| 项 | 值 |
| --- | --- |
| 远端 | `https://github.com/fwl414/fire`（public） |
| 仓库根 | 项目目录本身，`git init -b main` |
| 首次提交 | `6b7ba62` —— 712 文件 / 197,780 行 |
| 认证 | 系统级 `credential.helper=manager`（Git Credential Manager），无需 PAT |

入库前补的 `.gitignore`（原有规则只挡了 `node_modules/` 与 `fire_ai_agent*.db`，漏得不少）：

| 被挡住的 | 原因 |
| --- | --- |
| `.env.staging` | **含真实密钥**（Postgres 口令、`JWT_SECRET_KEY`、`METRICS_TOKEN`、Grafana 口令），文件头自己就写着「请勿提交到版本库」 |
| `*.db` / `*.db.*` / `backend/backups/` / `backend/data/_cleanup_backup_*/` | 运行库、备份、CI 结构校验库 |
| `backend/data/reports/`、`notification_read.json` | 运行时生成的巡检报告与通知已读状态 |
| `frontend/node_modules_old/` | 历史遗留旧依赖（含 9.45MB `esbuild.exe`） |
| `frontend/test-results/`、`playwright-report/` | Playwright 产物（各含 16MB `trace.zip`） |
| `backend/data/_cleanup_backup_*/fire_ai_agent.db.backup` 等 | `.db.*` 变体一律排除 |

另按「已暂存内容」扫了一遍硬编码密钥模式（`password|secret|token|api_key` + 16 位以上字面量）：
17 个命中全部是测试夹具与文档占位符（如 `"********"`），无真实凭据。

#### 触发覆盖：push 只跑 4 个作业

`ci-cd.yml` 共 8 个作业，但 **push 事件只覆盖 4 个** —— 这是首次实跑才看清的：

| 作业 | push | pull_request | workflow_dispatch |
| --- | --- | --- | --- |
| 后端测试（pytest 全量） | ✅ | ✅ | ✅（action=ci） |
| 前端构建 | ✅ | ✅ | ✅（action=ci） |
| 移动端 analyze + test | ✅ | ✅ | ✅（action=ci） |
| 生产镜像构建 | ✅ | ✅ | ✅（action=ci） |
| 移动端 APK 构建 | ⏭ | ✅ | ✅（action=ci） |
| 前端 E2E | ⏭ | ✅ | ✅（action=ci） |
| 发布到部署主机 | ⏭ | ⏭ | 仅 action=deploy |
| 回滚部署主机 | ⏭ | ⏭ | 仅 action=rollback |

原因在 `ci-cd.yml:143` 与 `:196` 的 `if`：
`github.event_name == 'pull_request' || (github.event_name == 'workflow_dispatch' && inputs.action == 'ci')`。
也就是说**光推 main 验证不到 APK 与 E2E**，要覆盖全部 6 个校验作业必须走 PR 或手动 `action=ci`。

#### run #1 结果：3 绿 1 红

| 作业 | 结果 |
| --- | --- |
| 移动端 analyze + test | success |
| 生产镜像构建 | success |
| 前端构建 | success |
| 后端测试（pytest 全量） | **failure**（步骤「全量测试」） |

#### 红灯根因：`test_cpu_and_network_need_two_samples` 是 flaky 用例

不是产品缺陷，是用例假设错了。证据链：

| 步骤 | 观察 |
| --- | --- |
| 同一 commit 连跑两遍 | 第一遍 `1 failed, 611 passed`；第二遍 `612 passed` —— 偶发 |
| 单独跑该用例 | 通过（冷启动时第一次 `host_snapshot()` 较慢，恰好跨过时间片） |
| 实测 `psutil.cpu_times()` 粒度 | 背靠背调用 20 次，**18 次 `delta <= 0`**；`gap=0.0s → delta=0.000000`，`gap=0.02s → 0.531250` |

机制：`_cpu_percent()` 在 `total_delta <= 0` 时**按设计返回 `None`**（首次无基准，不编数），
而用例在两次 `host_snapshot()` 之间没有任何等待 —— 只要两次调用落在同一个计数器时间片里就必然拿到 `None`。
Linux `/proc/stat` 的 USER_HZ 是 10ms 粒度（Windows 约 15.6ms），所以在 CI 上更容易踩到。

修复（`tests/test_system_metrics.py`）：两次采样之间等计数器真正推进（最多 20×20ms），
断言内容一条没改，**服务端行为不动**。改后连跑两遍全量均 `612 passed, 26 subtests passed`。

#### PR run #3：8 个作业全貌

push 只覆盖 4 个作业，所以另开 PR（`fix/flaky-cpu-sample-test` → `main`）走 `pull_request` 事件，
才把**从没跑过**的「移动端 APK 构建」与「前端 E2E」拉起来。8 个作业全部创建：

| 作业 | 结果 | 耗时 |
| --- | --- | --- |
| 移动端 analyze + test | success | 41s |
| 前端构建 | success | 1m9s |
| 生产镜像构建 | success | 52s |
| 移动端 APK 构建 | **success**（首次实跑，一次过） | 4m32s |
| 后端测试（pytest 全量） | **failure** | 33s（失败步骤本身 0s） |
| 前端 E2E | **failure** | 9m33s |
| 发布到部署主机 | skipped | — |
| 回滚部署主机 | skipped | — |

#### 失败一：后端测试 —— `pytest` 根本没装

```
Run python -m pytest tests/ -q
/opt/hostedtoolcache/Python/3.14.7/x64/bin/python: No module named pytest
Error: Process completed with exit code 1.
```

`backend/requirements.txt` 是**生产依赖**，不含 pytest；CI 装的正是它，所以命令 0 秒就退出
（失败步骤耗时 0s —— 根本没跑到用例）。本地能跑只是因为全局解释器装了 pytest 9.1.1，
与用例、与此前那个 flaky 测试都无关。

修复：新增 `backend/requirements-dev.txt`（`-r requirements.txt` + `pytest>=9.0`），
CI 的后端作业改成装它（pip 缓存键一并加上该文件）。生产镜像仍只装 `requirements.txt`。

#### 失败二：前端 E2E —— 4 failed / 3 flaky / 34 passed

| 失败用例 | 报错 |
| --- | --- |
| `realtime-push.spec.js:44` 令牌无效以 4401 关闭 | `Expected: 4401, Received: 1006` |
| `realtime-push.spec.js:53` 带令牌按令牌身份回话 | `应认证成功：{"ok":false,"code":1006}` |
| `realtime-push.spec.js:64` 推送后大屏立即刷新 | `Timeout 10000ms`，推送没到 |
| `data-screen.spec.js:230` 3D 场景建筑点击下钻 | `page.waitForURL` 超时（撞上 90s 用例超时） |

3 个 flaky（重试通过，不计失败）：`audit-log.spec.js:15`、`data-screen.spec.js:178`、
`system-monitor.spec.js:10`（磁盘值与页面值比对 —— 与刚修的 CPU 那个同类）。

**WebSocket 的 3 个失败是同一根因，而且本地必过**：本机用与 CI 相同的 Node 20 + Playwright 1.63
跑 `e2e/realtime-push.spec.js` 是 `3 passed`。CI 拿到的是 **1006（异常关闭，没拿到关闭帧）**，
即连接在到达后端前就断了 —— 而 HTTP 走同一个 Vite 代理是正常的（同批次的登录、大屏数据请求全 200）。
本轮先给用例装上诊断：失败时同时探一次「经 Vite 代理」与「直连后端 8010」，并把
`wasClean` / `readyState` / `onerror` 写进断言消息，下一轮 CI 就能直接判定断在代理还是后端。

**3D 下钻不是环境问题，是用例自己太慢**：原实现先扫完整张画布（9×7＝63 次 move + 读 cursor）
再回头点第一个命中点。CI 上这一扫要几十秒，把 90s 用例预算耗光；而且场景每帧都在渲染，
早先记下的坐标会漂移，回头点很可能已经落空。已改成「找到就立刻点」（命中即点，并在每轮重新量一次
`boundingBox`），整体给 45s 预算。本地回归 `4 passed (24.7s)`，其中 3D 用例 **14.5s**。

#### PR run #5：后端转绿，WebSocket 的根因是**生产依赖缺失**

装上测试期依赖后 `后端测试` 直接 **success（67s）**，8 个作业里 7 个绿/按设计跳过，只剩 E2E 红。

上一轮加的诊断给出了决定性证据 —— **走代理和直连后端同时失败**：

```
经代理： ws://127.0.0.1:5273/ws/notifications →
        {"ok":false,"code":1006,"wasClean":false,"readyState":3,"sawError":true}
直连后端：ws://127.0.0.1:8010/ws/notifications →
        {"ok":false,"code":1006,"wasClean":false,"readyState":3,"sawError":true}
```

`sawError:true` + `readyState:3` 说明**握手就没成功**，与 Vite 代理无关。顺着查依赖：

| 环境 | WebSocket 实现 |
| --- | --- |
| 本机（全局 Python） | `websockets 16.0` + `wsproto 1.3.2` 都在 → WS 正常，本地三个用例恒过 |
| `requirements.txt` | 只有 `uvicorn>=0.35.0`，**既没有 `websockets` 也没有 `wsproto`** |
| 生产 Dockerfile | `COPY backend/requirements.txt` + `pip install -r requirements.txt` → 同样没有 |

`pip install --dry-run -r requirements.txt` 的实证（修复前）：

```
Would install ... uvicorn-0.53.0      ← 只有 uvicorn，列表里没有 websockets / wsproto
```

uvicorn 自身不带 WS 协议实现，缺了它 `/ws/notifications` 的升级握手必然失败，浏览器侧就是
`onerror` + 1006。**所以这不只是 CI 问题，而是生产缺陷**：按当前 Dockerfile 构建的镜像里，
Web 端大屏实时推送与移动端 WebSocket 全都连不上，而且这个缺口从没被任何单测覆盖
（后端 WS 用例走 `TestClient` 的进程内 ASGI 传输，不需要真实 WS 实现）。

修复（`backend/requirements.txt`）：补 `websockets>=16.0`。刻意不引 `uvicorn[standard]` ——
那会连带 `httptools` / `uvloop` / `watchfiles`，给镜像构建加不必要的原生编译面。

另两个 E2E 失败（本轮一并修）：

| 用例 | 现象 | 改动 |
| --- | --- | --- |
| `audit-log.spec.js:15` | `login()` 里 `waitForURL(/dashboard/)` 超时 30s；重试时又报 `Execution context was destroyed`（登录后应用仍在跳转） | `login()` 超时提到 60s（CI 首次访问要等 Vite 现场转译整个应用）；`currentToken()` 改用 `waitForFunction`，跨导航重试后再取 token |
| `data-screen.spec.js:230` | 改成「命中即点」后，点击已跳转而画布从 DOM 消失，下一次 `canvas.evaluate` 等 20s 超时 | 读 cursor 加 `.catch(() => '')`（读不到当未命中）；点击后用 `waitForURL(..., 1500)` 等导航落地 |

本地回归：`realtime-push + data-screen + audit-log` → **12 passed（1 flaky，非改动项）**；
并把本机 `websockets` 升到 CI 会装的 17.1 再跑一次 WS 用例 → `3 passed`，确认版本组合没问题。

#### run #7：全绿

补上 `websockets` 后同一分支再跑一轮（`a7313ac`），8 个作业里 6 个 success、2 个按设计 skipped：

| 作业 | 结果 | 耗时 |
| --- | --- | --- |
| 后端测试（pytest 全量） | success | 68s |
| 前端构建 | success | 51s |
| 移动端 analyze + test | success | 47s |
| 生产镜像构建 | success | 44s |
| 移动端 APK 构建 | success | 363s |
| **前端 E2E** | **success** | 477s（用例步骤 **404s**；上一轮是 586s 且失败） |
| 发布到部署主机 | skipped | — |
| 回滚部署主机 | skipped | — |

三个 WS 用例在 CI 里**首次通过**；E2E 用例步骤耗时也从 586s 降到 404s —— 3D 用例不再空等
90s 超时、audit-log 不再重试。

至此 PR #1 上四项修复全部经真实 CI 验证：

| # | 修复 | 首次通过 |
| --- | --- | --- |
| 1 | `test_cpu_and_network_need_two_samples` 偶发失败（计数器粒度） | run #3 起 |
| 2 | 后端测试作业缺 pytest（`requirements-dev.txt`） | run #5 起 |
| 3 | **WebSocket 生产依赖缺失（`websockets>=16.0`）** | run #7 起 |
| 4 | E2E 的 login 冷启动超时与 3D 扫描导航竞态 | run #7 起 |

> 仍未实跑的只剩 `deploy` / `rollback`：两者要 `workflow_dispatch` + 仓库配置
> `DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_SSH_KEY` / `DEPLOY_PATH` 四个 Secrets，且本机没有
> 可用的部署主机，因此这两个作业目前只有「结构上存在 + 守卫步骤会明确报缺哪个 Secret」的保证。

#### 生产镜像实测：WS 修复前后对比

这条不能只靠推理（CI 只验证「镜像能不能构建」，不验证「跑起来 WS 通不通」），所以在真实镜像上做了前后对比：
本机 `docker build` 出镜像 → 起容器 → 用 `websockets` 客户端发起**真实握手**（故意带无效 token）。

| 镜像 | 镜像内依赖 | WS 探测结果 |
| --- | --- | --- |
| 旧（修复前构建的 `fire-ai-agent-backend:py314-check`） | `uvicorn 0.53.0`，无 websockets / wsproto | `HANDSHAKE_FAILED: InvalidStatus server rejected WebSocket connection: HTTP 404` |
| 新（修复后构建的 `fire-ai-agent:ws-fix`） | `uvicorn 0.53.0` + `websockets 17.1` | `CLOSED: code=4401 reason=令牌无效或已过期` |

新容器日志是 `INFO: ... "WebSocket /ws/notifications" [accepted]` —— 握手成功、首帧被后端收到，
才会按设计回 4401（探测故意用无效 token，所以 4401 正是期望值）。旧镜像**连握手都过不去**，
这就是「生产里实时推送一直不可用」的实证。

构建耗时：pip 层 213.8s（requirements 变更导致缓存失效重装），镜像 1.26GB。
验证用的两个容器已删除；两个镜像（各约 1.25GB）保留在本机，不需要时
`docker rmi fire-ai-agent:ws-fix fire-ai-agent-backend:py314-check` 即可。

#### run #11 与合并进 main

文档修正推上去后又跑了一轮，同样全绿（`509629b`，8 个作业 0 失败）：

| 作业 | 结果 | 耗时 |
| --- | --- | --- |
| 后端测试（pytest 全量） | success | 62s |
| 前端构建 | success | 66s |
| 移动端 analyze + test | success | 41s |
| 移动端 APK 构建 | success | 298s |
| 生产镜像构建 | success | 46s |
| 前端 E2E | success | 382s |
| 发布到部署主机 / 回滚部署主机 | skipped | — |

随后 **PR #1 已合并进 `main`**（9 个提交），main 从此带上全部四项修复。

#### 把「镜像跑起来验 WS」加进 CI

生产镜像那条暴露的不只是依赖漏项，还是**流程缺口**：`docker-build` 作业只验证「镜像能不能构建」，
从不把镜像跑起来；`release.sh` 的健康检查也只探 HTTP `/health`。于是「构建成功但功能不可用」
这类缺陷可以一路绿灯发到线上 —— 本次的 WS 缺陷正是如此。

改动（`.github/workflows/ci-cd.yml` 的 `docker-build` 作业）：

| 改动 | 原因 |
| --- | --- |
| 构建步骤加 `load: true` | buildx 默认只把镜像留在构建缓存里，不载入本地镜像库，下一步无法 `docker run` |
| 新增「冒烟：起容器并验证 WebSocket 可升级」 | 起容器 → 等 `/health` → 按 WebSocket 协议发一次升级请求 → **必须**含 `101 Switching Protocols`，否则打印容器日志并以 `::error::` 失败退出 |

判据的本地验证（先验证「这条检查本身对不对」，不依赖 CI）：

| 场景 | 响应 | 检查结果 |
| --- | --- | --- |
| uvicorn 正常运行 | `HTTP/1.1 101 Switching Protocols` | 通过 |
| `uvicorn --ws none`（等价于缺 WS 实现） | `HTTP/1.1 404 Not Found` | 失败（正是旧生产镜像的表现） |

用 `curl` 手工构造升级请求而不引第三方 WS 客户端：免装依赖，且「101 vs 4xx」这个判据
足够卡住本次的缺陷类型。`bash -n` 语法检查亦通过。

CI 实跑（run #16 的 `docker-build`，作业 94s、其中冒烟 15s）：

```
等待 /health 就绪…
就绪（第 3 次探测）
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
WebSocket 升级正常（101 Switching Protocols）
```

> `/health` 恒返回 HTTP 200（healthy / degraded 体现在 body），所以就绪循环用它判断「容器起来了」是可靠的。
> 探测返回 `curl: (28) ... timed out` 是**预期现象**：升级成功后连接会保持打开，curl 按 `--max-time` 收尾，
> 但响应头已经拿到，判据仍成立。

#### 查 Actions 日志的办法

`/actions/jobs/{id}/logs` 匿名访问返回 `Must have admin rights`，`workflow_dispatch` 也要 token。
可行路径：**在内置浏览器里登录 GitHub 后看 Web UI 的作业页面** ——
每个步骤是 `<details class="CheckStep">`，失败步骤默认展开，日志正文就在 DOM 里
（长日志分段渲染，需要边滚边取）。本次两个失败的根因都是这么读出来的。

#### 本轮遗留

- 仓库当前为 **public**，代码与 `docs/`（含审计报告、测试报告、截图）均已公开；如需转私有：
  Settings → 最下方 Danger Zone → Change repository visibility。
- E2E 的 flaky 用例尚未加固（重试可过，不阻塞流水线）：`data-screen.spec.js:129/178`、
  `system-monitor.spec.js:10` 等，均为「本地采样值 vs 页面值比对」或长等待型。
- **生产镜像需要重新构建**才能带上 `websockets`；正在跑的部署若依赖实时推送，升级后要验证一次
  `/ws/notifications` 能正常握手。
- 本机访问 GitHub 要看 Clash Verge 的状态：它开着时 DNS 会把 `github.com` 解析成 fake-ip
  （`198.18.0.57`）而系统代理常是关的（`ProxyEnable=0`），此时直连必然 TLS 握手失败，
  `git push` 前要先 `$env:HTTPS_PROXY="http://127.0.0.1:7897"`（或把 Clash 的「系统代理」打开）；
  它关掉时直连正常，不需要代理。

