<template>
  <div class="multimodal-page">
    <div class="page-header">
      <h2 class="page-title">多模态风险分析</h2>
      <p class="page-desc">融合文本描述、现场图片、设备遥测数据，进行综合风险评估</p>
    </div>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="input-card">
          <template #header>
            <div class="card-header">
              <span>📝 输入信息</span>
              <el-tag size="small" type="info">三模态联合分析</el-tag>
            </div>
          </template>

          <div class="input-section">
            <div class="section-title">
              <el-icon><Edit /></el-icon>
              <span>文本描述</span>
            </div>
            <el-input
              v-model="formData.description"
              type="textarea"
              :rows="4"
              placeholder="请输入巡检描述、故障描述或用户提问..."
            />
            <div class="quick-tags">
              <el-tag
                v-for="tag in quickTags"
                :key="tag"
                class="quick-tag"
                size="small"
                effect="plain"
                @click="addQuickTag(tag)"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>

          <div class="input-section">
            <div class="section-title">
              <el-icon><Picture /></el-icon>
              <span>现场图片</span>
            </div>
            <el-upload
              v-model:file-list="imageFiles"
              :auto-upload="false"
              :limit="5"
              list-type="picture-card"
              accept="image/*"
            >
              <el-icon><Plus /></el-icon>
            </el-upload>
          </div>

          <div class="input-section">
            <div class="section-title">
              <el-icon><DataAnalysis /></el-icon>
              <span>设备遥测数据</span>
            </div>
            <div class="telemetry-inputs">
              <el-row :gutter="10">
                <el-col :span="12">
                  <el-form-item label="温度(°C)">
                    <el-input-number v-model="telemetryData.temperature" :min="0" :max="200" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="烟雾(mg/m³)">
                    <el-input-number v-model="telemetryData.smoke" :min="0" :max="10" :step="0.1" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="10">
                <el-col :span="12">
                  <el-form-item label="电流(A)">
                    <el-input-number v-model="telemetryData.current" :min="0" :max="100" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="电压(V)">
                    <el-input-number v-model="telemetryData.voltage" :min="0" :max="500" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="10">
                <el-col :span="12">
                  <el-form-item label="水压(MPa)">
                    <el-input-number v-model="telemetryData.pressure" :min="0" :max="2" :step="0.1" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="剩余电流(mA)">
                    <el-input-number v-model="telemetryData.remaining_current" :min="0" :max="2000" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>

          <div class="input-section">
            <div class="section-title">
              <el-icon><OfficeBuilding /></el-icon>
              <span>建筑/区域信息</span>
            </div>
            <el-form :model="buildingInfo" label-width="100px">
              <el-form-item label="建筑名称">
                <el-input v-model="buildingInfo.name" placeholder="请输入建筑名称" />
              </el-form-item>
              <el-form-item label="区域位置">
                <el-input v-model="buildingInfo.location" placeholder="如：西侧楼道、A区实验室" />
              </el-form-item>
              <el-form-item label="环境类型">
                <el-select v-model="buildingInfo.envType" placeholder="请选择" style="width: 100%">
                  <el-option label="普通办公区" value="office" />
                  <el-option label="实验室" value="lab" />
                  <el-option label="仓库" value="warehouse" />
                  <el-option label="宿舍" value="dormitory" />
                  <el-option label="机房" value="server_room" />
                </el-select>
              </el-form-item>
              <el-form-item label="整改及时率">
                <el-slider v-model="buildingInfo.rectificationRate" :min="0" :max="100" show-input />
              </el-form-item>
            </el-form>
          </div>

          <el-button
            type="primary"
            size="large"
            class="analyze-btn"
            :loading="analyzing"
            @click="startAnalysis"
          >
            {{ analyzing ? '分析中...' : '启动多模态分析' }}
          </el-button>
        </el-card>
      </el-col>

      <el-col :span="16">
        <template v-if="!analysisResult">
          <el-empty description="请输入分析信息后点击启动分析" />
        </template>

        <template v-else>
          <el-row :gutter="16">
            <el-col :span="24">
              <el-card class="summary-card" :class="riskLevelClass">
                <div class="summary-top">
                  <div class="risk-score-box">
                    <div class="score-label">综合风险评分</div>
                    <div class="score-value">{{ analysisResult.risk_result?.risk_score || 0 }}</div>
                    <el-tag :type="riskTagType" size="large" class="risk-tag">
                      {{ analysisResult.risk_result?.risk_level || '低风险' }}
                    </el-tag>
                  </div>
                  <div class="summary-info">
                    <h3>{{ analysisResult.summary }}</h3>
                    <p class="explanation">{{ analysisResult.risk_result?.explanation }}</p>
                    <div class="stat-row">
                      <div class="stat-item">
                        <span class="stat-label">隐患数量</span>
                        <span class="stat-value danger">{{ analysisResult.fusion_result?.hazards?.length || 0 }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">处置优先级</span>
                        <span class="stat-value">{{ analysisResult.decision_result?.priority_label }}</span>
                      </div>
                      <div class="stat-item">
                        <span class="stat-label">分析耗时</span>
                        <span class="stat-value">{{ analysisResult.execution_time }}s</span>
                      </div>
                    </div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <el-tabs v-model="activeTab" class="result-tabs">
            <el-tab-pane label="隐患识别" name="hazards">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-card class="sub-card">
                    <template #header>
                      <span>识别来源</span>
                    </template>
                    <div class="source-list">
                      <div v-for="source in analysisResult.fusion_result?.sources || []" :key="source.source" class="source-item">
                        <div class="source-header">
                          <span class="source-name">{{ sourceLabels[source.source] || source.source }}</span>
                          <el-tag size="small">{{ source.hazards?.length || 0 }} 项</el-tag>
                        </div>
                        <div class="source-hazards">
                          <el-tag v-for="h in source.hazards" :key="h" size="small" type="warning" class="hazard-tag">
                            {{ h }}
                          </el-tag>
                        </div>
                      </div>
                    </div>
                  </el-card>
                </el-col>
                <el-col :span="12">
                  <el-card class="sub-card">
                    <template #header>
                      <span>融合后隐患列表</span>
                    </template>
                    <div v-if="analysisResult.fusion_result?.hazard_items?.length" class="hazard-items">
                      <div v-for="(item, idx) in analysisResult.fusion_result.hazard_items" :key="idx" class="hazard-item">
                        <div class="hazard-index">{{ idx + 1 }}</div>
                        <div class="hazard-info">
                          <div class="hazard-name">{{ item.hazard_name || item.type }}</div>
                          <div class="hazard-desc">{{ item.evidence || item.reason }}</div>
                        </div>
                        <el-tag :type="getSeverityType(item.severity)" size="small">
                          {{ item.severity || 'C级' }}
                        </el-tag>
                      </div>
                    </div>
                    <el-empty v-else description="未识别到隐患" />
                  </el-card>
                </el-col>
              </el-row>
            </el-tab-pane>

            <el-tab-pane label="风险评分详情" name="risk">
              <el-card class="sub-card">
                <template #header>
                  <span>评分因子明细</span>
                </template>
                <div class="score-details">
                  <div v-for="(detail, key) in analysisResult.risk_result?.score_details || {}" :key="key" class="score-item">
                    <div class="score-item-header">
                      <span class="score-item-name">{{ factorLabels[key] || key }}</span>
                      <span class="score-item-value">{{ Math.round(detail) }} 分</span>
                    </div>
                    <el-progress :percentage="Math.min(detail / 30 * 100, 100)" :stroke-width="8" :show-text="false" />
                  </div>
                </div>
              </el-card>
            </el-tab-pane>

            <el-tab-pane label="📋 处置建议" name="suggestions">
              <el-card class="sub-card">
                <template #header>
                  <div class="card-header">
                    <span>处置建议</span>
                    <el-tag :type="analysisResult.decision_result?.need_alarm ? 'danger' : 'info'" size="small">
                      {{ analysisResult.decision_result?.need_alarm ? '需启动报警' : '常规处置' }}
                    </el-tag>
                  </div>
                </template>
                <div v-if="analysisResult.decision_result?.recommendations?.length" class="recommendations">
                  <div v-for="(rec, idx) in analysisResult.decision_result.recommendations" :key="idx" class="recommendation-item">
                    <el-tag :type="getPriorityType(rec.priority)" size="small" class="rec-priority">
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
                <el-empty v-else description="暂无处置建议" />
              </el-card>
            </el-tab-pane>

            <el-tab-pane label="知识依据" name="knowledge">
              <el-card class="sub-card">
                <template #header>
                  <span>RAG 知识库引用 ({{ analysisResult.rag_references?.length || 0 }})</span>
                </template>
                <div v-if="analysisResult.rag_references?.length" class="rag-list">
                  <div v-for="(ref, idx) in analysisResult.rag_references" :key="idx" class="rag-item">
                    <div class="rag-title">
                      <el-icon><Document /></el-icon>
                      <span>{{ ref.title || ref.source }}</span>
                      <el-tag size="small" type="info">{{ ref.category || '消防知识' }}</el-tag>
                    </div>
                    <p class="rag-summary">{{ ref.summary || ref.content_preview?.slice(0, 150) }}...</p>
                    <div class="rag-tags">
                      <el-tag v-for="kw in ref.matched_keywords?.slice(0, 3)" :key="kw" size="small" effect="plain" type="success">
                        {{ kw }}
                      </el-tag>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无知识引用" />
              </el-card>
            </el-tab-pane>

            <el-tab-pane label="分析过程" name="agent">
              <el-card class="sub-card">
                <template #header>
                  <span>分析计划与步骤</span>
                </template>
                <el-steps direction="vertical" :active="analysisResult.analysis_plan?.length || 0" finish-status="success">
                  <el-step
                    v-for="step in analysisResult.analysis_plan || []"
                    :key="step.step"
                    :title="step.name"
                    :description="step.description"
                  />
                </el-steps>
              </el-card>
            </el-tab-pane>
          </el-tabs>
        </template>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Picture, DataAnalysis, OfficeBuilding, Plus, Document } from '@element-plus/icons-vue'
