<template>
  <div>
    <div class="page-title">刷题中心</div>

    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :span="6"><el-card class="metric"><span>累计答题</span><strong>{{ profile.total || 0 }}</strong></el-card></el-col>
      <el-col :span="6"><el-card class="metric"><span>正确率</span><strong>{{ profile.accuracy || 0 }}%</strong></el-card></el-col>
      <el-col :span="6"><el-card class="metric"><span>错题数</span><strong>{{ profile.wrong || 0 }}</strong></el-card></el-col>
      <el-col :span="6"><el-card class="metric"><span>收藏题</span><strong>{{ favorites.length }}</strong></el-card></el-col>
    </el-row>

    <el-card class="card">
      <template #header>学习计划</template>
      <el-alert :title="profile.advice || '完成每日练习后，系统会生成学习画像和薄弱知识点建议。'" type="info" show-icon />
      <el-steps :active="2" finish-status="success" align-center style="margin-top:18px">
        <el-step title="每日练习" description="10题" />
        <el-step title="错题复习" description="薄弱模块" />
        <el-step title="模拟考试" description="定时训练" />
        <el-step title="成绩统计" description="学习画像" />
      </el-steps>
    </el-card>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="每日练习" name="daily">
        <el-row :gutter="12">
          <el-col :span="16">
            <el-card class="card">
              <template #header>
                <div class="header-row">
                  <strong>每日练习</strong>
                  <el-button type="primary" @click="loadDaily">换一组</el-button>
                </div>
              </template>
              <el-table :data="dailyQuestions" border height="420">
                <el-table-column prop="exam_subject" label="科目" width="100" />
                <el-table-column prop="module" label="模块" width="140" />
                <el-table-column prop="question" label="题目" />
                <el-table-column label="操作" width="120">
                  <template #default="{ row }">
                    <el-button size="small" @click="favorite(row)">收藏</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card class="card">
              <template #header>今日目标</template>
              <div class="plan-item">完成 10 道练习题</div>
              <div class="plan-item">复习 3 道错题</div>
              <div class="plan-item">学习 1 个薄弱模块</div>
              <el-progress :percentage="Math.min((profile.total || 0) * 10, 100)" style="margin-top:14px" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="章节练习" name="chapter">
        <el-card class="card">
          <template #header>章节模块</template>
          <el-row :gutter="12">
            <el-col :span="6" v-for="m in modules" :key="m">
              <div class="chapter-card" @click="loadByModule(m)">
                <h3>{{ m }}</h3>
                <p>按模块进行专项练习</p>
              </div>
            </el-col>
          </el-row>
          <el-table :data="moduleQuestions" border style="margin-top:12px" height="360">
            <el-table-column prop="module" label="模块" width="150" />
            <el-table-column prop="question" label="题目" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="模拟考试" name="mock">
        <el-card class="card">
          <template #header>
            <div class="header-row">
              <strong>模拟考试</strong>
              <div>
                <el-tag type="warning">倒计时：{{ countdownText }}</el-tag>
                <el-button type="primary" style="margin-left:8px" @click="startMock">开始模拟考试</el-button>
              </div>
            </div>
          </template>
          <el-table :data="mockQuestions" border height="460">
            <el-table-column type="index" label="题号" width="70" />
            <el-table-column prop="exam_subject" label="科目" width="100" />
            <el-table-column prop="question" label="题目" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="错题本" name="wrong">
        <el-card class="card">
          <template #header>错题本</template>
          <el-table :data="wrongbook" border height="480">
            <el-table-column prop="module" label="模块" width="140" />
            <el-table-column prop="question" label="题目" />
            <el-table-column prop="user_answer" label="你的答案" width="100" />
            <el-table-column prop="correct_answer" label="正确答案" width="100" />
            <el-table-column prop="analysis" label="解析" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="收藏题" name="favorite">
        <el-card class="card">
          <template #header>收藏题</template>
          <el-table :data="favorites" border height="480">
            <el-table-column prop="module" label="模块" width="140" />
            <el-table-column prop="question" label="题目" />
            <el-table-column label="操作" width="100">
              <template #default="{ $index }"><el-button size="small" @click="favorites.splice($index,1)">移除</el-button></template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="成绩统计" name="stats">
        <el-row :gutter="12">
          <el-col :span="10">
            <el-card class="card">
              <template #header>薄弱知识点分析</template>
              <el-table :data="profile.weak_modules || []" border>
                <el-table-column prop="module" label="薄弱模块" />
                <el-table-column prop="wrong_count" label="错题数" width="100" />
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="14">
            <el-card class="card">
              <template #header>练习记录</template>
              <el-table :data="profile.latest || []" border height="340">
                <el-table-column prop="created_at" label="时间" width="170" />
                <el-table-column prop="module" label="模块" width="140" />
                <el-table-column prop="is_correct" label="结果" width="90">
                  <template #default="{ row }"><el-tag :type="row.is_correct ? 'success' : 'danger'">{{ row.is_correct ? '正确' : '错误' }}</el-tag></template>
                </el-table-column>
                <el-table-column prop="question" label="题目" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import request from "../api"

