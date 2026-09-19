# 智慧消防巡检 App（Flutter）

一线人员的移动工作台，对接后端 `/api/mobile/*`（移动端协同）与通用业务接口。

## 运行

```powershell
flutter pub get

# Android 模拟器：10.0.2.2 是宿主机的回环地址
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# 真机：换成开发机的局域网 IP
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
```

后端要先起来（仓库根目录 `start_all.bat`，或 `cd backend && python -m uvicorn main:app --port 8000`）；
账号用后端已有账号，首次部署可用 `backend/create_admin.py` 建管理员。登录页底部会显示当前后端地址，方便真机排查。

## 校验

```powershell
# 静态分析：本仓库目录名含非 ASCII 字符会让 `flutter analyze` 崩（原因见下），
# 用这个包装脚本（自动建 ASCII 目录联接）或直接 dart analyze
.\flutter_analyze.bat
dart analyze            # 不想建联接时的替代方案，规则与 flutter analyze 相同

flutter test            # 离线单元 + Widget 测试（本机：22 passed）

# 真实后端联调冒烟：先在另一个终端起后端（uvicorn main:app --port 8000），
# 它会真的登录、拉首页/告警/工单/设备/记录/通知、再登出；后端没起时整组跳过
flutter test test/live_api_smoke_test.dart

flutter build web       # 整包编译验证（本机通过）
```

> **为什么 `flutter analyze` 要包一层**：`flutter analyze` 会把项目根路径通过 LSP 报文交给分析器，
> 路径含非 ASCII 字符（本目录所属文件夹名带「副本」）时报文长度与实际字节数对不上，分析器直接崩：
> `FormatException: Unexpected end of input ... LspByteStreamServerChannel._readMessage`。
> 同一份代码放在纯 ASCII 路径下分析正常（实测 `No issues found`）。
> `flutter_analyze.bat` 用 `mklink /J`（不需要管理员权限）在 `F:\mob_ascii` 建一个指向本目录的联接再分析，
> **源码不复制、目录不改名**；换个位置可先 `set FLUTTER_ASCII_LINK=D:\mob_ascii`。
> `flutter test` 与 `flutter build` 不受影响。要治本就把仓库目录改成纯 ASCII 名。

## Android 模拟器联调

四条硬件相关链路（相机 / 扫码 / 定位 / WebSocket）已在 Android 16（API 36，`google_apis` x86_64）上跑通，
结论与截图见 `docs/test_report.md` 13.10。这里只留**在模拟器上复现时要先做的事**：

```powershell
# 1) 装包：后端 API 地址已编译进包（10.0.2.2 是宿主机回环）
F:\android-sdk\platform-tools\adb.exe install -r build\app\outputs\flutter-apk\app-x86_64-release.apk

# 2) 定位：必须先在 GMS 里打开「Improve Location Accuracy」，否则 App 取不到坐标
adb shell am start -n com.google.android.gms/.location.settings.LocationAccuracyNonwearableActivity
#    再注入坐标（参数顺序是 经度 纬度），之后在 App 内提交巡检
adb emu geo fix 116.3975 39.9093

# 3) 扫码：默认虚拟场景里没有二维码，用 imagefile 模式让后置相机渲染一张二维码图片
emulator -avd <你的AVD> -camera-back imagefile:F:\path\to\qr_device.png
```

- **定位取不到不是 App 的 bug**：`lib/pages/inspection_page.dart` 的 `_readPosition()` 任何失败都返回 `null`，
  降级为「无定位上报」，不阻断提交。模拟器上要么开上面那个 GMS 开关，要么换真机。
- **二维码别只放一个**：App 的相机预览会对图片做放大裁切，居中的单个二维码会被裁掉右半；
  建议在 1600x1200 画布上平铺若干个小二维码。内容用后端 `devices` 表里真实存在的 `device_code`，
  扫码页会按 `device_code` 精确比对后跳设备详情。
- 虚拟场景里的墙面海报是 `emulator/resources/poster.png`（由 `Toren1BD.posters` 摆放），
  **不在默认取景范围内**，换它没用；默认视野里那块大屏的贴图在 `Toren1BD.mtl` 里叫 `TV`，SDK 未附带，显示为缺图占位。

## 打包 APK

### 工具链

| 组件 | 版本 | 路径 |
| --- | --- | --- |
| Flutter | 3.47.5 | `F:\flutter` |
| JDK | Temurin 17.0.20.1 | `F:\jdk\jdk17` |
| Android SDK | platform-tools 37.0.1 + build-tools 36.0.0 + platform android-36 | `F:\android-sdk` |

