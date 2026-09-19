<template>
  <div class="report-center-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">统计报表中心</h2>
        <p class="page-desc">多维度数据统计分析与报表导出</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
        <el-button type="primary" @click="showExportDialog = true">
          <el-icon><Download /></el-icon>
          导出报表
        </el-button>
      </div>
    </div>

    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="报表类型">
          <el-select v-model="filters.report_type" style="width: 160px" @change="loadData">
            <el-option label="巡检统计报表" value="inspection" />
            <el-option label="工单统计报表" value="workorder" />
            <el-option label="风险分析报表" value="risk" />
            <el-option label="设备统计报表" value="device" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
            @change="onDateChange"
          />
        </el-form-item>
        <el-form-item label="建筑/区域">
          <el-select v-model="filters.building_id" placeholder="全部建筑" clearable style="width: 160px">
            <el-option label="综合办公楼A座" value="building_001" />
            <el-option label="实验楼B座" value="building_002" />
            <el-option label="学生宿舍C区" value="building_003" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="summary-row">
      <el-col :span="6" v-for="(item, idx) in summaryCards" :key="idx">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-icon" :class="item.colorClass">{{ item.icon }}</div>
          <div class="summary-content">
            <div class="summary-value">{{ item.value }}</div>
            <div class="summary-label">{{ item.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>{{ chartTitle }}</span>
            </div>
          </template>
          <div class="chart-container">
            <div ref="trendChartRef" class="trend-chart"></div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="side-card">
          <template #header>
            <div class="card-header">
              <span>{{ sideTitle }}</span>
            </div>
          </template>
          <div class="side-content">
            <div ref="pieChartRef" class="pie-chart"></div>
            <template v-if="filters.report_type === 'risk'">
              <div v-for="(item, idx) in riskFactors" :key="idx" class="factor-item" style="margin-top: 12px;">
                <div class="factor-header">
                  <span class="factor-name">{{ item.factor }}</span>
                  <span class="factor-weight">{{ item.weight }}%</span>
                </div>
                <el-progress :percentage="item.weight" :show-text="false" :status="item.trend === 'up' ? 'exception' : item.trend === 'down' ? 'success' : ''" />
                <div class="factor-trend" :class="item.trend">
                  趋势：{{ item.trend === 'up' ? '上升' : item.trend === 'down' ? '下降' : '稳定' }}
                </div>
              </div>
            </template>
            <template v-else-if="filters.report_type === 'device'">
              <div v-for="(item, idx) in deviceByType" :key="idx" class="device-item" style="margin-top: 12px;">
                <div class="device-header">
                  <span class="device-name">{{ item.name }}</span>
                  <span class="device-count">{{ item.onlineCount || 0 }}/{{ item.total || 0 }}</span>
                </div>
                <el-progress :percentage="Math.round((item.onlineCount || 0) / (item.total || 1) * 100)" :show-text="false" :status="(item.onlineCount || 0) / (item.total || 1) > 0.9 ? 'success' : (item.onlineCount || 0) / (item.total || 1) > 0.7 ? '' : 'exception'" />
                <div class="device-meta">
                  <span>离线: {{ item.offlineCount || 0 }}</span>
                  <span style="color: #ef4444">告警: {{ item.alertCount || 0 }}</span>
                </div>
              </div>
            </template>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="detail-card" v-if="filters.report_type === 'inspection'">
      <template #header>
        <div class="card-header">
          <span>各建筑巡检统计</span>
        </div>
      </template>
      <el-table :data="buildingStats" stripe>
        <el-table-column prop="name" label="建筑名称" min-width="160" />
        <el-table-column prop="value" label="巡检次数" width="120" />
        <el-table-column prop="highCount" label="高风险数" width="120">
          <template #default="{ row }">
            <el-tag type="danger" size="small">{{ row.highCount || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="mediumCount" label="中风险数" width="120">
          <template #default="{ row }">
            <el-tag type="warning" size="small">{{ row.mediumCount || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="avgRiskScore" label="平均风险分" width="120" />
      </el-table>
    </el-card>

    <el-card class="detail-card" v-if="filters.report_type === 'risk'">
      <template #header>
        <div class="card-header">
          <span>各建筑风险评分</span>
        </div>
      </template>
      <el-table :data="buildingsRisk" stripe>
        <el-table-column prop="name" label="建筑名称" min-width="160" />
        <el-table-column label="风险评分" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.avg_score || row.value || 0" :status="(row.avg_score || row.value || 0) > 70 ? 'exception' : (row.avg_score || row.value || 0) > 40 ? 'warning' : 'success'" />
          </template>
        </el-table-column>
        <el-table-column prop="avg_score" label="风险分" width="100" />
        <el-table-column label="趋势" width="100">
          <template #default="{ row }">
            <el-tag :type="'info'" size="small">
              稳定
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showExportDialog" title="导出报表" width="420px">
      <el-form :model="exportForm" label-width="100px">
        <el-form-item label="报表类型">
          <el-select v-model="exportForm.report_type" style="width: 100%">
            <el-option label="巡检统计报表" value="inspection" />
            <el-option label="工单统计报表" value="workorder" />
            <el-option label="风险分析报表" value="risk" />
            <el-option label="设备统计报表" value="device" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="exportDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio value="excel">Excel (.xlsx)</el-radio>
            <el-radio value="csv">CSV (.csv)</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExportDialog = false">取消</el-button>
        <el-button type="primary" @click="doExport" :loading="exporting">确认导出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { reportStatistics, reportExport } from '../api'

const loading = ref(false)
const exporting = ref(false)
const reportData = ref(null)
const dateRange = ref([])

const trendChartRef = ref(null)
const pieChartRef = ref(null)
let trendChart = null
let pieChart = null

const filters = ref({
  report_type: 'inspection',
  building_id: '',
  start_date: '',
  end_date: ''
})

const showExportDialog = ref(false)
const exportDateRange = ref([])
const exportForm = ref({
  report_type: 'inspection',
  format: 'excel'
})

const chartTitle = computed(() => {
  const titles = {
    inspection: '巡检趋势',
    workorder: '工单趋势',
    risk: '风险分布',
    device: '设备告警趋势'
  }
  return titles[filters.value.report_type] || '数据趋势'
})

const sideTitle = computed(() => {
  const titles = {
    inspection: '隐患类型排行',
    workorder: '📋 工单类型分布',
    risk: '风险因子分析',
    device: '📡 设备类型统计'
  }
  return titles[filters.value.report_type] || '统计分析'
})

const summaryCards = computed(() => {
  const data = reportData.value?.summary || {}
  const type = filters.value.report_type
  
  if (type === 'inspection') {
    return [
      { label: '巡检总数', value: data.total || 0, icon: '📋', colorClass: 'blue' },
      { label: '高风险', value: data.highCount || 0, icon: '🔴', colorClass: 'red' },
      { label: '中风险', value: data.mediumCount || 0, icon: '🟡', colorClass: 'orange' },
      { label: '高风险率', value: (data.highRiskRate || 0) + '%', icon: '', colorClass: 'purple' }
    ]
  } else if (type === 'workorder') {
    return [
      { label: '工单总数', value: data.total || 0, icon: '📋', colorClass: 'blue' },
      { label: '已完成', value: data.completedCount || 0, icon: '', colorClass: 'green' },
      { label: '处理中', value: data.processingCount || 0, icon: '⏳', colorClass: 'orange' },
      { label: '完成率', value: (data.completionRate || 0) + '%', icon: '', colorClass: 'purple' }
    ]
  } else if (type === 'risk') {
    return [
      { label: '建筑总数', value: data.total || 0, icon: '', colorClass: 'blue' },
      { label: '平均风险分', value: data.avgRiskScore || 0, icon: '', colorClass: 'orange' },
      { label: '高风险建筑', value: data.highCount || 0, icon: '🔴', colorClass: 'red' },
      { label: '中风险建筑', value: data.mediumCount || 0, icon: '🟡', colorClass: 'orange' }
    ]
  } else if (type === 'device') {
    return [
      { label: '设备总数', value: data.total || 0, icon: '📡', colorClass: 'blue' },
      { label: '在线设备', value: data.onlineCount || 0, icon: '', colorClass: 'green' },
      { label: '离线设备', value: data.offlineCount || 0, icon: '⚠️', colorClass: 'orange' },
      { label: '在线率', value: (data.onlineRate || 0) + '%', icon: '', colorClass: 'purple' }
    ]
  }
  return []
})

const chartData = computed(() => {
  if (filters.value.report_type === 'risk') {
    return reportData.value?.trend || []
  }
  return reportData.value?.trend || []
})

const topHazards = computed(() => reportData.value?.byCategory || [])
const workorderByType = computed(() => reportData.value?.byCategory || [])
const riskFactors = computed(() => reportData.value?.byCategory || [])
const deviceByType = computed(() => reportData.value?.byCategory || [])
const buildingStats = computed(() => reportData.value?.byCategory || [])
const buildingsRisk = computed(() => reportData.value?.trend || [])

function onDateChange(val) {
  if (val && val.length === 2) {
    filters.value.start_date = val[0]
    filters.value.end_date = val[1]
  } else {
    filters.value.start_date = ''
    filters.value.end_date = ''
  }
}

function resetFilters() {
  filters.value = {
    report_type: 'inspection',
    building_id: '',
    start_date: '',
    end_date: ''
  }
  dateRange.value = []
  loadData()
}

async function loadData() {
  loading.value = true
  try {
    const params = {
      report_type: filters.value.report_type
    }
    if (filters.value.start_date) params.start_date = filters.value.start_date
    if (filters.value.end_date) params.end_date = filters.value.end_date
    if (filters.value.building_id) params.building_id = filters.value.building_id
    
    const res = await reportStatistics(params)
    reportData.value = res.data
  } catch (e) {
    console.error('加载统计数据失败', e)
    ElMessage.error('加载统计数据失败')
  } finally {
    loading.value = false
  }
}

function refreshData() {
  loadData()
}

async function doExport() {
  exporting.value = true
  try {
    const params = {
      report_type: exportForm.value.report_type,
      format: exportForm.value.format
    }
    if (exportDateRange.value && exportDateRange.value.length === 2) {
      params.start_date = exportDateRange.value[0]
      params.end_date = exportDateRange.value[1]
    }
    
    // 导出失败就如实报错：不要伪造一个「导出成功」的文件糊弄用户
    const res = await reportExport(params)
    
    const data = res.data
    const contentType = res.headers['content-type'] || ''
    
    if (contentType.includes('application/json')) {
      const reader = new FileReader()
      reader.onload = () => {
        try {
          const json = JSON.parse(reader.result)
          ElMessage.error(json.message || '导出报表失败')
        } catch {
          ElMessage.error('导出报表失败')
        }
      }
      reader.readAsText(data)
      return
    }
    
    const url = window.URL.createObjectURL(new Blob([data]))
    const link = document.createElement('a')
    link.href = url
    
    const disposition = res.headers['content-disposition']
    let filename = `fire_report.${exportForm.value.format === 'excel' ? 'xlsx' : 'csv'}`
    if (disposition) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match) filename = match[1]
    }
    
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('报表导出成功')
    showExportDialog.value = false
  } catch (e) {
    console.error('导出报表失败', e)
    const msg = e?.response?.data?.message || e?.message || '导出报表失败'
    ElMessage.error(msg)
  } finally {
    exporting.value = false
  }
}

function initCharts() {
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
    updateTrendChart()
  }
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    updatePieChart()
  }
}

function updateTrendChart() {
  if (!trendChart || !chartData.value.length) return
  const type = filters.value.report_type
  let series = []
  if (type === 'inspection') {
    series = [
      { name: '高风险', type: 'line', data: chartData.value.map(d => d.highCount || d.count || 0), smooth: true, itemStyle: { color: '#ef4444' } },
      { name: '中风险', type: 'line', data: chartData.value.map(d => d.mediumCount || d.count || 0), smooth: true, itemStyle: { color: '#f59e0b' } },
      { name: '低风险', type: 'line', data: chartData.value.map(d => d.lowCount || d.count || 0), smooth: true, itemStyle: { color: '#22c55e' } },
    ]
  } else if (type === 'workorder') {
    series = [
      { name: '新增工单', type: 'bar', data: chartData.value.map(d => d.count || 0), itemStyle: { color: '#3b82f6' } },
    ]
  } else if (type === 'device') {
    series = [
      { name: '告警数量', type: 'line', data: chartData.value.map(d => d.count || 0), smooth: true, areaStyle: { opacity: 0.2 }, itemStyle: { color: '#ef4444' } },
    ]
  } else if (type === 'risk') {
    series = [
      { name: '平均风险分', type: 'line', data: chartData.value.map(d => d.avg_score || d.value || 0), smooth: true, areaStyle: { opacity: 0.15 }, itemStyle: { color: '#8b5cf6' } },
    ]
  }
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name), top: 0 },
    grid: { top: 40, right: 20, bottom: 30, left: 50 },
    xAxis: {
      type: 'category',
      data: chartData.value.map(d => d.date || d.name || '未知'),
      axisLine: { lineStyle: { color: '#ddd' } },
      axisLabel: { color: '#666', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#666', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series
  })
}

