<template>
  <div class="batch-inspection-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">批量巡检任务</h2>
        <p class="page-desc">创建和管理批量巡检任务，跟踪任务进度和结果</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshTasks" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button v-if="canCreate" type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建任务
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon total">📋</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total || 0 }}</div>
            <div class="stat-label">任务总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon running"></div>
          <div class="stat-content">
            <div class="stat-value warning">{{ stats.running || 0 }}</div>
            <div class="stat-label">执行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon completed"></div>
          <div class="stat-content">
            <div class="stat-value success">{{ stats.completed || 0 }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon risk">⚠️</div>
          <div class="stat-content">
            <div class="stat-value danger">{{ stats.high_risk || 0 }}</div>
            <div class="stat-label">高风险发现</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="任务状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 140px">
            <el-option label="待执行" value="pending" />
            <el-option label="执行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="建筑/区域">
          <el-input v-model="filters.building_id" placeholder="建筑ID" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTasks">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="tasks" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="task_name" label="任务名称" min-width="200" />
        <el-table-column prop="building_name" label="建筑/区域" width="160" />
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.completed_count / row.total_count * 100)"
              :status="row.status === 'completed' ? 'success' : row.status === 'running' ? '' : 'exception'"
            />
          </template>
        </el-table-column>
        <el-table-column label="巡检项" width="120">
          <template #default="{ row }">
            {{ row.completed_count }} / {{ row.total_count }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="priorityType(row.priority)" size="small">{{ row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inspector" label="负责人" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="row.status === 'running'" link type="warning" @click="viewProgress(row)">进度</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailDialog" title="任务详情" width="800px">
      <div v-if="currentTask" class="task-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务名称">{{ currentTask.task_name }}</el-descriptions-item>
          <el-descriptions-item label="任务状态">
            <el-tag :type="statusType(currentTask.status)">{{ statusText(currentTask.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="建筑/区域">{{ currentTask.building_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="priorityType(currentTask.priority)">{{ currentTask.priority }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="负责人">{{ currentTask.inspector }}</el-descriptions-item>
          <el-descriptions-item label="计划时间">{{ currentTask.scheduled_time }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ currentTask.created_at }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ currentTask.completed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">巡检结果汇总</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-statistic title="巡检项总数" :value="currentTask.total_count || 0" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="已完成" :value="currentTask.completed_count || 0" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="完成率" :value="Math.round((currentTask.completed_count || 0) / (currentTask.total_count || 1) * 100)" suffix="%" />
          </el-col>
        </el-row>

        <el-divider content-position="left">巡检结果列表</el-divider>
        <el-table :data="currentTask.results || []" max-height="300" size="small">
          <el-table-column prop="location" label="位置" width="140" />
          <el-table-column prop="risk_level" label="风险等级" width="100">
            <template #default="{ row }">
              <el-tag :type="riskType(row.risk_level)" size="small">{{ row.risk_level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="risk_score" label="风险分" width="80" />
          <el-table-column prop="hazard_count" label="隐患数" width="80" />
          <el-table-column prop="hazards" label="隐患类型" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="h in (row.hazards || []).slice(0, 2)" :key="h" size="small" style="margin-right: 4px">{{ h }}</el-tag>
              <span v-if="(row.hazards || []).length > 2">等{{ row.hazards.length }}项</span>
            </template>
          </el-table-column>
          <el-table-column prop="inspected_at" label="巡检时间" width="160" />
        </el-table>
      </div>
    </el-dialog>

    <el-dialog v-model="progressDialog" title="任务执行进度" width="500px">
      <div v-if="currentProgress" class="progress-detail">
        <el-progress
          :percentage="currentProgress.progress || 0"
          :status="currentProgress.status === 'completed' ? 'success' : currentProgress.status === 'running' ? '' : 'exception'"
          :stroke-width="20"
        />
        <div class="progress-info">
          <p>当前进度：{{ currentProgress.completed_count }} / {{ currentProgress.total_count }}</p>
          <p v-if="currentProgress.current_item">正在巡检：{{ currentProgress.current_item }}</p>
        </div>
        <el-row :gutter="16" class="risk-summary">
          <el-col :span="8">
            <el-statistic title="高风险" :value="currentProgress.high_risk_count || 0" value-style="color: #ef4444" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="中风险" :value="currentProgress.medium_risk_count || 0" value-style="color: #f59e0b" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="低风险" :value="currentProgress.low_risk_count || 0" value-style="color: #22c55e" />
          </el-col>
        </el-row>
      </div>
    </el-dialog>

    <el-dialog v-model="showCreateDialog" title="新建批量巡检任务" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="createForm.task_name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="建筑/区域">
          <el-select v-model="createForm.building_id" style="width: 100%">
            <el-option label="综合办公楼A座" value="building_001" />
            <el-option label="实验楼B座" value="building_002" />
            <el-option label="学生宿舍C区" value="building_003" />
          </el-select>
        </el-form-item>
        <el-form-item label="巡检项数量">
          <el-input-number v-model="createForm.item_count" :min="1" :max="50" style="width: 100%" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="createForm.priority">
            <el-radio value="高">高</el-radio>
            <el-radio value="中">中</el-radio>
            <el-radio value="低">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="createForm.inspector" placeholder="请输入负责人" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { batchInspectionList, batchInspectionCreate, batchInspectionDetail, batchInspectionProgress } from '../api'
import { getCurrentUser, hasPermission } from '../auth'

// 与后端 require_permission("batch:create") 对齐：无权限时不展示入口
const canCreate = computed(() => hasPermission(getCurrentUser(), 'batch:create'))

const loading = ref(false)
const creating = ref(false)
const tasks = ref([])
const stats = ref({ total: 0, running: 0, completed: 0, high_risk: 0 })
const filters = ref({ status: '', building_id: '' })

const detailDialog = ref(false)
const progressDialog = ref(false)
const currentTask = ref(null)
const currentProgress = ref(null)

const showCreateDialog = ref(false)
const createForm = ref({
  task_name: '',
  building_id: 'building_001',
  item_count: 10,
  priority: '中',
  inspector: '系统'
})

// 定时器引用
const progressTimers = ref(new Set())

function statusType(status) {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'pending') return 'info'
  return 'danger'
}

function statusText(status) {
  if (status === 'completed') return '已完成'
  if (status === 'running') return '执行中'
  if (status === 'pending') return '待执行'
  if (status === 'failed') return '执行失败'
  return '已取消'
}

function priorityType(priority) {
  if (priority === '高') return 'danger'
  if (priority === '中') return 'warning'
  return 'info'
}

function riskType(level) {
  if (level === '严重风险') return 'danger'
  if (level === '高风险') return 'warning'
  if (level === '中风险') return 'info'
  return 'success'
}

async function loadTasks() {
  loading.value = true
  try {
    const params = {}
    if (filters.value.status) params.status = filters.value.status
    if (filters.value.building_id) params.building_id = filters.value.building_id
    
    const res = await batchInspectionList(params)
    tasks.value = res.data.items || []
    
    stats.value = {
      total: res.data.total || 0,
      running: tasks.value.filter(t => t.status === 'running').length,
      completed: tasks.value.filter(t => t.status === 'completed').length,
      high_risk: 0
    }
  } catch (e) {
    console.error('加载任务列表失败', e)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = { status: '', building_id: '' }
  loadTasks()
}

function refreshTasks() {
  loadTasks()
}

async function viewDetail(row) {
  try {
    const res = await batchInspectionDetail(row.id)
    currentTask.value = res.data
    detailDialog.value = true
  } catch (e) {
    console.error('获取任务详情失败', e)
  }
}

async function viewProgress(row) {
  try {
    const res = await batchInspectionProgress(row.id)
    currentProgress.value = res.data
    progressDialog.value = true
    
    const timer = setInterval(async () => {
      const r = await batchInspectionProgress(row.id)
      currentProgress.value = r.data
      if (r.data.status === 'completed') {
        clearInterval(timer)
        progressTimers.value.delete(timer)
        loadTasks()
      }
    }, 2000)
    
    // 将定时器添加到集合中管理
    progressTimers.value.add(timer)
  } catch (e) {
    console.error('获取进度失败', e)
  }
}

async function createTask() {
  creating.value = true
  try {
    const items = []
    for (let i = 0; i < createForm.value.item_count; i++) {
      items.push({
        id: `ITEM-${i + 1}`,
        location: `巡检点${i + 1}`,
        description: `第${i + 1}个巡检点`,
      })
    }
    
    const buildingNames = {
      'building_001': '综合办公楼A座',
      'building_002': '实验楼B座',
      'building_003': '学生宿舍C区',
    }
    
    await batchInspectionCreate({
      task_name: createForm.value.task_name || `批量巡检-${new Date().toLocaleDateString()}`,
      building_id: createForm.value.building_id,
      building_name: buildingNames[createForm.value.building_id] || '未指定',
      inspection_items: items,
      inspector: createForm.value.inspector,
      priority: createForm.value.priority,
    })
    
    ElMessage.success('任务创建成功')
    showCreateDialog.value = false
    loadTasks()
  } catch (e) {
    console.error('创建任务失败', e)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  loadTasks()
})

// 组件卸载时清理所有定时器
onUnmounted(() => {
  progressTimers.value.forEach(timer => {
    clearInterval(timer)
  })
  progressTimers.value.clear()
})
</script>

<style scoped>
.batch-inspection-page {
  padding: 0;
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
.stats-row {
  margin-bottom: 16px;
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
  font-size: 26px;
  background: #eff6ff;
}
.stat-icon.total { background: #eff6ff; }
.stat-icon.running { background: #fef3c7; }
.stat-icon.completed { background: #dcfce7; }
.stat-icon.risk { background: #fee2e2; }
.stat-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}
.stat-value.danger { color: var(--fire-red); }
.stat-value.warning { color: var(--fire-orange); }
.stat-value.success { color: var(--fire-green); }
.stat-label {
  color: var(--fire-muted);
  font-size: 13px;
  margin-top: 4px;
}
.filter-card {
  margin-bottom: 16px;
}
.table-card {
  margin-top: 16px;
}
.progress-info {
  margin: 20px 0;
  color: #64748b;
  line-height: 2;
}
.risk-summary {
  margin-top: 16px;
}
</style>
