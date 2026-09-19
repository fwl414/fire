<template>
  <div>
    <div class="page-title">消防学习</div>

    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :span="6"><div class="metric"><span>题库题量</span><strong>{{ sourceSummary.merged_question_count || overview.quiz_count || 0 }}</strong></div></el-col>
      <el-col :span="6"><div class="metric"><span>当前题组</span><strong>{{ filteredQuiz.length }}</strong></div></el-col>
      <el-col :span="6"><div class="metric"><span>已答题</span><strong>{{ practiceRecords.length }}</strong></div></el-col>
      <el-col :span="6"><div class="metric"><span>正确率</span><strong>{{ accuracy }}%</strong></div></el-col>
    </el-row>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="刷题练习" name="quiz">
        <el-row :gutter="12">
          <el-col :span="5">
            <el-card class="card filter-card">
              <template #header>考试分类</template>
              <el-select v-model="selectedCategory" placeholder="资格方向" style="width:100%;margin-bottom:10px" @change="reloadQuiz">
                <el-option label="全部" value="" />
                <el-option v-for="c in filterOptions.categories" :key="c" :label="c" :value="c" />
              </el-select>
              <el-select v-model="selectedLevel" placeholder="等级" style="width:100%;margin-bottom:10px" @change="reloadQuiz">
                <el-option label="全部" value="" />
                <el-option v-for="l in filterOptions.levels" :key="l" :label="l" :value="l" />
              </el-select>
              <el-segmented v-model="selectedSubject" :options="subjectOptions" block @change="reloadQuiz" style="margin-bottom:10px" />
              <el-select v-model="selectedModule" placeholder="模块" style="width:100%;margin-bottom:10px" filterable @change="reloadQuiz">
                <el-option label="全部模块" value="" />
                <el-option v-for="m in filterOptions.modules" :key="m" :label="m" :value="m" />
              </el-select>
              <el-button style="width:100%;margin-bottom:10px" @click="shuffleQuiz">随机组题</el-button>
              <el-button style="width:100%" @click="clearFilter">清空筛选</el-button>
            </el-card>

            <el-card class="card">
              <template #header>答题卡</template>
              <div class="answer-grid">
                <button
                  v-for="(q, idx) in pageQuestions"
                  :key="q.id"
                  :class="['answer-dot', idx + pageStart === currentIndex ? 'current' : '', answerResults[q.id] ? (answerResults[q.id].is_correct ? 'correct' : 'wrong') : '']"
                  @click="goQuestion(idx + pageStart)"
                >
                  {{ idx + pageStart + 1 }}
                </button>
              </div>
              <div class="pager-row">
                <el-button size="small" @click="cardPrevPage">上一页</el-button>
                <span>{{ cardPage + 1 }} / {{ cardTotalPages }}</span>
                <el-button size="small" @click="cardNextPage">下一页</el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :span="13">
            <el-card class="card quiz-main">
              <template #header>
                <div class="header-row">
                  <strong>{{ selectedSubject || '全部科目' }} · {{ currentQuestion?.module || '-' }}</strong>
                  <span>{{ currentIndex + 1 }} / {{ filteredQuiz.length }}</span>
                </div>
              </template>

              <div v-if="currentQuestion">
                <div class="quiz-meta">
                  <el-tag>{{ currentQuestion.exam_category }}</el-tag>
                  <el-tag type="info">{{ currentQuestion.exam_level }}</el-tag>
                  <el-tag type="danger">{{ currentQuestion.exam_subject || '理论考试' }}</el-tag>
                  <el-tag type="warning">{{ currentQuestion.module }}</el-tag>
                  <el-tag type="success">{{ currentQuestion.source_type }}</el-tag>
                </div>

                <h2 class="question-title">{{ currentQuestion.question }}</h2>

                <el-radio-group v-if="currentQuestion.question_type !== 'multiple_choice'" v-model="answers[currentQuestion.id]" class="option-group">
                  <el-radio v-for="(text, key) in currentQuestion.options" :key="key" :label="key" class="option-item">
                    {{ key }}. {{ text }}
                  </el-radio>
                </el-radio-group>

                <el-checkbox-group v-else v-model="multiAnswers[currentQuestion.id]" class="option-group">
                  <el-checkbox v-for="(text, key) in currentQuestion.options" :key="key" :label="key" class="option-item">
                    {{ key }}. {{ text }}
                  </el-checkbox>
                </el-checkbox-group>

                <div class="quiz-actions">
                  <el-button @click="prevQuestion">上一题</el-button>
                  <el-button type="primary" @click="submitAnswer(currentQuestion.id)">提交答案</el-button>
                  <el-button type="success" @click="nextQuestion">下一题</el-button>
                  <el-button @click="toggleFavorite(currentQuestion)">收藏</el-button>
                  <el-button @click="randomNextQuestion">随机</el-button>
                </div>

                <el-alert
                  v-if="answerResults[currentQuestion.id]"
                  :title="answerResults[currentQuestion.id].is_correct ? '回答正确' : `回答错误，正确答案：${answerResults[currentQuestion.id].correct_answer}`"
                  :type="answerResults[currentQuestion.id].is_correct ? 'success' : 'error'"
                  show-icon
                  style="margin-top:12px"
                >
                  <div>{{ answerResults[currentQuestion.id].analysis }}</div>
                </el-alert>
              </div>
              <el-empty v-else description="当前筛选条件下没有题目，请清空筛选或切换考试科目。" />
            </el-card>

            <el-card v-if="agentFeedback" class="card">
              <template #header>学习 Agent 解析</template>
              <el-alert :title="agentFeedback.explainable_summary" type="info" show-icon style="margin-bottom:12px" />
              <p class="section-tip">{{ agentFeedback.diagnosis }}</p>
              <el-table :data="agentFeedback.agent_tool_calls || []" border>
                <el-table-column prop="tool" label="工具" width="180" />
                <el-table-column prop="type" label="类型" width="120" />
                <el-table-column prop="result" label="调用结果" />
              </el-table>
            </el-card>
          </el-col>

          <el-col :span="6">
            <el-card class="card">
              <template #header>练习统计</template>
              <div class="stat-row"><span>考试科目</span><b>{{ selectedSubject || '全部' }}</b></div>
              <div class="stat-row"><span>进度</span><b>{{ currentIndex + 1 }} / {{ filteredQuiz.length }}</b></div>
              <div class="stat-row"><span>已答</span><b>{{ practiceRecords.length }}</b></div>
              <div class="stat-row"><span>答对</span><b>{{ correctCount }}</b></div>
              <div class="stat-row"><span>收藏</span><b>{{ favorites.length }}</b></div>
              <div class="stat-row"><span>错题</span><b>{{ wrongRecords.length }}</b></div>
              <el-progress :percentage="progressPercent" style="margin-top:10px" />
              <el-button type="primary" style="width:100%;margin-top:12px" :loading="analyzing" @click="analyzeProgress">
                智能模型学习分析
              </el-button>
            </el-card>

            <el-card v-if="analysis" class="card">
              <template #header>智能学习建议</template>
              <pre class="answer">{{ analysis.llm_advice || analysis.advice }}</pre>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="考试科目" name="subjects">
        <el-row :gutter="12">
          <el-col :span="12" v-for="item in examSubjects" :key="item.exam_level + item.exam_category">
            <el-card class="card">
              <template #header>{{ item.exam_category }} · {{ item.exam_level }}</template>
              <el-card v-for="s in item.subjects" :key="s.name" shadow="never" style="margin-bottom:12px">
                <h3>{{ s.name }}</h3>
                <p>{{ s.description }}</p>
                <el-tag v-for="m in s.modules" :key="m" style="margin:0 6px 6px 0">{{ m }}</el-tag>
              </el-card>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- lazy：图表要等页签真正显示出来再挂载，否则 ECharts 会按 0 尺寸初始化 -->
      <el-tab-pane label="知识图谱/RAG" name="graph" lazy>
        <el-card class="card" style="margin-bottom: 12px">
          <template #header>
            <div class="graph-card-header">
              <span>学习知识图谱（节点 {{ graph.node_count || 0 }} · 关系 {{ graph.edge_count || 0 }}）</span>
              <span class="graph-card-tip">
                图中展示全部模块/知识点/课程与前 {{ graphShownQuestions }} 个题目节点，
                <router-link to="/knowledge-graph">打开完整图谱（含业务实体）</router-link>
              </span>
            </div>
          </template>
          <EChart v-if="graphOption.series" :option="graphOption" height="520px" />
          <el-empty v-else description="暂无图谱数据" />
        </el-card>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-card class="card">
              <template #header>学习知识图谱概览</template>
              <div class="stat-row"><span>节点数</span><b>{{ graph.node_count }}</b></div>
              <div class="stat-row"><span>关系数</span><b>{{ graph.edge_count }}</b></div>
              <div class="stat-row"><span>题目数</span><b>{{ graph.question_count }}</b></div>
              <p class="section-tip">{{ graph.explanation }}</p>
            </el-card>
            <el-card class="card">
              <template #header>高频模块</template>
              <div v-for="m in graph.top_modules || []" :key="m.name" class="bar-row">
                <span>{{ m.name }}</span>
                <b>{{ m.count }}</b>
              </div>
            </el-card>
          </el-col>
          <el-col :span="16">
            <el-card class="card">
              <template #header>学习 RAG 检索</template>
              <el-input v-model="ragQuery" placeholder="输入知识点、题目关键词，例如：灭火器 压力表 有效期" @keyup.enter="searchRag">
                <template #append><el-button @click="searchRag">检索</el-button></template>
              </el-input>
              <el-alert v-if="ragResult.summary" :title="ragResult.summary" type="info" show-icon style="margin:12px 0" />
              <el-table :data="ragResult.question_results || []" border height="460">
                <el-table-column prop="score" label="得分" width="70" />
                <el-table-column prop="exam_subject" label="科目" width="100" />
                <el-table-column prop="module" label="模块" width="130" />
                <el-table-column prop="topic" label="知识点" width="140" />
                <el-table-column prop="question" label="相关题目" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>