function updatePieChart() {
  if (!pieChart) return
  const type = filters.value.report_type
  let data = []
  let title = ''
  if (type === 'inspection') {
    data = topHazards.value.map(h => ({ name: h.name, value: h.value || h.count || 0 }))
    title = '隐患类型分布'
  } else if (type === 'workorder') {
    data = workorderByType.value.map(w => ({ name: w.name, value: w.value || w.count || 0 }))
    title = '工单类型占比'
  } else if (type === 'risk') {
    data = riskFactors.value.map(r => ({ name: r.name, value: r.value || r.weight || 0 }))
    title = '风险因素占比'
  } else if (type === 'device') {
    data = deviceByType.value.map(d => ({ name: d.name, value: d.value || d.total || 0 }))
    title = '设备类型分布'
  }
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    title: { text: title, left: 'center', top: 0, textStyle: { fontSize: 14, fontWeight: 600, color: '#0f172a' } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '55%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, fontSize: 11, color: '#475569' },
      labelLine: { show: true, length: 8, length2: 6 },
      data,
    }],
    color: ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316']
  })
}

function handleResize() {
  trendChart?.resize()
  pieChart?.resize()
}

watch(() => filters.value.report_type, () => {
  nextTick(() => {
    updateTrendChart()
    updatePieChart()
  })
})

