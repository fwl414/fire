<template>
  <div class="water-monitor-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防水源监测</div>
        <p class="subtitle">消火栓 · 消防水箱 · 消防水泵 · 实时压力水位监测 · 智能预警</p>
      </div>
      <div class="title-actions">
        <el-tag :type="loading ? 'info' : 'success'" effect="dark" size="large">
          <el-icon><Odometer /></el-icon>
          {{ loading ? '数据加载中' : '实时监测中' }}
        </el-tag>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Odometer /></el-icon></div>
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
            <div class="stat-label">压力异常</div>
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
        <div class="tab-item" :class="{ active: activeTab === 'hydrant' }" @click="activeTab = 'hydrant'">
          <el-icon><SwitchButton /></el-icon>
          消火栓监测
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'tank' }" @click="activeTab = 'tank'">
          <el-icon><Watermelon /></el-icon>
          消防水箱/水池
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'pump' }" @click="activeTab = 'pump'">
          <el-icon><Cpu /></el-icon>
          消防水泵
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'alarms' }" @click="activeTab = 'alarms'">
          <el-icon><Bell /></el-icon>
          告警记录
          <span v-if="stats.alarm" class="badge">{{ stats.alarm }}</span>
        </div>
      </div>

      <div v-if="activeTab === 'hydrant'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="hydrantBuildingFilter" placeholder="选择建筑" clearable style="width: 160px">
              <el-option label="全部建筑" value="" />
              <el-option label="1号办公楼" value="1号办公楼" />
              <el-option label="2号研发楼" value="2号研发楼" />
              <el-option label="3号宿舍楼" value="3号宿舍楼" />
              <el-option label="地下车库" value="地下车库" />
            </el-select>
            <el-select v-model="hydrantStatusFilter" placeholder="运行状态" clearable style="width: 140px">
              <el-option label="正常" value="normal" />
              <el-option label="预警" value="warning" />
              <el-option label="告警" value="alarm" />
              <el-option label="离线" value="offline" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="hydrantSearch" placeholder="搜索设备/位置" style="width: 200px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button :loading="loading" @click="refreshAll">
              <el-icon><Refresh /></el-icon>
              刷新数据
            </el-button>
          </div>
        </div>
        <el-alert
          v-if="!loading && !filteredHydrants.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无消火栓压力数据"
          description="设备上报 pressure 指标后，这里会显示真实值；从未上报的设备显示为「离线」。"
          style="margin-bottom: 12px"
        />
        <el-row :gutter="14">
          <el-col v-for="h in filteredHydrants" :key="h.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="device-card" shadow="hover" :class="h.status">
              <div class="device-card-header">
                <div class="device-icon">
                  <el-icon><SwitchButton /></el-icon>
                </div>
                <el-tag size="small" effect="dark" :type="hydrantStatusTag(h.status)">
                  {{ hydrantStatusText(h.status) }}
                </el-tag>
              </div>
              <div class="device-name">{{ h.name }}</div>
              <div class="device-location">{{ h.location }}</div>
              <div class="device-params">
                <div class="param-item">
                  <span class="param-label">水压</span>
                  <span class="param-value" :class="h.status">{{ displayValue(h.value, h.unit) }}</span>
                </div>
                <div class="param-item">
                  <span class="param-label">正常范围</span>
                  <span class="param-normal">{{ h.normalMin }} - {{ h.normalMax }} {{ h.unit }}</span>
                </div>
              </div>
              <div class="device-footer">
                <span class="update-time">更新：{{ h.update_time || '从未上报' }}</span>
                <el-button size="small" link type="primary">详情</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'tank'" class="tab-content">
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="水箱水位暂未接入遥测上报通道"
          description="后端遥测规则（TELEMETRY_RULES）目前只覆盖烟雾、温度、电流、电压、水压、剩余电流、电池电量，没有水位指标列。设备接入水位上报后此处会显示真实数据，当前不展示模拟值。"
        />
      </div>

      <div v-if="activeTab === 'pump'" class="tab-content">
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="消防水泵工况暂未接入遥测上报通道"
          description="进出口压力、流量、电机电流、累计运行时长等泵工况数据后端暂无对应指标列与上报通道。设备接入后此处会显示真实数据，当前不展示模拟值。"
        />
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
            <el-select v-model="alarmTypeFilter" placeholder="告警类型" clearable style="width: 160px">
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
        <el-table :data="filteredAlarms" stripe style="width: 100%" empty-text="暂无水系统告警记录">
          <el-table-column prop="alarm_time" label="告警时间" width="170" />
          <el-table-column label="级别" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="severityTagType(row.level)">
                {{ row.level_label }}
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
import {
  Odometer, CircleCheck, Warning, Bell, SwitchButton, Watermelon,
  Cpu, Search, Refresh
} from '@element-plus/icons-vue'
import { latestTelemetry } from '../api/telemetry'
import { alertList } from '../api/alert'

const activeTab = ref('hydrant')
const loading = ref(false)

// 水系统相关的告警类型（后端 device_ingest_service 按 pressure 指标生成的 alert_type）
const WATER_ALERT_TYPES = ['pressure_low', 'pressure_high']

// 消火栓压力是当前唯一接入遥测上报的水系统指标
const DEVICE_TYPE = '消火栓'

const hydrants = ref([])
const waterAlarms = ref([])

