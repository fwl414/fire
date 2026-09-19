<template>
  <div class="iot-device-page">
    <div class="title-row">
      <div>
        <div class="page-title">物联网设备接入</div>
        <p class="subtitle">设备管理 · 数据模拟 · 通信日志 · 实时监控 · 设备全生命周期管理</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Cpu /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalDevices }}</div>
            <div class="stat-label">设备总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><Connection /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.onlineDevices }}</div>
            <div class="stat-label">在线设备</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon cyan"><el-icon><DataAnalysis /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.todayData }}</div>
            <div class="stat-label">今日数据量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.alarmDevices }}</div>
            <div class="stat-label">告警设备数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'list' }" @click="activeTab = 'list'">
          <el-icon><List /></el-icon>
          设备列表
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'simulate' }" @click="activeTab = 'simulate'">
          <el-icon><VideoPlay /></el-icon>
          数据模拟
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'logs' }" @click="activeTab = 'logs'">
          <el-icon><Document /></el-icon>
          通信日志
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'detail' }" @click="activeTab = 'detail'">
          <el-icon><InfoFilled /></el-icon>
          设备详情
          <span v-if="selectedDevice" class="badge-dot"></span>
        </div>
      </div>

      <div v-if="activeTab === 'list'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="deviceTypeFilter" placeholder="设备类型" clearable style="width: 140px">
              <el-option label="烟感探测器" value="smoke" />
              <el-option label="温感探测器" value="temperature" />
              <el-option label="水压传感器" value="water_pressure" />
              <el-option label="电气火灾" value="electrical_fire" />
            </el-select>
            <el-select v-model="deviceStatusFilter" placeholder="设备状态" clearable style="width: 140px">
              <el-option label="在线" value="online" />
              <el-option label="离线" value="offline" />
              <el-option label="告警" value="alarm" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="deviceSearch" placeholder="搜索设备编号/位置" style="width: 240px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredDevices" stripe style="width: 100%" @row-click="handleRowClick">
          <el-table-column prop="device_code" label="设备编号" width="160" />
          <el-table-column label="设备类型" width="130">
            <template #default="{ row }">
              <el-tag size="small" :type="deviceTypeTag(row.type)" effect="light">
                {{ deviceTypeText(row.type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="安装位置" min-width="200" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="statusTagType(row.status)">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_report" label="最近上报时间" width="170" />
          <el-table-column label="信号强度" width="120">
            <template #default="{ row }">
              <div class="signal-bar">
                <div class="signal-bars">
                  <span :class="{ active: row.signal >= 20 }"></span>
                  <span :class="{ active: row.signal >= 40 }"></span>
                  <span :class="{ active: row.signal >= 60 }"></span>
                  <span :class="{ active: row.signal >= 80 }"></span>
                  <span :class="{ active: row.signal >= 95 }"></span>
                </div>
                <span class="signal-text">{{ row.signal }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="电量" width="110">
            <template #default="{ row }">
              <div class="battery-indicator">
                <div class="battery-body">
                  <div class="battery-fill" :style="{ width: row.battery + '%', background: batteryColor(row.battery) }"></div>
                </div>
                <span class="battery-text">{{ row.battery }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="viewDetail(row)">查看详情</el-button>
              <el-button link type="success" @click.stop="simulateDevice(row)">数据模拟</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'simulate'" class="tab-content">
        <div class="simulate-container">
          <div class="simulate-left">
            <div class="panel-title">
              <el-icon><Cpu /></el-icon>
              设备选择
            </div>
            <div class="device-select-list">
              <div
                v-for="d in onlineDeviceList"
                :key="d.id"
                class="device-select-item"
                :class="{ active: selectedSimDevice?.id === d.id }"
                @click="selectSimDevice(d)"
              >
                <div class="device-icon" :class="d.type">
                  <el-icon><component :is="deviceIcon(d.type)" /></el-icon>
                </div>
                <div class="device-info">
                  <div class="device-name">{{ d.device_code }}</div>
                  <div class="device-location">{{ d.location }}</div>
                </div>
                <div class="device-status-dot" :class="d.status"></div>
              </div>
            </div>
          </div>

          <div class="simulate-right">
            <div class="simulate-header">
              <div class="panel-title">
                <el-icon><DataAnalysis /></el-icon>
                实时数据监控
                <span v-if="selectedSimDevice" class="device-tag">{{ selectedSimDevice.device_code }}</span>
              </div>
              <div class="simulate-controls">
                <el-select v-model="updateInterval" size="small" style="width: 120px">
                  <el-option label="1秒更新" :value="1000" />
                  <el-option label="5秒更新" :value="5000" />
                  <el-option label="10秒更新" :value="10000" />
                </el-select>
                <el-button
                  size="small"
                  :type="isSimulating ? 'danger' : 'success'"
                  @click="toggleSimulation"
                >
                  <el-icon><component :is="isSimulating ? 'VideoPause' : 'VideoPlay'" /></el-icon>
                  {{ isSimulating ? '停止模拟' : '启动模拟' }}
                </el-button>
                <el-button size="small" type="warning" @click="triggerAlarm">
                  <el-icon><Warning /></el-icon>
                  模拟告警
                </el-button>
              </div>
            </div>

            <div v-if="selectedSimDevice" class="monitor-panel">
              <div class="current-value-row">
                <div class="value-card main">
                  <div class="value-label">当前值</div>
                  <div class="value-num" :class="{ alarm: isAlarming }">
                    {{ currentValue.toFixed(1) }}
                    <span class="value-unit">{{ valueUnit }}</span>
                  </div>
                  <div class="value-trend" :class="trendDir">
                    <el-icon><component :is="trendDir === 'up' ? 'Top' : 'Bottom'" /></el-icon>
                    {{ trendValue.toFixed(2) }}
                  </div>
                </div>
                <div class="value-card">
                  <div class="value-label">最小值</div>
                  <div class="value-num small">{{ minValue.toFixed(1) }}<span class="value-unit">{{ valueUnit }}</span></div>
                </div>
                <div class="value-card">
                  <div class="value-label">最大值</div>
                  <div class="value-num small">{{ maxValue.toFixed(1) }}<span class="value-unit">{{ valueUnit }}</span></div>
                </div>
                <div class="value-card">
                  <div class="value-label">平均值</div>
                  <div class="value-num small">{{ avgValue.toFixed(1) }}<span class="value-unit">{{ valueUnit }}</span></div>
                </div>
              </div>

              <div class="waveform-panel">
                <div class="waveform-header">
                  <span class="waveform-title">实时波形图</span>
                  <span class="waveform-status" :class="{ running: isSimulating }">
                    <span class="status-dot"></span>
                    {{ isSimulating ? '采集中' : '已停止' }}
                  </span>
                </div>
                <div class="waveform-container">
                  <div class="waveform-grid">
                    <div v-for="i in 5" :key="i" class="grid-line-h"></div>
                    <div v-for="i in 10" :key="'v'+i" class="grid-line-v"></div>
                  </div>
                  <svg class="waveform-svg" viewBox="0 0 600 200" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="waveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0.4" />
                        <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0" />
                      </linearGradient>
                    </defs>
                    <path :d="areaPath" fill="url(#waveGradient)" />
                    <path :d="linePath" fill="none" stroke="#3b82f6" stroke-width="2" />
                    <circle v-for="(p, idx) in wavePoints.slice(-5)" :key="idx" :cx="p.x" :cy="p.y" r="3" fill="#3b82f6" />
                    <circle v-if="wavePoints.length" :cx="wavePoints[wavePoints.length-1].x" :cy="wavePoints[wavePoints.length-1].y" r="5" fill="#fff" stroke="#3b82f6" stroke-width="2">
                      <animate attributeName="r" values="5;8;5" dur="1.5s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="1;0.5;1" dur="1.5s" repeatCount="indefinite" />
                    </circle>
                  </svg>
                  <div class="waveform-y-axis">
                    <span>{{ yAxisMax }}{{ valueUnit }}</span>
                    <span>{{ yAxisMin }}{{ valueUnit }}</span>
                  </div>
                </div>
              </div>

              <div class="param-grid">
                <div class="param-item">
                  <span class="param-label">信号强度</span>
                  <span class="param-value">{{ selectedSimDevice.signal }}%</span>
                </div>
                <div class="param-item">
                  <span class="param-label">电池电量</span>
                  <span class="param-value">{{ selectedSimDevice.battery }}%</span>
                </div>
                <div class="param-item">
                  <span class="param-label">上报间隔</span>
                  <span class="param-value">{{ updateInterval / 1000 }}s</span>
                </div>
                <div class="param-item">
                  <span class="param-label">已采集</span>
                  <span class="param-value">{{ dataPoints }} 点</span>
                </div>
              </div>
            </div>

            <el-empty v-else description="请选择左侧设备开始模拟" />
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'logs'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="logTypeFilter" placeholder="上报类型" clearable style="width: 140px">
              <el-option label="心跳" value="heartbeat" />
              <el-option label="数据" value="data" />
              <el-option label="告警" value="alarm" />
            </el-select>
            <el-select v-model="logStatusFilter" placeholder="通信状态" clearable style="width: 140px">
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button @click="clearLogs">
              <el-icon><Delete /></el-icon>
              清空日志
            </el-button>
          </div>
        </div>

        <el-table :data="filteredLogs" stripe style="width: 100%">
          <el-table-column prop="time" label="时间" width="170" />
          <el-table-column prop="device_code" label="设备编号" width="160" />
          <el-table-column label="上报类型" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="logTypeTag(row.type)" effect="light">
                {{ logTypeText(row.type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="数据内容" min-width="260" />
          <el-table-column label="通信状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'success' ? 'success' : 'danger'">
                {{ row.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="延迟" width="100">
            <template #default="{ row }">
              <span :class="row.delay < 100 ? 'success-text' : row.delay < 300 ? 'warning-text' : 'danger-text'">
                {{ row.delay }}ms
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'detail'" class="tab-content">
        <div v-if="selectedDevice" class="detail-container">
          <el-row :gutter="16">
            <el-col :xs="24" :md="8">
              <el-card class="detail-card" shadow="never">
                <div class="detail-card-title">
                  <el-icon><InfoFilled /></el-icon>
                  基本信息
                </div>
                <div class="detail-info-list">
                  <div class="info-row">
                    <span class="info-label">设备编号</span>
                    <span class="info-value">{{ selectedDevice.device_code }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">设备类型</span>
                    <span class="info-value">{{ deviceTypeText(selectedDevice.type) }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">设备型号</span>
                    <span class="info-value">{{ selectedDevice.model }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">安装位置</span>
                    <span class="info-value">{{ selectedDevice.location }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">安装日期</span>
                    <span class="info-value">{{ selectedDevice.install_date }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">生产厂商</span>
                    <span class="info-value">{{ selectedDevice.manufacturer }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">设备状态</span>
                    <span class="info-value">
                      <el-tag size="small" effect="dark" :type="statusTagType(selectedDevice.status)">
                        {{ statusText(selectedDevice.status) }}
                      </el-tag>
                    </span>
                  </div>
                </div>
              </el-card>

              <el-card class="detail-card" shadow="never">
                <div class="detail-card-title">
                  <el-icon><Setting /></el-icon>
                  运行参数
                </div>
                <div class="detail-info-list">
                  <div class="info-row">
                    <span class="info-label">协议类型</span>
                    <span class="info-value">{{ selectedDevice.protocol }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">上报间隔</span>
                    <span class="info-value">{{ selectedDevice.report_interval }}s</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">信号强度</span>
                    <span class="info-value">{{ selectedDevice.signal }}%</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">电池电量</span>
                    <span class="info-value">{{ selectedDevice.battery }}%</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">固件版本</span>
                    <span class="info-value">{{ selectedDevice.firmware }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">IP地址</span>
                    <span class="info-value">{{ selectedDevice.ip_address }}</span>
                  </div>
                </div>
              </el-card>
            </el-col>

            <el-col :xs="24" :md="16">
              <el-card class="detail-card" shadow="never">
                <div class="detail-card-title">
                  <el-icon><TrendCharts /></el-icon>
                  历史数据曲线（近24小时）
                </div>
                <div class="history-chart">
                  <svg class="history-svg" viewBox="0 0 800 220" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="historyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:#22c55e;stop-opacity:0.3" />
                        <stop offset="100%" style="stop-color:#22c55e;stop-opacity:0" />
                      </linearGradient>
                    </defs>
                    <path :d="historyAreaPath" fill="url(#historyGradient)" />
                    <path :d="historyLinePath" fill="none" stroke="#22c55e" stroke-width="2" />
                  </svg>
                  <div class="chart-x-axis">
                    <span v-for="h in 9" :key="h">{{ (h-1) * 3 }}:00</span>
                  </div>
                </div>
              </el-card>

              <el-card class="detail-card" shadow="never">
                <div class="detail-card-title">
                  <el-icon><Bell /></el-icon>
                  告警记录
                </div>
                <el-table :data="alarmRecords" size="small" stripe style="width: 100%">
                  <el-table-column prop="time" label="时间" width="170" />
                  <el-table-column prop="level" label="级别" width="90">
                    <template #default="{ row }">
                      <el-tag size="small" effect="dark" :type="row.level === 'critical' ? 'danger' : row.level === 'high' ? 'warning' : 'info'">
                        {{ row.level === 'critical' ? '严重' : row.level === 'high' ? '高危' : '一般' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="content" label="告警内容" min-width="200" />
                  <el-table-column prop="duration" label="持续时间" width="110" />
                  <el-table-column label="状态" width="90">
                    <template #default="{ row }">
                      <el-tag size="small" :type="row.status === 'resolved' ? 'success' : 'warning'">
                        {{ row.status === 'resolved' ? '已恢复' : '处理中' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </div>

        <el-empty v-else description="请在设备列表中选择一个设备查看详情">
          <template #description>
            <span>请在设备列表中点击设备行，或点击"查看详情"按钮</span>
          </template>
        </el-empty>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, Connection, DataAnalysis, Warning, List, VideoPlay, VideoPause, Document, InfoFilled, Search, Bell, Setting, TrendCharts, Top, Bottom, Delete, Position, Watermelon, Lightning } from '@element-plus/icons-vue'

const activeTab = ref('list')
const deviceSearch = ref('')
const deviceTypeFilter = ref('')
const deviceStatusFilter = ref('')
const logTypeFilter = ref('')
const logStatusFilter = ref('')
const selectedDevice = ref(null)
const selectedSimDevice = ref(null)
const updateInterval = ref(1000)
const isSimulating = ref(false)
const isAlarming = ref(false)
const currentValue = ref(0)
const trendValue = ref(0)
const trendDir = ref('up')
const dataPoints = ref(0)
const wavePoints = ref([])
const minValue = ref(0)
const maxValue = ref(0)
const avgValue = ref(0)

let simTimer = null
let dataTimer = null

const stats = ref({
  totalDevices: 128,
  onlineDevices: 112,
  todayData: '48.6K',
  alarmDevices: 5,
})

const devices = ref([
  { id: 1, device_code: 'IOT-SM-001', type: 'smoke', model: 'JTY-GD-3002', location: '综合办公楼A座3层走廊', status: 'online', last_report: '2026-09-09 14:32:15', signal: 92, battery: 85, install_date: '2025-03-15', manufacturer: '海湾安全技术', protocol: 'NB-IoT', report_interval: 30, firmware: 'v2.3.1', ip_address: '10.0.1.101' },
  { id: 2, device_code: 'IOT-SM-002', type: 'smoke', model: 'JTY-GD-3002', location: '综合办公楼A座5层会议室', status: 'online', last_report: '2026-09-09 14:31:48', signal: 88, battery: 76, install_date: '2025-03-15', manufacturer: '海湾安全技术', protocol: 'NB-IoT', report_interval: 30, firmware: 'v2.3.1', ip_address: '10.0.1.102' },
  { id: 3, device_code: 'IOT-TM-001', type: 'temperature', model: 'JTW-ZCD-3003', location: '实验楼B座2层实验室', status: 'alarm', last_report: '2026-09-09 14:30:22', signal: 95, battery: 90, install_date: '2025-05-20', manufacturer: '利达华信', protocol: 'LoRa', report_interval: 15, firmware: 'v1.8.5', ip_address: '10.0.2.101' },
  { id: 4, device_code: 'IOT-TM-002', type: 'temperature', model: 'JTW-ZCD-3003', location: '实验楼B座3层机房', status: 'online', last_report: '2026-09-09 14:32:05', signal: 85, battery: 68, install_date: '2025-05-20', manufacturer: '利达华信', protocol: 'LoRa', report_interval: 15, firmware: 'v1.8.5', ip_address: '10.0.2.102' },
  { id: 5, device_code: 'IOT-WP-001', type: 'water_pressure', model: 'PS-2000', location: '地下车库B1层喷淋管网', status: 'online', last_report: '2026-09-09 14:31:30', signal: 78, battery: 95, install_date: '2025-01-10', manufacturer: '上海松江', protocol: '4G', report_interval: 60, firmware: 'v3.0.2', ip_address: '10.0.3.101' },
  { id: 6, device_code: 'IOT-WP-002', type: 'water_pressure', model: 'PS-2000', location: '综合办公楼A座消防泵房', status: 'online', last_report: '2026-09-09 14:30:55', signal: 90, battery: 88, install_date: '2025-01-10', manufacturer: '上海松江', protocol: '4G', report_interval: 60, firmware: 'v3.0.2', ip_address: '10.0.3.102' },
  { id: 7, device_code: 'IOT-EF-001', type: 'electrical_fire', model: 'EF-R8', location: '学生宿舍C区配电间', status: 'online', last_report: '2026-09-09 14:32:00', signal: 93, battery: 100, install_date: '2025-06-01', manufacturer: '青鸟消防', protocol: 'RS485', report_interval: 10, firmware: 'v2.1.0', ip_address: '10.0.4.101' },
  { id: 8, device_code: 'IOT-EF-002', type: 'electrical_fire', model: 'EF-R8', location: '图书馆D馆配电室', status: 'offline', last_report: '2026-09-09 08:15:42', signal: 0, battery: 45, install_date: '2025-06-01', manufacturer: '青鸟消防', protocol: 'RS485', report_interval: 10, firmware: 'v2.1.0', ip_address: '10.0.4.102' },
  { id: 9, device_code: 'IOT-SM-003', type: 'smoke', model: 'JTY-GD-3002', location: '学生食堂厨房', status: 'alarm', last_report: '2026-09-09 14:29:18', signal: 75, battery: 62, install_date: '2025-04-10', manufacturer: '海湾安全技术', protocol: 'NB-IoT', report_interval: 30, firmware: 'v2.3.1', ip_address: '10.0.1.103' },
  { id: 10, device_code: 'IOT-SM-004', type: 'smoke', model: 'JTY-GD-3002', location: '图书馆D馆3层书库', status: 'online', last_report: '2026-09-09 14:31:20', signal: 82, battery: 79, install_date: '2025-07-22', manufacturer: '海湾安全技术', protocol: 'NB-IoT', report_interval: 30, firmware: 'v2.3.1', ip_address: '10.0.1.104' },
  { id: 11, device_code: 'IOT-TM-003', type: 'temperature', model: 'JTW-ZCD-3003', location: '地下车库B2层', status: 'offline', last_report: '2026-09-08 22:45:30', signal: 0, battery: 12, install_date: '2025-02-28', manufacturer: '利达华信', protocol: 'LoRa', report_interval: 15, firmware: 'v1.8.5', ip_address: '10.0.2.103' },
  { id: 12, device_code: 'IOT-WP-003', type: 'water_pressure', model: 'PS-2000', location: '实验楼B座消火栓系统', status: 'online', last_report: '2026-09-09 14:31:10', signal: 80, battery: 82, install_date: '2025-03-05', manufacturer: '上海松江', protocol: '4G', report_interval: 60, firmware: 'v3.0.2', ip_address: '10.0.3.103' },
])

const logs = ref([
  { id: 1, time: '2026-09-09 14:32:15', device_code: 'IOT-SM-001', type: 'heartbeat', content: '心跳包: 烟雾浓度=0.02%/m, 温度=25.3℃', status: 'success', delay: 45 },
  { id: 2, time: '2026-09-09 14:32:05', device_code: 'IOT-TM-002', type: 'data', content: '数据上报: 温度=28.6℃, 湿度=65.2%RH', status: 'success', delay: 78 },
  { id: 3, time: '2026-09-09 14:31:48', device_code: 'IOT-SM-002', type: 'heartbeat', content: '心跳包: 烟雾浓度=0.01%/m, 温度=26.1℃', status: 'success', delay: 52 },
  { id: 4, time: '2026-09-09 14:31:30', device_code: 'IOT-WP-001', type: 'data', content: '数据上报: 水压=0.68MPa, 流量=0.00L/s', status: 'success', delay: 125 },
  { id: 5, time: '2026-09-09 14:30:22', device_code: 'IOT-TM-001', type: 'alarm', content: '温度告警: 当前温度=68.5℃, 超过阈值55℃', status: 'success', delay: 38 },
  { id: 6, time: '2026-09-09 14:30:00', device_code: 'IOT-EF-001', type: 'data', content: '数据上报: 剩余电流=125mA, 线缆温度=42.3℃', status: 'success', delay: 89 },
  { id: 7, time: '2026-09-09 14:29:18', device_code: 'IOT-SM-003', type: 'alarm', content: '烟雾告警: 烟雾浓度=5.2%/m, 超过阈值0.5%/m', status: 'success', delay: 32 },
  { id: 8, time: '2026-09-09 14:28:55', device_code: 'IOT-EF-002', type: 'heartbeat', content: '心跳包: 通信异常，无响应', status: 'failed', delay: 3000 },
  { id: 9, time: '2026-09-09 14:28:30', device_code: 'IOT-WP-002', type: 'data', content: '数据上报: 水压=0.72MPa, 流量=0.00L/s', status: 'success', delay: 67 },
  { id: 10, time: '2026-09-09 14:27:20', device_code: 'IOT-SM-004', type: 'heartbeat', content: '心跳包: 烟雾浓度=0.01%/m, 温度=24.8℃', status: 'success', delay: 58 },
  { id: 11, time: '2026-09-09 14:26:10', device_code: 'IOT-WP-003', type: 'data', content: '数据上报: 水压=0.65MPa, 流量=0.00L/s', status: 'success', delay: 142 },
  { id: 12, time: '2026-09-09 14:25:45', device_code: 'IOT-TM-003', type: 'heartbeat', content: '心跳包: 设备离线，连接超时', status: 'failed', delay: 5000 },
])

const alarmRecords = ref([
  { id: 1, time: '2026-09-09 14:30:22', level: 'high', content: '温度超过告警阈值（当前68.5℃，阈值55℃）', duration: '1分53秒', status: 'processing' },
  { id: 2, time: '2026-09-09 14:29:18', level: 'critical', content: '烟雾浓度超标（当前5.2%/m，阈值0.5%/m）', duration: '2分57秒', status: 'processing' },
  { id: 3, time: '2026-09-08 16:42:30', level: 'medium', content: '电池电量过低（当前15%）', duration: '3小时', status: 'resolved' },
  { id: 4, time: '2026-09-07 09:15:08', level: 'high', content: '水压异常下降（当前0.45MPa）', duration: '45分钟', status: 'resolved' },
  { id: 5, time: '2026-09-05 22:08:55', level: 'medium', content: '信号强度减弱（当前35%）', duration: '2小时', status: 'resolved' },
])

const filteredDevices = computed(() => {
  let list = devices.value
  if (deviceSearch.value) {
    list = list.filter(d => d.device_code.includes(deviceSearch.value) || d.location.includes(deviceSearch.value))
  }
  if (deviceTypeFilter.value) {
    list = list.filter(d => d.type === deviceTypeFilter.value)
  }
  if (deviceStatusFilter.value) {
    list = list.filter(d => d.status === deviceStatusFilter.value)
  }
  return list
})

const filteredLogs = computed(() => {
  let list = logs.value
  if (logTypeFilter.value) {
    list = list.filter(l => l.type === logTypeFilter.value)
  }
  if (logStatusFilter.value) {
    list = list.filter(l => l.status === logStatusFilter.value)
  }
  return list
})

const onlineDeviceList = computed(() => {
  return devices.value.filter(d => d.status !== 'offline')
})

const valueUnit = computed(() => {
  if (!selectedSimDevice.value) return ''
  const map = {
    smoke: '%/m',
    temperature: '℃',
    water_pressure: 'MPa',
    electrical_fire: 'mA'
  }
  return map[selectedSimDevice.value.type] || ''
})

const yAxisMax = computed(() => {
  if (!selectedSimDevice.value) return 100
  const map = { smoke: 10, temperature: 80, water_pressure: 1.0, electrical_fire: 500 }
  return map[selectedSimDevice.value.type] || 100
})

const yAxisMin = computed(() => {
  if (!selectedSimDevice.value) return 0
  const map = { smoke: 0, temperature: 0, water_pressure: 0, electrical_fire: 0 }
  return map[selectedSimDevice.value.type] || 0
})

const linePath = computed(() => {
  if (wavePoints.value.length < 2) return ''
  return wavePoints.value.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(' ')
})

const areaPath = computed(() => {
  if (wavePoints.value.length < 2) return ''
  const line = wavePoints.value.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(' ')
  const lastX = wavePoints.value[wavePoints.value.length - 1].x
  const firstX = wavePoints.value[0].x
  return `${line} L ${lastX} 200 L ${firstX} 200 Z`
})

const historyData = ref([])

const historyLinePath = computed(() => {
  if (historyData.value.length < 2) return ''
  return historyData.value.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(' ')
})

const historyAreaPath = computed(() => {
  if (historyData.value.length < 2) return ''
  const line = historyData.value.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(' ')
  const lastX = historyData.value[historyData.value.length - 1].x
  const firstX = historyData.value[0].x
  return `${line} L ${lastX} 220 L ${firstX} 220 Z`
})

function deviceTypeText(type) {
  const map = { smoke: '烟感探测器', temperature: '温感探测器', water_pressure: '水压传感器', electrical_fire: '电气火灾' }
  return map[type] || '未知类型'
}

function deviceTypeTag(type) {
  const map = { smoke: '', temperature: 'warning', water_pressure: 'primary', electrical_fire: 'danger' }
  return map[type] || ''
}

function deviceIcon(type) {
  const map = { smoke: Position, temperature: Warning, water_pressure: Watermelon, electrical_fire: Lightning }
  return map[type] || Cpu
}

function statusText(status) {
  const map = { online: '在线', offline: '离线', alarm: '告警' }
  return map[status] || '未知'
}

function statusTagType(status) {
  const map = { online: 'success', offline: 'info', alarm: 'danger' }
  return map[status] || 'info'
}

function batteryColor(battery) {
  if (battery > 60) return '#22c55e'
  if (battery > 30) return '#f59e0b'
  return '#ef4444'
}

function logTypeText(type) {
  const map = { heartbeat: '心跳', data: '数据', alarm: '告警' }
  return map[type] || '未知'
}

function logTypeTag(type) {
  const map = { heartbeat: 'info', data: 'success', alarm: 'danger' }
  return map[type] || 'info'
}

function handleRowClick(row) {
  selectedDevice.value = row
  generateHistoryData()
}

function viewDetail(row) {
  selectedDevice.value = row
  activeTab.value = 'detail'
  generateHistoryData()
}

function simulateDevice(row) {
  selectedSimDevice.value = row
  activeTab.value = 'simulate'
  resetSimulation()
}

function selectSimDevice(device) {
  selectedSimDevice.value = device
  resetSimulation()
}

function resetSimulation() {
  stopSimulation()
  wavePoints.value = []
  dataPoints.value = 0
  isAlarming.value = false

  const baseValues = { smoke: 0.02, temperature: 25, water_pressure: 0.7, electrical_fire: 80 }
  const base = baseValues[selectedSimDevice.value?.type] || 50
  currentValue.value = base
  minValue.value = base
  maxValue.value = base
  avgValue.value = base
}

function toggleSimulation() {
  if (isSimulating.value) {
    stopSimulation()
  } else {
    startSimulation()
  }
}

function startSimulation() {
  if (!selectedSimDevice.value) {
    ElMessage.warning('请先选择一个设备')
    return
  }
  isSimulating.value = true
  simTimer = setInterval(updateSimData, updateInterval.value)
}

function stopSimulation() {
  isSimulating.value = false
  if (simTimer) {
    clearInterval(simTimer)
    simTimer = null
  }
}

function updateSimData() {
  const baseValues = { smoke: 0.02, temperature: 25, water_pressure: 0.7, electrical_fire: 80 }
  const ranges = { smoke: 0.01, temperature: 3, water_pressure: 0.05, electrical_fire: 20 }
  const alarmValues = { smoke: 5.2, temperature: 68.5, water_pressure: 0.35, electrical_fire: 380 }

  const type = selectedSimDevice.value.type
  const base = baseValues[type] || 50
  const range = ranges[type] || 10

  let newValue
  if (isAlarming.value) {
    newValue = alarmValues[type] + (Math.random() - 0.5) * range * 2
  } else {
    newValue = base + (Math.random() - 0.5) * range * 2
  }

  const diff = newValue - currentValue.value
  trendValue.value = Math.abs(diff)
  trendDir.value = diff >= 0 ? 'up' : 'down'
  currentValue.value = newValue

  if (dataPoints.value === 0) {
    minValue.value = newValue
    maxValue.value = newValue
  } else {
    minValue.value = Math.min(minValue.value, newValue)
    maxValue.value = Math.max(maxValue.value, newValue)
  }

  dataPoints.value++
  avgValue.value = avgValue.value + (newValue - avgValue.value) / dataPoints.value

  const yRange = yAxisMax.value - yAxisMin.value
  const y = 200 - ((newValue - yAxisMin.value) / yRange) * 180 - 10

  const xStep = 600 / 50
  wavePoints.value.push({ x: wavePoints.value.length * xStep, y: Math.max(10, Math.min(190, y)) })

  if (wavePoints.value.length > 50) {
    wavePoints.value.shift()
    wavePoints.value = wavePoints.value.map((p, i) => ({ ...p, x: i * xStep }))
  }

  addRandomLog()
}

function triggerAlarm() {
  if (!selectedSimDevice.value) {
    ElMessage.warning('请先选择设备')
    return
  }
  isAlarming.value = !isAlarming.value
  ElMessage.info(isAlarming.value ? '已触发模拟告警' : '已取消模拟告警')
}

function addRandomLog() {
  const types = ['heartbeat', 'data']
  const type = types[Math.floor(Math.random() * types.length)]
  const status = Math.random() > 0.05 ? 'success' : 'failed'
  const delay = status === 'success' ? Math.floor(Math.random() * 150 + 30) : Math.floor(Math.random() * 3000 + 1000)

  let content = ''
  const d = selectedSimDevice.value
  if (d.type === 'smoke') {
    content = `${type === 'heartbeat' ? '心跳包' : '数据上报'}: 烟雾浓度=${currentValue.value.toFixed(2)}%/m`
  } else if (d.type === 'temperature') {
    content = `${type === 'heartbeat' ? '心跳包' : '数据上报'}: 温度=${currentValue.value.toFixed(1)}℃`
  } else if (d.type === 'water_pressure') {
    content = `${type === 'heartbeat' ? '心跳包' : '数据上报'}: 水压=${currentValue.value.toFixed(2)}MPa`
  } else {
    content = `${type === 'heartbeat' ? '心跳包' : '数据上报'}: 剩余电流=${currentValue.value.toFixed(0)}mA`
  }

  if (isAlarming.value) {
    content = `告警上报: ${content}`
  }

  const now = new Date()
  const timeStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`

  logs.value.unshift({
    id: Date.now(),
    time: timeStr,
    device_code: d.device_code,
    type: isAlarming.value ? 'alarm' : type,
    content,
    status,
    delay
  })

  if (logs.value.length > 50) {
    logs.value = logs.value.slice(0, 50)
  }
}

function clearLogs() {
  logs.value = []
  ElMessage.success('日志已清空')
}

function generateHistoryData() {
  historyData.value = []
  const points = 48
  const baseValues = { smoke: 0.02, temperature: 25, water_pressure: 0.7, electrical_fire: 80 }
  const ranges = { smoke: 0.015, temperature: 8, water_pressure: 0.08, electrical_fire: 40 }
  const base = baseValues[selectedDevice.value?.type] || 50
  const range = ranges[selectedDevice.value?.type] || 20
  const yMax = yAxisMax.value
  const yMin = yAxisMin.value
  const yRange = yMax - yMin

  for (let i = 0; i < points; i++) {
    const x = (i / (points - 1)) * 800
    const noise = (Math.random() - 0.5) * range
    const trend = Math.sin(i / 6) * range * 0.5
    const value = base + noise + trend
    const y = 220 - ((value - yMin) / yRange) * 200 - 10
    historyData.value.push({ x, y: Math.max(10, Math.min(210, y)) })
  }
}

watch(updateInterval, () => {
  if (isSimulating.value) {
    stopSimulation()
    startSimulation()
  }
})

onMounted(() => {
  dataTimer = setInterval(() => {
    const count = parseInt(stats.value.todayData) + Math.floor(Math.random() * 5)
    stats.value.todayData = count + '.' + Math.floor(Math.random() * 10) + 'K'
  }, 3000)
})

onUnmounted(() => {
  stopSimulation()
  if (dataTimer) {
    clearInterval(dataTimer)
  }
})
</script>

<style scoped>
.iot-device-page {
  color: #0f172a;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.subtitle {
  margin: -4px 0 0;
  color: #64748b;
}

.stats-row {
  margin-bottom: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 4px;
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.cyan { background: linear-gradient(135deg, #06b6d4, #0891b2); }
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }

.stat-info .stat-num {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: #0f172a;
}

.stat-info .stat-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  margin-bottom: 12px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 20px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px;
  cursor: pointer;
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
  position: relative;
}

.tab-item:hover {
  color: #334155;
}

.tab-item.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 600;
}

.badge-dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
  margin-left: 2px;
}

.tab-content {
  padding-top: 4px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
}

.signal-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.signal-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 18px;
}

.signal-bars span {
  width: 3px;
  background: #e2e8f0;
  border-radius: 1px;
}

.signal-bars span:nth-child(1) { height: 4px; }
.signal-bars span:nth-child(2) { height: 8px; }
.signal-bars span:nth-child(3) { height: 12px; }
.signal-bars span:nth-child(4) { height: 16px; }
.signal-bars span:nth-child(5) { height: 18px; }

.signal-bars span.active {
  background: #22c55e;
}

.signal-text {
  font-size: 12px;
  color: #64748b;
  min-width: 32px;
}

.battery-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.battery-body {
  width: 36px;
  height: 14px;
  border: 1px solid #cbd5e1;
  border-radius: 2px;
  padding: 1px;
  position: relative;
}

.battery-body::after {
  content: '';
  position: absolute;
  right: -3px;
  top: 3px;
  width: 2px;
  height: 6px;
  background: #cbd5e1;
  border-radius: 0 1px 1px 0;
}

.battery-fill {
  height: 100%;
  border-radius: 1px;
  transition: width 0.3s;
}

.battery-text {
  font-size: 12px;
  color: #64748b;
  min-width: 32px;
}

.simulate-container {
  display: flex;
  gap: 16px;
  min-height: 500px;
}

.simulate-left {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  padding-right: 16px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 12px;
}

.panel-title .device-tag {
  font-size: 12px;
  font-weight: normal;
  color: #2563eb;
  background: #eff6ff;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.device-select-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 480px;
  overflow-y: auto;
}

.device-select-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.device-select-item:hover {
  border-color: #3b82f6;
  background: #f8fafc;
}

.device-select-item.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.device-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #fff;
  flex-shrink: 0;
}

.device-icon.smoke { background: linear-gradient(135deg, #64748b, #475569); }
.device-icon.temperature { background: linear-gradient(135deg, #f97316, #ea580c); }
.device-icon.water_pressure { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.device-icon.electrical_fire { background: linear-gradient(135deg, #ef4444, #dc2626); }

.device-info {
  flex: 1;
  min-width: 0;
}

.device-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-location {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.device-status-dot.online { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
.device-status-dot.alarm { background: #ef4444; box-shadow: 0 0 6px #ef4444; animation: blink 1s infinite; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.simulate-right {
  flex: 1;
  min-width: 0;
}

.simulate-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.simulate-controls {
  display: flex;
  gap: 10px;
}

.monitor-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.current-value-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 12px;
}

.value-card {
  background: #f8fafc;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}

.value-card.main {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
}

.value-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.value-num {
  font-size: 32px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.1;
}

.value-num.small {
  font-size: 20px;
}

.value-num.alarm {
  color: #ef4444;
  animation: pulse-alarm 0.5s infinite;
}

@keyframes pulse-alarm {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.value-unit {
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  margin-left: 4px;
}

.value-trend {
  font-size: 12px;
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.value-trend.up { color: #ef4444; }
.value-trend.down { color: #22c55e; }

.waveform-panel {
  background: #f8fafc;
  border-radius: 10px;
  padding: 16px;
}

.waveform-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.waveform-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.waveform-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.waveform-status .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
}

.waveform-status.running .status-dot {
  background: #22c55e;
  animation: pulse-dot 1s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.2); }
}

.waveform-container {
  position: relative;
  height: 200px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.waveform-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.grid-line-h {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: #f1f5f9;
}

.grid-line-h:nth-child(1) { top: 20%; }
.grid-line-h:nth-child(2) { top: 40%; }
.grid-line-h:nth-child(3) { top: 50%; }
.grid-line-h:nth-child(4) { top: 60%; }
.grid-line-h:nth-child(5) { top: 80%; }

.grid-line-v {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #f1f5f9;
}

.grid-line-v:nth-child(6) { left: 10%; }
.grid-line-v:nth-child(7) { left: 20%; }
.grid-line-v:nth-child(8) { left: 30%; }
.grid-line-v:nth-child(9) { left: 40%; }
.grid-line-v:nth-child(10) { left: 50%; }
.grid-line-v:nth-child(11) { left: 60%; }
.grid-line-v:nth-child(12) { left: 70%; }
.grid-line-v:nth-child(13) { left: 80%; }
.grid-line-v:nth-child(14) { left: 90%; }
.grid-line-v:nth-child(15) { left: 100%; }

.waveform-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.waveform-y-axis {
  position: absolute;
  right: 8px;
  top: 6px;
  bottom: 6px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
  pointer-events: none;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.param-item {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-label {
  font-size: 12px;
  color: #64748b;
}

.param-value {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.success-text {
  color: #16a34a;
  font-weight: 500;
}

.warning-text {
  color: #d97706;
  font-weight: 500;
}

.danger-text {
  color: #dc2626;
  font-weight: 500;
}

.detail-container {
  min-height: 400px;
}

.detail-card {
  margin-bottom: 16px;
}

.detail-card:last-child {
  margin-bottom: 0;
}

.detail-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e2e8f0;
}

.detail-info-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.info-label {
  color: #64748b;
  flex-shrink: 0;
}

.info-value {
  color: #0f172a;
  font-weight: 500;
  text-align: right;
  max-width: 60%;
  word-break: break-all;
}

.history-chart {
  position: relative;
  height: 220px;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 10px 25px;
}

.history-svg {
  width: 100%;
  height: 100%;
}

.chart-x-axis {
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 5px;
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
}
</style>
