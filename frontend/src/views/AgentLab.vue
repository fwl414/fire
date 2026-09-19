<template>
  <div class="agent-lab-page">
    <div class="title-row">
      <div>
        <div class="page-title">分析能力展示</div>
        <p class="subtitle">展示系统如何理解任务、选择工具、检索知识、计算风险并输出整改闭环建议。</p>
      </div>
      <div class="run-actions">
        <el-tag v-if="lastRunAt" type="success" effect="plain">最近运行：{{ lastRunAt }}</el-tag>
        <el-button type="primary" :loading="loading" @click="runDecisionChain">{{ loading ? '正在运行' : '运行决策链' }}</el-button>
      </div>
    </div>

    <el-alert
      class="explain-alert"
      type="info"
      :closable="false"
      show-icon
      title="这个页面用于演示 Agent 决策过程"
      description="它不是普通表单，而是把“任务理解 → 工具调用 → 知识检索 → 风险评分 → 整改闭环建议”的过程可视化，方便答辩时说明系统为什么这样判断。"
    />

    <el-row :gutter="12">
      <el-col :xs="24" :lg="7">
        <el-card class="card">
          <template #header>演示场景</template>
          <div class="scenario-list">
            <div
              v-for="s in scenarios"
              :key="s"
              class="scenario-card"
              :class="{ active: scenario === s }"
              @click="selectScenario(s)"
            >{{ s }}</div>
          </div>
          <el-input v-model="scenario" type="textarea" :rows="4" resize="none" placeholder="也可以输入自定义场景" style="margin-top:12px" />
          <el-button class="custom-run" plain type="primary" @click="runDecisionChain">按当前输入重新分析</el-button>
        </el-card>

        <el-card class="card summary-card">
          <template #header>最终决策摘要</template>
          <div class="risk-seal" :class="riskTone">{{ result.risk_level || '待分析' }}</div>
          <h2>{{ result.risk_score || 0 }} 分</h2>
          <p>{{ result.final_decision || '选择一个场景后运行 Agent 决策链。' }}</p>
          <div class="summary-meta">
            <span>运行批次：#{{ runNo }}</span>
            <span>分析场景：{{ result.scenario || scenario }}</span>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="17">
        <el-card class="card progress-card">
          <template #header>
            <div class="header-row"><strong>Agent 执行链路</strong><span>{{ loading ? '执行中，请稍候…' : '执行完成，可查看解释结果' }}</span></div>
          </template>
          <div class="decision-steps">
            <div v-for="(step, i) in decisionSteps" :key="step.name" class="decision-step" :class="{ active: i <= activeStep, done: !loading && i <= activeStep }">
              <b>{{ i + 1 }}</b>
              <div>
                <strong>{{ step.name }}</strong>
                <p>{{ step.desc }}</p>
              </div>
            </div>
          </div>
        </el-card>

        <el-card class="card">
          <template #header>为什么这样判定</template>
          <el-row :gutter="12">
            <el-col :xs="24" :md="8" v-for="(w, i) in result.why || []" :key="i">
              <div class="why-card"><b>{{ i + 1 }}</b><p>{{ w }}</p></div>
            </el-col>
          </el-row>
          <el-empty v-if="!(result.why || []).length" description="暂无解释，请先运行决策链" />
        </el-card>

        <el-row :gutter="12">
          <el-col :xs="24" :lg="12">
            <el-card class="card chain-card">
              <template #header>风险分数构成</template>
              <div v-for="s in result.score_breakdown || []" :key="s.factor" class="score-row">
                <div class="score-top"><span>{{ s.factor }}</span><b>+{{ s.score }}</b></div>
                <el-progress :percentage="Math.min(Number(s.score || 0), 100)" :stroke-width="10" />
                <p>{{ s.reason }}</p>
              </div>
              <el-empty v-if="!(result.score_breakdown || []).length" description="暂无评分构成" />
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card class="card chain-card">
              <template #header>工具调用矩阵</template>
              <div v-for="t in result.tools || []" :key="t.name" class="tool-row">
                <div><strong>{{ t.name }}</strong><p>{{ t.output }}</p></div>
                <el-tag :type="t.status === '已调用' ? 'success' : 'info'">{{ t.status }}</el-tag>
              </div>
              <el-empty v-if="!(result.tools || []).length" description="暂无工具调用记录" />
            </el-card>
          </el-col>
        </el-row>

        <el-card class="card">
          <template #header>命中的知识依据</template>
          <el-row :gutter="12">
            <el-col :xs="24" :md="8" v-for="k in result.knowledge_hits || []" :key="k.title">
              <div class="knowledge-card"><strong>{{ k.title }}</strong><p>{{ k.reason }}</p></div>
            </el-col>
          </el-row>
          <el-empty v-if="!(result.knowledge_hits || []).length" description="暂无知识命中" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'

