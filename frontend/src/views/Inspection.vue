<template>
  <div class="inspection-v119-page">
    <div class="title-row">
      <div>
        <div class="page-title">巡检管理</div>
        <p class="subtitle">巡检计划 · 路线管理 · 隐患排查 · 整改闭环 · 智能辅助识别</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="6" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalPlans }}</div>
            <div class="stat-label">巡检计划</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="6" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="6" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.hazards }}</div>
            <div class="stat-label">发现隐患</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="6" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Clock /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.pendingRectify }}</div>
            <div class="stat-label">待整改</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'plans' }" @click="activeTab = 'plans'">
          <el-icon><Calendar /></el-icon>
          巡检计划
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'hazards' }" @click="activeTab = 'hazards'">
          <el-icon><Warning /></el-icon>
          隐患台账
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'ai-check' }" @click="activeTab = 'ai-check'">
          <el-icon><Cpu /></el-icon>
          智能辅助巡检
        </div>
      </div>

      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="table-toolbar">
          <el-button type="primary" @click="showPlanDialog = true">
            <el-icon><Plus /></el-icon>
            新建计划
          </el-button>
          <el-input v-model="planSearch" placeholder="搜索计划名称" style="width:240px" clearable>
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <el-table :data="filteredPlans" stripe style="width:100%">
          <el-table-column prop="plan_no" label="计划编号" width="160" />
          <el-table-column prop="plan_name" label="计划名称" min-width="180" />
          <el-table-column prop="type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'daily' ? 'info' : row.type === 'weekly' ? 'primary' : 'warning'">
                {{ row.type === 'daily' ? '日检' : row.type === 'weekly' ? '周检' : '月检' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="route_name" label="巡检路线" width="160" />
          <el-table-column prop="inspector" label="巡检员" width="100" />
          <el-table-column prop="next_time" label="下次巡检时间" width="160" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'active' ? 'success' : 'info'">
                {{ row.status === 'active' ? '执行中' : '已停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default>
              <el-button link type="primary">查看</el-button>
              <el-button link type="warning">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'hazards'" class="tab-content">
        <div class="table-toolbar">
          <div class="filter-tags">
            <div class="filter-tag" :class="{ active: hazardFilter === 'all' }" @click="hazardFilter = 'all'">全部隐患</div>
            <div class="filter-tag" :class="{ active: hazardFilter === 'pending' }" @click="hazardFilter = 'pending'">待整改</div>
            <div class="filter-tag" :class="{ active: hazardFilter === 'rectifying' }" @click="hazardFilter = 'rectifying'">整改中</div>
            <div class="filter-tag" :class="{ active: hazardFilter === 'verified' }" @click="hazardFilter = 'verified'">已销号</div>
          </div>
        </div>
        <el-table :data="filteredHazards" stripe style="width:100%">
          <el-table-column prop="hazard_no" label="隐患编号" width="160" />
          <el-table-column prop="title" label="隐患描述" min-width="220" />
          <el-table-column label="等级" width="90">
            <template #default="{ row }">
              <div class="severity-badge" :class="row.level">
                {{ row.level === 'critical' ? '重大' : row.level === 'high' ? '较大' : row.level === 'medium' ? '一般' : '轻微' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="位置" width="180" />
          <el-table-column prop="found_time" label="发现时间" width="160" />
          <el-table-column prop="deadline" label="整改期限" width="160" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="statusTagType(row.status)">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary">详情</el-button>
              <el-button v-if="row.status === 'pending'" link type="warning">派单整改</el-button>
              <el-button v-if="row.status === 'rectifying'" link type="success">复查销号</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'ai-check'" class="tab-content">
        <el-row :gutter="14" align="top">
          <el-col :xs="24" :lg="9">
            <el-card class="card input-card" shadow="never">
              <template #header>
                <div class="header-row">
                  <strong>巡检输入</strong>
                  <el-tag type="info">文本 + 图片</el-tag>
                </div>
              </template>

              <el-form label-position="top">
                <el-form-item label="一键场景">
                  <el-select v-model="selectedScenario" placeholder="选择常用巡检场景" style="width:100%" @change="fillScenario">
                    <el-option v-for="s in scenarios" :key="s.id" :label="s.title" :value="s.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="巡检地点">
                  <el-input v-model="form.location" placeholder="例如：餐饮店后厨楼梯口 / 实验室A区" />
                </el-form-item>
                <el-form-item label="现场描述">
                  <el-input
                    v-model="form.description"
                    type="textarea"
                    :rows="4"
                    resize="none"
                    placeholder="描述现场情况，例如：楼梯口堆放纸箱，消防通道受阻，旁边有插排串联。"
                  />
                </el-form-item>
              </el-form>

              <div class="upload-section">
                <div class="section-title">现场图片</div>
                <div v-if="!uploadedImages.length" class="drop-zone" @click="openFilePicker" @dragover.prevent @drop.prevent="handleDrop">
                  <div class="upload-icon">＋</div>
                  <strong>点击或拖拽上传现场图片</strong>
                  <span>支持 jpg / png / webp，可上传多张现场图片</span>
                  <input ref="fileInputRef" class="hidden-input" type="file" accept="image/*" multiple @change="handleFileInput" />
                </div>

                <div v-else class="image-grid">
                  <div v-for="img in uploadedImages" :key="img.id" class="image-card">
                    <img :src="img.previewUrl" class="preview-img" @click="previewDialog = img" />
                    <div class="image-meta">
                      <strong>{{ img.name }}</strong>
                      <span>{{ formatSize(img.size) }} · {{ img.type || 'image' }}</span>
                      <el-tag size="small" type="success">{{ img.statusText }}</el-tag>
                    </div>
                    <div class="image-actions">
                      <el-button size="small" @click="openFilePicker">重新上传</el-button>
                      <el-button size="small" type="danger" plain @click="removeImage(img.id)">删除</el-button>
                    </div>
                  </div>
                  <input ref="fileInputRef" class="hidden-input" type="file" accept="image/*" multiple @change="handleFileInput" />
                </div>
              </div>

              <div v-if="currentScenario" class="scenario-box">
                <strong>{{ currentScenario.title }}</strong>
                <p>{{ currentScenario.talking_point }}</p>
                <el-tag v-for="t in currentScenario.tags" :key="t" size="small" style="margin:0 6px 6px 0">{{ t }}</el-tag>
              </div>

              <div class="button-row">
                <el-button type="primary" size="large" :loading="loading" @click="runAgent">开始分析</el-button>
                <el-button size="large" @click="reset">清空</el-button>
                <el-button size="large" :disabled="!result" @click="exportReport">导出报告</el-button>
              </div>
            </el-card>
          </el-col>

      <el-col :xs="24" :lg="15">
        <el-card class="card agent-card">
          <template #header>
            <div class="header-row">
              <strong>分析动态进度</strong>
              <el-tag :type="loading ? 'warning' : result ? 'success' : 'info'">{{ loading ? '分析中' : result ? '已完成' : '待启动' }}</el-tag>
            </div>
          </template>
          <div class="agent-flow">
            <div v-for="(step, index) in agentFlowSteps" :key="step.key" class="agent-step" :class="step.status">
              <div class="step-index">{{ index + 1 }}</div>
              <div class="step-body">
                <div class="step-top">
                  <strong>{{ step.title }}</strong>
                  <el-tag size="small" :type="stepStatusType(step.status)">{{ stepStatusText(step.status) }}</el-tag>
                </div>
                <p>{{ step.description }}</p>
                <span v-if="step.detail" class="step-detail">{{ step.detail }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <el-card v-if="!result" class="card empty-workbench">
          <el-empty description="上传现场图片或填写描述后点击“开始分析”，系统会展示识别过程、风险判断、知识库依据和整改闭环。" />
        </el-card>

        <el-row v-if="result" :gutter="12" class="summary-row">
          <el-col :xs="24" :sm="12" :md="6">
            <div class="risk-summary danger-border">
              <span>总体风险等级</span>
              <strong :class="riskClass">{{ riskLevel }}</strong>
              <small>{{ priorityText }}</small>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <div class="risk-summary">
              <span>风险评分</span>
              <strong>{{ riskScore }}</strong>
              <small>满分 100</small>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <div class="risk-summary">
              <span>发现隐患</span>
              <strong>{{ hazards.length }}</strong>
              <small>高风险 {{ highRiskCount }} 项</small>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <div class="risk-summary">
              <span>巡检记录</span>
              <strong>{{ recordId || '未保存' }}</strong>
              <small>{{ recordId ? '已自动沉淀' : '可手动生成' }}</small>
            </div>
          </el-col>
        </el-row>
      </el-col>
    </el-row>

    <el-alert
      v-if="result?.local_image_fallback"
      title="当前视觉模型未启用或调用失败，图片结果使用本地演示兜底。它不会伪装成真实视觉识别；启用视觉模型后可获得真实图片理解结果。"
      type="warning"
      show-icon
      class="card"
    />

    <el-card v-if="result" class="card result-tabs-card">
      <template #header>
        <div class="header-row">
          <strong>巡检结果工作台</strong>
          <div class="action-row">
            <el-button size="small" @click="saveInspectionRecord">生成/同步记录</el-button>
            <el-button size="small" type="primary" @click="exportReport">导出报告</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="resultTab">
        <el-tab-pane label="风险总览" name="overview">
          <el-row :gutter="12">
            <el-col :xs="24" :md="10">
              <el-card shadow="never" class="inner-card">
                <template #header>风险结论</template>
                <el-alert :title="plainConclusion" :type="riskAlertType" show-icon style="margin-bottom:12px" />
                <p class="plain-text">{{ riskReason }}</p>
                <div class="hazard-tags">
                  <el-tag v-for="h in hazards" :key="h" :type="tagTypeByHazard(h)" effect="plain" size="large">{{ h }}</el-tag>
                </div>
              </el-card>
            </el-col>
            <el-col :xs="24" :md="14">
              <el-card shadow="never" class="inner-card">
                <template #header>识别依据与优先处置</template>
                <el-descriptions border :column="1">
                  <el-descriptions-item label="为什么判定">{{ resultExplanation.why_high_risk }}</el-descriptions-item>
                  <el-descriptions-item label="评分逻辑">{{ resultExplanation.score_logic }}</el-descriptions-item>
                  <el-descriptions-item label="优先整改">{{ resultExplanation.priority_fix }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="隐患识别" name="hazards">
          <el-table :data="hazardDetails" border>
            <el-table-column prop="hazard_name" label="隐患名称" width="150" />
            <el-table-column prop="risk_level" label="风险等级" width="110">
              <template #default="{ row }"><el-tag :type="riskTagType(row.risk_level)">{{ row.risk_level }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column prop="evidence" label="识别依据" min-width="220" />
            <el-table-column prop="possible_consequence" label="可能后果" min-width="220" />
            <el-table-column prop="suggestion" label="整改建议" min-width="240" />
            <el-table-column prop="need_immediate_fix" label="立即整改" width="100">
              <template #default="{ row }"><el-tag :type="row.need_immediate_fix ? 'danger' : 'info'">{{ row.need_immediate_fix ? '是' : '否' }}</el-tag></template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!hazardDetails.length" description="未发现明显隐患" />
        </el-tab-pane>

        <el-tab-pane label="知识库引用依据" name="rag">
          <el-row :gutter="12">
            <el-col :xs="24" :md="8" v-for="ref in ragReferenceCards" :key="ref.id">
              <div class="knowledge-card">
                <div class="header-row">
                  <el-tag size="small">{{ ref.category }}</el-tag>
                  <span class="similarity">{{ ref.similarity }}%</span>
                </div>
                <h3>{{ ref.title }}</h3>
                <p>{{ ref.summary }}</p>
                <div class="muted">来源：{{ ref.source }}</div>
                <el-collapse>
                  <el-collapse-item title="展开查看依据" :name="ref.id">
                    <p class="plain-text">{{ ref.content_preview }}</p>
                    <div class="kw-line">{{ (ref.matched_keywords || []).join('、') }}</div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </el-col>
          </el-row>
          <el-empty v-if="!ragReferenceCards.length" description="暂无知识库引用结果" />
        </el-tab-pane>

        <el-tab-pane label="分析决策链" name="chain">
          <el-timeline>
            <el-timeline-item v-for="node in decisionChain" :key="node.id" :timestamp="node.title" placement="top">
              <el-card shadow="never" class="chain-card">
                <div class="header-row"><strong>{{ node.action }}</strong><el-tag type="success">{{ node.status }}</el-tag></div>
                <p><b>输入：</b>{{ node.input }}</p>
                <p><b>输出：</b>{{ node.output }}</p>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <el-tab-pane label="工具中心" name="tools">
          <el-table :data="toolCenter" border>
            <el-table-column prop="tool_name" label="工具" width="180" />
            <el-table-column prop="purpose" label="用途" min-width="240" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }"><el-tag :type="toolStatusType(row.status)">{{ row.status }}</el-tag></template>
            </el-table-column>
            <el-table-column label="输入参数" min-width="220">
              <template #default="{ row }">{{ row.input_params?.summary }}</template>
            </el-table-column>
            <el-table-column label="输出结果" min-width="240">
              <template #default="{ row }">{{ row.output_result?.summary }}</template>
            </el-table-column>
            <el-table-column prop="duration_ms" label="耗时(ms)" width="100" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="整改工单" name="orders">
          <div class="header-row" style="margin-bottom:12px">
            <el-alert v-if="workorders.summary" :title="workorders.summary" type="success" show-icon style="flex:1" />
            <el-button v-if="workorders.orders?.length" type="primary" @click="simulateFirstOrder">模拟闭环</el-button>
          </div>
          <el-table :data="workorders.orders || []" border>
            <el-table-column prop="hazard" label="隐患" width="150" />
            <el-table-column prop="priority" label="优先级" width="90" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="responsible_role" label="责任角色" width="170" />
            <el-table-column prop="deadline" label="整改时限" width="160" />
            <el-table-column prop="recommended_action" label="整改建议" />
          </el-table>
          <el-timeline v-if="closedOrder.timeline" style="margin-top:12px">
            <el-timeline-item v-for="t in closedOrder.timeline" :key="t.status + t.time" :timestamp="t.time">
              <strong>{{ t.status }}</strong> - {{ t.operator }}：{{ t.note }}
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <el-tab-pane label="巡检报告" name="report">
          <el-alert v-if="report.summary" :title="report.summary" type="info" show-icon style="margin-bottom:12px" />
          <h3>{{ report.title || '消防巡检报告' }}</h3>
          <el-timeline>
            <el-timeline-item v-for="s in report.sections || reportSections" :key="s.title">
              <strong>{{ s.title }}</strong><p>{{ s.content }}</p>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <el-tab-pane label="技术细节" name="tech">
          <el-collapse>
            <el-collapse-item title="分析追踪" name="trace"><pre>{{ JSON.stringify(result.agent_trace || result.agent_summary || {}, null, 2) }}</pre></el-collapse-item>
            <el-collapse-item title="原始结果 JSON" name="json"><pre>{{ JSON.stringify(result, null, 2) }}</pre></el-collapse-item>
          </el-collapse>
        </el-tab-pane>
      </el-tabs>
    </el-card>
      </div>

    </el-card>

    <el-dialog :model-value="!!previewDialog" title="现场图片预览" width="760px" @update:model-value="v => { if (!v) previewDialog=null }" @close="previewDialog=null">
      <img v-if="previewDialog" :src="previewDialog.previewUrl" class="dialog-img" />
      <template #footer>
        <el-button @click="previewDialog=null">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import request from "../api"
import { riskTagType } from "../utils/riskStyle"
import { ElMessage } from "element-plus"
import {
  Document, CircleCheck, Warning, Clock, Calendar, Cpu, Plus, Search
} from '@element-plus/icons-vue'

const activeTab = ref('plans')
const planSearch = ref('')
const hazardFilter = ref('all')
const showPlanDialog = ref(false)

const stats = ref({
  totalPlans: 12,
  completed: 8,
  hazards: 23,
  pendingRectify: 7,
})

const plans = ref([
  { plan_no: 'INSP-2026-001', plan_name: '综合办公楼日常巡检', type: 'daily', route_name: '办公楼A路线', inspector: '张工', next_time: '2026-09-22 09:00', status: 'active' },
  { plan_no: 'INSP-2026-002', plan_name: '实验楼周度巡检', type: 'weekly', route_name: '实验楼B路线', inspector: '李工', next_time: '2026-09-23 10:00', status: 'active' },
  { plan_no: 'INSP-2026-003', plan_name: '学生宿舍月度巡检', type: 'monthly', route_name: '宿舍C区路线', inspector: '王工', next_time: '2026-09-30 14:00', status: 'active' },
  { plan_no: 'INSP-2026-004', plan_name: '图书馆消防设施巡检', type: 'weekly', route_name: '图书馆D路线', inspector: '赵工', next_time: '2026-09-25 08:30', status: 'active' },
  { plan_no: 'INSP-2026-005', plan_name: '地下车库巡检', type: 'daily', route_name: '车库B1路线', inspector: '陈工', next_time: '2026-09-22 16:00', status: 'inactive' },
])

const hazardLedger = ref([
  { hazard_no: 'HZD-2026-045', title: '消防通道堆放杂物堵塞', level: 'high', location: '综合办公楼A座3楼东侧', found_time: '2026-09-20 14:30', deadline: '2026-09-23', status: 'pending' },
  { hazard_no: 'HZD-2026-044', title: '烟感探测器故障报警', level: 'medium', location: '实验楼B座2层203室', found_time: '2026-09-20 10:15', deadline: '2026-09-25', status: 'rectifying' },
  { hazard_no: 'HZD-2026-043', title: '灭火器压力不足需更换', level: 'low', location: '学生宿舍C区1楼大厅', found_time: '2026-09-19 16:40', deadline: '2026-09-28', status: 'verified' },
  { hazard_no: 'HZD-2026-042', title: '消火栓箱内水带缺失', level: 'critical', location: '图书馆D馆地下一层', found_time: '2026-09-19 09:20', deadline: '2026-09-21', status: 'rectifying' },
  { hazard_no: 'HZD-2026-041', title: '应急照明灯具不亮', level: 'medium', location: '综合办公楼A座地下室', found_time: '2026-09-18 15:50', deadline: '2026-09-24', status: 'verified' },
  { hazard_no: 'HZD-2026-040', title: '防火门闭门器损坏', level: 'high', location: '实验楼B座安全出口', found_time: '2026-09-18 11:30', deadline: '2026-09-22', status: 'pending' },
])

const filteredPlans = computed(() => {
  if (!planSearch.value) return plans.value
  return plans.value.filter(p => p.plan_name.includes(planSearch.value) || p.plan_no.includes(planSearch.value))
})

const filteredHazards = computed(() => {
  if (hazardFilter.value === 'all') return hazardLedger.value
  if (hazardFilter.value === 'pending') return hazardLedger.value.filter(h => h.status === 'pending')
  if (hazardFilter.value === 'rectifying') return hazardLedger.value.filter(h => h.status === 'rectifying')
  if (hazardFilter.value === 'verified') return hazardLedger.value.filter(h => h.status === 'verified')
  return hazardLedger.value
})

function statusText(status) {
  const map = { pending: '待整改', rectifying: '整改中', verified: '已销号', closed: '已关闭' }
  return map[status] || '待整改'
}

function statusTagType(status) {
  if (status === 'pending') return 'danger'
  if (status === 'rectifying') return 'warning'
  if (status === 'verified' || status === 'closed') return 'success'
  return 'info'
}

const scenarios = ref([])
const selectedScenario = ref("")
const currentScenario = ref(null)
const uploadedImages = ref([])
const fileInputRef = ref(null)
const loading = ref(false)
const result = ref(null)
const workorders = ref({})
const closedOrder = ref({})
const report = ref({})
const savedRecord = ref({})
const resultTab = ref("overview")
const previewDialog = ref(null)
let flowTimer = null

const form = ref({ location: "实验室A区", description: "消防通道被杂物堵塞，插排串联，旁边堆放纸箱。" })

const AGENT_STEPS = [
  { key: "task_understanding", title: "任务理解", description: "正在理解巡检任务、地点、文字描述和图片输入。" },
  { key: "image_recognition", title: "图像识别", description: "正在识别图片中的消防设施与环境风险。" },
  { key: "risk_extraction", title: "风险提取", description: "正在提取消防通道、设施遮挡、电气线路、可燃物等隐患。" },
  { key: "rag_retrieval", title: "知识库检索", description: "正在检索消防法规、巡检标准和整改知识库。" },
  { key: "rule_check", title: "规则校验", description: "正在匹配消防安全规则并校验模型输出。" },
  { key: "risk_scoring", title: "风险评分", description: "正在融合隐患数量、严重度和场景因素计算风险等级。" },
  { key: "rectification_suggestion", title: "整改建议", description: "正在生成整改措施、责任角色和闭环复查要求。" },
  { key: "report_generation", title: "报告生成", description: "正在生成巡检报告和可导出内容。" },
]
const agentFlowSteps = ref(AGENT_STEPS.map(s => ({ ...s, status: "waiting", detail: "" })))

const hazards = computed(() => result.value?.hazards || result.value?.risk?.hazards || result.value?.agent_trace?.risk_result?.hazards || [])
const riskLevel = computed(() => result.value?.risk_level || result.value?.risk?.risk_level || result.value?.agent_trace?.risk_result?.risk_level || "未评估")
const riskScore = computed(() => result.value?.risk_score ?? result.value?.risk?.risk_score ?? result.value?.agent_trace?.risk_result?.risk_score ?? 0)
const riskAlertType = computed(() => riskTagType(riskLevel.value) === "danger" ? "error" : riskTagType(riskLevel.value))
const riskClass = computed(() => riskLevel.value.includes("高") || riskLevel.value.includes("严重") ? "risk-high" : riskLevel.value.includes("中") ? "risk-mid" : "risk-low")
const hazardDetails = computed(() => result.value?.hazard_results || (result.value?.hazard_items || []).map((x, i) => ({ id: i, hazard_name: x.hazard_name || x.type, risk_level: x.risk_level || x.severity, category: x.category, evidence: x.reason, possible_consequence: x.possible_consequence, suggestion: x.measure, need_immediate_fix: x.need_immediate_fix })))
const highRiskCount = computed(() => hazardDetails.value.filter(h => ["高风险", "严重风险"].includes(h.risk_level) || h.need_immediate_fix).length)
const recordId = computed(() => savedRecord.value?.record_id || result.value?.record_id || "")
const priorityText = computed(() => riskLevel.value.includes("严重") || riskLevel.value.includes("高") ? "建议立即整改" : riskLevel.value.includes("中") ? "建议限期整改" : "建议持续优化")
const plainConclusion = computed(() => `本次巡检发现 ${hazards.value.length} 项消防安全隐患，综合风险评分 ${riskScore.value} 分，风险等级为 ${riskLevel.value}。`)
const riskReason = computed(() => result.value?.risk_reason || (hazards.value.length ? `风险主要来自：${hazards.value.join("、")}。` : "未发现明显消防安全隐患，建议保持日常巡检。"))
const ragReferenceCards = computed(() => result.value?.rag_reference_cards || (result.value?.rag_references || []).map((r, i) => ({ id: r.chunk_id || i, title: r.title || r.source, category: r.category || "消防知识", similarity: Math.round((r.score || 0) * 100), summary: (r.content || "").slice(0, 160), source: r.source || "系统知识库", content_preview: r.content || "", matched_keywords: r.matched_keywords || [] })))
const decisionChain = computed(() => result.value?.agent_decision_chain || [])
const toolCenter = computed(() => result.value?.agent_tool_center || result.value?.tool_calls || [])
const resultExplanation = computed(() => result.value?.result_explanation || { why_high_risk: riskReason.value, score_logic: `风险评分 ${riskScore.value}`, priority_fix: result.value?.suggestion || "建议现场复核并整改。" })
const reportSections = computed(() => [
  { title: "巡检基本信息", content: `地点：${form.value.location || "未填写"}；生成时间：${new Date().toLocaleString()}` },
  { title: "图片识别结果", content: hazards.value.length ? `识别到：${hazards.value.join("、")}` : "未发现明显隐患" },
  { title: "风险等级", content: `${riskLevel.value}，评分 ${riskScore.value}` },
  { title: "整改建议", content: resultExplanation.value.priority_fix },
])

const loadScenarios = async () => {
  try { scenarios.value = (await request.get("/api/demo/scenarios")).data }
  catch { scenarios.value = [] }
}
const fillScenario = () => {
  const s = scenarios.value.find(x => x.id === selectedScenario.value)
  currentScenario.value = s || null
  if (s) { form.value.location = s.location; form.value.description = s.description }
}

const openFilePicker = () => fileInputRef.value?.click()
const createImageItem = file => ({ id: `${Date.now()}_${Math.random()}`, file, previewUrl: URL.createObjectURL(file), name: file.name, size: file.size, type: file.type, status: "ready", statusText: "已选择" })
const addFiles = files => {
  const imageFiles = Array.from(files || []).filter(f => f.type.startsWith("image/"))
  if (!imageFiles.length) return ElMessage.warning("请选择图片文件")
  uploadedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl))
  uploadedImages.value = imageFiles.slice(0, 5).map(createImageItem)
}
const handleFileInput = e => { addFiles(e.target.files); e.target.value = "" }
const handleDrop = e => addFiles(e.dataTransfer.files)
const removeImage = id => {
  const old = uploadedImages.value.find(x => x.id === id)
  if (old) URL.revokeObjectURL(old.previewUrl)
  uploadedImages.value = uploadedImages.value.filter(x => x.id !== id)
}
const formatSize = size => {
  if (!size) return "0 B"
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

const resetFlow = () => { agentFlowSteps.value = AGENT_STEPS.map(s => ({ ...s, status: "waiting", detail: "" })) }
const simulateFlow = () => {
  clearInterval(flowTimer)
  resetFlow()
  let index = 0
  agentFlowSteps.value[0].status = "running"
  flowTimer = setInterval(() => {
    if (!loading.value) return
    agentFlowSteps.value = agentFlowSteps.value.map((s, i) => {
      if (i < index) return { ...s, status: "completed", detail: "已完成" }
      if (i === index) return { ...s, status: "running", detail: s.description }
      return { ...s, status: "waiting", detail: "" }
    })
    index = Math.min(index + 1, AGENT_STEPS.length - 1)
  }, 680)
}
const completeFlow = () => {
  clearInterval(flowTimer)
  agentFlowSteps.value = agentFlowSteps.value.map((s, i) => ({ ...s, status: "completed", detail: result.value?.agent_steps?.[i] || "已完成" }))
}
const failFlow = () => {
  clearInterval(flowTimer)
  agentFlowSteps.value = agentFlowSteps.value.map((s, i) => i === 0 ? { ...s, status: "failed", detail: "分析暂未完成" } : s)
}

const runAgent = async () => {
  if (!form.value.description && !uploadedImages.value.length) return ElMessage.warning("请填写现场描述或上传图片")
  loading.value = true
  result.value = null
  workorders.value = {}
  closedOrder.value = {}
  report.value = {}
  savedRecord.value = {}
  // 这里要重置的是结果区的页签（el-tabs v-model="resultTab"）。
  // 早先误写成 activeTab，而 activeTab 是外层「巡检计划/隐患台账/智能辅助巡检」的开关，
  // 被置成 "overview" 后三个 v-if 分支全部不成立，整个 tab 内容区连同输入表单和结果区一起被卸载，
  // 表现为点完「开始分析」页面空白。
  resultTab.value = "overview"
  simulateFlow()
  try {
    const fd = new FormData()
    fd.append("location", form.value.location || "")
    fd.append("description", form.value.description || "")
    if (uploadedImages.value[0]?.file) fd.append("file", uploadedImages.value[0].file)
    uploadedImages.value.slice(1).forEach(img => fd.append("images", img.file))
    const res = await request.post("/api/inspection/analyze", fd, { headers: { "Content-Type": "multipart/form-data" } })
    result.value = res.data
    savedRecord.value = result.value?.record_id ? { record_id: result.value.record_id, message: "系统已自动保存巡检记录" } : {}
    workorders.value = (await request.post("/api/workorders/generate", { location: form.value.location, hazards: hazards.value, risk_level: riskLevel.value, risk_score: riskScore.value })).data
    report.value = (await request.post("/api/reports/inspection", { location: form.value.location, hazards: hazards.value, risk_level: riskLevel.value, risk_score: riskScore.value, workorders: workorders.value.orders || [] })).data
    completeFlow()
    ElMessage.success("巡检分析完成")
  } catch (e) {
    console.error(e)
    failFlow()
    ElMessage.error("分析暂未完成，请稍后重试。")
  } finally {
    loading.value = false
  }
}

const saveInspectionRecord = async () => {
  if (!result.value) return
  savedRecord.value = (await request.post("/api/records/save-inspection", { location: form.value.location, description: form.value.description, hazards: hazards.value, risk_level: riskLevel.value, risk_score: riskScore.value, result: result.value, workorders: workorders.value.orders || [], report: report.value })).data
  ElMessage.success("巡检记录已同步保存")
}
const exportReport = () => {
  if (!result.value) return
  const lines = [
    "消防巡检报告",
    "====================",
    `巡检地点：${form.value.location || "未填写"}`,
    `生成时间：${new Date().toLocaleString()}`,
    `风险等级：${riskLevel.value}`,
    `风险评分：${riskScore.value}`,
    `识别隐患：${hazards.value.join("、") || "无"}`,
    "",
    "一、隐患明细",
    ...hazardDetails.value.map((h, i) => `${i + 1}. ${h.hazard_name}｜${h.risk_level}\n依据：${h.evidence}\n后果：${h.possible_consequence}\n建议：${h.suggestion}`),
    "",
    "二、知识库引用依据",
    ...ragReferenceCards.value.map((r, i) => `${i + 1}. ${r.title}｜${r.category}｜相似度 ${r.similarity}%\n${r.summary}`),
    "",
    "三、系统结果解释",
    resultExplanation.value.why_high_risk,
    resultExplanation.value.priority_fix,
  ]
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `消防巡检报告_${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}
const reset = () => {
  form.value = { location: "", description: "" }
  selectedScenario.value = ""
  currentScenario.value = null
  uploadedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl))
  uploadedImages.value = []
  result.value = null
  workorders.value = {}
  report.value = {}
  savedRecord.value = {}
  resetFlow()
}
const simulateFirstOrder = async () => {
  const first = (workorders.value.orders || [])[0]
  if (!first) return
  closedOrder.value = (await request.post("/api/workorders/simulate-flow", first)).data
}

const stepStatusType = status => ({ completed: "success", running: "warning", failed: "danger", waiting: "info" }[status] || "info")
const stepStatusText = status => ({ completed: "已完成", running: "执行中", failed: "失败", waiting: "等待中" }[status] || status)
const toolStatusType = status => ["success", "completed"].includes(status) ? "success" : status === "fallback" ? "warning" : status === "failed" ? "danger" : "info"
const tagTypeByHazard = h => h.includes("通道") || h.includes("出口") || h.includes("电动车") || h.includes("消防栓") ? "danger" : h.includes("电气") ? "warning" : "info"

onMounted(loadScenarios)
onBeforeUnmount(() => {
  clearInterval(flowTimer)
  uploadedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl))
})
</script>

<style scoped>
.inspection-v119-page { color:#0f172a; }
.title-row { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; }
.subtitle { margin: -4px 0 0; color:#64748b; }

.stats-row { margin-bottom: 14px; }

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
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }

.stat-info .stat-num {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: #0f172a;
}

.stat-info .stat-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.module-card { margin-bottom: 12px; }

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
}

.tab-item:hover {
  color: #334155;
}

.tab-item.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 600;
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

.filter-tags {
  display: flex;
  gap: 8px;
}

.filter-tag {
  padding: 6px 16px;
  border-radius: 20px;
  background: #f1f5f9;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-tag:hover {
  background: #e2e8f0;
}

.filter-tag.active {
  background: #dbeafe;
  color: #2563eb;
  font-weight: 600;
}

.severity-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
}

.severity-badge.critical {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.severity-badge.high {
  background: #fffbeb;
  color: #d97706;
  border: 1px solid #fde68a;
}

.severity-badge.medium {
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}

.severity-badge.low {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
}

.card { margin-bottom: 12px; }
.header-row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.action-row, .button-row { display:flex; gap:10px; flex-wrap:wrap; }
.input-card { border-top:4px solid #409eff; }
.upload-section { margin: 4px 0 12px; }
.section-title { font-weight:700; color:#0f172a; margin-bottom:10px; }
.drop-zone { min-height:190px; border:1.5px dashed #93c5fd; border-radius:16px; background:linear-gradient(180deg,#f8fbff,#eef6ff); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; cursor:pointer; text-align:center; color:#2563eb; transition:.2s; }
.drop-zone:hover { border-color:#409eff; transform:translateY(-1px); }
.drop-zone span { color:#64748b; font-size:13px; }
.upload-icon { width:52px; height:52px; border-radius:50%; background:#dbeafe; display:flex; align-items:center; justify-content:center; font-size:32px; color:#2563eb; }
.hidden-input { display:none; }
.image-grid { display:grid; grid-template-columns:1fr; gap:10px; }
.image-card { border:1px solid #e2e8f0; border-radius:14px; background:#fff; padding:10px; display:grid; grid-template-columns:110px 1fr; gap:10px; align-items:center; }
.preview-img { width:110px; height:90px; object-fit:cover; border-radius:10px; cursor:zoom-in; background:#f1f5f9; }
.image-meta { display:flex; flex-direction:column; gap:6px; min-width:0; }
.image-meta strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.image-meta span { color:#64748b; font-size:12px; }
.image-actions { grid-column:1 / -1; display:flex; gap:8px; }
.scenario-box { background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:10px; margin-bottom:12px; }
.scenario-box p { color:#64748b; line-height:1.6; margin:6px 0; }
.agent-card { min-height: 360px; }
.agent-flow { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px; }
.agent-step { display:flex; gap:10px; border:1px solid #e5e7eb; background:#fff; border-radius:14px; padding:12px; min-height:92px; position:relative; overflow:hidden; }
.agent-step.running { border-color:#f59e0b; background:#fffbeb; }
.agent-step.completed { border-color:#86efac; background:#f0fdf4; }
.agent-step.failed { border-color:#fecaca; background:#fff1f2; }
.agent-step.running::after { content:""; position:absolute; left:0; bottom:0; height:3px; width:40%; background:#f59e0b; animation:loadingbar 1.1s infinite alternate; }
@keyframes loadingbar { from { width:25%; } to { width:92%; } }
.step-index { width:32px; height:32px; border-radius:50%; background:#e0f2fe; color:#0369a1; display:flex; align-items:center; justify-content:center; font-weight:800; flex:0 0 auto; }
.step-body { flex:1; min-width:0; }
.step-top { display:flex; justify-content:space-between; gap:8px; align-items:center; }
.step-body p { margin:6px 0; color:#64748b; line-height:1.5; font-size:13px; }
.step-detail { color:#2563eb; font-size:12px; }
.empty-workbench { min-height: 180px; display:flex; align-items:center; justify-content:center; }
.summary-row { margin-bottom: 12px; }
.risk-summary { border:1px solid #e5e7eb; border-radius:16px; background:#fff; padding:14px; min-height:104px; display:flex; flex-direction:column; justify-content:center; gap:6px; box-shadow:0 8px 24px rgba(15,23,42,.05); }
.risk-summary span { color:#64748b; font-size:13px; }
.risk-summary strong { font-size:28px; line-height:1; }
.risk-summary small { color:#94a3b8; }
.danger-border { border-top:4px solid #ef4444; }
.risk-high { color:#ef4444; }
.risk-mid { color:#f59e0b; }
.risk-low { color:#16a34a; }
.result-tabs-card :deep(.el-tabs__content) { padding-top: 8px; }
.inner-card { min-height: 280px; }
.plain-text { color:#475569; line-height:1.8; margin:0 0 12px; }
.hazard-tags { display:flex; gap:8px; flex-wrap:wrap; }
.knowledge-card { border:1px solid #e5e7eb; border-radius:14px; padding:12px; min-height:250px; margin-bottom:12px; background:#fff; }
.knowledge-card h3 { margin:10px 0 8px; font-size:16px; }
.knowledge-card p { color:#475569; line-height:1.7; }
.similarity { color:#2563eb; font-weight:800; }
.muted { color:#94a3b8; font-size:12px; margin:8px 0; }
.kw-line { color:#2563eb; font-size:12px; }
.chain-card p { color:#475569; line-height:1.7; }
.dialog-img { width:100%; max-height:70vh; object-fit:contain; border-radius:12px; background:#0f172a; }
pre { white-space:pre-wrap; max-height:360px; overflow:auto; background:#0f172a; color:#e5e7eb; padding:12px; border-radius:10px; }
@media (max-width: 900px) { .agent-flow { grid-template-columns:1fr; } .title-row { flex-direction:column; } }
</style>
