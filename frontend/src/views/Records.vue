<template>
  <div class="records-page">
    <div class="title-row">
      <div><div class="page-title">巡检报告与档案</div><p class="subtitle">档案编号、来源类型、风险等级章、操作日志、报告验真、图片证据和整改闭环集中管理。</p></div>
    </div>

    <el-row :gutter="12" class="metric-row">
      <el-col :xs="24" :sm="12" :md="6"><div class="metric-card blue"><span>巡检档案</span><strong>{{ dashboard.archive_count || 0 }}</strong><small>已归档记录</small></div></el-col>
      <el-col :xs="24" :sm="12" :md="6"><div class="metric-card green"><span>报告数量</span><strong>{{ dashboard.report_count || 0 }}</strong><small>可打印 / 验真</small></div></el-col>
      <el-col :xs="24" :sm="12" :md="6"><div class="metric-card red"><span>高风险档案</span><strong>{{ dashboard.high_risk_count || 0 }}</strong><small>建议重点复查</small></div></el-col>
      <el-col :xs="24" :sm="12" :md="6"><div class="metric-card orange"><span>闭环率</span><strong>{{ dashboard.closed_loop_rate || 0 }}%</strong><small>{{ dashboard.closed_workorder_count || 0 }}/{{ dashboard.workorder_count || 0 }} 工单</small></div></el-col>
    </el-row>

    <el-card class="card filter-card">
      <template #header><div class="header-row"><strong>档案筛选</strong><el-button @click="load">刷新</el-button></div></template>
      <el-form :inline="true" :model="filters">
        <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="地点 / 隐患 / 报告编号" clearable style="width:220px" @keyup.enter="load" /></el-form-item>
        <el-form-item label="风险等级"><el-select v-model="filters.risk_level" clearable placeholder="全部" style="width:140px"><el-option label="低风险" value="低风险"/><el-option label="中风险" value="中风险"/><el-option label="高风险" value="高风险"/><el-option label="严重风险" value="严重风险"/></el-select></el-form-item>
        <el-form-item label="复查状态"><el-select v-model="filters.review_status" clearable placeholder="全部" style="width:150px"><el-option label="待复查" value="待复查"/><el-option label="持续跟踪" value="持续跟踪"/><el-option label="已复查" value="已复查"/><el-option label="已通过" value="已通过"/></el-select></el-form-item>
        <el-form-item><el-button type="primary" @click="load">查询</el-button><el-button @click="resetFilters">重置</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card class="card">
      <template #header><div class="header-row"><strong>巡检档案列表</strong><span class="muted">共 {{ archives.length }} 条</span></div></template>
      <VirtualTable :data="archives" :total="archives.length" :loading="loading" :table-height="500">
        <el-table-column prop="created_at" label="巡检时间" width="170" />
        <el-table-column prop="report_no" label="报告编号" width="200" show-overflow-tooltip />
        <el-table-column prop="location" label="地点" width="160" show-overflow-tooltip />
        <el-table-column prop="risk_level" label="风险等级" width="110"><template #default="{row}"><el-tag :type="riskTag(row.risk_level)">{{ row.risk_level }}</el-tag></template></el-table-column>
        <el-table-column prop="risk_score" label="评分" width="80" />
        <el-table-column prop="hazard_count" label="隐患" width="70" />
        <el-table-column prop="workorder_count" label="工单" width="70" />
        <el-table-column prop="closed_loop_rate" label="闭环率" width="90"><template #default="{row}">{{ row.closed_loop_rate || 0 }}%</template></el-table-column>
        <el-table-column prop="review_status" label="复查状态" width="110"><template #default="{row}"><el-tag :type="reviewTag(row.review_status)">{{ row.review_status }}</el-tag></template></el-table-column>
        <el-table-column prop="description" label="现场描述" min-width="240" show-overflow-tooltip />
        <el-table-column label="操作" width="260" fixed="right"><template #default="{row}"><el-button size="small" @click="openDetail(row.id)">详情</el-button><el-button size="small" type="primary" @click="printReport(row.id)">报告</el-button><el-button size="small" @click="verify(row)">验真</el-button></template></el-table-column>
      </VirtualTable>
      <el-empty v-if="!archives.length" description="暂无巡检档案。请先在巡检页面完成分析。" />
    </el-card>

    <el-drawer v-model="drawerVisible" title="巡检档案详情" size="76%">
      <template v-if="detail.id">
        <div class="detail-head">
          <div><h2>{{ detail.location || '未填写地点' }}</h2><p class="muted">档案编号：{{ detail.id }} ｜ 报告编号：{{ detail.report_no || '-' }}</p></div>
          <div class="detail-actions"><el-button @click="verify(detail)">报告验真</el-button><el-button @click="printReport(detail.id)">打印报告</el-button><el-button type="primary" @click="downloadMarkdown">导出 Markdown</el-button></div>
        </div>

        <el-row :gutter="12" class="identity-row">
          <el-col :xs="24" :md="6"><div class="identity-card risk"><span>风险等级章</span><strong :class="riskClass(detail.risk_level)">{{ detail.risk_level }}</strong></div></el-col>
          <el-col :xs="24" :md="6"><div class="identity-card"><span>来源类型</span><strong>{{ detail.source_type || '人工巡检' }}</strong></div></el-col>
          <el-col :xs="24" :md="6"><div class="identity-card"><span>报告状态</span><strong>{{ detail.report_status || '已生成' }}</strong></div></el-col>
          <el-col :xs="24" :md="6"><div class="identity-card"><span>闭环状态</span><strong>{{ detail.closure_status || '-' }}</strong></div></el-col>
        </el-row>

        <el-tabs v-model="detailTab">
          <el-tab-pane label="档案概览" name="overview">
            <el-descriptions border :column="2">
              <el-descriptions-item label="巡检时间">{{ detail.created_at }}</el-descriptions-item>
              <el-descriptions-item label="巡检人员">{{ detail.inspector }}</el-descriptions-item>
              <el-descriptions-item label="复查状态">{{ detail.review_status }}</el-descriptions-item>
              <el-descriptions-item label="报告摘要哈希">{{ detail.report_hash }}</el-descriptions-item>
              <el-descriptions-item label="现场描述" :span="2">{{ detail.description || '未填写' }}</el-descriptions-item>
            </el-descriptions>
            <h3>报告完整性检查</h3><div class="check-list"><el-tag v-for="c in detail.quality?.checklist || []" :key="c.label" :type="c.ok ? 'success' : 'warning'" effect="plain">{{ c.ok ? '✓' : '!' }} {{ c.label }}</el-tag></div>
          </el-tab-pane>

          <el-tab-pane label="图片证据链" name="images">
            <el-row :gutter="12">
              <el-col :xs="24" :md="12" v-for="row in imageCompareRows" :key="row.order_id || row.hazard"><div class="compare-card"><h3>{{ row.hazard || '现场图片证据' }}</h3><div class="compare-grid"><div><strong>整改前</strong><p v-for="p in row.before_images" :key="p">{{ p }}</p><el-empty v-if="!row.before_images?.length" description="暂无" /></div><div><strong>整改后 / 复查</strong><p v-for="p in [...(row.after_images||[]), ...(row.review_images||[])]" :key="p">{{ p }}</p><el-empty v-if="!(row.after_images||[]).length && !(row.review_images||[]).length" description="暂无" /></div></div><p class="muted">复查意见：{{ row.review_note || '待补充' }}</p></div></el-col>
            </el-row>
            <el-empty v-if="!imageCompareRows.length" description="暂无图片证据链。" />
          </el-tab-pane>

          <el-tab-pane label="知识库依据" name="rag">
            <el-table :data="detail.rag_references || []" border><el-table-column prop="title" label="标题" width="220"/><el-table-column prop="category" label="分类" width="120"/><el-table-column prop="similarity" label="相似度" width="100"/><el-table-column label="摘要"><template #default="{row}">{{ row.summary || row.content || row.content_preview }}</template></el-table-column></el-table>
          </el-tab-pane>

          <el-tab-pane label="整改工单" name="workorders">
            <el-table :data="detail.workorders || []" border><el-table-column prop="hazard" label="隐患" width="160"/><el-table-column prop="status" label="状态" width="100"/><el-table-column prop="responsible_role" label="责任角色" width="180"/><el-table-column prop="deadline" label="整改时限" width="160"/><el-table-column prop="recommended_action" label="整改建议"/></el-table>
          </el-tab-pane>

          <el-tab-pane label="操作日志" name="logs">
            <el-timeline><el-timeline-item v-for="t in detail.operation_logs || detail.archive_timeline || []" :key="t.title + t.time" :timestamp="t.time"><strong>{{ t.title }}</strong><p>{{ t.content }}</p></el-timeline-item></el-timeline>
          </el-tab-pane>
        </el-tabs>
      </template>
      <el-empty v-else description="请选择一条档案记录。" />
    </el-drawer>
  </div>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../api'
