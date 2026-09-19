<template>
  <div class="system-monitor-page">
    <div class="title-row">
      <div>
        <div class="page-title">系统监控中心</div>
        <p class="subtitle">服务状态 · 性能监控 · 资源占用 · 运行健康度</p>
      </div>
      <div class="actions">
        <el-button type="primary" :loading="loading" @click="loadAll"><el-icon><Refresh /></el-icon>刷新数据</el-button>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-icon"><el-icon><Cpu /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ percent(host.cpu) }}</div>
            <div class="stat-label">CPU使用率</div>
            <div class="stat-trend up" v-if="host.cpu !== null && host.cpu > 60">偏高</div>
            <div class="stat-trend down" v-else-if="host.cpu !== null">正常</div>
            <div class="stat-trend" v-else>等待采样</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-icon memory"><el-icon><Coin /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ percent(host.memory) }}</div>
            <div class="stat-label">内存使用率</div>
            <div class="stat-trend up" v-if="host.memory !== null && host.memory > 70">偏高</div>
            <div class="stat-trend down" v-else-if="host.memory !== null">正常</div>
            <div class="stat-trend" v-else>等待采样</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-icon disk"><el-icon><FolderOpened /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ percent(host.disk) }}</div>
            <div class="stat-label">磁盘使用率</div>
            <div class="stat-trend up" v-if="host.disk !== null && host.disk > 80">偏高</div>
            <div class="stat-trend down" v-else-if="host.disk !== null">正常</div>
            <div class="stat-trend" v-else>等待采样</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card">
          <div class="stat-icon network"><el-icon><Connection /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ networkRecv }}</div>
            <div class="stat-label">网络接收 (KB/s)</div>
            <div class="stat-trend down">发送 {{ networkSent }} KB/s</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="tab-bar">
      <div class="tab-item" :class="{ active: activeTab === 'service' }" @click="activeTab = 'service'">
        <el-icon><SetUp /></el-icon>服务状态
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'performance' }" @click="activeTab = 'performance'">
        <el-icon><DataAnalysis /></el-icon>性能监控
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'database' }" @click="activeTab = 'database'">
        <el-icon><Coin /></el-icon>数据库状态
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'api' }" @click="activeTab = 'api'">
        <el-icon><Link /></el-icon>接口监控
      </div>
    </div>

    <el-card v-if="activeTab === 'service'" class="content-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <strong>系统服务状态</strong>
          <el-tag :type="servicesOk ? 'success' : 'danger'" effect="dark">
            {{ health.overall || '检测中' }}
          </el-tag>
        </div>
      </template>
      <el-row :gutter="14">
        <el-col v-for="check in serviceChecks" :key="check.name" :xs="24" :sm="12" :md="8" :lg="6">
          <div class="service-card" :class="{ offline: check.status !== '正常' }">
            <div class="service-header">
              <div class="service-name">{{ check.name }}</div>
              <span class="service-status-dot" :class="check.status === '正常' ? 'running' : 'stopped'"></span>
            </div>
            <div class="service-type">{{ check.detail }}</div>
            <div class="service-footer">
              <el-tag
                size="small"
                :type="check.status === '正常' ? 'success' : check.status === '异常' ? 'danger' : 'warning'"
                effect="light"
              >
                {{ check.status }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
      <el-empty v-if="!serviceChecks.length" description="正在检测各项子系统状态" />
    </el-card>

    <el-card v-if="activeTab === 'performance'" class="content-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <strong>实时性能监控</strong>
          <span class="muted">服务启动以来的真实采样 {{ trendPoints.length }} 个点，每 {{ POLL_SECONDS }} 秒采样一次</span>
        </div>
      </template>
      <el-row :gutter="14">
        <el-col :xs="24" :md="12">
          <div class="chart-card">
            <div class="chart-title">CPU 使用率趋势</div>
            <div class="mini-chart">
              <svg viewBox="0 0 300 100" preserveAspectRatio="none" class="trend-svg">
                <defs>
                  <linearGradient id="cpuGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0.4" />
                    <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0" />
                  </linearGradient>
                </defs>
                <path :d="cpuPath" fill="url(#cpuGradient)" stroke="none" />
                <path :d="cpuLine" fill="none" stroke="#3b82f6" stroke-width="2" />
              </svg>
            </div>
            <div class="chart-stats">
              <div><span class="label">当前</span><span class="value blue">{{ percent(host.cpu) }}</span></div>
              <div><span class="label">峰值</span><span class="value warning">{{ percent(cpuPeak) }}</span></div>
              <div><span class="label">均值</span><span class="value">{{ percent(cpuAvg) }}</span></div>
            </div>
          </div>
        </el-col>
        <el-col :xs="24" :md="12">
          <div class="chart-card">
            <div class="chart-title">内存使用率趋势</div>
            <div class="mini-chart">
              <svg viewBox="0 0 300 100" preserveAspectRatio="none" class="trend-svg">
                <defs>
                  <linearGradient id="memGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#22c55e;stop-opacity:0.4" />
                    <stop offset="100%" style="stop-color:#22c55e;stop-opacity:0" />
                  </linearGradient>
                </defs>
                <path :d="memPath" fill="url(#memGradient)" stroke="none" />
                <path :d="memLine" fill="none" stroke="#22c55e" stroke-width="2" />
              </svg>
            </div>
            <div class="chart-stats">
              <div><span class="label">当前</span><span class="value green">{{ percent(host.memory) }}</span></div>
              <div><span class="label">峰值</span><span class="value warning">{{ percent(memPeak) }}</span></div>
              <div><span class="label">均值</span><span class="value">{{ percent(memAvg) }}</span></div>
            </div>
          </div>
        </el-col>
      </el-row>

      <el-divider />

      <div class="section-title">资源占用排行（共 {{ processes.total }} 个进程）</div>
      <el-table :data="processes.items" size="small" style="width:100%" empty-text="正在采集进程数据">
        <el-table-column prop="name" label="进程名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="pid" label="PID" width="90" />
        <el-table-column label="CPU占用" width="170">
          <template #default="{ row }">
            <el-progress
              :percentage="progressPercent(row.cpu_percent)"
              :stroke-width="8"
              :color="row.cpu_percent > 50 ? '#f59e0b' : '#22c55e'"
            />
          </template>
        </el-table-column>
        <el-table-column label="内存占用" width="170">
          <template #default="{ row }">
            <el-progress
              :percentage="progressPercent(row.memory_percent)"
              :stroke-width="8"
              :color="row.memory_percent > 50 ? '#ef4444' : '#3b82f6'"
            />
          </template>
        </el-table-column>
        <el-table-column label="启动时间" width="170">
          <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
        </el-table-column>
      </el-table>
      <p class="muted" v-if="processes.cpu_basis">{{ processes.cpu_basis }}</p>
    </el-card>

    <el-card v-if="activeTab === 'database'" class="content-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <strong>数据库状态</strong>
          <el-tag :type="db.connected ? 'success' : 'danger'" effect="dark">
            {{ db.connected ? '连接正常' : '连接异常' }}
          </el-tag>
        </div>
      </template>
      <el-row :gutter="14">
        <el-col :xs="24" :sm="12" :md="6">
          <div class="db-stat-card">
            <div class="db-label">数据库类型</div>
            <div class="db-value">{{ db.dialect || '--' }}</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="db-stat-card">
            <div class="db-label">库大小</div>
            <div class="db-value">{{ formatBytes(db.size_bytes) }}</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="db-stat-card">
            <div class="db-label">连接池签出</div>
            <div class="db-value">{{ dbConnections }}<span class="db-unit">个</span></div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="db-stat-card">
            <div class="db-label">数据表 / 总记录</div>
            <div class="db-value">{{ dbTables.length }}<span class="db-unit">/ {{ dbTotalRows }}</span></div>
          </div>
        </el-col>
      </el-row>

      <el-divider />

      <div class="section-title">数据表记录数</div>
      <el-table :data="dbTables" size="small" style="width:100%" max-height="380" empty-text="读取中">
        <el-table-column prop="name" label="表名" min-width="220" show-overflow-tooltip />
        <el-table-column prop="row_count" label="记录数" width="140" align="right" />
        <el-table-column label="数据大小" width="140" align="right">
          <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
        </el-table-column>
      </el-table>
      <el-alert
        v-if="dbUnsupported.length"
        type="info"
        :closable="false"
        show-icon
        style="margin-top:12px"
        :title="`当前数据库（${db.dialect}）不提供 QPS / TPS / 缓存命中率，页面不再用估算值填充`"
      />
    </el-card>

    <el-card v-if="activeTab === 'api'" class="content-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <strong>API接口监控</strong>
          <span class="muted">本进程启动以来的真实计数（已运行 {{ formatDuration(apiStats.uptime_seconds) }}），重启后从零开始</span>
        </div>
      </template>
      <el-row :gutter="14">
        <el-col :xs="12" :sm="6">
          <div class="api-stat">
            <div class="api-num">{{ apiStats.total }}</div>
            <div class="api-label">总请求数</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="api-stat success">
            <div class="api-num">{{ apiStats.success }}</div>
            <div class="api-label">成功请求</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="api-stat fail">
            <div class="api-num">{{ apiStats.failed }}</div>
            <div class="api-label">失败请求</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="api-stat avg">
            <div class="api-num">{{ apiStats.avg_duration_ms === null ? '--' : apiStats.avg_duration_ms }}<span style="font-size:14px">ms</span></div>
            <div class="api-label">平均响应</div>
          </div>
        </el-col>
      </el-row>

      <el-divider />

      <div class="section-title">接口调用排行</div>
      <el-table :data="apiRows" size="small" style="width:100%" empty-text="本进程还没有记录到请求">
        <el-table-column prop="method" label="方法" width="70">
          <template #default="{ row }">
            <el-tag size="small" :type="row.method === 'GET' ? 'success' : row.method === 'POST' ? 'primary' : 'warning'">
              {{ row.method }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="接口路径" min-width="220" show-overflow-tooltip />
        <el-table-column prop="count" label="调用次数" width="110" align="right" />
        <el-table-column label="成功率" width="140">
          <template #default="{ row }">
            <el-progress :percentage="row.success_rate" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column label="平均耗时" width="110" align="right">
          <template #default="{ row }">
            <span :class="{ slow: row.avg_time > 500 }">{{ row.avg_time === null ? '--' : row.avg_time }}ms</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed" label="错误数" width="100" align="right" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { Refresh, Cpu, Coin, FolderOpened, Connection } from '@element-plus/icons-vue'
import request from '../api'

const loading = ref(false)
const activeTab = ref('service')

// 所有数字都来自后端真实采集（backend/services/system_metrics_service.py）。
// 改造前这里用 Math.random() 每 3 秒改写 CPU/内存/网络，趋势曲线也是随机数滚出来的。
const POLL_SECONDS = 5

const host = ref({ cpu: null, memory: null, disk: null, network: null, trend: [] })
const health = ref({ overall: '', checks: [] })
const processes = ref({ items: [], total: 0, cpu_basis: '' })
const db = ref({ connected: false, tables: [], pool: {}, unsupported_metrics: [] })
const apiStats = ref({ total: 0, success: 0, failed: 0, avg_duration_ms: null, by_path: [], uptime_seconds: 0 })

const serviceChecks = computed(() => health.value.checks || [])
const servicesOk = computed(() => health.value.overall === '正常')

// CPU 与网络速率按两次采样差值计算，首次访问后端返回 null —— 显示「--」而不是编一个数
const percent = (value) => (value === null || value === undefined ? '--' : `${value}%`)
const networkRecv = computed(() => (host.value.network ? `${host.value.network.recv_kbps}` : '--'))
const networkSent = computed(() => (host.value.network ? `${host.value.network.sent_kbps}` : '--'))

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return '--'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatTime(timestamp) {
  if (!timestamp) return '--'
  const d = new Date(timestamp * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '--'
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (hours) return `${hours} 小时 ${minutes} 分`
  if (minutes) return `${minutes} 分 ${total % 60} 秒`
  return `${total} 秒`
}

// ---- 性能趋势：用后端返回的真实采样点画线 ----
const trendPoints = computed(() => host.value.trend || [])
const peakOf = (field) => (trendPoints.value.length ? Math.max(...trendPoints.value.map(p => p[field])) : null)
const avgOf = (field) => (trendPoints.value.length
  ? Math.round(trendPoints.value.reduce((sum, p) => sum + p[field], 0) / trendPoints.value.length * 10) / 10
  : null)
const cpuPeak = computed(() => peakOf('cpu'))
const cpuAvg = computed(() => avgOf('cpu'))
const memPeak = computed(() => peakOf('memory'))
const memAvg = computed(() => avgOf('memory'))

function trendPath(field, closeArea) {
  const points = trendPoints.value
  // 只有一个采样点时画不出趋势线，返回空路径（不补点凑曲线）
  if (points.length < 2) return ''
  const w = 300, h = 100
  const step = w / (points.length - 1)
  let d = `M 0 ${h - points[0][field] * 0.9}`
  points.forEach((p, i) => {
    if (i > 0) d += ` L ${i * step} ${h - p[field] * 0.9}`
  })
  if (closeArea) d += ` L ${w} ${h} L 0 ${h} Z`
  return d
}

const cpuLine = computed(() => trendPath('cpu', false))
const cpuPath = computed(() => trendPath('cpu', true))
const memLine = computed(() => trendPath('memory', false))
const memPath = computed(() => trendPath('memory', true))

// el-progress 只接受 0~100，进程 CPU 占用可能超过 100%（按单核计）
const progressPercent = (value) => Math.max(0, Math.min(100, Number(value) || 0))

// ---- 数据库：只展示查得到的项，QPS 之类 SQLite 没有的如实说明 ----
const dbTables = computed(() => db.value.tables || [])
const dbTotalRows = computed(() => dbTables.value.reduce((sum, item) => sum + (item.row_count || 0), 0))
const dbPool = computed(() => db.value.pool || {})
const dbConnections = computed(() => (dbPool.value.checked_out === undefined ? '--' : dbPool.value.checked_out))
const dbUnsupported = computed(() => db.value.unsupported_metrics || [])

// ---- 接口监控：本进程启动以来的真实计数 ----
const apiRows = computed(() => (apiStats.value.by_path || []).map(row => ({
  ...row,
  avg_time: row.avg_duration_ms,
  success_rate: row.count ? Math.round((row.count - row.failed) / row.count * 1000) / 10 : 0,
})))

let timer = null

async function loadHost() {
  try {
    host.value = (await request.get('/api/system/host')).data || host.value
  } catch (e) {
    // 失败原因由请求拦截器统一提示
  }
}

async function loadHealth() {
  try {
    health.value = (await request.get('/api/system/health')).data || health.value
  } catch (e) {}
}

async function loadProcesses() {
  try {
    processes.value = (await request.get('/api/system/processes', { params: { limit: 8 } })).data || processes.value
  } catch (e) {}
}

async function loadDatabase() {
  try {
    db.value = (await request.get('/api/system/database')).data || db.value
  } catch (e) {}
}

async function loadApiStats() {
  try {
    apiStats.value = (await request.get('/api/system/api-stats', { params: { limit: 10 } })).data || apiStats.value
  } catch (e) {}
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadHost(), loadHealth()])
    // 当前页签的数据顺带刷新，切页签时再拉其余的
    if (activeTab.value === 'performance') await loadProcesses()
    if (activeTab.value === 'database') await loadDatabase()
    if (activeTab.value === 'api') await loadApiStats()
  } finally {
    loading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'performance') loadProcesses()
  if (tab === 'database') loadDatabase()
  if (tab === 'api') loadApiStats()
})

