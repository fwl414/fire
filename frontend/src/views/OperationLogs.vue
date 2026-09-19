<template>
  <div class="operation-logs-page">
    <div class="title-row">
      <div>
        <div class="page-title">操作日志审计</div>
        <p class="subtitle">系统操作全记录 · 安全审计追踪 · 登录日志 · 操作追溯</p>
      </div>
      <div class="actions">
        <el-button @click="refreshAll"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button type="primary" plain><el-icon><Download /></el-icon>导出日志</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="metric-row">
      <el-col :xs="12" :sm="6">
        <div class="metric-card">
          <el-icon class="metric-icon"><Document /></el-icon>
          <span>日志总数</span>
          <strong>{{ metricText(metrics?.total) }}</strong>
          <small>操作日志全量</small>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="metric-card orange">
          <el-icon class="metric-icon"><Warning /></el-icon>
          <span>业务状态变更</span>
          <strong>{{ metricText(metrics?.status_changed_count) }}</strong>
          <small>工单/档案/复查状态流转</small>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="metric-card red">
          <el-icon class="metric-icon"><Bell /></el-icon>
          <span>异常与预警</span>
          <strong>{{ metricText(abnormalCount) }}</strong>
          <small>错误 + 预警日志</small>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="metric-card green">
          <el-icon class="metric-icon"><User /></el-icon>
          <span>今日登录用户</span>
          <strong>{{ metricText(metrics?.today_login_users) }}</strong>
          <small>今日登录成功的账号数</small>
        </div>
      </el-col>
    </el-row>

    <div class="tab-bar">
      <div class="tab-item" :class="{ active: activeTab === 'operation' }" @click="switchTab('operation')">
        <el-icon><List /></el-icon>操作日志
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'login' }" @click="switchTab('login')">
        <el-icon><UserFilled /></el-icon>登录日志
      </div>
    </div>

    <el-card v-if="activeTab === 'operation'" class="card filter-card" shadow="never">
      <template #header>
        <div class="header-row">
          <strong>筛选条件</strong>
          <span class="muted">支持按模块、等级、操作人、时间范围查询</span>
        </div>
      </template>
      <el-form :inline="true" :model="filters">
        <el-form-item label="操作模块">
          <el-select v-model="filters.module" clearable style="width:150px">
            <el-option v-for="m in moduleList" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="日志等级">
          <el-select v-model="filters.level" clearable style="width:130px">
            <el-option label="普通" value="info"/>
            <el-option label="预警" value="warning"/>
            <el-option label="危险" value="danger"/>
            <el-option label="成功" value="success"/>
          </el-select>
        </el-form-item>
        <el-form-item label="操作人">
          <el-input v-model="filters.username" clearable placeholder="操作人账号" style="width:140px" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.date_range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" clearable placeholder="标题 / 详情 / IP" style="width:220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button>
          <el-button @click="reset"><el-icon><RefreshLeft /></el-icon>重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="activeTab === 'operation'" class="card" shadow="never">
      <template #header>
        <div class="header-row">
          <strong>操作日志列表</strong>
          <div class="header-actions">
            <span class="muted">共 {{ total }} 条</span>
            <el-button size="small" :loading="verifying" @click="handleVerify">
              <el-icon><Warning /></el-icon>校验完整性
            </el-button>
            <el-button size="small" type="primary" :loading="exporting" @click="handleExport('csv')">
              <el-icon><Download /></el-icon>导出 CSV
            </el-button>
            <el-button size="small" :loading="exporting" @click="handleExport('json')">
              <el-icon><Download /></el-icon>导出 JSON
            </el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="items" border stripe style="width:100%">
        <el-table-column prop="created_at" label="操作时间" width="170" />
        <el-table-column prop="seq" label="链序号" width="80" />
        <el-table-column prop="module" label="操作模块" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="moduleTagType(row.module)">{{ row.module }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="日志等级" width="90">
          <template #default="{row}">
            <el-tag size="small" :type="tagType(row.level)">{{ levelText(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="操作内容" width="180" show-overflow-tooltip />
        <el-table-column label="状态变化" width="170">
          <template #default="{row}">
            <span v-if="row.status_before || row.status_after">
              {{ row.status_before || '-' }} → {{ row.status_after || '-' }}
            </span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="操作人" width="100" />
        <el-table-column prop="ip_address" label="IP地址" width="130" />
        <el-table-column prop="target_id" label="关联对象" width="180" show-overflow-tooltip />
        <el-table-column prop="description" label="操作详情" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click="viewLogDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager-row">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="load"
        />
      </div>
    </el-card>

    <el-card v-if="activeTab === 'login'" class="card filter-card" shadow="never">
      <template #header>
        <div class="header-row">
          <strong>筛选条件</strong>
          <span class="muted">支持按用户、状态、时间范围查询</span>
        </div>
      </template>
      <el-form :inline="true" :model="loginFilters">
        <el-form-item label="用户名">
          <el-input v-model="loginFilters.username" clearable placeholder="支持模糊匹配" style="width:140px" />
        </el-form-item>
        <el-form-item label="登录状态">
          <el-select v-model="loginFilters.status" clearable style="width:130px">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="loginFilters.date_range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item label="IP地址">
          <el-input v-model="loginFilters.ip" clearable placeholder="输入IP" style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loginPage = 1; loadLogin()"><el-icon><Search /></el-icon>查询</el-button>
          <el-button @click="resetLogin"><el-icon><RefreshLeft /></el-icon>重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="activeTab === 'login'" class="card" shadow="never">
      <template #header>
        <div class="header-row">
          <strong>登录日志列表</strong>
          <span class="muted">共 {{ loginTotal }} 条</span>
        </div>
      </template>
      <el-table v-loading="loginLoading" :data="loginLogs" border stripe style="width:100%">
        <el-table-column prop="login_time" label="登录时间" width="170" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column label="姓名" width="100">
          <template #default="{ row }">{{ row.real_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="IP地址" width="140">
          <template #default="{ row }">{{ row.ip_address || '—' }}</template>
        </el-table-column>
        <el-table-column label="登录地点" width="100">
          <template #default="{ row }">{{ row.location || '—' }}</template>
        </el-table-column>
        <el-table-column label="设备信息" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ deviceText(row) }}</template>
        </el-table-column>
        <el-table-column label="登录状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="dark" :type="row.status === 'success' ? 'success' : 'danger'">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="失败原因" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.fail_reason || '—' }}</template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无登录记录" :image-size="60" />
        </template>
      </el-table>
      <div class="pager-row">
        <el-pagination
          v-model:current-page="loginPage"
          v-model:page-size="loginPageSize"
          :total="loginTotal"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadLogin"
          @size-change="loginPage = 1; loadLogin()"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailDialog" title="日志详情" width="640px">
      <div v-if="currentLog" class="log-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="操作时间" :span="2">{{ currentLog.created_at }}</el-descriptions-item>
          <el-descriptions-item label="链序号">{{ currentLog.seq ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="操作模块">{{ currentLog.module }}</el-descriptions-item>
          <el-descriptions-item label="日志等级">
            <el-tag size="small" :type="tagType(currentLog.level)">{{ levelText(currentLog.level) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="操作人">{{ currentLog.username }}</el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ currentLog.ip_address }}</el-descriptions-item>
          <el-descriptions-item label="操作内容" :span="2">{{ currentLog.title }}</el-descriptions-item>
          <el-descriptions-item label="关联对象" :span="2">{{ currentLog.target_id || '—' }}</el-descriptions-item>
          <el-descriptions-item label="操作详情" :span="2">{{ currentLog.description || '—' }}</el-descriptions-item>
          <el-descriptions-item label="本行哈希" :span="2">
            <span class="hash-text">{{ currentLog.hash || '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="前序哈希" :span="2">
            <span class="hash-text">{{ currentLog.prev_hash || '—' }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import {
  Refresh, Download, Document, Warning, Bell, User, List,
  UserFilled, Search, RefreshLeft
} from '@element-plus/icons-vue'
import {
  operationLogs,
  operationLogDashboard,
  loginLogs as fetchLoginLogs,
  exportOperationLogs,
  verifyOperationLogChain,
} from '../api'

const activeTab = ref('operation')
const filters = ref({ module:'', level:'', keyword:'', username:'', date_range: [] })
const loginFilters = ref({ username:'', status:'', date_range:[], ip:'' })
const detailDialog = ref(false)
const currentLog = ref(null)

// 指标卡来自后端汇总接口；加载失败时保持 null，卡片显示 —，不用 0 冒充真实值
const metrics = ref(null)

const abnormalCount = computed(() => {
  if (!metrics.value) return null
  return (metrics.value.warning_count || 0) + (metrics.value.error_count || 0)
})

function metricText(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString('zh-CN')
}

const moduleList = [
  '设备管理', '报警中心', '巡检管理', '维保管理', '系统管理', '用户管理', '知识库',
  '整改工单', '整改复查', '巡检档案', '操作日志'
]

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const exporting = ref(false)
const verifying = ref(false)

// 登录日志来自后端 login_logs（登录成功与失败都记），不再使用演示数据
const loginLogs = ref([])
const loginTotal = ref(0)
const loginPage = ref(1)
const loginPageSize = ref(20)
const loginLoading = ref(false)

function deviceText(row) {
  const parts = [row.os, row.browser].filter(Boolean)
  return parts.length ? parts.join(' / ') : '—'
}

function tagType(level){ return level==='danger'?'danger':level==='warning'?'warning':level==='success'?'success':'info' }
function levelText(level){ return {danger:'危险',warning:'预警',success:'成功',info:'普通'}[level] || '普通' }

function moduleTagType(module) {
  const map = { '系统管理': 'info', '用户管理': 'warning', '报警中心': 'danger', '设备管理': 'primary' }
  return map[module] || ''
}

function viewLogDetail(row) {
  currentLog.value = row
  detailDialog.value = true
}

function reset() {
  filters.value = { module:'', level:'', keyword:'', username:'', date_range: [] }
  page.value = 1
  load()
}

function resetLogin() {
  loginFilters.value = { username:'', status:'', date_range:[], ip:'' }
  loginPage.value = 1
  loadLogin()
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'login' && loginLogs.value.length === 0) loadLogin()
}

function toDate(value) {
  if (!value) return ''
  const d = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function loadLogin() {
  loginLoading.value = true
  try {
    const range = loginFilters.value.date_range || []
    const { data } = await fetchLoginLogs({
      username: loginFilters.value.username,
      status: loginFilters.value.status,
      ip_address: loginFilters.value.ip,
      start: toDate(range[0]),
      end: toDate(range[1]),
      page: loginPage.value,
      page_size: loginPageSize.value,
    })
    loginLogs.value = data.items || []
    loginTotal.value = data.total || 0
  } catch (error) {
    // 拦截器已提示具体原因
  } finally {
    loginLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await operationLogs({
      module: filters.value.module,
      level: filters.value.level,
      username: filters.value.username,
      keyword: filters.value.keyword,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    // 拦截器已提示具体原因
  } finally {
    loading.value = false
  }
}

async function handleExport(format) {
  exporting.value = true
  try {
    const filename = await exportOperationLogs({
      format,
      module: filters.value.module,
      level: filters.value.level,
      username: filters.value.username,
      keyword: filters.value.keyword,
    })
    ElMessage.success(`已导出 ${filename}`)
  } catch (error) {
    // 拦截器已提示具体原因
  } finally {
    exporting.value = false
  }
}

async function handleVerify() {
  verifying.value = true
  try {
    const { data } = await verifyOperationLogChain()
    if (data.ok) {
      ElNotification({
        title: '审计日志完整性校验通过',
        message: `已校验 ${data.checked} 条记录，链尾哈希 ${String(data.head_hash).slice(0, 16)}…`
          + (data.unverified_legacy ? `；另有 ${data.unverified_legacy} 条历史记录未接入哈希链` : ''),
        type: 'success',
        duration: 8000,
      })
    } else {
      ElNotification({
        title: '审计日志完整性校验未通过',
        message: `第 ${data.first_broken?.seq} 条异常：${data.first_broken?.reason}`,
        type: 'error',
        duration: 0,
      })
    }
  } catch (error) {
    // 拦截器已提示具体原因
  } finally {
    verifying.value = false
  }
}

async function loadDashboard() {
  try {
    const { data } = await operationLogDashboard()
    metrics.value = data
  } catch (error) {
    // 拦截器已提示具体原因；保留上一次的汇总，首次加载失败时卡片显示 —
  }
}

function refreshAll() {
  loadDashboard()
  load()
  if (activeTab.value === 'login') loadLogin()
}

onMounted(refreshAll)
</script>

<style scoped>
.operation-logs-page {
  padding: 0;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.actions {
  display: flex;
  gap: 10px;
}

.metric-row {
  margin-bottom: 14px;
}

.metric-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: relative;
  overflow: hidden;
}

.metric-icon {
  position: absolute;
  right: 16px;
  top: 16px;
  font-size: 28px;
  color: #3b82f6;
  opacity: 0.2;
}

.metric-card.orange .metric-icon { color: #f59e0b; }
.metric-card.red .metric-icon { color: #ef4444; }
.metric-card.green .metric-icon { color: #22c55e; }

.metric-card span {
  font-size: 13px;
  color: #64748b;
}

.metric-card strong {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  font-family: 'Consolas', monospace;
}

.metric-card small {
  font-size: 11px;
  color: #94a3b8;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.tab-item {
  padding: 8px 18px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-item:hover {
  background: #f1f5f9;
  color: #334155;
}

.tab-item.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.card {
  margin-bottom: 14px;
}

.filter-card {
  margin-bottom: 14px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.hash-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  word-break: break-all;
  color: #64748b;
}

.muted {
  font-size: 12px;
  color: #94a3b8;
}

.log-detail {
  padding: 10px 0;
}
</style>
