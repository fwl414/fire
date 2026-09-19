<template>
  <div class="device-management">
    <div class="page-header">
      <div>
        <h2 class="page-title">设备管理</h2>
        <p class="page-desc">消防设备全生命周期管理，支持设备档案、状态监控、维保记录</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openAdd">
          <el-icon><Plus /></el-icon>
          新增设备
        </el-button>
        <el-button @click="exportData">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
      </div>
    </div>

    <el-row :gutter="12" class="stat-row">
      <el-col :xs="12" :sm="6" :md="4">
        <div class="stat-card total">
          <div class="stat-icon"><el-icon><Cpu /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">设备总数</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :md="4">
        <div class="stat-card online">
          <div class="stat-icon"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.normal }}</div>
            <div class="stat-label">正常运行</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :md="4">
        <div class="stat-card warning">
          <div class="stat-icon"><el-icon><Warning /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.warning }}</div>
            <div class="stat-label">待维保</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :md="4">
        <div class="stat-card danger">
          <div class="stat-icon"><el-icon><CircleClose /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.fault }}</div>
            <div class="stat-label">故障/离线</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :md="4">
        <div class="stat-card info">
          <div class="stat-icon"><el-icon><Clock /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.overdue }}</div>
            <div class="stat-label">超期未检</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :md="4">
        <div class="stat-card purple">
          <div class="stat-icon"><el-icon><Calendar /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.thisMonth }}</div>
            <div class="stat-label">本月新增</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm" @submit.prevent>
        <el-form-item label="设备名称">
          <el-input v-model="filterForm.keyword" placeholder="请输入设备名称/编号" clearable style="width: 200px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="filterForm.type" placeholder="全部类型" clearable style="width: 140px">
            <el-option v-for="t in deviceTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属建筑">
          <el-select v-model="filterForm.building" placeholder="全部建筑" clearable style="width: 160px">
            <el-option v-for="b in buildingList" :key="b.id" :label="b.building_name || b.name" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable style="width: 140px">
            <el-option label="正常运行" value="正常" />
            <el-option label="待维保" value="待维保" />
            <el-option label="故障" value="故障" />
            <el-option label="离线" value="离线" />
            <el-option label="已报废" value="已报废" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDevices">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="deviceList" border stripe v-loading="loading" style="width: 100%">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="device_code" label="设备编号" width="130" />
        <el-table-column prop="device_name" label="设备名称" min-width="150">
          <template #default="{ row }">
            <span class="device-name-link" @click="viewDetail(row)">{{ row.device_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="device_type" label="设备类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="getTypeTagType(row.device_type)">{{ row.device_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="所属建筑" min-width="140">
          <template #default="{ row }">
            <span>{{ getBuildingName(row.building_id) }}</span>
            <span v-if="row.floor_id" class="floor-info">· {{ getFloorName(row.floor_id) }}层</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="安装位置" min-width="150" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small" effect="light">
              <span class="status-dot"></span>
              {{ row.status || '正常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="install_date" label="安装日期" width="110" />
        <el-table-column prop="last_maintenance" label="上次维保" width="110" />
        <el-table-column prop="next_maintenance" label="下次维保" width="110">
          <template #default="{ row }">
            <span :class="{ 'overdue': isOverdue(row.next_maintenance) }">{{ row.next_maintenance || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewDetail(row)">详情</el-button>
            <el-button size="small" link @click="editDevice(row)">编辑</el-button>
            <el-button size="small" type="danger" link @click="deleteDevice(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadDevices"
          @current-change="loadDevices"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="680px">
      <el-form :model="deviceForm" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备名称" prop="device_name">
              <el-input v-model="deviceForm.device_name" placeholder="请输入设备名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备编号" prop="device_code">
              <el-input v-model="deviceForm.device_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备类型" prop="device_type">
              <el-select v-model="deviceForm.device_type" placeholder="请选择设备类型" style="width: 100%">
                <el-option v-for="t in deviceTypes" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备状态" prop="status">
              <el-select v-model="deviceForm.status" placeholder="请选择状态" style="width: 100%">
                <el-option label="正常运行" value="正常" />
                <el-option label="待维保" value="待维保" />
                <el-option label="故障" value="故障" />
                <el-option label="离线" value="离线" />
                <el-option label="已报废" value="已报废" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属建筑" prop="building_id">
              <el-select v-model="deviceForm.building_id" placeholder="请选择建筑" style="width: 100%" @change="onBuildingChange">
                <el-option v-for="b in buildingList" :key="b.id" :label="b.building_name || b.name" :value="b.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属楼层" prop="floor_id">
              <el-select v-model="deviceForm.floor_id" placeholder="请选择楼层" style="width: 100%">
                <el-option v-for="f in floorList" :key="f.id" :label="f.floor_name" :value="f.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="安装位置" prop="location">
              <el-input v-model="deviceForm.location" placeholder="请输入详细安装位置" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="安装日期" prop="install_date">
              <el-date-picker v-model="deviceForm.install_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="上次维保" prop="last_maintenance">
              <el-date-picker v-model="deviceForm.last_maintenance" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="下次维保" prop="next_maintenance">
              <el-date-picker v-model="deviceForm.next_maintenance" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="设备描述">
              <el-input v-model="deviceForm.description" type="textarea" :rows="3" placeholder="请输入设备描述、备注信息" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="设备监测详情" size="680px">
      <div v-if="currentDevice" class="device-detail">
        <div class="detail-header">
          <div>
            <div class="detail-title">{{ currentDevice.device_name }}</div>
            <div class="detail-sub">{{ currentDevice.device_code }} · {{ currentDevice.device_type }}</div>
          </div>
          <div class="detail-status">
            <el-tag :type="getStatusTagType(currentDevice.status)" size="large" effect="dark">
              <span class="status-indicator"></span>
              {{ currentDevice.status || '正常' }}
            </el-tag>
            <div class="last-report">最后上报: {{ lastReportTime }}</div>
          </div>
        </div>

        <div class="monitor-stats">
          <div class="monitor-stat" v-for="m in monitorData" :key="m.label">
            <div class="monitor-value" :style="{ color: m.color }">{{ m.value }}<small>{{ m.unit }}</small></div>
            <div class="monitor-label">{{ m.label }}</div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">
            <span>实时数据曲线</span>
            <div class="time-selector">
              <span :class="{ active: timeRange === '1h' }" @click="timeRange = '1h'">1小时</span>
              <span :class="{ active: timeRange === '24h' }" @click="timeRange = '24h'">24小时</span>
              <span :class="{ active: timeRange === '7d' }" @click="timeRange = '7d'">7天</span>
            </div>
          </div>
          <div ref="chartRef" class="detail-chart"></div>
        </div>

        <el-tabs v-model="detailTab" class="detail-tabs">
          <el-tab-pane label="基本信息" name="base">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="设备编号">{{ currentDevice.device_code || '-' }}</el-descriptions-item>
              <el-descriptions-item label="设备类型">{{ currentDevice.device_type || '-' }}</el-descriptions-item>
              <el-descriptions-item label="所属建筑">{{ getBuildingName(currentDevice.building_id) }}</el-descriptions-item>
              <el-descriptions-item label="所属楼层">{{ getFloorName(currentDevice.floor_id) }}层</el-descriptions-item>
              <el-descriptions-item label="安装位置">{{ currentDevice.location || '-' }}</el-descriptions-item>
              <el-descriptions-item label="安装日期">{{ currentDevice.install_date || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane label="报警历史" name="alarm">
            <div class="alarm-history">
              <div class="alarm-history-item" v-for="a in alarmHistory" :key="a.id">
                <div class="alarm-history-dot" :class="a.level"></div>
                <div class="alarm-history-content">
                  <div class="alarm-history-title">
                    {{ a.title }}
                    <el-tag size="small" :type="a.level === 'danger' ? 'danger' : 'warning'">{{ a.levelText }}</el-tag>
                  </div>
                  <div class="alarm-history-desc">{{ a.desc }}</div>
                  <div class="alarm-history-time">{{ a.time }}</div>
                </div>
              </div>
              <el-empty v-if="!alarmHistory.length" description="暂无报警记录" :image-size="60" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="维保记录" name="maintenance">
            <div class="timeline">
              <div class="timeline-item" v-for="m in maintenanceRecords" :key="m.id">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <div class="timeline-title">{{ m.title }}</div>
                  <div class="timeline-desc">{{ m.desc }}</div>
                  <div class="timeline-time">{{ m.time }} · {{ m.operator }}</div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>

        <div class="detail-actions">
          <el-button type="primary" @click="editFromDetail">编辑设备</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  Plus,
  Download,
  Search,
  Cpu,
  CircleCheck,
  Warning,
  CircleClose,
  Clock,
  Calendar
} from '@element-plus/icons-vue'
import request from '../api'
import { getGisBuildings } from '../api/gis'
import { listFloors } from '../api/floor'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const chartRef = ref(null)
const currentDevice = ref(null)
const detailTab = ref('base')
const timeRange = ref('1h')

let detailChart = null

const deviceList = ref([])
const buildingList = ref([])
const floorList = ref([])

const lastReportTime = computed(() => {
  const now = new Date()
  now.setMinutes(now.getMinutes() - Math.floor(Math.random() * 10))
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
})

const monitorData = computed(() => {
  const type = currentDevice.value?.device_type || ''
  if (type.includes('烟感')) {
    return [
      { label: '烟雾浓度', value: (Math.random() * 0.5 + 0.1).toFixed(2), unit: ' %obs/m', color: '#ff6b6b' },
      { label: '工作温度', value: (Math.random() * 15 + 20).toFixed(1), unit: ' ℃', color: '#ff9500' },
      { label: '电池电量', value: Math.floor(Math.random() * 30 + 70), unit: ' %', color: '#34c759' },
      { label: '信号强度', value: Math.floor(Math.random() * 20 + 80), unit: ' %', color: '#00d4ff' },
    ]
  } else if (type.includes('温感')) {
    return [
      { label: '当前温度', value: (Math.random() * 20 + 18).toFixed(1), unit: ' ℃', color: '#ff9500' },
      { label: '报警阈值', value: 68, unit: ' ℃', color: '#ff3b30' },
      { label: '电池电量', value: Math.floor(Math.random() * 30 + 70), unit: ' %', color: '#34c759' },
      { label: '信号强度', value: Math.floor(Math.random() * 20 + 80), unit: ' %', color: '#00d4ff' },
    ]
  } else if (type.includes('消火栓') || type.includes('喷淋')) {
    return [
      { label: '水压值', value: (Math.random() * 0.3 + 0.8).toFixed(2), unit: ' MPa', color: '#00d4ff' },
      { label: '阀门状态', value: 1, unit: ' 正常', color: '#34c759' },
      { label: '流量', value: (Math.random() * 5 + 2).toFixed(1), unit: ' L/s', color: '#00aaff' },
      { label: '信号强度', value: Math.floor(Math.random() * 20 + 80), unit: ' %', color: '#8b5cf6' },
    ]
  } else {
    return [
      { label: '工作状态', value: 1, unit: ' 正常', color: '#34c759' },
      { label: '工作电压', value: (Math.random() * 1 + 11).toFixed(1), unit: ' V', color: '#ffcc00' },
      { label: '电池电量', value: Math.floor(Math.random() * 30 + 70), unit: ' %', color: '#34c759' },
      { label: '信号强度', value: Math.floor(Math.random() * 20 + 80), unit: ' %', color: '#00d4ff' },
    ]
  }
})

const alarmHistory = computed(() => {
  const status = currentDevice.value?.status
  if (status === '故障' || status === '离线') {
    return [
      { id: 1, title: '设备通信中断', level: 'danger', levelText: '故障', desc: '设备连续3次心跳超时，判定为离线状态', time: '2026-09-09 10:23:45' },
      { id: 2, title: '电池电压低', level: 'warning', levelText: '预警', desc: '设备电池电压低于阈值，建议尽快更换电池', time: '2026-09-08 16:45:12' },
    ]
  }
  return [
    { id: 1, title: '烟雾浓度异常', level: 'warning', levelText: '预警', desc: '烟雾浓度短暂升高，已自动恢复正常', time: '2026-09-05 14:32:18' },
  ]
})

const maintenanceRecords = computed(() => [
  { id: 1, title: '月度例行维保', desc: '对设备进行外观检查、功能测试、清洁维护，设备运行正常', time: '2026-08-15', operator: '张工' },
  { id: 2, title: '电池更换', desc: '设备电池使用到期，更换全新锂电池', time: '2026-06-20', operator: '李工' },
  { id: 3, title: '季度检测', desc: '季度全面检测，包括功能测试、模拟报警、联动测试', time: '2026-03-10', operator: '王工' },
])

const filterForm = ref({
  keyword: '',
  type: '',
  building: '',
  status: ''
})

const pagination = ref({
  page: 1,
  size: 20,
  total: 0
})

const deviceForm = ref({
  device_name: '',
  device_code: '',
  device_type: '烟感探测器',
  status: '正常',
  building_id: null,
  floor_id: null,
  location: '',
  install_date: '',
  last_maintenance: '',
  next_maintenance: '',
  description: ''
})

const formRules = {
  device_name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  building_id: [{ required: true, message: '请选择所属建筑', trigger: 'change' }],
}

const deviceTypes = [
  '烟感探测器', '温感探测器', '手动报警按钮', '消火栓', '喷淋头',
  '防火门', '灭火器', '应急照明', '疏散指示', '消防水泵',
  '稳压泵', '水流指示器', '信号蝶阀', '排烟风机', '防火卷帘'
]

const stats = computed(() => {
  const list = deviceList.value
  return {
    total: list.length,
    normal: list.filter(d => d.status === '正常' || !d.status).length,
    warning: list.filter(d => d.status === '待维保').length,
    fault: list.filter(d => d.status === '故障' || d.status === '离线').length,
    overdue: list.filter(d => isOverdue(d.next_maintenance)).length,
    thisMonth: list.filter(d => {
      if (!d.install_date) return false
      const d1 = new Date(d.install_date)
      const now = new Date()
      return d1.getMonth() === now.getMonth() && d1.getFullYear() === now.getFullYear()
    }).length
  }
})

const dialogTitle = computed(() => isEdit.value ? '编辑设备' : '新增设备')

function getTypeTagType(type) {
  const map = {
    '烟感探测器': 'danger',
    '温感探测器': 'warning',
    '消火栓': 'primary',
    '灭火器': 'success',
    '喷淋头': 'info',
    '防火门': 'success',
  }
  return map[type] || 'info'
}

function getStatusTagType(status) {
  if (!status || status === '正常') return 'success'
  if (status === '待维保') return 'warning'
  if (status === '故障' || status === '离线') return 'danger'
  if (status === '已报废') return 'info'
  return 'info'
}

function isOverdue(dateStr) {
  if (!dateStr) return false
  return new Date(dateStr) < new Date(new Date().toDateString())
}

function getBuildingName(id) {
  const b = buildingList.value.find(x => x.id === id)
  return b ? (b.building_name || b.name) : '-'
}

function getFloorName(id) {
  const f = floorList.value.find(x => x.id === id)
  return f ? f.floor_number : '-'
}

async function loadBuildings() {
  try {
    const res = await getGisBuildings()
    buildingList.value = res.data?.buildings || res.data || []
  } catch (e) {
    buildingList.value = [
      { id: 1, building_name: '综合办公楼A座' },
      { id: 2, building_name: '实验楼B座' },
      { id: 3, building_name: '学生宿舍C区' },
    ]
  }
}

async function loadFloors(buildingId) {
  if (!buildingId) {
    floorList.value = []
    return
  }
  try {
    const res = await listFloors(buildingId)
    floorList.value = res.data || []
  } catch (e) {
    floorList.value = [
      { id: 1, floor_name: '1层', floor_number: 1 },
      { id: 2, floor_name: '2层', floor_number: 2 },
      { id: 3, floor_name: '3层', floor_number: 3 },
    ]
  }
}

async function loadDevices() {
  loading.value = true
  try {
    const res = await request.get('/api/devices', { params: {
      page: pagination.value.page,
      page_size: pagination.value.size,
      keyword: filterForm.value.keyword,
      device_type: filterForm.value.type,
      building_id: filterForm.value.building,
      status: filterForm.value.status,
    }})
    deviceList.value = res.data?.items || res.data || mockDevices()
    pagination.value.total = res.data?.total || deviceList.value.length
  } catch (e) {
    deviceList.value = mockDevices()
    pagination.value.total = deviceList.value.length
  } finally {
    loading.value = false
  }
}

function mockDevices() {
  const types = deviceTypes
  const buildings = buildingList.value.length ? buildingList.value : [
    { id: 1, building_name: '综合办公楼A座' },
    { id: 2, building_name: '实验楼B座' },
    { id: 3, building_name: '学生宿舍C区' },
  ]
  const statuses = ['正常', '正常', '正常', '待维保', '故障', '离线']
  const arr = []
  for (let i = 1; i <= 35; i++) {
    const b = buildings[i % buildings.length]
    arr.push({
      id: i,
      device_code: `FD${String(i).padStart(6, '0')}`,
      device_name: `${types[i % types.length]}-${String(i).padStart(3, '0')}`,
      device_type: types[i % types.length],
      building_id: b.id,
      floor_id: (i % 5) + 1,
      location: `${b.building_name} ${i % 5 + 1}层 ${i % 10 + 1}号点位`,
      status: statuses[i % statuses.length],
      install_date: `2024-${String((i % 12) + 1).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
      last_maintenance: `2026-${String(((i * 2) % 9) + 1).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
      next_maintenance: i % 5 === 0 ? `2026-0${(i % 3) + 1}-${String((i % 28) + 1).padStart(2, '0')}` : `2026-1${(i % 3)}-${String((i % 28) + 1).padStart(2, '0')}`,
      description: '消防设备，定期检查维护'
    })
  }
  return arr
}

function resetFilter() {
  filterForm.value = { keyword: '', type: '', building: '', status: '' }
  pagination.value.page = 1
  loadDevices()
}

function openAdd() {
  isEdit.value = false
  deviceForm.value = {
    device_name: '',
    device_code: '',
    device_type: '烟感探测器',
    status: '正常',
    building_id: null,
    floor_id: null,
    location: '',
    install_date: '',
    last_maintenance: '',
    next_maintenance: '',
    description: ''
  }
  floorList.value = []
  dialogVisible.value = true
}

function editDevice(row) {
  isEdit.value = true
  deviceForm.value = { ...row }
  loadFloors(row.building_id)
  dialogVisible.value = true
}

function viewDetail(row) {
  currentDevice.value = row
  detailVisible.value = true
  detailTab.value = 'base'
  nextTick(() => {
    initDetailChart()
  })
}

function initDetailChart() {
  if (!chartRef.value) return
  if (detailChart) detailChart.dispose()
  
  detailChart = echarts.init(chartRef.value)
  
  const type = currentDevice.value?.device_type || ''
  let yAxisName = '数值'
  let seriesName = '监测值'
  let color = '#00d4ff'
  let baseValue = 25
  
  if (type.includes('烟感')) {
    yAxisName = '烟雾浓度(%obs/m)'
    seriesName = '烟雾浓度'
    color = '#ff6b6b'
    baseValue = 0.3
  } else if (type.includes('温感')) {
    yAxisName = '温度(℃)'
    seriesName = '温度'
    color = '#ff9500'
    baseValue = 25
  } else if (type.includes('消火栓') || type.includes('喷淋')) {
    yAxisName = '水压(MPa)'
    seriesName = '水压'
    color = '#00d4ff'
    baseValue = 0.9
  }
  
  const hours = timeRange.value === '1h' ? 12 : timeRange.value === '24h' ? 24 : 7
  const xData = []
  const seriesData = []
  
  for (let i = hours - 1; i >= 0; i--) {
    if (timeRange.value === '1h') {
      xData.push(`${i * 5}分前`)
    } else if (timeRange.value === '24h') {
      xData.push(`${i}时前`)
    } else {
      xData.push(`${i}天前`)
    }
    seriesData.push(baseValue + (Math.random() - 0.5) * baseValue * 0.4)
  }
  
  detailChart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, right: 20, bottom: 30, left: 60 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: xData.reverse(),
      axisLine: { lineStyle: { color: '#ddd' } },
      axisLabel: { color: '#666', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
      nameTextStyle: { color: '#666', fontSize: 11 },
      axisLine: { show: false },
      axisLabel: { color: '#666', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [{
      name: seriesName,
      type: 'line',
      data: seriesData.reverse(),
      smooth: true,
      lineStyle: { color, width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color + '40' },
          { offset: 1, color: color + '05' },
        ])
      },
      itemStyle: { color },
    }]
  })
}

watch(timeRange, () => {
  if (detailVisible.value) {
    nextTick(() => initDetailChart())
  }
})

function editFromDetail() {
  detailVisible.value = false
  editDevice(currentDevice.value)
}

async function onBuildingChange(buildingId) {
  deviceForm.value.floor_id = null
  await loadFloors(buildingId)
}

async function saveDevice() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await request.put(`/api/devices/${deviceForm.value.id}`, deviceForm.value)
      ElMessage.success('更新成功')
    } else {
      await request.post('/api/devices', deviceForm.value)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadDevices()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteDevice(row) {
  try {
    await ElMessageBox.confirm(`确认删除设备 "${row.device_name}" 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消'
    })
    await request.delete(`/api/devices/${row.id}`)
    ElMessage.success('删除成功')
    loadDevices()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function exportData() {
  ElMessage.info('导出功能开发中')
}

onMounted(() => {
  loadBuildings()
  loadDevices()
})
</script>

<style scoped>
.device-management {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 6px;
}

.page-desc {
  color: #64748b;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.stat-row {
  margin-bottom: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
  flex-shrink: 0;
}

.stat-card.total .stat-icon { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-card.online .stat-icon { background: linear-gradient(135deg, #4ade80, #22c55e); }
.stat-card.warning .stat-icon { background: linear-gradient(135deg, #fbbf24, #f59e0b); }
.stat-card.danger .stat-icon { background: linear-gradient(135deg, #f87171, #ef4444); }
.stat-card.info .stat-icon { background: linear-gradient(135deg, #60a5fa, #3b82f6); }
.stat-card.purple .stat-icon { background: linear-gradient(135deg, #a78bfa, #8b5cf6); }

.stat-content { flex: 1; }

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 12px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.table-card {
  margin-bottom: 12px;
}

.device-name-link {
  color: #2563eb;
  cursor: pointer;
}

.device-name-link:hover {
  text-decoration: underline;
}

.floor-info {
  color: #64748b;
  font-size: 12px;
}

.status-dot {
  margin-right: 4px;
  font-size: 10px;
}

.overdue {
  color: #ef4444;
  font-weight: 600;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.device-detail {
  padding: 10px 0;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.detail-title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.detail-sub {
  color: #64748b;
  font-size: 13px;
}

.detail-status {
  text-align: right;
}

.status-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  margin-right: 6px;
  animation: pulse 2s infinite;
}

.last-report {
  color: #94a3b8;
  font-size: 12px;
  margin-top: 6px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.monitor-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.monitor-stat {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  text-align: center;
}

.monitor-value {
  font-size: 22px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  line-height: 1.2;
}

.monitor-value small {
  font-size: 12px;
  font-weight: 500;
  margin-left: 2px;
}

.monitor-label {
  color: #64748b;
  font-size: 12px;
  margin-top: 6px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.time-selector {
  display: flex;
  gap: 4px;
  background: #f1f5f9;
  padding: 3px;
  border-radius: 6px;
}

.time-selector span {
  padding: 4px 10px;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.time-selector span.active {
  background: #fff;
  color: #2563eb;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.detail-chart {
  width: 100%;
  height: 200px;
}

.detail-tabs {
  margin-top: 10px;
}

.alarm-history {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alarm-history-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 3px solid #f59e0b;
}

.alarm-history-item.danger {
  border-left-color: #ef4444;
}

.alarm-history-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;
  background: #f59e0b;
}

.alarm-history-dot.danger {
  background: #ef4444;
}

.alarm-history-content {
  flex: 1;
  min-width: 0;
}

.alarm-history-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #1e293b;
  font-size: 13px;
  margin-bottom: 6px;
}

.alarm-history-desc {
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 6px;
}

.alarm-history-time {
  color: #94a3b8;
  font-size: 11px;
}

.timeline {
  position: relative;
  padding-left: 20px;
}

.timeline-item {
  position: relative;
  padding-bottom: 20px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: -20px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #3b82f6;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #3b82f6;
}

.timeline-item::before {
  content: '';
  position: absolute;
  left: -15px;
  top: 16px;
  bottom: 0;
  width: 2px;
  background: #e2e8f0;
}

.timeline-item:last-child::before {
  display: none;
}

.timeline-content {
  background: #f8fafc;
  padding: 12px;
  border-radius: 8px;
}

.timeline-title {
  font-weight: 600;
  color: #1e293b;
  font-size: 13px;
  margin-bottom: 6px;
}

.timeline-desc {
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 6px;
}

.timeline-time {
  color: #94a3b8;
  font-size: 11px;
}

.detail-desc {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}

.detail-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}
</style>
