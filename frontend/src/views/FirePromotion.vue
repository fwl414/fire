<template>
  <div class="fire-promotion-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防宣传活动管理</div>
        <p class="subtitle">活动计划 · 活动记录 · 宣传资料 · 宣传效果 · 全员消防安全宣传教育</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Flag /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalActivities }}</div>
            <div class="stat-label">活动总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><Calendar /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.monthActivities }}</div>
            <div class="stat-label">本月活动</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.participants }}</div>
            <div class="stat-label">参与人数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.coverageRate }}%</div>
            <div class="stat-label">宣传覆盖率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'plans' }" @click="activeTab = 'plans'">
          <el-icon><Calendar /></el-icon>
          活动计划
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><Document /></el-icon>
          活动记录
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'materials' }" @click="activeTab = 'materials'">
          <el-icon><Picture /></el-icon>
          宣传资料
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'effects' }" @click="activeTab = 'effects'">
          <el-icon><DataAnalysis /></el-icon>
          宣传效果
        </div>
      </div>

      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="openPlanDialog()">
              <el-icon><Plus /></el-icon>
              新增活动
            </el-button>
            <el-select v-model="planTypeFilter" placeholder="活动类型" clearable style="width: 140px">
              <el-option label="消防讲座" value="lecture" />
              <el-option label="应急演练" value="drill" />
              <el-option label="安全培训" value="training" />
              <el-option label="消防宣传日" value="promotion_day" />
            </el-select>
            <el-select v-model="planStatusFilter" placeholder="计划状态" clearable style="width: 140px">
              <el-option label="待执行" value="pending" />
              <el-option label="进行中" value="ongoing" />
              <el-option label="已完成" value="completed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="planSearch" placeholder="搜索活动名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table :data="filteredPlans" stripe style="width: 100%">
          <el-table-column prop="plan_name" label="活动名称" min-width="200" />
          <el-table-column prop="type" label="活动类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="activityTypeTag(row.type)">{{ activityTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="活动地点" width="160" />
          <el-table-column prop="organizer" label="组织部门" width="120" />
          <el-table-column prop="planned_date" label="计划日期" width="120" />
          <el-table-column prop="planned_persons" label="预计人数" width="100" align="center" />
          <el-table-column label="进度" width="160">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="8" :color="row.progress === 100 ? '#22c55e' : '#3b82f6'" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="planStatusTag(row.status)">
                {{ planStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewPlan(row)">查看</el-button>
              <el-button link type="warning" @click="openPlanDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="deletePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="filteredPlans.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="recordTypeFilter" placeholder="活动类型" clearable style="width: 140px">
              <el-option label="消防讲座" value="lecture" />
              <el-option label="应急演练" value="drill" />
              <el-option label="安全培训" value="training" />
              <el-option label="消防宣传日" value="promotion_day" />
            </el-select>
            <el-date-picker
              v-model="recordDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
            />
          </div>
          <div class="toolbar-right">
            <el-button type="primary">
              <el-icon><Download /></el-icon>
              导出记录
            </el-button>
            <el-input v-model="recordSearch" placeholder="搜索活动名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table :data="filteredRecords" stripe style="width: 100%">
          <el-table-column prop="activity_name" label="活动名称" min-width="200" />
          <el-table-column prop="type" label="活动类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="activityTypeTag(row.type)">{{ activityTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="活动地点" width="140" />
          <el-table-column prop="actual_date" label="活动日期" width="120" />
          <el-table-column prop="actual_persons" label="参与人数" width="100" align="center" />
          <el-table-column label="效果评价" width="160">
            <template #default="{ row }">
              <div class="rating">
                <span v-for="i in 5" :key="i" class="star" :class="{ active: i <= row.rating }">★</span>
                <span class="rating-text">{{ row.rating }}.0</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="organizer" label="组织部门" width="120" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetailDialog(row)">详情</el-button>
              <el-button link type="success">导出</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="filteredRecords.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'materials'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="uploadDialogVisible = true">
              <el-icon><Upload /></el-icon>
              上传资料
            </el-button>
            <el-select v-model="materialTypeFilter" placeholder="资料类型" clearable style="width: 140px">
              <el-option label="宣传海报" value="poster" />
              <el-option label="视频资料" value="video" />
              <el-option label="宣传手册" value="brochure" />
              <el-option label="PPT课件" value="ppt" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="materialSearch" placeholder="搜索资料名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-row :gutter="14">
          <el-col v-for="m in filteredMaterials" :key="m.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="material-card" shadow="hover">
              <div class="material-cover" :class="m.type">
                <el-icon class="cover-icon">
                  <Picture v-if="m.type === 'poster'" />
                  <VideoPlay v-else-if="m.type === 'video'" />
                  <Document v-else-if="m.type === 'brochure'" />
                  <Notebook v-else />
                </el-icon>
                <div class="material-size">{{ m.size }}</div>
              </div>
              <div class="material-body">
                <div class="material-title">{{ m.title }}</div>
                <div class="material-desc">{{ m.description }}</div>
                <div class="material-meta">
                  <el-tag size="small" :type="materialTypeTag(m.type)">{{ materialTypeText(m.type) }}</el-tag>
                  <span class="download-count">{{ m.download_count }}次下载</span>
                </div>
              </div>
              <div class="material-footer">
                <span class="upload-time">{{ m.upload_time }}</span>
                <div class="material-actions">
                  <el-button size="small" type="primary" link>
                    <el-icon><View /></el-icon>
                    预览
                  </el-button>
                  <el-button size="small" type="success" link>
                    <el-icon><Download /></el-icon>
                    下载
                  </el-button>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'effects'" class="tab-content">
        <el-row :gutter="14" class="charts-row">
          <el-col :xs="24" :md="14">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">参与人数趋势</div>
              <div ref="participantTrendRef" class="chart-container"></div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="10">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">活动类型占比</div>
              <div ref="activityTypeRef" class="chart-container"></div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="14" class="charts-row">
          <el-col :xs="24" :md="12">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">满意度统计</div>
              <div ref="satisfactionRef" class="chart-container"></div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">各部门参与情况</div>
              <div ref="deptParticipationRef" class="chart-container"></div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <el-dialog v-model="planDialogVisible" :title="editingPlan ? '编辑活动计划' : '新增活动计划'" width="600px">
      <el-form :model="planForm" label-width="100px">
        <el-form-item label="活动名称">
          <el-input v-model="planForm.plan_name" placeholder="请输入活动名称" />
        </el-form-item>
        <el-form-item label="活动类型">
          <el-select v-model="planForm.type" placeholder="请选择活动类型" style="width: 100%">
            <el-option label="消防讲座" value="lecture" />
            <el-option label="应急演练" value="drill" />
            <el-option label="安全培训" value="training" />
            <el-option label="消防宣传日" value="promotion_day" />
          </el-select>
        </el-form-item>
        <el-form-item label="活动地点">
          <el-input v-model="planForm.location" placeholder="请输入活动地点" />
        </el-form-item>
        <el-form-item label="组织部门">
          <el-input v-model="planForm.organizer" placeholder="请输入组织部门" />
        </el-form-item>
        <el-form-item label="计划日期">
          <el-date-picker v-model="planForm.planned_date" type="date" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预计人数">
          <el-input-number v-model="planForm.planned_persons" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="活动描述">
          <el-input v-model="planForm.description" type="textarea" :rows="3" placeholder="请输入活动描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="活动详情" width="700px">
      <template v-if="currentActivity">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="活动名称" :span="2">{{ currentActivity.activity_name }}</el-descriptions-item>
          <el-descriptions-item label="活动类型">
            <el-tag :type="activityTypeTag(currentActivity.type)">{{ activityTypeText(currentActivity.type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="活动地点">{{ currentActivity.location }}</el-descriptions-item>
          <el-descriptions-item label="活动日期">{{ currentActivity.actual_date }}</el-descriptions-item>
          <el-descriptions-item label="组织部门">{{ currentActivity.organizer }}</el-descriptions-item>
          <el-descriptions-item label="参与人数">{{ currentActivity.actual_persons }}人</el-descriptions-item>
          <el-descriptions-item label="效果评价">
            <div class="rating">
              <span v-for="i in 5" :key="i" class="star" :class="{ active: i <= currentActivity.rating }">★</span>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="负责人">{{ currentActivity.leader }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-section">
          <div class="section-title">活动总结</div>
          <p class="section-content">{{ currentActivity.summary }}</p>
        </div>
        <div class="detail-section">
          <div class="section-title">活动照片</div>
          <div class="photo-grid">
            <div v-for="(photo, index) in currentActivity.photos" :key="index" class="photo-item">
              <div class="photo-placeholder">
                <el-icon><Picture /></el-icon>
              </div>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传宣传资料" width="500px">
      <el-upload
        drag
        action="#"
        :auto-upload="false"
        multiple
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持海报、视频、手册、PPT等格式文件上传
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary">开始上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import {
  Flag, Calendar, User, TrendCharts, Document, Picture, DataAnalysis,
  Plus, Search, Download, Upload, VideoPlay, Notebook, View, UploadFilled
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('plans')
const planTypeFilter = ref('')
const planStatusFilter = ref('')
const planSearch = ref('')
const recordTypeFilter = ref('')
const recordSearch = ref('')
const recordDateRange = ref([])
const materialTypeFilter = ref('')
const materialSearch = ref('')
const planDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const editingPlan = ref(null)
const currentActivity = ref(null)

const participantTrendRef = ref(null)
const activityTypeRef = ref(null)
const satisfactionRef = ref(null)
const deptParticipationRef = ref(null)

let participantTrendChart = null
let activityTypeChart = null
let satisfactionChart = null
let deptParticipationChart = null

const stats = ref({
  totalActivities: 86,
  monthActivities: 12,
  participants: 3580,
  coverageRate: 94.5
})

const planForm = ref({
  plan_name: '',
  type: '',
  location: '',
  organizer: '',
  planned_date: '',
  planned_persons: 50,
  description: ''
})

const activityPlans = ref([
  { id: 1, plan_name: '2024年消防安全知识讲座', type: 'lecture', location: '办公楼一楼会议室', organizer: '安保部', planned_date: '2024-09-15', planned_persons: 120, progress: 0, status: 'pending', description: '面向全体员工的消防安全知识普及讲座' },
  { id: 2, plan_name: '第三季度消防应急演练', type: 'drill', location: '园区广场', organizer: '安保部', planned_date: '2024-09-20', planned_persons: 200, progress: 35, status: 'ongoing', description: '全员参与的火灾应急疏散演练' },
  { id: 3, plan_name: '消防设施操作培训', type: 'training', location: '消防控制室', organizer: '技术部', planned_date: '2024-09-25', planned_persons: 30, progress: 0, status: 'pending', description: '消防设施操作员专项技能培训' },
  { id: 4, plan_name: '119消防宣传日活动', type: 'promotion_day', location: '园区各区域', organizer: '安保部', planned_date: '2024-11-09', planned_persons: 500, progress: 20, status: 'ongoing', description: '全国消防日系列宣传活动' },
  { id: 5, plan_name: '新员工消防安全培训', type: 'training', location: '培训中心', organizer: '人力资源部', planned_date: '2024-09-10', planned_persons: 25, progress: 100, status: 'completed', description: '新入职员工消防安全基础知识培训' },
  { id: 6, plan_name: '易燃易爆场所安全讲座', type: 'lecture', location: '仓储楼会议室', organizer: '仓储物流部', planned_date: '2024-08-28', planned_persons: 45, progress: 100, status: 'completed', description: '仓储区域消防安全专项讲座' },
  { id: 7, plan_name: '志愿消防队技能培训', type: 'training', location: '消防训练场地', organizer: '安保部', planned_date: '2024-10-10', planned_persons: 24, progress: 0, status: 'pending', description: '志愿消防队灭火技能实操培训' },
  { id: 8, plan_name: '夏季防火安全宣传', type: 'promotion_day', location: '员工宿舍区', organizer: '后勤部', planned_date: '2024-07-15', planned_persons: 300, progress: 100, status: 'cancelled', description: '因天气原因取消' },
])

const activityRecords = ref([
  { id: 1, activity_name: '2024年上半年消防安全知识讲座', type: 'lecture', location: '办公楼一楼会议室', actual_date: '2024-06-15', actual_persons: 132, rating: 5, organizer: '安保部', leader: '张建国', summary: '本次讲座涵盖了消防法规、火灾预防、火场逃生等内容，参与员工反响热烈，互动环节积极提问。通过现场演示和案例分析，有效提升了员工的消防安全意识和应急处置能力。', photos: [1, 2, 3, 4] },
  { id: 2, activity_name: '第二季度消防应急演练', type: 'drill', location: '园区广场', actual_date: '2024-06-20', actual_persons: 215, rating: 4, organizer: '安保部', leader: '李明华', summary: '演练模拟办公楼三层发生火灾，各部门按照预案有序疏散，全程用时4分30秒，达到预期目标。演练后进行了总结讲评，指出了存在的问题和改进方向。', photos: [1, 2, 3] },
  { id: 3, activity_name: '消防控制室操作员培训', type: 'training', location: '消防控制室', actual_date: '2024-05-10', actual_persons: 28, rating: 5, organizer: '技术部', leader: '王志强', summary: '为期三天的专项培训，内容包括火灾自动报警系统、自动喷水灭火系统、消火栓系统等设施的操作与维护。培训结束后进行了考核，全部人员合格。', photos: [1, 2] },
  { id: 4, activity_name: '119消防宣传日活动', type: 'promotion_day', location: '园区各区域', actual_date: '2023-11-09', actual_persons: 486, rating: 5, organizer: '安保部', leader: '张建国', summary: '活动包括消防知识展览、灭火器实操体验、火场逃生模拟、安全咨询等多个环节，吸引了大量员工参与，有效提高了全员消防安全意识。', photos: [1, 2, 3, 4, 5, 6] },
  { id: 5, activity_name: '电气火灾防范培训', type: 'training', location: '培训中心', actual_date: '2024-04-20', actual_persons: 78, rating: 4, organizer: '技术部', leader: '赵晓燕', summary: '针对电气火灾高发特点，讲解了电气火灾成因、预防措施、用电安全规范等内容，结合典型案例进行分析，提高了员工的电气安全意识。', photos: [1, 2, 3] },
  { id: 6, activity_name: '仓储区域消防安全讲座', type: 'lecture', location: '仓储楼会议室', actual_date: '2024-03-15', actual_persons: 52, rating: 4, organizer: '仓储物流部', leader: '陈大伟', summary: '针对仓储区域特点，重点讲解了货物储存防火要求、消防设施使用、应急处置流程等内容，提升了仓储人员的消防安全技能。', photos: [1, 2] },
])

const materials = ref([
  { id: 1, title: '消防安全知识海报', type: 'poster', description: '消防四个能力建设宣传海报', size: '2.3MB', download_count: 256, upload_time: '2024-08-10' },
  { id: 2, title: '火场逃生教学视频', type: 'video', description: '火灾逃生技巧与疏散指引教学视频', size: '128MB', download_count: 189, upload_time: '2024-08-05' },
  { id: 3, title: '员工消防安全手册', type: 'brochure', description: '员工必备消防安全知识手册', size: '5.6MB', download_count: 423, upload_time: '2024-07-20' },
  { id: 4, title: '消防设施操作培训PPT', type: 'ppt', description: '各类消防设施操作使用培训课件', size: '15.2MB', download_count: 134, upload_time: '2024-07-15' },
  { id: 5, title: '119消防日主题海报', type: 'poster', description: '2024年119消防宣传日主题海报', size: '3.1MB', download_count: 312, upload_time: '2024-11-01' },
  { id: 6, title: '灭火器使用教学视频', type: 'video', description: '手提式干粉灭火器正确使用方法', size: '86MB', download_count: 278, upload_time: '2024-06-18' },
  { id: 7, title: '电气防火安全手册', type: 'brochure', description: '电气火灾预防与安全用电指南', size: '4.2MB', download_count: 198, upload_time: '2024-05-22' },
  { id: 8, title: '应急疏散演练培训课件', type: 'ppt', description: '应急疏散组织与实施培训PPT', size: '22.5MB', download_count: 167, upload_time: '2024-04-10' },
])

function activityTypeText(type) {
  const map = { lecture: '消防讲座', drill: '应急演练', training: '安全培训', promotion_day: '消防宣传日' }
  return map[type] || type
}
function activityTypeTag(type) {
  const map = { lecture: 'primary', drill: 'warning', training: 'success', promotion_day: 'danger' }
  return map[type] || 'info'
}
function planStatusText(status) {
  const map = { pending: '待执行', ongoing: '进行中', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}
function planStatusTag(status) {
  const map = { pending: 'info', ongoing: 'primary', completed: 'success', cancelled: 'danger' }
  return map[status] || 'info'
}
function materialTypeText(type) {
  const map = { poster: '宣传海报', video: '视频资料', brochure: '宣传手册', ppt: 'PPT课件' }
  return map[type] || type
}
function materialTypeTag(type) {
  const map = { poster: 'danger', video: 'primary', brochure: 'success', ppt: 'warning' }
  return map[type] || 'info'
}

const filteredPlans = computed(() => {
  let list = activityPlans.value
  if (planTypeFilter.value) list = list.filter(p => p.type === planTypeFilter.value)
  if (planStatusFilter.value) list = list.filter(p => p.status === planStatusFilter.value)
  if (planSearch.value) list = list.filter(p => p.plan_name.includes(planSearch.value))
  return list
})

const filteredRecords = computed(() => {
  let list = activityRecords.value
  if (recordTypeFilter.value) list = list.filter(r => r.type === recordTypeFilter.value)
  if (recordSearch.value) list = list.filter(r => r.activity_name.includes(recordSearch.value))
  return list
})

const filteredMaterials = computed(() => {
  let list = materials.value
  if (materialTypeFilter.value) list = list.filter(m => m.type === materialTypeFilter.value)
  if (materialSearch.value) list = list.filter(m => m.title.includes(materialSearch.value) || m.description.includes(materialSearch.value))
  return list
})

function openPlanDialog(row) {
  if (row) {
    editingPlan.value = row
    planForm.value = { ...row }
  } else {
    editingPlan.value = null
    planForm.value = {
      plan_name: '',
      type: '',
      location: '',
      organizer: '',
      planned_date: '',
      planned_persons: 50,
      description: ''
    }
  }
  planDialogVisible.value = true
}

function savePlan() {
  if (editingPlan.value) {
    const index = activityPlans.value.findIndex(p => p.id === editingPlan.value.id)
    if (index > -1) {
      activityPlans.value[index] = { ...activityPlans.value[index], ...planForm.value }
    }
    ElMessage.success('编辑成功')
  } else {
    const newPlan = {
      id: Date.now(),
      ...planForm.value,
      progress: 0,
      status: 'pending'
    }
    activityPlans.value.unshift(newPlan)
    ElMessage.success('新增成功')
  }
  planDialogVisible.value = false
}

function deletePlan(row) {
  ElMessageBox.confirm('确定要删除该活动计划吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    const index = activityPlans.value.findIndex(p => p.id === row.id)
    if (index > -1) {
      activityPlans.value.splice(index, 1)
    }
    ElMessage.success('删除成功')
  }).catch(() => {})
}

function viewPlan(row) {
  ElMessage.info('查看活动：' + row.plan_name)
}

function openDetailDialog(row) {
  currentActivity.value = row
  detailDialogVisible.value = true
}

function initCharts() {
  if (participantTrendRef.value) {
    participantTrendChart = echarts.init(participantTrendRef.value)
    participantTrendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['参与人数', '活动场次'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月']
      },
      yAxis: [
        { type: 'value', name: '人数' },
        { type: 'value', name: '场次' }
      ],
      series: [
        {
          name: '参与人数',
          type: 'line',
          smooth: true,
          data: [280, 320, 450, 380, 520, 680, 420, 350, 180],
          itemStyle: { color: '#3b82f6' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
            ])
          }
        },
        {
          name: '活动场次',
          type: 'bar',
          yAxisIndex: 1,
          data: [6, 8, 10, 9, 12, 15, 8, 7, 4],
          itemStyle: { color: '#22c55e', borderRadius: [4, 4, 0, 0] }
        }
      ]
    })
  }

  if (activityTypeRef.value) {
    activityTypeChart = echarts.init(activityTypeRef.value)
    activityTypeChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, left: 'center' },
      series: [
        {
          name: '活动类型',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 14, fontWeight: 'bold' }
          },
          data: [
            { value: 28, name: '消防讲座', itemStyle: { color: '#3b82f6' } },
            { value: 22, name: '应急演练', itemStyle: { color: '#f59e0b' } },
            { value: 25, name: '安全培训', itemStyle: { color: '#22c55e' } },
            { value: 11, name: '消防宣传日', itemStyle: { color: '#ef4444' } }
          ]
        }
      ]
    })
  }

  if (satisfactionRef.value) {
    satisfactionChart = echarts.init(satisfactionRef.value)
    satisfactionChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: ['非常满意', '满意', '一般', '不满意', '非常不满意'] },
      yAxis: { type: 'value', name: '人数' },
      series: [
        {
          type: 'bar',
          data: [
            { value: 1856, itemStyle: { color: '#22c55e', borderRadius: [4, 4, 0, 0] } },
            { value: 1235, itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] } },
            { value: 368, itemStyle: { color: '#f59e0b', borderRadius: [4, 4, 0, 0] } },
            { value: 92, itemStyle: { color: '#f97316', borderRadius: [4, 4, 0, 0] } },
            { value: 29, itemStyle: { color: '#ef4444', borderRadius: [4, 4, 0, 0] } }
          ],
          barWidth: '50%'
        }
      ]
    })
  }

  if (deptParticipationRef.value) {
    deptParticipationChart = echarts.init(deptParticipationRef.value)
    deptParticipationChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['参与人数', '部门总人数'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: ['后勤部', '技术部', '行政部', '仓储部', '安保部', '销售部']
      },
      series: [
        {
          name: '参与人数',
          type: 'bar',
          data: [420, 580, 320, 280, 150, 450],
          itemStyle: { color: '#8b5cf6', borderRadius: [0, 4, 4, 0] }
        },
        {
          name: '部门总人数',
          type: 'bar',
          data: [450, 620, 350, 300, 160, 500],
          itemStyle: { color: '#c4b5fd', borderRadius: [0, 4, 4, 0] }
        }
      ]
    })
  }
}

