<template>
  <div class="maintenance-page">
    <div class="title-row">
      <div>
        <div class="page-title">维保管理</div>
        <p class="subtitle">维保计划 · 维保记录 · 单位管理 · 超期预警 · 设备全生命周期管理</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Calendar /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalPlans }}</div>
            <div class="stat-label">维保计划</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.completed }}</div>
            <div class="stat-label">本月完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.overdue }}</div>
            <div class="stat-label">超期未保</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.companies }}</div>
            <div class="stat-label">维保单位</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'plans' }" @click="activeTab = 'plans'">
          <el-icon><Calendar /></el-icon>
          维保计划
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><Document /></el-icon>
          维保记录
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'companies' }" @click="activeTab = 'companies'">
          <el-icon><OfficeBuilding /></el-icon>
          维保单位
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'overdue' }" @click="activeTab = 'overdue'">
          <el-icon><Bell /></el-icon>
          超期预警
          <span v-if="stats.overdue" class="badge">{{ stats.overdue }}</span>
        </div>
      </div>

      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="openAddPlan">
              <el-icon><Plus /></el-icon>
              新建计划
            </el-button>
            <el-select v-model="planTypeFilter" placeholder="维保类型" clearable style="width: 140px" @change="loadPlans">
              <el-option label="月度维保" value="monthly" />
              <el-option label="季度维保" value="quarterly" />
              <el-option label="半年度维保" value="half_year" />
              <el-option label="年度维保" value="yearly" />
            </el-select>
            <el-select v-model="planStatusFilter" placeholder="执行状态" clearable style="width: 140px" @change="loadPlans">
              <el-option label="执行中" value="active" />
              <el-option label="已暂停" value="paused" />
              <el-option label="已结束" value="ended" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="planSearch" placeholder="搜索计划名称" style="width: 220px" clearable @keyup.enter="loadPlans">
              <template #prefix><el-icon><Search /></el-icon></template>
              <template #append>
                <el-button @click="loadPlans">搜索</el-button>
              </template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredPlans" stripe style="width: 100%">
          <el-table-column prop="plan_no" label="计划编号" width="160" />
          <el-table-column prop="plan_name" label="计划名称" min-width="180" />
          <el-table-column label="维保类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="planTypeTag(row.type)">{{ planTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="building_name" label="覆盖建筑" width="160" />
          <el-table-column prop="device_count" label="设备数量" width="100" align="center" />
          <el-table-column prop="company" label="维保单位" width="160" />
          <el-table-column prop="next_date" label="下次维保" width="140" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'active' ? 'success' : row.status === 'paused' ? 'warning' : 'info'">
                {{ row.status === 'active' ? '执行中' : row.status === 'paused' ? '已暂停' : '已结束' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="editPlan(row)">编辑</el-button>
              <el-button link type="warning" @click="togglePlanStatus(row)">
                {{ row.status === 'active' ? '暂停' : '启用' }}
              </el-button>
              <el-button link type="danger" @click="deletePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="recordTypeFilter" placeholder="维保类型" clearable style="width: 140px" @change="loadRecords">
              <el-option label="月度维保" value="monthly" />
              <el-option label="季度维保" value="quarterly" />
              <el-option label="年度维保" value="yearly" />
            </el-select>
            <el-select v-model="recordResultFilter" placeholder="维保结果" clearable style="width: 140px" @change="loadRecords">
              <el-option label="正常" value="normal" />
              <el-option label="有故障" value="fault" />
              <el-option label="待复检" value="recheck" />
            </el-select>
            <el-date-picker
              v-model="recordDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
            />
          </div>
          <div class="toolbar-right">
            <el-button @click="exportRecords">
              <el-icon><Download /></el-icon>
              导出记录
            </el-button>
          </div>
        </div>

        <el-table :data="filteredRecords" stripe style="width: 100%">
          <el-table-column prop="record_no" label="记录编号" width="170" />
          <el-table-column prop="plan_name" label="维保计划" min-width="180" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ planTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="building_name" label="建筑" width="140" />
          <el-table-column prop="device_count" label="维保设备" width="100" align="center" />
          <el-table-column prop="fault_count" label="发现故障" width="100" align="center">
            <template #default="{ row }">
              <span :class="row.fault_count > 0 ? 'danger-text' : ''">{{ row.fault_count }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="maintainer" label="维保人员" width="110" />
          <el-table-column prop="maintain_date" label="维保日期" width="130" />
          <el-table-column label="结果" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.result === 'normal' ? 'success' : row.result === 'fault' ? 'danger' : 'warning'">
                {{ row.result === 'normal' ? '正常' : row.result === 'fault' ? '有故障' : '待复检' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
              <el-button link type="success">报告</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'companies'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showCompanyForm = true">
              <el-icon><Plus /></el-icon>
              添加单位
            </el-button>
          </div>
          <div class="toolbar-right">
            <el-input v-model="companySearch" placeholder="搜索单位名称" style="width: 220px" clearable @keyup.enter="loadCompanies">
              <template #prefix><el-icon><Search /></el-icon></template>
              <template #append>
                <el-button @click="loadCompanies">搜索</el-button>
              </template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" v-for="c in filteredCompanies" :key="c.id">
            <el-card class="company-card" shadow="hover">
              <div class="company-header">
                <div class="company-logo">{{ c.name.charAt(0) }}</div>
                <div class="company-info">
                  <div class="company-name">{{ c.name }}</div>
                  <div class="company-qualification">{{ c.qualification }}</div>
                </div>
                <el-tag size="small" :type="c.status === 'active' ? 'success' : 'info'">
                  {{ c.status === 'active' ? '合作中' : '已停用' }}
                </el-tag>
              </div>
              <div class="company-detail">
                <div class="detail-row">
                  <span class="label">资质等级</span>
                  <span class="value">{{ c.level }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">联系人</span>
                  <span class="value">{{ c.contact }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">联系电话</span>
                  <span class="value">{{ c.phone }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">在保设备</span>
                  <span class="value highlight">{{ c.device_count }} 台</span>
                </div>
                <div class="detail-row">
                  <span class="label">合同到期</span>
                  <span class="value" :class="c.days_left < 30 ? 'danger-text' : ''">{{ c.contract_end }} ({{ c.days_left }}天)</span>
                </div>
              </div>
              <div class="company-actions">
                <el-button size="small">查看详情</el-button>
                <el-button size="small" type="primary">维保记录</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'overdue'" class="tab-content">
        <el-alert
          title="以下设备已超过维保周期，请及时安排维保，避免设备故障影响消防安全。"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />
        <el-table :data="overdueDevices" stripe style="width: 100%">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="device_code" label="设备编号" width="160" />
          <el-table-column prop="device_name" label="设备名称" min-width="180" />
          <el-table-column prop="device_type" label="设备类型" width="130" />
          <el-table-column prop="building_name" label="安装位置" width="180" />
          <el-table-column prop="last_maintenance" label="上次维保" width="130" />
          <el-table-column prop="next_maintenance" label="应维保日期" width="130" />
          <el-table-column label="超期天数" width="110">
            <template #default="{ row }">
              <span class="danger-text"><strong>{{ row.overdue_days }}</strong> 天</span>
            </template>
          </el-table-column>
          <el-table-column prop="maintenance_company" label="维保单位" width="160" />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default>
              <el-button link type="primary">立即派单</el-button>
              <el-button link type="warning">通知维保</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="showPlanForm" title="新建维保计划" width="600px">
      <el-form :model="planForm" label-width="100px">
        <el-form-item label="计划名称">
          <el-input v-model="planForm.plan_name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="维保类型">
          <el-select v-model="planForm.type" style="width: 100%">
            <el-option label="月度维保" value="monthly" />
            <el-option label="季度维保" value="quarterly" />
            <el-option label="半年度维保" value="half_year" />
            <el-option label="年度维保" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="覆盖建筑">
          <el-select v-model="planForm.building_id" placeholder="请选择建筑" style="width: 100%" clearable>
            <el-option
              v-for="b in buildingList"
              :key="b.id"
              :label="b.building_name || b.name"
              :value="b.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="维保单位">
          <el-select v-model="planForm.company_id" placeholder="请选择维保单位" style="width: 100%" clearable>
            <el-option
              v-for="c in companies"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="planForm.start_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="planForm.end_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="维保内容">
          <el-input v-model="planForm.content" type="textarea" :rows="3" placeholder="请输入维保内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPlanForm = false">取消</el-button>
        <el-button type="primary" @click="submitPlan">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Calendar, CircleCheck, Warning, OfficeBuilding, Bell, Plus, Search, Download, Document, Edit, Delete
} from '@element-plus/icons-vue'
import request from '../api'

const activeTab = ref('plans')
const showPlanForm = ref(false)
const showCompanyForm = ref(false)
const loading = ref(false)
const planSearch = ref('')
const planTypeFilter = ref('')
const planStatusFilter = ref('')
const recordTypeFilter = ref('')
const recordResultFilter = ref('')
const recordDateRange = ref([])
const companySearch = ref('')
const editingPlanId = ref(null)

const stats = ref({
  totalPlans: 0,
  completed: 0,
  overdue: 0,
  companies: 0,
})

const plans = ref([])
const records = ref([])
const companies = ref([])
const overdueDevices = ref([])
const buildingList = ref([])

const planForm = ref({
  plan_name: '',
  type: 'monthly',
  building_id: null,
  company_id: null,
  start_date: '',
  end_date: '',
  content: '',
  status: 'active',
})

const filteredPlans = computed(() => plans.value)
const filteredRecords = computed(() => records.value)
const filteredCompanies = computed(() => companies.value)

function planTypeText(type) {
  const map = { monthly: '月度维保', quarterly: '季度维保', half_year: '半年度维保', yearly: '年度维保' }
  return map[type] || '月度维保'
}

function planTypeTag(type) {
  const map = { monthly: '', quarterly: 'primary', half_year: 'warning', yearly: 'danger' }
  return map[type] || ''
}

async function loadStats() {
  try {
    const res = await request.get('/api/maintenance/stats')
    stats.value = res.data
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

async function loadPlans() {
  try {
    const params = {}
    if (planTypeFilter.value) params.type = planTypeFilter.value
    if (planStatusFilter.value) params.status = planStatusFilter.value
    if (planSearch.value) params.keyword = planSearch.value
    const res = await request.get('/api/maintenance/plans', { params })
    plans.value = res.data
  } catch (e) {
    ElMessage.error('加载维保计划失败')
  }
}

async function loadRecords() {
  try {
    const params = {}
    if (recordTypeFilter.value) params.type = recordTypeFilter.value
    if (recordResultFilter.value) params.result = recordResultFilter.value
    const res = await request.get('/api/maintenance/records', { params })
    records.value = res.data
  } catch (e) {
    ElMessage.error('加载维保记录失败')
  }
}

async function loadCompanies() {
  try {
    const params = {}
    if (companySearch.value) params.keyword = companySearch.value
    const res = await request.get('/api/maintenance/companies', { params })
    companies.value = res.data
  } catch (e) {
    ElMessage.error('加载维保单位失败')
  }
}

async function loadOverdue() {
  try {
    const res = await request.get('/api/maintenance/overdue')
    overdueDevices.value = res.data
  } catch (e) {
    console.error('加载超期设备失败', e)
  }
}

async function loadBuildings() {
  try {
    const res = await request.get('/api/buildings')
    buildingList.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('加载建筑列表失败', e)
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([
      loadStats(),
      loadPlans(),
      loadRecords(),
      loadCompanies(),
      loadOverdue(),
      loadBuildings(),
    ])
  } finally {
    loading.value = false
  }
}

function resetPlanForm() {
  planForm.value = {
    plan_name: '',
    type: 'monthly',
    building_id: null,
    company_id: null,
    start_date: '',
    end_date: '',
    content: '',
    status: 'active',
  }
  editingPlanId.value = null
}

function openAddPlan() {
  resetPlanForm()
  showPlanForm.value = true
}

async function submitPlan() {
  if (!planForm.value.plan_name) {
    ElMessage.warning('请输入计划名称')
    return
  }
  try {
    if (editingPlanId.value) {
      await request.put(`/api/maintenance/plans/${editingPlanId.value}`, planForm.value)
      ElMessage.success('维保计划更新成功')
    } else {
      await request.post('/api/maintenance/plans', planForm.value)
      ElMessage.success('维保计划创建成功')
    }
    showPlanForm.value = false
    resetPlanForm()
    await loadPlans()
    await loadStats()
  } catch (e) {
    ElMessage.error(editingPlanId.value ? '更新失败' : '创建失败')
  }
}

async function editPlan(row) {
  editingPlanId.value = row.id
  planForm.value = {
    plan_name: row.plan_name,
    type: row.type,
    building_id: row.building_id,
    company_id: row.company_id,
    start_date: row.start_date || '',
    end_date: row.end_date || '',
    content: row.content || '',
    status: row.status,
  }
  showPlanForm.value = true
}

async function deletePlan(row) {
  try {
    await ElMessageBox.confirm(`确定删除维保计划"${row.plan_name}"吗？`, '确认删除', { type: 'warning' })
    await request.delete(`/api/maintenance/plans/${row.id}`)
    ElMessage.success('删除成功')
    await loadPlans()
    await loadStats()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function togglePlanStatus(row) {
  try {
    await request.post(`/api/maintenance/plans/${row.id}/status`, { status: row.status === 'active' ? 'paused' : 'active' })
    ElMessage.success('状态已更新')
    await loadPlans()
    await loadStats()
  } catch (e) {
    ElMessage.error('操作失败')
    await loadPlans()
  }
}

function exportRecords() {
  ElMessage.success('正在导出维保记录...')
}

watch(activeTab, (tab) => {
  if (tab === 'plans') loadPlans()
  else if (tab === 'records') loadRecords()
  else if (tab === 'companies') loadCompanies()
  else if (tab === 'overdue') loadOverdue()
})

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.maintenance-page {
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
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

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

.tab-item .badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  line-height: 18px;
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

.danger-text {
  color: #dc2626;
  font-weight: 600;
}

.company-card {
  margin-bottom: 16px;
}

.company-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.company-logo {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.company-info {
  flex: 1;
  min-width: 0;
}

.company-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 2px;
}

.company-qualification {
  font-size: 12px;
  color: #64748b;
}

.company-detail {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 14px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.detail-row .label {
  color: #64748b;
}

.detail-row .value {
  color: #0f172a;
  font-weight: 500;
}

.detail-row .value.highlight {
  color: #2563eb;
}

.company-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
