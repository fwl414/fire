# 智慧消防管理系统 - 企业化 P0 基线静态审计报告

**项目基线**: V1.0.0
**审计日期**: 2026-09-09
**审计范围**: 后端源码静态审计 + 轻量测试
**审计方法**: 路由枚举、代码扫描、依赖分析、配置检查

---

## 一、执行摘要

| 分类 | 数量 | 说明 |
|------|------|------|
| 总路由数 | 290 | FastAPI实际注册路由 |
| 公开路由 | 5 | 登录、健康检查、API文档 |
| 已认证路由 | 226 | 有 get_current_user 依赖 |
| 认证缺失路由 | 59 | 无认证依赖的敏感接口 |
| 认证覆盖率 | 79.3% | 非公开路由中的认证比例 |

**风险汇总**:
- BLOCKER: 5项
- HIGH: 4项
- MEDIUM: 3项
- CLOSED: 2项
- UNKNOWN: 2项

---

## 二、BLOCKER 级问题（必须优先修复）

### B1. 59个敏感API接口缺少认证保护
**严重度**: BLOCKER
**文件**: 多个路由文件

**详情**:
59个非公开API接口没有任何认证依赖，未登录用户可直接访问。涉及用户管理、角色管理、设备管理、工单管理、楼层管理、GIS地图、故障管理、操作日志、系统权限等核心敏感模块。

**影响范围**:
- `/api/system/users*` - 用户管理（增删改查、重置密码、启用禁用）
- `/api/system/roles*` - 角色管理（增删改查）
- `/api/system/permissions` - 权限列表
- `/api/system/operation-logs*` - 操作日志
- `/api/devices*` - 设备管理（旧路由，重复）
- `/api/device-telemetry*` - 设备遥测
- `/api/floors*` - 楼层管理
- `/api/faults*` - 故障管理
- `/api/workorders*` - 工单管理（旧路由）
- `/api/gis/*` - GIS地图数据
- `/api/auth/me` - 当前用户信息
- `/api/auth/change-password` - 修改密码
- `/api/auth/logout` - 登出
- `/api/auth/refresh` - 刷新Token
- `/api/auth/role-permissions` - 角色权限配置
- `/api/auth/demo-accounts` - 演示账号列表
- `/api/telemetry/*` - 遥测分析
- `/api/demo/*` - 演示数据接口
- `/api/defense/demo-flow` - 演示流程
- `/api/project/overview` - 项目概览

**修复建议**:
1. 为所有敏感路由统一添加 `get_current_user` 依赖
2. 公开接口显式列入白名单并文档化
3. 采用 "默认拒绝" 策略：新接口默认需要认证

---

### B2. 多租户隔离完全缺失
**严重度**: BLOCKER
**文件**: `database.py`

**详情**:
- 核心业务表（User, Building, Device, Alert, InspectionRecord, WorkOrder, Maintenance等）均无 `tenant_id` 字段
- `get_current_user` 只返回用户对象，不包含租户上下文
- 所有查询直接按ID查询，无租户过滤，存在严重IDOR（不安全的直接对象引用）风险
- 攻击者只需知道或猜测ID即可跨组织访问任意数据

**证据**:
- `database.py` 中无任何 `tenant_id` 字段定义
- `auth_service.py` 的 `get_current_user` 函数未解析或返回租户信息
- 各路由模块的查询均为 `.filter(Model.id == id)`，无租户过滤

**修复建议**:
1. 核心业务表增加 `tenant_id` 字段并建立索引
2. 认证后从用户关联关系获取可信租户上下文
3. 统一在查询层做租户过滤（可通过BaseQuery或中间层实现）
4. 管理员跨租户权限需显式定义和审计

---

### B3. 资源级权限缺失，存在IDOR风险
**严重度**: BLOCKER
**文件**: 多个路由文件

**详情**:
- 已认证的226个路由中，绝大多数只有 `get_current_user` 认证，没有对象级权限校验
- 通过 `building_id`, `device_id`, `alert_id`, `record_id`, `order_id` 等路径参数直接查询资源
- 任何已登录用户（即使是viewer角色）只要知道ID就能访问/修改任意资源
- 导出、批量操作等接口同样缺乏资源级权限控制