import request from '../api'

const activeTab = ref('hazards')
const analyzing = ref(false)
const analysisResult = ref(null)
const imageFiles = ref([])

const formData = ref({
  description: ''
})

const telemetryData = ref({
  temperature: 25,
  smoke: 0.1,
  current: 10,
  voltage: 220,
  pressure: 0.4,
  remaining_current: 100
})

const buildingInfo = ref({
  name: '综合办公楼',
  location: '',
  envType: 'office',
  rectificationRate: 85
})

const quickTags = [
  '通道堵塞',
  '灭火器缺失',
  '配电箱杂物',
  '电线杂乱',
  '电动车充电',
  '烟雾异常'
]

const sourceLabels = {
  text: '文本识别',
  image: '图像识别',
  telemetry: '遥测分析'
}

const factorLabels = {
  hazard_level: '隐患等级',
  hazard_frequency: '隐患频次',
  rectification_rate: '整改及时率',
  overdue_tasks: '逾期任务',
  device_online: '设备在线率',
  device_alarm: '设备告警',
  device_aging: '设备老化',
  environment: '环境风险',
  history_accident: '历史事故',
  inspection_deviation: '巡检偏差'
}

const riskLevelClass = computed(() => {
  const score = analysisResult.value?.risk_result?.risk_score || 0
  if (score >= 85) return 'risk-critical'
  if (score >= 60) return 'risk-high'
  if (score >= 35) return 'risk-medium'
  return 'risk-low'
})

