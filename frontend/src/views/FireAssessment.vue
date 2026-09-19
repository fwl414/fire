<template>
  <div class="fire-assessment-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防安全评估</div>
        <p class="subtitle">消防安全自评 · 风险等级评定 · 评估报告 · 持续改进</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalAssessments }}</div>
            <div class="stat-label">评估次数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><Medal /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num grade-b">{{ stats.currentGrade }}</div>
            <div class="stat-label">当前等级</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><DataLine /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.avgScore }}<span class="unit">分</span></div>
            <div class="stat-label">平均得分</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.rectificationRate }}<span class="unit">%</span></div>
            <div class="stat-label">整改完成率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">
          <el-icon><DataAnalysis /></el-icon>
          评估概览
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'items' }" @click="activeTab = 'items'">
          <el-icon><List /></el-icon>
          评估项目
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'history' }" @click="activeTab = 'history'">
          <el-icon><Clock /></el-icon>
          历史评估
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'rectification' }" @click="activeTab = 'rectification'">
          <el-icon><Tools /></el-icon>
          整改跟踪
          <span v-if="pendingRectification" class="badge">{{ pendingRectification }}</span>
        </div>
      </div>

      <div v-if="activeTab === 'overview'" class="tab-content">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-card class="overview-card" shadow="never">
              <div class="card-title">当前评估得分</div>
              <div class="gauge-wrapper">
                <div class="gauge-container">
                  <svg class="gauge-svg" viewBox="0 0 200 200">
                    <circle cx="100" cy="100" r="80" fill="none" stroke="#e2e8f0" stroke-width="16" />
                    <circle
                      cx="100" cy="100" r="80" fill="none"
                      :stroke="gaugeColor"
                      stroke-width="16"
                      stroke-linecap="round"
                      :stroke-dasharray="gaugeDashArray"
                      stroke-dashoffset="0"
                      transform="rotate(-90 100 100)"
                    />
                  </svg>
                  <div class="gauge-center">
                    <div class="gauge-score">{{ currentAssessment.score }}</div>
                    <div class="gauge-label">综合得分</div>
                  </div>
                </div>
                <div class="grade-badge-wrapper">
                  <div class="grade-badge" :class="'grade-' + currentAssessment.grade.toLowerCase()">
                    {{ currentAssessment.grade }}级
                  </div>
                  <div class="grade-desc">{{ gradeDesc }}</div>
                </div>
              </div>
              <div class="score-progress-list">
                <div class="score-progress-item" v-for="dim in dimensions" :key="dim.name">
                  <div class="progress-header">
                    <span class="progress-label">{{ dim.name }}</span>
                    <span class="progress-value">{{ dim.score }}/{{ dim.full }}</span>
                  </div>
                  <div class="progress-bar-bg">
                    <div
                      class="progress-bar-fill"
                      :style="{ width: (dim.score / dim.full * 100) + '%', background: dim.color }"
                    ></div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card class="overview-card" shadow="never">
              <div class="card-title">各维度得分</div>
              <div class="radar-wrapper">
                <div class="radar-chart">
                  <svg viewBox="0 0 300 300" class="radar-svg">
                    <polygon :points="radarPoints[4]" fill="none" stroke="#e2e8f0" stroke-width="1" />
                    <polygon :points="radarPoints[3]" fill="none" stroke="#e2e8f0" stroke-width="1" />
                    <polygon :points="radarPoints[2]" fill="none" stroke="#e2e8f0" stroke-width="1" />
                    <polygon :points="radarPoints[1]" fill="none" stroke="#e2e8f0" stroke-width="1" />
                    <polygon :points="radarPoints[0]" fill="none" stroke="#e2e8f0" stroke-width="1" />
                    <line v-for="(axis, i) in radarAxes" :key="'axis-'+i"
                      x1="150" y1="150" :x2="axis.x" :y2="axis.y"
                      stroke="#e2e8f0" stroke-width="1" />
                    <polygon :points="radarDataPoints"
                      fill="rgba(59, 130, 246, 0.2)"
                      stroke="#3b82f6" stroke-width="2" />
                    <circle v-for="(p, i) in radarDataPointsArray" :key="'point-'+i"
                      :cx="p.x" :cy="p.y" r="5" fill="#3b82f6" />
                    <text v-for="(label, i) in radarLabels" :key="'label-'+i"
                      :x="label.x" :y="label.y" text-anchor="middle"
                      class="radar-label-text" dominant-baseline="middle">
                      {{ label.text }}
                    </text>
                  </svg>
                </div>
                <div class="radar-legend">
                  <div v-for="dim in dimensions" :key="dim.name" class="legend-item">
                    <span class="legend-dot" :style="{ background: dim.color }"></span>
                    <span class="legend-name">{{ dim.name }}</span>
                    <span class="legend-score">{{ dim.score }}分</span>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :xs="24" :md="12">
            <el-card class="overview-card" shadow="never">
              <div class="card-title">
                <el-icon><WarningFilled /></el-icon>
                主要问题
              </div>
              <div class="issue-list">
                <div class="issue-item" v-for="(issue, idx) in mainIssues" :key="idx">
                  <div class="issue-level" :class="'level-' + issue.level">{{ issue.levelText }}</div>
                  <div class="issue-content">
                    <div class="issue-title">{{ issue.title }}</div>
                    <div class="issue-desc">{{ issue.desc }}</div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card class="overview-card" shadow="never">
              <div class="card-title">
                <el-icon><Sunny /></el-icon>
                改进建议
              </div>
              <div class="suggestion-list">
                <div class="suggestion-item" v-for="(sug, idx) in suggestions" :key="idx">
                  <div class="suggestion-num">{{ idx + 1 }}</div>
                  <div class="suggestion-content">
                    <div class="suggestion-title">{{ sug.title }}</div>
                    <div class="suggestion-desc">{{ sug.desc }}</div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'items'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="categoryFilter" placeholder="评估类别" clearable style="width: 160px">
              <el-option label="建筑防火" value="建筑防火" />
              <el-option label="安全管理" value="安全管理" />
              <el-option label="设施设备" value="设施设备" />
              <el-option label="人员素质" value="人员素质" />
              <el-option label="应急能力" value="应急能力" />
            </el-select>
            <el-select v-model="complianceFilter" placeholder="达标状态" clearable style="width: 140px">
              <el-option label="达标" :value="true" />
              <el-option label="不达标" :value="false" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出评估表
            </el-button>
          </div>
        </div>

        <el-table :data="filteredItems" stripe style="width: 100%">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="category" label="评估类别" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="categoryTagType(row.category)">{{ row.category }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="item_name" label="评估项目" min-width="200" />
          <el-table-column prop="full_score" label="标准分" width="90" align="center" />
          <el-table-column prop="deduct_score" label="扣分" width="80" align="center">
            <template #default="{ row }">
              <span v-if="row.deduct_score > 0" class="danger-text">-{{ row.deduct_score }}</span>
              <span v-else>0</span>
            </template>
          </el-table-column>
          <el-table-column prop="actual_score" label="实得分" width="90" align="center">
            <template #default="{ row }">
              <strong :class="row.deduct_score > 0 ? 'danger-text' : 'success-text'">{{ row.actual_score }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="是否达标" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.is_compliant ? 'success' : 'danger'">
                {{ row.is_compliant ? '达标' : '不达标' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="deduct_reason" label="扣分原因" min-width="200">
            <template #default="{ row }">
              <span v-if="row.deduct_reason">{{ row.deduct_reason }}</span>
              <span v-else class="muted-text">-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'history'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="historyTypeFilter" placeholder="评估类型" clearable style="width: 140px">
              <el-option label="月度评估" value="monthly" />
              <el-option label="季度评估" value="quarterly" />
              <el-option label="年度评估" value="yearly" />
            </el-select>
            <el-select v-model="historyGradeFilter" placeholder="评估等级" clearable style="width: 140px">
              <el-option label="A级" value="A" />
              <el-option label="B级" value="B" />
              <el-option label="C级" value="C" />
              <el-option label="D级" value="D" />
            </el-select>
            <el-date-picker
              v-model="historyDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
            />
          </div>
          <div class="toolbar-right">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              发起评估
            </el-button>
          </div>
        </div>

        <el-table :data="filteredHistory" stripe style="width: 100%">
          <el-table-column prop="assessment_no" label="评估编号" width="160" />
          <el-table-column prop="assessment_date" label="评估日期" width="130" />
          <el-table-column label="评估类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="typeTagType(row.type)">{{ typeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="score" label="评估得分" width="100" align="center">
            <template #default="{ row }">
              <strong>{{ row.score }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="评估等级" width="100" align="center">
            <template #default="{ row }">
              <span class="grade-tag" :class="'grade-tag-' + row.grade.toLowerCase()">{{ row.grade }}级</span>
            </template>
          </el-table-column>
          <el-table-column prop="issue_count" label="存在问题数" width="110" align="center" />
          <el-table-column label="整改完成率" width="120" align="center">
            <template #default="{ row }">
              <div class="mini-progress">
                <div class="mini-bar-bg">
                  <div class="mini-bar-fill" :style="{ width: row.rectification_rate + '%' }"></div>
                </div>
                <span class="mini-progress-text">{{ row.rectification_rate }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default>
              <el-button link type="primary">查看报告</el-button>
              <el-button link type="success">下载</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'rectification'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="rectStatusFilter" placeholder="整改状态" clearable style="width: 160px">
              <el-option label="未整改" value="pending" />
              <el-option label="整改中" value="processing" />
              <el-option label="已完成" value="completed" />
              <el-option label="已复查" value="verified" />
            </el-select>
            <el-select v-model="deptFilter" placeholder="责任部门" clearable style="width: 160px">
              <el-option label="安保部" value="安保部" />
              <el-option label="工程部" value="工程部" />
              <el-option label="物业部" value="物业部" />
              <el-option label="行政部" value="行政部" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出清单
            </el-button>
          </div>
        </div>

        <el-table :data="filteredRectification" stripe style="width: 100%">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="issue_desc" label="问题描述" min-width="240" />
          <el-table-column prop="department" label="责任部门" width="110" />
          <el-table-column prop="responsible" label="责任人" width="100" />
          <el-table-column prop="deadline" label="整改期限" width="120" />
          <el-table-column label="整改状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="rectStatusType(row.status)">
                {{ rectStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="verify_result" label="复查结果" min-width="160">
            <template #default="{ row }">
              <span v-if="row.verify_result">{{ row.verify_result }}</span>
              <span v-else class="muted-text">待复查</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary">详情</el-button>
              <el-button v-if="row.status === 'completed'" link type="success">复查</el-button>
              <el-button v-if="row.status === 'pending' || row.status === 'processing'" link type="warning">催办</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts, Medal, DataLine, CircleCheck, DataAnalysis, List, Clock, Tools, WarningFilled, Sunny, Download, Plus } from '@element-plus/icons-vue'

const activeTab = ref('overview')
const categoryFilter = ref('')
const complianceFilter = ref('')
const historyTypeFilter = ref('')
const historyGradeFilter = ref('')
const historyDateRange = ref([])
const rectStatusFilter = ref('')
const deptFilter = ref('')

const stats = ref({
  totalAssessments: 24,
  currentGrade: 'B',
  avgScore: 86.5,
  rectificationRate: 78,
})

const currentAssessment = ref({
  score: 85,
  grade: 'B',
  date: '2026-09-05',
  type: 'quarterly',
})

const dimensions = ref([
  { name: '建筑防火', score: 88, full: 100, color: '#3b82f6' },
  { name: '安全管理', score: 82, full: 100, color: '#22c55e' },
  { name: '设施设备', score: 90, full: 100, color: '#f59e0b' },
  { name: '人员素质', score: 78, full: 100, color: '#8b5cf6' },
  { name: '应急能力', score: 86, full: 100, color: '#ef4444' },
])

const mainIssues = ref([
  { level: 'high', levelText: '严重', title: '消防通道被占用', desc: '地下车库B1层东出口消防通道堆放杂物，影响疏散' },
  { level: 'medium', levelText: '一般', title: '应急照明故障', desc: '综合办公楼3层西侧走廊3盏应急照明灯不亮' },
  { level: 'medium', levelText: '一般', title: '培训记录不全', desc: '新入职员工消防安全培训记录缺失，需补全' },
  { level: 'low', levelText: '轻微', title: '灭火器压力不足', desc: '实验楼B座2层2具灭火器压力表显示黄区' },
])

const suggestions = ref([
  { title: '立即清理消防通道', desc: '组织人员对地下车库消防通道进行清理，确保畅通，并建立定期巡查机制' },
  { title: '修复应急照明设施', desc: '安排电工对应急照明故障点进行排查维修，更换损坏灯具' },
  { title: '完善培训体系', desc: '建立新员工入职消防安全培训制度，确保100%培训合格后方可上岗' },
  { title: '加强设备维护', desc: '增加灭火器检查频次，及时更换压力不足的灭火器' },
])

const assessmentItems = ref([
  { category: '建筑防火', item_name: '防火分区设置', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '建筑防火', item_name: '安全出口数量', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '建筑防火', item_name: '疏散通道宽度', full_score: 10, deduct_score: 2, actual_score: 8, is_compliant: false, deduct_reason: '地下车库通道堆放杂物' },
  { category: '建筑防火', item_name: '防火门完好率', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '建筑防火', item_name: '应急照明完好率', full_score: 10, deduct_score: 3, actual_score: 7, is_compliant: false, deduct_reason: '3层西侧3盏灯故障' },
  { category: '安全管理', item_name: '消防安全制度', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '安全管理', item_name: '消防安全责任人', full_score: 5, deduct_score: 0, actual_score: 5, is_compliant: true, deduct_reason: '' },
  { category: '安全管理', item_name: '消防档案管理', full_score: 10, deduct_score: 1, actual_score: 9, is_compliant: true, deduct_reason: '部分记录不完整' },
  { category: '安全管理', item_name: '日常巡查制度', full_score: 10, deduct_score: 2, actual_score: 8, is_compliant: false, deduct_reason: '巡查记录缺项' },
  { category: '安全管理', item_name: '隐患整改制度', full_score: 5, deduct_score: 0, actual_score: 5, is_compliant: true, deduct_reason: '' },
  { category: '设施设备', item_name: '火灾自动报警系统', full_score: 15, deduct_score: 0, actual_score: 15, is_compliant: true, deduct_reason: '' },
  { category: '设施设备', item_name: '自动喷水灭火系统', full_score: 15, deduct_score: 1, actual_score: 14, is_compliant: true, deduct_reason: '1个喷头漏水' },
  { category: '设施设备', item_name: '消火栓系统', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '设施设备', item_name: '灭火器配置', full_score: 10, deduct_score: 2, actual_score: 8, is_compliant: false, deduct_reason: '2具压力不足' },
  { category: '设施设备', item_name: '防排烟系统', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '人员素质', item_name: '消防安全培训', full_score: 10, deduct_score: 3, actual_score: 7, is_compliant: false, deduct_reason: '新员工培训记录缺失' },
  { category: '人员素质', item_name: '四个能力掌握', full_score: 10, deduct_score: 2, actual_score: 8, is_compliant: false, deduct_reason: '部分员工操作不熟练' },
  { category: '人员素质', item_name: '持证上岗情况', full_score: 5, deduct_score: 0, actual_score: 5, is_compliant: true, deduct_reason: '' },
  { category: '应急能力', item_name: '应急预案制定', full_score: 10, deduct_score: 0, actual_score: 10, is_compliant: true, deduct_reason: '' },
  { category: '应急能力', item_name: '应急演练频次', full_score: 10, deduct_score: 1, actual_score: 9, is_compliant: true, deduct_reason: '本年度仅演练1次' },
  { category: '应急能力', item_name: '应急物资储备', full_score: 5, deduct_score: 0, actual_score: 5, is_compliant: true, deduct_reason: '' },
  { category: '应急能力', item_name: '疏散引导能力', full_score: 5, deduct_score: 0, actual_score: 5, is_compliant: true, deduct_reason: '' },
])

const historyRecords = ref([
  { assessment_no: 'FA-2026-Q3', assessment_date: '2026-09-05', type: 'quarterly', score: 85, grade: 'B', issue_count: 12, rectification_rate: 67 },
  { assessment_no: 'FA-2026-M08', assessment_date: '2026-08-01', type: 'monthly', score: 82, grade: 'B', issue_count: 15, rectification_rate: 80 },
  { assessment_no: 'FA-2026-M07', assessment_date: '2026-07-03', type: 'monthly', score: 88, grade: 'B', issue_count: 8, rectification_rate: 100 },
  { assessment_no: 'FA-2026-Q2', assessment_date: '2026-06-28', type: 'quarterly', score: 91, grade: 'A', issue_count: 6, rectification_rate: 100 },
  { assessment_no: 'FA-2026-M06', assessment_date: '2026-06-02', type: 'monthly', score: 86, grade: 'B', issue_count: 10, rectification_rate: 90 },
  { assessment_no: 'FA-2026-M05', assessment_date: '2026-05-06', type: 'monthly', score: 84, grade: 'B', issue_count: 11, rectification_rate: 82 },
  { assessment_no: 'FA-2026-Q1', assessment_date: '2026-03-25', type: 'quarterly', score: 79, grade: 'C', issue_count: 18, rectification_rate: 72 },
  { assessment_no: 'FA-2025-Y', assessment_date: '2025-12-28', type: 'yearly', score: 83, grade: 'B', issue_count: 14, rectification_rate: 85 },
])

const rectificationTasks = ref([
  { issue_desc: '地下车库B1层东出口消防通道堆放杂物，影响疏散', department: '物业部', responsible: '王主管', deadline: '2026-09-10', status: 'processing', verify_result: '' },
  { issue_desc: '综合办公楼3层西侧走廊3盏应急照明灯不亮', department: '工程部', responsible: '李工', deadline: '2026-09-12', status: 'pending', verify_result: '' },
  { issue_desc: '新入职员工消防安全培训记录缺失', department: '行政部', responsible: '张经理', deadline: '2026-09-15', status: 'pending', verify_result: '' },
  { issue_desc: '实验楼B座2层2具灭火器压力不足', department: '安保部', responsible: '赵班长', deadline: '2026-09-08', status: 'completed', verify_result: '' },
  { issue_desc: '消防水泵房1号喷淋泵有漏水现象', department: '工程部', responsible: '李工', deadline: '2026-08-30', status: 'verified', verify_result: '已更换密封件，运行正常' },
  { issue_desc: '火灾自动报警系统有3个故障点位', department: '工程部', responsible: '孙工', deadline: '2026-08-25', status: 'verified', verify_result: '已修复，系统运行正常' },
  { issue_desc: '员工食堂燃气报警系统未按规定测试', department: '安保部', responsible: '赵班长', deadline: '2026-09-20', status: 'pending', verify_result: '' },
  { issue_desc: '部分楼层疏散指示标志损坏', department: '工程部', responsible: '李工', deadline: '2026-09-18', status: 'processing', verify_result: '' },
])

const pendingRectification = computed(() => {
  return rectificationTasks.value.filter(t => t.status === 'pending' || t.status === 'processing').length
})

const gaugeColor = computed(() => {
  const score = currentAssessment.value.score
  if (score >= 90) return '#22c55e'
  if (score >= 80) return '#3b82f6'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
})

const gaugeDashArray = computed(() => {
  const circumference = 2 * Math.PI * 80
  const ratio = currentAssessment.value.score / 100
  return `${circumference * ratio} ${circumference}`
})

const gradeDesc = computed(() => {
  const grade = currentAssessment.value.grade
  const map = {
    'A': '优秀，消防安全状况良好',
    'B': '良好，存在一般隐患需整改',
    'C': '合格，存在较多隐患需重点整改',
    'D': '不合格，存在重大安全隐患',
  }
  return map[grade] || ''
})

const radarAxes = computed(() => {
  const count = 5
  const cx = 150, cy = 150, r = 100
  const axes = []
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 / count) * i - Math.PI / 2
    axes.push({
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    })
  }
  return axes
})

const radarPoints = computed(() => {
  const count = 5
  const cx = 150, cy = 150
  const levels = [0.2, 0.4, 0.6, 0.8, 1.0]
  return levels.map(level => {
    const r = 100 * level
    const points = []
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 / count) * i - Math.PI / 2
      points.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`)
    }
    return points.join(' ')
  })
})

const radarDataPointsArray = computed(() => {
  const count = 5
  const cx = 150, cy = 150, r = 100
  return dimensions.value.map((dim, i) => {
    const angle = (Math.PI * 2 / count) * i - Math.PI / 2
    const ratio = dim.score / dim.full
    return {
      x: cx + r * ratio * Math.cos(angle),
      y: cy + r * ratio * Math.sin(angle),
    }
  })
})

const radarDataPoints = computed(() => {
  return radarDataPointsArray.value.map(p => `${p.x},${p.y}`).join(' ')
})

const radarLabels = computed(() => {
  const count = 5
  const cx = 150, cy = 150, r = 130
  return dimensions.value.map((dim, i) => {
    const angle = (Math.PI * 2 / count) * i - Math.PI / 2
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      text: dim.name,
    }
  })
})

const filteredItems = computed(() => {
  let list = assessmentItems.value
  if (categoryFilter.value) {
    list = list.filter(i => i.category === categoryFilter.value)
  }
  if (complianceFilter.value !== '') {
    list = list.filter(i => i.is_compliant === complianceFilter.value)
  }
  return list
})

const filteredHistory = computed(() => {
  let list = historyRecords.value
  if (historyTypeFilter.value) {
    list = list.filter(h => h.type === historyTypeFilter.value)
  }
  if (historyGradeFilter.value) {
    list = list.filter(h => h.grade === historyGradeFilter.value)
  }
  return list
})

const filteredRectification = computed(() => {
  let list = rectificationTasks.value
  if (rectStatusFilter.value) {
    list = list.filter(r => r.status === rectStatusFilter.value)
  }
  if (deptFilter.value) {
    list = list.filter(r => r.department === deptFilter.value)
  }
  return list
})

function categoryTagType(category) {
  const map = {
    '建筑防火': 'primary',
    '安全管理': 'success',
    '设施设备': 'warning',
    '人员素质': 'danger',
    '应急能力': 'info',
  }
  return map[category] || ''
}

function typeText(type) {
  const map = { monthly: '月度评估', quarterly: '季度评估', yearly: '年度评估' }
  return map[type] || '月度评估'
}

function typeTagType(type) {
  const map = { monthly: '', quarterly: 'primary', yearly: 'danger' }
  return map[type] || ''
}

function rectStatusText(status) {
  const map = {
    pending: '未整改',
    processing: '整改中',
    completed: '已完成',
    verified: '已复查',
  }
  return map[status] || '未整改'
}

function rectStatusType(status) {
  const map = {
    pending: 'danger',
    processing: 'warning',
    completed: 'primary',
    verified: 'success',
  }
  return map[status] || 'info'
}
</script>

<style scoped>
.fire-assessment-page {
  color: #0f172a;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.subtitle {
  margin: -4px 0 0;
  color: #64748b;
}

.stats-row {
  margin-bottom: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 4px;
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

.stat-info .stat-num {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: #0f172a;
}

.stat-info .stat-num .unit {
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  margin-left: 2px;
}

.stat-info .stat-num.grade-b {
  color: #3b82f6;
}

.stat-info .stat-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  margin-bottom: 12px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 20px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px;
  cursor: pointer;
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
  position: relative;
}

.tab-item:hover {
  color: #334155;
}

.tab-item.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 600;
}

.tab-item .badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  line-height: 18px;
}

.tab-content {
  padding-top: 4px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
}

.danger-text {
  color: #dc2626;
  font-weight: 600;
}

.success-text {
  color: #16a34a;
  font-weight: 600;
}

.muted-text {
  color: #94a3b8;
}

.overview-card {
  height: 100%;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.gauge-wrapper {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 20px;
}

.gauge-container {
  position: relative;
  width: 180px;
  height: 180px;
  flex-shrink: 0;
}

.gauge-svg {
  width: 100%;
  height: 100%;
}

.gauge-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.gauge-score {
  font-size: 36px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1;
}

.gauge-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.grade-badge-wrapper {
  flex: 1;
}

.grade-badge {
  display: inline-block;
  padding: 8px 24px;
  border-radius: 10px;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8px;
}

.grade-a { background: linear-gradient(135deg, #22c55e, #16a34a); }
.grade-b { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.grade-c { background: linear-gradient(135deg, #f59e0b, #d97706); }
.grade-d { background: linear-gradient(135deg, #ef4444, #dc2626); }

.grade-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

.score-progress-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-progress-item .progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.progress-label {
  font-size: 13px;
  color: #334155;
  font-weight: 500;
}

.progress-value {
  font-size: 13px;
  color: #64748b;
}

.progress-bar-bg {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.radar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.radar-chart {
  width: 300px;
  height: 300px;
}

.radar-svg {
  width: 100%;
  height: 100%;
}

.radar-label-text {
  font-size: 12px;
  fill: #64748b;
}

.radar-legend {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  width: 100%;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-name {
  color: #334155;
  flex: 1;
}

.legend-score {
  color: #2563eb;
  font-weight: 600;
}

.issue-list, .suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}

.issue-level {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  height: fit-content;
}

.issue-level.level-high {
  background: #fef2f2;
  color: #dc2626;
}

.issue-level.level-medium {
  background: #fffbeb;
  color: #d97706;
}

.issue-level.level-low {
  background: #eff6ff;
  color: #2563eb;
}

.issue-content {
  flex: 1;
  min-width: 0;
}

.issue-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
}

.issue-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.suggestion-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}

.suggestion-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.suggestion-content {
  flex: 1;
  min-width: 0;
}

.suggestion-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
}

.suggestion-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.grade-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.grade-tag-a { background: linear-gradient(135deg, #22c55e, #16a34a); }
.grade-tag-b { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.grade-tag-c { background: linear-gradient(135deg, #f59e0b, #d97706); }
.grade-tag-d { background: linear-gradient(135deg, #ef4444, #dc2626); }

.mini-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.mini-bar-bg {
  width: 60px;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.mini-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #22c55e);
  border-radius: 3px;
}

.mini-progress-text {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}
</style>
