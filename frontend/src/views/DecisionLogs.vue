<template>
  <div class="decision-logs-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">分析日志</h2>
        <p class="page-desc">记录所有系统的分析决策过程，支持溯源与人工复核</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshLogs" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="exportLogs">
          <el-icon><Download /></el-icon>
          导出日志
        </el-button>
      </div>
    </div>

    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="分析类型">
          <el-select v-model="filters.analysisType" placeholder="全部类型" clearable style="width: 160px">
            <el-option label="智能巡检" value="inspection" />
            <el-option label="多模态分析" value="multimodal" />
            <el-option label="设备告警分析" value="alert_analysis" />
            <el-option label="风险评估" value="risk_assessment" />
            <el-option label="工单处置建议" value="workorder" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="filters.riskLevel" placeholder="全部等级" clearable style="width: 140px">
            <el-option label="严重风险" value="critical" />
            <el-option label="高风险" value="high" />
            <el-option label="中风险" value="medium" />
            <el-option label="低风险" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 140px">
            <el-option label="待复核" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已调整" value="adjusted" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchLogs">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon total"></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">总决策数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon pending">⏳</div>
          <div class="stat-content">
            <div class="stat-value warning">{{ stats.pending }}</div>
            <div class="stat-label">待复核</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon approved"></div>
          <div class="stat-content">
            <div class="stat-value success">{{ stats.approved }}</div>
            <div class="stat-label">已通过</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon adjusted"></div>
          <div class="stat-content">
            <div class="stat-value info">{{ stats.adjusted }}</div>
            <div class="stat-label">人工调整</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="logs-card">
      <el-table :data="logs" stripe @row-click="viewLogDetail">
        <el-table-column label="时间" width="180" prop="created_at" />
        <el-table-column label="分析类型" width="140">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.analysis_type)" size="small">
              {{ getTypeLabel(row.analysis_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="240">
          <template #default="{ row }">
            <div class="log-title">{{ row.title }}</div>
            <div class="log-subtitle">{{ row.location || row.building_name || '' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="风险评分" width="120">
          <template #default="{ row }">
            <div class="risk-score-inline">
              <span class="score-num" :class="getScoreClass(row.risk_score)">{{ row.risk_score }}</span>
              <span class="score-label">分</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="隐患数" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="warning" size="small">{{ row.hazard_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click.stop="viewLogDetail(row)">查看</el-button>
            <el-button size="small" link @click.stop="approveLog(row)" v-if="row.status === 'pending'">通过</el-button>
            <el-button size="small" link type="warning" @click.stop="adjustLog(row)" v-if="row.status === 'pending'">调整</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          layout="total, prev, pager, next, jumper"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <el-drawer v-model="detailDrawer" title="决策详情" size="600px">
      <div v-if="selectedLog" class="log-detail">
        <div class="detail-header">
          <el-tag :type="getTypeColor(selectedLog.analysis_type)" size="large">
            {{ getTypeLabel(selectedLog.analysis_type) }}
          </el-tag>
          <el-tag :type="getStatusType(selectedLog.status)" size="large">
            {{ getStatusLabel(selectedLog.status) }}
          </el-tag>
        </div>

        <h3 class="detail-title">{{ selectedLog.title }}</h3>
        <div class="detail-meta">
          <span>📍 {{ selectedLog.location || selectedLog.building_name || '未指定' }}</span>
          <span>🕐 {{ selectedLog.created_at }}</span>
          <span>{{ selectedLog.agent_version || 'Agent v1.0' }}</span>
        </div>

        <div class="detail-section">
          <h4>风险评估结果</h4>
          <div class="risk-summary-box" :class="getRiskClass(selectedLog.risk_score)">
            <div class="risk-score-big">
              <span class="big-score">{{ selectedLog.risk_score }}</span>
              <span class="big-label">风险分</span>
            </div>
            <div class="risk-info">
              <div class="risk-level">{{ getRiskLevel(selectedLog.risk_score) }}</div>
              <p class="risk-explanation">{{ selectedLog.risk_explanation }}</p>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h4>识别的隐患 ({{ selectedLog.hazard_count || 0 }})</h4>
          <div v-if="selectedLog.hazards?.length" class="hazard-list">
            <div v-for="(hazard, idx) in selectedLog.hazards" :key="idx" class="hazard-item">
              <span class="hazard-index">{{ idx + 1 }}</span>
              <div class="hazard-info">
                <div class="hazard-name">{{ hazard.name || hazard.type }}</div>
                <div class="hazard-desc">{{ hazard.evidence || hazard.reason || '' }}</div>
              </div>
              <el-tag :type="getSeverityType(hazard.severity)" size="small">
                {{ hazard.severity || 'C级' }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else description="未识别到隐患" :image-size="80" />
        </div>

        <div class="detail-section">
          <h4>📋 处置建议</h4>
          <div v-if="selectedLog.recommendations?.length" class="recommendation-list">
            <div v-for="(rec, idx) in selectedLog.recommendations" :key="idx" class="rec-item">
              <el-tag :type="getPriorityType(rec.priority)" size="small" class="rec-tag">
                {{ rec.priority }}
              </el-tag>
              <div class="rec-content">
                <div class="rec-action">{{ rec.action }}</div>
                <div class="rec-meta">
                  <span>责任人：{{ rec.responsible || '待分配' }}</span>
                  <span>时限：{{ rec.timeframe || '待确定' }}</span>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无处置建议" :image-size="80" />
        </div>

        <div class="detail-section">
          <h4>Agent 思考过程</h4>
          <el-steps direction="vertical" :active="selectedLog.analysis_steps?.length || 0" finish-status="success">
            <el-step
              v-for="(step, idx) in selectedLog.analysis_steps || []"
              :key="idx"
              :title="step.name || `步骤 ${idx + 1}`"
              :description="step.description || step.note || ''"
            />
          </el-steps>
        </div>

        <div class="detail-section">
          <h4>知识依据 ({{ selectedLog.knowledge_refs?.length || 0 }})</h4>
          <div v-if="selectedLog.knowledge_refs?.length" class="knowledge-list">
            <div v-for="(ref, idx) in selectedLog.knowledge_refs" :key="idx" class="knowledge-item">
              <div class="knowledge-title">
                <el-icon><Document /></el-icon>
                <span>{{ ref.title || ref.source }}</span>
              </div>
              <p class="knowledge-snippet">{{ ref.snippet || ref.content_preview?.slice(0, 100) }}...</p>
            </div>
          </div>
          <el-empty v-else description="无知识引用" :image-size="80" />
        </div>

        <div class="detail-actions" v-if="selectedLog.status === 'pending'">
          <el-button type="success" @click="approveLog(selectedLog)" style="flex: 1">
            <el-icon><Check /></el-icon>
            复核通过
          </el-button>
          <el-button type="warning" @click="adjustLog(selectedLog)" style="flex: 1">
            <el-icon><Edit /></el-icon>
            人工调整
          </el-button>
          <el-button type="danger" @click="rejectLog(selectedLog)" style="flex: 1">
            <el-icon><Close /></el-icon>
            驳回
          </el-button>
        </div>

        <div class="detail-feedback" v-if="selectedLog.review_note">
          <el-alert :title="'复核说明：' + selectedLog.review_note" type="info" :closable="false" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Download, Document, Check, Edit, Close } from '@element-plus/icons-vue'
import request from '../api'

const loading = ref(false)
const detailDrawer = ref(false)
const selectedLog = ref(null)

const filters = ref({
  analysisType: '',
  riskLevel: '',
  status: '',
  dateRange: []
})

const pagination = ref({
  page: 1,
  size: 10,
  total: 30
})

const logs = ref([])

const stats = ref({
  total: 30,
  pending: 8,
  approved: 18,
  adjusted: 4
})

const demoLogs = [
  {
    id: 'DL-20260627-001',
    analysis_type: 'multimodal',
    title: '综合办公楼A座多模态风险分析',
    location: '综合办公楼A座',
    building_name: '综合办公楼A座',
    risk_score: 87,
    hazard_count: 4,
    status: 'pending',
    created_at: '2026-06-27 10:30:00',
    agent_version: 'Agent v2.1',
    risk_explanation: '该楼风险评分87分，主要由于过去30天内3次电气报警未及时闭环，且西侧疏散通道堆放杂物多次被拍照上报。',
    hazards: [
      { name: '疏散通道堵塞', severity: 'A级', evidence: '西侧楼道堆放纸箱、桌椅等杂物' },
      { name: '灭火器缺失', severity: 'B级', evidence: '3层西侧灭火器箱为空' },
      { name: '配电箱杂物', severity: 'B级', evidence: '配电室门口堆放纸箱' },
      { name: '温度偏高', severity: 'C级', evidence: '配电室温度达58°C' },
    ],
    recommendations: [
      { action: '立即清理西侧疏散通道杂物', priority: '紧急', responsible: '物业张工', timeframe: '2小时内' },
      { action: '补齐3层西侧灭火器并检查压力', priority: '高', responsible: '消防设施管理员', timeframe: '24小时内' },
      { action: '清理配电室周边杂物，检查通风系统', priority: '高', responsible: '电工班', timeframe: '24小时内' },
      { action: '安排电气安全专项检查', priority: '中', responsible: '安全管理员', timeframe: '3天内' },
    ],
    analysis_steps: [
      { name: '任务分解', description: '分析用户输入，分解为文本、图像、遥测三类分析任务' },
      { name: '文本分析', description: '解析巡检描述，识别关键词和隐患类型' },
      { name: '图像分析', description: '调用视觉模型检测图片中的风险目标' },
      { name: '遥测分析', description: '分析设备遥测数据，判断异常状态' },
      { name: '多源融合', description: '融合三模态结果，去重合并，生成统一隐患列表' },
      { name: '风险评估', description: '基于隐患清单计算综合风险评分' },
      { name: '知识检索', description: '检索RAG知识库相关法规和处置方案' },
      { name: '生成建议', description: '综合所有信息生成处置建议和工单' },
    ],
    knowledge_refs: [
      { title: '建筑设计防火规范 GB50016', snippet: '疏散走道和安全出口的净宽度应符合规定，不得堆放杂物...' },
      { title: '建筑灭火器配置设计规范', snippet: '每个设置点的灭火器数量不宜多于5具，不应少于2具...' },
      { title: '用电安全导则', snippet: '配电装置周围不得堆放易燃、易爆、潮湿和其他影响操作的物品...' },
    ]
  },
  {
    id: 'DL-20260627-002',
    analysis_type: 'alert_analysis',
    title: '实验楼B座剩余电流告警分析',
    location: '实验楼B座3层',
    building_name: '实验楼B座',
    risk_score: 72,
    hazard_count: 2,
    status: 'approved',
    created_at: '2026-06-27 09:45:00',
    agent_version: 'Agent v2.1',
    risk_explanation: '实验楼B座风险评分72分，主要由于3层实验室剩余电流连续3天超阈值，且化学品存放区通风系统异常。',
    hazards: [
      { name: '剩余电流超标', severity: 'B级', evidence: '3层回路剩余电流达820mA，连续3天超阈值' },
      { name: '通风系统异常', severity: 'C级', evidence: '化学品存放区排风设备告警' },
    ],
    recommendations: [
      { action: '安排电工检测3层电气回路，排查漏电原因', priority: '高', responsible: '电工班', timeframe: '24小时内' },
      { action: '检查化学品存放区通风系统', priority: '中', responsible: '设备维护组', timeframe: '3天内' },
    ],
    analysis_steps: [
      { name: '告警接收', description: '接收设备告警，识别告警类型和设备位置' },
      { name: '历史数据分析', description: '查询该设备近7天遥测数据，分析趋势' },
      { name: '原因推断', description: '基于数据模式推断可能的漏电原因' },
      { name: '风险评估', description: '评估告警对整体风险的影响' },
      { name: '生成建议', description: '给出排查方向和处置建议' },
    ],
    knowledge_refs: [
      { title: '剩余电流动作保护装置安装和运行', snippet: '剩余电流保护装置的额定剩余动作电流应符合相关规定...' },
    ]
  },
  {
    id: 'DL-20260627-003',
    analysis_type: 'inspection',
    title: '学生宿舍C区例行巡检',
    location: '学生宿舍C区',
    building_name: '学生宿舍C区',
    risk_score: 58,
    hazard_count: 3,
    status: 'adjusted',
    created_at: '2026-06-27 08:20:00',
    agent_version: 'Agent v2.0',
    risk_explanation: '学生宿舍C区风险评分58分，发现3处电动车违规充电和电线私拉乱接现象。',
    hazards: [
      { name: '电动车违规充电', severity: 'B级', evidence: '发现3处室内电动车充电' },
      { name: '电线私拉乱接', severity: 'C级', evidence: '走廊有临时拖线板' },
    ],
    recommendations: [
      { action: '立即清理违规充电车辆', priority: '高', responsible: '宿管人员', timeframe: '立即' },
      { action: '加强宿舍安全巡查和宣传', priority: '中', responsible: '宿管处', timeframe: '持续' },
    ],
    analysis_steps: [
      { name: '巡检数据接收', description: '接收巡检人员上传的文本和图片' },
      { name: '隐患识别', description: 'AI识别图片和文本中的隐患' },
      { name: '风险评分', description: '计算区域风险评分' },
      { name: '生成工单', description: '自动生成整改工单' },
    ],
    knowledge_refs: [
      { title: '高等学校消防安全管理规定', snippet: '学生宿舍内严禁私拉乱接电线，严禁使用明火和大功率电器...' },
    ],
    review_note: '人工复核：增加了安全宣传建议，风险评分从62调整为58。'
  },
]

function getTypeLabel(type) {
  const map = {
    inspection: '智能巡检',
    multimodal: '多模态分析',
    alert_analysis: '告警分析',
    risk_assessment: '风险评估',
    workorder: '工单建议'
  }
  return map[type] || type
}

function getTypeColor(type) {
  const map = {
    inspection: 'primary',
    multimodal: 'danger',
    alert_analysis: 'warning',
    risk_assessment: 'info',
    workorder: 'success'
  }
  return map[type] || 'info'
}

function getStatusLabel(status) {
  const map = {
    pending: '待复核',
    approved: '已通过',
    adjusted: '已调整',
    rejected: '已驳回'
  }
  return map[status] || status
}

function getStatusType(status) {
  const map = {
    pending: 'warning',
    approved: 'success',
    adjusted: 'info',
    rejected: 'danger'
  }
  return map[status] || 'info'
}

function getRiskLevel(score) {
  if (score >= 85) return '严重风险'
  if (score >= 60) return '高风险'
  if (score >= 35) return '中风险'
  return '低风险'
}

function getRiskClass(score) {
  if (score >= 85) return 'risk-critical'
  if (score >= 60) return 'risk-high'
  if (score >= 35) return 'risk-medium'
  return 'risk-low'
}

function getScoreClass(score) {
  if (score >= 85) return 'score-critical'
  if (score >= 60) return 'score-high'
  if (score >= 35) return 'score-medium'
  return 'score-low'
}

function getSeverityType(severity) {
  if (severity === 'A级' || severity === '严重') return 'danger'
  if (severity === 'B级' || severity === '高') return 'warning'
  return 'info'
}

function getPriorityType(priority) {
  if (priority === '紧急' || priority === 'critical') return 'danger'
  if (priority === '高' || priority === 'high') return 'warning'
  if (priority === '中' || priority === 'medium') return 'warning'
  return 'info'
}

function loadLogs() {
  loading.value = true
  setTimeout(() => {
    logs.value = demoLogs
    loading.value = false
  }, 500)
}

function searchLogs() {
  loadLogs()
  ElMessage.success('搜索完成')
}

function resetFilters() {
  filters.value = {
    analysisType: '',
    riskLevel: '',
    status: '',
    dateRange: []
  }
  loadLogs()
}

function refreshLogs() {
  loadLogs()
  ElMessage.success('日志已刷新')
}

function exportLogs() {
  ElMessage.info('日志导出功能开发中')
}

function viewLogDetail(row) {
  selectedLog.value = row
  detailDrawer.value = true
}

function approveLog(row) {
  ElMessageBox.confirm('确认通过该决策？', '复核确认', {
    type: 'success'
  }).then(() => {
    row.status = 'approved'
    stats.value.pending--
    stats.value.approved++
    ElMessage.success('已通过复核')
  }).catch(() => {})
}

function adjustLog(row) {
  ElMessage.info('人工调整功能开发中')
}

function rejectLog(row) {
  ElMessageBox.confirm('确认驳回该决策？', '驳回确认', {
    type: 'warning'
  }).then(() => {
    row.status = 'rejected'
    stats.value.pending--
    ElMessage.success('已驳回')
  }).catch(() => {})
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.decision-logs-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 6px;
}

.page-desc {
  color: var(--fire-muted);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-card {
  margin-bottom: 16px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.stat-icon {
  font-size: 32px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}

.stat-value.warning { color: var(--fire-orange); }
.stat-value.success { color: var(--fire-green); }
.stat-value.info { color: var(--fire-blue); }

.stat-label {
  color: var(--fire-muted);
  font-size: 13px;
}

.logs-card {
  margin-bottom: 16px;
}

.log-title {
  font-weight: 600;
  margin-bottom: 2px;
}

.log-subtitle {
  font-size: 12px;
  color: var(--fire-muted);
}

.risk-score-inline {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-num {
  font-size: 18px;
  font-weight: 700;
}

.score-num.score-critical { color: var(--fire-red); }
.score-num.score-high { color: var(--fire-orange); }
.score-num.score-medium { color: #f59e0b; }
.score-num.score-low { color: var(--fire-green); }

.score-label {
  font-size: 12px;
  color: var(--fire-muted);
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.log-detail {
  padding: 4px;
}

.detail-header {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.detail-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 8px;
}

.detail-meta {
  display: flex;
  gap: 20px;
  color: var(--fire-muted);
  font-size: 13px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--fire-border);
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}

.risk-summary-box {
  display: flex;
  gap: 20px;
  padding: 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f0fdf4, #ffffff);
  border-left: 4px solid var(--fire-green);
}

.risk-summary-box.risk-critical {
  background: linear-gradient(135deg, #fef2f2, #ffffff);
  border-left-color: var(--fire-red);
}

.risk-summary-box.risk-high {
  background: linear-gradient(135deg, #fff7ed, #ffffff);
  border-left-color: var(--fire-orange);
}

.risk-summary-box.risk-medium {
  background: linear-gradient(135deg, #fffbeb, #ffffff);
  border-left-color: #f59e0b;
}

.risk-score-big {
  text-align: center;
  min-width: 100px;
}

.big-score {
  font-size: 48px;
  font-weight: 800;
  line-height: 1;
  display: block;
}

.risk-critical .big-score { color: var(--fire-red); }
.risk-high .big-score { color: var(--fire-orange); }
.risk-medium .big-score { color: #f59e0b; }
.risk-low .big-score { color: var(--fire-green); }

.big-label {
  font-size: 13px;
  color: var(--fire-muted);
}

.risk-info {
  flex: 1;
}

.risk-level {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}

.risk-explanation {
  color: var(--fire-muted);
  line-height: 1.6;
  margin: 0;
}

.hazard-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hazard-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
  align-items: flex-start;
}

.hazard-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--fire-blue);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.hazard-info {
  flex: 1;
}

.hazard-name {
  font-weight: 600;
  margin-bottom: 4px;
}

.hazard-desc {
  font-size: 13px;
  color: var(--fire-muted);
}

.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rec-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  background: #f8fafc;
  border-radius: 10px;
}

.rec-tag {
  flex-shrink: 0;
  height: fit-content;
}

.rec-content {
  flex: 1;
}

.rec-action {
  font-weight: 600;
  margin-bottom: 6px;
}

.rec-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--fire-muted);
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.knowledge-item {
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}

.knowledge-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  margin-bottom: 6px;
}

.knowledge-snippet {
  font-size: 13px;
  color: var(--fire-muted);
  line-height: 1.5;
  margin: 0;
}

.detail-actions {
  display: flex;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--fire-border);
}

.detail-feedback {
  margin-top: 16px;
}
</style>