const scenarios = ['消防通道堵塞巡检', '实验室电气线路过载', '机房烟感报警处置', '灭火器被遮挡', '电动车违规充电', '消防水压异常']
const scenario = ref(scenarios[0])
const result = ref({})
const loading = ref(false)
const lastRunAt = ref('')
const runNo = ref(0)
const activeStep = ref(-1)
let stepTimer = null

const decisionSteps = [
  { name: '任务理解', desc: '解析巡检场景、地点、隐患关键词。' },
  { name: '工具选择', desc: '选择文本识别、图像分析、RAG 检索等工具。' },
  { name: '知识检索', desc: '匹配消防法规、制度和整改知识条目。' },
  { name: '风险评分', desc: '按严重度、场景叠加和闭环要求计算分数。' },
  { name: '整改决策', desc: '输出责任角色、整改时限和复查方式。' },
]

const riskTone = computed(() => String(result.value.risk_level || '').includes('高') || String(result.value.risk_level || '').includes('严重') ? 'danger' : String(result.value.risk_level || '').includes('中') ? 'warning' : 'success')

function buildFallbackDecision(text) {
  const high = ['烟', '电', '堵塞', '违规', '报警', '过载'].some(k => text.includes(k))
  const riskScore = high ? 82 : 58
  const riskLevel = high ? '高风险' : '中风险'
  return {
    scenario: text,
    risk_level: riskLevel,
    risk_score: riskScore,
    why: [
      '识别到可能影响疏散、灭火或报警联动的关键风险特征。',
      '风险与消防通道、电气火灾、设施遮挡或硬件报警等知识条目匹配。',
      '当前场景需要明确责任人、整改时限和复查闭环。',
    ],
    score_breakdown: [
      { factor: '隐患严重度', score: 35, reason: '影响人员疏散或初期处置能力。' },
      { factor: '场景叠加', score: 20, reason: '存在可燃物、电气或硬件报警等叠加因素。' },
      { factor: '闭环要求', score: 15, reason: '需要生成工单并复查。' },
      { factor: '人工复核', score: high ? 12 : 6, reason: '现场图片或描述仍建议人工确认。' },
    ],
    tools: [
      { name: '文本隐患识别', status: '已调用', output: '抽取消防隐患关键词和场景。' },
      { name: '图像证据分析', status: '按需调用', output: '识别疑似隐患标签与置信度。' },
      { name: 'RAG 知识检索', status: '已调用', output: '返回法规、标准和整改依据。' },
      { name: '风险评分引擎', status: '已调用', output: `输出 ${riskScore} 分，${riskLevel}。` },
      { name: '整改闭环工具', status: '已调用', output: '生成整改建议、责任角色和复查要求。' },
    ],
    knowledge_hits: [
      { title: '消防通道与疏散通道管理', reason: '涉及疏散通道畅通要求。' },
      { title: '电气火灾风险防控', reason: '涉及插排、过载、温升或违规充电。' },
      { title: '整改闭环管理', reason: '涉及工单、复查和归档。' },
    ],
    final_decision: '建议将该场景纳入整改工单，按风险等级确定整改时限，整改完成后上传前后对比图片并复查归档。',
  }
}

function startStepAnimation() {
  clearInterval(stepTimer)
  activeStep.value = -1
  stepTimer = setInterval(() => {
    activeStep.value += 1
    if (activeStep.value >= decisionSteps.length - 1) {
      clearInterval(stepTimer)
    }
  }, 220)
}

