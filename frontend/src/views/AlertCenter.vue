<template>
  <div class="alert-center-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">设备告警中心</h2>
        <p class="page-desc">设备告警自动联动系统，实时分析告警并生成处置工单</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="showSimulateDialog = true">
          <el-icon><Warning /></el-icon>
          模拟告警
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon total">📡</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total || 0 }}</div>
            <div class="stat-label">告警总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon critical"></div>
          <div class="stat-content">
            <div class="stat-value danger">{{ stats.by_severity?.critical || 0 }}</div>
            <div class="stat-label">严重告警</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon high">⚠️</div>
          <div class="stat-content">
            <div class="stat-value warning">{{ stats.by_severity?.high || 0 }}</div>
            <div class="stat-label">高级告警</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon auto"></div>
          <div class="stat-content">
            <div class="stat-value success">{{ stats.auto_workorder_count || 0 }}</div>
            <div class="stat-label">自动工单率 {{ stats.auto_workorder_rate || 0 }}%</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div class="status-tabs">
      <div class="status-tab" :class="{ active: statusTab === 'all' }" @click="statusTab = 'all'">
        全部告警
        <span class="tab-count">{{ stats.total || 0 }}</span>
      </div>
      <div class="status-tab" :class="{ active: statusTab === 'pending' }" @click="statusTab = 'pending'">
        待确认
        <span class="tab-count danger">{{ pendingCount }}</span>
      </div>
      <div class="status-tab" :class="{ active: statusTab === 'processing' }" @click="statusTab = 'processing'">
        处置中
        <span class="tab-count warning">{{ processingCount }}</span>
      </div>
      <div class="status-tab" :class="{ active: statusTab === 'resolved' }" @click="statusTab = 'resolved'">
        已处理
        <span class="tab-count success">{{ resolvedCount }}</span>
      </div>
    </div>

    <el-card class="table-card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <el-button type="danger" @click="batchConfirm" :disabled="!selectedAlerts.length">
            <el-icon><Check /></el-icon>
            批量确认
          </el-button>
          <el-button type="primary" @click="batchDispatch" :disabled="!selectedAlerts.length">
            <el-icon><Promotion /></el-icon>
            批量派单
          </el-button>
        </div>
        <div class="toolbar-right">
          <el-button @click="refreshData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" @click="showSimulateDialog = true">
            <el-icon><Warning /></el-icon>
            模拟告警
          </el-button>
        </div>
      </div>

      <el-table :data="filteredAlerts" v-loading="loading" stripe style="width: 100%" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="alert_id" label="告警编号" width="130" />
        <el-table-column label="告警级别" width="90">
          <template #default="{ row }">
            <div class="severity-badge" :class="row.severity">
              {{ severityText(row.severity) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="alert_name" label="告警类型" width="120">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small" effect="light">{{ row.alert_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备" width="120" />
        <el-table-column prop="building_name" label="位置" min-width="130" />
        <el-table-column label="处置状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.process_status)" size="small" effect="dark">
              {{ statusText(row.process_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="告警时间" width="160" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="row.process_status === 'pending'" link type="success" @click="confirmAlert(row)">确认</el-button>
            <el-button v-if="row.process_status === 'confirmed' || row.process_status === 'pending'" link type="warning" @click="dispatchAlert(row)">派单</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailDialog" title="告警详情" width="900px">
      <div v-if="currentAlert" class="alert-detail">
        <div class="detail-header">
          <div class="detail-title-row">
            <el-tag size="large" :type="severityType(currentAlert.severity)" effect="dark">
              {{ severityText(currentAlert.severity) }}
            </el-tag>
            <span class="detail-alert-name">{{ currentAlert.alert_name }}</span>
            <el-tag :type="statusTagType(currentAlert.process_status)" effect="light">
              {{ statusText(currentAlert.process_status) }}
            </el-tag>
          </div>
          <div class="detail-alert-id">{{ currentAlert.alert_id }}</div>
        </div>

        <el-row :gutter="20">
          <el-col :span="14">
            <div class="detail-section">
              <div class="section-title">基本信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="设备编号">{{ currentAlert.device_id }}</el-descriptions-item>
                <el-descriptions-item label="告警时间">{{ currentAlert.created_at }}</el-descriptions-item>
                <el-descriptions-item label="告警位置" :span="2">{{ currentAlert.building_name }}</el-descriptions-item>
                <el-descriptions-item label="风险等级">
                  <el-tag size="small" :type="riskType(currentAlert.risk_level)">{{ currentAlert.risk_level }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="告警来源">物联网设备</el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="detail-section">
              <div class="section-title">处置流程</div>
              <div class="process-flow">
                <div v-for="(step, idx) in processSteps" :key="step.key" class="process-step" :class="{ active: step.active, done: step.done, current: step.current }">
                  <div class="step-icon">
                    <el-icon v-if="step.done"><CircleCheckFilled /></el-icon>
                    <span v-else>{{ idx + 1 }}</span>
                  </div>
                  <div class="step-info">
                    <div class="step-name">{{ step.name }}</div>
                    <div class="step-time">{{ step.time || '—' }}</div>
                    <div v-if="step.operator" class="step-operator">操作人：{{ step.operator }}</div>
                  </div>
                  <div v-if="idx < processSteps.length - 1" class="step-line"></div>
                </div>
              </div>
            </div>

            <div class="detail-section" v-if="currentAlert.process_status !== 'pending'">
              <div class="section-title">处置记录</div>
              <el-timeline>
                <el-timeline-item
                  v-for="(record, idx) in processRecords"
                  :key="idx"
                  :type="record.type"
                  :timestamp="record.time"
                >
                  <div class="record-title">{{ record.title }}</div>
                  <div class="record-content">{{ record.content }}</div>
                  <div v-if="record.operator" class="record-operator">— {{ record.operator }}</div>
                </el-timeline-item>
              </el-timeline>
            </div>
          </el-col>

          <el-col :span="10">
            <div class="detail-section">
              <div class="section-title">快速操作</div>
              <div class="quick-actions">
                <el-button v-if="currentAlert.process_status === 'pending'" type="primary" style="width:100%;margin-bottom:10px" @click="confirmAlert(currentAlert)">
                  <el-icon><Check /></el-icon>确认告警
                </el-button>
                <el-button v-if="currentAlert.process_status === 'pending' || currentAlert.process_status === 'confirmed'" type="warning" style="width:100%;margin-bottom:10px" @click="dispatchAlert(currentAlert)">
                  <el-icon><Promotion /></el-icon>派发工单
                </el-button>
                <el-button v-if="currentAlert.process_status === 'dispatched' || currentAlert.process_status === 'processing'" type="success" style="width:100%;margin-bottom:10px" @click="handleDispose">
                  <el-icon><Tools /></el-icon>现场处置
                </el-button>
                <el-button v-if="currentAlert.process_status === 'processed'" style="width:100%;margin-bottom:10px" @click="handleReview">
                  <el-icon><View /></el-icon>复查确认
                </el-button>
                <el-button v-if="currentAlert.process_status === 'reviewed'" type="info" style="width:100%;margin-bottom:10px" @click="handleArchive">
                  <el-icon><FolderChecked /></el-icon>归档结案
                </el-button>
                <el-button type="danger" plain style="width:100%" @click="handleFalseAlarm">
                  <el-icon><Close /></el-icon>误报消除
                </el-button>
              </div>
            </div>

            <div class="detail-section">
              <div class="section-title">关联信息</div>
              <div class="related-info">
                <div class="related-item">
                  <el-icon><VideoCamera /></el-icon>
                  <span>关联视频：2路</span>
                  <el-button link type="primary" size="small">查看</el-button>
                </div>
                <div class="related-item">
                  <el-icon><OfficeBuilding /></el-icon>
                  <span>附近设备：6个</span>
                  <el-button link type="primary" size="small">查看</el-button>
                </div>
                <div class="related-item">
                  <el-icon><User /></el-icon>
                  <span>附近人员：3人</span>
                  <el-button link type="primary" size="small">查看</el-button>
                </div>
              </div>
            </div>

            <div class="detail-section">
              <div class="section-title ai-title">
                <el-icon><ChatDotRound /></el-icon>
                智能分析
                <el-tag v-if="aiAnalyzeResult" size="small" type="success" effect="light">
                  置信度 {{ (aiAnalyzeResult.confidence * 100).toFixed(0) }}%
                </el-tag>
              </div>
              
              <div v-if="!aiAnalyzeResult && !aiAnalyzeLoading" class="ai-analyze-entry">
                <div class="ai-entry-icon">
                  <el-icon :size="36"><MagicStick /></el-icon>
                </div>
                <p>点击下方按钮，AI将深度分析告警原因并生成处置方案</p>
                <el-button type="primary" :loading="aiAnalyzeLoading" @click="handleAIAnalyze">
                  <el-icon><MagicStick /></el-icon>
                  深度分析
                </el-button>
              </div>
              
              <div v-else-if="aiAnalyzeLoading" class="ai-loading">
                <div class="loading-spinner-small"></div>
                <span>正在分析中，请稍候...</span>
              </div>
              
              <div v-else class="ai-analysis-content">
                <div class="ai-risk-score">
                  <div class="score-circle">
                    <svg viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" stroke-width="8"/>
                      <circle 
                        cx="50" cy="50" r="40" fill="none" 
                        :stroke="aiAnalyzeResult.risk_score > 70 ? '#ef4444' : aiAnalyzeResult.risk_score > 40 ? '#f59e0b' : '#22c55e'"
                        stroke-width="8"
                        stroke-linecap="round"
                        :stroke-dasharray="`${aiAnalyzeResult.risk_score * 2.51} 251`"
                        transform="rotate(-90 50 50)"
                      />
                    </svg>
                    <div class="score-text">
                      <div class="score-value">{{ aiAnalyzeResult.risk_score }}</div>
                      <div class="score-label">风险评分</div>
                    </div>
                  </div>
                  <div class="risk-level-tag" :class="aiAnalyzeResult.risk_level">
                    {{ aiAnalyzeResult.risk_level }}
                  </div>
                </div>
                
                <el-tabs v-model="aiAnalyzeTab" size="small">
                  <el-tab-pane label="推理过程" name="reasoning">
                    <div class="reasoning-steps">
                      <div v-for="(step, idx) in aiAnalyzeResult.reasoning_steps" :key="idx" class="reasoning-step">
                        <div class="step-num">{{ step.step }}</div>
                        <div class="step-content">
                          <div class="step-title-row">
                            <span class="step-title">{{ step.title }}</span>
                            <el-tag size="small" type="info" effect="plain">
                              置信度 {{ (step.confidence * 100).toFixed(0) }}%
                            </el-tag>
                          </div>
                          <div class="step-desc">{{ step.content }}</div>
                          <div v-if="step.references && step.references.length" class="step-refs">
                            <div class="refs-label">
                              <el-icon><Files /></el-icon>
                              引用依据：
                            </div>
                            <div class="refs-list">
                              <el-tag 
                                v-for="(ref, ri) in step.references" 
                                :key="ri" 
                                size="small" 
                                effect="plain"
                                type="primary"
                              >
                                {{ ref }}
                              </el-tag>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </el-tab-pane>
                  
                  <el-tab-pane label="处置步骤" name="disposal">
                    <div class="disposal-steps">
                      <div class="disposal-type-tag immediate">立即处置</div>
                      <div 
                        v-for="step in aiAnalyzeResult.disposal_steps.filter(s => s.type === 'immediate')" 
                        :key="step.order" 
                        class="disposal-step"
                      >
                        <div class="step-order">{{ step.order }}</div>
                        <div class="step-detail">
                          <div class="step-detail-title">{{ step.title }}</div>
                          <div class="step-detail-desc">{{ step.detail }}</div>
                        </div>
                      </div>
                      <div class="disposal-type-tag investigation">排查步骤</div>
                      <div 
                        v-for="step in aiAnalyzeResult.disposal_steps.filter(s => s.type === 'investigation')" 
                        :key="step.order" 
                        class="disposal-step"
                      >
                        <div class="step-order">{{ step.order }}</div>
                        <div class="step-detail">
                          <div class="step-detail-title">{{ step.title }}</div>
                          <div class="step-detail-desc">{{ step.detail }}</div>
                        </div>
                      </div>
                    </div>
                    <div class="disposal-action">
                      <el-button type="primary" style="width: 100%" @click="handleGenerateRectification">
                        <el-icon><Files /></el-icon>
                        生成整改工单
                      </el-button>
                    </div>
                  </el-tab-pane>
                  
                  <el-tab-pane label="相关知识" name="knowledge">
                    <div class="knowledge-list">
                      <div 
                        v-for="(item, idx) in aiAnalyzeResult.related_knowledge" 
                        :key="idx" 
                        class="knowledge-item"
                      >
                        <div class="knowledge-icon">
                          <el-icon><Collection /></el-icon>
                        </div>
                        <div class="knowledge-info">
                          <div class="knowledge-title">{{ item.title }}</div>
                          <div class="knowledge-meta">
                            <el-tag size="small" effect="plain">{{ item.type }}</el-tag>
                            <span class="knowledge-match">匹配度 {{ item.match }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </el-tab-pane>
                  
                  <el-tab-pane label="类似告警" name="similar">
                    <div class="similar-alerts">
                      <div 
                        v-for="(alert, idx) in aiAnalyzeResult.similar_alerts" 
                        :key="idx" 
                        class="similar-alert-item"
                      >
                        <div class="similar-id">{{ alert.id }}</div>
                        <div class="similar-info">
                          <div class="similar-location">{{ alert.location }}</div>
                          <div class="similar-meta">
                            <span>{{ alert.time }}</span>
                            <el-tag size="small" :type="similarAlertTagType(alert.result)" effect="plain">
                              {{ alert.result }}
                            </el-tag>
                          </div>
                        </div>
                      </div>
                      <el-empty
                        v-if="!aiAnalyzeResult.similar_alerts?.length"
                        description="本租户暂无同类型历史告警"
                        :image-size="60"
                      />
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="detailDialog = false">关闭</el-button>
        <el-button type="primary" @click="detailDialog = false">打印工单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRectificationDialog" title="生成整改方案" width="600px">
      <div v-loading="rectificationLoading">
        <div v-if="rectificationPlan">
          <el-alert 
            :title="`预计整改期限：${rectificationPlan.estimated_deadline_days}天`" 
            type="warning" 
            :closable="false" 
            show-icon
            style="margin-bottom: 16px"
          />
          
          <div class="rectification-section">
            <div class="rect-section-title">整改步骤</div>
            <div class="rect-steps">
              <div v-for="step in rectificationPlan.rectification_steps" :key="step.order" class="rect-step">
                <div class="rect-step-num">{{ step.order }}</div>
                <div class="rect-step-content">
                  <div class="rect-step-text">{{ step.content }}</div>
                  <el-tag size="small" effect="plain" type="info">预计 {{ step.duration }}</el-tag>
                </div>
              </div>
            </div>
          </div>
          
          <div class="rectification-section">
            <div class="rect-section-title">验收标准</div>
            <ul class="rect-list">
              <li v-for="(item, idx) in rectificationPlan.acceptance_criteria" :key="idx">{{ item }}</li>
            </ul>
          </div>
          
          <div class="rectification-section">
            <div class="rect-section-title">所需资源</div>
            <div class="rect-tags">
              <el-tag v-for="(res, idx) in rectificationPlan.required_resources" :key="idx" effect="plain">
                {{ res }}
              </el-tag>
            </div>
          </div>
          
          <div class="rectification-section">
            <div class="rect-section-title">注意事项</div>
            <ul class="rect-list warning">
              <li v-for="(note, idx) in rectificationPlan.notes" :key="idx">{{ note }}</li>
            </ul>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showRectificationDialog = false">关闭</el-button>
        <el-button type="primary" @click="confirmCreateWorkorder">确认创建工单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showSimulateDialog" title="模拟设备告警" width="500px">
      <el-form :model="simulateForm" label-width="100px">
        <el-form-item label="告警类型">
          <el-select v-model="simulateForm.alert_type" style="width: 100%">
            <el-option label="烟雾浓度超标" value="smoke_high" />
            <el-option label="温度异常升高" value="temperature_high" />
            <el-option label="剩余电流超标" value="remaining_current" />
            <el-option label="电流过载" value="current_high" />
            <el-option label="水压过低" value="pressure_low" />
            <el-option label="设备离线" value="device_offline" />
            <el-option label="电池电量低" value="battery_low" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备ID">
          <el-input v-model="simulateForm.device_id" placeholder="请输入设备ID" />
        </el-form-item>
        <el-form-item label="告警值">
          <el-input-number v-model="simulateForm.alert_value" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="建筑名称">
          <el-input v-model="simulateForm.building_name" placeholder="请输入建筑/区域名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSimulateDialog = false">取消</el-button>
        <el-button type="primary" @click="simulateAlert" :loading="simulating">触发告警</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh, Warning, Check, Promotion, CircleCheckFilled,
  Tools, View, FolderChecked, Close, VideoCamera, OfficeBuilding, User,
  ChatDotRound, MagicStick, TrendCharts, Collection, Files
} from '@element-plus/icons-vue'
import { alertList, alertStatistics, alertProcess } from '../api'
import { analyzeAlert, generateRectificationPlan } from '@/api/intelligence'

const loading = ref(false)
const alerts = ref([])
const stats = ref({})
const statusTab = ref('all')
const selectedAlerts = ref([])
const filters = ref({
  alert_type: '',
  severity: '',
  building_id: ''
})

const detailDialog = ref(false)
const currentAlert = ref(null)
const aiAnalyzeLoading = ref(false)
const aiAnalyzeResult = ref(null)
const aiAnalyzeTab = ref('reasoning')
const showRectificationDialog = ref(false)
const rectificationPlan = ref(null)
const rectificationLoading = ref(false)

const showSimulateDialog = ref(false)
const simulating = ref(false)
const simulateForm = ref({
  alert_type: 'smoke_high',
  device_id: 'DEV-SIM-001',
  alert_value: 85,
  building_name: '综合办公楼A座'
})

const pendingCount = computed(() => alerts.value.filter(a => a.process_status === 'pending').length)
const processingCount = computed(() => alerts.value.filter(a => ['pending', 'confirmed', 'dispatched', 'processing'].includes(a.process_status)).length)
const resolvedCount = computed(() => alerts.value.filter(a => a.process_status === 'resolved' || a.process_status === 'closed').length)

const filteredAlerts = computed(() => {
  if (statusTab.value === 'all') return alerts.value
  if (statusTab.value === 'pending') return alerts.value.filter(a => a.process_status === 'pending')
  if (statusTab.value === 'processing') return alerts.value.filter(a => ['confirmed', 'dispatched', 'processing'].includes(a.process_status))
  if (statusTab.value === 'resolved') return alerts.value.filter(a => a.process_status === 'resolved' || a.process_status === 'closed')
  return alerts.value
})

function severityText(severity) {
  const map = { critical: '严重', high: '高', medium: '中', low: '低' }
  return map[severity] || '中'
}

function statusText(status) {
  const map = {
    pending: '待确认',
    confirmed: '已确认',
    dispatched: '已派单',
    processing: '处置中',
    resolved: '已处理',
    closed: '已归档',
    ignored: '已忽略'
  }
  return map[status] || '待确认'
}

function statusTagType(status) {
  if (status === 'pending') return 'danger'
  if (['confirmed', 'dispatched', 'processing'].includes(status)) return 'warning'
  if (status === 'resolved' || status === 'closed') return 'success'
  if (status === 'ignored') return 'info'
  return 'info'
}

function onSelectionChange(val) {
  selectedAlerts.value = val
}

function severityType(severity) {
  if (severity === 'critical') return 'danger'
  if (severity === 'high') return 'warning'
  if (severity === 'medium') return 'info'
  return ''
}

function riskType(level) {
  if (level === '严重风险') return 'danger'
  if (level === '高风险') return 'warning'
  if (level === '中风险') return 'info'
  return 'success'
}

// 「类似告警」里展示的是本租户真实历史告警的处置状态（不再是随机编出来的结果）
function similarAlertTagType(result) {
  if (result === '已处置') return 'success'
  if (result === '待处置' || result === '处置中') return 'warning'
  return 'info'
}

async function loadStatistics() {
  try {
    const res = await alertStatistics()
    stats.value = res.data
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

async function loadAlerts() {
  loading.value = true
  try {
    const params = {}
    if (filters.value.alert_type) params.alert_type = filters.value.alert_type
    if (filters.value.severity) params.severity = filters.value.severity
    if (filters.value.building_id) params.building_id = filters.value.building_id
    const res = await alertList(params)
    const list = res.data.items || []
    list.forEach((item, idx) => {
      if (!item.process_status) {
        const statuses = ['pending', 'pending', 'confirmed', 'dispatched', 'processing', 'resolved', 'resolved']
        item.process_status = statuses[idx % statuses.length]
      }
    })
    alerts.value = list
  } catch (e) {
    const mock = generateMockAlerts()
    alerts.value = mock
  } finally {
    loading.value = false
  }
}

function generateMockAlerts() {
  const types = [
    { name: '烟雾浓度超标', type: 'smoke_high', severity: 'critical' },
    { name: '温度异常升高', type: 'temperature_high', severity: 'high' },
    { name: '设备离线', type: 'device_offline', severity: 'high' },
    { name: '水压过低', type: 'pressure_low', severity: 'medium' },
    { name: '电池电量低', type: 'battery_low', severity: 'low' },
    { name: '电流过载', type: 'current_high', severity: 'high' },
  ]
  const buildings = ['综合办公楼A座', '实验楼B座', '学生宿舍C区', '图书馆D馆']
  const statuses = ['pending', 'pending', 'confirmed', 'dispatched', 'processing', 'resolved', 'resolved', 'closed']
  const arr = []
  for (let i = 1; i <= 25; i++) {
    const t = types[i % types.length]
    arr.push({
      id: i,
      alert_id: `AL${String(20260900 + i).padStart(10, '0')}`,
      alert_name: t.name,
      alert_type: t.type,
      severity: t.severity,
      device_id: `DEV-${String(i).padStart(6, '0')}`,
      building_name: buildings[i % buildings.length],
      risk_level: i % 4 === 0 ? '严重风险' : i % 3 === 0 ? '高风险' : i % 2 === 0 ? '中风险' : '低风险',
      process_status: statuses[i % statuses.length],
      created_at: `2026-09-0${(i % 9) + 1} ${String(8 + (i % 12)).padStart(2, '0')}:${String(i * 7 % 60).padStart(2, '0')}:${String(i * 13 % 60).padStart(2, '0')}`,
      workorder: i % 3 === 0 ? {
        id: `WO${String(1000 + i).padStart(6, '0')}`,
        title: `${t.name}处置工单`,
        status: i % 2 === 0 ? '处理中' : '已完成',
        responsible_role: '维保工程师',
        deadline: `2026-09-1${(i % 9) + 2}`,
        auto_generated: i % 2 === 0,
        recommended_action: '立即现场核查设备状态，确认告警真实性并采取相应处置措施'
      } : null,
      analysis: {
        analysis_steps: [
          { step: 1, name: '数据接收', description: '接收到设备告警数据' },
          { step: 2, name: '阈值分析', description: '检测值超过预设告警阈值' },
          { step: 3, name: '趋势研判', description: '分析近10分钟数据变化趋势' },
          { step: 4, name: '关联分析', description: '关联周边设备状态综合判断' },
          { step: 5, name: '风险评估', description: '评估当前告警风险等级' },
          { step: 6, name: '处置建议', description: '生成处置建议并自动派单' },
        ],
        trend: { description: '数据呈持续上升趋势，需立即关注' },
        most_likely_causes: [
          '设备周边环境异常变化',
          '设备灵敏度漂移导致误报',
          '真实火情初期烟雾浓度升高',
        ],
        immediate_actions: [
          '立即派人前往现场核查',
          '查看视频监控确认现场情况',
          '通知相关区域人员做好疏散准备',
          '检查周边消防设施状态',
        ]
      },
      risk_update: { success: true, new_score: '75分（高风险）' }
    })
  }
  stats.value.total = arr.length
  stats.value.by_severity = {
    critical: arr.filter(a => a.severity === 'critical').length,
    high: arr.filter(a => a.severity === 'high').length,
    medium: arr.filter(a => a.severity === 'medium').length,
    low: arr.filter(a => a.severity === 'low').length,
  }
  stats.value.auto_workorder_count = arr.filter(a => a.workorder?.auto_generated).length
  stats.value.auto_workorder_rate = Math.round(stats.value.auto_workorder_count / arr.length * 100)
  return arr
}

async function refreshData() {
  await Promise.all([loadStatistics(), loadAlerts()])
}

function resetFilters() {
  filters.value = {
    alert_type: '',
    severity: '',
    building_id: ''
  }
  loadAlerts()
}

function viewDetail(row) {
  currentAlert.value = row
  detailDialog.value = true
  aiAnalyzeResult.value = null
  aiAnalyzeTab.value = 'reasoning'
}

async function handleAIAnalyze() {
  if (!currentAlert.value) return
  
  aiAnalyzeLoading.value = true
  try {
    const res = await analyzeAlert({
      alert_id: currentAlert.value.id,
      alert_type: currentAlert.value.alert_type,
      alert_name: currentAlert.value.alert_name,
      severity: currentAlert.value.severity,
      device_id: currentAlert.value.device_id,
      building_name: currentAlert.value.building_name,
    })
    // 接口外层是 { ok, data }：以前只取到信封，弹窗里全是 undefined
    aiAnalyzeResult.value = res.data?.data || null
  } catch (e) {
    ElMessage.error('分析失败，请稍后重试')
  } finally {
    aiAnalyzeLoading.value = false
  }
}

async function handleGenerateRectification() {
  if (!currentAlert.value) return
  
  rectificationLoading.value = true
  try {
    const res = await generateRectificationPlan({
      hazard_type: '消防设施',
      risk_level: currentAlert.value.severity,
      description: currentAlert.value.alert_name,
      building_name: currentAlert.value.building_name,
      device_id: currentAlert.value.device_id,
    })
    // 同上：整改方案也是 { ok, data } 信封
    rectificationPlan.value = res.data?.data || null
    showRectificationDialog.value = true
  } catch (e) {
    ElMessage.error('生成整改方案失败')
  } finally {
    rectificationLoading.value = false
  }
}

function confirmCreateWorkorder() {
  ElMessage.success('整改工单已创建！')
  showRectificationDialog.value = false
  if (currentAlert.value) {
    currentAlert.value.process_status = 'dispatched'
  }
}

const processSteps = computed(() => {
  if (!currentAlert.value) return []
  const status = currentAlert.value.process_status
  const steps = [
    { key: 'detect', name: '设备监测', done: true, time: currentAlert.value.created_at, operator: '系统自动' },
    { key: 'alert', name: '触发告警', done: true, time: currentAlert.value.created_at, operator: '系统自动' },
    { key: 'confirm', name: '告警确认', done: status !== 'pending', time: status !== 'pending' ? currentAlert.value.created_at : '', operator: status !== 'pending' ? '值班员' : '' },
    { key: 'dispatch', name: '派发工单', done: ['dispatched', 'processing', 'processed', 'reviewed', 'archived'].includes(status), time: ['dispatched', 'processing'].includes(status) ? currentAlert.value.created_at : '', operator: ['dispatched', 'processing'].includes(status) ? '值班班长' : '' },
    { key: 'process', name: '现场处置', done: ['processed', 'reviewed', 'archived'].includes(status), time: status === 'processed' ? currentAlert.value.created_at : '', operator: status === 'processed' ? '巡检员' : '' },
    { key: 'review', name: '复查确认', done: ['reviewed', 'archived'].includes(status), time: status === 'reviewed' ? currentAlert.value.created_at : '', operator: status === 'reviewed' ? '安管员' : '' },
    { key: 'archive', name: '归档结案', done: status === 'archived', time: status === 'archived' ? currentAlert.value.created_at : '', operator: status === 'archived' ? '系统' : '' },
  ]
  const currentIdx = steps.findIndex(s => !s.done)
  if (currentIdx >= 0) {
    steps[currentIdx].current = true
  }
  return steps
})

const processRecords = computed(() => {
  if (!currentAlert.value) return []
  const records = [
    { title: '设备数据异常，触发告警', content: currentAlert.value.alert_name + '，设备编号：' + currentAlert.value.device_id, time: currentAlert.value.created_at, type: 'danger', operator: '系统' },
  ]
  if (currentAlert.value.process_status !== 'pending') {
    records.push({ title: '值班员确认告警', content: '经视频复核，确认告警属实，通知相关人员到场', time: currentAlert.value.created_at, type: 'warning', operator: '张建国' })
  }
  if (['dispatched', 'processing', 'processed', 'reviewed', 'archived'].includes(currentAlert.value.process_status)) {
    records.push({ title: '派发处置工单', content: '工单已派发至巡检组，要求30分钟内到场处置', time: currentAlert.value.created_at, type: 'primary', operator: '值班班长' })
  }
  if (['processed', 'reviewed', 'archived'].includes(currentAlert.value.process_status)) {
    records.push({ title: '现场处置完成', content: '巡检员已到达现场，查明原因并完成处置，设备恢复正常', time: currentAlert.value.created_at, type: 'success', operator: '李明华' })
  }
  if (['reviewed', 'archived'].includes(currentAlert.value.process_status)) {
    records.push({ title: '复查确认通过', content: '安管员现场复查，确认隐患已消除，符合安全要求', time: currentAlert.value.created_at, type: 'success', operator: '王安全' })
  }
  if (currentAlert.value.process_status === 'archived') {
    records.push({ title: '告警已归档结案', content: '全流程闭环完成，记录归档保存', time: currentAlert.value.created_at, type: 'info', operator: '系统' })
  }
  return records.reverse()
})

function handleDispose() {
  if (currentAlert.value) {
    currentAlert.value.process_status = 'processed'
    ElMessage.success('处置完成，等待复查')
  }
}

function handleReview() {
  if (currentAlert.value) {
    currentAlert.value.process_status = 'reviewed'
    ElMessage.success('复查通过')
  }
}

function handleArchive() {
  if (currentAlert.value) {
    currentAlert.value.process_status = 'archived'
    ElMessage.success('已归档结案')
    detailDialog.value = false
  }
}

function handleFalseAlarm() {
  ElMessageBox.confirm('确认该告警为误报？', '提示', { type: 'warning' })
    .then(() => {
      if (currentAlert.value) {
        currentAlert.value.process_status = 'archived'
        ElMessage.success('已标记为误报并归档')
        detailDialog.value = false
      }
    })
    .catch(() => {})
}

function confirmAlert(row) {
  row.process_status = 'confirmed'
  ElMessage.success('告警已确认')
}

function dispatchAlert(row) {
  ElMessageBox.prompt('请输入处理人员', '派单确认', {
    confirmButtonText: '确认派单',
    cancelButtonText: '取消',
    inputValue: '张工',
  }).then(() => {
    row.process_status = 'dispatched'
    ElMessage.success('已派单处理')
  }).catch(() => {})
}

async function batchConfirm() {
  if (!selectedAlerts.value.length) return
  try {
    await ElMessageBox.confirm(`确认选中的 ${selectedAlerts.value.length} 条告警吗？`, '批量确认', {
      type: 'warning',
    })
    selectedAlerts.value.forEach(a => {
      const found = alerts.value.find(x => x.id === a.id)
      if (found) found.process_status = 'confirmed'
    })
    ElMessage.success('批量确认成功')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

async function batchDispatch() {
  if (!selectedAlerts.value.length) return
  try {
    await ElMessageBox.confirm(`将选中的 ${selectedAlerts.value.length} 条告警派单处理？`, '批量派单', {
      type: 'warning',
    })
    selectedAlerts.value.forEach(a => {
      const found = alerts.value.find(x => x.id === a.id)
      if (found) found.process_status = 'dispatched'
    })
    ElMessage.success('批量派单成功')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

async function simulateAlert() {
  simulating.value = true
  try {
    const formData = new FormData()
    formData.append('device_id', simulateForm.value.device_id)
    formData.append('alert_type', simulateForm.value.alert_type)
    formData.append('alert_value', simulateForm.value.alert_value)
    formData.append('building_name', simulateForm.value.building_name)
    formData.append('building_id', 'building_sim')
    
    const history = []
    for (let i = 0; i < 10; i++) {
      history.push({
        value: simulateForm.value.alert_value - i * 2 + Math.random() * 5,
        timestamp: new Date(Date.now() - i * 10 * 60 * 1000).toISOString()
      })
    }
    formData.append('telemetry_history', JSON.stringify(history))
    formData.append('device_info', JSON.stringify({
      name: '模拟设备-' + simulateForm.value.device_id,
      location: simulateForm.value.building_name,
      type: 'simulator'
    }))

    await alertProcess(formData)
    ElMessage.success('告警已触发，Agent正在处理...')
    showSimulateDialog.value = false
    setTimeout(() => refreshData(), 500)
  } catch (e) {
    console.error('模拟告警失败', e)
  } finally {
    simulating.value = false
  }
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.alert-center-page {
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

.status-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.status-tab {
  flex: 1;
  padding: 14px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 3px solid transparent;
  font-size: 14px;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.status-tab:hover {
  background: #f8fafc;
  color: #334155;
}

.status-tab.active {
  color: #2563eb;
  font-weight: 600;
  border-bottom-color: #2563eb;
  background: #f0f7ff;
}

.tab-count {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #e2e8f0;
  color: #475569;
  font-weight: 500;
}

.tab-count.danger {
  background: #fee2e2;
  color: #dc2626;
}

.tab-count.warning {
  background: #fef3c7;
  color: #d97706;
}

.tab-count.success {
  background: #dcfce7;
  color: #16a34a;
}

.table-card {
  margin-bottom: 12px;
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

.severity-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
}

.severity-badge.critical {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.severity-badge.high {
  background: #fffbeb;
  color: #d97706;
  border: 1px solid #fde68a;
}

.severity-badge.medium {
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}

.severity-badge.low {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
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
.stat-icon.critical { background: #fef2f2; }
.stat-icon.high { background: #fffbeb; }
.stat-icon.auto { background: #f0fdf4; }
.stat-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}
.stat-value.danger { color: var(--fire-red); }
.stat-value.warning { color: var(--fire-orange); }
.stat-value.success { color: var(--fire-green); }
.stat-value.info { color: var(--fire-blue); }
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
.cause-list {
  margin: 0;
  padding-left: 20px;
  line-height: 2;
  color: #475569;
}
.workorder-card {
  background: #f8fafc;
}
.workorder-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.workorder-info {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}
.workorder-desc {
  font-size: 14px;
  color: #334155;
  line-height: 1.6;
}
.alert-detail :deep(.el-descriptions__label) {
  width: 120px;
}

.detail-header {
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}

.detail-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}

.detail-alert-name {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.detail-alert-id {
  font-size: 13px;
  color: #64748b;
}

.detail-section {
  margin-bottom: 18px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #3b82f6;
}

.process-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}

.process-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  position: relative;
  padding-bottom: 18px;
}

.process-step:last-child {
  padding-bottom: 0;
}

.step-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  z-index: 2;
}

.process-step.done .step-icon {
  background: #22c55e;
  color: #fff;
}

.process-step.current .step-icon {
  background: #3b82f6;
  color: #fff;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
  animation: step-pulse 2s ease-in-out infinite;
}

@keyframes step-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2); }
  50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.1); }
}

.step-info {
  flex: 1;
  padding-top: 2px;
}

.step-name {
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
}

.process-step.done .step-name,
.process-step.current .step-name {
  color: #0f172a;
}

.step-time {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.step-operator {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.step-line {
  position: absolute;
  left: 13px;
  top: 28px;
  bottom: 0;
  width: 2px;
  background: #e2e8f0;
}

.process-step.done .step-line {
  background: #22c55e;
}

.record-title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.record-content {
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
  line-height: 1.5;
}

.record-operator {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  text-align: right;
}

.quick-actions {
  display: flex;
  flex-direction: column;
}

.related-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
}

.related-item :deep(.el-icon) {
  color: #3b82f6;
}

.related-item span {
  flex: 1;
}

.cause-list-small {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: #475569;
  line-height: 1.8;
}

.action-tip {
  font-size: 13px;
  color: #92400e;
  margin-top: 4px;
  line-height: 1.5;
}

.ai-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ai-title .el-tag {
  margin-left: auto;
}

.ai-analyze-entry {
  text-align: center;
  padding: 24px 12px;
  background: linear-gradient(135deg, #eff6ff, #ecfeff);
  border-radius: 8px;
}
.ai-entry-icon {
  color: #3b82f6;
  margin-bottom: 10px;
}
.ai-analyze-entry p {
  color: #64748b;
  font-size: 13px;
  margin: 0 0 12px;
}

.ai-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 30px 0;
  color: #64748b;
  font-size: 13px;
}

.loading-spinner-small {
  width: 20px;
  height: 20px;
  border: 2px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: aiSpin 0.8s linear infinite;
}

@keyframes aiSpin {
  to { transform: rotate(360deg); }
}

.ai-risk-score {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.score-circle {
  position: relative;
  width: 64px;
  height: 64px;
}
.score-circle svg {
  width: 100%;
  height: 100%;
}
.score-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.score-value {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1;
}
.score-label {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}

.risk-level-tag {
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}
.risk-level-tag.严重风险,
.risk-level-tag.critical {
  background: #fef2f2;
  color: #dc2626;
}
.risk-level-tag.高风险,
.risk-level-tag.high {
  background: #fff7ed;
  color: #ea580c;
}
.risk-level-tag.中风险,
.risk-level-tag.medium {
  background: #fefce8;
  color: #ca8a04;
}
.risk-level-tag.低风险,
.risk-level-tag.low {
  background: #f0fdf4;
  color: #16a34a;
}

.reasoning-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.reasoning-step {
  display: flex;
  gap: 10px;
}
.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-content {
  flex: 1;
}
.step-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.step-title {
  font-weight: 600;
  font-size: 13px;
  color: #1e293b;
}
.step-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.step-refs {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}
.refs-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 6px;
}
.refs-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.disposal-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.disposal-type-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px;
  align-self: flex-start;
  margin-top: 8px;
}
.disposal-type-tag.immediate {
  background: #fef2f2;
  color: #dc2626;
}
.disposal-type-tag.investigation {
  background: #fefce8;
  color: #ca8a04;
}
.disposal-step {
  display: flex;
  gap: 10px;
  padding: 8px;
  background: #f8fafc;
  border-radius: 6px;
}
.step-order {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-detail-title {
  font-size: 12px;
  font-weight: 500;
  color: #334155;
  margin-bottom: 2px;
}
.step-detail-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}
.disposal-action {
  margin-top: 12px;
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.knowledge-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: #f8fafc;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.knowledge-item:hover {
  background: #eff6ff;
}
.knowledge-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #dbeafe;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.knowledge-title {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 4px;
}
.knowledge-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.knowledge-match {
  font-size: 11px;
  color: #64748b;
}

.similar-alerts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.similar-alert-item {
  display: flex;
  gap: 10px;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}
.similar-id {
  font-size: 11px;
  color: #64748b;
  font-family: monospace;
}
.similar-info {
  flex: 1;
}
.similar-location {
  font-size: 12px;
  color: #334155;
  margin-bottom: 2px;
}
.similar-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #94a3b8;
}

.rectification-section {
  margin-bottom: 16px;
}
.rect-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #3b82f6;
}
.rect-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rect-step {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: #f8fafc;
  border-radius: 6px;
}
.rect-step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.rect-step-content {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}
.rect-step-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
}
.rect-list {
  margin: 0;
  padding-left: 20px;
}
.rect-list li {
  margin-bottom: 6px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}
.rect-list.warning li {
  color: #b45309;
}
.rect-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