const riskTagType = computed(() => {
  const level = analysisResult.value?.risk_result?.risk_level
  if (level === '严重风险') return 'danger'
  if (level === '高风险') return 'warning'
  if (level === '中风险') return 'warning'
  return 'success'
})

function addQuickTag(tag) {
  if (!formData.value.description) {
    formData.value.description = tag
  } else if (!formData.value.description.includes(tag)) {
    formData.value.description += '，' + tag
  }
}

function getSeverityType(severity) {
  if (severity === 'A' || severity === '严重') return 'danger'
  if (severity === 'B' || severity === '高') return 'warning'
  return 'info'
}

function getPriorityType(priority) {
  if (priority === '紧急' || priority === 'critical') return 'danger'
  if (priority === '高' || priority === 'high') return 'warning'
  if (priority === '中' || priority === 'medium') return 'warning'
  return 'info'
}

function buildTelemetryArray() {
  const data = telemetryData.value
  const result = []
  
  if (data.temperature !== undefined) {
    result.push({ metric_type: 'temperature', value: data.temperature, unit: '°C' })
  }
  if (data.smoke !== undefined) {
    result.push({ metric_type: 'smoke', value: data.smoke, unit: 'mg/m³' })
  }
  if (data.current !== undefined) {
    result.push({ metric_type: 'current', value: data.current, unit: 'A' })
  }
  if (data.voltage !== undefined) {
    result.push({ metric_type: 'voltage', value: data.voltage, unit: 'V' })
  }
  if (data.pressure !== undefined) {
    result.push({ metric_type: 'pressure', value: data.pressure, unit: 'MPa' })
  }
  if (data.remaining_current !== undefined) {
    result.push({ metric_type: 'remaining_current', value: data.remaining_current, unit: 'mA' })
  }
  
  return result
}