import VirtualTable from '../components/VirtualTable.vue'
const route=useRoute(); const router=useRouter(); const archives=ref([]); const dashboard=ref({}); const filters=ref({keyword:'',risk_level:'',review_status:''}); const drawerVisible=ref(false); const detail=ref({}); const detailTab=ref('overview'); const loading=ref(false)
const imageCompareRows=computed(()=>{ const rows=detail.value.before_after_images||[]; if(rows.length)return rows; const paths=detail.value.image_paths||[]; return paths.length?[{hazard:'现场图片证据',before_images:paths,after_images:[],review_images:[],review_note:''}]:[] })
function riskTag(l){return String(l).includes('高')||String(l).includes('严重')?'danger':String(l).includes('中')?'warning':'success'}
function reviewTag(s){return String(s).includes('复查')?'warning':String(s).includes('通过')?'success':'info'}
function riskClass(l){return riskTag(l)==='danger'?'risk-high':riskTag(l)==='warning'?'risk-mid':'risk-low'}
async function load(){ loading.value=true; try{ dashboard.value=(await request.get('/api/inspection-archives/dashboard')).data; archives.value=(await request.get('/api/inspection-archives',{params:filters.value})).data }finally{ loading.value=false } }
function resetFilters(){ filters.value={keyword:'',risk_level:'',review_status:''}; load() }
async function openDetail(id){ detail.value=(await request.get(`/api/inspection-archives/${id}`)).data; detailTab.value='overview'; drawerVisible.value=true }
function printReport(id){ router.push(`/report-print/${id}`) }
function verify(row){ const no=row.report_no||row.id; window.open(`/report-verify/${no}`,'_blank') }
async function downloadMarkdown(){ const res=await request.get(`/api/reports/enhanced/${detail.value.id}`,{params:{format:'markdown'}}); const blob=new Blob([res.data.content||''],{type:'text/markdown;charset=utf-8'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=res.data.filename||`${detail.value.id}.md`; a.click(); URL.revokeObjectURL(url) }
async function openByQuery(){ await load(); const id=route.query.record_id; if(id) await openDetail(id) }
onMounted(openByQuery)
watch(() => route.query.record_id, openByQuery)
</script>
<style scoped>
.title-row,.header-row,.detail-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.subtitle{margin:-6px 0 0;color:#64748b}.muted{color:#64748b;font-size:13px}.metric-row,.identity-row{margin-bottom:12px}.metric-card,.identity-card{background:#fff;border:1px solid #e2e8f0;border-top:4px solid #2563eb;border-radius:16px;padding:14px}.metric-card.green{border-top-color:#22c55e}.metric-card.red{border-top-color:#ef4444}.metric-card.orange{border-top-color:#f59e0b}.metric-card span,.identity-card span{color:#64748b}.metric-card strong{display:block;font-size:34px;margin:8px 0}.metric-card small{color:#94a3b8}.detail-head h2{margin:0}.detail-actions{display:flex;gap:8px}.identity-card strong{display:block;font-size:22px;margin-top:8px}.identity-card.risk strong{font-size:28px}.risk-high{color:#dc2626}.risk-mid{color:#d97706}.risk-low{color:#16a34a}.check-list{display:flex;gap:8px;flex-wrap:wrap}.compare-card{border:1px solid #e2e8f0;border-radius:16px;padding:14px;background:#fff;margin-bottom:12px}.compare-card h3{margin-top:0}.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.compare-grid>div{border:1px dashed #cbd5e1;border-radius:12px;padding:12px;background:#f8fafc}.compare-grid p{color:#475569;line-height:1.6}
</style>
