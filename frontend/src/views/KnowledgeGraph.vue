<template>
  <div class="kg-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">知识图谱</h2>
        <p class="page-desc">
          业务实体图谱由业务表现算（建筑 / 楼层 / 设备 / 告警 / 工单 / 巡检 / 隐患类型 / 知识条目），
          学习知识图谱来自题库与课程数据；点击任意节点可下钻查看它的邻居
        </p>
      </div>
      <el-button :loading="loading" @click="reload">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar">
        <el-radio-group v-model="graphKind" @change="reload">
          <el-radio-button value="business">业务实体图谱</el-radio-button>
          <el-radio-button value="learning">学习知识图谱</el-radio-button>
        </el-radio-group>

        <template v-if="graphKind === 'business'">
          <el-select
            v-model="centerEntity"
            placeholder="以某个实体为中心（可选）"
            style="width: 260px"
            clearable
            filterable
            remote
            :remote-method="searchEntities"
            :loading="searching"
            @change="onCenterChange"
          >
            <el-option
              v-for="item in searchResults"
              :key="item.id"
              :label="`${item.typeLabel} · ${item.label}`"
              :value="item.id"
            />
          </el-select>
          <el-select v-model="depth" style="width: 130px" @change="loadBusinessGraph">
            <el-option label="1 度邻居" :value="1" />
            <el-option label="2 度邻居" :value="2" />
            <el-option label="3 度邻居" :value="3" />
          </el-select>
          <el-button v-if="centerEntity" @click="clearCenter">看全图</el-button>
          <span class="toolbar-hint">{{ businessHint }}</span>
        </template>

        <template v-else>
          <el-select v-model="learningQuestionLimit" style="width: 160px" @change="loadLearningGraph">
            <el-option label="题目节点 20" :value="20" />
            <el-option label="题目节点 50" :value="50" />
            <el-option label="题目节点 80" :value="80" />
          </el-select>
          <span class="toolbar-hint">节点与关系来自 quiz_bank.json / courses.json</span>
        </template>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="selectedNode ? 17 : 24">
        <el-card class="graph-card" shadow="never">
          <div v-if="!nodes.length" class="graph-empty">
            <el-empty :description="emptyText" />
          </div>
          <EChart v-else :option="chartOption" height="620px" @click="onChartClick" />
        </el-card>
      </el-col>

      <el-col v-if="selectedNode" :span="7">
        <el-card class="detail-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>节点详情</span>
              <el-button text @click="selectedNode = null">关闭</el-button>
            </div>
          </template>

          <div class="detail-type">{{ selectedNode.typeLabel }}</div>
          <div class="detail-label">{{ selectedNode.name }}</div>

          <div class="detail-rows">
            <div v-for="row in detailRows" :key="row.label" class="detail-row">
              <span class="row-label">{{ row.label }}</span>
              <span class="row-value">{{ row.value }}</span>
            </div>
          </div>

          <div class="detail-section-title">关联关系（{{ relatedEdges.length }}）</div>
          <div class="relation-list">
            <div v-for="(edge, index) in relatedEdges" :key="index" class="relation-item">
              <el-tag size="small" effect="plain">{{ edge.relationLabel }}</el-tag>
              <span class="relation-target">{{ edge.otherLabel }}</span>
              <span class="relation-direction">{{ edge.direction }}</span>
            </div>
            <el-empty v-if="!relatedEdges.length" description="该节点在当前图中没有连边" :image-size="50" />
          </div>

          <el-button
            v-if="graphKind === 'business' && selectedNode"
            type="primary"
            style="width: 100%; margin-top: 12px"
            @click="drillTo(selectedNode)"
          >
            以此节点为中心下钻
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="stat-card" shadow="never">
      <div class="stat-header">
        <span>当前图统计</span>
        <span class="stat-total">节点 {{ nodes.length }} · 关系 {{ edges.length }}</span>
      </div>
      <div class="stat-tags">
        <el-tag v-for="(count, type) in nodeCounts" :key="type" size="small" effect="plain">
          {{ typeLabels[type] || type }} {{ count }}
        </el-tag>
      </div>
      <div v-if="overviewTags.length" class="stat-note">
        <div>本租户全量概览：{{ overviewTags.join(' · ') }}</div>
      </div>
      <div v-if="sources.length" class="stat-note">
        <div v-for="(item, index) in sources" :key="index">· {{ item }}</div>
      </div>
      <div v-if="truncatedNote" class="stat-note warn">{{ truncatedNote }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import EChart from '../components/EChart.vue'
import { kgGraph, kgOverview, kgSearch, kgSubgraph, learningKnowledgeGraph } from '../api/knowledgeGraph'

// 节点类型配色：业务图与学习图各一套，图例与节点色同源
const TYPE_COLORS = {
  building: '#3b82f6',
  floor: '#60a5fa',
  device: '#22c55e',
  alert: '#ef4444',
  workorder: '#f59e0b',
  inspection: '#8b5cf6',
  hazard: '#ec4899',
  knowledge: '#0ea5e9',
  资格方向: '#2563eb',
  等级: '#0ea5e9',
  模块: '#22c55e',
  知识点: '#f59e0b',
  题目: '#8b5cf6',
  课程: '#ec4899',
}

const TYPE_SIZES = {
  building: 46,
  floor: 32,
  device: 20,
  workorder: 20,
  inspection: 18,
  hazard: 26,
  knowledge: 22,
}

const graphKind = ref('business')
const loading = ref(false)
const searching = ref(false)
const depth = ref(1)
const centerEntity = ref('')
const searchResults = ref([])
const learningQuestionLimit = ref(50)

const nodes = ref([])
const edges = ref([])
const typeLabels = ref({})
const nodeCounts = ref({})
const overviewCounts = ref({})
const sources = ref([])
const truncated = ref({})
const selectedNode = ref(null)

const businessHint = '整图默认取最近 40 条告警 / 工单 / 巡检记录，点节点可下钻'

const emptyText = computed(() =>
  graphKind.value === 'business'
    ? '当前范围内没有可展示的实体（先录入建筑、设备与巡检数据）'
    : '学习数据为空，请先导入题库与课程'
)

// 「本租户全量概览」只说明规模，不代表当前这张图里渲染了多少节点
const overviewTags = computed(() =>
  Object.entries(overviewCounts.value)
    .filter(([, count]) => count > 0)
    .map(([type, count]) => `${typeLabels.value[type] || type} ${count}`)
)

const truncatedNote = computed(() => {
  if (graphKind.value !== 'business') return ''
  const hit = Object.entries(truncated.value || {}).filter(([, value]) => value)
  if (!hit.length) return ''
  return `注意：${hit.map(([key]) => key).join(' / ')} 已达到上限被截断，可用搜索 + 下钻查看更多`
})

const detailRows = computed(() => {
  const node = selectedNode.value
  if (!node) return []
  const rows = Object.entries(node.raw || {})
    .filter(([key]) => !['id', 'label', 'type'].includes(key) && key !== 'name')
    .map(([key, value]) => ({ label: key, value: formatValue(value) }))
  return rows.length ? rows : [{ label: '说明', value: '该节点没有附加属性' }]
})

const relatedEdges = computed(() => {
  const node = selectedNode.value
  if (!node) return []
  const byId = new Map(nodes.value.map(item => [item.id, item]))
  return edges.value
    .filter(edge => edge.source === node.id || edge.target === node.id)
    .map(edge => {
      const outgoing = edge.source === node.id
      const otherId = outgoing ? edge.target : edge.source
      return {
        relationLabel: edge.relationLabel || edge.relation,
        otherLabel: byId.get(otherId)?.name || otherId,
        direction: outgoing ? '→ 指向' : '← 来自',
      }
    })
})

const chartOption = computed(() => {
  const categories = [...new Set(nodes.value.map(node => node.typeLabel))]
  const categoryIndex = Object.fromEntries(categories.map((name, index) => [name, index]))
  return {
    tooltip: {
      formatter: params => {
        if (params.dataType === 'edge') {
          return `${params.data.relationLabel}<br/>${params.data.sourceName} → ${params.data.targetName}`
        }
        return `<b>${params.data.name}</b><br/>${params.data.typeLabel}`
      },
    },
    legend: [{ data: categories, top: 0, type: 'scroll' }],
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        top: 30,
        categories: categories.map(name => ({ name })),
        force: { repulsion: 260, edgeLength: [70, 150], gravity: 0.06 },
        label: { show: true, position: 'right', fontSize: 11, formatter: '{b}' },
        labelLayout: { hideOverlap: true },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
        lineStyle: { color: 'source', curveness: 0.08, opacity: 0.55 },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 6,
        data: nodes.value.map(node => ({
          id: node.id,
          name: node.name,
          typeLabel: node.typeLabel,
          category: categoryIndex[node.typeLabel],
          symbolSize: node.size,
          itemStyle: { color: TYPE_COLORS[node.type] || '#94a3b8' },
        })),
        links: edges.value.map(edge => ({
          source: edge.source,
          target: edge.target,
          relationLabel: edge.relationLabel || edge.relation,
          sourceName: edge.sourceName || '',
          targetName: edge.targetName || '',
        })),
      },
    ],
  }
})

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** 生成唯一显示名：同名节点加后缀，避免 ECharts 把两个节点认成一个 */
function uniqueNames(items) {
  const used = new Map()
  return items.map(item => {
    const base = item.label || item.id
    const seen = used.get(base) || 0
    used.set(base, seen + 1)
    return { ...item, name: seen === 0 ? base : `${base} (${item.id})` }
  })
}