function buildBuildingInfo() {
  const info = buildingInfo.value
  const env = {
    has_lab: info.envType === 'lab',
    has_chemicals: info.envType === 'lab',
    has_ev_charging: false
  }
  
  const inspectionStats = {
    rectification_rate: info.rectificationRate / 100,
    pending_tasks: 2,
    overdue_tasks: info.rectificationRate < 70 ? 1 : 0
  }
  
  return {
    id: 'building_demo',
    name: info.name,
    location: info.location,
    environment: env,
    inspection_stats: inspectionStats
  }
}

async function startAnalysis() {
  if (!formData.value.description && !imageFiles.value.length) {
    ElMessage.warning('请至少输入文本描述或上传图片')
    return
  }
  
  analyzing.value = true
  analysisResult.value = null
  
  try {
    const formDataObj = new FormData()
    formDataObj.append('description', formData.value.description)
    formDataObj.append('telemetry_data', JSON.stringify(buildTelemetryArray()))
    formDataObj.append('building_info', JSON.stringify(buildBuildingInfo()))
    
    const response = await request.post('/api/multimodal/analyze', formDataObj, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    analysisResult.value = response.data
    ElMessage.success('分析完成')
  } catch (error) {
    console.error('分析失败:', error)
    ElMessage.error('分析失败，请稍后重试')
  } finally {
    analyzing.value = false
  }
}
</script>

<style scoped>
.multimodal-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--fire-text);
}

.page-desc {
  color: var(--fire-muted);
  margin: 0;
}

.input-card {
  position: sticky;
  top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.input-section {
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--fire-text);
}

.quick-tags {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.quick-tag:hover {
  transform: translateY(-1px);
}

.telemetry-inputs :deep(.el-form-item) {
  margin-bottom: 12px;
}

.analyze-btn {
  width: 100%;
  margin-top: 10px;
  height: 48px;
  font-size: 16px;
}

.summary-card {
  margin-bottom: 16px;
  border-left: 4px solid var(--fire-green);
}

.summary-card.risk-critical {
  border-left-color: var(--fire-red);
  background: linear-gradient(135deg, #fff5f5, #ffffff);
}

.summary-card.risk-high {
  border-left-color: var(--fire-orange);
  background: linear-gradient(135deg, #fffaf2, #ffffff);
}

.summary-card.risk-medium {
  border-left-color: #f59e0b;
  background: linear-gradient(135deg, #fffbeb, #ffffff);
}

.summary-top {
  display: flex;
  gap: 30px;
  align-items: center;
}

.risk-score-box {
  text-align: center;
  min-width: 140px;
}

.score-label {
  color: var(--fire-muted);
  font-size: 13px;
  margin-bottom: 4px;
}

.score-value {
  font-size: 48px;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 8px;
}

.risk-critical .score-value {
  color: var(--fire-red);
}

.risk-high .score-value {
  color: var(--fire-orange);
}

.risk-medium .score-value {
  color: #f59e0b;
}

.risk-tag {
  font-size: 14px;
}

.summary-info {
  flex: 1;
}

.summary-info h3 {
  margin: 0 0 8px;
  font-size: 18px;
}

.explanation {
  color: var(--fire-muted);
  margin: 0 0 16px;
  line-height: 1.6;
}

.stat-row {
  display: flex;
  gap: 30px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  color: var(--fire-muted);
  font-size: 12px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
}

.stat-value.danger {
  color: var(--fire-red);
}

.result-tabs {
  margin-top: 16px;
}

.sub-card {
  margin-bottom: 16px;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-item {
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}

.source-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.source-name {
  font-weight: 600;
}

.source-hazards {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hazard-tag {
  margin-right: 0;
}

.hazard-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hazard-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}

.hazard-index {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--fire-blue);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
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
  line-height: 1.5;
}

.score-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-item-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.score-item-name {
  font-weight: 500;
}

.score-item-value {
  font-weight: 700;
  color: var(--fire-blue);
}

.recommendations {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.recommendation-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  background: #f8fafc;
  border-radius: 10px;
}

.rec-priority {
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

.rag-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rag-item {
  padding: 14px;
  background: #f8fafc;
  border-radius: 10px;
}

.rag-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 8px;
}

.rag-summary {
  color: var(--fire-muted);
  font-size: 13px;
  line-height: 1.6;
  margin: 0 0 8px;
}

.rag-tags {
  display: flex;
  gap: 6px;
}
</style>