watch(chartData, () => {
  nextTick(() => {
    updateTrendChart()
    updatePieChart()
  })
}, { deep: true })

onMounted(() => {
  loadData()
  nextTick(() => {
    initCharts()
    window.addEventListener('resize', handleResize)
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.report-center-page {
  padding: 0;
}
.chart-container {
  min-height: 320px;
}

.trend-chart {
  width: 100%;
  height: 320px;
}

.pie-chart {
  width: 100%;
  height: 240px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-title {
  font-size: 24px;
  font-weight: 800;
  margin: 0 0 6px;
  color: var(--fire-text);
}
.page-desc {
  color: var(--fire-muted);
  margin: 0;
  font-size: 14px;
}
.header-actions {
  display: flex;
  gap: 10px;
}
.filter-card {
  margin-bottom: 16px;
}
.summary-row {
  margin-bottom: 16px;
}
.summary-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 4px;
}
.summary-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
}
.summary-icon.blue { background: #eff6ff; }
.summary-icon.green { background: #dcfce7; }
.summary-icon.red { background: #fee2e2; }
.summary-icon.orange { background: #fef3c7; }
.summary-icon.purple { background: #f3e8ff; }
.summary-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}
.summary-label {
  color: var(--fire-muted);
  font-size: 13px;
  margin-top: 4px;
}
.chart-card, .side-card, .detail-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}
.chart-container {
  min-height: 300px;
}
.side-content {
  max-height: 380px;
  overflow-y: auto;
}
.rank-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}
.rank-item:last-child {
  border-bottom: none;
}
.rank-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  margin-right: 12px;
  color: #64748b;
}
.rank-num.top {
  background: #f59e0b;
  color: white;
}
.rank-name {
  flex: 1;
  font-size: 14px;
  color: #334155;
}
.rank-count {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}
.factor-item {
  padding: 12px 0;
  border-bottom: 1px solid #f1f5f9;
}
.factor-item:last-child {
  border-bottom: none;
}
.factor-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.factor-name {
  font-size: 14px;
  color: #334155;
}
.factor-weight {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}
.factor-trend {
  font-size: 12px;
  margin-top: 4px;
}
.factor-trend.up { color: #ef4444; }
.factor-trend.down { color: #22c55e; }
.factor-trend.stable { color: #64748b; }
.device-item {
  padding: 12px 0;
  border-bottom: 1px solid #f1f5f9;
}
.device-item:last-child {
  border-bottom: none;
}
.device-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.device-name {
  font-size: 14px;
  color: #334155;
}
.device-count {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}
.device-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}
</style>