async function runDecisionChain() {
  const text = (scenario.value || '').trim() || scenarios[0]
  scenario.value = text
  loading.value = true
  runNo.value += 1
  startStepAnimation()
  try {
    const res = await request.post('/api/agent/explain', { scenario: text }, { silentError: true })
    result.value = { ...buildFallbackDecision(text), ...(res.data || {}), run_id: Date.now() }
    ElMessage.success('Agent 决策链已运行完成')
  } catch (e) {
    result.value = { ...buildFallbackDecision(text), run_id: Date.now() }
    ElMessage.warning('在线研判暂不可用，已使用本地决策链展示')
  } finally {
    loading.value = false
    activeStep.value = decisionSteps.length - 1
    lastRunAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }
}

function selectScenario(s) {
  scenario.value = s
  runDecisionChain()
}

onMounted(runDecisionChain)
</script>

<style scoped>
.title-row{display:flex;justify-content:space-between;align-items:center;gap:12px}.subtitle{margin:-6px 0 0;color:#64748b}.run-actions{display:flex;gap:10px;align-items:center}.explain-alert{margin-bottom:12px}.header-row{display:flex;justify-content:space-between;align-items:center;color:#64748b}.scenario-list{display:grid;gap:8px}.scenario-card{border:1px solid #e2e8f0;border-radius:12px;padding:11px;background:#fff;cursor:pointer}.scenario-card.active,.scenario-card:hover{border-color:#2563eb;background:#eff6ff;color:#1d4ed8;font-weight:700}.custom-run{width:100%;margin-top:10px}.summary-card{text-align:center}.risk-seal{display:inline-flex;width:98px;height:98px;border-radius:50%;align-items:center;justify-content:center;border:4px solid #22c55e;color:#16a34a;font-weight:900;margin:8px auto;transform:rotate(-10deg)}.risk-seal.danger{border-color:#ef4444;color:#dc2626}.risk-seal.warning{border-color:#f59e0b;color:#d97706}.summary-card h2{font-size:40px;margin:6px 0}.summary-card p{color:#475569;line-height:1.7}.summary-meta{display:grid;gap:4px;color:#94a3b8;font-size:12px;margin-top:8px}.progress-card{margin-bottom:12px}.decision-steps{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.decision-step{display:flex;gap:10px;align-items:flex-start;border:1px solid #e2e8f0;border-radius:14px;padding:12px;background:#f8fafc;opacity:.65;transition:.18s}.decision-step.active{opacity:1;border-color:#bfdbfe;background:#eff6ff;transform:translateY(-1px)}.decision-step.done{border-color:#bbf7d0;background:#f0fdf4}.decision-step b{display:inline-flex;width:26px;height:26px;border-radius:50%;background:#e2e8f0;color:#475569;align-items:center;justify-content:center;flex:0 0 auto}.decision-step.active b{background:#2563eb;color:#fff}.decision-step.done b{background:#22c55e;color:#fff}.decision-step strong{display:block;color:#0f172a}.decision-step p{margin:4px 0 0;color:#64748b;line-height:1.45;font-size:12px}.why-card{border:1px solid #e2e8f0;border-radius:16px;padding:14px;min-height:128px;background:#fff}.why-card b{display:inline-flex;width:28px;height:28px;border-radius:50%;background:#eff6ff;color:#2563eb;align-items:center;justify-content:center}.why-card p{color:#475569;line-height:1.7}.chain-card{min-height:370px}.score-row{margin-bottom:16px}.score-top,.tool-row{display:flex;justify-content:space-between;align-items:center;gap:12px}.score-row p,.tool-row p,.knowledge-card p{color:#64748b;line-height:1.6;margin:6px 0 0}.tool-row{border:1px solid #e2e8f0;border-radius:14px;padding:12px;margin-bottom:10px;background:#fff}.knowledge-card{border:1px solid #e2e8f0;border-top:4px solid #2563eb;border-radius:16px;padding:14px;background:#fff;min-height:116px}@media(max-width:1100px){.decision-steps{grid-template-columns:1fr}}
</style>