function buildBusinessGraph(data) {
  const labels = data.node_types || {}
  typeLabels.value = Object.fromEntries(Object.entries(labels).map(([key, value]) => [key, value.label]))
  const rawNodes = uniqueNames(data.nodes || []).map(node => ({
    id: node.id,
    name: node.name,
    type: node.type,
    typeLabel: labels[node.type]?.label || node.type,
    size: node.type === 'alert' && node.severity === 'critical'
      ? 26
      : TYPE_SIZES[node.type] || 20,
    raw: node,
  }))
  const byId = new Map(rawNodes.map(node => [node.id, node]))
  const rawEdges = (data.edges || []).map(edge => ({
    source: edge.source,
    target: edge.target,
    relation: edge.relation,
    relationLabel: edge.relationLabel || edge.relation,
    sourceName: byId.get(edge.source)?.name || edge.source,
    targetName: byId.get(edge.target)?.name || edge.target,
  }))
  nodes.value = rawNodes
  edges.value = rawEdges
  nodeCounts.value = data.counts || {}
  truncated.value = data.truncated || {}
}

function buildLearningGraph(data) {
  typeLabels.value = {}
  const rawNodes = uniqueNames(data.nodes || []).map(node => ({
    id: node.id,
    name: node.name,
    type: node.type,
    typeLabel: node.type,
    size: 16 + Math.min(20, Math.sqrt(node.count || 1) * 4),
    raw: node,
  }))
  const byId = new Map(rawNodes.map(node => [node.id, node]))
  nodes.value = rawNodes
  edges.value = (data.edges || []).map(edge => ({
    source: edge.source,
    target: edge.target,
    relation: edge.relation,
    relationLabel: edge.relation,
    sourceName: byId.get(edge.source)?.name || edge.source,
    targetName: byId.get(edge.target)?.name || edge.target,
  }))
  nodeCounts.value = rawNodes.reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1
    return acc
  }, {})
  overviewCounts.value = {}
  truncated.value = {}
  sources.value = [
    `本次渲染的题目节点上限：${learningQuestionLimit.value}`,
    '数据来源：backend/data/learning/quiz_bank.json 与 courses.json',
  ]
}

