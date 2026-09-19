<template>
  <div class="print-page">
    <div class="toolbar no-print">
      <el-button @click="goBack">返回</el-button>
      <el-select v-model="templateKey" style="width:180px" @change="load">
        <el-option v-for="t in templates" :key="t.key" :label="t.name" :value="t.key" />
      </el-select>
      <el-button @click="downloadMarkdown">导出 Markdown</el-button>
      <el-button @click="openVerify">报告验真</el-button>
      <el-button type="primary" @click="window.print()">打印 / 另存为 PDF</el-button>
    </div>

    <el-skeleton v-if="loading" animated class="paper" />

    <div v-else-if="detail.id" class="paper">
      <div class="cover">
        <div>
          <h1>消防安全巡检报告</h1>
          <p>消防安全综合管理平台</p>
        </div>
        <div class="verify-box">
          <img :src="verifyQrSrc" alt="报告验真二维码" />
          <span>扫码验真</span>
        </div>
      </div>

      <div class="meta-grid">
        <div><span>报告编号</span><strong>{{ detail.report_no || '-' }}</strong></div>
        <div><span>档案编号</span><strong>{{ detail.id }}</strong></div>
        <div><span>巡检地点</span><strong>{{ detail.location || '-' }}</strong></div>
        <div><span>巡检时间</span><strong>{{ detail.created_at || '-' }}</strong></div>
        <div><span>巡检人员</span><strong>{{ detail.inspector || '安全管理员' }}</strong></div>
        <div><span>复查状态</span><strong>{{ detail.review_status || '-' }}</strong></div>
        <div><span>风险等级</span><strong :class="riskClass(detail.risk_level)">{{ detail.risk_level || '-' }}</strong></div>
        <div><span>风险评分</span><strong>{{ detail.risk_score || 0 }}</strong></div>
      </div>

      <div class="summary-cards">
        <div><span>隐患数量</span><strong>{{ detail.hazards?.length || 0 }}</strong></div>
        <div><span>图片证据</span><strong>{{ detail.image_paths?.length || 0 }}</strong></div>
        <div><span>整改工单</span><strong>{{ detail.workorders?.length || 0 }}</strong></div>
        <div><span>报告完整度</span><strong>{{ detail.quality?.score || 0 }}%</strong></div>
      </div>

      <section>
        <h2>一、巡检基本信息</h2>
        <p>{{ detail.description || '未填写现场描述。' }}</p>
      </section>

      <section>
        <h2>二、现场图片证据</h2>
        <ul v-if="detail.image_paths?.length">
          <li v-for="p in detail.image_paths" :key="p">{{ p }}</li>
        </ul>
        <p v-else>未记录图片证据路径。后续可扩展为报告内嵌图片。</p>
      </section>

      <section>
        <h2>三、综合风险结论</h2>
        <p>本次巡检综合风险等级为 <b :class="riskClass(detail.risk_level)">{{ detail.risk_level }}</b>，风险评分 {{ detail.risk_score }} 分。</p>
        <p>主要隐患：{{ hazardsText }}</p>
      </section>

      <section>
        <h2>四、隐患明细与整改建议</h2>
        <table>
          <thead><tr><th>#</th><th>隐患</th><th>等级</th><th>识别依据</th><th>整改建议</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in detail.hazard_details || []" :key="i">
              <td>{{ i + 1 }}</td>
              <td>{{ h.hazard_name || h.type }}</td>
              <td>{{ h.risk_level || h.severity }}</td>
              <td>{{ h.evidence || h.reason || '系统识别到相关风险。' }}</td>
              <td>{{ h.suggestion || h.measure || '建议现场复核并整改。' }}</td>
            </tr>
            <tr v-if="!detail.hazard_details?.length"><td colspan="5">暂无结构化隐患明细。</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>五、RAG 引用依据</h2>
        <table>
          <thead><tr><th>#</th><th>标题</th><th>分类</th><th>相似度</th><th>摘要</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in detail.rag_references || []" :key="i">
              <td>{{ i + 1 }}</td>
              <td>{{ r.title || r.source }}</td>
              <td>{{ r.category || '消防知识' }}</td>
              <td>{{ r.similarity || r.score || '' }}</td>
              <td>{{ r.summary || r.content || r.content_preview }}</td>
            </tr>
            <tr v-if="!detail.rag_references?.length"><td colspan="5">暂无 RAG 引用依据。</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>六、整改工单与闭环复查</h2>
        <table>
          <thead><tr><th>#</th><th>隐患</th><th>状态</th><th>责任角色</th><th>整改时限</th><th>整改建议</th></tr></thead>
          <tbody>
            <tr v-for="(o, i) in detail.workorders || []" :key="o.id || i">
              <td>{{ i + 1 }}</td>
              <td>{{ o.hazard }}</td>
              <td>{{ o.status }}</td>
              <td>{{ o.responsible_role }}</td>
              <td>{{ o.deadline }}</td>
              <td>{{ o.recommended_action }}</td>
            </tr>
            <tr v-if="!detail.workorders?.length"><td colspan="6">暂无整改工单。</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>七、报告验真与 AI 生成说明</h2>
        <p>验真地址：{{ verifyUrl }}</p>
        <p>报告由巡检模块生成，包含现场输入、隐患识别、风险评分、知识引用、整改工单和复查信息。报告结论建议由消防安全管理员结合现场情况复核后归档。</p>
      </section>

      <div class="sign-row">
        <div>巡检人员：__________</div>
        <div>复查人员：__________</div>
        <div>归档日期：__________</div>
      </div>
    </div>

    <el-empty v-else class="paper" description="未找到报告" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import request from "../api"

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const detail = ref({})
const templates = ref([])
const templateKey = ref(route.query.template || "standard")

