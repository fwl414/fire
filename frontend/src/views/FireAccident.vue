<template>
  <div class="fire-accident-page">
    <div class="title-row">
      <div>
        <div class="page-title">火灾事故管理</div>
        <p class="subtitle">事故台账 · 事故调查 · 统计分析 · 事故案例 · 全生命周期事故管理</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><WarningFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalAccidents }}</div>
            <div class="stat-label">事故总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Calendar /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.yearAccidents }}</div>
            <div class="stat-label">本年事故</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon yellow"><el-icon><Money /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.directLoss }}<span class="unit">万</span></div>
            <div class="stat-label">直接损失</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><UserFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.casualties }}</div>
            <div class="stat-label">伤亡人数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'ledger' }" @click="activeTab = 'ledger'">
          <el-icon><Notebook /></el-icon>
          事故台账
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'investigation' }" @click="activeTab = 'investigation'">
          <el-icon><Search /></el-icon>
          事故调查
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'analysis' }" @click="activeTab = 'analysis'">
          <el-icon><DataAnalysis /></el-icon>
          统计分析
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'cases' }" @click="activeTab = 'cases'">
          <el-icon><Collection /></el-icon>
          事故案例
        </div>
      </div>

      <div v-if="activeTab === 'ledger'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showAccidentDialog = true">
              <el-icon><Plus /></el-icon>
              新增事故
            </el-button>
            <el-select v-model="levelFilter" placeholder="事故等级" clearable style="width: 140px">
              <el-option label="一般事故" value="general" />
              <el-option label="较大事故" value="major" />
              <el-option label="重大事故" value="serious" />
              <el-option label="特别重大事故" value="critical" />
            </el-select>
            <el-select v-model="causeFilter" placeholder="事故原因" clearable style="width: 160px">
              <el-option label="电气火灾" value="electrical" />
              <el-option label="用火不慎" value="firecareless" />
              <el-option label="吸烟" value="smoking" />
              <el-option label="自燃" value="spontaneous" />
              <el-option label="纵火" value="arson" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
            />
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出台账
            </el-button>
            <el-input v-model="accidentSearch" placeholder="搜索事故名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredAccidents" stripe style="width: 100%">
          <el-table-column prop="accident_no" label="事故编号" width="160" fixed="left" />
          <el-table-column prop="accident_name" label="事故名称" min-width="200" />
          <el-table-column prop="occur_time" label="发生时间" width="160" />
          <el-table-column prop="location" label="发生地点" min-width="180" show-overflow-tooltip />
          <el-table-column prop="cause" label="事故原因" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ causeText(row.cause) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="事故等级" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="levelTagType(row.level)">
                {{ levelText(row.level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="direct_loss" label="直接损失(万)" width="120" align="center" />
          <el-table-column prop="injuries" label="受伤人数" width="100" align="center" />
          <el-table-column prop="deaths" label="死亡人数" width="100" align="center" />
          <el-table-column label="处理状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
              <el-button link type="warning">编辑</el-button>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="accidentList.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'investigation'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="investStatusFilter" placeholder="调查状态" clearable style="width: 140px">
              <el-option label="调查中" value="investigating" />
              <el-option label="已完成" value="completed" />
              <el-option label="已结案" value="closed" />
            </el-select>
            <el-select v-model="investLevelFilter" placeholder="事故等级" clearable style="width: 140px">
              <el-option label="一般事故" value="general" />
              <el-option label="较大事故" value="major" />
              <el-option label="重大事故" value="serious" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出调查报告
            </el-button>
          </div>
        </div>

        <el-table :data="filteredInvestigations" stripe style="width: 100%">
          <el-table-column prop="invest_no" label="调查编号" width="160" fixed="left" />
          <el-table-column prop="accident_name" label="事故名称" min-width="200" />
          <el-table-column prop="accident_level" label="事故等级" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="levelTagType(row.accident_level)">
                {{ levelText(row.accident_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="invest_team" label="调查组" width="180" />
          <el-table-column prop="team_leader" label="组长" width="100" />
          <el-table-column prop="start_date" label="调查开始" width="120" />
          <el-table-column label="调查进度" width="180">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="8" :color="progressColor(row.progress)" />
            </template>
          </el-table-column>
          <el-table-column label="调查状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="investStatusTag(row.status)">
                {{ investStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="report_no" label="调查报告" width="160">
            <template #default="{ row }">
              <el-button v-if="row.report_no" link type="primary">{{ row.report_no }}</el-button>
              <span v-else class="muted-text">待出具</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default>
              <el-button link type="primary">查看</el-button>
              <el-button link type="success">调查报告</el-button>
              <el-button link type="warning">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="investigationList.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'analysis'" class="tab-content">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">事故原因分布</div>
              <EChart :option="causePieOption" height="280px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">事故等级分布</div>
              <EChart :option="levelBarOption" height="280px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">事故类型统计</div>
              <div class="type-stats">
                <div v-for="item in typeStats" :key="item.name" class="type-stat-item">
                  <div class="type-icon" :style="{ background: item.color }">
                    <el-icon><component :is="item.icon" /></el-icon>
                  </div>
                  <div class="type-info">
                    <div class="type-name">{{ item.name }}</div>
                    <div class="type-count">{{ item.count }} 起</div>
                  </div>
                  <div class="type-bar-wrap">
                    <div class="type-bar-bg">
                      <div class="type-bar-fill" :style="{ width: item.percent + '%', background: item.color }"></div>
                    </div>
                    <span class="type-percent">{{ item.percent }}%</span>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card class="chart-card" shadow="never" style="margin-top: 16px">
          <div class="chart-title">年度事故趋势（近6年）</div>
          <EChart :option="yearlyTrendOption" height="320px" />
        </el-card>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :xs="24" :md="12">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">月度事故分布</div>
              <EChart :option="monthlyBarOption" height="280px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">损失金额统计</div>
              <div class="loss-stats">
                <div class="loss-total">
                  <div class="loss-label">累计直接经济损失</div>
                  <div class="loss-value">¥ {{ stats.directLoss }} 万元</div>
                </div>
                <div class="loss-list">
                  <div class="loss-item" v-for="(item, idx) in lossBreakdown" :key="idx">
                    <div class="loss-item-header">
                      <span class="loss-item-name">{{ item.name }}</span>
                      <span class="loss-item-amount">¥{{ item.amount }}万</span>
                    </div>
                    <div class="loss-item-bar-bg">
                      <div class="loss-item-bar-fill" :style="{ width: item.percent + '%', background: item.color }"></div>
                    </div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'cases'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="caseTypeFilter" placeholder="案例类型" clearable style="width: 140px">
              <el-option label="典型案例" value="typical" />
              <el-option label="警示案例" value="warning" />
              <el-option label="成功处置" value="success" />
            </el-select>
            <el-select v-model="caseIndustryFilter" placeholder="行业分类" clearable style="width: 160px">
              <el-option label="商业建筑" value="commercial" />
              <el-option label="工业厂房" value="industrial" />
              <el-option label="住宅小区" value="residential" />
              <el-option label="公众聚集" value="public" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="caseSearch" placeholder="搜索案例名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col v-for="item in filteredCases" :key="item.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="case-card" shadow="hover">
              <div class="case-cover" :class="'level-' + item.level">
                <div class="case-type-badge" :class="item.type">{{ caseTypeText(item.type) }}</div>
                <div class="case-level">{{ levelText(item.level) }}</div>
              </div>
              <div class="case-body">
                <div class="case-title">{{ item.title }}</div>
                <div class="case-meta">
                  <span><el-icon><LocationFilled /></el-icon> {{ item.location }}</span>
                  <span><el-icon><Calendar /></el-icon> {{ item.date }}</span>
                </div>
                <div class="case-desc">{{ item.description }}</div>
                <div class="case-stats">
                  <div class="case-stat">
                    <span class="case-stat-label">直接损失</span>
                    <span class="case-stat-value">¥{{ item.loss }}万</span>
                  </div>
                  <div class="case-stat">
                    <span class="case-stat-label">伤亡人数</span>
                    <span class="case-stat-value">{{ item.casualties }}人</span>
                  </div>
                </div>
              </div>
              <div class="case-footer">
                <el-button size="small" type="primary" link>查看详情</el-button>
                <el-button size="small" type="success" link>经验教训</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <el-dialog v-model="showAccidentDialog" title="新增事故记录" width="650px">
      <el-form :model="accidentForm" label-width="110px">
        <el-form-item label="事故名称">
          <el-input v-model="accidentForm.accident_name" placeholder="请输入事故名称" />
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="发生时间">
              <el-date-picker
                v-model="accidentForm.occur_time"
                type="datetime"
                placeholder="选择发生时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="事故等级">
              <el-select v-model="accidentForm.level" placeholder="请选择事故等级" style="width: 100%">
                <el-option label="一般事故" value="general" />
                <el-option label="较大事故" value="major" />
                <el-option label="重大事故" value="serious" />
                <el-option label="特别重大事故" value="critical" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="发生地点">
          <el-input v-model="accidentForm.location" placeholder="请输入发生地点" />
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="事故原因">
              <el-select v-model="accidentForm.cause" placeholder="请选择事故原因" style="width: 100%">
                <el-option label="电气火灾" value="electrical" />
                <el-option label="用火不慎" value="firecareless" />
                <el-option label="吸烟" value="smoking" />
                <el-option label="自燃" value="spontaneous" />
                <el-option label="纵火" value="arson" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="直接损失(万)">
              <el-input-number v-model="accidentForm.direct_loss" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="受伤人数">
              <el-input-number v-model="accidentForm.injuries" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="死亡人数">
              <el-input-number v-model="accidentForm.deaths" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="事故概况">
          <el-input v-model="accidentForm.description" type="textarea" :rows="3" placeholder="请输入事故概况" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAccidentDialog = false">取消</el-button>
        <el-button type="primary" @click="submitAccident">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { WarningFilled, Calendar, Money, UserFilled, Notebook, Search, DataAnalysis, Collection, Plus, Download, LocationFilled, Lightning, Warning } from '@element-plus/icons-vue'
import EChart from '../components/EChart.vue'

const activeTab = ref('ledger')

const stats = ref({
  totalAccidents: 38,
  yearAccidents: 7,
  directLoss: 586.5,
  casualties: 12,
})

const levelFilter = ref('')
const causeFilter = ref('')
const dateRange = ref([])
const accidentSearch = ref('')

const investStatusFilter = ref('')
const investLevelFilter = ref('')

const caseTypeFilter = ref('')
const caseIndustryFilter = ref('')
const caseSearch = ref('')

const showAccidentDialog = ref(false)
const accidentForm = ref({
  accident_name: '',
  occur_time: '',
  level: '',
  location: '',
  cause: '',
  direct_loss: 0,
  injuries: 0,
  deaths: 0,
  description: '',
})

const accidentList = ref([
  { id: 1, accident_no: 'SG-2026-001', accident_name: '食堂厨房油锅起火事故', occur_time: '2026-08-15 11:30', location: '员工食堂一层厨房', cause: 'firecareless', level: 'general', direct_loss: 5.2, injuries: 0, deaths: 0, status: 'closed', description: '厨师操作不当导致油锅过热起火，及时扑灭' },
  { id: 2, accident_no: 'SG-2026-002', accident_name: '仓库货物自燃事故', occur_time: '2026-06-20 03:15', location: '地下一层仓储区', cause: 'spontaneous', level: 'major', direct_loss: 85.6, injuries: 2, deaths: 0, status: 'completed', description: '化学品存储不当导致自燃，火势蔓延较快' },
  { id: 3, accident_no: 'SG-2026-003', accident_name: '配电室电气火灾', occur_time: '2026-04-10 14:22', location: '地下二层配电室', cause: 'electrical', level: 'general', direct_loss: 12.8, injuries: 0, deaths: 0, status: 'closed', description: '配电柜短路引发火灾，气体灭火系统启动' },
  { id: 4, accident_no: 'SG-2025-012', accident_name: '实验室酒精起火事故', occur_time: '2025-11-08 09:45', location: '实验楼A座3层实验室', cause: 'firecareless', level: 'general', direct_loss: 3.5, injuries: 1, deaths: 0, status: 'closed', description: '实验操作不当导致酒精洒出引燃' },
  { id: 5, accident_no: 'SG-2025-010', accident_name: '宿舍违规用电起火', occur_time: '2025-09-02 22:10', location: '学生宿舍B栋502室', cause: 'electrical', level: 'major', direct_loss: 28.3, injuries: 3, deaths: 1, status: 'closed', description: '使用大功率电器导致线路过载起火' },
  { id: 6, accident_no: 'SG-2025-008', accident_name: '车库车辆自燃事故', occur_time: '2025-07-15 15:30', location: '地下车库B1层', cause: 'spontaneous', level: 'general', direct_loss: 18.0, injuries: 0, deaths: 0, status: 'closed', description: '小轿车发动机舱自燃，消防喷淋启动' },
  { id: 7, accident_no: 'SG-2025-005', accident_name: '吸烟引发杂物间火灾', occur_time: '2025-05-20 16:40', location: '综合办公楼12层杂物间', cause: 'smoking', level: 'general', direct_loss: 2.1, injuries: 0, deaths: 0, status: 'closed', description: '乱扔烟头引燃杂物' },
  { id: 8, accident_no: 'SG-2024-015', accident_name: '重大仓库火灾事故', occur_time: '2024-12-03 02:25', location: '物流仓库B区', cause: 'electrical', level: 'serious', direct_loss: 320.0, injuries: 5, deaths: 2, status: 'closed', description: '电气线路老化引发重大火灾，损失惨重' },
])

const investigationList = ref([
  { id: 1, invest_no: 'DC-2026-001', accident_name: '食堂厨房油锅起火事故', accident_level: 'general', invest_team: '一般事故调查组', team_leader: '张调查员', start_date: '2026-08-16', progress: 100, status: 'closed', report_no: 'BG-DC-2026-001' },
  { id: 2, invest_no: 'DC-2026-002', accident_name: '仓库货物自燃事故', accident_level: 'major', invest_team: '较大事故调查组', team_leader: '李组长', start_date: '2026-06-21', progress: 85, status: 'investigating', report_no: '' },
  { id: 3, invest_no: 'DC-2026-003', accident_name: '配电室电气火灾', accident_level: 'general', invest_team: '一般事故调查组', team_leader: '王调查员', start_date: '2026-04-11', progress: 100, status: 'completed', report_no: 'BG-DC-2026-003' },
  { id: 4, invest_no: 'DC-2025-008', accident_name: '宿舍违规用电起火', accident_level: 'major', invest_team: '较大事故调查组', team_leader: '赵组长', start_date: '2025-09-03', progress: 100, status: 'closed', report_no: 'BG-DC-2025-008' },
  { id: 5, invest_no: 'DC-2024-012', accident_name: '重大仓库火灾事故', accident_level: 'serious', invest_team: '重大事故调查组', team_leader: '孙局长', start_date: '2024-12-04', progress: 100, status: 'closed', report_no: 'BG-DC-2024-012' },
])

const caseList = ref([
  { id: 1, title: '某商场重大火灾事故案例分析', type: 'warning', level: 'serious', location: '北京市朝阳区', date: '2024-08-12', description: '因电气线路老化引发的重大火灾，造成严重人员伤亡和财产损失，教训深刻。', loss: 520, casualties: 28, industry: 'commercial' },
  { id: 2, title: '化工企业爆炸火灾事故', type: 'typical', level: 'critical', location: '江苏省苏州市', date: '2023-11-05', description: '化工厂反应釜超压爆炸引发火灾，由于应急处置得当，未造成更大伤亡。', loss: 1200, casualties: 5, industry: 'industrial' },
  { id: 3, title: '居民楼电动车充电起火', type: 'warning', level: 'major', location: '上海市浦东新区', date: '2025-03-18', description: '电动车在楼道内充电引发火灾，造成人员伤亡，暴露消防安全意识薄弱问题。', loss: 45, casualties: 3, industry: 'residential' },
  { id: 4, title: 'KTV成功疏散案例', type: 'success', level: 'general', location: '广州市天河区', date: '2025-06-22', description: 'KTV包厢起火，由于员工培训到位，疏散有序，300余人全部安全撤离。', loss: 12, casualties: 0, industry: 'public' },
  { id: 5, title: '仓库吸烟引发火灾', type: 'typical', level: 'major', location: '深圳市龙岗区', date: '2024-05-10', description: '仓管员违规吸烟引燃货物，造成较大经济损失，责任人被追究刑事责任。', loss: 280, casualties: 0, industry: 'industrial' },
  { id: 6, title: '酒店厨房火灾成功处置', type: 'success', level: 'general', location: '杭州市西湖区', date: '2025-09-15', description: '酒店厨房油锅起火，厨师正确使用灭火毯，5分钟内成功扑灭，未造成大损失。', loss: 0.8, casualties: 0, industry: 'commercial' },
  { id: 7, title: '医院电气火灾案例', type: 'warning', level: 'major', location: '成都市武侯区', date: '2024-02-28', description: '医院配电间起火，因备用电源和应急措施到位，病人安全转移，无人员伤亡。', loss: 65, casualties: 0, industry: 'public' },
  { id: 8, title: '学校实验室火灾事故', type: 'typical', level: 'general', location: '武汉市洪山区', date: '2025-04-08', description: '学生实验操作不当引发火灾，实验室消防设施发挥作用，及时扑灭。', loss: 8.5, casualties: 2, industry: 'public' },
])

const typeStats = ref([
  { name: '电气火灾', count: 14, percent: 36.8, color: '#ef4444', icon: 'Lightning' },
  { name: '用火不慎', count: 9, percent: 23.7, color: '#f97316', icon: 'Warning' },
  { name: '吸烟', count: 6, percent: 15.8, color: '#eab308', icon: 'Warning' },
  { name: '自燃', count: 5, percent: 13.2, color: '#3b82f6', icon: 'Warning' },
  { name: '其他', count: 4, percent: 10.5, color: '#8b5cf6', icon: 'Warning' },
])

const lossBreakdown = ref([
  { name: '建筑损失', amount: 225.5, percent: 38.4, color: '#ef4444' },
  { name: '设备损失', amount: 168.3, percent: 28.7, color: '#f97316' },
  { name: '货物损失', amount: 120.8, percent: 20.6, color: '#eab308' },
  { name: '其他损失', amount: 71.9, percent: 12.3, color: '#3b82f6' },
])

const causePieOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c}起 ({d}%)'
  },
  legend: {
    orient: 'vertical',
    left: 'left',
    top: 'center',
    itemWidth: 12,
    itemHeight: 12,
    textStyle: { fontSize: 12, color: '#64748b' }
  },
  series: [
    {
      name: '事故原因',
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['65%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      labelLine: {
        show: false
      },
      data: [
        { value: 14, name: '电气火灾', itemStyle: { color: '#ef4444' } },
        { value: 9, name: '用火不慎', itemStyle: { color: '#f97316' } },
        { value: 6, name: '吸烟', itemStyle: { color: '#eab308' } },
        { value: 5, name: '自燃', itemStyle: { color: '#3b82f6' } },
        { value: 4, name: '其他', itemStyle: { color: '#8b5cf6' } },
      ]
    }
  ]
}))

const levelBarOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: '10%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: ['一般事故', '较大事故', '重大事故', '特别重大'],
    axisLabel: {
      fontSize: 11,
      color: '#64748b',
      interval: 0,
      rotate: 0
    },
    axisLine: { lineStyle: { color: '#e2e8f0' } }
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      fontSize: 11,
      color: '#94a3b8'
    },
    splitLine: { lineStyle: { color: '#f1f5f9' } }
  },
  series: [
    {
      name: '事故数量',
      type: 'bar',
      barWidth: '40%',
      data: [
        { value: 22, itemStyle: { color: '#22c55e', borderRadius: [4, 4, 0, 0] } },
        { value: 10, itemStyle: { color: '#f97316', borderRadius: [4, 4, 0, 0] } },
        { value: 5, itemStyle: { color: '#ef4444', borderRadius: [4, 4, 0, 0] } },
        { value: 1, itemStyle: { color: '#7c1d1d', borderRadius: [4, 4, 0, 0] } },
      ]
    }
  ]
}))

