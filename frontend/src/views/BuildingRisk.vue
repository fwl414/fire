<template>
  <div class="building-risk-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">建筑火灾风险预测</h2>
        <p class="page-desc">
          基于历史告警/工单/巡检/设备数据训练的逻辑回归模型，预测每栋建筑在
          <strong>未来 {{ windowDays }} 天</strong>出现严重告警或告警升级的概率
        </p>
      </div>
      <div class="header-actions">
        <el-button :loading="loading" @click="loadAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button
          type="primary"
          :loading="training"
          :disabled="!canTrain"
          @click="trainModel"
        >
          <el-icon><MagicStick /></el-icon>
          {{ model.trained ? '重新训练模型' : '训练模型' }}
        </el-button>
      </div>
    </div>

    <!-- 模型状态：有没有模型、指标如何，全部摆出来；没训练就不给任何预测分数 -->
    <el-card class="model-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>模型状态</span>
          <el-tag :type="model.trained ? 'success' : 'info'" size="small" effect="dark">
            {{ model.trained ? '已训练' : '尚未训练' }}
          </el-tag>
        </div>
      </template>

      <el-alert
        v-if="!model.trained"
        type="warning"
        :closable="false"
        show-icon
        :title="model.message || '模型尚未训练'"
        description="未训练时本页不展示任何预测分数。训练需要至少 40 条样本（建筑数 × 观测周数），样本不足接口会直接拒绝并说明原因。"
      />

      <template v-else>
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="训练时间">{{ formatTime(model.trained_at) }}</el-descriptions-item>
          <el-descriptions-item label="训练 / 回测样本">
            {{ metrics.train_samples ?? '--' }} / {{ metrics.test_samples ?? '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="正样本占比">
            {{ metrics.base_rate != null ? (metrics.base_rate * 100).toFixed(1) + '%' : '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="回测 AUC">
            {{ metrics.roc_auc != null ? metrics.roc_auc.toFixed(3) : '样本单一，无法计算' }}
          </el-descriptions-item>
          <el-descriptions-item label="精确率">{{ formatRate(metrics.precision) }}</el-descriptions-item>
          <el-descriptions-item label="召回率">{{ formatRate(metrics.recall) }}</el-descriptions-item>
          <el-descriptions-item label="准确率">{{ formatRate(metrics.accuracy) }}</el-descriptions-item>
          <el-descriptions-item label="Brier 分数">
            {{ metrics.brier != null ? metrics.brier.toFixed(3) : '--' }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="model-note">
          <div><span class="note-label">标签定义：</span>{{ model.label_definition }}</div>
          <div v-if="model.limitations?.length">
            <span class="note-label">已知局限：</span>
            <ul class="limitation-list">
              <li v-for="(item, idx) in model.limitations" :key="idx">{{ item }}</li>
            </ul>
          </div>
        </div>
      </template>
    </el-card>

    <el-row v-if="model.trained" :gutter="16" class="stat-row">
      <el-col v-for="band in bands" :key="band.key" :span="6">
        <el-card class="stat-card" :class="band.key" shadow="hover">
          <div class="stat-icon">{{ band.icon }}</div>
          <div class="stat-content">
            <div class="stat-value">{{ band.count }}</div>
            <div class="stat-label">{{ band.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="model.trained" :gutter="16">
      <el-col :span="selectedBuilding ? 16 : 24">
        <el-card class="main-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>建筑预测结果（按概率倒序）</span>
              <el-select v-model="filterLevel" placeholder="预测等级筛选" style="width: 150px" clearable>
                <el-option label="严重风险" value="严重风险" />
                <el-option label="高风险" value="高风险" />
                <el-option label="中风险" value="中风险" />
                <el-option label="低风险" value="低风险" />
              </el-select>
            </div>
          </template>

          <div v-if="filteredBuildings.length" class="building-grid">
            <div
              v-for="building in filteredBuildings"
              :key="building.buildingId"
              class="building-card"
              :class="levelClass(building.predictedLevel)"
              @click="selectBuilding(building)"
            >
              <div class="building-header">
                <span class="building-name">{{ building.buildingName }}</span>
                <el-tag :type="levelTagType(building.predictedLevel)" size="small">
                  {{ building.predictedLevel }}
                </el-tag>
              </div>
              <div class="building-score">
                <div class="score-circle" :class="levelClass(building.predictedLevel)">
                  <span class="score-num">{{ Math.round(building.probability * 100) }}%</span>
                  <span class="score-label">预测概率</span>
                </div>
                <div class="rule-score">
                  <span class="rule-score-label">规则分（现行口径）</span>
                  <span class="rule-score-value">{{ building.ruleScore ?? '--' }}</span>
                </div>
              </div>
              <div class="building-info">
                <div class="info-item">
                  <span class="info-label">近{{ windowDays }}天告警</span>
                  <span class="info-value">{{ value(building, 'alerts_7d') }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">未闭环工单</span>
                  <span class="info-value">{{ value(building, 'open_tickets') }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">逾期工单</span>
                  <span class="info-value">{{ value(building, 'overdue_tickets') }}</span>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else description="当前筛选条件下没有建筑" />
        </el-card>
      </el-col>

      <el-col v-if="selectedBuilding" :span="8">
        <el-card class="side-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>{{ selectedBuilding.buildingName }} 预测详情</span>
              <el-button text @click="selectedBuilding = null">关闭</el-button>
            </div>
          </template>

          <div class="detail-section">
            <div class="detail-score-box" :class="levelClass(selectedBuilding.predictedLevel)">
              <div class="detail-score">{{ Math.round(selectedBuilding.probability * 100) }}%</div>
              <div class="detail-level">{{ selectedBuilding.predictedLevel }}</div>
              <div class="detail-update">
                未来 {{ windowDays }} 天出现严重告警的概率
              </div>
            </div>
          </div>

          <div class="detail-section">
            <h4>因子贡献（logit 贡献，正=推高概率）</h4>
            <div class="factor-list">
              <div v-for="factor in selectedBuilding.topFactors" :key="factor.name" class="factor-item">
                <div class="factor-header">
                  <span class="factor-name">{{ factor.label }}</span>
                  <span class="factor-score">
                    值 {{ factor.value }} / 贡献 {{ factor.contribution > 0 ? '+' : '' }}{{ factor.contribution }}
                  </span>
                </div>
                <div class="factor-bar-bg">
                  <div
                    class="factor-bar"
                    :class="factor.contribution > 0 ? 'factor-up' : 'factor-down'"
                    :style="{ width: factorWidth(factor.contribution) }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <h4>模型输入特征（观测窗口实测值）</h4>
            <div class="feature-list">
              <div v-for="item in featureRows" :key="item.name" class="feature-row">
                <span class="feature-name">{{ item.label }}</span>
                <span class="feature-value">{{ item.value }}</span>
              </div>
            </div>
          </div>

          <div class="detail-actions">
            <el-button type="primary" style="width: 100%" @click="goBuildingDetail">
              查看建筑详情
            </el-button>
            <el-button style="width: 100%" @click="goWorkorders">查看关联工单</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, MagicStick } from '@element-plus/icons-vue'
import { riskModelInfo, riskPredictions, trainRiskModel } from '../api/risk'
import { getCurrentUser, hasPermission } from '../auth'

const router = useRouter()

const loading = ref(false)
const training = ref(false)
const model = ref({ trained: false, features: [], message: '' })
const predictions = ref([])
const windowDays = ref(7)
const filterLevel = ref('')
const selectedBuilding = ref(null)

const canTrain = computed(() => hasPermission(getCurrentUser(), 'risk:model'))

const metrics = computed(() => model.value.metrics || {})

// 预测概率分档（与后端 risk_model_service.risk_band 保持一致）
const BANDS = [
  { key: 'critical', label: '严重风险（概率≥70%）', icon: '🔴', match: level => level === '严重风险' },
  { key: 'high', label: '高风险（45%~70%）', icon: '🟠', match: level => level === '高风险' },
  { key: 'medium', label: '中风险（20%~45%）', icon: '🟡', match: level => level === '中风险' },
  { key: 'low', label: '低风险（<20%）', icon: '🟢', match: level => level === '低风险' },
]

const bands = computed(() =>
  BANDS.map(band => ({
    ...band,
    count: predictions.value.filter(item => band.match(item.predictedLevel)).length,
  }))
)

const filteredBuildings = computed(() => {
  if (!filterLevel.value) return predictions.value
  return predictions.value.filter(item => item.predictedLevel === filterLevel.value)
})

const featureRows = computed(() => {
  const features = selectedBuilding.value?.features || {}
  const labels = Object.fromEntries((model.value.features || []).map(item => [item.name, item.label]))
  return Object.entries(features).map(([name, value]) => ({
    name,
    label: labels[name] || name,
    value,
  }))
})

function value(building, key) {
  const raw = building.features?.[key]
  if (raw == null) return '--'
  return Number.isInteger(raw) ? raw : Number(raw).toFixed(1)
}

function levelClass(level) {
  if (level === '严重风险') return 'critical'
  if (level === '高风险') return 'high'
  if (level === '中风险') return 'medium'
  return 'low'
}

function levelTagType(level) {
  if (level === '严重风险') return 'danger'
  if (level === '高风险') return 'warning'
  if (level === '中风险') return 'info'
  return 'success'
}

function factorWidth(contribution) {
  const max = Math.max(...(selectedBuilding.value?.topFactors || []).map(item => Math.abs(item.contribution)), 1)
  return `${Math.min(100, Math.abs(contribution) / max * 100)}%`
}

function formatRate(rate) {
  return rate == null ? '--' : `${(rate * 100).toFixed(1)}%`
}

function formatTime(text) {
  if (!text) return '--'
  return String(text).replace('T', ' ').slice(0, 19)
}

async function loadModel() {
  const res = await riskModelInfo()
  model.value = res.data || { trained: false }
  if (model.value.window_days) windowDays.value = model.value.window_days
}

async function loadPredictions() {
  const res = await riskPredictions()
  const data = res.data || {}
  model.value = { ...model.value, ...data }
  predictions.value = data.items || []
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadModel(), loadPredictions()])
  } catch (e) {
    // 失败原因由请求拦截器统一提示
  } finally {
    loading.value = false
  }
}

async function trainModel() {
  training.value = true
  try {
    const res = await trainRiskModel()
    const metricsText = res.data?.metrics?.roc_auc != null
      ? `，回测 AUC ${res.data.metrics.roc_auc.toFixed(3)}`
      : ''
    ElMessage.success(`模型已训练${metricsText}`)
    await loadAll()
  } catch (e) {
    // 样本不足等原因由拦截器提示（后端会带上具体说明）
  } finally {
    training.value = false
  }
}

function selectBuilding(building) {
  selectedBuilding.value = building
}

function goBuildingDetail() {
  router.push(`/building-detail/${selectedBuilding.value.buildingId}`)
}

function goWorkorders() {
  router.push(`/workorders?building_id=${selectedBuilding.value.buildingId}`)
}

onMounted(loadAll)
</script>

<style scoped>
.building-risk-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  color: #0f172a;
}

.page-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: #64748b;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.model-card {
  margin-bottom: 16px;
  border-radius: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.model-note {
  margin-top: 12px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.8;
}

.note-label {
  color: #334155;
  font-weight: 600;
}

.limitation-list {
  margin: 4px 0 0;
  padding-left: 18px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 10px;
  border-left: 4px solid #e2e8f0;
}

.stat-card.critical {
  border-left-color: #ef4444;
}

.stat-card.high {
  border-left-color: #f97316;
}

.stat-card.medium {
  border-left-color: #f59e0b;
}

.stat-card.low {
  border-left-color: #22c55e;
}

.stat-icon {
  font-size: 26px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.main-card,
.side-card {
  border-radius: 10px;
}

.building-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.building-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.building-card:hover {
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.building-card.critical {
  border-color: #fecaca;
}

.building-card.high {
  border-color: #fed7aa;
}

.building-card.medium {
  border-color: #fde68a;
}

.building-card.low {
  border-color: #bbf7d0;
}

.building-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.building-name {
  font-weight: 600;
  color: #0f172a;
}

.building-score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.score-circle {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.score-circle.critical {
  background: linear-gradient(135deg, #ef4444, #b91c1c);
}

.score-circle.high {
  background: linear-gradient(135deg, #f97316, #ea580c);
}

.score-circle.medium {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.score-circle.low {
  background: linear-gradient(135deg, #22c55e, #15803d);
}

.score-num {
  font-size: 20px;
  font-weight: 700;
}

.score-label {
  font-size: 11px;
  opacity: 0.9;
}

.rule-score {
  text-align: right;
  font-size: 12px;
  color: #64748b;
}

.rule-score-value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #334155;
}

.building-info {
  display: flex;
  justify-content: space-between;
  border-top: 1px dashed #e2e8f0;
  padding-top: 10px;
}

.info-item {
  text-align: center;
}

.info-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}

.detail-section {
  margin-bottom: 18px;
}

.detail-section h4 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #334155;
}

.detail-score-box {
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  color: #fff;
}

.detail-score-box.critical {
  background: linear-gradient(135deg, #ef4444, #b91c1c);
}

.detail-score-box.high {
  background: linear-gradient(135deg, #f97316, #ea580c);
}

.detail-score-box.medium {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.detail-score-box.low {
  background: linear-gradient(135deg, #22c55e, #15803d);
}

.detail-score {
  font-size: 30px;
  font-weight: 700;
}

.detail-level {
  font-size: 14px;
}

.detail-update {
  font-size: 11px;
  opacity: 0.9;
  margin-top: 4px;
}

.factor-item {
  margin-bottom: 12px;
}

.factor-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
}

.factor-bar-bg {
  height: 6px;
  border-radius: 4px;
  background: #f1f5f9;
  overflow: hidden;
}

.factor-bar {
  height: 100%;
  border-radius: 4px;
}

.factor-up {
  background: #ef4444;
}

.factor-down {
  background: #22c55e;
}

.feature-list {
  font-size: 12px;
}

.feature-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.feature-row:last-child {
  border-bottom: none;
}

.feature-name {
  color: #94a3b8;
}

.feature-value {
  color: #334155;
  font-weight: 600;
}

.detail-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
