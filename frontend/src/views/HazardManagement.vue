<template>
  <div class="hazard-page">
    <div class="title-row">
      <div>
        <div class="page-title">隐患排查治理</div>
        <p class="subtitle">风险分级管控 · 隐患排查治理 · 双重预防机制</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><WarningFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.riskPoints }}</div>
            <div class="stat-label">风险点总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon yellow"><el-icon><InfoFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.generalHazards }}</div>
            <div class="stat-label">一般隐患</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><CircleCloseFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.majorHazards }}</div>
            <div class="stat-label">重大隐患</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheckFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.completionRate }}%</div>
            <div class="stat-label">整改完成率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'risk' }" @click="activeTab = 'risk'">
          <el-icon><Histogram /></el-icon>
          风险分级管控
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'checklist' }" @click="activeTab = 'checklist'">
          <el-icon><DocumentChecked /></el-icon>
          隐患排查清单
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'ledger' }" @click="activeTab = 'ledger'">
          <el-icon><Notebook /></el-icon>
          隐患治理台账
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'analysis' }" @click="activeTab = 'analysis'">
          <el-icon><DataAnalysis /></el-icon>
          统计分析
        </div>
      </div>

      <div v-if="activeTab === 'risk'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              新增风险点
            </el-button>
            <el-select v-model="riskLevelFilter" placeholder="风险等级" clearable style="width: 140px">
              <el-option label="重大风险（红）" value="red" />
              <el-option label="较大风险（橙）" value="orange" />
              <el-option label="一般风险（黄）" value="yellow" />
              <el-option label="低风险（蓝）" value="blue" />
            </el-select>
            <el-select v-model="riskDeptFilter" placeholder="责任部门" clearable style="width: 160px">
              <el-option label="安全保卫部" value="安全保卫部" />
              <el-option label="设备管理部" value="设备管理部" />
              <el-option label="后勤保障部" value="后勤保障部" />
              <el-option label="物业管理部" value="物业管理部" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="riskSearch" placeholder="搜索风险点名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <div v-for="(group, level) in groupedRiskPoints" :key="level" class="risk-group">
          <div class="risk-group-header">
            <div class="risk-level-badge" :class="level">{{ levelText(level) }}</div>
            <span class="risk-group-count">共 {{ group.length }} 个风险点</span>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="point in group" :key="point.id">
              <el-card class="risk-card" shadow="hover" :class="'level-' + level">
                <div class="risk-card-header">
                  <div class="risk-level-tag" :class="level">{{ levelText(level) }}</div>
                  <el-tag size="small" :type="point.status === 'controlled' ? 'success' : 'warning'">
                    {{ point.status === 'controlled' ? '可控' : '需关注' }}
                  </el-tag>
                </div>
                <div class="risk-name">{{ point.name }}</div>
                <div class="risk-area">
                  <el-icon><LocationFilled /></el-icon>
                  {{ point.area }}
                </div>
                <div class="risk-detail">
                  <div class="detail-item">
                    <span class="label">管控措施</span>
                    <span class="value">{{ point.measures }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="label">责任部门</span>
                    <span class="value">{{ point.department }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="label">责任人</span>
                    <span class="value">{{ point.person }}</span>
                  </div>
                </div>
                <div class="risk-card-actions">
                  <el-button size="small" type="primary" link>查看详情</el-button>
                  <el-button size="small" type="warning" link>编辑</el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </div>

      <div v-if="activeTab === 'checklist'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              新增排查项
            </el-button>
            <el-select v-model="checklistCycleFilter" placeholder="排查周期" clearable style="width: 140px">
              <el-option label="每日" value="daily" />
              <el-option label="每周" value="weekly" />
              <el-option label="每月" value="monthly" />
              <el-option label="每季度" value="quarterly" />
            </el-select>
            <el-select v-model="checklistResultFilter" placeholder="排查结果" clearable style="width: 140px">
              <el-option label="正常" value="normal" />
              <el-option label="有隐患" value="hazard" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出清单
            </el-button>
            <el-input v-model="checklistSearch" placeholder="搜索排查项目" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredChecklist" stripe style="width: 100%">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="item" label="排查项目" min-width="160" />
          <el-table-column prop="content" label="排查内容" min-width="220" show-overflow-tooltip />
          <el-table-column prop="standard" label="排查标准" min-width="220" show-overflow-tooltip />
          <el-table-column label="排查周期" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="cycleTagType(row.cycle)">{{ cycleText(row.cycle) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="department" label="责任部门" width="140" />
          <el-table-column prop="last_check_time" label="最近排查时间" width="160" />
          <el-table-column label="排查结果" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.result === 'normal' ? 'success' : 'danger'">
                {{ row.result === 'normal' ? '正常' : '有隐患' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default>
              <el-button link type="primary">排查</el-button>
              <el-button link type="success">记录</el-button>
              <el-button link type="warning">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'ledger'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              登记隐患
            </el-button>
            <el-select v-model="ledgerLevelFilter" placeholder="隐患等级" clearable style="width: 140px">
              <el-option label="一般隐患" value="general" />
              <el-option label="重大隐患" value="major" />
            </el-select>
            <el-select v-model="ledgerStatusFilter" placeholder="治理状态" clearable style="width: 140px">
              <el-option label="待整改" value="pending" />
              <el-option label="整改中" value="processing" />
              <el-option label="待验收" value="reviewing" />
              <el-option label="已完成" value="completed" />
            </el-select>
            <el-date-picker
              v-model="ledgerDateRange"
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
          </div>
        </div>

        <el-table :data="filteredLedger" stripe style="width: 100%">
          <el-table-column prop="hazard_no" label="隐患编号" width="140" fixed="left" />
          <el-table-column prop="description" label="隐患描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="隐患等级" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.level === 'major' ? 'danger' : 'warning'">
                {{ row.level === 'major' ? '重大隐患' : '一般隐患' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="所在位置" width="160" show-overflow-tooltip />
          <el-table-column prop="find_time" label="发现时间" width="120" />
          <el-table-column prop="department" label="责任部门" width="120" />
          <el-table-column prop="person" label="责任人" width="90" />
          <el-table-column prop="deadline" label="整改期限" width="120" />
          <el-table-column prop="measures" label="整改措施" min-width="180" show-overflow-tooltip />
          <el-table-column prop="complete_time" label="完成时间" width="120" />
          <el-table-column label="验收结果" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.accept_result" size="small" effect="dark" :type="row.accept_result === 'pass' ? 'success' : 'danger'">
                {{ row.accept_result === 'pass' ? '合格' : '不合格' }}
              </el-tag>
              <span v-else class="text-muted">待验收</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
              <el-button link type="success">验收</el-button>
              <el-button link type="warning">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'analysis'" class="tab-content">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">隐患类型分布</div>
              <div class="bar-chart">
                <div v-for="item in hazardTypeStats" :key="item.name" class="bar-item">
                  <div class="bar-label">
                    <span>{{ item.name }}</span>
                    <span class="bar-value">{{ item.count }} 项</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" :style="{ width: item.percent + '%', background: item.color }"></div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :sm="12" :md="8">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">风险等级分布</div>
              <div class="pie-chart-wrapper">
                <div class="donut-chart">
                  <svg viewBox="0 0 100 100" class="donut-svg">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#f1f5f9" stroke-width="12" />
                    <circle
                      cx="50" cy="50" r="40" fill="none" stroke="#dc2626" stroke-width="12"
                      stroke-dasharray="25.12 226.08" stroke-dashoffset="0"
                      transform="rotate(-90 50 50)"
                    />
                    <circle
                      cx="50" cy="50" r="40" fill="none" stroke="#f97316" stroke-width="12"
                      stroke-dasharray="50.24 226.08" stroke-dashoffset="-25.12"
                      transform="rotate(-90 50 50)"
                    />
                    <circle
                      cx="50" cy="50" r="40" fill="none" stroke="#eab308" stroke-width="12"
                      stroke-dasharray="75.36 226.08" stroke-dashoffset="-75.36"
                      transform="rotate(-90 50 50)"
                    />
                    <circle
                      cx="50" cy="50" r="40" fill="none" stroke="#3b82f6" stroke-width="12"
                      stroke-dasharray="75.36 226.08" stroke-dashoffset="-150.72"
                      transform="rotate(-90 50 50)"
                    />
                  </svg>
                  <div class="donut-center">
                    <div class="donut-total">{{ stats.riskPoints }}</div>
                    <div class="donut-label">风险点总数</div>
                  </div>
                </div>
                <div class="pie-legend">
                  <div class="legend-item">
                    <span class="legend-dot" style="background: #dc2626"></span>
                    <span>重大风险</span>
                    <span class="legend-value">10%</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-dot" style="background: #f97316"></span>
                    <span>较大风险</span>
                    <span class="legend-value">20%</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-dot" style="background: #eab308"></span>
                    <span>一般风险</span>
                    <span class="legend-value">30%</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-dot" style="background: #3b82f6"></span>
                    <span>低风险</span>
                    <span class="legend-value">40%</span>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :sm="12" :md="8">
            <el-card class="chart-card" shadow="never">
              <div class="chart-title">隐患来源分布</div>
              <div class="source-chart">
                <div v-for="item in sourceStats" :key="item.name" class="source-item">
                  <div class="source-icon" :style="{ background: item.color }">
                    <el-icon><component :is="item.icon" /></el-icon>
                  </div>
                  <div class="source-info">
                    <div class="source-name">{{ item.name }}</div>
                    <div class="source-count">{{ item.count }} 项</div>
                  </div>
                  <div class="source-percent">{{ item.percent }}%</div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card class="chart-card" shadow="never" style="margin-top: 16px">
          <div class="chart-title">隐患整改趋势（近6个月）</div>
          <div class="line-chart">
            <div class="chart-y-axis">
              <span>50</span>
              <span>40</span>
              <span>30</span>
              <span>20</span>
              <span>10</span>
              <span>0</span>
            </div>
            <div class="chart-content">
              <div class="chart-grid">
                <div v-for="i in 5" :key="i" class="grid-line"></div>
              </div>
              <svg class="line-svg" viewBox="0 0 600 200" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="lineGradient1" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0.3" />
                    <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0" />
                  </linearGradient>
                  <linearGradient id="lineGradient2" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#22c55e;stop-opacity:0.3" />
                    <stop offset="100%" style="stop-color:#22c55e;stop-opacity:0" />
                  </linearGradient>
                </defs>
                <path d="M0,160 L100,120 L200,140 L300,80 L400,100 L500,60 L600,40 L600,200 L0,200 Z" fill="url(#lineGradient1)" />
                <path d="M0,180 L100,160 L200,170 L300,130 L400,140 L500,100 L600,80 L600,200 L0,200 Z" fill="url(#lineGradient2)" />
                <polyline points="0,160 100,120 200,140 300,80 400,100 500,60 600,40" fill="none" stroke="#3b82f6" stroke-width="2" />
                <polyline points="0,180 100,160 200,170 300,130 400,140 500,100 600,80" fill="none" stroke="#22c55e" stroke-width="2" />
                <circle cx="0" cy="160" r="4" fill="#3b82f6" />
                <circle cx="100" cy="120" r="4" fill="#3b82f6" />
                <circle cx="200" cy="140" r="4" fill="#3b82f6" />
                <circle cx="300" cy="80" r="4" fill="#3b82f6" />
                <circle cx="400" cy="100" r="4" fill="#3b82f6" />
                <circle cx="500" cy="60" r="4" fill="#3b82f6" />
                <circle cx="600" cy="40" r="4" fill="#3b82f6" />
                <circle cx="0" cy="180" r="4" fill="#22c55e" />
                <circle cx="100" cy="160" r="4" fill="#22c55e" />
                <circle cx="200" cy="170" r="4" fill="#22c55e" />
                <circle cx="300" cy="130" r="4" fill="#22c55e" />
                <circle cx="400" cy="140" r="4" fill="#22c55e" />
                <circle cx="500" cy="100" r="4" fill="#22c55e" />
                <circle cx="600" cy="80" r="4" fill="#22c55e" />
              </svg>
              <div class="chart-x-axis">
                <span>4月</span>
                <span>5月</span>
                <span>6月</span>
                <span>7月</span>
                <span>8月</span>
                <span>9月</span>
              </div>
            </div>
          </div>
          <div class="chart-legend">
            <div class="legend-item">
              <span class="legend-line" style="background: #3b82f6"></span>
              <span>发现隐患数</span>
            </div>
            <div class="legend-item">
              <span class="legend-line" style="background: #22c55e"></span>
              <span>完成整改数</span>
            </div>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  WarningFilled, InfoFilled, CircleCloseFilled, CircleCheckFilled,
  Histogram, DocumentChecked, Notebook, DataAnalysis,
  Plus, Search, Download, LocationFilled, OfficeBuilding, ChatDotRound
} from '@element-plus/icons-vue'

const activeTab = ref('risk')

const stats = ref({
  riskPoints: 128,
  generalHazards: 23,
  majorHazards: 5,
  completionRate: 87.5,
})

const riskSearch = ref('')
const riskLevelFilter = ref('')
const riskDeptFilter = ref('')

const checklistSearch = ref('')
const checklistCycleFilter = ref('')
const checklistResultFilter = ref('')

const ledgerLevelFilter = ref('')
const ledgerStatusFilter = ref('')
const ledgerDateRange = ref([])

const riskPoints = ref([
  { id: 1, name: '消防水泵房用电安全', level: 'red', area: '地下一层水泵房', measures: '每日巡检、定期检测、双电源供电', department: '设备管理部', person: '张工', status: 'controlled' },
  { id: 2, name: '配电室消防隐患', level: 'red', area: '地下二层配电室', measures: '气体灭火系统、温度监控、专人值守', department: '设备管理部', person: '李工', status: 'controlled' },
  { id: 3, name: '柴油发电机房', level: 'orange', area: '地下一层机房', measures: '通风系统、防火分隔、定期维护', department: '设备管理部', person: '王工', status: 'controlled' },
  { id: 4, name: '厨房燃气管道', level: 'orange', area: '学生食堂一层', measures: '燃气报警、自动切断阀、每日检查', department: '后勤保障部', person: '赵师傅', status: 'attention' },
  { id: 5, name: '化学品储藏室', level: 'orange', area: '实验楼B座一层', measures: '防爆电气、通风系统、双人双锁', department: '安全保卫部', person: '刘主任', status: 'controlled' },
  { id: 6, name: '消防通道堵塞', level: 'yellow', area: '综合办公楼各层', measures: '定期检查、标识明确、及时清理', department: '物业管理部', person: '孙主管', status: 'controlled' },
  { id: 7, name: '应急照明不足', level: 'yellow', area: '地下车库B1层', measures: '增设灯具、定期测试、及时更换', department: '设备管理部', person: '周工', status: 'attention' },
  { id: 8, name: '烟感探测器老化', level: 'yellow', area: '学生宿舍C区', measures: '分批更换、定期检测、加强维护', department: '设备管理部', person: '吴工', status: 'controlled' },
  { id: 9, name: '灭火器过期', level: 'blue', area: '图书馆D馆各层', measures: '按时年检、及时更换、加强巡查', department: '安全保卫部', person: '郑班长', status: 'controlled' },
  { id: 10, name: '疏散标识不清', level: 'blue', area: '实验楼A座', measures: '增设标识、定期检查、及时维护', department: '物业管理部', person: '冯主管', status: 'controlled' },
  { id: 11, name: '防火门闭门器损坏', level: 'blue', area: '综合办公楼3层', measures: '及时维修、定期检查、加强保养', department: '物业管理部', person: '陈师傅', status: 'controlled' },
  { id: 12, name: '室内消火栓压力不足', level: 'yellow', area: '学生宿舍B区', measures: '管网检测、水泵调试、定期测试', department: '设备管理部', person: '褚工', status: 'attention' },
])

const checklist = ref([
  { id: 1, item: '消防供水系统', content: '检查消防水池、水泵、管网及消火栓', standard: '水压正常、水量充足、设备完好', cycle: 'weekly', department: '设备管理部', last_check_time: '2026-09-08 09:30', result: 'normal' },
  { id: 2, item: '火灾自动报警系统', content: '检查探测器、控制器、联动设备', standard: '报警及时、联动正常、设备完好', cycle: 'monthly', department: '设备管理部', last_check_time: '2026-09-05 14:20', result: 'normal' },
  { id: 3, item: '自动喷水灭火系统', content: '检查喷淋头、管网、报警阀组', standard: '压力正常、喷头完好、阀门灵活', cycle: 'monthly', department: '设备管理部', last_check_time: '2026-09-01 10:15', result: 'hazard' },
  { id: 4, item: '消防通道及疏散', content: '检查通道畅通、标识清晰、应急照明', standard: '通道畅通、标识明显、照明正常', cycle: 'daily', department: '物业管理部', last_check_time: '2026-09-09 08:00', result: 'normal' },
  { id: 5, item: '灭火器配置', content: '检查灭火器数量、压力、有效期', standard: '配置齐全、压力正常、在有效期内', cycle: 'monthly', department: '安全保卫部', last_check_time: '2026-09-03 16:45', result: 'hazard' },
  { id: 6, item: '防火门及卷帘', content: '检查防火门、卷帘门及其控制装置', standard: '关闭严密、升降正常、控制有效', cycle: 'quarterly', department: '物业管理部', last_check_time: '2026-08-20 11:30', result: 'normal' },
  { id: 7, item: '燃气安全', content: '检查燃气管道、阀门、报警装置', standard: '无泄漏、阀门正常、报警有效', cycle: 'daily', department: '后勤保障部', last_check_time: '2026-09-09 07:30', result: 'normal' },
  { id: 8, item: '电气安全', content: '检查配电箱、线路、接地装置', standard: '布线规范、无过热、接地良好', cycle: 'monthly', department: '设备管理部', last_check_time: '2026-09-07 15:00', result: 'normal' },
  { id: 9, item: '应急广播系统', content: '检查广播主机、扬声器、联动功能', standard: '声音清晰、覆盖全面、联动正常', cycle: 'quarterly', department: '设备管理部', last_check_time: '2026-08-25 09:00', result: 'hazard' },
  { id: 10, item: '消防电梯', content: '检查消防电梯功能、迫降、通讯', standard: '迫降正常、通讯畅通、功能完好', cycle: 'quarterly', department: '设备管理部', last_check_time: '2026-08-28 14:00', result: 'normal' },
])

const ledger = ref([
  { hazard_no: 'HZ-2026-001', description: '3层走廊烟感探测器误报频繁', level: 'general', location: '综合办公楼A座3层走廊', find_time: '2026-09-02', department: '设备管理部', person: '李工', deadline: '2026-09-12', measures: '更换探测器并清洁线路', complete_time: '2026-09-08', accept_result: 'pass' },
  { hazard_no: 'HZ-2026-002', description: '地下车库B1层应急照明部分失效', level: 'general', location: '地下车库B1层西区', find_time: '2026-09-03', department: '设备管理部', person: '王工', deadline: '2026-09-13', measures: '更换故障应急灯具及蓄电池', complete_time: '', accept_result: '' },
  { hazard_no: 'HZ-2026-003', description: '食堂厨房燃气报警传感器故障', level: 'major', location: '学生食堂一层厨房', find_time: '2026-09-01', department: '后勤保障部', person: '赵师傅', deadline: '2026-09-06', measures: '立即更换传感器并校准系统', complete_time: '2026-09-05', accept_result: 'pass' },
  { hazard_no: 'HZ-2026-004', description: '实验楼化学品储藏室通风不畅', level: 'major', location: '实验楼B座一层储藏室', find_time: '2026-08-28', department: '安全保卫部', person: '刘主任', deadline: '2026-09-08', measures: '增设排风设备，优化通风系统', complete_time: '2026-09-07', accept_result: 'pass' },
  { hazard_no: 'HZ-2026-005', description: '学生宿舍C区5具灭火器过期', level: 'general', location: '学生宿舍C区各层', find_time: '2026-09-04', department: '安全保卫部', person: '郑班长', deadline: '2026-09-14', measures: '统一更换过期灭火器', complete_time: '', accept_result: '' },
  { hazard_no: 'HZ-2026-006', description: '消防水泵接合器锈蚀严重', level: 'general', location: '综合办公楼A座北侧', find_time: '2026-08-30', department: '设备管理部', person: '张工', deadline: '2026-09-15', measures: '除锈刷漆，更换密封件', complete_time: '2026-09-06', accept_result: 'fail' },
  { hazard_no: 'HZ-2026-007', description: '图书馆D馆防火卷帘门无法升降', level: 'major', location: '图书馆D馆一层大厅', find_time: '2026-09-05', department: '物业管理部', person: '孙主管', deadline: '2026-09-10', measures: '检修电机及控制系统', complete_time: '', accept_result: '' },
  { hazard_no: 'HZ-2026-008', description: '办公楼疏散指示标志损坏3处', level: 'general', location: '综合办公楼A座2-4层', find_time: '2026-09-06', department: '物业管理部', person: '冯主管', deadline: '2026-09-16', measures: '更换损坏的疏散指示标志', complete_time: '', accept_result: '' },
])

const hazardTypeStats = ref([
  { name: '消防设施', count: 18, percent: 60, color: '#3b82f6' },
  { name: '电气安全', count: 6, percent: 20, color: '#f97316' },
  { name: '通道疏散', count: 3, percent: 10, color: '#22c55e' },
  { name: '燃气安全', count: 2, percent: 6.7, color: '#eab308' },
  { name: '其他', count: 1, percent: 3.3, color: '#8b5cf6' },
])

const sourceStats = ref([
  { name: '日常巡检', count: 15, percent: 50, color: '#3b82f6', icon: 'Search' },
  { name: '专项检查', count: 8, percent: 26.7, color: '#22c55e', icon: 'DocumentChecked' },
  { name: '系统报警', count: 4, percent: 13.3, color: '#f97316', icon: 'WarningFilled' },
  { name: '上级督查', count: 2, percent: 6.7, color: '#8b5cf6', icon: 'OfficeBuilding' },
  { name: '群众举报', count: 1, percent: 3.3, color: '#eab308', icon: 'ChatDotRound' },
])

const groupedRiskPoints = computed(() => {
  let list = riskPoints.value
  if (riskSearch.value) {
    list = list.filter(p => p.name.includes(riskSearch.value) || p.area.includes(riskSearch.value))
  }
  if (riskLevelFilter.value) {
    list = list.filter(p => p.level === riskLevelFilter.value)
  }
  if (riskDeptFilter.value) {
    list = list.filter(p => p.department === riskDeptFilter.value)
  }
  const groups = { red: [], orange: [], yellow: [], blue: [] }
  list.forEach(p => {
    if (groups[p.level]) groups[p.level].push(p)
  })
  return groups
})

const filteredChecklist = computed(() => {
  let list = checklist.value
  if (checklistSearch.value) {
    list = list.filter(c => c.item.includes(checklistSearch.value) || c.content.includes(checklistSearch.value))
  }
  if (checklistCycleFilter.value) {
    list = list.filter(c => c.cycle === checklistCycleFilter.value)
  }
  if (checklistResultFilter.value) {
    list = list.filter(c => c.result === checklistResultFilter.value)
  }
  return list
})

const filteredLedger = computed(() => {
  let list = ledger.value
  if (ledgerLevelFilter.value) {
    list = list.filter(l => l.level === ledgerLevelFilter.value)
  }
  return list
})

function levelText(level) {
  const map = { red: '重大风险', orange: '较大风险', yellow: '一般风险', blue: '低风险' }
  return map[level] || ''
}

function cycleText(cycle) {
  const map = { daily: '每日', weekly: '每周', monthly: '每月', quarterly: '每季度' }
  return map[cycle] || ''
}

function cycleTagType(cycle) {
  const map = { daily: 'danger', weekly: 'warning', monthly: 'primary', quarterly: 'info' }
  return map[cycle] || ''
}
</script>

<style scoped>
.hazard-page {
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

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.yellow { background: linear-gradient(135deg, #eab308, #ca8a04); }
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }

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
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
}

.risk-group {
  margin-bottom: 24px;
}

.risk-group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.risk-level-badge {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.risk-level-badge.red { background: #dc2626; }
.risk-level-badge.orange { background: #f97316; }
.risk-level-badge.yellow { background: #eab308; }
.risk-level-badge.blue { background: #3b82f6; }

.risk-group-count {
  font-size: 13px;
  color: #64748b;
}

.risk-card {
  margin-bottom: 16px;
  border-left: 4px solid transparent;
}

.risk-card.level-red { border-left-color: #dc2626; }
.risk-card.level-orange { border-left-color: #f97316; }
.risk-card.level-yellow { border-left-color: #eab308; }
.risk-card.level-blue { border-left-color: #3b82f6; }

.risk-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.risk-level-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #fff;
}

.risk-level-tag.red { background: #fef2f2; color: #dc2626; }
.risk-level-tag.orange { background: #fff7ed; color: #f97316; }
.risk-level-tag.yellow { background: #fefce8; color: #ca8a04; }
.risk-level-tag.blue { background: #eff6ff; color: #2563eb; }

.risk-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.risk-area {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
}

.risk-detail {
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.detail-item .label {
  color: #64748b;
}

.detail-item .value {
  color: #0f172a;
  font-weight: 500;
  max-width: 60%;
  text-align: right;
}

.risk-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.text-muted {
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

.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bar-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bar-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #475569;
}

.bar-value {
  font-weight: 600;
  color: #0f172a;
}

.bar-track {
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}

.pie-chart-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.donut-chart {
  position: relative;
  width: 180px;
  height: 180px;
}

.donut-svg {
  width: 100%;
  height: 100%;
}

.donut-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.donut-total {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.donut-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.pie-legend {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-value {
  margin-left: auto;
  font-weight: 600;
  color: #0f172a;
}

.source-chart {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: #f8fafc;
  border-radius: 10px;
}

.source-icon {
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

.source-info {
  flex: 1;
  min-width: 0;
}

.source-name {
  font-size: 14px;
  font-weight: 500;
  color: #0f172a;
  margin-bottom: 2px;
}

.source-count {
  font-size: 12px;
  color: #64748b;
}

.source-percent {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.line-chart {
  display: flex;
  height: 240px;
  gap: 12px;
}

.chart-y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
  width: 30px;
  text-align: right;
  padding: 4px 0;
}

.chart-content {
  flex: 1;
  position: relative;
}

.chart-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.grid-line {
  height: 1px;
  background: #f1f5f9;
}

.line-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: calc(100% - 24px);
}

.chart-x-axis {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 24px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  font-size: 12px;
  color: #64748b;
}

.chart-legend {
  display: flex;
  gap: 24px;
  justify-content: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.chart-legend .legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}

.legend-line {
  width: 20px;
  height: 3px;
  border-radius: 2px;
}
</style>
