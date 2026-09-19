<template>
  <div class="hardware-page">
    <div class="hardware-hero">
      <div>
        <p class="eyebrow">多源感知 · 风险联动 · 闭环处置</p>
        <h1>硬件事件中心</h1>
        <p class="hero-desc">统一汇聚烟感、电气火灾探测、摄像头识别和设备离线等事件，进入风险研判与整改闭环流程。</p>
        <div class="hero-flow">
          <span>设备上报</span><i></i><span>风险研判</span><i></i><span>人工复核</span><i></i><span>整改闭环</span>
        </div>
      </div>
      <div class="hero-status">
        <span>当前态势</span>
        <strong>{{ situationText }}</strong>
        <el-progress :percentage="closedRate" :stroke-width="8" :show-text="false" />
        <p>闭环率 {{ closedRate }}%，高风险事件优先进入处置队列。</p>
      </div>
    </div>

    <div class="metric-grid">
      <div v-for="m in metrics" :key="m.label" class="metric-card" :class="m.className">
        <div class="metric-icon">{{ m.icon }}</div>
        <div>
          <span>{{ m.label }}</span>
          <strong>{{ m.value }}</strong>
          <p>{{ m.desc }}</p>
        </div>
      </div>
    </div>

    <el-row :gutter="16" class="content-row">
      <el-col :lg="10" :md="24" :sm="24">
        <el-card class="panel-card priority-card">
          <template #header>
            <div class="header-row">
              <strong>处置优先队列</strong>
              <el-tag type="danger" effect="plain">{{ priorityEvents.length }} 条需关注</el-tag>
            </div>
          </template>
          <div class="priority-list">
            <div v-for="event in priorityEvents" :key="event.id" class="priority-item" @click="openDetail(event)">
              <div class="priority-top">
                <div>
                  <strong>{{ event.event_name }}</strong>
                  <p>{{ event.location }} · {{ event.device_name }}</p>
                </div>
                <el-tag :type="riskTagType(event.risk_level)" effect="light">{{ event.risk_level }}</el-tag>
              </div>
              <p class="priority-desc">{{ event.description }}</p>
              <div class="priority-foot">
                <span>{{ shortTime(event.created_at) }}</span>
                <el-button link type="primary">查看研判</el-button>
              </div>
            </div>
            <el-empty v-if="!priorityEvents.length" description="暂无高优先级硬件事件" :image-size="90" />
          </div>
        </el-card>
      </el-col>

      <el-col :lg="14" :md="24" :sm="24">
        <el-card class="panel-card">
          <template #header>
            <div class="header-row">
              <strong>事件态势分布</strong>
              <el-button type="primary" @click="newEvent">新增事件</el-button>
            </div>
          </template>
          <div class="type-grid">
            <div v-for="item in eventTypeStats" :key="item.type" class="type-item">
              <div class="type-top"><span>{{ item.name }}</span><strong>{{ item.count }}</strong></div>
              <el-progress :percentage="item.percent" :stroke-width="9" :show-text="false" />
              <p>{{ item.description }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="panel-card table-card">
      <template #header>
        <div class="header-row table-header">
          <div>
            <strong>硬件事件列表</strong>
            <p>按风险等级和处置状态筛选，快速定位需要处理的事件。</p>
          </div>
          <div class="filter-actions">
            <el-select v-model="eventTypeFilter" clearable placeholder="事件类型" @change="loadEvents">
              <el-option v-for="t in eventTypes" :key="t.type" :label="t.name" :value="t.type" />
            </el-select>
            <el-select v-model="statusFilter" clearable placeholder="状态" @change="loadEvents">
              <el-option label="待处理" value="待处理" />
              <el-option label="处理中" value="处理中" />
              <el-option label="已闭环" value="已闭环" />
            </el-select>
            <el-button @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="events" class="event-table" row-key="id">
        <el-table-column label="事件" min-width="260">
          <template #default="{ row }">
            <div class="event-cell">
              <div class="event-icon" :class="riskClass(row.risk_level)">{{ eventIcon(row.event_type) }}</div>
              <div>
                <strong>{{ row.event_name }}</strong>
                <p>{{ row.description }}</p>
                <span>{{ shortTime(row.created_at) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="位置 / 设备" min-width="190">
          <template #default="{ row }">
            <div class="muted-main">{{ row.location }}</div>
            <div class="muted-sub">{{ row.device_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="110">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.risk_level)" effect="light">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处置建议" min-width="220">
          <template #default="{ row }">
            <span class="suggestion-text">{{ row.analysis?.suggested_action || '建议完成现场复核后进入闭环处置。' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
            <el-button size="small" type="primary" plain @click="updateStatus(row, '处理中')" :disabled="row.status !== '待处理'">处理</el-button>
            <el-button size="small" type="success" plain @click="updateStatus(row, '已闭环')" :disabled="row.status === '已闭环'">闭环</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="硬件事件研判详情" size="54%">
      <div v-if="current.id" class="detail-drawer">
        <div class="detail-head" :class="riskClass(current.risk_level)">
          <div>
            <span>{{ current.event_name }}</span>
            <h2>{{ current.location }}</h2>
            <p>{{ current.description }}</p>
          </div>
          <el-tag :type="riskTagType(current.risk_level)" effect="dark">{{ current.risk_level }}</el-tag>
        </div>

        <div class="detail-grid">
          <div><span>设备</span><strong>{{ current.device_name }}</strong></div>
          <div><span>状态</span><strong>{{ current.status }}</strong></div>
          <div><span>风险分</span><strong>{{ current.risk_score || 0 }}</strong></div>
          <div><span>上报时间</span><strong>{{ current.created_at }}</strong></div>
        </div>

        <el-card class="mini-card">
          <template #header><strong>Agent 风险研判</strong></template>
          <p class="analysis-summary">{{ current.analysis?.agent_summary || '系统已完成基础风险研判。' }}</p>
          <div class="hazard-tags">
            <el-tag v-for="h in current.analysis?.hazards || []" :key="h" type="warning" effect="plain">{{ h }}</el-tag>
          </div>
        </el-card>

        <el-card class="mini-card">
          <template #header><strong>处置路径</strong></template>
          <div class="process-line">
            <div :class="{active:true}"><span>1</span><p>确认报警</p></div>
            <div :class="{active: current.status !== '待处理'}"><span>2</span><p>现场复核</p></div>
            <div :class="{active: current.status === '已闭环'}"><span>3</span><p>整改闭环</p></div>
          </div>
          <p class="process-tip">{{ current.analysis?.suggested_action || '建议根据风险等级安排现场复核和整改复查。' }}</p>
        </el-card>

        <el-card class="mini-card">
          <template #header><strong>决策项</strong></template>
          <el-table :data="current.analysis?.decision_policy?.decision_items || []" border>
            <el-table-column prop="label" label="检查项" />
            <el-table-column label="是否触发" width="120">
              <template #default="{ row }">
                <el-tag :type="row.value ? 'danger' : 'success'">{{ row.value ? '已触发' : '未触发' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </el-drawer>

    <el-dialog v-model="dialogVisible" title="新增硬件事件" width="640px">
      <el-form label-width="90px">
        <el-form-item label="事件类型">
          <el-select v-model="form.event_type" style="width:100%">
            <el-option v-for="t in eventTypes" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置"><el-input v-model="form.location" placeholder="例如：机房B区 / 实验室A区" /></el-form-item>
        <el-form-item label="设备编号"><el-input v-model="form.device_id" placeholder="例如：SMK-001" /></el-form-item>
        <el-form-item label="设备名称"><el-input v-model="form.device_name" placeholder="例如：机房烟感" /></el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="form.risk_level" style="width:100%">
            <el-option label="低风险" value="低风险" />
            <el-option label="中风险" value="中风险" />
            <el-option label="高风险" value="高风险" />
            <el-option label="严重风险" value="严重风险" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险评分"><el-input-number v-model="form.risk_score" :min="0" :max="100" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" rows="5" placeholder="描述报警原因、现场现象或设备异常情况" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" @click="saveEvent">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import request from "../api"
import { riskTagType } from "../utils/riskStyle"

const dashboard = ref({})
const events = ref([])
const eventTypes = ref([])
const statusFilter = ref("")
const eventTypeFilter = ref("")
const drawerVisible = ref(false)
const dialogVisible = ref(false)
const current = ref({})
const form = ref({ event_type: "manual_report", location: "", device_id: "", device_name: "", risk_level: "中风险", risk_score: 45, description: "" })

const closedRate = computed(() => {
  const total = Number(dashboard.value.total || 0)
  return total ? Math.round((Number(dashboard.value.closed || 0) / total) * 100) : 0
})
const situationText = computed(() => {
  const risk = Number(dashboard.value.high || 0) + Number(dashboard.value.serious || 0)
  return risk > 0 ? `${risk} 条风险事件需优先关注` : "当前硬件态势平稳"
})
const metrics = computed(() => [
  { label: "事件总数", value: dashboard.value.total || 0, desc: "已接入硬件上报", icon: "📡", className: "blue" },
  { label: "待处理", value: dashboard.value.pending || 0, desc: "等待确认与派发", icon: "⏱", className: "orange" },
  { label: "处理中", value: dashboard.value.processing || 0, desc: "正在现场复核", icon: "🛠", className: "blue" },
  { label: "已闭环", value: dashboard.value.closed || 0, desc: "完成处置归档", icon: "", className: "green" },
  { label: "高风险", value: dashboard.value.high || 0, desc: "需要优先处置", icon: "⚠️", className: "red" },
  { label: "严重风险", value: dashboard.value.serious || 0, desc: "建议立即响应", icon: "", className: "darkred" },
])
const priorityEvents = computed(() => events.value.filter(e => e.status !== "已闭环" && (String(e.risk_level).includes("高") || String(e.risk_level).includes("严重"))).slice(0, 5))
const eventTypeStats = computed(() => {
  const total = events.value.length || 1
  return eventTypes.value.map(t => {
    const count = events.value.filter(e => e.event_type === t.type).length
    return { ...t, count, percent: Math.round(count / total * 100) }
  })
})

const load = async () => {
  eventTypes.value = (await request.get("/api/hardware/event-types", { silentError: true })).data
  dashboard.value = (await request.get("/api/hardware/events-dashboard", { silentError: true })).data
  await loadEvents()
}

const loadEvents = async () => {
  events.value = (await request.get("/api/hardware/events", {
    params: { status: statusFilter.value || "", event_type: eventTypeFilter.value || "" },
    silentError: true
  })).data
}

const openDetail = row => { current.value = row; drawerVisible.value = true }
const updateStatus = async (row, status) => { await request.post(`/api/hardware/events/${row.id}/status`, { status }); ElMessage.success("状态已更新"); await load() }
const newEvent = () => { form.value = { event_type: "manual_report", location: "", device_id: "", device_name: "", risk_level: "中风险", risk_score: 45, description: "" }; dialogVisible.value = true }
const saveEvent = async () => { await request.post("/api/hardware/events", form.value); ElMessage.success("事件已创建"); dialogVisible.value = false; await load() }
const shortTime = t => String(t || "").slice(5, 16)
const eventIcon = type => ({ smoke_alarm: "烟", temperature_alarm: "温", electrical_alarm: "电", camera_snapshot: "视", device_offline: "离", manual_report: "报" }[type] || "事")
const riskClass = level => String(level || "").includes("严重") ? "serious" : String(level || "").includes("高") ? "high" : String(level || "").includes("中") ? "medium" : "low"
const statusType = status => status === "已闭环" ? "success" : status === "处理中" ? "primary" : "warning"

onMounted(load)
</script>

<style scoped>
.hardware-page { display:flex; flex-direction:column; gap:16px; }
.hardware-hero { display:flex; justify-content:space-between; gap:22px; align-items:stretch; background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 58%,#2563eb 100%); color:#fff; border-radius:24px; padding:26px; box-shadow:0 18px 40px rgba(30,58,138,.18); }
.eyebrow { margin:0 0 8px; color:#bfdbfe; font-weight:700; letter-spacing:.4px; }
.hardware-hero h1 { margin:0; font-size:30px; letter-spacing:.5px; }
.hero-desc { max-width:760px; margin:10px 0 18px; color:#dbeafe; line-height:1.75; }
.hero-flow { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
.hero-flow span { background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18); padding:7px 12px; border-radius:999px; font-size:13px; }
.hero-flow i { width:22px; height:1px; background:rgba(255,255,255,.45); }
.hero-status { width:300px; flex-shrink:0; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18); border-radius:20px; padding:18px; backdrop-filter: blur(4px); }
.hero-status span { color:#bfdbfe; font-size:13px; }
.hero-status strong { display:block; font-size:24px; margin:8px 0 12px; }
.hero-status p { color:#dbeafe; margin:12px 0 0; line-height:1.6; }
.metric-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:12px; }
.metric-card { background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:16px; display:flex; gap:12px; align-items:center; box-shadow:0 10px 24px rgba(15,23,42,.045); position:relative; overflow:hidden; }
.metric-card:before { content:""; position:absolute; inset:0 auto 0 0; width:4px; background:#2563eb; }
.metric-card.orange:before { background:#f59e0b; } .metric-card.green:before { background:#22c55e; } .metric-card.red:before { background:#ef4444; } .metric-card.darkred:before { background:#991b1b; }
.metric-icon { width:40px; height:40px; border-radius:14px; display:flex; align-items:center; justify-content:center; background:#eff6ff; font-weight:800; }
.metric-card.orange .metric-icon { background:#fff7ed; } .metric-card.green .metric-icon { background:#f0fdf4; } .metric-card.red .metric-icon, .metric-card.darkred .metric-icon { background:#fef2f2; }
.metric-card span { display:block; color:#64748b; font-size:13px; }
.metric-card strong { display:block; font-size:28px; margin:3px 0; color:#0f172a; }
.metric-card p { margin:0; color:#94a3b8; font-size:12px; }
.content-row { align-items:stretch; }
.panel-card { height:100%; }
.header-row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.priority-list { max-height:330px; overflow:auto; padding-right:4px; display:flex; flex-direction:column; gap:10px; }
.priority-item { border:1px solid #e2e8f0; border-radius:16px; padding:14px; background:linear-gradient(180deg,#fff,#f8fafc); cursor:pointer; transition:.18s; }
.priority-item:hover { transform:translateY(-2px); box-shadow:0 10px 22px rgba(15,23,42,.08); }
.priority-top, .priority-foot { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.priority-top strong { font-size:15px; }
.priority-top p, .priority-desc, .priority-foot span { color:#64748b; margin:4px 0 0; line-height:1.55; }
.priority-desc { margin:10px 0; }
.type-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.type-item { border:1px solid #e2e8f0; border-radius:16px; padding:14px; background:#fff; }
.type-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.type-top span { color:#475569; font-weight:700; }
.type-top strong { font-size:22px; color:#2563eb; }
.type-item p { margin:10px 0 0; color:#94a3b8; font-size:12px; line-height:1.5; }
.table-header p { color:#64748b; margin:6px 0 0; font-size:13px; font-weight:400; }
.filter-actions { display:flex; gap:8px; align-items:center; }
.filter-actions .el-select { width:150px; }
.event-cell { display:flex; gap:12px; align-items:flex-start; }
.event-icon { width:40px; height:40px; border-radius:14px; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-weight:800; }
.event-icon.low { background:#f0fdf4; color:#16a34a; } .event-icon.medium { background:#fff7ed; color:#d97706; } .event-icon.high { background:#fef2f2; color:#dc2626; } .event-icon.serious { background:#7f1d1d; color:white; }
.event-cell strong, .muted-main { color:#0f172a; font-weight:700; }
.event-cell p { color:#475569; margin:4px 0; line-height:1.5; }
.event-cell span, .muted-sub { color:#94a3b8; font-size:12px; }
.suggestion-text { color:#475569; line-height:1.55; }
.detail-drawer { display:flex; flex-direction:column; gap:14px; }
.detail-head { border-radius:20px; padding:20px; color:#fff; background:linear-gradient(135deg,#2563eb,#60a5fa); display:flex; justify-content:space-between; gap:16px; }
.detail-head.medium { background:linear-gradient(135deg,#f59e0b,#fbbf24); } .detail-head.high { background:linear-gradient(135deg,#ef4444,#fb7185); } .detail-head.serious { background:linear-gradient(135deg,#7f1d1d,#ef4444); } .detail-head.low { background:linear-gradient(135deg,#16a34a,#4ade80); }
.detail-head span { opacity:.85; } .detail-head h2 { margin:6px 0; } .detail-head p { margin:0; line-height:1.6; }
.detail-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
.detail-grid div { background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:12px; }
.detail-grid span { display:block; color:#64748b; font-size:12px; margin-bottom:6px; }
.detail-grid strong { color:#0f172a; font-size:14px; }
.mini-card { border-radius:16px; }
.analysis-summary { color:#475569; line-height:1.75; margin:0 0 12px; }
.hazard-tags { display:flex; flex-wrap:wrap; gap:8px; }
.process-line { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.process-line div { border:1px solid #e2e8f0; border-radius:16px; padding:12px; text-align:center; background:#f8fafc; }
.process-line div.active { border-color:#93c5fd; background:#eff6ff; }
.process-line span { width:28px; height:28px; display:inline-flex; align-items:center; justify-content:center; border-radius:50%; background:#2563eb; color:#fff; font-weight:800; }
.process-line p { margin:8px 0 0; color:#475569; }
.process-tip { color:#64748b; line-height:1.7; }
@media (max-width:1200px) { .metric-grid { grid-template-columns:repeat(3,1fr); } .hardware-hero { flex-direction:column; } .hero-status { width:auto; } }
@media (max-width:760px) { .metric-grid, .type-grid, .detail-grid { grid-template-columns:1fr; } .filter-actions { flex-wrap:wrap; } .hardware-hero { padding:18px; } }
</style>
