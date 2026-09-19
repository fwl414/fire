<template>
  <div>
    <div class="title-row">
      <div>
        <div class="page-title">系统通知中心</div>
        <p class="subtitle">高风险隐患、工单逾期、待复查任务、硬件报警和报告生成提醒集中展示。</p>
      </div>
      <div class="actions"><el-button @click="load">刷新</el-button><el-button type="primary" @click="markAllRead">全部已读</el-button></div>
    </div>

    <el-row :gutter="12" class="summary-row">
      <el-col :xs="24" :sm="8"><div class="summary-card"><span>未读通知</span><strong>{{ summary.unread || 0 }}</strong><small>需要处理或确认</small></div></el-col>
      <el-col :xs="24" :sm="8"><div class="summary-card warning"><span>高优先级</span><strong>{{ summary.high_priority || 0 }}</strong><small>高风险 / 已逾期</small></div></el-col>
      <el-col :xs="24" :sm="8"><div class="summary-card danger"><span>待处理</span><strong>{{ summary.pending || 0 }}</strong><small>工单和硬件事件</small></div></el-col>
    </el-row>

    <el-card class="card">
      <template #header>
        <div class="header-row"><strong>通知列表</strong><el-radio-group v-model="filter" size="small" @change="load"><el-radio-button label="all">全部</el-radio-button><el-radio-button label="danger">高风险</el-radio-button><el-radio-button label="warning">预警</el-radio-button><el-radio-button label="info">普通</el-radio-button></el-radio-group></div>
      </template>
      <div class="notification-list">
        <div v-for="n in filtered" :key="n.id" class="notification-card" :class="n.level">
          <div class="n-head"><strong>{{ n.title }}</strong><el-tag :type="tagType(n.level)">{{ n.level_text }}</el-tag></div>
          <p>{{ n.content }}</p><div class="state-line">{{ n.state_snapshot }} · {{ n.next_action }}</div>
          <div class="n-meta"><span>{{ n.source }} · {{ n.created_at }}</span><el-button type="primary" link @click="go(n)">查看来源</el-button></div>
        </div>
      </div>
      <el-empty v-if="!filtered.length" description="暂无符合条件的通知" />
    </el-card>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api'
const router = useRouter()
const summary = ref({})
const items = ref([])
const filter = ref('all')
const filtered = computed(() => filter.value === 'all' ? items.value : items.value.filter(i => i.level === filter.value))
function tagType(level) { return level === 'danger' ? 'danger' : level === 'warning' ? 'warning' : level === 'success' ? 'success' : 'info' }
async function load() { 
  try {
    summary.value = (await request.get('/api/notifications/summary')).data || {}
    items.value = (await request.get('/api/notifications', { params: { limit: 200 } })).data.items || []
  } catch (e) {
    // 失败就呈现空态。以前这里会塞回 2024-01-15 的演示通知，把真实故障藏起来：
    // 页面看着有 3 条未读，其实一条都没取到。错误提示由请求拦截器统一给出。
    summary.value = {}
    items.value = []
  }
}
async function markAllRead() { 
  try {
    await request.post('/api/notifications/mark-all-read')
    ElMessage.success('已标记为全部已读')
  } catch (e) {
    // 以前这里也弹「已标记为全部已读」（注释写着「前端模拟成功」），失败被伪装成成功
  }
  await load()
}
function go(n) { if (n.link) router.push(n.link) }
onMounted(load)
</script>
<style scoped>
.title-row,.header-row,.n-head,.n-meta{display:flex;justify-content:space-between;align-items:center;gap:12px}.subtitle{color:#64748b;margin:-6px 0 0}.summary-row{margin-bottom:12px}.summary-card{background:#fff;border:1px solid #e2e8f0;border-top:4px solid #2563eb;border-radius:16px;padding:16px}.summary-card.warning{border-top-color:#f59e0b}.summary-card.danger{border-top-color:#ef4444}.summary-card span{color:#64748b}.summary-card strong{display:block;font-size:34px;margin:8px 0}.summary-card small{color:#94a3b8}.notification-list{display:grid;gap:12px}.notification-card{border:1px solid #e2e8f0;border-left:4px solid #94a3b8;border-radius:16px;padding:14px;background:#fff}.notification-card.danger{border-left-color:#ef4444;background:#fffafa}.notification-card.warning{border-left-color:#f59e0b;background:#fffaf2}.notification-card p{color:#475569;line-height:1.7}.state-line{display:inline-block;margin-bottom:8px;padding:4px 8px;border-radius:999px;background:#f1f5f9;color:#64748b;font-size:12px}.n-meta span{color:#94a3b8;font-size:12px}
</style>
