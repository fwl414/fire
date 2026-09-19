<template>
  <div class="knowledge-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防知识库</div>
        <p class="subtitle">分类管理 · 引用相似度 · 展开依据 · 新增/编辑/停用 · 检索测试</p>
      </div>
    </div>

    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :xs="12" :md="6"><el-card class="metric-card"><span>知识条目</span><strong>{{ stats.total || 0 }}</strong></el-card></el-col>
      <el-col :xs="12" :md="6"><el-card class="metric-card"><span>启用条目</span><strong>{{ stats.enabled || 0 }}</strong></el-card></el-col>
      <el-col :xs="12" :md="6"><el-card class="metric-card"><span>停用条目</span><strong>{{ stats.disabled || 0 }}</strong></el-card></el-col>
      <el-col :xs="12" :md="6"><el-card class="metric-card"><span>分类数量</span><strong>{{ categoryCount }}</strong></el-card></el-col>
    </el-row>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="知识条目管理" name="manage">
        <el-card class="card">
          <template #header>
            <div class="header-row">
              <strong>知识条目</strong>
              <div class="filter-row">
                <el-select v-model="filters.category" clearable placeholder="按分类筛选" style="width:160px" @change="load">
                  <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
                </el-select>
                <el-select v-model="filters.enabled" clearable placeholder="状态" style="width:110px" @change="load">
                  <el-option label="启用" value="1" />
                  <el-option label="停用" value="0" />
                </el-select>
                <el-input v-model="filters.keyword" clearable placeholder="关键词搜索" style="width:200px" @keyup.enter="localFilter" />
                <el-button @click="localFilter">搜索</el-button>
                <el-button type="primary" @click="newEntry">新增知识</el-button>
              </div>
            </div>
          </template>

          <el-table :data="visibleEntries" border>
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-box">
                  <p><b>来源说明：</b>{{ row.source || '-' }}</p>
                  <p><b>关键词：</b>{{ row.keywords || '-' }}</p>
                  <p><b>正文内容：</b>{{ row.content }}</p>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" width="220" />
            <el-table-column prop="category" label="分类" width="130">
              <template #default="{ row }"><el-tag>{{ row.category || '综合知识' }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="keywords" label="关键词" width="220" show-overflow-tooltip />
            <el-table-column prop="content" label="摘要" show-overflow-tooltip />
            <el-table-column prop="updated_at" label="更新时间" width="160" />
            <el-table-column prop="enabled" label="状态" width="90">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" @change="toggleStatus(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="editEntry(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteEntry(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="检索测试与引用预览" name="search">
        <el-card class="card">
          <template #header>RAG 检索测试</template>
          <el-input v-model="query" placeholder="输入关键词，例如：消防通道堵塞、灭火器遮挡、电气线路杂乱" @keyup.enter="search">
            <template #append><el-button @click="search">检索</el-button></template>
          </el-input>
          <el-row :gutter="12" style="margin-top:12px">
            <el-col :xs="24" :md="8" v-for="r in searchResult.results || []" :key="r.id || r.title">
              <div class="ref-card">
                <div class="header-row"><el-tag>{{ r.category || '知识' }}</el-tag><strong>{{ toPercent(r.score) }}%</strong></div>
                <h3>{{ r.title }}</h3>
                <p>{{ r.content }}</p>
                <div class="muted">来源：{{ r.source || '-' }}</div>
                <div class="kw-line">{{ ((r.matched_keywords || []).join('、')) }}</div>
              </div>
            </el-col>
          </el-row>
          <el-empty v-if="!(searchResult.results || []).length" description="暂无检索结果" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="知识分类统计" name="category">
        <el-card class="card">
          <template #header>分类结构</template>
          <el-row :gutter="12">
            <el-col :xs="12" :md="6" v-for="c in normalizedCategoryStats" :key="c.name">
              <div class="category-card"><strong>{{ c.name }}</strong><span>{{ c.count }} 条</span></div>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="问答输出规范" name="qa-format">
        <el-card class="card">
          <template #header>问答结构</template>
          <el-steps :active="4" finish-status="success" align-center>
            <el-step title="先给结论" />
            <el-step title="再给依据" />
            <el-step title="操作建议" />
            <el-step title="风险提示" />
          </el-steps>
          <el-alert title="该结构会同步应用到问答和巡检建议的引用展示。" type="success" show-icon style="margin-top:16px" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialogVisible" title="知识条目" width="760px">
      <el-form label-width="96px">
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" filterable allow-create style="width:100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词"><el-input v-model="form.keywords" placeholder="用逗号分隔，如：消防通道,堵塞,疏散" /></el-form-item>
        <el-form-item label="来源"><el-input v-model="form.source" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        <el-form-item label="正文内容"><el-input v-model="form.content" type="textarea" rows="8" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" @click="saveEntry">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import request from "../api"

const activeTab = ref("manage")
const stats = ref({})
const entries = ref([])
const visibleEntries = ref([])
const dialogVisible = ref(false)
const query = ref("消防通道堵塞 可燃物堆积")
const searchResult = ref({})
const categories = ref(["消防法规", "消防设施", "疏散通道", "电气火灾", "仓储安全", "应急处置", "巡检标准", "处罚依据"])
const filters = ref({ category: "", enabled: "", keyword: "" })
const form = ref({ title: "", category: "疏散通道", keywords: "", source: "用户维护", content: "", enabled: true })

const categoryCount = computed(() => normalizedCategoryStats.value.length)
const normalizedCategoryStats = computed(() => {
  const fromStats = stats.value.categories || []
  const map = {}
  for (const c of fromStats) map[c.name] = c.count
  for (const c of categories.value) if (!map[c]) map[c] = 0
  return Object.entries(map).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count)
})