const hazardsText = computed(() => (detail.value.hazards || []).join("、") || "未发现明显隐患")
const verifyNo = computed(() => detail.value.report_no || detail.value.id || route.params.id)
const verifyUrl = computed(() => `${window.location.origin}/report-verify/${verifyNo.value}`)
const verifyQrSrc = computed(() => `/api/reports/verify-qr/${verifyNo.value}`)
const riskClass = level => String(level).includes("高") || String(level).includes("严重") ? "risk-high" : String(level).includes("中") ? "risk-mid" : "risk-low"

const loadTemplates = async () => {
  try { templates.value = (await request.get("/api/reports/templates")).data.templates || [] }
  catch { templates.value = [] }
}
const load = async () => {
  loading.value = true
  try {
    detail.value = (await request.get(`/api/inspection-archives/${route.params.id}`)).data || {}
  } catch {
    detail.value = {}
  } finally { loading.value = false }
}
const downloadMarkdown = async () => {
  try {
    const res = await request.get(`/api/reports/enhanced/${route.params.id}`, { params: { template: templateKey.value, format: "markdown" } })
    const blob = new Blob([res.data.content || ""], { type: res.data.mime_type || "text/markdown;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = res.data.filename || `${route.params.id}_report.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    return
  }
}
const goBack = () => router.back()
const openVerify = () => window.open(verifyUrl.value, "_blank")

onMounted(async () => { await loadTemplates(); await load() })
</script>

<style scoped>
.print-page { background:#f1f5f9; min-height:100vh; padding:24px; color:#0f172a; }
.toolbar { max-width:980px; margin:0 auto 16px; display:flex; gap:10px; align-items:center; }
.paper { background:#fff; max-width:980px; margin:0 auto; padding:48px; box-shadow:0 8px 28px rgba(15,23,42,.10); }
.cover { display:flex; justify-content:space-between; align-items:center; gap:24px; margin-bottom:30px; border-bottom:1px solid #e2e8f0; padding-bottom:18px; }
.cover h1 { margin:0 0 8px; font-size:28px; }
.cover p { color:#64748b; margin:0; }
.verify-box { width:116px; text-align:center; color:#64748b; font-size:12px; }
.verify-box img { width:104px; height:104px; border:1px solid #e2e8f0; border-radius:10px; padding:4px; background:#fff; }
.meta-grid { display:grid; grid-template-columns:repeat(2,1fr); border:1px solid #cbd5e1; margin-bottom:24px; }
.meta-grid div { padding:10px 12px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; gap:10px; }
.meta-grid span { color:#64748b; }
.summary-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:26px; }
.summary-cards div { background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:12px; }
.summary-cards span { color:#64748b; display:block; }
.summary-cards strong { font-size:24px; color:#2563eb; }
section { margin-top:26px; page-break-inside:avoid; }
h2 { font-size:18px; border-left:5px solid #2563eb; padding-left:10px; }
p, li { line-height:1.8; }
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:10px; }
th, td { border:1px solid #cbd5e1; padding:8px; vertical-align:top; }
th { background:#f8fafc; }
.sign-row { display:grid; grid-template-columns:repeat(3,1fr); margin-top:42px; gap:18px; }
.risk-high { color:#dc2626; font-weight:800; }
.risk-mid { color:#d97706; font-weight:800; }
.risk-low { color:#16a34a; font-weight:800; }
@media print {
  .no-print { display:none; }
  .print-page { background:white; padding:0; }
  .paper { box-shadow:none; max-width:none; padding:0; }
}
</style>