const yearlyTrendOption = computed(() => ({
  tooltip: {
    trigger: 'axis'
  },
  legend: {
    data: ['事故起数', '直接损失(万)', '伤亡人数'],
    top: 0,
    textStyle: { fontSize: 12, color: '#64748b' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: '15%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: ['2021年', '2022年', '2023年', '2024年', '2025年', '2026年'],
    axisLabel: { fontSize: 12, color: '#64748b' },
    axisLine: { lineStyle: { color: '#e2e8f0' } }
  },
  yAxis: [
    {
      type: 'value',
      name: '起数/人数',
      axisLabel: { fontSize: 11, color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#f1f5f9' } }
    },
    {
      type: 'value',
      name: '损失(万元)',
      axisLabel: { fontSize: 11, color: '#94a3b8' },
      splitLine: { show: false }
    }
  ],
  series: [
    {
      name: '事故起数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 3, color: '#3b82f6' },
      itemStyle: { color: '#3b82f6' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.02)' }
          ]
        }
      },
      data: [12, 9, 8, 10, 7, 7]
    },
    {
      name: '伤亡人数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 3, color: '#ef4444' },
      itemStyle: { color: '#ef4444' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(239, 68, 68, 0.25)' },
            { offset: 1, color: 'rgba(239, 68, 68, 0.02)' }
          ]
        }
      },
      data: [5, 3, 2, 7, 3, 2]
    },
    {
      name: '直接损失(万)',
      type: 'bar',
      yAxisIndex: 1,
      barWidth: '20%',
      itemStyle: { color: '#f97316', borderRadius: [4, 4, 0, 0] },
      data: [125, 98, 86, 320, 65, 102]
    }
  ]
}))

const monthlyBarOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: '8%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
    axisLabel: { fontSize: 11, color: '#64748b' },
    axisLine: { lineStyle: { color: '#e2e8f0' } }
  },
  yAxis: {
    type: 'value',
    axisLabel: { fontSize: 11, color: '#94a3b8' },
    splitLine: { lineStyle: { color: '#f1f5f9' } }
  },
  series: [
    {
      name: '事故起数',
      type: 'bar',
      barWidth: '50%',
      itemStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#3b82f6' },
            { offset: 1, color: '#93c5fd' }
          ]
        },
        borderRadius: [4, 4, 0, 0]
      },
      data: [3, 2, 4, 5, 6, 4, 3, 5, 2, 1, 2, 1]
    }
  ]
}))

const filteredAccidents = computed(() => {
  let list = accidentList.value
  if (levelFilter.value) list = list.filter(a => a.level === levelFilter.value)
  if (causeFilter.value) list = list.filter(a => a.cause === causeFilter.value)
  if (accidentSearch.value) list = list.filter(a => a.accident_name.includes(accidentSearch.value) || a.accident_no.includes(accidentSearch.value))
  return list
})

const filteredInvestigations = computed(() => {
  let list = investigationList.value
  if (investStatusFilter.value) list = list.filter(i => i.status === investStatusFilter.value)
  if (investLevelFilter.value) list = list.filter(i => i.accident_level === investLevelFilter.value)
  return list
})