const loadCategories = async () => {
  try { categories.value = (await request.get("/api/rag/categories")).data.categories || categories.value } catch {}
}
const load = async () => {
  stats.value = (await request.get("/api/rag/admin/stats")).data
  entries.value = (await request.get("/api/knowledge", { params: { category: filters.value.category, enabled: filters.value.enabled } })).data
  localFilter()
}
const localFilter = () => {
  const kw = filters.value.keyword.trim()
  visibleEntries.value = !kw ? entries.value : entries.value.filter(e => `${e.title} ${e.category} ${e.keywords} ${e.content}`.includes(kw))
}

const newEntry = () => {
  form.value = { title: "", category: "疏散通道", keywords: "", source: "用户维护", content: "", enabled: true }
  dialogVisible.value = true
}
const editEntry = row => { form.value = { ...row }; dialogVisible.value = true }
const saveEntry = async () => {
  if (!form.value.title || !form.value.content) return ElMessage.warning("标题和正文不能为空")
  await request.post("/api/knowledge", form.value)
  ElMessage.success("已保存")
  dialogVisible.value = false
  await load()
}
const deleteEntry = async id => {
  await ElMessageBox.confirm("确认删除该知识条目？", "提示", { type: "warning" })
  await request.delete(`/api/knowledge/${id}`)
  ElMessage.success("已删除")
  await load()
}
const toggleStatus = async row => {
  await request.patch(`/api/knowledge/${row.id}/status`, { enabled: row.enabled })
  ElMessage.success(row.enabled ? "已启用" : "已停用")
  await load()
}
const search = async () => { searchResult.value = (await request.get("/api/rag/admin/search", { params: { query: query.value, limit: 12 } })).data }
const toPercent = score => {
  const n = Number(score || 0)
  if (n <= 1) return Math.round(n * 100)
  return Math.round(n)
}

onMounted(async () => {
  await loadCategories()
  await load()
  await search()
})
</script>

<style scoped>
.title-row { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; }
.subtitle { margin:-4px 0 0; color:#64748b; }
.card { margin-bottom: 12px; }
.metric-card :deep(.el-card__body) { display:flex; justify-content:space-between; align-items:center; }
.metric-card span { color:#64748b; }
.metric-card strong { font-size:28px; color:#2563eb; }
.header-row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.filter-row { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
.expand-box { padding: 10px 36px; color:#475569; line-height:1.8; }
.ref-card { border:1px solid #e5e7eb; border-radius:14px; padding:12px; min-height:230px; margin-bottom:12px; background:#fff; }
.ref-card h3 { margin:10px 0 8px; font-size:16px; }
.ref-card p { color:#475569; line-height:1.7; display:-webkit-box; -webkit-line-clamp:5; -webkit-box-orient:vertical; overflow:hidden; }
.muted { color:#94a3b8; font-size:12px; margin-bottom:6px; }
.kw-line { color:#2563eb; font-size:12px; }
.category-card { border:1px solid #e5e7eb; border-radius:14px; background:#fff; padding:16px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; }
.category-card strong { color:#0f172a; }
.category-card span { color:#2563eb; font-weight:700; }
@media (max-width: 900px) { .header-row { align-items:flex-start; flex-direction:column; } .filter-row { justify-content:flex-start; } }
</style>