`JAVA_HOME` / `ANDROID_HOME` / `ANDROID_SDK_ROOT` 已写入用户环境变量。
`F:\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat --list_installed` 可查已装组件。

### 构建

```powershell
cd mobile_app
.\build_apk.bat                          # 默认 http://10.0.2.2:8000（Android 模拟器回环）
.\build_apk.bat http://192.168.1.10:8000 # 真机：开发机局域网 IP
.\build_apk.bat https://fire.example.com # 已上 HTTPS 的部署
```

`build_apk.bat` 自动设好 `JAVA_HOME`/`ANDROID_HOME`，并走 `F:\mob_ascii` 的 ASCII 联接（同 `flutter_analyze.bat`）。

`API_BASE_URL` 通过 `--dart-define` **编译进包**，必须在构建时给，装完改不了。

产物在 `build/app/outputs/flutter-apk/`：

| 文件 | 体积 | 用途 |
| --- | --- | --- |
| `app-release.apk` | 66.6 MB | 通用包，含 arm64-v8a / armeabi-v7a / x86_64 |
| `app-arm64-v8a-release.apk` | 24.4 MB | 现场分发推荐（2019 年后的手机） |
| `app-armeabi-v7a-release.apk` | 20.4 MB | 老旧 32 位机型 |
| `app-x86_64-release.apk` | 26.8 MB | 模拟器 |

分 ABI 包需额外加 `--split-per-abi`，脚本默认只出通用包。注意分 ABI 包的 `versionCode` 是 `2001`，
通用包是 `1`，**同一台设备不要混装这两类包**，否则会被系统判为降级而拒绝安装。

### 签名

release 用 `android/app/fire-release.jks`（RSA 2048，有效期 10000 天，别名 `fire-release`）签名，
口令在 `android/key.properties`。两者都已写进 `.gitignore`，**不要提交**。
`key.properties` 不存在时构建自动回退到 debug 签名，保证新克隆的仓库仍能直接 `flutter run` / `flutter build`。

> ⚠️ 把 `fire-release.jks` + `key.properties` 另外备份一份。丢失这份 keystore 后，
> 已装机的 App 就无法覆盖升级，只能让用户卸载重装；换口令或换 keystore 同样会因签名不一致装不上。

### 明文 HTTP

现场部署多为「内网服务器 + HTTP」，而 Android 9（API 28）起默认禁止明文流量，不放开会完全连不上后端。
`android/app/src/main/res/xml/network_security_config.xml` 里 `cleartextTrafficPermitted="true"`；
后端切到 HTTPS 后把该值改成 `false` 即可整体收紧，不需要改 Java/Kotlin 代码。

### 包名 / 版本 / 图标

- 包名 `com.fire.inspection.mobile`，`applicationId` 与 `namespace` 同步，`MainActivity` 位于 `android/app/src/main/kotlin/com/fire/inspection/mobile/`
- iOS / macOS 的 bundle id、Linux 的 `APPLICATION_ID`、Windows 的 `CompanyName` 同为 `com.fire.inspection.mobile`；各平台显示名统一为「智慧消防巡检」
- 全项目版本统一为 `1.0.0`（根 `VERSION`、`backend/pyproject.toml`、`frontend/package.json`），本包为 `1.0.0+1`
- `minSdk 24`（Android 7.0）/ `targetSdk 36` / `compileSdk 36`
- 版本号取 `pubspec.yaml` 的 `version: 1.0.0+1`，`+` 前是 versionName、`+` 后是 versionCode
- 图标：`res/mipmap-*/ic_launcher.png` 与 `ic_launcher_round.png`，另配 `res/mipmap-anydpi-v26/` 自适应图标
  （前景 `drawable/ic_launcher_foreground.xml`、背景 `drawable/ic_launcher_background.xml`），启动闪屏复用同一前景
- `application` 上还设了 `android:allowBackup="false"`：App 把 JWT 存在 SharedPreferences，
  关掉备份可避免令牌随 adb backup / 云备份被导出

### CI

`.github/workflows/ci-cd.yml` 里的两个作业（在仓库根目录跑，`working-directory: mobile_app`）：