const filteredCases = computed(() => {
  let list = caseList.value
  if (caseTypeFilter.value) list = list.filter(c => c.type === caseTypeFilter.value)
  if (caseIndustryFilter.value) list = list.filter(c => c.industry === caseIndustryFilter.value)
  if (caseSearch.value) list = list.filter(c => c.title.includes(caseSearch.value))
  return list
})

function levelText(level) {
  const map = { general: '一般事故', major: '较大事故', serious: '重大事故', critical: '特别重大' }
  return map[level] || level
}

function levelTagType(level) {
  const map = { general: 'success', major: 'warning', serious: 'danger', critical: 'danger' }
  return map[level] || ''
}

function causeText(cause) {
  const map = { electrical: '电气火灾', firecareless: '用火不慎', smoking: '吸烟', spontaneous: '自燃', arson: '纵火', other: '其他' }
  return map[cause] || cause
}

function statusText(status) {
  const map = { investigating: '调查中', completed: '已完成', closed: '已结案' }
  return map[status] || status
}

function statusTagType(status) {
  const map = { investigating: 'warning', completed: 'primary', closed: 'success' }
  return map[status] || ''
}

function investStatusText(status) {
  const map = { investigating: '调查中', completed: '已完成', closed: '已结案' }
  return map[status] || status
}