**典型模式**:
```python
@router.get("/api/buildings/{building_id}/detail")
def get_building_detail(building_id: int, db: Session = Depends(get_db), ...):
    building = db.query(Building).filter(Building.id == building_id).first()
    # 没有检查当前用户是否有权访问该建筑
```

**修复建议**:
1. 实现资源归属查询校验层
2. 列表、详情、搜索、统计、导出、批量接口统一做权限过滤
3. 为每类核心资源加入跨用户/跨角色负向测试

---

### B4. 默认演示账号硬编码，生产环境自动创建
**严重度**: BLOCKER
**文件**: `database.py` L616-L633

**详情**:
系统初始化时自动创建4个默认账号，密码均为固定弱密码 `123456`：
- admin / 123456 （系统管理员，全部权限）
- inspector / 123456 （巡检员）
- rectifier / 123456 （整改负责人）
- viewer / 123456 （查看用户）

**风险**:
- 生产环境部署后若未修改默认密码，攻击者可直接登录获取管理员权限
- admin账号拥有 `*` 通配符权限，相当于系统完全接管
- 密码强度极低（6位纯数字），暴力破解秒级完成

**修复建议**:
1. 生产环境禁止自动创建默认账号
2. 首次启动强制设置管理员密码
3. 演示账号仅在明确的 `DEMO_MODE` 环境变量下创建
4. 默认密码需满足复杂度要求或随机生成并打印到日志

---

### B5. 数据库无Migration机制，依赖SQLite特有实现
**严重度**: BLOCKER
**文件**: `database.py`, 多个service文件

**详情**:
1. **无Migration机制**: 使用 `Base.metadata.create_all()` 自动建表，没有版本化迁移工具（Alembic）
2. **默认SQLite**: 生产数据库默认使用SQLite，不适合企业生产环境
3. **大量直接sqlite3调用**: 至少6个服务模块直接使用 `sqlite3` 模块操作数据库，绕过SQLAlchemy ORM：
   - `services/health_service.py`
   - `services/rag_admin_service.py`
   - `services/operation_log_service.py`
   - `services/hardware_event_service.py`
   - `services/learning_profile_service.py`
   - `services/record_persistence_service.py`
4. **无PostgreSQL支持**: 代码中无任何PostgreSQL适配代码，文档声明支持但未实际实现
5. **无事务保证**: 多表操作使用独立sqlite3连接，事务一致性无法保证

**修复建议**:
1. 引入 Alembic migration 体系
2. 将直接sqlite3调用迁移到SQLAlchemy
3. 统一生产数据库为 PostgreSQL
4. 定义关键外键约束、唯一约束和非空约束

---

## 三、HIGH 级问题

### H1. JWT Secret有硬编码默认值
**严重度**: HIGH
**文件**: `services/auth_service.py` L27-L38

**详情**:
```python
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = "fire_ai_agent_dev_key_change_in_production_!" + os.urandom(16).hex()
```

**问题**:
- 虽然有环境变量，但未设置时会生成一个基于固定前缀 + 随机数的密钥
- 生产环境若忘记设置环境变量，每次重启密钥都会变化（导致所有Token失效）
- 固定前缀 `fire_ai_agent_dev_key_change_in_production_!` 在代码库中，降低了熵

**修复建议**:
1. 生产环境强制要求 `JWT_SECRET_KEY` 环境变量，否则启动失败
2. 密钥长度建议至少32字节随机字符串
3. 开发环境可使用固定值但需明确警告

---

### H2. CORS默认允许所有来源
**严重度**: HIGH
**文件**: `main.py` L87

**详情**:
```python
allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
```
默认值为 `*`，允许任意来源跨域请求。

**风险**:
- 配合凭据（credentials=True）时，若前端域名被劫持，攻击者可发起CSRF-like攻击
- 生产环境应限制为明确的域名列表

**修复建议**:
1. 生产环境必须配置明确的CORS白名单
2. 默认值改为空列表或特定域名，而非 `*`
3. `allow_credentials=True` 时不允许 `*` 来源