async function loadBusinessGraph() {
  if (centerEntity.value) {
    const [entityType, ...rest] = String(centerEntity.value).split(':')
    const resp = await kgSubgraph({
      entity_type: entityType,
      entity_id: rest.join(':'),
      depth: depth.value,
    })
    buildBusinessGraph(resp.data)
  } else {
    // 整图默认限量，避免一上来就渲染上千个节点；需要更多就用搜索 + 下钻
    const resp = await kgGraph({ alerts: 40, workorders: 40, inspections: 40 })
    buildBusinessGraph(resp.data)
  }
}

async function loadLearningGraph() {
  const resp = await learningKnowledgeGraph({ limit_questions: learningQuestionLimit.value })
  buildLearningGraph(resp.data)
}

async function loadOverview() {
  const resp = await kgOverview()
  const data = resp.data || {}
  overviewCounts.value = data.node_counts || {}
  sources.value = data.sources || []
  // 刻意不动 nodeCounts：那一行标签描述的是**当前这张图**渲染了什么，
  // 而 overview 的口径是全量（上限也不同），混在一起会自相矛盾
}

async function reload() {
  loading.value = true
  selectedNode.value = null
  try {
    if (graphKind.value === 'business') {
      await Promise.all([loadBusinessGraph(), loadOverview()])
    } else {
      await loadLearningGraph()
    }
  } catch (e) {
    // 失败原因由请求拦截器统一提示
  } finally {
    loading.value = false
  }
}

async function searchEntities(keyword) {
  if (!keyword) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    const resp = await kgSearch({ keyword })
    searchResults.value = resp.data?.items || []
  } catch (e) {
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

function onChartClick(params) {
  if (params.dataType !== 'node') return
  selectedNode.value = nodes.value.find(node => node.name === params.name) || null
}

// 搜索框选中一个实体后立即以它为中心取子图（清空时回到整图）
function onCenterChange() {
  selectedNode.value = null
  loadBusinessGraph()
}

function drillTo(node) {
  centerEntity.value = node.id
  loadBusinessGraph()
}

function clearCenter() {
  centerEntity.value = ''
  reload()
}

onMounted(reload)
</script>

<style scoped>
.kg-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
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
  max-width: 900px;
  line-height: 1.6;
}

.toolbar-card {
  margin-bottom: 14px;
  border-radius: 10px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-hint {
  font-size: 12px;
  color: #94a3b8;
}

.graph-card,
.detail-card,
.stat-card {
  border-radius: 10px;
  margin-bottom: 14px;
}

.graph-empty {
  padding: 60px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-type {
  font-size: 12px;
  color: #94a3b8;
}

.detail-label {
  font-size: 17px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 12px;
  word-break: break-all;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  padding: 4px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.row-label {
  color: #94a3b8;
  flex-shrink: 0;
}

.row-value {
  color: #334155;
  font-weight: 500;
  text-align: right;
  word-break: break-all;
}

.detail-section-title {
  margin: 14px 0 8px;
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}

.relation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 4px 0;
}

.relation-target {
  color: #334155;
  flex: 1;
  word-break: break-all;
}

.relation-direction {
  color: #94a3b8;
  flex-shrink: 0;
}

.stat-header {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #334155;
  font-weight: 600;
  margin-bottom: 10px;
}

.stat-total {
  font-weight: 400;
  color: #64748b;
}

.stat-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stat-note {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.8;
}

.stat-note.warn {
  color: #d97706;
}
</style>
