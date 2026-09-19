<template>
  <div>
    <div class="title-row">
      <div><div class="page-title">整改工单</div><p class="subtitle">逾期预警、待复查提醒、高风险优先处理和整改前后图片证据链。</p></div>
      <el-button @click="loadAll">刷新</el-button>
    </div>

    <el-row :gutter="12" class="metric-row">
      <el-col :xs="24" :sm="12" :md="6" v-for="c in summaryCards" :key="c.label">
        <div class="metric-card" :class="c.tone"><span>{{ c.label }}</span><strong>{{ c.value }}</strong><small>{{ c.desc }}</small></div>
      </el-col>
    </el-row>

    <el-card class="card">
      <template #header>
        <div class="header-row"><strong>工单列表</strong><div><el-select v-model="statusFilter" clearable placeholder="状态筛选" style="width:150px;margin-right:8px" @change="loadOrders"><el-option label="待派单" value="待派单"/><el-option label="整改中" value="整改中"/><el-option label="待复查" value="待复查"/><el-option label="已闭环" value="已闭环"/></el-select><el-button type="primary" @click="loadAll">刷新</el-button></div></div>
      </template>
      <VirtualTable :data="orders" :total="orders.length" :loading="loading" :table-height="500">
        <el-table-column prop="hazard" label="隐患" width="140" />
        <el-table-column prop="location" label="地点" width="150" show-overflow-tooltip />
        <el-table-column prop="risk_level" label="风险" width="95"><template #default="{row}"><el-tag :type="riskType(row.risk_level)">{{ row.risk_level }}</el-tag></template></el-table-column>
        <el-table-column prop="status" label="状态" width="95"><template #default="{row}"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column label="预警" width="130"><template #default="{row}"><el-tag :type="warningInfo(row).type">{{ warningInfo(row).text }}</el-tag></template></el-table-column>
        <el-table-column prop="responsible_role" label="责任角色" width="180" show-overflow-tooltip />
        <el-table-column prop="deadline" label="整改时限" width="150" />
        <el-table-column prop="recommended_action" label="整改建议" min-width="260" show-overflow-tooltip />
        <el-table-column label="证据" width="120"><template #default="{row}">{{ (row.before_images||[]).length }} / {{ (row.after_images||[]).length }}</template></el-table-column>
        <el-table-column label="操作" width="210" fixed="right"><template #default="{row}"><el-button size="small" @click="openDetail(row)">详情</el-button><el-button size="small" type="primary" @click="nextStatus(row)" :disabled="row.status==='已闭环'">推进</el-button></template></el-table-column>
      </VirtualTable>
      <el-empty v-if="!orders.length" description="暂无整改工单。请先在巡检页面生成整改工单。" />
    </el-card>

    <el-drawer v-model="drawerVisible" title="整改工单详情" size="62%">
      <template v-if="current.id">
        <div class="drawer-head"><div><h2>{{ current.hazard }}</h2><p>{{ current.location }} · {{ current.id }}</p></div><el-tag :type="statusType(current.status)" size="large">{{ current.status }}</el-tag></div>
        <el-descriptions border :column="2">
          <el-descriptions-item label="责任角色">{{ current.responsible_role }}</el-descriptions-item>
          <el-descriptions-item label="整改时限">{{ current.deadline }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">{{ current.risk_level }}</el-descriptions-item>
          <el-descriptions-item label="预警状态">{{ warningInfo(current).text }}</el-descriptions-item>
          <el-descriptions-item label="整改建议" :span="2">{{ current.recommended_action }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs v-model="tab" class="detail-tabs">
          <el-tab-pane label="整改前后对比" name="evidence">
            <el-alert title="可填写图片路径、URL 或现场说明；后续接入真实上传时可直接替换为图片地址。" type="info" show-icon style="margin-bottom:12px" />
            <el-row :gutter="12">
              <el-col :xs="24" :md="12"><div class="image-panel before"><h3>整改前图片 / 证据</h3><div v-for="(img,i) in beforeImages" :key="i" class="image-row"><span>{{ img }}</span><el-button link type="danger" @click="beforeImages.splice(i,1)">删除</el-button></div><el-input v-model="newBefore" placeholder="添加整改前图片路径或证据说明" @keyup.enter="addBefore"><template #append><el-button @click="addBefore">添加</el-button></template></el-input></div></el-col>
              <el-col :xs="24" :md="12"><div class="image-panel after"><h3>整改后图片 / 复查证据</h3><div v-for="(img,i) in afterImages" :key="i" class="image-row"><span>{{ img }}</span><el-button link type="danger" @click="afterImages.splice(i,1)">删除</el-button></div><el-input v-model="newAfter" placeholder="添加整改后图片路径或复查说明" @keyup.enter="addAfter"><template #append><el-button @click="addAfter">添加</el-button></template></el-input></div></el-col>
            </el-row>
            <el-input v-model="reviewNote" type="textarea" :rows="3" placeholder="复查意见，例如：现场已清理，通道恢复畅通，复查通过。" style="margin-top:12px" />
            <div class="btn-row"><el-button type="primary" @click="saveEvidence">保存证据链</el-button><el-button @click="addMockAfter">添加模拟整改后图片</el-button></div>
          </el-tab-pane>
          <el-tab-pane label="复查闭环" name="review">
            <el-alert title="复查通过时可自动闭环；复查不通过时退回整改中并继续跟踪。" type="warning" show-icon style="margin-bottom:12px" />
            <el-form label-width="110px">
              <el-form-item label="复查人员"><el-input v-model="reviewer" placeholder="安全管理员" /></el-form-item>
              <el-form-item label="复查结论"><el-radio-group v-model="reviewResult"><el-radio-button label="通过">通过</el-radio-button><el-radio-button label="不通过">不通过</el-radio-button></el-radio-group></el-form-item>
              <el-form-item label="复查说明"><el-input v-model="reviewNote" type="textarea" :rows="3" placeholder="例如：现场已清理，照片与现场一致，复查通过。" /></el-form-item>
              <el-form-item label="自动闭环"><el-switch v-model="autoClose" active-text="通过后自动闭环" /></el-form-item>
              <el-form-item><el-button type="primary" @click="submitReview">提交复查结论</el-button></el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="状态流转" name="timeline">
            <el-timeline>
              <el-timeline-item v-for="t in current.timeline || []" :key="t.status + t.time" :timestamp="t.time"><strong>{{ t.status }}</strong> - {{ t.operator }}：{{ t.note }}</el-timeline-item>
            </el-timeline>
          </el-tab-pane>
          <el-tab-pane label="智能辅助整改" name="ai-assist">
            <div class="ai-assist-panel">
              <div class="ai-assist-header">
                <div class="ai-icon">
                  <el-icon><MagicStick /></el-icon>
                </div>
                <div>
                  <strong>智能整改助手</strong>
                  <p>基于隐患类型和风险等级，智能生成整改方案和资源建议</p>
                </div>
                <el-button type="primary" :loading="aiLoading" @click="generateAiPlan">
                  <el-icon><Refresh /></el-icon>
                  生成整改方案
                </el-button>
              </div>

              <el-empty v-if="!aiPlan" description='点击"生成整改方案"，AI将根据隐患信息智能生成整改建议' />

              <div v-if="aiPlan" class="ai-plan-content">
                <el-card shadow="never" class="ai-card">
                  <template #header>
                    <div class="ai-card-header">
                      <el-icon><Warning /></el-icon>
                      <strong>风险评估</strong>
                    </div>
                  </template>
                  <el-alert :title="aiPlan.risk_summary" :type="aiPlan.risk_level === '高' ? 'danger' : aiPlan.risk_level === '中' ? 'warning' : 'info'" show-icon style="margin-bottom:12px" />
                  <div class="ai-section">
                    <div class="ai-section-title">整改难度</div>
                    <el-progress :percentage="aiPlan.difficulty || 50" :color="aiPlan.difficulty > 70 ? '#ef4444' : aiPlan.difficulty > 40 ? '#f59e0b' : '#22c55e'" />
                  </div>
                  <div class="ai-section">
                    <div class="ai-section-title">预计整改时长</div>
                    <span class="ai-highlight">{{ aiPlan.estimated_time || '2-3天' }}</span>
                  </div>
                </el-card>

                <el-card shadow="never" class="ai-card">
                  <template #header>
                    <div class="ai-card-header">
                      <el-icon><List /></el-icon>
                      <strong>整改步骤</strong>
                    </div>
                  </template>
                  <div class="step-list">
                    <div v-for="(step, idx) in aiPlan.steps || []" :key="idx" class="step-item">
                      <div class="step-num">{{ idx + 1 }}</div>
                      <div class="step-content">
                        <div class="step-title">{{ step.action }}</div>
                        <div class="step-desc">{{ step.detail }}</div>
                        <div class="step-meta">
                          <el-tag size="small" type="info">{{ step.responsible }}</el-tag>
                          <el-tag size="small">{{ step.duration }}</el-tag>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-card>

                <el-row :gutter="12">
                  <el-col :xs="24" :md="12">
                    <el-card shadow="never" class="ai-card">
                      <template #header>
                        <div class="ai-card-header">
                          <el-icon><Tools /></el-icon>
                          <strong>所需资源</strong>
                        </div>
                      </template>
                      <ul class="resource-list">
                        <li v-for="(r, idx) in aiPlan.resources || []" :key="idx">
                          <el-icon><Check /></el-icon>
                          {{ r }}
                        </li>
                      </ul>
                    </el-card>
                  </el-col>
                  <el-col :xs="24" :md="12">
                    <el-card shadow="never" class="ai-card">
                      <template #header>
                        <div class="ai-card-header">
                          <el-icon><Notebook /></el-icon>
                          <strong>注意事项</strong>
                        </div>
                      </template>
                      <ul class="notice-list">
                        <li v-for="(n, idx) in aiPlan.notices || []" :key="idx">
                          <el-icon><InfoFilled /></el-icon>
                          {{ n }}
                        </li>
                      </ul>
                    </el-card>
                  </el-col>
                </el-row>

                <el-card shadow="never" class="ai-card">
                  <template #header>
                    <div class="ai-card-header">
                      <el-icon><Reading /></el-icon>
                      <strong>法规依据</strong>
                    </div>
                  </template>
                  <div class="regulation-list">
                    <div v-for="(r, idx) in aiPlan.regulations || []" :key="idx" class="regulation-item">
                      <el-tag size="small" type="success">{{ r.code }}</el-tag>
                      <span>{{ r.name }}</span>
                    </div>
                  </div>
                </el-card>

                <div class="ai-actions">
                  <el-button @click="applyAiSuggestion">应用建议到工单</el-button>
                  <el-button type="primary" @click="generateAiPlan">重新生成</el-button>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  MagicStick, Refresh, Warning, List, Tools,
  Check, Notebook, InfoFilled, Reading
} from '@element-plus/icons-vue'
import request from '../api'
import { generateRectificationPlan } from '../api/intelligence'
import VirtualTable from '../components/VirtualTable.vue'
const route=useRoute();
const dashboard=ref({}); const orders=ref([]); const statusFilter=ref(''); const drawerVisible=ref(false); const current=ref({}); const tab=ref('evidence'); const loading=ref(false)
const beforeImages=ref([]); const afterImages=ref([]); const reviewImages=ref([]); const newBefore=ref(''); const newAfter=ref(''); const reviewNote=ref(''); const reviewer=ref('安全管理员'); const reviewResult=ref('通过'); const autoClose=ref(true)
const aiLoading=ref(false); const aiPlan=ref(null)
const summaryCards=computed(()=>{ const cards=dashboard.value.summary_cards||[]; const get=l=>cards.find(c=>c.label===l)?.value||0; return [
  {label:'待派单', value:get('待派单'), tone:'orange', desc:'等待责任人接收'}, {label:'整改中', value:get('整改中'), tone:'blue', desc:'正在推进整改'}, {label:'待复查', value:get('待复查'), tone:'orange', desc:'需要现场复核'}, {label:'已闭环', value:get('已闭环'), tone:'green', desc:`闭环率 ${dashboard.value.closed_loop_rate||0}%`}
]})
function statusType(s){ if(s==='已闭环')return'success'; if(s==='待复查')return'warning'; if(s==='整改中')return'primary'; return'info' }
function riskType(l){ return String(l).includes('高')||String(l).includes('严重')?'danger':String(l).includes('中')?'warning':'success' }
function parseTime(t){ const d=new Date(String(t||'').replace(/-/g,'/')); return isNaN(d.getTime())?null:d }
function warningInfo(row){ if(row.status==='已闭环')return{type:'success',text:'已闭环'}; const d=parseTime(row.deadline); const now=new Date(); if(d&&d<now)return{type:'danger',text:'已逾期'}; if(d&&d-now<48*3600*1000)return{type:'warning',text:'即将逾期'}; if(row.status==='待复查')return{type:'warning',text:'待复查'}; if(String(row.risk_level).includes('高')||String(row.risk_level).includes('严重'))return{type:'danger',text:'高风险优先'}; return{type:'info',text:'正常跟进'} }
async function loadDashboard(){ dashboard.value=(await request.get('/api/workorders/rectification/dashboard')).data }
async function loadOrders(){ loading.value=true; try{ const res=await request.get('/api/workorders/rectification',{params:{status:statusFilter.value||''}}); const body=res.data||{}; orders.value=Array.isArray(body)?body:(body.items||[]) }finally{ loading.value=false } }
async function loadAll(){ loading.value=true; try{ await loadDashboard(); await loadOrders() }finally{ loading.value=false } }
async function openDetail(row){ current.value=(await request.get(`/api/workorders/rectification/${row.id}`)).data; beforeImages.value=[...(current.value.before_images||[])]; afterImages.value=[...(current.value.after_images||[])]; reviewImages.value=[...(current.value.review_images||[])]; reviewNote.value=current.value.review_note||''; reviewer.value=current.value.reviewer||'安全管理员'; reviewResult.value=current.value.review_result||'通过'; autoClose.value=true; aiPlan.value=null; drawerVisible.value=true }
function addBefore(){ if(newBefore.value.trim()){ beforeImages.value.push(newBefore.value.trim()); newBefore.value='' } }
function addAfter(){ if(newAfter.value.trim()){ afterImages.value.push(newAfter.value.trim()); newAfter.value='' } }
function addMockAfter(){ afterImages.value.push(`整改后复查图片-${new Date().toLocaleString()}：隐患已整改，现场恢复正常。`) }
async function saveEvidence(){ current.value=(await request.post(`/api/workorders/${current.value.id}/evidence`,{before_images:beforeImages.value, after_images:afterImages.value, review_images:reviewImages.value, review_note:reviewNote.value, operator:'安全管理员'})).data; ElMessage.success('证据链已保存'); await loadAll() }
async function nextStatus(row){ const map={'待派单':'整改中','整改中':'待复查','待复查':'已闭环'}; const status=map[row.status]||'整改中'; await request.post(`/api/workorders/rectification/${row.id}/status`,{status,operator:'安全管理员',note:`将工单推进至：${status}`}); ElMessage.success('状态已更新'); await loadAll() }
async function submitReview(){ current.value=(await request.post(`/api/workorders/${current.value.id}/review`,{reviewer:reviewer.value,result:reviewResult.value,note:reviewNote.value,review_images:reviewImages.value,auto_close:autoClose.value})).data; ElMessage.success('复查结论已提交'); await loadAll() }

async function generateAiPlan() {
  if (!current.value?.id) return
  aiLoading.value = true
  try {
    const res = await generateRectificationPlan({
      order_id: current.value.id,
      hazard: current.value.hazard || '',
      location: current.value.location || '',
      risk_level: current.value.risk_level || '中',
      description: current.value.recommended_action || '',
    })
    const raw = res.data
    aiPlan.value = {
      risk_summary: `该隐患为${current.value.risk_level || '中'}风险，需要及时整改`,
      risk_level: current.value.risk_level || '中',
      difficulty: raw.estimated_deadline_days ? Math.min(90, raw.estimated_deadline_days * 15) : 50,
      estimated_time: raw.estimated_deadline_days ? `${raw.estimated_deadline_days}天` : '3-5天',
      steps: (raw.rectification_steps || []).map((s, i) => ({
        action: s.content,
        detail: `第${i + 1}步整改工作内容`,
        responsible: i === 0 ? '安全管理员' : i === 2 ? '维修人员' : '整改责任人',
        duration: s.duration || '1天',
      })),
      resources: raw.required_resources || ['整改责任人1名', '安全防护用品', '必要的工具设备'],
      notices: raw.notes || ['整改过程中注意安全防护', '整改完成后及时申请复查'],
      regulations: [
        { code: 'GB50016', name: '建筑设计防火规范' },
        { code: 'GB50166', name: '火灾自动报警系统施工及验收标准' },
        { code: 'GA654', name: '人员密集场所消防安全管理' },
      ],
      acceptance_criteria: raw.acceptance_criteria || [],
      confidence: raw.confidence,
    }
    ElMessage.success('整改方案生成成功')
  } catch (e) {
    ElMessage.error('生成失败，请稍后重试')
  } finally {
    aiLoading.value = false
  }
}

function applyAiSuggestion() {
  if (!aiPlan.value) return
  if (aiPlan.value.steps?.length) {
    const suggestions = aiPlan.value.steps.map((s, i) => `${i + 1}. ${s.action}：${s.detail}`).join('；')
    current.value.recommended_action = suggestions
  }
  ElMessage.success('已应用AI建议到工单')
}
async function openByQuery(){ await loadAll(); const id=route.query.order_id; if(id){ const row=orders.value.find(o=>o.id===id) || {id}; await openDetail(row) } }
onMounted(openByQuery)
watch(() => route.query.order_id, openByQuery)
</script>
<style scoped>
.title-row,.header-row,.drawer-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.subtitle{margin:-6px 0 0;color:#64748b}.metric-row{margin-bottom:12px}.metric-card{background:#fff;border:1px solid #e2e8f0;border-top:4px solid #2563eb;border-radius:16px;padding:14px}.metric-card.orange{border-top-color:#f59e0b}.metric-card.green{border-top-color:#22c55e}.metric-card span{color:#64748b}.metric-card strong{display:block;font-size:34px;margin:8px 0}.metric-card small{color:#94a3b8}.drawer-head h2{margin:0}.drawer-head p{color:#64748b}.detail-tabs{margin-top:14px}.image-panel{border:1px solid #e2e8f0;border-radius:16px;padding:14px;min-height:240px;background:#fff}.image-panel.before{border-top:4px solid #f59e0b}.image-panel.after{border-top:4px solid #22c55e}.image-row{display:flex;justify-content:space-between;gap:10px;align-items:center;border:1px dashed #cbd5e1;border-radius:10px;padding:8px;margin-bottom:8px;color:#475569}.btn-row{display:flex;gap:10px;margin-top:12px}

.ai-assist-panel {
  padding: 4px 0;
}
.ai-assist-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  background: linear-gradient(135deg, #eff6ff, #ecfeff);
  border-radius: 12px;
  margin-bottom: 16px;
}
.ai-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.ai-assist-header > div:nth-child(2) {
  flex: 1;
}
.ai-assist-header strong {
  font-size: 15px;
  color: #0f172a;
  display: block;
  margin-bottom: 4px;
}
.ai-assist-header p {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}
.ai-card {
  margin-bottom: 14px;
  border-radius: 12px;
}
.ai-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1e293b;
}
.ai-card-header .el-icon {
  color: #3b82f6;
}
.ai-section {
  margin-bottom: 14px;
}
.ai-section:last-child {
  margin-bottom: 0;
}
.ai-section-title {
  font-size: 13px;
  color: #475569;
  margin-bottom: 8px;
  font-weight: 500;
}
.ai-highlight {
  font-size: 18px;
  font-weight: 700;
  color: #2563eb;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.step-item {
  display: flex;
  gap: 12px;
}
.step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #dbeafe;
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-content {
  flex: 1;
  padding-bottom: 12px;
  border-bottom: 1px dashed #f1f5f9;
}
.step-item:last-child .step-content {
  border-bottom: none;
  padding-bottom: 0;
}
.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}
.step-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
  line-height: 1.6;
}
.step-meta {
  display: flex;
  gap: 8px;
}

.resource-list, .notice-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.resource-list li, .notice-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: #334155;
  border-bottom: 1px solid #f8fafc;
}
.resource-list li:last-child, .notice-list li:last-child {
  border-bottom: none;
}
.resource-list .el-icon {
  color: #22c55e;
  margin-top: 2px;
  flex-shrink: 0;
}
.notice-list .el-icon {
  color: #3b82f6;
  margin-top: 2px;
  flex-shrink: 0;
}

.regulation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.regulation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 13px;
  color: #334155;
}

.ai-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
