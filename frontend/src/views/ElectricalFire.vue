<template>
  <div class="electrical-fire-page">
    <div class="title-row">
      <div>
        <div class="page-title">电气火灾监测</div>
        <p class="subtitle">漏电监测 · 温度监测 · 电流监测 · 电气火灾隐患预警</p>
      </div>
      <div class="title-actions">
        <el-tag :type="loading ? 'info' : 'success'" effect="dark" size="large">
          <el-icon><Lightning /></el-icon>
          {{ loading ? '数据加载中' : '实时监测中' }}
        </el-tag>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Position /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalPoints }}</div>
            <div class="stat-label">监测点位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.normal }}</div>
            <div class="stat-label">正常运行</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.warning }}</div>
            <div class="stat-label">预警数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Bell /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.alarm }}</div>
            <div class="stat-label">告警数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'leakage' }" @click="activeTab = 'leakage'">
          <el-icon><Connection /></el-icon>
          漏电监测
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'temperature' }" @click="activeTab = 'temperature'">
          <el-icon><ColdDrink /></el-icon>
          温度监测
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'current' }" @click="activeTab = 'current'">
          <el-icon><Lightning /></el-icon>
          电流监测
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'alarms' }" @click="activeTab = 'alarms'">
          <el-icon><Bell /></el-icon>
          告警记录
          <span v-if="stats.alarm" class="badge">{{ stats.alarm }}</span>
        </div>
      </div>

      <div v-if="activeTab === 'leakage'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="leakageBuildingFilter" placeholder="选择建筑" clearable style="width: 160px">
              <el-option label="全部建筑" value="" />
              <el-option label="1号办公楼" value="1" />
              <el-option label="2号研发楼" value="2" />
              <el-option label="3号宿舍楼" value="3" />
              <el-option label="地下车库" value="4" />
            </el-select>
            <el-select v-model="leakageStatusFilter" placeholder="运行状态" clearable style="width: 140px">
              <el-option label="正常" value="normal" />
              <el-option label="预警" value="warning" />
              <el-option label="告警" value="alarm" />
              <el-option label="离线" value="offline" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="leakageSearch" placeholder="搜索回路/位置" style="width: 200px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-alert
          v-if="!loading && !filteredLeakage.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无配电箱剩余电流数据"
          description="设备上报 remaining_current 指标后，这里会显示真实值；从未上报的设备显示为「离线」。"
          style="margin-bottom: 12px"
        />
        <el-row :gutter="14">
          <el-col v-for="l in filteredLeakage" :key="l.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="device-card" shadow="hover" :class="l.status">
              <div class="device-card-header">
                <div class="device-icon leakage">
                  <el-icon><Connection /></el-icon>
                </div>
                <el-tag size="small" effect="dark" :type="leakageStatusTag(l.status)">
                  {{ leakageStatusText(l.status) }}
                </el-tag>
              </div>
              <div class="device-name">{{ l.name }}</div>
              <div class="device-location">{{ l.location }}</div>
              <div class="device-subinfo">{{ l.code }}</div>
              <div class="device-params">
                <div class="param-item">
                  <span class="param-label">剩余电流</span>
                  <span class="param-value" :class="l.status">{{ displayValue(l.value, l.unit) }}</span>
                </div>
                <div class="param-item">
                  <span class="param-label">告警阈值</span>
                  <span class="param-normal">{{ displayValue(l.alarmThreshold, l.unit) }}</span>
                </div>
              </div>
              <div class="device-footer">
                <span class="update-time">更新：{{ l.update_time || '从未上报' }}</span>
                <el-button size="small" link type="primary">详情</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'temperature'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="tempStatusFilter" placeholder="运行状态" clearable style="width: 140px">
              <el-option label="正常" value="normal" />
              <el-option label="预警" value="warning" />
              <el-option label="告警" value="alarm" />
              <el-option label="离线" value="offline" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button :loading="loading" @click="refreshAll">
              <el-icon><Refresh /></el-icon>
              刷新数据
            </el-button>
          </div>
        </div>
        <el-alert
          v-if="!loading && !filteredTemperatures.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无配电箱温度数据"
          description="设备上报 temperature 指标后，这里会显示真实值。"
          style="margin-bottom: 12px"
        />
        <el-row :gutter="14">
          <el-col v-for="t in filteredTemperatures" :key="t.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="temp-card" shadow="hover" :class="t.status">
              <div class="temp-header">
                <div class="temp-name">{{ t.name }}</div>
                <el-tag size="small" effect="dark" :type="tempStatusTag(t.status)">
                  {{ tempStatusText(t.status) }}
                </el-tag>
              </div>
              <div class="temp-location">{{ t.location }}</div>
              <div class="temp-type-tag">
                <el-tag size="small" type="info">{{ t.code }}</el-tag>
              </div>
              <div class="temp-visual">
                <div class="thermometer">
                  <div class="thermometer-tube">
                    <div class="thermometer-fill" :style="{ height: getTempPercent(t) + '%', background: getTempColor(t) }"></div>
                    <div class="thermometer-scale">
                      <span v-for="tick in tempScaleTicks()" :key="tick">{{ tick }}</span>
                    </div>
                  </div>
                  <div class="thermometer-bulb" :style="{ background: getTempColor(t) }"></div>
                </div>
                <div class="temp-info">
                  <div class="info-row">
                    <span class="info-label">当前温度</span>
                    <span class="info-value big" :style="{ color: getTempColor(t) }">{{ displayValue(t.value, t.unit) }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">正常范围</span>
                    <span class="info-value">{{ t.normalMin }} - {{ t.normalMax }} ℃</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">预警阈值</span>
                    <span class="info-value">{{ displayValue(t.warningThreshold, '℃') }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">告警阈值</span>
                    <span class="info-value">{{ displayValue(t.alarmThreshold, '℃') }}</span>
                  </div>
                </div>
              </div>
              <div class="temp-footer">
                <span class="update-time">更新：{{ t.update_time || '从未上报' }}</span>
                <el-button size="small" link type="primary">历史曲线</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'current'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="currentBuildingFilter" placeholder="选择建筑" clearable style="width: 160px">
              <el-option label="全部建筑" value="" />
              <el-option label="1号办公楼" value="1号办公楼" />
              <el-option label="2号研发楼" value="2号研发楼" />
              <el-option label="3号宿舍楼" value="3号宿舍楼" />
              <el-option label="地下车库" value="地下车库" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="currentSearch" placeholder="搜索设备/位置" style="width: 200px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-alert
          v-if="!loading && !filteredCurrents.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无配电箱电流数据"
          description="设备上报 current 指标后，这里会显示真实值。"
          style="margin-bottom: 12px"
        />
        <el-table :data="filteredCurrents" stripe style="width: 100%">
          <el-table-column prop="name" label="设备名称" min-width="180" />
          <el-table-column prop="code" label="设备编号" width="150" />
          <el-table-column prop="location" label="位置" min-width="180" />
          <el-table-column label="电流" width="140">
            <template #default="{ row }">
              <span :class="currentValueStatus(row) === 'normal' ? '' : currentValueStatus(row) === 'offline' ? '' : 'warning-text'">
                {{ displayValue(row.value, row.unit) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="电压" width="140">
            <template #default="{ row }">
              {{ voltageByDevice[row.id] == null ? '--' : `${voltageByDevice[row.id]} V` }}
            </template>
          </el-table-column>
          <el-table-column label="阈值（预警 / 告警）" min-width="180">
            <template #default="{ row }">
              {{ displayValue(row.warningThreshold, row.unit) }} / {{ displayValue(row.alarmThreshold, row.unit) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="leakageStatusTag(row.status)">
                {{ leakageStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">{{ row.update_time || '从未上报' }}</template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'alarms'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="alarmLevelFilter" placeholder="告警级别" clearable style="width: 140px">
              <el-option label="严重" value="critical" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
            <el-select v-model="alarmTypeFilter" placeholder="告警类型" clearable style="width: 180px">
              <el-option
                v-for="opt in alarmTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="alarmSearch" placeholder="搜索告警" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table :data="filteredAlarms" stripe style="width: 100%" empty-text="暂无电气类告警记录">
          <el-table-column prop="alarm_time" label="告警时间" width="170" />
          <el-table-column label="级别" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="severityTagType(row.level)">
                {{ row.severity_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="140">
            <template #default="{ row }">
              {{ row.type_label }}
            </template>
          </el-table-column>
          <el-table-column prop="device_name" label="设备名称" width="180" />
          <el-table-column prop="location" label="位置" min-width="160" />
          <el-table-column prop="value" label="告警值" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="alertStatusTagType(row.status)">
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Lightning, Position, CircleCheck, Warning, Bell, Connection, ColdDrink, Search, Refresh } from '@element-plus/icons-vue'
import { latestTelemetry } from '../api/telemetry'
import { alertList } from '../api/alert'

const activeTab = ref('leakage')
const loading = ref(false)

// 电气火灾相关的告警类型（后端 device_ingest_service 按指标生成的 alert_type）
const ELECTRICAL_ALERT_TYPES = ['remaining_current', 'temperature_high', 'current_high', 'voltage_high']

// 监测点位 = 配电箱设备；电气三类指标（漏电/温度/电流/电压）都从配电箱上报
const DEVICE_TYPE = '配电箱'

const leakageList = ref([])
const temperatureList = ref([])
const currentList = ref([])
const voltageList = ref([])
const electricalAlarms = ref([])
// 温度页签的温度计刻度要用告警阈值上限，其余指标直接用行内的阈值字段
const tempThresholds = ref({})

// 电流页需要并排看电压，按 device_id 建索引
const voltageByDevice = computed(() => {
  const map = {}
  for (const row of voltageList.value) map[row.id] = row.value
  return map
})

// 按设备取三类指标里最差的状态，得出统计卡的正常/预警/告警数。
// 从未上报过某指标的设备状态为 offline，不计入正常，也不计入预警/告警。
const stats = computed(() => {
  const statusOf = new Map()
  const merge = (row) => {
    if (!row) return
    const list = statusOf.get(row.id) || []
    list.push(row.status)
    statusOf.set(row.id, list)
  }
  leakageList.value.forEach(merge)
  temperatureList.value.forEach(merge)
  currentList.value.forEach(merge)

  let normal = 0
  let warning = 0
  let alarm = 0
  for (const statuses of statusOf.values()) {
    if (statuses.includes('alarm')) alarm += 1
    else if (statuses.includes('warning')) warning += 1
    else if (statuses.includes('normal')) normal += 1
  }
  return { totalPoints: statusOf.size, normal, warning, alarm }
})

const leakageBuildingFilter = ref('')
const leakageStatusFilter = ref('')
const leakageSearch = ref('')
const tempStatusFilter = ref('')
const currentBuildingFilter = ref('')
const currentSearch = ref('')
const alarmLevelFilter = ref('')
const alarmTypeFilter = ref('')
const alarmSearch = ref('')

// 把后端遥测行映射成页面字段：值/阈值/状态全部来自 /api/telemetry/latest，
// 设备没有上报过的指标 value 为 null、status 为 offline，如实展示「--」。
function mapTelemetry(row) {
  return {
    id: row.device_id,
    name: row.device_name,
    code: row.device_code,
    location: row.location,
    value: row.value,
    unit: row.unit,
    status: row.status,
    warningThreshold: row.warning_threshold,
    alarmThreshold: row.alarm_threshold,
    normalMin: row.normal_min,
    normalMax: row.normal_max,
    update_time: row.update_time ? row.update_time.replace('T', ' ').slice(0, 19) : '',
  }
}

async function loadTelemetry() {
  loading.value = true
  try {
    const [leakageResp, temperatureResp, currentResp, voltageResp] = await Promise.all([
      latestTelemetry(DEVICE_TYPE, 'remaining_current'),
      latestTelemetry(DEVICE_TYPE, 'temperature'),
      latestTelemetry(DEVICE_TYPE, 'current'),
      latestTelemetry(DEVICE_TYPE, 'voltage'),
    ])
    // 项目里的 axios 实例返回完整 response，业务数据在 .data
    const leakage = leakageResp.data || {}
    const temperature = temperatureResp.data || {}
    const current = currentResp.data || {}
    const voltage = voltageResp.data || {}
    leakageList.value = (leakage.items || []).map(mapTelemetry)
    temperatureList.value = (temperature.items || []).map(mapTelemetry)
    currentList.value = (current.items || []).map(mapTelemetry)
    voltageList.value = (voltage.items || []).map(mapTelemetry)
    tempThresholds.value = temperature.thresholds || {}
  } catch (e) {
    leakageList.value = []
    temperatureList.value = []
    currentList.value = []
    voltageList.value = []
    tempThresholds.value = {}
  } finally {
    loading.value = false
  }
}

async function loadAlarms() {
  try {
    const resp = await alertList({ limit: 200 })
    electricalAlarms.value = (resp.data?.items || [])
      .filter(a => ELECTRICAL_ALERT_TYPES.includes(a.alert_type))
      .map(a => ({
        id: a.id,
        alarm_time: (a.created_at || '').replace('T', ' ').slice(0, 19),
        level: a.severity,
        type: a.alert_type,
        // 中文类型名由后端统一给出，前端不再各写一套映射
        type_label: a.alert_type_label || a.alert_type,
        severity_label: a.severity_label || a.severity,
        device_name: a.device_name || '',
        location: a.location || '',
        value: a.alert_value == null ? '--' : `${a.alert_value} ${a.alert_unit || ''}`.trim(),
        status: a.status,
        status_label: a.status_label || a.status,
      }))
  } catch (e) {
    electricalAlarms.value = []
  }
}

function refreshAll() {
  loadTelemetry()
  loadAlarms()
}

onMounted(() => {
  refreshAll()
})

function leakageStatusText(status) {
  const map = { normal: '正常', warning: '预警', alarm: '告警', offline: '离线' }
  return map[status] || status
}
function leakageStatusTag(status) {
  const map = { normal: 'success', warning: 'warning', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

// 告警级别的颜色（文案由后端 severity_label 给，前端只管配色）
function severityTagType(severity) {
  const map = { critical: 'danger', high: 'danger', medium: 'warning', low: 'info' }
  return map[severity] || 'info'
}

// 处置状态的颜色（文案由后端 status_label 给）
function alertStatusTagType(status) {
  const map = { pending: 'danger', processing: 'warning', resolved: 'success', merged: 'info' }
  return map[status] || 'info'
}
function tempStatusText(status) {
  const map = { normal: '正常', warning: '预警', alarm: '告警', offline: '离线' }
  return map[status] || status
}
function tempStatusTag(status) {
  const map = { normal: 'success', warning: 'warning', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

// 温度计按后端给的阈值上限画刻度，避免前端写死 80/60/40/20 这套刻度
function tempScaleMax() {
  const t = tempThresholds.value || {}
  const candidates = [t.alarm_threshold, t.normal_range && t.normal_range[1]].filter(v => typeof v === 'number')
  return candidates.length ? Math.max(...candidates) : 80
}

// 刻度值跟着后端阈值走，不再写死 80/60/40/20/0
function tempScaleTicks() {
  const max = tempScaleMax()
  return [max, max * 0.75, max * 0.5, max * 0.25, 0].map(v => `${Math.round(v)}℃`)
}

function getTempPercent(row) {
  const max = tempScaleMax()
  if (row.value == null) return 0
  return Math.max(0, Math.min(100, (row.value / max) * 100))
}

function getTempColor(row) {
  if (row.status === 'alarm') return '#ef4444'
  if (row.status === 'warning') return '#f59e0b'
  if (row.status === 'offline') return '#94a3b8'
  return '#22c55e'
}

// 数值展示：null（从未上报）显示「--」，不编数字
function displayValue(value, unit) {
  if (value === null || value === undefined) return '--'
  return unit ? `${value} ${unit}` : String(value)
}

// 相对阈值的位置，用于给电流等单值指标上色
function currentValueStatus(row) {
  if (row.value === null || row.value === undefined) return 'offline'
  return row.status
}

const filteredLeakage = computed(() => {
  let list = leakageList.value
  if (leakageStatusFilter.value) list = list.filter(l => l.status === leakageStatusFilter.value)
  if (leakageSearch.value) {
    const kw = leakageSearch.value
    list = list.filter(l => l.name.includes(kw) || l.code.includes(kw) || l.location.includes(kw))
  }
  return list
})

const filteredTemperatures = computed(() => {
  let list = temperatureList.value
  if (tempStatusFilter.value) list = list.filter(t => t.status === tempStatusFilter.value)
  return list
})

const filteredCurrents = computed(() => {
  let list = currentList.value
  if (currentBuildingFilter.value) list = list.filter(c => c.location.includes(currentBuildingFilter.value))
  if (currentSearch.value) {
    const kw = currentSearch.value
    list = list.filter(c => c.name.includes(kw) || c.code.includes(kw) || c.location.includes(kw))
  }
  return list
})

const filteredAlarms = computed(() => {
  let list = electricalAlarms.value
  if (alarmLevelFilter.value) list = list.filter(a => a.level === alarmLevelFilter.value)
  if (alarmTypeFilter.value) list = list.filter(a => a.type === alarmTypeFilter.value)
  if (alarmSearch.value) {
    const kw = alarmSearch.value
    list = list.filter(a => a.device_name.includes(kw) || a.location.includes(kw))
  }
  return list
})

// 下拉选项只列当前真实存在的告警类型，标签用后端给的中文名（不写死映射表）
const alarmTypeOptions = computed(() => {
  const seen = new Map()
  for (const a of electricalAlarms.value) {
    if (!seen.has(a.type)) seen.set(a.type, a.type_label)
  }
  return [...seen.entries()].map(([value, label]) => ({ value, label }))
})
</script>

<style scoped>
.electrical-fire-page {
  padding: 0;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
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

.el-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.orange { background: linear-gradient(135deg, #f59e0b, #d97706); }
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 18px;
  padding-bottom: 14px;
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
  position: relative;
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

.tab-item .badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.device-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  transition: all 0.2s;
}

.device-card.warning {
  border-color: #fbbf24;
  box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.2);
}

.device-card.alarm {
  border-color: #f87171;
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.2);
}

.device-card.offline {
  border-color: #d1d5db;
  opacity: 0.7;
}

.device-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.device-icon {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.device-icon.leakage {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
}

.device-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 2px;
}

.device-location {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.device-subinfo {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.device-params {
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.param-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
}

.param-label {
  color: #94a3b8;
}

.param-value {
  font-weight: 600;
  color: #0f172a;
}

.param-value.warning {
  color: #f59e0b;
}

.param-value.alarm {
  color: #ef4444;
}

.param-normal {
  color: #64748b;
  font-size: 12px;
}

.device-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

.update-time {
  font-size: 11px;
  color: #94a3b8;
}

.temp-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.temp-card.warning {
  border-color: #fbbf24;
  box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.2);
}

.temp-card.alarm {
  border-color: #f87171;
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.2);
}

.temp-card.offline {
  border-color: #d1d5db;
  opacity: 0.7;
}

.temp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.temp-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.temp-location {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.temp-type-tag {
  margin-bottom: 12px;
}

.temp-visual {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
}

.thermometer {
  width: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.thermometer-tube {
  width: 16px;
  height: 120px;
  border: 2px solid #cbd5e1;
  border-radius: 8px 8px 0 0;
  position: relative;
  background: #f1f5f9;
  overflow: hidden;
  margin-bottom: -2px;
}

.thermometer-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  transition: height 0.5s ease;
}

.thermometer-scale {
  position: absolute;
  right: -35px;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
}

.thermometer-bulb {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid #cbd5e1;
  margin-top: -2px;
}

.temp-info {
  flex: 1;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  font-size: 12px;
}

.info-label {
  color: #94a3b8;
}

.info-value {
  color: #334155;
  font-weight: 500;
}

.info-value.big {
  font-size: 18px;
  font-weight: 700;
}

.temp-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

.load-rate-cell {
  display: flex;
  align-items: center;
}

.load-rate-text {
  font-weight: 600;
  font-size: 13px;
  min-width: 40px;
  text-align: right;
}

.danger-text {
  color: #ef4444;
  font-weight: 600;
}

.warning-text {
  color: #f59e0b;
  font-weight: 600;
}
</style>