---

### H3. Token黑名单基于JSON文件，无持久化且性能差
**严重度**: HIGH
**文件**: `services/token_blacklist_service.py`

**详情**:
- Token黑名单存储在JSON文件中（`token_blacklist.json`）
- 每次检查都加载整个文件到内存
- 多进程部署时文件同步有问题
- 无自动清理过期Token的机制

**修复建议**:
1. 改用 Redis 存储黑名单
2. 设置TTL自动过期（与Token过期时间一致）
3. 或使用短期Access Token + 长Refresh Token方案，减少黑名单依赖

---

### H4. RBAC权限系统有实现但几乎未使用
**严重度**: HIGH
**文件**: `services/auth_service.py` L227-L255

**详情**:
- 项目实现了完整的 `require_permission()` 和 `require_role()` 函数
- 有4个系统角色和权限配置
- 但226个已认证路由中，几乎没有路由使用这些权限检查
- 权限形同虚设，任何已登录用户可访问所有已认证接口

**证据**:
- 路由中只有 `get_current_user` 依赖，没有 `require_permission` 或 `require_role`

**修复建议**:
1. 按模块梳理权限矩阵
2. 管理类接口（用户、角色、系统设置）限制为admin角色
3. 业务接口按职责分配权限（巡检员、整改员、查看用户）
4. 写操作权限与读操作权限分离

---

## 四、MEDIUM 级问题

### M1. 登录失败限制存在但仅内存存储
**严重度**: MEDIUM
**文件**: `services/auth_service.py` L42-L85

**详情**:
- 已实现登录失败次数限制（5次失败锁定15分钟）
- 但存储在内存字典 `_login_failures` 中
- 多进程/多实例部署时无法共享
- 服务重启后锁定状态清零

**当前状态**: 部分CLOSED（功能存在，但生产部署方式下不足）

**修复建议**:
1. 改用 Redis 或数据库存储失败记录
2. 支持IP级别的速率限制，防止账号枚举

---

### M2. 文件上传接口情况不明
**严重度**: MEDIUM
**状态**: UNKNOWN

**详情**:
- 代码扫描未找到使用 `UploadFile` 或 `File()` 的FastAPI上传接口
- 但存在 `/api/bim/upload/{building_id}` 和 `/api/floors/{floor_id}/plan` 等上传相关路径
- 需进一步确认上传实现方式和安全措施

**修复建议**:
1. 确认所有文件上传入口
2. 实现文件大小限制、MIME类型验证、随机文件名
3. 上传目录与代码隔离

---

### M3. 操作日志绕过SQLAlchemy，无统一审计机制
**严重度**: MEDIUM
**文件**: `services/operation_log_service.py`

**详情**:
- 操作日志使用独立的sqlite3连接和表
- 与主数据库模型分离，查询和维护不一致
- 日志写入是否覆盖所有关键操作存疑
- 无法通过外键关联用户、资源等主数据

**修复建议**:
1. 操作日志表纳入主数据库和ORM模型
2. 定义统一的操作日志接口
3. 关键操作（登录、权限变更、数据删除、配置修改）必须记录

---

## 五、CLOSED 项（已有证据证明实现）

### C1. JWT令牌基础功能
**状态**: CLOSED
**证据**:
- 支持 Access Token 和 Refresh Token
- Token类型区分（access/refresh）
- 令牌签发、解析、过期校验正常
- 测试用例验证通过（10个测试全部通过）

### C2. 密码哈希与验证
**状态**: CLOSED
**证据**:
- 使用 PBKDF2-HMAC-SHA256，100000次迭代
- 随机salt（每用户独立）
- 验证函数正确实现
- 测试用例验证通过（8个测试全部通过）

---

## 六、UNKNOWN 项（需进一步验证）

### U1. 速率限制中间件实际效果
**状态**: UNKNOWN
**文件**: `services/rate_limit_middleware.py`

**说明**:
代码中存在 `RateLimitMiddleware`，但需验证：
- IP级别的限制是否正确实现
- 用户级别的限制是否正确实现
- 绕过方式（如X-Forwarded-For伪造）