function resizeCharts() {
  participantTrendChart?.resize()
  activityTypeChart?.resize()
  satisfactionChart?.resize()
  deptParticipationChart?.resize()
}

watch(activeTab, (newTab) => {
  if (newTab === 'effects') {
    nextTick(() => {
      initCharts()
    })
  }
})

onMounted(() => {
  window.addEventListener('resize', resizeCharts)
})
</script>

<style scoped>
.fire-promotion-page {
  padding: 0;
}

.title-row {
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

.rating {
  display: flex;
  align-items: center;
  gap: 4px;
}

.star {
  font-size: 14px;
  color: #e2e8f0;
}

.star.active {
  color: #f59e0b;
}

.rating-text {
  font-size: 12px;
  color: #64748b;
  margin-left: 4px;
}

.material-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.material-cover {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  color: #fff;
}

.material-cover.poster { background: linear-gradient(135deg, #ef4444, #dc2626); }
.material-cover.video { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.material-cover.brochure { background: linear-gradient(135deg, #22c55e, #16a34a); }
.material-cover.ppt { background: linear-gradient(135deg, #f59e0b, #d97706); }

.cover-icon {
  font-size: 48px;
  opacity: 0.8;
}

.material-size {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.4);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.material-body {
  padding: 12px 14px;
}

.material-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
  line-height: 1.4;
  height: 21px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.material-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
  height: 32px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.material-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.download-count {
  font-size: 12px;
  color: #94a3b8;
}

.material-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-top: 1px solid #f1f5f9;
}

.upload-time {
  font-size: 12px;
  color: #94a3b8;
}

.material-actions {
  display: flex;
  gap: 8px;
}

.charts-row {
  margin-bottom: 14px;
}

.charts-row:last-child {
  margin-bottom: 0;
}

.chart-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 12px;
}

.chart-container {
  width: 100%;
  height: 300px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.detail-section {
  margin-top: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
}

.section-content {
  color: #475569;
  line-height: 1.8;
  margin: 0;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.photo-item {
  aspect-ratio: 1;
}

.photo-placeholder {
  width: 100%;
  height: 100%;
  background: #f1f5f9;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 32px;
}
</style>
