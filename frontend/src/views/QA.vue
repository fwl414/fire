<template>
  <div class="qa-page">
    <div class="title-row">
      <div><div class="page-title">消防问答</div><p class="subtitle">常见问题和处置建议</p></div>
      <el-tag type="success" effect="dark">处置手册模式</el-tag>
    </div>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="8">
        <el-card class="card">
          <template #header>提问设置</template>
          <el-radio-group v-model="mode" class="mode-group">
            <el-radio-button label="应急处置" />
            <el-radio-button label="法规依据" />
            <el-radio-button label="整改建议" />
            <el-radio-button label="学习解释" />
          </el-radio-group>
          <el-input v-model="question" type="textarea" :rows="6" resize="none" placeholder="例如：消防通道堵塞怎么处理？" />
          <div class="ask-actions"><el-button type="primary" :loading="loading" @click="ask">提交问题</el-button><el-button @click="question=''">清空</el-button></div>
        </el-card>

        <el-card class="card">
          <template #header>常见问题卡片</template>
          <div class="scene-list">
            <div v-for="q in sceneQuestions" :key="q.question" class="scene-card" @click="useQuestion(q.question, q.mode)">
              <strong>{{ q.question }}</strong><span>{{ q.mode }} · {{ q.tag }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="16">
        <el-card v-if="!result" class="card empty-card"><el-empty description="选择常见问题或输入问题后，系统会按“先做什么、禁止做什么、通知谁、多久内整改、依据是什么、是否生成工单”的结构返回。" /></el-card>

        <el-card v-else class="card answer-card">
          <template #header><div class="header-row"><strong>消防处置手册</strong><el-tag :type="result.used_text_model_api ? 'success' : 'info'">{{ result.used_text_model_api ? '知识库增强' : '知识库 + 规则' }}</el-tag></div></template>
          <el-alert v-if="error" :title="error" type="warning" show-icon class="mb" />
          <div class="manual-hero">
            <span>一句话结论</span>
            <h2>{{ manual.conclusion }}</h2>
          </div>
          <el-row :gutter="12" class="manual-grid">
            <el-col :xs="24" :md="12" v-for="card in manualCards" :key="card.title">
              <div class="manual-card" :class="card.tone"><strong>{{ card.title }}</strong><p>{{ card.content }}</p></div>
            </el-col>
          </el-row>

          <el-card shadow="never" class="suggestion-box">
            <template #header><div class="header-row"><strong>整改工单建议</strong><el-button size="small" type="primary" @click="buildSuggestion">生成工单建议</el-button></div></template>
            <template v-if="workorderSuggestion.suggested">
              <el-descriptions border :column="2">
                <el-descriptions-item label="是否建议生成工单"><el-tag type="danger">建议</el-tag></el-descriptions-item>
                <el-descriptions-item label="建议风险等级">{{ workorderSuggestion.risk_level }}</el-descriptions-item>
                <el-descriptions-item label="隐患类型">{{ workorderSuggestion.hazard }}</el-descriptions-item>
                <el-descriptions-item label="整改期限">{{ workorderSuggestion.deadline }}</el-descriptions-item>
                <el-descriptions-item label="责任部门">{{ workorderSuggestion.responsible_role }}</el-descriptions-item>
                <el-descriptions-item label="复查方式">{{ workorderSuggestion.review_method }}</el-descriptions-item>
                <el-descriptions-item label="建议动作" :span="2">{{ workorderSuggestion.recommended_action }}</el-descriptions-item>
              </el-descriptions>
            </template>
            <p v-else class="muted">点击按钮后，系统会根据本次问答自动判断是否建议纳入整改闭环。</p>
          </el-card>

          <el-tabs v-model="activeTab" class="qa-tabs">
            <el-tab-pane label="知识库引用依据" name="refs">
              <el-row :gutter="12"><el-col :xs="24" :md="12" v-for="(r,idx) in result.references || []" :key="idx"><div class="ref-card"><div class="header-row"><strong>{{ r.title }}</strong><el-tag size="small">{{ r.category || '知识' }}</el-tag></div><p>{{ r.content || r.summary || r.content_preview }}</p><div class="muted">匹配关键词：{{ (r.matched_keywords || []).join('、') || '-' }}</div></div></el-col></el-row>
              <el-empty v-if="!(result.references||[]).length" description="暂无引用知识" />
            </el-tab-pane>
            <el-tab-pane label="原始回答" name="raw"><pre class="answer">{{ result.answer }}</pre></el-tab-pane>
            <el-tab-pane label="处理过程" name="steps"><el-timeline><el-timeline-item v-for="(s,i) in result.agent_steps || []" :key="i">{{ s }}</el-timeline-item></el-timeline></el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import request from '../api'
const question=ref('消防通道堵塞怎么处理？'); const mode=ref('应急处置'); const result=ref(null); const loading=ref(false); const error=ref(''); const activeTab=ref('refs'); const workorderSuggestion=ref({})
const sceneQuestions=[
  {question:'消防通道堵塞怎么处理？',mode:'应急处置',tag:'疏散通道'},
  {question:'电气火灾如何预防？',mode:'法规依据',tag:'电气安全'},
  {question:'实验室发现异味怎么办？',mode:'应急处置',tag:'实验室'},
  {question:'烟感报警后怎么处置？',mode:'应急处置',tag:'硬件报警'},
  {question:'灭火器压力不足怎么办？',mode:'整改建议',tag:'消防设施'},
  {question:'电动车违规充电怎么处理？',mode:'整改建议',tag:'电动车'},
]
const manual=computed(()=>{ const a=result.value?.answer||''; return {
  conclusion: firstSentence(section(a,['结论','一句话结论'])||a)||'该问题涉及消防安全风险，应立即核查现场并纳入整改闭环。',
  doFirst: section(a,['先做什么','操作建议','建议'])||'立即确认现场风险，清理障碍物或停止危险行为，必要时切断电源并疏散人员。',
  forbidden: section(a,['禁止做什么','禁止事项'])||'禁止带电用水处置电气火灾，禁止继续占用疏散通道，禁止隐患未复查即关闭工单。',
  notify: section(a,['通知谁','上报'])||'通知区域安全责任人、物业/安保人员；高风险或疑似火情应同步通知消防安全管理员。',
  deadline: section(a,['多久内整改','整改期限'])||'高风险建议 24 小时内整改；严重或正在发展的火情应立即处置并启动应急流程。',
  basis: section(a,['依据','法规依据'])||refText.value||'依据消防安全管理制度、疏散通道管理要求和单位巡检规范执行。',
}})
const refText=computed(()=>{ const refs=result.value?.references||[]; return refs.slice(0,2).map(r=>`可参考《${r.title}》`).join('、') })
const manualCards=computed(()=>[
  {title:'先做什么',content:manual.value.doFirst,tone:'blue'}, {title:'禁止做什么',content:manual.value.forbidden,tone:'red'}, {title:'通知谁',content:manual.value.notify,tone:'orange'}, {title:'多久内整改',content:manual.value.deadline,tone:'green'}, {title:'依据是什么',content:manual.value.basis,tone:'slate'}, {title:'是否需要生成工单',content:'若存在堵塞、遮挡、违规充电、烟感报警、电气过载等隐患，建议生成整改工单并复查。',tone:'purple'}
])
function section(text, keys){ for(const key of keys){ const re=new RegExp(`${key}[：:\n\s]*(.*?)(?=\n[#一二三四五六0-9、.．]*?(结论|一句话结论|先做什么|禁止做什么|通知谁|多久内整改|整改期限|依据|法规依据|操作建议|风险提示)[:：]|$)`,'s'); const m=String(text||'').match(re); if(m&&m[1]) return m[1].trim().slice(0,260)} return '' }
function firstSentence(text){ return (text||'').split(/[。\n]/).find(x=>x.trim())?.trim() }
function useQuestion(q,m){ question.value=q; mode.value=m; ask() }
async function ask(){ if(!question.value.trim())return; loading.value=true; error.value=''; workorderSuggestion.value={}; try{ const fd=new FormData(); fd.append('question',`【${mode.value}模式】${question.value}。请按：一句话结论、先做什么、禁止做什么、通知谁、多久内整改、依据是什么、是否建议生成工单 输出。`); result.value=(await request.post('/api/qa/fire',fd)).data; await buildSuggestion() }catch(e){ error.value='智能问答暂时异常，请稍后重试。' }finally{ loading.value=false } }
async function buildSuggestion(){ if(!result.value)return; workorderSuggestion.value=(await request.post('/api/qa/workorder-suggestion',{question:question.value, answer:result.value.answer||''})).data }
onMounted(()=>{})
</script>
<style scoped>
.title-row,.header-row{display:flex;justify-content:space-between;align-items:center;gap:12px}.subtitle{margin:-6px 0 0;color:#64748b}.mode-group{display:flex;flex-wrap:wrap;margin-bottom:12px}.ask-actions{display:flex;gap:10px;margin-top:12px}.scene-list{display:grid;gap:10px}.scene-card{border:1px solid #e2e8f0;border-radius:14px;padding:12px;background:#fff;cursor:pointer}.scene-card:hover{border-color:#2563eb;background:#eff6ff}.scene-card strong{display:block;margin-bottom:4px}.scene-card span,.muted{color:#64748b;font-size:12px}.empty-card{min-height:520px;display:flex;align-items:center;justify-content:center}.manual-hero{background:linear-gradient(135deg,#eff6ff,#fff);border:1px solid #dbeafe;border-radius:18px;padding:18px;margin-bottom:12px}.manual-hero span{color:#2563eb;font-weight:700}.manual-hero h2{font-size:22px;margin:8px 0 0}.manual-card{border:1px solid #e2e8f0;border-top:4px solid #2563eb;border-radius:16px;padding:14px;min-height:138px;background:#fff;margin-bottom:12px}.manual-card.red{border-top-color:#ef4444}.manual-card.orange{border-top-color:#f59e0b}.manual-card.green{border-top-color:#22c55e}.manual-card.slate{border-top-color:#64748b}.manual-card.purple{border-top-color:#8b5cf6}.manual-card p{color:#475569;line-height:1.7}.suggestion-box{margin:8px 0 12px}.ref-card{border:1px solid #e2e8f0;border-radius:14px;padding:12px;margin-bottom:12px;background:#fff}.ref-card p{color:#475569;line-height:1.7}.answer{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;line-height:1.8}.mb{margin-bottom:12px}
</style>