| 作业 | 触发 | 内容 |
| --- | --- | --- |
| `mobile-analyze-test` | push / PR / 手动 | `flutter pub get` + `flutter analyze --fatal-infos` + `flutter test` |
| `mobile-apk` | PR / 手动 action=ci | `flutter build apk --release`，APK 上传为 `mobile-apk` 产物 |

CI 里的 `API_BASE_URL` 取仓库变量 `vars.API_BASE_URL`（未配置则退回 `http://10.0.2.2:8000`），
只用于验证能不能出包；正式分发包用 `build_apk.bat <真实后端地址>`。
`test/live_api_smoke_test.dart` 在后端未启动时自动跳过，CI 中不会误报失败。

> 构建时会提示 Gradle 8.14 / AGP 8.11.1 / Kotlin 2.2.20 版本偏低（Flutter 建议 Gradle ≥9.1、AGP ≥9.0.1、Kotlin ≥2.3.20）。
> 目前只是弃用预警，不影响出包；升级三件套属于破坏性改动，需单独验证。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `lib/main.dart` | 入口、路由表、启动鉴权门（AuthGate）、主框架（5 个 tab + 扫码入口 + 通知角标） |
| `lib/services/api_client.dart` | HTTP 底座：Bearer 注入、401 自动刷新并重放、超时、错误文案提取、响应解包 |
| `lib/services/api_service.dart` | 业务接口层（所有后端调用集中在此）+ 解析辅助 `asMap/asMapList/textOf/intOf` |
| `lib/services/app_services.dart` | 全局 `api`、`session`（用户信息 / 未读通知）、`alertPushTick`（推送刷新计数） |
| `lib/services/ws_service.dart` | `/ws/notifications` 客户端：首帧 token 鉴权、心跳、指数退避重连 |
| `lib/pages/` | 登录、首页、巡检、工单、告警、我的；设备台账、巡检记录、消防问答、消息通知、扫码；4 个详情页 |
| `lib/widgets/common.dart` | 共用组件（三态视图 / 状态标签 / 信息行 / 卡片）与时间、颜色格式化 |

## 改动前请先知道的几个对接坑（代码里已处理）

- **后端没有统一响应包装**：`/api/records`、`/api/faults` 返回裸数组，`/api/dashboard/stats` 返回裸对象，
  `/api/alert/list`、`/api/devices`、`/api/workorders` 返回 `{items,total,...}`，只有少数接口是 `{ok,code,message,data}`。
  统一由 `ApiClient._unwrap` 判断，页面取值一律走解析辅助函数，**不要强转 `as Map<String,dynamic>`**。
- **参数形式不统一**：登录 / 刷新 / 改密 / 消防问答 / 故障状态在后端是 **Form**（`application/x-www-form-urlencoded`），
  其余多为 JSON。
- **巡检记录有两套存储**：Agent 写主库 `inspection_records`（`/api/records`、首页统计读它），
  Web「巡检档案 / 报告打印 / 复查」读运行库 `inspection_records`（`record_persistence_service`）。
  Web 巡检页是「analyze 写主库 + `POST /api/records/save-inspection` 写运行库」两步，
  `/api/mobile/report` 也必须两步都做（见 `routers/mobile.py` 的 `_mirror_report_to_archive`），
  否则现场上报在 Web 巡检档案里看不到。档案 id 用 `REC-M-<主库记录id>` 保证幂等。
- **工单状态机只认**：待受理 / 处理中 / 待复查 / 已完成 / 已关闭。
  历史遗留的「待处理」与「待受理」等价（后端已做兼容），新写入一律用「待受理」；
  传其它取值会被 `/api/workorders/{id}/status` 拒绝（400）。
- **状态值两套**：工单状态只认中文（待受理 / 处理中 / 待复查 / 已完成 / 已关闭），
  告警状态只认英文（pending / processing / resolved）。
- **时间字段**是 UTC 的 ISO 字符串且常不带 `Z`（如 `2026-09-19T04:55:01.854600`），
  展示必须用 `widgets/common.dart` 里的 `formatShortTime/formatFullTime/formatRelativeTime`，直接 `DateTime.parse` 会差 8 小时。
- **令牌续期**：`/api/auth/refresh` 自身也要求 access token 仍然有效，所以只能「提前续期」（默认剩余不足 60 分钟时续），
  一旦过期就必须重新登录 —— 这是后端契约决定的，不是 App 的取舍。
- Android 联网/相机/定位权限已声明在 `android/app/src/main/AndroidManifest.xml`（main，不是只有 debug）。