function investStatusTag(status) {
  const map = { investigating: 'warning', completed: 'primary', closed: 'success' }
  return map[status] || ''
}

function caseTypeText(type) {
  const map = { typical: '典型案例', warning: '警示案例', success: '成功处置' }
  return map[type] || type
}

function progressColor(progress) {
  if (progress >= 100) return '#22c55e'
  if (progress >= 60) return '#3b82f6'
  return '#f59e0b'
}

function submitAccident() {
  ElMessage.success('事故记录创建成功')
  showAccidentDialog.value = false
}
</script>

<style scoped>
.fire-accident-page {
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
  font-size: 13px;
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

.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.yellow { background: linear-gradient(135deg, #eab308, #ca8a04); }
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

.tab-content {
  padding-top: 4px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.muted-text {
  color: #94a3b8;
  font-size: 13px;
}

.chart-card {
  height: 100%;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 16px;
}

.type-stats {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.type-stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: #f8fafc;
  border-radius: 10px;
}

.type-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  flex-shrink: 0;
}

.type-info {
  flex: 1;
  min-width: 0;
}

.type-name {
  font-size: 14px;
  font-weight: 500;
  color: #0f172a;
  margin-bottom: 2px;
}

.type-count {
  font-size: 12px;
  color: #64748b;
}

.type-bar-wrap {
  width: 120px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.type-bar-bg {
  flex: 1;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.type-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.type-percent {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  width: 36px;
  text-align: right;
}

.loss-stats {
  padding: 4px 0;
}

.loss-total {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, #fef2f2, #fff7ed);
  border-radius: 10px;
  margin-bottom: 16px;
}

.loss-label {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 6px;
}

.loss-value {
  font-size: 24px;
  font-weight: 700;
  color: #dc2626;
}

.loss-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.loss-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 13px;
}

.loss-item-name {
  color: #334155;
  font-weight: 500;
}

.loss-item-amount {
  color: #0f172a;
  font-weight: 600;
}

.loss-item-bar-bg {
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.loss-item-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.case-card {
  margin-bottom: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.case-cover {
  height: 120px;
  position: relative;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.case-cover.level-general { background: linear-gradient(135deg, #22c55e, #16a34a); }
.case-cover.level-major { background: linear-gradient(135deg, #f59e0b, #d97706); }
.case-cover.level-serious { background: linear-gradient(135deg, #ef4444, #dc2626); }
.case-cover.level-critical { background: linear-gradient(135deg, #7c1d1d, #450a0a); }

.case-type-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  align-self: flex-start;
}

.case-level {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  text-align: right;
}

.case-body {
  padding: 14px;
}

.case-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.case-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
}

.case-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.case-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.case-stats {
  display: flex;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.case-stat {
  flex: 1;
  text-align: center;
}

.case-stat-label {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.case-stat-value {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.case-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid #f1f5f9;
}
</style>