// 统计卡基于消火栓的真实上报状态；没上报过的设备状态为 offline，不计入正常
const stats = computed(() => {
  let normal = 0
  let warning = 0
  let alarm = 0
  for (const h of hydrants.value) {
    if (h.status === 'alarm') alarm += 1
    else if (h.status === 'warning') warning += 1
    else if (h.status === 'normal') normal += 1
  }
  return { totalPoints: hydrants.value.length, normal, warning, alarm }
})

const hydrantBuildingFilter = ref('')
const hydrantStatusFilter = ref('')
const hydrantSearch = ref('')
const alarmLevelFilter = ref('')
const alarmTypeFilter = ref('')
const alarmSearch = ref('')

// 把后端遥测行映射成页面字段；value 为 null 表示该设备从未上报，如实显示「--」
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
    const resp = await latestTelemetry(DEVICE_TYPE, 'pressure')
    // 项目里的 axios 实例返回完整 response，业务数据在 .data
    const pressure = resp.data || {}
    hydrants.value = (pressure.items || []).map(mapTelemetry)
  } catch (e) {
    hydrants.value = []
  } finally {
    loading.value = false
  }
}

async function loadAlarms() {
  try {
    const resp = await alertList({ limit: 200 })
    waterAlarms.value = (resp.data?.items || [])
      .filter(a => WATER_ALERT_TYPES.includes(a.alert_type))
      .map(a => ({
        id: a.id,
        alarm_time: (a.created_at || '').replace('T', ' ').slice(0, 19),
        level: a.severity,
        level_label: a.severity_label || a.severity,
        type: a.alert_type,
        type_label: a.alert_type_label || a.alert_type,
        device_name: a.device_name || '',
        location: a.location || '',
        value: a.alert_value == null ? '--' : `${a.alert_value} ${a.alert_unit || ''}`.trim(),
        status: a.status,
        status_label: a.status_label || a.status,
      }))
  } catch (e) {
    waterAlarms.value = []
  }
}

function refreshAll() {
  loadTelemetry()
  loadAlarms()
}

onMounted(() => {
  refreshAll()
})

function hydrantStatusText(status) {
  const map = { normal: '正常', warning: '预警', alarm: '告警', offline: '离线' }
  return map[status] || status
}
function hydrantStatusTag(status) {
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

// 数值展示：null（从未上报）显示「--」，不编数字
function displayValue(value, unit) {
  if (value === null || value === undefined) return '--'
  return unit ? `${value} ${unit}` : String(value)
}

const filteredHydrants = computed(() => {
  let list = hydrants.value
  if (hydrantBuildingFilter.value) list = list.filter(h => h.location.includes(hydrantBuildingFilter.value))
  if (hydrantStatusFilter.value) list = list.filter(h => h.status === hydrantStatusFilter.value)
  if (hydrantSearch.value) {
    const kw = hydrantSearch.value
    list = list.filter(h => h.name.includes(kw) || h.code.includes(kw) || h.location.includes(kw))
  }
  return list
})

const filteredAlarms = computed(() => {
  let list = waterAlarms.value
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
  for (const a of waterAlarms.value) {
    if (!seen.has(a.type)) seen.set(a.type, a.type_label)
  }
  return [...seen.entries()].map(([value, label]) => ({ value, label }))
})
</script>

<style scoped>
.water-monitor-page {
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

.device-card.low {
  border-color: #fbbf24;
  box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.2);
}

.device-card.high {
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
  background: linear-gradient(135deg, #0ea5e9, #0284c7);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
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

.param-value.low {
  color: #f59e0b;
}

.param-value.high {
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

.tank-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.tank-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.tank-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.tank-visual {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
}

.tank-container {
  width: 80px;
  height: 140px;
  border: 2px solid #cbd5e1;
  border-radius: 4px 4px 8px 8px;
  position: relative;
  background: #f1f5f9;
  overflow: hidden;
  flex-shrink: 0;
}

.tank-water {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(180deg, #38bdf8, #0ea5e9);
  transition: height 0.5s ease;
}

.water-wave {
  position: absolute;
  top: -6px;
  left: 0;
  right: 0;
  height: 12px;
  background: radial-gradient(ellipse at center, transparent 0%, transparent 40%, #38bdf8 40%);
  animation: wave 2s ease-in-out infinite;
}

@keyframes wave {
  0%, 100% { transform: translateX(-2px); }
  50% { transform: translateX(2px); }
}

.tank-scale {
  position: absolute;
  right: -45px;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
}

.tank-info {
  flex: 1;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
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
  font-size: 16px;
  font-weight: 700;
  color: #0ea5e9;
}

.tank-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

.pump-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.pump-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.pump-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pump-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.pump-icon.running {
  background: linear-gradient(135deg, #22c55e, #16a34a);
  animation: pulse-green 2s ease-in-out infinite;
}

.pump-icon.standby {
  background: linear-gradient(135deg, #94a3b8, #64748b);
}

.pump-icon.fault {
  background: linear-gradient(135deg, #ef4444, #dc2626);
}

@keyframes pulse-green {
  0%, 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
}

.pump-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.pump-type {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.pump-params {
  margin-bottom: 12px;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.param-box {
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 8px;
  text-align: center;
}

.param-num {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.param-num.accent {
  color: #0ea5e9;
}

.param-unit {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.param-desc {
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
}

.pump-footer {
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.pump-stats {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.pump-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
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