<el-tab-pane label="错题本/学习画像" name="profile">
  <el-row :gutter="12">
    <el-col :span="6"><div class="metric"><span>累计答题</span><strong>{{ learningProfile.total || 0 }}</strong></div></el-col>
    <el-col :span="6"><div class="metric"><span>答对</span><strong>{{ learningProfile.correct || 0 }}</strong></div></el-col>
    <el-col :span="6"><div class="metric"><span>错题</span><strong>{{ learningProfile.wrong || 0 }}</strong></div></el-col>
    <el-col :span="6"><div class="metric"><span>正确率</span><strong>{{ learningProfile.accuracy || 0 }}%</strong></div></el-col>
  </el-row>

  <el-card class="card">
    <template #header>学习建议</template>
    <el-alert :title="learningProfile.advice || '完成刷题后将生成学习建议。'" type="info" show-icon />
  </el-card>

  <el-row :gutter="12">
    <el-col :span="10">
      <el-card class="card">
        <template #header>薄弱模块</template>
        <el-table :data="learningProfile.weak_modules || []" border>
          <el-table-column prop="module" label="模块" />
          <el-table-column prop="wrong_count" label="错题数" width="100" />
        </el-table>
      </el-card>
    </el-col>
    <el-col :span="14">
      <el-card class="card">
        <template #header>错题本</template>
        <el-table :data="wrongbook" border height="420">
          <el-table-column prop="module" label="模块" width="130" />
          <el-table-column prop="question" label="题目" />
          <el-table-column prop="user_answer" label="你的答案" width="90" />
          <el-table-column prop="correct_answer" label="正确答案" width="90" />
        </el-table>
      </el-card>
    </el-col>
  </el-row>