### U2. WebSocket认证
**状态**: UNKNOWN

**说明**:
存在WebSocket相关路由（`/api/ws/status`, `/api/ws/test-broadcast`），但需验证：
- WebSocket连接是否进行认证
- 消息收发是否有权限校验

---

## 七、路由认证矩阵（部分）

### 公开路由（5个）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 登录 |
| GET | /health | 健康检查 |
| GET | /docs | Swagger UI |
| GET | /redoc | ReDoc |
| GET | /openapi.json | OpenAPI Schema |

### 认证缺失的高风险路由（部分，共59个）
| 方法 | 路径 | 风险 |
|------|------|------|
| GET/POST/PUT/DELETE | /api/system/users* | 用户管理完全无认证 |
| GET/POST/PUT/DELETE | /api/system/roles* | 角色管理完全无认证 |
| GET | /api/system/permissions | 权限列表无认证 |
| GET | /api/system/operation-logs* | 操作日志无认证 |
| GET/POST/PUT/DELETE | /api/devices* | 设备管理（旧路由）无认证 |
| GET/POST | /api/device-telemetry* | 设备遥测无认证 |
| GET/POST/PUT/DELETE | /api/floors* | 楼层管理无认证 |
| GET/PUT | /api/faults* | 故障管理无认证 |
| GET/POST | /api/workorders* | 工单管理（旧路由）无认证 |
| GET | /api/gis/* | GIS数据无认证 |
| GET | /api/auth/me | 当前用户信息无认证 |
| POST | /api/auth/change-password | 修改密码无认证 |
| POST | /api/auth/logout | 登出无认证 |
| POST | /api/auth/refresh | 刷新Token无认证 |
| GET | /api/auth/role-permissions | 权限配置无认证 |
| GET | /api/auth/demo-accounts | 演示账号列表无认证 |
| POST | /api/demo/seed | 演示数据生成无认证 |
| POST | /api/demo/seed-all | 全量演示数据无认证 |
| POST | /api/telemetry/* | 遥测分析无认证 |

---

## 八、建议下一批修改范围（批次B）

**原则**: 只修复最关键的安全BLOCKER，不做大规模重构。

### 第一优先级（必须做）
1. **补全59个缺失认证的路由** - 统一添加 `get_current_user` 依赖
   - 预计改动：9个路由文件（device.py, floor.py, gis.py, workorder.py, user.py, auth.py补充等）
   - 验证方式：路由审计脚本重新运行，认证覆盖率达到100%

2. **默认账号安全改造**
   - 移除硬编码的 `123456` 密码
   - 生产环境不自动创建演示账号
   - 首次启动提示设置管理员密码

3. **JWT Secret强制配置**
   - 生产环境无 `JWT_SECRET_KEY` 则启动失败
   - 移除固定前缀

### 第二优先级（建议做）
4. **CORS生产安全配置**
   - 默认值改为空列表
   - 生产环境必须配置明确的白名单

5. **关键管理接口加上RBAC角色限制**
   - 用户管理、角色管理、系统设置限制为admin角色
   - 先加角色层控制，再细化权限

### 第三优先级（暂不做，留到后续批次）
- 多租户隔离（tenant_id全量改造，工作量大，单独批次）
- PostgreSQL + Alembic（数据层大改造，单独批次C）
- 资源级权限细粒度控制（需设计权限模型）
- 所有Mock模块接真实API（按业务需求逐步推进）

---

## 九、审计证据文件

本次审计生成的辅助文件：
- `audit_routes.py` - 路由枚举与认证分类脚本（可重复运行验证）

---

## 十、结论

当前系统处于 **"功能完整原型"** 阶段，距离企业生产级有显著差距。最紧急的问题集中在：

1. **认证不完整** - 约20%敏感接口裸奔（B1）
2. **无租户隔离** - 跨组织数据完全无保护（B2）
3. **默认弱密码** - admin/123456自动创建（B4）
4. **无数据迁移** - SQLite + 手动建表，生产不可控（B5）

建议立即启动 **批次B：认证默认拒绝 + 角色基线 + 默认账号修复**，用最小改动关闭最严重的BLOCKER。
