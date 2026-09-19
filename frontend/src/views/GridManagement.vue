<template>
  <div class="grid-management-page">
    <div class="title-row">
      <div>
        <div class="page-title">网格化管理</div>
        <p class="subtitle">消防责任区域划分 · 网格员管理 · 隐患上报 · 闭环处置</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Grid /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalGrids }}</div>
            <div class="stat-label">网格总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.gridWorkers }}</div>
            <div class="stat-label">网格员数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.pendingHazards }}</div>
            <div class="stat-label">待处理隐患</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.completedHazards }}</div>
            <div class="stat-label">已完成隐患</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'grids' }" @click="activeTab = 'grids'">
          <el-icon><Grid /></el-icon>
          网格区域
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'workers' }" @click="activeTab = 'workers'">
          <el-icon><UserFilled /></el-icon>
          网格员管理
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'reports' }" @click="activeTab = 'reports'">
          <el-icon><Document /></el-icon>
          隐患上报
          <span v-if="stats.pendingHazards" class="badge">{{ stats.pendingHazards }}</span>
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><List /></el-icon>
          处置记录
        </div>
      </div>

      <div v-if="activeTab === 'grids'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showGridForm = true">
              <el-icon><Plus /></el-icon>
              新增网格
            </el-button>
            <el-select v-model="gridAreaFilter" placeholder="所属区域" clearable style="width: 140px">
              <el-option label="东区" value="east" />
              <el-option label="西区" value="west" />
              <el-option label="南区" value="south" />
              <el-option label="北区" value="north" />
              <el-option label="中心区" value="center" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="gridSearch" placeholder="搜索网格名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="g in filteredGrids" :key="g.id">
            <el-card class="grid-card" shadow="hover">
              <div class="grid-header">
                <div class="grid-icon"><el-icon><Grid /></el-icon></div>
                <div class="grid-title">
                  <div class="grid-name">{{ g.name }}</div>
                  <div class="grid-code">{{ g.code }}</div>
                </div>
                <el-tag size="small" :type="g.area === 'center' ? 'danger' : g.area === 'east' ? 'primary' : g.area === 'west' ? 'success' : g.area === 'south' ? 'warning' : 'info'">
                  {{ g.area_text }}
                </el-tag>
              </div>
              <div class="grid-detail">
                <div class="detail-row">
                  <span class="label">所属区域</span>
                  <span class="value">{{ g.area_text }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">覆盖面积</span>
                  <span class="value">{{ g.area_size }} ㎡</span>
                </div>
                <div class="detail-row">
                  <span class="label">重点部位</span>
                  <span class="value highlight">{{ g.key_points }} 处</span>
                </div>
                <div class="detail-row">
                  <span class="label">网格员</span>
                  <span class="value">{{ g.worker_name }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">隐患数量</span>
                  <span class="value" :class="g.hazard_count > 0 ? 'danger-text' : ''">{{ g.hazard_count }} 个</span>
                </div>
              </div>
              <div class="grid-actions">
                <el-button size="small">查看详情</el-button>
                <el-button size="small" type="primary">隐患列表</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'workers'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showWorkerForm = true">
              <el-icon><Plus /></el-icon>
              添加网格员
            </el-button>
            <el-select v-model="workerStatusFilter" placeholder="在岗状态" clearable style="width: 140px">
              <el-option label="在岗" value="on_duty" />
              <el-option label="休假" value="off_duty" />
              <el-option label="离职" value="resigned" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="workerSearch" placeholder="搜索姓名/网格" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredWorkers" stripe style="width: 100%">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column prop="grid_name" label="负责网格" width="160" />
          <el-table-column prop="phone" label="联系电话" width="140" />
          <el-table-column prop="entry_date" label="入职日期" width="120" />
          <el-table-column prop="responsible_area" label="负责区域" min-width="160" />
          <el-table-column label="在岗状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'on_duty' ? 'success' : row.status === 'off_duty' ? 'warning' : 'info'">
                {{ row.status === 'on_duty' ? '在岗' : row.status === 'off_duty' ? '休假' : '离职' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="handled_hazards" label="处理隐患数" width="110" align="center">
            <template #default="{ row }">
              <span class="highlight-text">{{ row.handled_hazards }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default>
              <el-button link type="primary">查看</el-button>
              <el-button link type="warning">编辑</el-button>
              <el-button link type="danger">停用</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'reports'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="hazardTypeFilter" placeholder="隐患类型" clearable style="width: 140px">
              <el-option label="电气火灾" value="electrical" />
              <el-option label="消防通道" value="passage" />
              <el-option label="消防设施" value="facility" />
              <el-option label="易燃易爆" value="flammable" />
              <el-option label="其他隐患" value="other" />
            </el-select>
            <el-select v-model="hazardLevelFilter" placeholder="隐患等级" clearable style="width: 140px">
              <el-option label="一般隐患" value="normal" />
              <el-option label="较大隐患" value="major" />
              <el-option label="重大隐患" value="critical" />
            </el-select>
            <el-select v-model="hazardStatusFilter" placeholder="处置状态" clearable style="width: 140px">
              <el-option label="待受理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="已整改" value="rectified" />
              <el-option label="已销号" value="closed" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button @click="exportReports">
              <el-icon><Download /></el-icon>
              导出报表
            </el-button>
          </div>
        </div>

        <el-table :data="filteredReports" stripe style="width: 100%">
          <el-table-column prop="report_time" label="上报时间" width="160" />
          <el-table-column prop="grid_name" label="网格" width="140" />
          <el-table-column prop="reporter" label="上报人" width="100" />
          <el-table-column prop="location" label="隐患位置" min-width="180" show-overflow-tooltip />
          <el-table-column label="隐患类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="hazardTypeTag(row.type)">{{ hazardTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="隐患等级" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="hazardLevelTag(row.level)">
                {{ hazardLevelText(row.level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="图片" width="80" align="center">
            <template #default="{ row }">
              <el-image
                v-if="row.image"
                :src="row.image"
                :preview-src-list="[row.image]"
                fit="cover"
                style="width: 50px; height: 50px; border-radius: 6px; cursor: pointer"
              />
              <span v-else class="no-image">-</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="hazardStatusTag(row.status)">
                {{ hazardStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary">详情</el-button>
              <el-button v-if="row.status === 'pending'" link type="success">受理</el-button>
              <el-button v-if="row.status === 'processing'" link type="warning">处置</el-button>
              <el-button v-if="row.status === 'rectified'" link type="primary">销号</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="recordResultFilter" placeholder="整改结果" clearable style="width: 140px">
              <el-option label="整改完成" value="completed" />
              <el-option label="部分整改" value="partial" />
              <el-option label="未整改" value="none" />
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
            <el-button @click="exportRecords">
              <el-icon><Download /></el-icon>
              导出记录
            </el-button>
          </div>
        </div>

        <el-table :data="filteredRecords" stripe style="width: 100%">
          <el-table-column prop="hazard_no" label="隐患编号" width="160" />
          <el-table-column prop="report_time" label="上报时间" width="160" />
          <el-table-column prop="acceptor" label="受理人" width="100" />
          <el-table-column prop="measures" label="处置措施" min-width="200" show-overflow-tooltip />
          <el-table-column prop="deadline" label="整改时限" width="120" />
          <el-table-column label="整改结果" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.result === 'completed' ? 'success' : row.result === 'partial' ? 'warning' : 'danger'">
                {{ row.result === 'completed' ? '整改完成' : row.result === 'partial' ? '部分整改' : '未整改' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="close_time" label="销号时间" width="160" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
              <el-button link type="success">报告</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="showGridForm" title="新增网格" width="600px">
      <el-form :model="gridForm" label-width="100px">
        <el-form-item label="网格名称">
          <el-input v-model="gridForm.name" placeholder="请输入网格名称" />
        </el-form-item>
        <el-form-item label="网格编号">
          <el-input v-model="gridForm.code" placeholder="请输入网格编号" />
        </el-form-item>
        <el-form-item label="所属区域">
          <el-select v-model="gridForm.area" style="width: 100%">
            <el-option label="东区" value="east" />
            <el-option label="西区" value="west" />
            <el-option label="南区" value="south" />
            <el-option label="北区" value="north" />
            <el-option label="中心区" value="center" />
          </el-select>
        </el-form-item>
        <el-form-item label="覆盖面积">
          <el-input v-model="gridForm.area_size" placeholder="请输入覆盖面积（㎡）" />
        </el-form-item>
        <el-form-item label="网格员">
          <el-select v-model="gridForm.worker_id" style="width: 100%">
            <el-option label="张伟" :value="1" />
            <el-option label="李娜" :value="2" />
            <el-option label="王强" :value="3" />
            <el-option label="刘芳" :value="4" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGridForm = false">取消</el-button>
        <el-button type="primary" @click="submitGrid">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Grid, User, UserFilled, Warning, CircleCheck, Document, List, Plus, Search, Download
} from '@element-plus/icons-vue'

const activeTab = ref('grids')
const showGridForm = ref(false)
const showWorkerForm = ref(false)
const gridSearch = ref('')
const gridAreaFilter = ref('')
const workerSearch = ref('')
const workerStatusFilter = ref('')
const hazardTypeFilter = ref('')
const hazardLevelFilter = ref('')
const hazardStatusFilter = ref('')
const recordResultFilter = ref('')
const recordDateRange = ref([])

const stats = ref({
  totalGrids: 36,
  gridWorkers: 48,
  pendingHazards: 12,
  completedHazards: 156,
})

const grids = ref([
  { id: 1, name: '中心广场网格', code: 'GRID-C-001', area: 'center', area_text: '中心区', area_size: 12500, key_points: 8, worker_name: '张伟', hazard_count: 2 },
  { id: 2, name: '东区办公网格', code: 'GRID-E-001', area: 'east', area_text: '东区', area_size: 18000, key_points: 12, worker_name: '李娜', hazard_count: 0 },
  { id: 3, name: '东区宿舍网格', code: 'GRID-E-002', area: 'east', area_text: '东区', area_size: 22000, key_points: 15, worker_name: '王强', hazard_count: 3 },
  { id: 4, name: '西区实验网格', code: 'GRID-W-001', area: 'west', area_text: '西区', area_size: 15600, key_points: 20, worker_name: '刘芳', hazard_count: 1 },
  { id: 5, name: '西区图书馆网格', code: 'GRID-W-002', area: 'west', area_text: '西区', area_size: 9800, key_points: 6, worker_name: '陈明', hazard_count: 0 },
  { id: 6, name: '南区食堂网格', code: 'GRID-S-001', area: 'south', area_text: '南区', area_size: 6500, key_points: 10, worker_name: '赵丽', hazard_count: 4 },
  { id: 7, name: '南区体育网格', code: 'GRID-S-002', area: 'south', area_text: '南区', area_size: 25000, key_points: 5, worker_name: '孙磊', hazard_count: 1 },
  { id: 8, name: '北区车库网格', code: 'GRID-N-001', area: 'north', area_text: '北区', area_size: 14000, key_points: 8, worker_name: '周杰', hazard_count: 2 },
  { id: 9, name: '北区综合楼网格', code: 'GRID-N-002', area: 'north', area_text: '北区', area_size: 16800, key_points: 14, worker_name: '吴敏', hazard_count: 0 },
  { id: 10, name: '中心配电网格', code: 'GRID-C-002', area: 'center', area_text: '中心区', area_size: 3200, key_points: 18, worker_name: '郑涛', hazard_count: 5 },
  { id: 11, name: '东区科研网格', code: 'GRID-E-003', area: 'east', area_text: '东区', area_size: 19500, key_points: 22, worker_name: '冯雪', hazard_count: 3 },
  { id: 12, name: '西区教学网格', code: 'GRID-W-003', area: 'west', area_text: '西区', area_size: 21000, key_points: 16, worker_name: '韩磊', hazard_count: 1 },
])

const workers = ref([
  { id: 1, name: '张伟', grid_name: '中心广场网格', phone: '138****1234', entry_date: '2023-03-15', responsible_area: '中心广场及周边建筑', status: 'on_duty', handled_hazards: 28 },
  { id: 2, name: '李娜', grid_name: '东区办公网格', phone: '139****5678', entry_date: '2022-08-20', responsible_area: '东区办公楼A-F座', status: 'on_duty', handled_hazards: 35 },
  { id: 3, name: '王强', grid_name: '东区宿舍网格', phone: '137****9012', entry_date: '2023-01-10', responsible_area: '东区学生宿舍1-8号楼', status: 'on_duty', handled_hazards: 42 },
  { id: 4, name: '刘芳', grid_name: '西区实验网格', phone: '136****3456', entry_date: '2022-05-18', responsible_area: '西区实验楼A-E座', status: 'off_duty', handled_hazards: 31 },
  { id: 5, name: '陈明', grid_name: '西区图书馆网格', phone: '135****7890', entry_date: '2023-06-22', responsible_area: '图书馆及周边区域', status: 'on_duty', handled_hazards: 18 },
  { id: 6, name: '赵丽', grid_name: '南区食堂网格', phone: '138****2345', entry_date: '2022-11-08', responsible_area: '学生食堂及商业街', status: 'on_duty', handled_hazards: 52 },
  { id: 7, name: '孙磊', grid_name: '南区体育网格', phone: '139****6789', entry_date: '2023-04-30', responsible_area: '体育馆及运动场', status: 'on_duty', handled_hazards: 15 },
  { id: 8, name: '周杰', grid_name: '北区车库网格', phone: '137****0123', entry_date: '2022-09-12', responsible_area: '北区地下车库及人防', status: 'on_duty', handled_hazards: 27 },
  { id: 9, name: '吴敏', grid_name: '北区综合楼网格', phone: '136****4567', entry_date: '2023-02-28', responsible_area: '北区综合楼及会议室', status: 'resigned', handled_hazards: 22 },
  { id: 10, name: '郑涛', grid_name: '中心配电网格', phone: '135****8901', entry_date: '2022-07-05', responsible_area: '中心配电房及设备间', status: 'on_duty', handled_hazards: 63 },
])

const reports = ref([
  { id: 1, report_time: '2026-09-08 14:30:25', grid_name: '南区食堂网格', reporter: '赵丽', location: '学生食堂一楼后厨', type: 'electrical', level: 'major', image: '', status: 'pending' },
  { id: 2, report_time: '2026-09-08 10:15:42', grid_name: '东区宿舍网格', reporter: '王强', location: '3号楼3层走廊', type: 'passage', level: 'normal', image: '', status: 'processing' },
  { id: 3, report_time: '2026-09-07 16:45:10', grid_name: '中心配电网格', reporter: '郑涛', location: '中心配电房B区', type: 'facility', level: 'critical', image: '', status: 'processing' },
  { id: 4, report_time: '2026-09-07 09:20:33', grid_name: '西区实验网格', reporter: '刘芳', location: '实验楼C座502室', type: 'flammable', level: 'major', image: '', status: 'rectified' },
  { id: 5, report_time: '2026-09-06 15:08:55', grid_name: '中心广场网格', reporter: '张伟', location: '中心广场地下通道', type: 'facility', level: 'normal', image: '', status: 'closed' },
  { id: 6, report_time: '2026-09-06 11:30:18', grid_name: '北区车库网格', reporter: '周杰', location: '地下车库B2层东区', type: 'electrical', level: 'normal', image: '', status: 'closed' },
  { id: 7, report_time: '2026-09-05 13:55:40', grid_name: '东区办公网格', reporter: '李娜', location: '办公楼B座12层', type: 'passage', level: 'normal', image: '', status: 'closed' },
  { id: 8, report_time: '2026-09-05 08:42:27', grid_name: '南区食堂网格', reporter: '赵丽', location: '食堂二楼操作间', type: 'flammable', level: 'critical', image: '', status: 'pending' },
  { id: 9, report_time: '2026-09-04 17:20:15', grid_name: '东区宿舍网格', reporter: '王强', location: '5号楼地下室', type: 'other', level: 'major', image: '', status: 'processing' },
  { id: 10, report_time: '2026-09-04 10:05:50', grid_name: '西区实验网格', reporter: '刘芳', location: '实验楼A座301室', type: 'facility', level: 'normal', image: '', status: 'closed' },
  { id: 11, report_time: '2026-09-03 14:48:33', grid_name: '南区体育网格', reporter: '孙磊', location: '体育馆器材室', type: 'other', level: 'normal', image: '', status: 'closed' },
  { id: 12, report_time: '2026-09-03 09:30:08', grid_name: '中心配电网格', reporter: '郑涛', location: '配电房C区配电柜', type: 'electrical', level: 'critical', image: '', status: 'rectified' },
])

const records = ref([
  { id: 1, hazard_no: 'HZ-20260906-001', report_time: '2026-09-06 15:08:55', acceptor: '李主任', measures: '更换损坏的应急照明灯，疏通安全出口', deadline: '2026-09-08', result: 'completed', close_time: '2026-09-08 10:30:00' },
  { id: 2, hazard_no: 'HZ-20260906-002', report_time: '2026-09-06 11:30:18', acceptor: '王队长', measures: '修复故障烟感探测器，检查线路', deadline: '2026-09-07', result: 'completed', close_time: '2026-09-07 16:45:00' },
  { id: 3, hazard_no: 'HZ-20260905-001', report_time: '2026-09-05 13:55:40', acceptor: '张工', measures: '清理消防通道杂物，设置警示标识', deadline: '2026-09-06', result: 'completed', close_time: '2026-09-06 09:20:00' },
  { id: 4, hazard_no: 'HZ-20260904-001', report_time: '2026-09-04 10:05:50', acceptor: '刘工', measures: '维修消火栓，更换水带', deadline: '2026-09-06', result: 'completed', close_time: '2026-09-05 14:10:00' },
  { id: 5, hazard_no: 'HZ-20260903-001', report_time: '2026-09-03 14:48:33', acceptor: '陈经理', measures: '整理器材室，增设灭火器', deadline: '2026-09-05', result: 'completed', close_time: '2026-09-04 11:30:00' },
  { id: 6, hazard_no: 'HZ-20260902-001', report_time: '2026-09-02 08:30:15', acceptor: '李主任', measures: '整改电气线路，更换老化线缆', deadline: '2026-09-05', result: 'partial', close_time: '-' },
  { id: 7, hazard_no: 'HZ-20260901-001', report_time: '2026-09-01 16:20:45', acceptor: '王队长', measures: '拆除违规搭建物，疏通消防通道', deadline: '2026-09-03', result: 'completed', close_time: '2026-09-03 17:00:00' },
  { id: 8, hazard_no: 'HZ-20260831-001', report_time: '2026-08-31 10:45:30', acceptor: '张工', measures: '更换消防泵密封件，测试水压', deadline: '2026-09-02', result: 'completed', close_time: '2026-09-02 15:30:00' },
])

const gridForm = ref({
  name: '',
  code: '',
  area: 'east',
  area_size: '',
  worker_id: 1,
})

const filteredGrids = computed(() => {
  let list = grids.value
  if (gridSearch.value) {
    list = list.filter(g => g.name.includes(gridSearch.value) || g.code.includes(gridSearch.value))
  }
  if (gridAreaFilter.value) {
    list = list.filter(g => g.area === gridAreaFilter.value)
  }
  return list
})

const filteredWorkers = computed(() => {
  let list = workers.value
  if (workerSearch.value) {
    list = list.filter(w => w.name.includes(workerSearch.value) || w.grid_name.includes(workerSearch.value))
  }
  if (workerStatusFilter.value) {
    list = list.filter(w => w.status === workerStatusFilter.value)
  }
  return list
})

const filteredReports = computed(() => {
  let list = reports.value
  if (hazardTypeFilter.value) {
    list = list.filter(r => r.type === hazardTypeFilter.value)
  }
  if (hazardLevelFilter.value) {
    list = list.filter(r => r.level === hazardLevelFilter.value)
  }
  if (hazardStatusFilter.value) {
    list = list.filter(r => r.status === hazardStatusFilter.value)
  }
  return list
})

const filteredRecords = computed(() => {
  let list = records.value
  if (recordResultFilter.value) {
    list = list.filter(r => r.result === recordResultFilter.value)
  }
  return list
})

function hazardTypeText(type) {
  const map = { electrical: '电气火灾', passage: '消防通道', facility: '消防设施', flammable: '易燃易爆', other: '其他隐患' }
  return map[type] || '其他隐患'
}

function hazardTypeTag(type) {
  const map = { electrical: 'danger', passage: 'warning', facility: 'primary', flammable: 'danger', other: 'info' }
  return map[type] || 'info'
}

function hazardLevelText(level) {
  const map = { normal: '一般隐患', major: '较大隐患', critical: '重大隐患' }
  return map[level] || '一般隐患'
}

function hazardLevelTag(level) {
  const map = { normal: 'success', major: 'warning', critical: 'danger' }
  return map[level] || 'success'
}

function hazardStatusText(status) {
  const map = { pending: '待受理', processing: '处理中', rectified: '已整改', closed: '已销号' }
  return map[status] || '待受理'
}

function hazardStatusTag(status) {
  const map = { pending: 'warning', processing: 'primary', rectified: 'success', closed: 'info' }
  return map[status] || 'warning'
}

function submitGrid() {
  ElMessage.success('网格创建成功')
  showGridForm.value = false
}

function exportReports() {
  ElMessage.success('正在导出隐患报表...')
}

function exportRecords() {
  ElMessage.success('正在导出处置记录...')
}
</script>

<style scoped>
.grid-management-page {
  color: #0f172a;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
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

.highlight-text {
  color: #2563eb;
  font-weight: 600;
}

.grid-card {
  margin-bottom: 16px;
}

.grid-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.grid-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.grid-title {
  flex: 1;
  min-width: 0;
}

.grid-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 2px;
}

.grid-code {
  font-size: 12px;
  color: #64748b;
}

.grid-detail {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 14px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.detail-row .label {
  color: #64748b;
}

.detail-row .value {
  color: #0f172a;
  font-weight: 500;
}

.detail-row .value.highlight {
  color: #2563eb;
}

.grid-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.no-image {
  color: #cbd5e1;
  font-size: 18px;
}
</style>