</el-tab-pane>

      <el-tab-pane label="题库来源" name="sources">
        <el-card class="card">
          <template #header>题库导入概览</template>
          <el-descriptions border :column="2">
            <el-descriptions-item label="合并后题目数">{{ sourceSummary.merged_question_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="补充导入">{{ sourceSummary.supplement_parsed_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="考试科目">{{ (sourceSummary.exam_subjects || []).join('、') }}</el-descriptions-item>
            <el-descriptions-item label="说明">{{ sourceSummary.note || '-' }}</el-descriptions-item>
          </el-descriptions>
          <h3>资料文件</h3>
          <el-table :data="sourceDocs" border>
            <el-table-column prop="group" label="类别" width="150" />
            <el-table-column prop="name" label="文件名" min-width="260" />
            <el-table-column prop="parsed_question_count" label="解析题数" width="100" />
            <el-table-column prop="description" label="说明" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue"
import request from "../api"
import { ElMessage } from "element-plus"
import EChart from "../components/EChart.vue"

const activeTab = ref("quiz")
const overview = ref({})
const sourceSummary = ref({})
const sourceDocs = ref([])
const examSubjects = ref([])
const filterOptions = ref({ categories: [], levels: [], subjects: [], modules: [] })
const selectedCategory = ref("消防设施操作员")
const selectedLevel = ref("中级")
const selectedSubject = ref("理论考试")
const selectedModule = ref("")
const filteredQuiz = ref([])
const answers = ref({})
const multiAnswers = ref({})
const answerResults = ref({})
const practiceRecords = ref([])
const favorites = ref([])
const analysis = ref(null)
const agentFeedback = ref(null)
const analyzing = ref(false)
const currentIndex = ref(0)
const cardPage = ref(0)
const cardPageSize = 50
const graph = ref({})
const ragQuery = ref("灭火器 压力表 有效期")
const ragResult = ref({})
const learningProfile = ref({})
const wrongbook = ref([])

const subjectOptions = computed(() => ["理论考试", "实操考试", "全部科目"])
const currentQuestion = computed(() => filteredQuiz.value[currentIndex.value] || null)
const correctCount = computed(() => practiceRecords.value.filter(r => r.is_correct).length)
const wrongRecords = computed(() => practiceRecords.value.filter(r => !r.is_correct))
const accuracy = computed(() => !practiceRecords.value.length ? 0 : Math.round(correctCount.value / practiceRecords.value.length * 100))
const progressPercent = computed(() => !filteredQuiz.value.length ? 0 : Math.round((currentIndex.value + 1) / filteredQuiz.value.length * 100))
const cardTotalPages = computed(() => Math.max(1, Math.ceil(filteredQuiz.value.length / cardPageSize)))
const pageStart = computed(() => cardPage.value * cardPageSize)
const pageQuestions = computed(() => filteredQuiz.value.slice(pageStart.value, pageStart.value + cardPageSize))

const load = async () => {
  overview.value = (await request.get("/api/learning/overview")).data
  sourceSummary.value = (await request.get("/api/learning/source-summary")).data
  sourceDocs.value = (await request.get("/api/learning/source-docs")).data
  examSubjects.value = (await request.get("/api/learning/exam-subjects")).data
  filterOptions.value = (await request.get("/api/learning/filter-options")).data
  await reloadQuiz()
  await loadGraph()
  await loadLearningProfile()
}

const reloadQuiz = async () => {
  const res = await request.get("/api/learning/quiz", {
    params: {
      limit: 3000,
      exam_category: selectedCategory.value,
      exam_level: selectedLevel.value,
      exam_subject: selectedSubject.value === "全部科目" ? "" : selectedSubject.value,
      module: selectedModule.value
    }
  })
  filteredQuiz.value = res.data || []
  currentIndex.value = 0
  cardPage.value = 0
  agentFeedback.value = null
}

const clearFilter = async () => {
  selectedCategory.value = ""
  selectedLevel.value = ""
  selectedSubject.value = "全部科目"
  selectedModule.value = ""
  await reloadQuiz()
}

const shuffleQuiz = () => {
  filteredQuiz.value = [...filteredQuiz.value].sort(() => Math.random() - 0.5)
  currentIndex.value = 0
  cardPage.value = 0
  agentFeedback.value = null
}

const goQuestion = idx => {
  currentIndex.value = idx
  agentFeedback.value = null
}
const cardPrevPage = () => { if (cardPage.value > 0) cardPage.value-- }
const cardNextPage = () => { if (cardPage.value < cardTotalPages.value - 1) cardPage.value++ }

const prevQuestion = () => {
  if (!filteredQuiz.value.length) return
  currentIndex.value = (currentIndex.value - 1 + filteredQuiz.value.length) % filteredQuiz.value.length
  cardPage.value = Math.floor(currentIndex.value / cardPageSize)
  agentFeedback.value = null
}
const nextQuestion = () => {
  if (!filteredQuiz.value.length) return
  currentIndex.value = (currentIndex.value + 1) % filteredQuiz.value.length
  cardPage.value = Math.floor(currentIndex.value / cardPageSize)
  agentFeedback.value = null
}
const randomNextQuestion = () => {
  if (!filteredQuiz.value.length) return
  currentIndex.value = Math.floor(Math.random() * filteredQuiz.value.length)
  cardPage.value = Math.floor(currentIndex.value / cardPageSize)
  agentFeedback.value = null
}
const toggleFavorite = q => {
  const i = favorites.value.findIndex(x => x.id === q.id)
  if (i >= 0) favorites.value.splice(i, 1)
  else favorites.value.push(q)
}

const submitAnswer = async (id) => {
  const q = filteredQuiz.value.find(x => x.id === id) || {}
  const userAnswer = q.question_type === "multiple_choice"
    ? (multiAnswers.value[id] || []).sort().join(",")
    : (answers.value[id] || "")

  const res = await request.post("/api/learning/quiz/submit", {
    question_id: id,
    user_answer: userAnswer
  })
  answerResults.value[id] = res.data

  const record = {
    question_id: id,
    user_answer: userAnswer,
    is_correct: res.data.is_correct,
    topic: res.data.topic || q.topic,
    exam_category: q.exam_category,
    exam_level: q.exam_level,
    exam_subject: q.exam_subject,
    module: q.module,
    analysis: res.data.analysis,
  }
  const index = practiceRecords.value.findIndex(r => r.question_id === id)
  if (index >= 0) practiceRecords.value[index] = record
  else practiceRecords.value.push(record)

  await request.post("/api/learning/attempts", {
    question_id: id,
    question: q,
    user_answer: userAnswer,
    is_correct: res.data.is_correct,
    submit_result: res.data
  })
  await loadLearningProfile()

  const feedback = await request.post("/api/learning/quiz/agent-feedback", {
    question_id: id,
    submit_result: res.data,
    recent_records: practiceRecords.value
  })
  agentFeedback.value = feedback.data
}

const analyzeProgress = async () => {
  analyzing.value = true
  try {
    const res = await request.post("/api/learning/progress/analyze", {
      records: practiceRecords.value,
      use_llm: true
    })
    analysis.value = res.data
  } finally {
    analyzing.value = false
  }
}

const loadLearningProfile = async () => {
  learningProfile.value = (await request.get("/api/learning/profile")).data
  wrongbook.value = (await request.get("/api/learning/wrongbook")).data
}

const loadGraph = async () => {
  graph.value = (await request.get("/api/learning/knowledge-graph", { params: { limit_questions: 80 } })).data
}

// 图谱可视化：改造前这个页签只显示了 3 个数字，接口返回的 nodes/edges 从没画出来过。
// 题目节点太多会把力导向图糊成一团，这里只取前 VISIBLE_QUESTION_NODES 个题目，
// 其余类型（资格方向/等级/模块/知识点/课程）全量展示。
const VISIBLE_QUESTION_NODES = 20
const GRAPH_TYPE_COLORS = {
  资格方向: "#2563eb",
  等级: "#0ea5e9",
  模块: "#22c55e",
  知识点: "#f59e0b",
  题目: "#8b5cf6",
  课程: "#ec4899",
}

const graphOption = computed(() => {
  const allNodes = graph.value?.nodes || []
  const allEdges = graph.value?.edges || []
  if (!allNodes.length) return {}

  const questionNodes = allNodes.filter(node => node.type === "题目")
  const keptQuestions = questionNodes.slice(0, VISIBLE_QUESTION_NODES)
  const others = allNodes.filter(node => node.type !== "题目")
  const kept = [...others, ...keptQuestions]

  // ECharts 要求节点 name/id 全局唯一，重名会直接报错导致整张图不渲染。
  // 学习图谱里确实存在重名（同一知识点挂在多个模块下、等级名在不同方向下重复），
  // 这里按出现顺序给重名节点加后缀，并用下标作为稳定键（不依赖接口的 id 是否唯一）。
  const names = new Map()
  const used = new Map()
  kept.forEach((node, index) => {
    const base = String(node.label || node.id).slice(0, 24)
    const seen = used.get(base) || 0
    used.set(base, seen + 1)
    names.set(index, seen === 0 ? base : `${base} #${index}`)
  })
  const indexById = new Map()
  kept.forEach((node, index) => {
    if (!indexById.has(node.id)) indexById.set(node.id, index)
  })

  const categories = [...new Set(kept.map(node => node.type))]
  const categoryIndex = Object.fromEntries(categories.map((name, index) => [name, index]))
  const links = allEdges
    .filter(edge => indexById.has(edge.source) && indexById.has(edge.target))
    .map(edge => ({
      source: names.get(indexById.get(edge.source)),
      target: names.get(indexById.get(edge.target)),
      value: edge.relation,
    }))

  return {
    tooltip: {},
    legend: [{ data: categories, top: 0, type: "scroll" }],
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        top: 30,
        categories: categories.map(name => ({ name })),
        force: { repulsion: 200, edgeLength: [60, 130], gravity: 0.08 },
        label: { show: true, position: "right", fontSize: 11, formatter: "{b}" },
        labelLayout: { hideOverlap: true },
        lineStyle: { color: "source", curveness: 0.08, opacity: 0.5 },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 5,
        data: kept.map((node, index) => ({
          name: names.get(index),
          category: categoryIndex[node.type],
          symbolSize: 14 + Math.min(22, Math.sqrt(node.count || 1) * 4),
          itemStyle: { color: GRAPH_TYPE_COLORS[node.type] || "#94a3b8" },
        })),
        links,
      },
    ],
  }
})

const graphShownQuestions = computed(() =>
  Math.min(VISIBLE_QUESTION_NODES, (graph.value?.nodes || []).filter(node => node.type === "题目").length)
)
const searchRag = async () => {
  ragResult.value = (await request.get("/api/learning/rag-search", {
    params: { query: ragQuery.value, limit: 10 }
  })).data
}

onMounted(load)
</script>

<style scoped>
.metric {
  background:#fff;
  border:1px solid #e2e8f0;
  border-radius:12px;
  padding:14px;
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.metric strong { font-size:28px; color:#2563eb; }
.card { margin-bottom:12px; }
.filter-card :deep(.el-segmented) { width:100%; }
.quiz-main { min-height:560px; }
.quiz-meta { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }
.question-title { font-size:24px; line-height:1.5; margin:14px 0 20px; }
.option-group { display:flex; flex-direction:column; gap:12px; }
.option-item {
  border:1px solid #e5e7eb;
  border-radius:12px;
  padding:12px 14px;
  margin-right:0;
  background:#fff;
}
.quiz-actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
.answer-grid {
  display:grid;
  grid-template-columns: repeat(5, 1fr);
  gap:8px;
}
.answer-dot {
  border:1px solid #dcdfe6;
  border-radius:8px;
  padding:7px 0;
  background:#fff;
  cursor:pointer;
}
.answer-dot.current { background:#409eff; color:#fff; border-color:#409eff; }
.answer-dot.correct { background:#f0f9eb; border-color:#67c23a; color:#67c23a; }
.answer-dot.wrong { background:#fef0f0; border-color:#f56c6c; color:#f56c6c; }
.pager-row { display:flex; justify-content:space-between; align-items:center; margin-top:12px; }
.stat-row, .bar-row {
  display:flex;
  justify-content:space-between;
  padding:8px 0;
  border-bottom:1px solid #f1f5f9;
}
.answer {
  white-space:pre-wrap;
  background:#f8fafc;
  border-radius:10px;
  padding:14px;
  line-height:1.8;
  font-family:inherit;
  max-height:360px;
  overflow:auto;
}
.section-tip {
  color:#64748b;
  line-height:1.7;
  background:#f8fafc;
  border:1px solid #e2e8f0;
  border-radius:12px;
  padding:12px 14px;
}
.header-row { display:flex; justify-content:space-between; align-items:center; }
.graph-card-header { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
.graph-card-tip { font-size:12px; color:#64748b; font-weight:400; }
</style>
