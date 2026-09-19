<template>
  <div class="key-unit-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防重点单位管理</div>
        <p class="subtitle">消防安全重点单位档案 · 风险分级 · 监督检查</p>
      </div>
      <div class="actions">
        <el-button type="primary" @click="showForm = true; formData = {}">
          <el-icon><Plus /></el-icon>新增单位
        </el-button>
        <el-button @click="exportData">
          <el-icon><Download /></el-icon>导出
        </el-button>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.total }}</div>
            <div class="stat-label">重点单位总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.highRisk }}</div>
            <div class="stat-label">高风险单位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Check /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.checkedThisMonth }}</div>
            <div class="stat-label">本月已检查</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.qualifiedRate }}%</div>
            <div class="stat-label">合格率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div class="tab-bar">
      <div class="tab-item" :class="{ active: activeTab === 'list' }" @click="activeTab = 'list'">
        <el-icon><List /></el-icon>单位台账
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'level' }" @click="activeTab = 'level'">
        <el-icon><TrendCharts /></el-icon>风险分级
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'inspection' }" @click="activeTab = 'inspection'">
        <el-icon><Document /></el-icon>监督检查
      </div>
      <div class="tab-item" :class="{ active: activeTab === 'statistics' }" @click="activeTab = 'statistics'">
        <el-icon><DataAnalysis /></el-icon>统计分析
      </div>
    </div>

    <el-card v-if="activeTab === 'list'" class="content-card" shadow="never">
      <div class="filter-bar">
        <el-input v-model="searchKeyword" placeholder="搜索单位名称" style="width: 220px" clearable>
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filterLevel" placeholder="风险等级" clearable style="width: 140px">
          <el-option label="一级单位" value="level1" />
          <el-option label="二级单位" value="level2" />
          <el-option label="三级单位" value="level3" />
        </el-select>
        <el-select v-model="filterIndustry" placeholder="行业类型" clearable style="width: 160px">
          <el-option label="商场市场" value="mall" />
          <el-option label="宾馆饭店" value="hotel" />
          <el-option label="娱乐场所" value="entertainment" />
          <el-option label="学校医院" value="school" />
          <el-option label="工厂企业" value="factory" />
          <el-option label="仓库物流" value="warehouse" />
        </el-select>
        <el-button type="primary" @click="loadData">查询</el-button>
      </div>
      <el-table :data="unitList" style="width: 100%" stripe>
        <el-table-column prop="unitName" label="单位名称" min-width="200">
          <template #default="{ row }">
            <span class="link-text" @click="viewDetail(row)">{{ row.unitName }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业类型" width="120" />
        <el-table-column prop="level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)" effect="dark">{{ row.levelText }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
        <el-table-column prop="legalPerson" label="法人" width="100" />
        <el-table-column prop="contactPhone" label="联系电话" width="130" />
        <el-table-column prop="lastCheckDate" label="最近检查" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'normal' ? 'success' : 'danger'">
              {{ row.status === 'normal' ? '正常' : '停业' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">查看</el-button>
            <el-button link type="primary" size="small" @click="editUnit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteUnit(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-card v-if="activeTab === 'level'" class="content-card" shadow="never">
      <el-row :gutter="20">
        <el-col :xs="24" :md="12">
          <div class="chart-title">风险等级分布</div>
          <div ref="levelChartRef" class="chart-container"></div>
        </el-col>
        <el-col :xs="24" :md="12">
          <div class="chart-title">行业风险分布</div>
          <div ref="industryChartRef" class="chart-container"></div>
        </el-col>
      </el-row>
      <el-divider />
      <div class="level-list">
        <div class="level-section">
          <div class="level-header level-1">
            <el-icon><WarningFilled /></el-icon>
            <span>一级消防安全重点单位</span>
            <el-tag type="danger" effect="dark">{{ level1List.length }} 家</el-tag>
          </div>
          <el-table :data="level1List" size="small" stripe>
            <el-table-column prop="unitName" label="单位名称" />
            <el-table-column prop="industry" label="行业" width="120" />
            <el-table-column prop="address" label="地址" show-overflow-tooltip />
            <el-table-column prop="contactPhone" label="联系电话" width="130" />
          </el-table>
        </div>
        <div class="level-section">
          <div class="level-header level-2">
            <el-icon><Warning /></el-icon>
            <span>二级消防安全重点单位</span>
            <el-tag type="warning" effect="dark">{{ level2List.length }} 家</el-tag>
          </div>
          <el-table :data="level2List" size="small" stripe>
            <el-table-column prop="unitName" label="单位名称" />
            <el-table-column prop="industry" label="行业" width="120" />
            <el-table-column prop="address" label="地址" show-overflow-tooltip />
            <el-table-column prop="contactPhone" label="联系电话" width="130" />
          </el-table>
        </div>
      </div>
    </el-card>

    <el-card v-if="activeTab === 'inspection'" class="content-card" shadow="never">
      <div class="filter-bar">
        <el-input v-model="inspectionSearch" placeholder="搜索检查记录" style="width: 220px" clearable>
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="inspectionResult" placeholder="检查结果" clearable style="width: 140px">
          <el-option label="合格" value="pass" />
          <el-option label="限期整改" value="rectify" />
          <el-option label="不合格" value="fail" />
        </el-select>
        <el-button type="primary" @click="loadInspections">查询</el-button>
        <el-button type="success" @click="showInspectionForm = true; inspectionForm = {}">新增检查</el-button>
      </div>
      <el-table :data="inspectionList" style="width: 100%" stripe>
        <el-table-column prop="inspectionNo" label="检查编号" width="160" />
        <el-table-column prop="unitName" label="被检单位" min-width="200" />
        <el-table-column prop="inspectionType" label="检查类型" width="120" />
        <el-table-column prop="inspector" label="检查人员" width="100" />
        <el-table-column prop="inspectionDate" label="检查日期" width="120" />
        <el-table-column prop="result" label="检查结果" width="120">
          <template #default="{ row }">
            <el-tag :type="row.result === 'pass' ? 'success' : row.result === 'rectify' ? 'warning' : 'danger'">
              {{ row.resultText }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="problems" label="发现问题" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewInspection(row)">详情</el-button>
            <el-button link type="primary" size="small" @click="downloadReport(row)">报告</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="activeTab === 'statistics'" class="content-card" shadow="never">
      <el-row :gutter="20">
        <el-col :xs="24" :md="16">
          <div class="chart-title">单位检查趋势（近12个月）</div>
          <div ref="trendChartRef" class="chart-container trend-chart"></div>
        </el-col>
        <el-col :xs="24" :md="8">
          <div class="chart-title">问题类型统计</div>
          <div ref="problemChartRef" class="chart-container"></div>
        </el-col>
      </el-row>
    </el-card>

    <el-dialog v-model="showForm" title="重点单位信息" width="720px" destroy-on-close>
      <el-form :model="formData" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="单位名称" required>
              <el-input v-model="formData.unitName" placeholder="请输入单位名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="行业类型" required>
              <el-select v-model="formData.industry" placeholder="请选择" style="width: 100%">
                <el-option label="商场市场" value="mall" />
                <el-option label="宾馆饭店" value="hotel" />
                <el-option label="娱乐场所" value="entertainment" />
                <el-option label="学校医院" value="school" />
                <el-option label="工厂企业" value="factory" />
                <el-option label="仓库物流" value="warehouse" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="风险等级" required>
              <el-select v-model="formData.level" placeholder="请选择" style="width: 100%">
                <el-option label="一级单位" value="level1" />
                <el-option label="二级单位" value="level2" />
                <el-option label="三级单位" value="level3" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位状态">
              <el-select v-model="formData.status" placeholder="请选择" style="width: 100%">
                <el-option label="正常营业" value="normal" />
                <el-option label="停业" value="closed" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="单位地址" required>
          <el-input v-model="formData.address" placeholder="请输入详细地址" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="法人代表">
              <el-input v-model="formData.legalPerson" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="formData.contactPhone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="消防安全责任人">
              <el-input v-model="formData.fireManager" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任人电话">
              <el-input v-model="formData.fireManagerPhone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="建筑面积">
          <el-input v-model="formData.area" placeholder="平方米">
            <template #append>㎡</template>
          </el-input>
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="formData.remark" type="textarea" :rows="3" placeholder="请输入备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" @click="saveUnit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../api'

const activeTab = ref('list')
const searchKeyword = ref('')
const filterLevel = ref('')
const filterIndustry = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const showForm = ref(false)
const formData = ref({})
const loading = ref(false)

const stats = ref({})

const unitList = ref([])

const level1List = computed(() => unitList.value.filter(u => u.level === 'level1'))
const level2List = computed(() => unitList.value.filter(u => u.level === 'level2'))

const levelChartRef = ref(null)
const industryChartRef = ref(null)
const trendChartRef = ref(null)
const problemChartRef = ref(null)

const inspectionSearch = ref('')
const inspectionResult = ref('')
const showInspectionForm = ref(false)
const inspectionForm = ref({})
const inspectionList = ref([])
const inspectionTotal = ref(0)
const inspectionPage = ref(1)
const inspectionPageSize = ref(20)

const industryMap = {
  mall: '商场市场',
  hotel: '宾馆饭店',
  entertainment: '娱乐场所',
  school: '学校医院',
  factory: '工厂企业',
  warehouse: '仓库物流',
  other: '其他'
}

const levelTextMap = {
  level1: '一级单位',
  level2: '二级单位',
  level3: '三级单位'
}

const resultTextMap = {
  pass: '合格',
  rectify: '限期整改',
  fail: '不合格'
}

function mapUnitData(item) {
  return {
    ...item,
    levelText: levelTextMap[item.level] || item.level,
    industry: industryMap[item.industry] || item.industry,
    contactPhone: item.phone || item.contactPhone,
    area: item.buildingArea || item.area,
    fireManagerPhone: item.firePhone || item.fireManagerPhone
  }
}

function mapInspectionData(item) {
  return {
    ...item,
    resultText: resultTextMap[item.result] || item.result,
    inspectionNo: item.id ? `JC${item.id}` : item.inspectionNo,
    problems: item.problemsFound || item.problems
  }
}

function levelTagType(level) {
  if (level === 'level1') return 'danger'
  if (level === 'level2') return 'warning'
  return 'info'
}

async function loadStats() {
  try {
    const res = await request.get('/api/key-units/stats')
    stats.value = res.data || {}
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      pageSize: pageSize.value
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterLevel.value) params.level = filterLevel.value
    if (filterIndustry.value) params.industry = filterIndustry.value
    const res = await request.get('/api/key-units', { params })
    const data = res.data || {}
    unitList.value = (data.list || []).map(mapUnitData)
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error('加载单位列表失败')
  } finally {
    loading.value = false
  }
}

function handleSizeChange(val) {
  pageSize.value = val
  currentPage.value = 1
  loadData()
}
function handlePageChange(val) {
  currentPage.value = val
  loadData()
}

function viewDetail(row) {
  formData.value = { ...row }
  showForm.value = true
}

function editUnit(row) {
  formData.value = { ...row }
  showForm.value = true
}

async function deleteUnit(row) {
  try {
    await ElMessageBox.confirm(`确定删除单位"${row.unitName}"吗？`, '提示', { type: 'warning' })
    await request.delete(`/api/key-units/${row.id}`)
    ElMessage.success('删除成功')
    await loadData()
    await loadStats()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function saveUnit() {
  if (!formData.value.unitName) {
    ElMessage.warning('请输入单位名称')
    return
  }
  try {
    const payload = {
      unitName: formData.value.unitName,
      industry: formData.value.industry,
      level: formData.value.level,
      status: formData.value.status || 'normal',
      address: formData.value.address,
      legalPerson: formData.value.legalPerson,
      phone: formData.value.contactPhone || formData.value.phone,
      fireManager: formData.value.fireManager,
      firePhone: formData.value.fireManagerPhone || formData.value.firePhone,
      buildingArea: formData.value.area || formData.value.buildingArea,
      staffCount: formData.value.staffCount,
      unitCode: formData.value.unitCode,
      contact: formData.value.contact
    }
    if (formData.value.id) {
      await request.put(`/api/key-units/${formData.value.id}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/api/key-units', payload)
      ElMessage.success('新增成功')
    }
    showForm.value = false
    await loadData()
    await loadStats()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

function exportData() {
  ElMessage.success('导出成功')
}

async function loadInspections() {
  try {
    const params = {
      page: inspectionPage.value,
      pageSize: inspectionPageSize.value
    }
    const res = await request.get('/api/key-units/inspections', { params })
    const data = res.data || {}
    inspectionList.value = (data.list || []).map(mapInspectionData)
    inspectionTotal.value = data.total || 0
  } catch (e) {
    ElMessage.error('加载检查记录失败')
  }
}

function viewInspection(row) {
  ElMessage.info('查看检查详情：' + row.inspectionNo)
}

function downloadReport(row) {
  ElMessage.success('正在下载报告：' + row.inspectionNo)
}

function initLevelChart() {
  if (!levelChartRef.value || !levelChartRef.value.offsetWidth) return
  try {
    const chart = echarts.getInstanceByDom(levelChartRef.value)
    if (chart) {
      chart.dispose()
    }
    const newChart = echarts.init(levelChartRef.value)
    newChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: '5%', left: 'center' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
        data: [
          { value: 12, name: '一级单位', itemStyle: { color: '#ef4444' } },
          { value: 35, name: '二级单位', itemStyle: { color: '#f59e0b' } },
          { value: 39, name: '三级单位', itemStyle: { color: '#22c55e' } },
        ]
      }]
    })
  } catch (e) {
    console.error('初始化等级图表失败:', e)
  }
}

function initIndustryChart() {
  if (!industryChartRef.value || !industryChartRef.value.offsetWidth) return
  try {
    const chart = echarts.getInstanceByDom(industryChartRef.value)
    if (chart) {
      chart.dispose()
    }
    const newChart = echarts.init(industryChartRef.value)
    newChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: '5%', left: 'center' },
      series: [{
        type: 'pie',
        radius: '65%',
        data: [
          { value: 18, name: '商场市场', itemStyle: { color: '#2563eb' } },
          { value: 15, name: '宾馆饭店', itemStyle: { color: '#8b5cf6' } },
          { value: 12, name: '娱乐场所', itemStyle: { color: '#ec4899' } },
          { value: 14, name: '学校医院', itemStyle: { color: '#10b981' } },
          { value: 16, name: '工厂企业', itemStyle: { color: '#f59e0b' } },
          { value: 11, name: '仓库物流', itemStyle: { color: '#06b6d4' } },
        ],
        label: { formatter: '{b}: {c}家' }
      }]
    })
  } catch (e) {
    console.error('初始化行业图表失败:', e)
  }
}

function initTrendChart() {
  if (!trendChartRef.value || !trendChartRef.value.offsetWidth) return
  try {
    const chart = echarts.getInstanceByDom(trendChartRef.value)
    if (chart) {
      chart.dispose()
    }
    const newChart = echarts.init(trendChartRef.value)
  const months = ['2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月', '1月']
    newChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['检查次数', '合格数', '整改数'] },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: months, boundaryGap: false },
      yAxis: { type: 'value' },
      series: [
        { name: '检查次数', type: 'line', smooth: true, data: [28, 32, 30, 35, 38, 40, 42, 38, 36, 34, 32, 34], itemStyle: { color: '#2563eb' }, areaStyle: { opacity: 0.1 } },
        { name: '合格数', type: 'line', smooth: true, data: [25, 29, 28, 32, 35, 37, 39, 35, 33, 31, 30, 31], itemStyle: { color: '#22c55e' } },
        { name: '整改数', type: 'line', smooth: true, data: [3, 3, 2, 3, 3, 3, 3, 3, 3, 3, 2, 3], itemStyle: { color: '#f59e0b' } },
      ]
    })
  } catch (e) {
    console.error('初始化趋势图表失败:', e)
  }
}

function initProblemChart() {
  if (!problemChartRef.value || !problemChartRef.value.offsetWidth) return
  try {
    const chart = echarts.getInstanceByDom(problemChartRef.value)
    if (chart) {
      chart.dispose()
    }
    const newChart = echarts.init(problemChartRef.value)
  newChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: ['消防设施故障', '疏散通道堵塞', '电气隐患', '安全出口问题', '消防管理问题', '其他'] },
      series: [{
        type: 'bar',
        data: [
          { value: 28, itemStyle: { color: '#ef4444' } },
          { value: 22, itemStyle: { color: '#f59e0b' } },
          { value: 18, itemStyle: { color: '#2563eb' } },
          { value: 15, itemStyle: { color: '#8b5cf6' } },
          { value: 12, itemStyle: { color: '#10b981' } },
          { value: 8, itemStyle: { color: '#64748b' } },
        ],
        label: { show: true, position: 'right' }
      }]
    })
  } catch (e) {
    console.error('初始化问题图表失败:', e)
  }
}

watch(activeTab, (val) => {
  nextTick(() => {
    if (val === 'level') {
      initLevelChart()
      initIndustryChart()
    }
    if (val === 'statistics') {
      initTrendChart()
      initProblemChart()
    }
    if (val === 'inspection') {
      loadInspections()
    }
  })
})

onMounted(async () => {
  await loadStats()
  await loadData()
  window.addEventListener('resize', () => {
    echarts.getInstanceByDom(levelChartRef.value)?.resize()
    echarts.getInstanceByDom(industryChartRef.value)?.resize()
    echarts.getInstanceByDom(trendChartRef.value)?.resize()
    echarts.getInstanceByDom(problemChartRef.value)?.resize()
  })
})
</script>

<style scoped>
.key-unit-page { padding-bottom: 20px; }
.title-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-title { font-size: 22px; font-weight: 800; color: #0f172a; }
.subtitle { color: #64748b; margin: 6px 0 0; font-size: 13px; }
.actions { display: flex; gap: 10px; }
.stats-row { margin-bottom: 16px; }
.stat-card { display: flex; align-items: center; gap: 14px; padding: 8px 12px; }
.stat-icon {
  width: 48px; height: 48px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #2563eb, #60a5fa); color: white; font-size: 22px;
}
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #f87171); }
.stat-icon.orange { background: linear-gradient(135deg, #f59e0b, #fbbf24); }
.stat-icon.blue { background: linear-gradient(135deg, #2563eb, #60a5fa); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #4ade80); }
.stat-info { flex: 1; }
.stat-num { font-size: 24px; font-weight: 800; color: #0f172a; }
.stat-label { color: #64748b; font-size: 13px; margin-top: 2px; }
.tab-bar {
  display: flex; gap: 4px; margin-bottom: 16px;
  background: #f1f5f9; padding: 6px; border-radius: 14px; width: fit-content;
}
.tab-item {
  padding: 10px 22px; border-radius: 10px; cursor: pointer;
  display: flex; align-items: center; gap: 8px; font-weight: 600;
  color: #64748b; transition: all 0.2s;
}
.tab-item:hover { color: #0f172a; }
.tab-item.active { background: white; color: #2563eb; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.link-text { color: #2563eb; cursor: pointer; text-decoration: none; }
.link-text:hover { text-decoration: underline; }
.chart-container { height: 320px; }
.chart-title { font-weight: 700; margin-bottom: 10px; color: #0f172a; }
.trend-chart { height: 380px; }
.level-list { display: flex; flex-direction: column; gap: 20px; }
.level-section { }
.level-header {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-radius: 12px; margin-bottom: 12px;
  font-weight: 700; font-size: 15px;
}
.level-header.level-1 { background: #fef2f2; color: #dc2626; }
.level-header.level-2 { background: #fffbeb; color: #d97706; }
.level-header span { flex: 1; }
</style>
