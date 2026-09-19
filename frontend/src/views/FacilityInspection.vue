<template>
  <div class="facility-inspection-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防设施检测管理</div>
        <p class="subtitle">检测计划 · 检测记录 · 检测机构 · 复检管理 · 全流程设施检测监管</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.planCount }}</div>
            <div class="stat-label">检测计划数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheckFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.completedCount }}</div>
            <div class="stat-label">已完成检测</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><RefreshRight /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.recheckCount }}</div>
            <div class="stat-label">待复检</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><Medal /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.passRate }}<span class="unit">%</span></div>
            <div class="stat-label">合格率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'plans' }" @click="activeTab = 'plans'">
          <el-icon><Calendar /></el-icon>
          检测计划
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><Notebook /></el-icon>
          检测记录
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'agencies' }" @click="activeTab = 'agencies'">
          <el-icon><OfficeBuilding /></el-icon>
          检测机构
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'recheck' }" @click="activeTab = 'recheck'">
          <el-icon><RefreshRight /></el-icon>
          复检管理
          <span v-if="pendingRecheckCount" class="badge">{{ pendingRecheckCount }}</span>
        </div>
      </div>

      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showPlanDialog = true">
              <el-icon><Plus /></el-icon>
              新增计划
            </el-button>
            <el-select v-model="planTypeFilter" placeholder="检测类型" clearable style="width: 160px">
              <el-option label="年度检测" value="yearly" />
              <el-option label="季度检测" value="quarterly" />
              <el-option label="月度检测" value="monthly" />
              <el-option label="专项检测" value="special" />
            </el-select>
            <el-select v-model="planStatusFilter" placeholder="计划状态" clearable style="width: 140px">
              <el-option label="待执行" value="pending" />
              <el-option label="进行中" value="ongoing" />
              <el-option label="已完成" value="completed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出计划
            </el-button>
            <el-input v-model="planSearch" placeholder="搜索计划名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredPlans" stripe style="width: 100%">
          <el-table-column prop="plan_no" label="计划编号" width="160" fixed="left" />
          <el-table-column prop="plan_name" label="计划名称" min-width="200" />
          <el-table-column label="检测类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="planTypeTag(row.type)">{{ planTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="facility_type" label="设施类型" width="140" />
          <el-table-column prop="agency" label="检测机构" width="160" />
          <el-table-column prop="start_date" label="开始日期" width="120" />
          <el-table-column prop="end_date" label="结束日期" width="120" />
          <el-table-column prop="inspector" label="负责人" width="100" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="planStatusTag(row.status)">
                {{ planStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default>
              <el-button link type="primary">查看</el-button>
              <el-button link type="warning">编辑</el-button>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="inspectionPlans.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="recordResultFilter" placeholder="检测结果" clearable style="width: 140px">
              <el-option label="合格" value="pass" />
              <el-option label="不合格" value="fail" />
              <el-option label="待复检" value="recheck" />
            </el-select>
            <el-select v-model="recordFacilityFilter" placeholder="设施类型" clearable style="width: 160px">
              <el-option label="火灾自动报警系统" value="alarm" />
              <el-option label="自动喷水灭火系统" value="sprinkler" />
              <el-option label="消火栓系统" value="hydrant" />
              <el-option label="防排烟系统" value="smoke" />
              <el-option label="气体灭火系统" value="gas" />
              <el-option label="应急照明系统" value="lighting" />
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
            <el-button>
              <el-icon><Download /></el-icon>
              导出记录
            </el-button>
          </div>
        </div>

        <el-table :data="filteredRecords" stripe style="width: 100%">
          <el-table-column prop="record_no" label="记录编号" width="160" fixed="left" />
          <el-table-column prop="facility_name" label="设施名称" min-width="180" />
          <el-table-column prop="facility_type" label="设施类型" width="140" />
          <el-table-column prop="location" label="所在位置" min-width="160" show-overflow-tooltip />
          <el-table-column prop="inspect_date" label="检测日期" width="120" />
          <el-table-column prop="agency" label="检测机构" width="160" />
          <el-table-column prop="inspector" label="检测人员" width="100" />
          <el-table-column label="检测结果" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="resultTagType(row.result)">
                {{ resultText(row.result) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="report_no" label="报告编号" width="160" />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
              <el-button link type="success">下载报告</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="inspectionRecords.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'agencies'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              新增机构
            </el-button>
            <el-select v-model="agencyQualificationFilter" placeholder="资质等级" clearable style="width: 140px">
              <el-option label="一级资质" value="level1" />
              <el-option label="二级资质" value="level2" />
              <el-option label="三级资质" value="level3" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="agencySearch" placeholder="搜索机构名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col v-for="agency in filteredAgencies" :key="agency.id" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="agency-card" shadow="hover">
              <div class="agency-header">
                <div class="agency-logo" :class="'level-' + agency.qualification_level">
                  <el-icon><OfficeBuilding /></el-icon>
                </div>
                <div class="agency-badge" :class="'level-' + agency.qualification_level">
                  {{ qualificationText(agency.qualification_level) }}
                </div>
              </div>
              <div class="agency-name">{{ agency.name }}</div>
              <div class="agency-qualification-no">资质证书：{{ agency.qualification_no }}</div>
              <div class="agency-info-list">
                <div class="info-item">
                  <span class="info-label">
                    <el-icon><User /></el-icon>
                    联系人
                  </span>
                  <span class="info-value">{{ agency.contact_person }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">
                    <el-icon><Phone /></el-icon>
                    联系电话
                  </span>
                  <span class="info-value">{{ agency.contact_phone }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">
                    <el-icon><LocationFilled /></el-icon>
                    地址
                  </span>
                  <span class="info-value">{{ agency.address }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">
                    <el-icon><Clock /></el-icon>
                    资质有效期
                  </span>
                  <span class="info-value" :class="{ expired: agency.is_expiring }">
                    {{ agency.valid_until }}
                  </span>
                </div>
              </div>
              <div class="agency-stats">
                <div class="stat-item">
                  <div class="stat-num">{{ agency.done_count }}</div>
                  <div class="stat-label">已完成检测</div>
                </div>
                <div class="stat-item">
                  <div class="stat-num">{{ agency.pass_rate }}%</div>
                  <div class="stat-label">合格率</div>
                </div>
                <div class="stat-item">
                  <div class="stat-num">{{ agency.rating }}</div>
                  <div class="stat-label">评分</div>
                </div>
              </div>
              <div class="agency-actions">
                <el-button size="small" type="primary" link>查看详情</el-button>
                <el-button size="small" type="warning" link>编辑</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'recheck'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="recheckStatusFilter" placeholder="复检状态" clearable style="width: 140px">
              <el-option label="待申请" value="pending" />
              <el-option label="已申请" value="applied" />
              <el-option label="复检中" value="ongoing" />
              <el-option label="已完成" value="completed" />
            </el-select>
            <el-select v-model="recheckFacilityFilter" placeholder="设施类型" clearable style="width: 160px">
              <el-option label="火灾自动报警系统" value="alarm" />
              <el-option label="自动喷水灭火系统" value="sprinkler" />
              <el-option label="消火栓系统" value="hydrant" />
              <el-option label="防排烟系统" value="smoke" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出清单
            </el-button>
          </div>
        </div>

        <el-table :data="filteredRecheck" stripe style="width: 100%">
          <el-table-column prop="recheck_no" label="复检编号" width="160" fixed="left" />
          <el-table-column prop="original_record_no" label="原检测编号" width="160" />
          <el-table-column prop="facility_name" label="设施名称" min-width="180" />
          <el-table-column prop="location" label="所在位置" min-width="160" show-overflow-tooltip />
          <el-table-column prop="problem_desc" label="不合格项" min-width="200" show-overflow-tooltip />
          <el-table-column prop="apply_date" label="申请日期" width="120" />
          <el-table-column prop="deadline" label="复检期限" width="120" />
          <el-table-column prop="applicant" label="申请人" width="100" />
          <el-table-column label="复检状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="recheckStatusTag(row.status)">
                {{ recheckStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary">详情</el-button>
              <el-button v-if="row.status === 'pending'" link type="success">申请复检</el-button>
              <el-button v-if="row.status === 'completed'" link type="success">查看报告</el-button>
              <el-button link type="warning">记录</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="recheckList.length"
            :page-size="10"
            background
          />
        </div>
      </div>
    </el-card>

    <el-dialog v-model="showPlanDialog" title="新增检测计划" width="600px">
      <el-form :model="planForm" label-width="100px">
        <el-form-item label="计划名称">
          <el-input v-model="planForm.plan_name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="检测类型">
          <el-select v-model="planForm.type" placeholder="请选择检测类型" style="width: 100%">
            <el-option label="年度检测" value="yearly" />
            <el-option label="季度检测" value="quarterly" />
            <el-option label="月度检测" value="monthly" />
            <el-option label="专项检测" value="special" />
          </el-select>
        </el-form-item>
        <el-form-item label="设施类型">
          <el-select v-model="planForm.facility_type" placeholder="请选择设施类型" style="width: 100%">
            <el-option label="火灾自动报警系统" value="alarm" />
            <el-option label="自动喷水灭火系统" value="sprinkler" />
            <el-option label="消火栓系统" value="hydrant" />
            <el-option label="防排烟系统" value="smoke" />
            <el-option label="气体灭火系统" value="gas" />
            <el-option label="应急照明系统" value="lighting" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测机构">
          <el-select v-model="planForm.agency" placeholder="请选择检测机构" style="width: 100%">
            <el-option v-for="a in agencies" :key="a.id" :label="a.name" :value="a.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测周期">
          <el-date-picker
            v-model="planForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="planForm.inspector" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="planForm.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPlanDialog = false">取消</el-button>
        <el-button type="primary" @click="submitPlan">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document, CircleCheckFilled, RefreshRight, Medal,
  Calendar, Notebook, OfficeBuilding, Plus, Search, Download,
  User, Phone, LocationFilled, Clock
} from '@element-plus/icons-vue'

const activeTab = ref('plans')

const stats = ref({
  planCount: 56,
  completedCount: 42,
  recheckCount: 8,
  passRate: 92.5,
})

const planTypeFilter = ref('')
const planStatusFilter = ref('')
const planSearch = ref('')

const recordResultFilter = ref('')
const recordFacilityFilter = ref('')
const recordDateRange = ref([])

const agencyQualificationFilter = ref('')
const agencySearch = ref('')

const recheckStatusFilter = ref('')
const recheckFacilityFilter = ref('')

const showPlanDialog = ref(false)
const planForm = ref({
  plan_name: '',
  type: '',
  facility_type: '',
  agency: '',
  dateRange: [],
  inspector: '',
  remark: '',
})

const inspectionPlans = ref([
  { id: 1, plan_no: 'JCJH-2026-001', plan_name: '2026年度消防设施全面检测', type: 'yearly', facility_type: '全部系统', agency: '安盾消防检测有限公司', start_date: '2026-03-01', end_date: '2026-03-15', inspector: '张工', status: 'completed' },
  { id: 2, plan_no: 'JCJH-2026-002', plan_name: 'Q1火灾自动报警系统检测', type: 'quarterly', facility_type: '火灾自动报警系统', agency: '安盾消防检测有限公司', start_date: '2026-01-10', end_date: '2026-01-20', inspector: '李工', status: 'completed' },
  { id: 3, plan_no: 'JCJH-2026-003', plan_name: 'Q2自动喷水灭火系统检测', type: 'quarterly', facility_type: '自动喷水灭火系统', agency: '华安消防技术服务公司', start_date: '2026-04-05', end_date: '2026-04-15', inspector: '王工', status: 'pending' },
  { id: 4, plan_no: 'JCJH-2026-004', plan_name: '9月消火栓系统月度检测', type: 'monthly', facility_type: '消火栓系统', agency: '消防设施检测中心', start_date: '2026-09-15', end_date: '2026-09-18', inspector: '赵工', status: 'ongoing' },
  { id: 5, plan_no: 'JCJH-2026-005', plan_name: '配电室气体灭火系统专项检测', type: 'special', facility_type: '气体灭火系统', agency: '安盾消防检测有限公司', start_date: '2026-09-20', end_date: '2026-09-22', inspector: '孙工', status: 'pending' },
  { id: 6, plan_no: 'JCJH-2026-006', plan_name: 'Q3防排烟系统检测', type: 'quarterly', facility_type: '防排烟系统', agency: '华安消防技术服务公司', start_date: '2026-07-10', end_date: '2026-07-20', inspector: '周工', status: 'completed' },
  { id: 7, plan_no: 'JCJH-2026-007', plan_name: '应急照明及疏散指示专项检测', type: 'special', facility_type: '应急照明系统', agency: '消防设施检测中心', start_date: '2026-08-15', end_date: '2026-08-20', inspector: '吴工', status: 'completed' },
  { id: 8, plan_no: 'JCJH-2026-008', plan_name: '10月消防设施月度巡检', type: 'monthly', facility_type: '全部系统', agency: '安盾消防检测有限公司', start_date: '2026-10-10', end_date: '2026-10-12', inspector: '郑工', status: 'cancelled' },
])

const inspectionRecords = ref([
  { id: 1, record_no: 'JCJL-2026-001', facility_name: '火灾自动报警系统（主控制器）', facility_type: '火灾自动报警系统', location: '消防控制室', inspect_date: '2026-09-08', agency: '安盾消防检测有限公司', inspector: '张检测员', result: 'pass', report_no: 'BG-2026-001' },
  { id: 2, record_no: 'JCJL-2026-002', facility_name: '自动喷水灭火系统（湿式报警阀）', facility_type: '自动喷水灭火系统', location: '地下一层水泵房', inspect_date: '2026-09-06', agency: '华安消防技术服务公司', inspector: '李检测员', result: 'pass', report_no: 'BG-2026-002' },
  { id: 3, record_no: 'JCJL-2026-003', facility_name: '室内消火栓系统', facility_type: '消火栓系统', location: '综合办公楼各层', inspect_date: '2026-09-05', agency: '消防设施检测中心', inspector: '王检测员', result: 'recheck', report_no: 'BG-2026-003' },
  { id: 4, record_no: 'JCJL-2026-004', facility_name: '机械排烟系统', facility_type: '防排烟系统', location: '地下车库', inspect_date: '2026-09-04', agency: '安盾消防检测有限公司', inspector: '赵检测员', result: 'pass', report_no: 'BG-2026-004' },
  { id: 5, record_no: 'JCJL-2026-005', facility_name: '七氟丙烷气体灭火系统', facility_type: '气体灭火系统', location: '地下二层配电室', inspect_date: '2026-09-03', agency: '华安消防技术服务公司', inspector: '孙检测员', result: 'fail', report_no: 'BG-2026-005' },
  { id: 6, record_no: 'JCJL-2026-006', facility_name: '应急照明集中电源', facility_type: '应急照明系统', location: '各楼层弱电井', inspect_date: '2026-09-02', agency: '消防设施检测中心', inspector: '周检测员', result: 'pass', report_no: 'BG-2026-006' },
  { id: 7, record_no: 'JCJL-2026-007', facility_name: '防火卷帘门系统', facility_type: '防火分隔设施', location: '各层防火分区', inspect_date: '2026-09-01', agency: '安盾消防检测有限公司', inspector: '吴检测员', result: 'recheck', report_no: 'BG-2026-007' },
  { id: 8, record_no: 'JCJL-2026-008', facility_name: '消防水泵接合器', facility_type: '消火栓系统', location: '建筑北侧室外', inspect_date: '2026-08-30', agency: '华安消防技术服务公司', inspector: '郑检测员', result: 'pass', report_no: 'BG-2026-008' },
])

const agencies = ref([
  { id: 1, name: '安盾消防检测有限公司', qualification_level: 'level1', qualification_no: 'XFJC-2025-001', contact_person: '张经理', contact_phone: '138****1234', address: '北京市朝阳区消防路88号', valid_until: '2027-06-30', is_expiring: false, done_count: 128, pass_rate: 96, rating: 4.8 },
  { id: 2, name: '华安消防技术服务公司', qualification_level: 'level1', qualification_no: 'XFJC-2025-002', contact_person: '李经理', contact_phone: '139****5678', address: '上海市浦东新区安全大厦15层', valid_until: '2026-12-15', is_expiring: true, done_count: 95, pass_rate: 93, rating: 4.6 },
  { id: 3, name: '消防设施检测中心', qualification_level: 'level2', qualification_no: 'XFJC-2025-003', contact_person: '王主任', contact_phone: '137****9012', address: '广州市天河区检测园区', valid_until: '2027-03-20', is_expiring: false, done_count: 76, pass_rate: 91, rating: 4.5 },
  { id: 4, name: '永安消防工程检测公司', qualification_level: 'level2', qualification_no: 'XFJC-2025-004', contact_person: '赵经理', contact_phone: '136****3456', address: '深圳市南山区科技园', valid_until: '2026-10-08', is_expiring: true, done_count: 58, pass_rate: 89, rating: 4.3 },
  { id: 5, name: '中安消防技术检测公司', qualification_level: 'level3', qualification_no: 'XFJC-2025-005', contact_person: '孙工', contact_phone: '135****7890', address: '杭州市西湖区文三路', valid_until: '2027-08-12', is_expiring: false, done_count: 42, pass_rate: 87, rating: 4.2 },
  { id: 6, name: '众安消防检测服务部', qualification_level: 'level3', qualification_no: 'XFJC-2025-006', contact_person: '周工', contact_phone: '134****2345', address: '成都市武侯区', valid_until: '2027-01-18', is_expiring: false, done_count: 35, pass_rate: 85, rating: 4.0 },
])

const recheckList = ref([
  { id: 1, recheck_no: 'FJ-2026-001', original_record_no: 'JCJL-2026-003', facility_name: '室内消火栓系统', location: '综合办公楼3层', problem_desc: '3层西侧2个消火栓压力不足，出水压力低于0.15MPa', apply_date: '2026-09-06', deadline: '2026-09-16', applicant: '王主管', status: 'ongoing' },
  { id: 2, recheck_no: 'FJ-2026-002', original_record_no: 'JCJL-2026-005', facility_name: '七氟丙烷气体灭火系统', location: '地下二层配电室', problem_desc: '气瓶压力低于设计值，需重新充装', apply_date: '2026-09-04', deadline: '2026-09-14', applicant: '李工', status: 'applied' },
  { id: 3, recheck_no: 'FJ-2026-003', original_record_no: 'JCJL-2026-007', facility_name: '防火卷帘门系统', location: '一层大厅东侧', problem_desc: '东侧防火卷帘门下降速度过快，运行不平稳', apply_date: '', deadline: '2026-09-12', applicant: '', status: 'pending' },
  { id: 4, recheck_no: 'FJ-2026-004', original_record_no: 'JCJL-2026-009', facility_name: '应急照明疏散指示', location: '地下车库B2层', problem_desc: 'B2层西区3盏应急照明灯不亮', apply_date: '2026-08-28', deadline: '2026-09-08', applicant: '赵工', status: 'completed' },
  { id: 5, recheck_no: 'FJ-2026-005', original_record_no: 'JCJL-2026-010', facility_name: '机械加压送风系统', location: '楼梯间前室', problem_desc: '2号楼楼梯间前室正压值不足', apply_date: '', deadline: '2026-09-20', applicant: '', status: 'pending' },
  { id: 6, recheck_no: 'FJ-2026-006', original_record_no: 'JCJL-2026-012', facility_name: '消防电梯', location: '1号楼消防电梯', problem_desc: '消防电梯迫降功能测试异常', apply_date: '2026-09-01', deadline: '2026-09-11', applicant: '孙工', status: 'completed' },
])

const pendingRecheckCount = computed(() => {
  return recheckList.value.filter(r => r.status === 'pending' || r.status === 'applied' || r.status === 'ongoing').length
})

const filteredPlans = computed(() => {
  let list = inspectionPlans.value
  if (planTypeFilter.value) list = list.filter(p => p.type === planTypeFilter.value)
  if (planStatusFilter.value) list = list.filter(p => p.status === planStatusFilter.value)
  if (planSearch.value) list = list.filter(p => p.plan_name.includes(planSearch.value) || p.plan_no.includes(planSearch.value))
  return list
})

const filteredRecords = computed(() => {
  let list = inspectionRecords.value
  if (recordResultFilter.value) list = list.filter(r => r.result === recordResultFilter.value)
  if (recordFacilityFilter.value) list = list.filter(r => r.facility_type === recordFacilityFilter.value)
  return list
})

const filteredAgencies = computed(() => {
  let list = agencies.value
  if (agencyQualificationFilter.value) list = list.filter(a => a.qualification_level === agencyQualificationFilter.value)
  if (agencySearch.value) list = list.filter(a => a.name.includes(agencySearch.value))
  return list
})

const filteredRecheck = computed(() => {
  let list = recheckList.value
  if (recheckStatusFilter.value) list = list.filter(r => r.status === recheckStatusFilter.value)
  if (recheckFacilityFilter.value) list = list.filter(r => r.facility_name.includes(recheckFacilityFilter.value))
  return list
})

function planTypeText(type) {
  const map = { yearly: '年度检测', quarterly: '季度检测', monthly: '月度检测', special: '专项检测' }
  return map[type] || type
}

function planTypeTag(type) {
  const map = { yearly: 'danger', quarterly: 'primary', monthly: 'success', special: 'warning' }
  return map[type] || ''
}

function planStatusText(status) {
  const map = { pending: '待执行', ongoing: '进行中', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}

function planStatusTag(status) {
  const map = { pending: 'info', ongoing: 'warning', completed: 'success', cancelled: 'info' }
  return map[status] || ''
}

function resultText(result) {
  const map = { pass: '合格', fail: '不合格', recheck: '待复检' }
  return map[result] || result
}

function resultTagType(result) {
  const map = { pass: 'success', fail: 'danger', recheck: 'warning' }
  return map[result] || ''
}

function qualificationText(level) {
  const map = { level1: '一级资质', level2: '二级资质', level3: '三级资质' }
  return map[level] || level
}

function recheckStatusText(status) {
  const map = { pending: '待申请', applied: '已申请', ongoing: '复检中', completed: '已完成' }
  return map[status] || status
}

function recheckStatusTag(status) {
  const map = { pending: 'info', applied: 'warning', ongoing: 'primary', completed: 'success' }
  return map[status] || ''
}

function submitPlan() {
  ElMessage.success('检测计划创建成功')
  showPlanDialog.value = false
}
</script>

<style scoped>
.facility-inspection-page {
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

.agency-card {
  margin-bottom: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.agency-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.agency-logo {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
}

.agency-logo.level-level1 { background: linear-gradient(135deg, #ef4444, #dc2626); }
.agency-logo.level-level2 { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.agency-logo.level-level3 { background: linear-gradient(135deg, #22c55e, #16a34a); }

.agency-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.agency-badge.level-level1 { background: #fef2f2; color: #dc2626; }
.agency-badge.level-level2 { background: #eff6ff; color: #2563eb; }
.agency-badge.level-level3 { background: #f0fdf4; color: #16a34a; }

.agency-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
}

.agency-qualification-no {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.agency-info-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  gap: 8px;
}

.info-label {
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.info-value {
  color: #0f172a;
  font-weight: 500;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-value.expired {
  color: #ef4444;
}

.agency-stats {
  display: flex;
  justify-content: space-around;
  padding: 12px 0;
  border-top: 1px solid #f1f5f9;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 12px;
}

.stat-item {
  text-align: center;
}

.stat-item .stat-num {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 2px;
}

.stat-item .stat-label {
  font-size: 11px;
  color: #64748b;
}

.agency-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