const activeTab = ref("daily")
const profile = ref({})
const wrongbook = ref([])
const dailyQuestions = ref([])
const moduleQuestions = ref([])
const mockQuestions = ref([])
const modules = ref([])
const favorites = ref(JSON.parse(localStorage.getItem("fire_favorite_questions") || "[]"))
const countdown = ref(45 * 60)
let timer = null

const countdownText = computed(() => {
  const m = String(Math.floor(countdown.value / 60)).padStart(2, "0")
  const s = String(countdown.value % 60).padStart(2, "0")
  return `${m}:${s}`
})

const loadProfile = async () => {
  profile.value = (await request.get("/api/learning/profile")).data
  wrongbook.value = (await request.get("/api/learning/wrongbook")).data
}

const loadDaily = async () => {
  const res = await request.get("/api/learning/quiz", { params: { limit: 10, exam_level: "中级" } })
  dailyQuestions.value = (res.data || []).sort(() => Math.random() - 0.5).slice(0, 10)
}

const loadOptions = async () => {
  const res = await request.get("/api/learning/filter-options")
  modules.value = (res.data.modules || []).slice(0, 12)
}

const loadByModule = async module => {
  const res = await request.get("/api/learning/quiz", { params: { limit: 20, module } })
  moduleQuestions.value = res.data || []
}

const startMock = async () => {
  countdown.value = 45 * 60
  clearInterval(timer)
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) clearInterval(timer)
  }, 1000)
  const res = await request.get("/api/learning/quiz", { params: { limit: 50, exam_level: "中级" } })
  mockQuestions.value = (res.data || []).sort(() => Math.random() - 0.5).slice(0, 50)
}

const favorite = q => {
  if (!favorites.value.find(x => x.id === q.id)) {
    favorites.value.push(q)
    localStorage.setItem("fire_favorite_questions", JSON.stringify(favorites.value))
    ElMessage.success("已收藏")
  }
}

onMounted(async () => {
  await loadProfile()
  await loadOptions()
  await loadDaily()
})
</script>

<style scoped>
.metric :deep(.el-card__body) { display:flex; justify-content:space-between; align-items:center; }
.metric span { color:#64748b; }
.metric strong { font-size:28px; color:#2563eb; }
.header-row { display:flex; justify-content:space-between; align-items:center; }
.plan-item { padding:10px 0; border-bottom:1px solid #f1f5f9; }
.chapter-card {
  border:1px solid #e2e8f0;
  border-radius:14px;
  padding:14px;
  margin-bottom:12px;
  cursor:pointer;
  min-height:110px;
}
.chapter-card:hover {
  border-color:#409eff;
  box-shadow:0 6px 16px rgba(64,158,255,.15);
}
.chapter-card h3 { margin:0 0 8px; }
.chapter-card p { color:#64748b; }
</style>