onMounted(() => {
  loadAll()
  // 轮询真实指标；原来这里是每 3 秒用随机数改写页面数字
  timer = setInterval(loadHost, POLL_SECONDS * 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.system-monitor-page {
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

.stats-row {
  margin-bottom: 14px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  gap: 14px;
  align-items: center;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 22px;
  flex-shrink: 0;
}

.stat-icon.memory { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.disk { background: linear-gradient(135deg, #f59e0b, #d97706); }
.stat-icon.network { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

.stat-info {
  flex: 1;
}

.stat-num {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  font-family: 'Consolas', monospace;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin: 2px 0;
}

.stat-trend {
  font-size: 11px;
}

.stat-trend.up { color: #f59e0b; }
.stat-trend.down { color: #22c55e; }

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

.content-card {
  margin-bottom: 14px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.muted {
  font-size: 12px;
  color: #94a3b8;
}

.service-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;
  transition: all 0.2s;
}

.service-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.service-card.offline {
  opacity: 0.6;
}

.service-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.service-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #eff6ff;
  color: #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.service-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
}

.service-status-dot.stopped {
  background: #94a3b8;
  box-shadow: none;
}

.service-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 2px;
}

.service-type {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
}

.service-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 12px;
}

.service-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.chart-card {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
}

.mini-chart {
  height: 120px;
  margin-bottom: 12px;
}

.trend-svg {
  width: 100%;
  height: 100%;
}

.chart-stats {
  display: flex;
  justify-content: space-around;
}

.chart-stats > div {
  text-align: center;
}

.chart-stats .label {
  font-size: 12px;
  color: #94a3b8;
  display: block;
}

.chart-stats .value {
  font-size: 18px;
  font-weight: 600;
  font-family: 'Consolas', monospace;
  color: #0f172a;
}

.chart-stats .value.blue { color: #3b82f6; }
.chart-stats .value.green { color: #22c55e; }
.chart-stats .value.warning { color: #f59e0b; }

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
}

.db-stat-card {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 14px;
}

.db-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}

.db-value {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  font-family: 'Consolas', monospace;
  margin-bottom: 8px;
}

.db-unit {
  font-size: 13px;
  color: #64748b;
  font-weight: 400;
  margin-left: 4px;
}

.db-trend {
  font-size: 12px;
  margin-top: 6px;
}

.db-trend.up { color: #ef4444; }
.db-trend.down { color: #22c55e; }

.api-stat {
  text-align: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.api-num {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Consolas', monospace;
  color: #0f172a;
}

.api-stat.success .api-num { color: #22c55e; }
.api-stat.fail .api-num { color: #ef4444; }
.api-stat.avg .api-num { color: #3b82f6; }

.api-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.slow {
  color: #ef4444;
  font-weight: 500;
}
</style>
