<template>
  <div class="fire-training-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防安全培训</div>
        <p class="subtitle">培训课程 · 培训计划 · 考试考核 · 培训档案 · 全员消防安全教育</p>
      </div>
      <div class="title-actions">
        <el-tag :type="loading ? 'info' : 'success'" effect="dark" size="large">
          <el-icon><Reading /></el-icon>
          {{ loading ? '数据加载中' : '数据已同步' }}
        </el-tag>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Reading /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.course_count ?? '--' }}</div>
            <div class="stat-label">培训课程</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.trained_count ?? '--' }}</div>
            <div class="stat-label">已培训人数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Notebook /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.exam_count ?? '--' }}</div>
            <div class="stat-label">考试场次</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><Medal /></el-icon></div>
          <div class="stat-info">
            <!-- 一条成绩都没有时后端返回 null，界面显示「--」，不拿 0 冒充通过率 -->
            <div class="stat-num">{{ stats.pass_rate === null || stats.pass_rate === undefined ? '--' : `${stats.pass_rate}%` }}</div>
            <div class="stat-label">通过率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'courses' }" @click="activeTab = 'courses'">
          <el-icon><Reading /></el-icon>
          培训课程
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'plans' }" @click="activeTab = 'plans'">
          <el-icon><Calendar /></el-icon>
          培训计划
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'exams' }" @click="activeTab = 'exams'">
          <el-icon><Notebook /></el-icon>
          考试考核
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><Document /></el-icon>
          培训档案
        </div>
      </div>

      <!-- ① 培训课程：只读展示学习模块的真实课程 -->
      <div v-if="activeTab === 'courses'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="courseCategoryFilter" placeholder="课程分类" clearable style="width: 160px">
              <el-option v-for="c in courseCategories" :key="c" :label="c" :value="c" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="courseSearch" placeholder="搜索课程名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button @click="loadCourses">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
        <el-alert
          v-if="!loading && !filteredCourses.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无课程数据"
          description="课程由学习模块统一维护（data/learning/courses.json），本页只读展示，不在此新增课程。"
          style="margin-bottom: 12px"
        />
        <el-row :gutter="14">
          <el-col v-for="c in filteredCourses" :key="c.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="course-card" shadow="hover">
              <div class="course-cover" :style="courseCoverStyle(c.category)">
                <el-icon class="cover-icon"><VideoPlay /></el-icon>
                <div class="course-level">{{ c.level || '未分级' }}</div>
              </div>
              <div class="course-body">
                <div class="course-title">{{ c.title }}</div>
                <div class="course-desc">{{ c.summary }}</div>
                <div class="course-meta">
                  <el-tag size="small" :type="courseCategoryTag(c.category)">{{ c.category }}</el-tag>
                  <span class="course-count">{{ (c.knowledge_points || []).length }} 个知识点</span>
                </div>
              </div>
              <div class="course-footer">
                <span class="course-points">
                  关联视频 {{ (c.related_videos || []).length }} · 关联题目 {{ (c.related_questions || []).length }}
                </span>
                <el-button size="small" type="primary" link @click="openCourseDetail(c)">查看要点</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <!-- ② 培训计划 -->
      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button v-if="canManage" type="primary" @click="openPlanDialog()">
              <el-icon><Plus /></el-icon>
              新建计划
            </el-button>
            <el-select v-model="planStatusFilter" placeholder="计划状态" clearable style="width: 140px">
              <el-option
                v-for="(label, code) in planStatusLabels"
                :key="code"
                :label="label"
                :value="code"
              />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="planSearch" placeholder="搜索计划名称" style="width: 220px" clearable @keyup.enter="loadPlans">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button @click="loadPlans">查询</el-button>
          </div>
        </div>
        <el-table v-loading="plansLoading" :data="plans" stripe style="width: 100%" empty-text="暂无培训计划">
          <el-table-column prop="plan_name" label="计划名称" min-width="200" />
          <el-table-column prop="plan_type" label="培训类型" width="110">
            <template #default="{ row }">
              <el-tag size="small">{{ row.plan_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="target" label="培训对象" width="130" />
          <el-table-column prop="trainer" label="培训讲师" width="100" />
          <el-table-column prop="start_date" label="开始日期" width="115" />
          <el-table-column prop="end_date" label="结束日期" width="115" />
          <el-table-column label="人数（计划/实际）" width="150" align="center">
            <template #default="{ row }">
              {{ row.person_count }} / {{ row.actual_count }}
            </template>
          </el-table-column>
          <el-table-column label="进度" width="150">
            <template #default="{ row }">
              <el-progress
                :percentage="row.progress"
                :stroke-width="8"
                :color="row.progress === 100 ? '#22c55e' : '#3b82f6'"
              />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="planStatusTag(row.status)">
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="canManage" label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPlanDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="planPagination.page"
            v-model:page-size="planPagination.size"
            layout="total, prev, pager, next"
            :total="planPagination.total"
            background
            @current-change="loadPlans"
          />
        </div>
      </div>

      <!-- ③ 考试考核 -->
      <div v-if="activeTab === 'exams'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button v-if="canManage" type="primary" @click="openExamDialog()">
              <el-icon><Plus /></el-icon>
              新建考试
            </el-button>
            <el-select v-model="examStatusFilter" placeholder="考试状态" clearable style="width: 140px">
              <el-option
                v-for="(label, code) in examStatusLabels"
                :key="code"
                :label="label"
                :value="code"
              />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="examSearch" placeholder="搜索考试名称" style="width: 220px" clearable @keyup.enter="loadExams">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button @click="loadExams">查询</el-button>
          </div>
        </div>
        <el-alert
          v-if="!examsLoading && !exams.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无考试场次"
          description="新建考试场次后，参考人数、平均分与及格率会按培训档案里的成绩自动汇总。"
          style="margin-bottom: 12px"
        />
        <el-row :gutter="14">
          <el-col v-for="e in exams" :key="e.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="exam-card" shadow="hover" :class="e.status">
              <div class="exam-header">
                <el-tag size="small" effect="dark" :type="examStatusTag(e.status)">
                  {{ e.status_label }}
                </el-tag>
                <span class="exam-time">{{ e.duration_minutes }} 分钟</span>
              </div>
              <div class="exam-title">{{ e.title }}</div>
              <div class="exam-desc">{{ e.description || '未填写说明' }}</div>
              <div class="exam-info-row">
                <span><el-icon><Document /></el-icon> {{ e.question_count }} 题</span>
                <span><el-icon><User /></el-icon> {{ e.attend_count }} 人已考</span>
              </div>
              <div class="exam-info-row">
                <span><el-icon><Trophy /></el-icon> 平均分 {{ formatScore(e.avg_score) }}</span>
                <span><el-icon><CircleCheck /></el-icon> 及格率 {{ formatRate(e.pass_rate) }}</span>
              </div>
              <div class="exam-info-row">
                <span>及格线 {{ e.pass_score }} 分</span>
                <span>{{ e.start_time || '未安排时间' }}</span>
              </div>
              <div v-if="canManage" class="exam-footer">
                <el-button size="small" type="primary" link @click="openExamDialog(e)">编辑</el-button>
                <el-button size="small" type="danger" link @click="removeExam(e)">删除</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="examPagination.page"
            v-model:page-size="examPagination.size"
            layout="total, prev, pager, next"
            :total="examPagination.total"
            background
            @current-change="loadExams"
          />
        </div>
      </div>

      <!-- ④ 培训档案 -->
      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button v-if="canManage" type="primary" @click="openRecordDialog()">
              <el-icon><Plus /></el-icon>
              新建档案
            </el-button>
            <el-select v-model="recordDeptFilter" placeholder="选择部门" clearable style="width: 140px">
              <el-option v-for="d in departments" :key="d" :label="d" :value="d" />
            </el-select>
            <el-date-picker
              v-model="recordDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 260px"
            />
            <el-button @click="loadRecords">查询</el-button>
          </div>
          <div class="toolbar-right">
            <el-button :loading="exporting" @click="exportRecords">
              <el-icon><Download /></el-icon>
              导出档案
            </el-button>
            <el-input v-model="recordSearch" placeholder="搜索姓名/课程" style="width: 200px" clearable @keyup.enter="loadRecords">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table v-loading="recordsLoading" :data="records" stripe style="width: 100%" empty-text="暂无培训档案">
          <el-table-column prop="trainee_name" label="姓名" width="100" />
          <el-table-column prop="department" label="部门" width="110" />
          <el-table-column label="培训课程" min-width="200">
            <template #default="{ row }">
              {{ row.course_name || row.plan_name || '--' }}
            </template>
          </el-table-column>
          <el-table-column prop="train_date" label="培训日期" width="115" />
          <el-table-column prop="study_hours" label="学时" width="80" align="center" />
          <el-table-column label="考试成绩" width="100" align="center">
            <template #default="{ row }">
              <!-- 没参加考试时成绩为 null，显示「--」而不是 0 分 -->
              <span :class="row.is_passed === null ? '' : (row.is_passed ? 'pass' : 'fail')">
                {{ row.exam_score === null ? '--' : row.exam_score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="是否合格" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="resultTag(row)">
                {{ row.result_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="证书编号" width="150">
            <template #default="{ row }">{{ row.cert_no || '--' }}</template>
          </el-table-column>
          <el-table-column v-if="canManage" label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openRecordDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removeRecord(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="recordPagination.page"
            v-model:page-size="recordPagination.size"
            layout="total, prev, pager, next"
            :total="recordPagination.total"
            background
            @current-change="loadRecords"
          />
        </div>
      </div>
    </el-card>

    <!-- 计划弹窗 -->
    <el-dialog v-model="planDialogVisible" :title="planDialogTitle" width="620px">
      <el-form ref="planFormRef" :model="planForm" :rules="planRules" label-width="100px">
        <el-form-item label="计划名称" prop="plan_name">
          <el-input v-model="planForm.plan_name" placeholder="如：2026年上半年全员消防安全培训" />
        </el-form-item>
        <el-form-item label="培训类型" prop="plan_type">
          <el-select v-model="planForm.plan_type" style="width: 100%">
            <el-option v-for="t in planTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="培训对象">
          <el-input v-model="planForm.target" placeholder="如：全体员工" />
        </el-form-item>
        <el-form-item label="培训讲师">
          <el-input v-model="planForm.trainer" placeholder="如：张教官" />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="planForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="planForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划人数">
          <el-input-number v-model="planForm.person_count" :min="0" style="width: 180px" />
        </el-form-item>
        <el-form-item label="进度">
          <el-slider v-model="planForm.progress" :min="0" :max="100" show-input />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="planForm.status" style="width: 100%">
            <el-option
              v-for="(label, code) in planStatusLabels"
              :key="code"
              :label="label"
              :value="code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="planForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>

    <!-- 考试弹窗 -->
    <el-dialog v-model="examDialogVisible" :title="examDialogTitle" width="620px">
      <el-form ref="examFormRef" :model="examForm" :rules="examRules" label-width="100px">
        <el-form-item label="考试名称" prop="title">
          <el-input v-model="examForm.title" placeholder="如：2026年上半年消防安全知识考试" />
        </el-form-item>
        <el-form-item label="考试说明">
          <el-input v-model="examForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="考试时长">
          <el-input-number v-model="examForm.duration_minutes" :min="1" style="width: 180px" />
          <span class="form-hint">分钟</span>
        </el-form-item>
        <el-form-item label="题目数量">
          <el-input-number v-model="examForm.question_count" :min="0" style="width: 180px" />
        </el-form-item>
        <el-form-item label="及格分">
          <el-input-number v-model="examForm.pass_score" :min="0" style="width: 180px" />
          <span class="form-hint">培训档案按此分数判定合格</span>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="examForm.start_time"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="examForm.status" style="width: 100%">
            <el-option
              v-for="(label, code) in examStatusLabels"
              :key="code"
              :label="label"
              :value="code"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="examDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveExam">保存</el-button>
      </template>
    </el-dialog>

    <!-- 培训档案弹窗 -->
    <el-dialog v-model="recordDialogVisible" :title="recordDialogTitle" width="640px">
      <el-form ref="recordFormRef" :model="recordForm" :rules="recordRules" label-width="100px">
        <el-form-item label="姓名" prop="trainee_name">
          <el-input v-model="recordForm.trainee_name" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="recordForm.department" placeholder="如：安保部" />
        </el-form-item>
        <el-form-item label="所属计划">
          <el-select v-model="recordForm.plan_id" placeholder="可不选" clearable style="width: 100%" @change="onPlanPicked">
            <el-option v-for="p in planOptions" :key="p.id" :label="p.plan_name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="培训课程">
          <el-input v-model="recordForm.course_name" placeholder="选择计划后自动填充，也可手填" />
        </el-form-item>
        <el-form-item label="培训日期">
          <el-date-picker v-model="recordForm.train_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="学时">
          <el-input-number v-model="recordForm.study_hours" :min="0" :precision="1" style="width: 180px" />
        </el-form-item>
        <el-form-item label="考试场次">
          <el-select v-model="recordForm.exam_id" placeholder="可不选" clearable style="width: 100%">
            <el-option v-for="e in examOptions" :key="e.id" :label="`${e.title}（及格 ${e.pass_score} 分）`" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试成绩">
          <el-input-number v-model="recordForm.exam_score" :min="0" :precision="1" style="width: 180px" />
          <span class="form-hint">留空表示还没考试</span>
        </el-form-item>
        <el-form-item label="证书编号">
          <el-input v-model="recordForm.cert_no" placeholder="不合格或未考试可留空" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRecord">保存</el-button>
      </template>
    </el-dialog>

    <!-- 课程要点（只读） -->
    <el-dialog v-model="courseDialogVisible" :title="courseDetail.title || '课程要点'" width="560px">
      <div v-if="courseDetail.title">
        <p class="detail-summary">{{ courseDetail.summary }}</p>
        <div class="detail-section-title">知识点</div>
        <ul class="detail-list">
          <li v-for="(point, idx) in courseDetail.knowledge_points || []" :key="idx">{{ point }}</li>
        </ul>
        <div class="detail-section-title">处置流程</div>
        <ol class="detail-list">
          <li v-for="(step, idx) in courseDetail.flow || []" :key="idx">{{ step }}</li>
        </ol>
        <div class="detail-section-title">关联隐患</div>
        <div class="detail-tags">
          <el-tag v-for="h in courseDetail.related_hazards || []" :key="h" size="small" type="warning">{{ h }}</el-tag>
          <span v-if="!(courseDetail.related_hazards || []).length" class="detail-empty">无</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Reading, User, Notebook, Medal, Calendar, Document, VideoPlay,
  Plus, Search, Download, Trophy, CircleCheck, Refresh
} from '@element-plus/icons-vue'
import { getCurrentUser, hasPermission } from '../auth'
import {
  createTrainingExam, createTrainingPlan, createTrainingRecord,
  deleteTrainingExam, deleteTrainingPlan, deleteTrainingRecord,
  exportTrainingRecords, trainingCourses, trainingExams, trainingPlans,
  trainingRecords, trainingStats, updateTrainingExam, updateTrainingPlan,
  updateTrainingRecord,
} from '../api/training'

const activeTab = ref('courses')
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)

const canManage = computed(() => hasPermission(getCurrentUser(), 'training:manage'))

// 分类配色只是展示层的事，分类本身取自课程数据（不在前端写死分类清单）
const CATEGORY_COLORS = {
  电气安全: ['#3b82f6', '#2563eb'],
  应急处置: ['#ef4444', '#dc2626'],
  电动车安全: ['#f59e0b', '#d97706'],
  疏散安全: ['#22c55e', '#16a34a'],
  设施管理: ['#8b5cf6', '#7c3aed'],
}
const CATEGORY_TAGS = {
  电气安全: 'primary',
  应急处置: 'danger',
  电动车安全: 'warning',
  疏散安全: 'success',
  设施管理: 'info',
}

// 状态枚举与文案由后端给（/api/training/stats 返回），前端不另写一份
const planStatusLabels = ref({})
const examStatusLabels = ref({})
const planTypes = ref([])
const stats = ref({})

// ---------- 课程 ----------
const courses = ref([])
const courseCategoryFilter = ref('')
const courseSearch = ref('')
const courseDialogVisible = ref(false)
const courseDetail = ref({})

const courseCategories = computed(() => {
  const seen = new Set()
  for (const c of courses.value) if (c.category) seen.add(c.category)
  return [...seen]
})

const filteredCourses = computed(() => {
  let list = courses.value
  if (courseCategoryFilter.value) list = list.filter(c => c.category === courseCategoryFilter.value)
  if (courseSearch.value) {
    const kw = courseSearch.value
    list = list.filter(c => (c.title || '').includes(kw) || (c.summary || '').includes(kw))
  }
  return list
})

function courseCoverStyle(category) {
  const colors = CATEGORY_COLORS[category] || ['#6366f1', '#4f46e5']
  return { background: `linear-gradient(135deg, ${colors[0]}, ${colors[1]})` }
}
function courseCategoryTag(category) {
  return CATEGORY_TAGS[category] || 'info'
}
function openCourseDetail(course) {
  courseDetail.value = course
  courseDialogVisible.value = true
}

async function loadCourses() {
  try {
    const { data } = await trainingCourses()
    courses.value = Array.isArray(data) ? data : []
  } catch (e) {
    courses.value = []
  }
}

// ---------- 计划 ----------
const plans = ref([])
const plansLoading = ref(false)
const planStatusFilter = ref('')
const planSearch = ref('')
const planPagination = ref({ page: 1, size: 10, total: 0 })
const planOptions = ref([])

const planDialogVisible = ref(false)
const planFormRef = ref(null)
const editingPlanId = ref(null)
const planForm = ref({})

const planDialogTitle = computed(() => (editingPlanId.value ? '编辑培训计划' : '新建培训计划'))
const planRules = {
  plan_name: [{ required: true, message: '请填写计划名称', trigger: 'blur' }],
  plan_type: [{ required: true, message: '请选择培训类型', trigger: 'change' }],
}

function emptyPlanForm() {
  return {
    plan_name: '',
    plan_type: planTypes.value[0] || '',
    target: '',
    trainer: '',
    start_date: '',
    end_date: '',
    person_count: 0,
    progress: 0,
    status: 'pending',
    remark: '',
  }
}

async function loadPlans() {
  plansLoading.value = true
  try {
    const { data } = await trainingPlans({
      keyword: planSearch.value,
      status: planStatusFilter.value,
      page: planPagination.value.page,
      page_size: planPagination.value.size,
    })
    plans.value = data.items || []
    planPagination.value.total = data.total || 0
  } catch (e) {
    plans.value = []
    planPagination.value.total = 0
  } finally {
    plansLoading.value = false
  }
}

async function loadPlanOptions() {
  try {
    const { data } = await trainingPlans({ page: 1, page_size: 100 })
    planOptions.value = data.items || []
  } catch (e) {
    planOptions.value = []
  }
}

function openPlanDialog(row) {
  editingPlanId.value = row ? row.id : null
  planForm.value = row
    ? {
        plan_name: row.plan_name,
        plan_type: row.plan_type,
        target: row.target,
        trainer: row.trainer,
        start_date: row.start_date,
        end_date: row.end_date,
        person_count: row.person_count,
        progress: row.progress,
        status: row.status,
        remark: row.remark,
      }
    : emptyPlanForm()
  planDialogVisible.value = true
}

async function savePlan() {
  try {
    await planFormRef.value.validate()
  } catch (e) {
    return
  }
  saving.value = true
  try {
    const payload = { ...planForm.value }
    const res = editingPlanId.value
      ? await updateTrainingPlan(editingPlanId.value, payload)
      : await createTrainingPlan(payload)
    ElMessage.success(res.data.message || '已保存')
    planDialogVisible.value = false
    await Promise.all([loadPlans(), loadPlanOptions(), loadStats()])
  } catch (e) {
    // 校验类错误（400）由请求拦截器提示，这里不再重复弹窗
  } finally {
    saving.value = false
  }
}

async function removePlan(row) {
  try {
    await ElMessageBox.confirm(`确认删除培训计划「${row.plan_name}」吗？`, '删除确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    const res = await deleteTrainingPlan(row.id)
    ElMessage.success(res.data.message || '已删除')
    await Promise.all([loadPlans(), loadPlanOptions(), loadStats()])
  } catch (e) {}
}

function planStatusTag(status) {
  const map = { pending: 'info', ongoing: 'primary', completed: 'success' }
  return map[status] || 'info'
}

// ---------- 考试 ----------
const exams = ref([])
const examsLoading = ref(false)
const examStatusFilter = ref('')
const examSearch = ref('')
const examPagination = ref({ page: 1, size: 12, total: 0 })
const examOptions = ref([])

const examDialogVisible = ref(false)
const examFormRef = ref(null)
const editingExamId = ref(null)
const examForm = ref({})

const examDialogTitle = computed(() => (editingExamId.value ? '编辑考试场次' : '新建考试场次'))
const examRules = {
  title: [{ required: true, message: '请填写考试名称', trigger: 'blur' }],
}

function emptyExamForm() {
  return {
    title: '',
    description: '',
    duration_minutes: 60,
    question_count: 0,
    pass_score: 60,
    start_time: '',
    status: 'pending',
  }
}

async function loadExams() {
  examsLoading.value = true
  try {
    const { data } = await trainingExams({
      keyword: examSearch.value,
      status: examStatusFilter.value,
      page: examPagination.value.page,
      page_size: examPagination.value.size,
    })
    exams.value = data.items || []
    examPagination.value.total = data.total || 0
  } catch (e) {
    exams.value = []
    examPagination.value.total = 0
  } finally {
    examsLoading.value = false
  }
}

async function loadExamOptions() {
  try {
    const { data } = await trainingExams({ page: 1, page_size: 100 })
    examOptions.value = data.items || []
  } catch (e) {
    examOptions.value = []
  }
}

function openExamDialog(row) {
  editingExamId.value = row ? row.id : null
  examForm.value = row
    ? {
        title: row.title,
        description: row.description,
        duration_minutes: row.duration_minutes,
        question_count: row.question_count,
        pass_score: row.pass_score,
        start_time: row.start_time ? `${row.start_time}:00` : '',
        status: row.status,
      }
    : emptyExamForm()
  examDialogVisible.value = true
}

async function saveExam() {
  try {
    await examFormRef.value.validate()
  } catch (e) {
    return
  }
  saving.value = true
  try {
    const payload = { ...examForm.value }
    const res = editingExamId.value
      ? await updateTrainingExam(editingExamId.value, payload)
      : await createTrainingExam(payload)
    ElMessage.success(res.data.message || '已保存')
    examDialogVisible.value = false
    await Promise.all([loadExams(), loadExamOptions(), loadStats()])
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function removeExam(row) {
  try {
    await ElMessageBox.confirm(`确认删除考试场次「${row.title}」吗？`, '删除确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    const res = await deleteTrainingExam(row.id)
    ElMessage.success(res.data.message || '已删除')
    await Promise.all([loadExams(), loadExamOptions(), loadStats()])
  } catch (e) {}
}

function examStatusTag(status) {
  const map = { pending: 'info', ongoing: 'success', ended: 'primary' }
  return map[status] || 'info'
}
// 聚合值可能为 null（还没人考），显示「--」而不是 0
function formatScore(value) {
  return value === null || value === undefined ? '--' : value
}
function formatRate(value) {
  return value === null || value === undefined ? '--' : `${value}%`
}

// ---------- 档案 ----------
const records = ref([])
const recordsLoading = ref(false)
const recordDeptFilter = ref('')
const recordSearch = ref('')
const recordDateRange = ref([])
const recordPagination = ref({ page: 1, size: 10, total: 0 })

const recordDialogVisible = ref(false)
const recordFormRef = ref(null)
const editingRecordId = ref(null)
const recordForm = ref({})

const recordDialogTitle = computed(() => (editingRecordId.value ? '编辑培训档案' : '新建培训档案'))
const recordRules = {
  trainee_name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
}

const departments = computed(() => {
  const seen = new Set()
  for (const r of records.value) if (r.department) seen.add(r.department)
  return [...seen]
})

function emptyRecordForm() {
  return {
    trainee_name: '',
    department: '',
    plan_id: null,
    course_name: '',
    train_date: '',
    study_hours: 0,
    exam_id: null,
    exam_score: null,
    cert_no: '',
  }
}

function recordFilterParams() {
  const range = recordDateRange.value || []
  return {
    keyword: recordSearch.value,
    department: recordDeptFilter.value,
    date_from: range[0] || '',
    date_to: range[1] || '',
  }
}

async function loadRecords() {
  recordsLoading.value = true
  try {
    const { data } = await trainingRecords({
      ...recordFilterParams(),
      page: recordPagination.value.page,
      page_size: recordPagination.value.size,
    })
    records.value = data.items || []
    recordPagination.value.total = data.total || 0
  } catch (e) {
    records.value = []
    recordPagination.value.total = 0
  } finally {
    recordsLoading.value = false
  }
}

function openRecordDialog(row) {
  editingRecordId.value = row ? row.id : null
  recordForm.value = row
    ? {
        trainee_name: row.trainee_name,
        department: row.department,
        plan_id: row.plan_id,
        course_name: row.course_name,
        train_date: row.train_date,
        study_hours: row.study_hours,
        exam_id: row.exam_id,
        exam_score: row.exam_score,
        cert_no: row.cert_no,
      }
    : emptyRecordForm()
  recordDialogVisible.value = true
}

// 选了计划就把课程名带出来，省一次手填
function onPlanPicked(planId) {
  const plan = planOptions.value.find(p => p.id === planId)
  if (plan && !recordForm.value.course_name) {
    recordForm.value.course_name = plan.plan_name
  }
}

async function saveRecord() {
  try {
    await recordFormRef.value.validate()
  } catch (e) {
    return
  }
  saving.value = true
  try {
    // 成绩留空要显式传 null（表示还没考试），undefined 会被 JSON 丢掉导致清空无效
    const payload = { ...recordForm.value }
    if (payload.exam_score === undefined) payload.exam_score = null
    const res = editingRecordId.value
      ? await updateTrainingRecord(editingRecordId.value, payload)
      : await createTrainingRecord(payload)
    ElMessage.success(res.data.message || '已保存')
    recordDialogVisible.value = false
    await Promise.all([loadRecords(), loadStats()])
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function removeRecord(row) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.trainee_name}」的这条培训档案吗？`, '删除确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    const res = await deleteTrainingRecord(row.id)
    ElMessage.success(res.data.message || '已删除')
    await Promise.all([loadRecords(), loadStats()])
  } catch (e) {}
}

function resultTag(row) {
  if (row.is_passed === null) return 'info'
  return row.is_passed ? 'success' : 'danger'
}

async function exportRecords() {
  exporting.value = true
  try {
    const res = await exportTrainingRecords(recordFilterParams())
    const url = URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `培训档案-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    // 不能紧接着 revoke：浏览器此时还在读这个 blob，立即释放会把下载取消掉
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
    ElMessage.success('档案已导出')
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// ---------- 概览 ----------
async function loadStats() {
  const { data } = await trainingStats()
  stats.value = data
  planStatusLabels.value = data.plan_status_labels || {}
  examStatusLabels.value = data.exam_status_labels || {}
  planTypes.value = data.plan_types || []
}

async function loadAll() {
  loading.value = true
  try {
    try {
      await loadStats()
    } catch (e) {
      // 统计失败不阻塞其余页签
    }
    await Promise.all([
      loadCourses(),
      loadPlans(),
      loadExams(),
      loadRecords(),
      loadPlanOptions(),
      loadExamOptions(),
    ])
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.fire-training-page {
  padding: 0;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.el-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.orange { background: linear-gradient(135deg, #f59e0b, #d97706); }
.stat-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e2e8f0;
}

.tab-item {
  padding: 8px 18px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-item:hover {
  background: #f1f5f9;
  color: #334155;
}

.tab-item.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.course-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.course-cover {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  color: #fff;
}

.cover-icon {
  font-size: 40px;
  opacity: 0.8;
}

.course-level {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.4);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.course-body {
  padding: 12px 14px;
}

.course-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
  line-height: 1.4;
  height: 42px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.course-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
  height: 48px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.course-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.course-count {
  font-size: 12px;
  color: #94a3b8;
}

.course-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-top: 1px solid #f1f5f9;
}

.course-points {
  font-size: 12px;
  color: #94a3b8;
}

.exam-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.exam-card.ongoing {
  border-color: #22c55e;
  box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.2);
}

.exam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.exam-time {
  font-size: 12px;
  color: #94a3b8;
}

.exam-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
}

.exam-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
  height: 32px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.exam-info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
  padding: 4px 0;
}

.exam-info-row span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.exam-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 10px;
  margin-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.pass {
  color: #22c55e;
  font-weight: 600;
}

.fail {
  color: #ef4444;
  font-weight: 600;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.detail-summary {
  font-size: 13px;
  color: #475569;
  margin: 0 0 14px;
  line-height: 1.6;
}

.detail-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  margin: 14px 0 6px;
}

.detail-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #475569;
  line-height: 1.8;
}

.detail-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.detail-empty {
  font-size: 13px;
  color: #94a3b8;
}
</style>
