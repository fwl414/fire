<template>
  <div class="duty-room-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防控制室</div>
        <p class="subtitle">值班管理 · 交接班记录 · 值班日志 · 符合GB25201建筑消防设施维护管理标准</p>
      </div>
      <div class="title-actions">
        <el-tag v-if="currentShift" type="success" effect="dark" size="large">
          <el-icon><Sunrise /></el-icon>
          值班中 · {{ currentShift.shift_name }}
        </el-tag>
        <el-tag v-else type="info" effect="dark" size="large">未安排值班</el-tag>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.onDuty }}</div>
            <div class="stat-label">当前值班</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.monthlyRecords }}</div>
            <div class="stat-label">本月值班记录</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.alarmCount }}</div>
            <div class="stat-label">本期接警数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.handledAlarms }}</div>
            <div class="stat-label">已处理告警</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="duty-info-row">
      <el-col :lg="16" :md="24">
        <el-card class="module-card" shadow="never">
          <div class="card-header">
            <div class="card-title">当前值班信息</div>
            <div class="card-subtitle">{{ todayStr }}</div>
          </div>
          <div v-if="currentShift" class="shift-info">
            <div class="shift-main">
              <div class="shift-badge">
                <span class="shift-name">{{ currentShift.shift_name }}</span>
                <span class="shift-time">{{ currentShift.start_time }} - {{ currentShift.end_time }}</span>
              </div>
              <div class="duty-persons">
                <div v-for="p in currentShift.persons" :key="p.id" class="duty-person">
                  <div class="person-avatar">{{ p.name.slice(0,1) }}</div>
                  <div class="person-info">
                    <div class="person-name">{{ p.name }}</div>
                    <div class="person-role">{{ p.role }}</div>
                  </div>
                  <el-tag size="small" type="success" effect="dark">在岗</el-tag>
                </div>
              </div>
            </div>
            <div class="shift-actions">
              <el-button type="primary" :disabled="!canManage" @click="openHandoverDialog()">
                <el-icon><Switch /></el-icon>
                交接班
              </el-button>
              <el-button :disabled="!canManage" @click="openLogDialog()">
                <el-icon><Edit /></el-icon>
                值班记录
              </el-button>
            </div>
          </div>
          <el-empty v-else description="暂无值班安排" />
        </el-card>
      </el-col>
      <el-col :lg="8" :md="24">
        <el-card class="module-card" shadow="never">
          <div class="card-header">
            <div class="card-title">值班制度</div>
          </div>
          <div class="rules-list">
            <div class="rule-item">
              <el-icon color="#22c55e"><CircleCheck /></el-icon>
              <span>实行24小时专人值班制度</span>
            </div>
            <div class="rule-item">
              <el-icon color="#22c55e"><CircleCheck /></el-icon>
              <span>每班值班人员不少于2人</span>
            </div>
            <div class="rule-item">
              <el-icon color="#22c55e"><CircleCheck /></el-icon>
              <span>值班人员持证上岗</span>
            </div>
            <div class="rule-item">
              <el-icon color="#22c55e"><CircleCheck /></el-icon>
              <span>严格执行交接班制度</span>
            </div>
            <div class="rule-item">
              <el-icon color="#22c55e"><CircleCheck /></el-icon>
              <span>确保消防设施正常运行</span>
            </div>
            <div class="rule-item">
              <el-icon color="#22c55e"><CircleCheck /></el-icon>
              <span>熟练掌握应急处置程序</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><Notebook /></el-icon>
          值班记录
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'handover' }" @click="activeTab = 'handover'">
          <el-icon><Switch /></el-icon>
          交接班记录
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'schedule' }" @click="activeTab = 'schedule'">
          <el-icon><Calendar /></el-icon>
          值班排班
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'persons' }" @click="activeTab = 'persons'">
          <el-icon><UserFilled /></el-icon>
          值班人员
        </div>
      </div>

      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" :disabled="!canManage" @click="openLogDialog()">
              <el-icon><Plus /></el-icon>
              新增记录
            </el-button>
          </div>
          <div class="toolbar-right">
            <el-date-picker
              v-model="logDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
              @change="handleRecordsPageChange(1)"
            />
            <el-input v-model="logSearch" placeholder="搜索记录内容 / 值班人 / 班次" style="width: 260px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table :data="filteredLogs" stripe style="width: 100%">
          <el-table-column prop="record_date" label="值班日期" width="120" />
          <el-table-column prop="shift_name" label="班次" width="110" />
          <el-table-column prop="duty_person" label="值班人" width="100" />
          <el-table-column prop="weather" label="天气" width="80" />
          <el-table-column prop="alarm_count" label="接警" width="70" align="center" />
          <el-table-column prop="handled_count" label="已处理" width="80" align="center" />
          <el-table-column label="设备状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.equipment_status === 'normal' ? 'success' : 'warning'">
                {{ row.equipment_status === 'normal' ? '正常' : '异常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="记录内容" min-width="240" show-overflow-tooltip />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :disabled="!canManage" @click="openLogDialog(row)">编辑</el-button>
              <el-button link type="danger" :disabled="!canManage" @click="removeRecord(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="recordsTotal"
            :page-size="recordsPageSize"
            :current-page="recordsPage"
            @current-change="handleRecordsPageChange"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'handover'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="handoverFilter" placeholder="交接状态" clearable style="width: 140px">
              <el-option label="已完成" value="completed" />
              <el-option label="待接班" value="pending" />
              <el-option label="异常" value="abnormal" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="handoverSearch" placeholder="搜索交接班记录" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table :data="filteredHandovers" stripe style="width: 100%">
          <el-table-column prop="handover_time" label="交接时间" width="170" />
          <el-table-column prop="shift_name" label="班次" width="110" />
          <el-table-column prop="from_person" label="交班人" width="100" />
          <el-table-column prop="to_person" label="接班人" width="100" />
          <el-table-column prop="equipment_status" label="设备状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.equipment_status === 'normal' ? 'success' : 'warning'">
                {{ row.equipment_status === 'normal' ? '正常' : '异常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="交接状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'completed' ? 'success' : row.status === 'pending' ? 'warning' : 'danger'">
                {{ row.status === 'completed' ? '已完成' : row.status === 'pending' ? '待接班' : '异常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="pending_matters" label="遗留事项" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" :disabled="!canManage" @click="removeHandover(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="handoversTotal"
            :page-size="handoversPageSize"
            :current-page="handoversPage"
            @current-change="handleHandoversPageChange"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'schedule'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" :disabled="!canManage" @click="openShiftDialog()">
              <el-icon><Plus /></el-icon>
              新增排班
            </el-button>
            <el-date-picker
              v-model="scheduleWeek"
              type="week"
              format="YYYY 第 ww 周"
              value-format="YYYY-MM-DD"
              :clearable="false"
              style="width: 180px"
              @change="loadWeekShifts"
            />
            <span class="toolbar-hint">{{ weekRangeText }}</span>
          </div>
        </div>
        <el-table :data="scheduleRows" border style="width: 100%" class="schedule-table">
          <el-table-column label="班次" width="120" align="center" fixed>
            <template #default="{ row }">
              <div class="schedule-shift">
                <span class="p-name">{{ row.shiftName }}</span>
                <span class="p-role">{{ row.timeRange }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-for="d in weekDays" :key="d.date" :label="d.label" align="center">
            <template #default="{ row }">
              <div class="schedule-cell" :class="{ 'is-today': d.date === todayDateStr }">
                <div v-for="(p, index) in row.cells[d.date] || []" :key="index" class="schedule-person">
                  <span class="p-name">{{ p.name }}</span>
                  <span class="p-role">{{ p.role }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!scheduleRows.length" description="本周暂无排班" />
      </div>

      <div v-if="activeTab === 'persons'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <span class="toolbar-hint">名单来自「值班排班」，此处只读</span>
          </div>
          <div class="toolbar-right">
            <el-input v-model="personSearch" placeholder="搜索姓名" style="width: 200px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-row :gutter="14">
          <el-col v-for="p in filteredPersons" :key="p.name" :xs="24" :sm="12" :md="8" :lg="6">
            <el-card class="person-card" shadow="hover">
              <div class="person-card-top">
                <div class="person-avatar-lg">{{ p.name.slice(0,1) }}</div>
                <div class="person-card-info">
                  <div class="person-card-name">{{ p.name }}</div>
                  <div class="person-card-post">{{ p.role || '未标注角色' }}</div>
                </div>
                <el-tag size="small" :type="p.onDuty ? 'success' : 'info'" effect="dark">
                  {{ p.statusText }}
                </el-tag>
              </div>
              <div class="person-card-body">
                <div v-for="s in p.shifts" :key="s.id" class="person-row">
                  <span>{{ s.date }}</span>
                  <span>{{ s.shiftName }} {{ s.timeRange }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-if="!filteredPersons.length" description="暂无排班人员" />
      </div>
    </el-card>

    <el-dialog v-model="showHandoverDialog" title="交接班" width="640px">
      <el-form :model="handoverForm" label-width="100px">
        <el-form-item label="交班班次">
          <span>{{ currentShift?.shift_name || '今日暂无生效班次' }}</span>
        </el-form-item>
        <el-form-item label="交班人">
          <span>{{ currentShiftPersonNames || '今日班次尚未排人' }}</span>
        </el-form-item>
        <el-form-item label="接班人">
          <el-select
            v-model="handoverForm.takeover_persons"
            multiple
            filterable
            allow-create
            placeholder="选择或输入接班人员"
            style="width: 100%"
          >
            <el-option v-for="p in scheduledPersons" :key="p.id" :label="p.name" :value="p.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备状态">
          <el-radio-group v-model="handoverForm.equipment_status">
            <el-radio value="normal">全部正常</el-radio>
            <el-radio value="abnormal">有异常</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="遗留事项">
          <el-input v-model="handoverForm.pending_matters" type="textarea" :rows="3" placeholder="请填写需要交接的事项..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showHandoverDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="savingHandover"
          :disabled="!currentShift || !currentShiftPersonNames || !handoverForm.takeover_persons.length"
          @click="doHandover"
        >
          确认交接
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showLogDialog" :title="logForm.id ? '编辑值班记录' : '新增值班记录'" width="600px">
      <el-form :model="logForm" label-width="100px">
        <el-form-item label="值班日期">
          <el-date-picker v-model="logForm.record_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="班次">
          <el-select v-model="logForm.shift_id" placeholder="选择班次" clearable style="width: 100%" @change="applyShiftToLog">
            <el-option
              v-for="s in shifts"
              :key="s.id"
              :label="`${s.dutyDate} ${s.shiftName} ${s.startTime}-${s.endTime}`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="值班人">
          <el-select v-model="logForm.duty_person" placeholder="选择或输入值班人" filterable allow-create style="width: 100%">
            <el-option v-for="p in currentShift?.persons || []" :key="p.name" :label="p.name" :value="p.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="天气">
          <el-input v-model="logForm.weather" placeholder="如：晴 / 阴 / 雨" />
        </el-form-item>
        <el-form-item label="设备状态">
          <el-radio-group v-model="logForm.equipment_status">
            <el-radio value="normal">正常</el-radio>
            <el-radio value="abnormal">异常</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="接警 / 处理">
          <el-input-number v-model="logForm.alarm_count" :min="0" />
          <span style="margin: 0 8px; color: #666;">/</span>
          <el-input-number v-model="logForm.handled_count" :min="0" />
        </el-form-item>
        <el-form-item label="记录内容">
          <el-input v-model="logForm.content" type="textarea" :rows="4" placeholder="请详细描述..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showLogDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingLog" :disabled="!logForm.record_date || !logForm.duty_person" @click="saveLog">
          保存记录
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showShiftDialog" title="新增排班" width="560px">
      <el-form :model="shiftForm" label-width="100px">
        <el-form-item label="班次名称">
          <el-input v-model="shiftForm.shift_name" placeholder="如：白班 / 夜班" />
        </el-form-item>
        <el-form-item label="班次类型">
          <el-radio-group v-model="shiftForm.shift_type">
            <el-radio value="day">日班</el-radio>
            <el-radio value="night">夜班</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="值班日期">
          <el-date-picker v-model="shiftForm.duty_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="值班时段">
          <el-time-select v-model="shiftForm.start_time" start="00:00" step="00:30" end="23:30" placeholder="开始时间" style="width: 150px" />
          <span style="margin: 0 8px; color: #666;">-</span>
          <el-time-select v-model="shiftForm.end_time" start="00:00" step="00:30" end="23:30" placeholder="结束时间" style="width: 150px" />
        </el-form-item>
        <el-form-item label="值班人员">
          <el-select
            v-model="shiftForm.persons"
            multiple
            filterable
            allow-create
            placeholder="选择或输入值班人员"
            style="width: 100%"
          >
            <el-option v-for="p in scheduledPersons" :key="p.id" :label="p.name" :value="p.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showShiftDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="savingShift"
          :disabled="!shiftForm.shift_name || !shiftForm.duty_date"
          @click="saveShift"
        >
          保存排班
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  User, Document, Warning, CircleCheck, Sunrise, Switch, Edit,
  Notebook, Calendar, UserFilled, Plus, Search
} from '@element-plus/icons-vue'
import request from '../api'
import { getCurrentUser, hasPermission } from '../auth'

const activeTab = ref('records')
const showHandoverDialog = ref(false)
const showLogDialog = ref(false)

const stats = ref({})
const shifts = ref([])
const recordsTotal = ref(0)
const handoversTotal = ref(0)
const recordsPage = ref(1)
const recordsPageSize = ref(20)
const handoversPage = ref(1)
const handoversPageSize = ref(20)

const todayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日 星期${'日一二三四五六'[d.getDay()]}`
})

const todayDateStr = computed(() => {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
})

const currentShift = computed(() => {
  const todayShifts = shifts.value.filter(s => s.dutyDate === todayDateStr.value && s.status === 'active')
  if (todayShifts.length === 0) return null
  const shift = todayShifts[0]
  return {
    id: shift.id,
    shift_name: shift.shiftName,
    start_time: shift.startTime,
    end_time: shift.endTime,
    persons: normalizePersons(shift.persons),
  }
})

// 库里的 persons 既可能是 ["张三"] 也可能是 [{id,name,role}]，统一成对象再渲染
function normalizePersons(raw) {
  let list = raw
  if (typeof list === 'string') {
    try {
      list = JSON.parse(list)
    } catch (e) {
      list = []
    }
  }
  if (!Array.isArray(list)) return []
  return list.map((item, index) => {
    if (typeof item === 'string') return { id: index + 1, name: item, role: '' }
    return { id: item.id ?? index + 1, name: item.name || '', role: item.role || '' }
  })
}

const currentShiftPersonNames = computed(
  () => (currentShift.value?.persons || []).map(p => p.name).filter(Boolean).join('、')
)

const canManage = computed(() => hasPermission(getCurrentUser(), 'duty:manage'))

// 跨全部排班收集出现过的值班人，作为「接班人」下拉的候选（也可以直接输入名单外的人）
const scheduledPersons = computed(() => {
  const byName = new Map()
  for (const shift of shifts.value) {
    for (const p of normalizePersons(shift.persons)) {
      if (!p.name || byName.has(p.name)) continue
      byName.set(p.name, { id: p.id, name: p.name, role: p.role })
    }
  }
  return [...byName.values()]
})

const dutyLogs = ref([])

const handoverRecords = ref([])

// 周排班表按「周一 ~ 周日」渲染，数据来自 GET /api/duty/shifts?start_date&end_date
const weekShifts = ref([])
const scheduleWeek = ref(todayDateStr.value)
const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function toDateStr(d) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 取某个日期所在周的周一；传空则用今天。返回七天的日期与显示文案 */
function weekDaysOf(raw) {
  const base = raw ? new Date(`${String(raw).slice(0, 10)}T00:00:00`) : new Date()
  if (Number.isNaN(base.getTime())) return weekDaysOf('')
  const offset = base.getDay() === 0 ? 6 : base.getDay() - 1
  base.setDate(base.getDate() - offset)
  return WEEK_LABELS.map((label, index) => {
    const d = new Date(base)
    d.setDate(base.getDate() + index)
    return { date: toDateStr(d), label: `${label} ${d.getMonth() + 1}/${d.getDate()}` }
  })
}

const weekDays = computed(() => weekDaysOf(scheduleWeek.value))

const weekRangeText = computed(() => `${weekDays.value[0].date} ~ ${weekDays.value[6].date}`)

// 同一周里「班次名 + 时段」相同的就是一行；单元格里放当天该班次的人
const scheduleRows = computed(() => {
  const rows = new Map()
  for (const shift of weekShifts.value) {
    const timeRange = `${shift.startTime}-${shift.endTime}`
    const key = `${shift.shiftName}|${timeRange}`
    const row = rows.get(key) || { key, shiftName: shift.shiftName, timeRange, cells: {} }
    const persons = normalizePersons(shift.persons)
    if (persons.length) row.cells[shift.dutyDate] = persons
    rows.set(key, row)
  }
  return [...rows.values()].sort(
    (a, b) => a.timeRange.localeCompare(b.timeRange) || a.shiftName.localeCompare(b.shiftName)
  )
})

async function loadWeekShifts(anchor = scheduleWeek.value) {
  const days = weekDaysOf(anchor)
  try {
    const res = await request.get('/api/duty/shifts', {
      params: { start_date: days[0].date, end_date: days[6].date }
    })
    weekShifts.value = res.data || []
  } catch (e) {
    ElMessage.error('加载本周排班失败')
  }
}

const showShiftDialog = ref(false)
const savingShift = ref(false)

function emptyShiftForm() {
  return {
    shift_name: '',
    shift_type: 'day',
    duty_date: todayDateStr.value,
    start_time: '08:00',
    end_time: '20:00',
    persons: [],
  }
}

const shiftForm = ref(emptyShiftForm())

function openShiftDialog() {
  const form = emptyShiftForm()
  // 默认排到当前正在看的那一周：今天就在这一周就用今天，否则用那一周的周一
  const days = weekDaysOf(scheduleWeek.value)
  if (!days.some(d => d.date === todayDateStr.value)) form.duty_date = days[0].date
  shiftForm.value = form
  showShiftDialog.value = true
}

async function saveShift() {
  if (!shiftForm.value.shift_name || !shiftForm.value.duty_date) {
    ElMessage.warning('班次名称与值班日期不能为空')
    return
  }
  savingShift.value = true
  try {
    const res = await request.post('/api/duty/shifts', { ...shiftForm.value })
    ElMessage.success('排班已创建')
    showShiftDialog.value = false
    const savedDate = res.data?.shift?.dutyDate
    if (savedDate) scheduleWeek.value = savedDate
    // 排班变了，「当前值班信息」也要跟着变
    await Promise.all([loadWeekShifts(scheduleWeek.value), loadShifts()])
  } catch (e) {
    // 失败原因由拦截器统一提示（例如同日同名班次、同一人同日重复排班）
  } finally {
    savingShift.value = false
  }
}

const logSearch = ref('')
const logDateRange = ref([])
const handoverFilter = ref('')
const handoverSearch = ref('')
const personSearch = ref('')

const savingLog = ref(false)
const savingHandover = ref(false)

const handoverForm = ref({
  takeover_persons: [],
  equipment_status: 'normal',
  pending_matters: '',
})

function emptyLogForm() {
  return {
    id: null,
    record_date: todayDateStr.value,
    shift_id: null,
    duty_person: '',
    weather: '',
    equipment_status: 'normal',
    alarm_count: 0,
    handled_count: 0,
    content: '',
  }
}

const logForm = ref(emptyLogForm())

const filteredLogs = computed(() => {
  const keyword = logSearch.value.trim()
  if (!keyword) return dutyLogs.value
  return dutyLogs.value.filter(l =>
    (l.content || '').includes(keyword) ||
    (l.duty_person || '').includes(keyword) ||
    (l.shift_name || '').includes(keyword)
  )
})

const filteredHandovers = computed(() => {
  let list = handoverRecords.value
  if (handoverFilter.value) list = list.filter(h => h.status === handoverFilter.value)
  const keyword = handoverSearch.value.trim()
  if (!keyword) return list
  return list.filter(h =>
    (h.from_person || '').includes(keyword) ||
    (h.to_person || '').includes(keyword) ||
    (h.shift_name || '').includes(keyword)
  )
})

// 「值班人员」页签：后端没有人员主数据表，只能按真实排班推——列出今天及以后
// 每个班次的当班人，证书、电话、入职日期这些库里没有的信息一律不显示
const dutyPersonCards = computed(() => {
  const today = todayDateStr.value
  const byName = new Map()
  for (const shift of shifts.value) {
    // 停用的班次不算当班
    if (!shift.dutyDate || shift.status !== 'active' || shift.dutyDate < today) continue
    const onDuty = shift.id === currentShift.value?.id
    for (const p of normalizePersons(shift.persons)) {
      if (!p.name) continue
      const card = byName.get(p.name) || { name: p.name, role: p.role, onDuty: false, shifts: [] }
      if (!card.role && p.role) card.role = p.role
      card.onDuty = card.onDuty || onDuty
      card.shifts.push({
        id: shift.id,
        date: shift.dutyDate,
        shiftName: shift.shiftName,
        timeRange: `${shift.startTime}-${shift.endTime}`,
      })
      byName.set(p.name, card)
    }
  }
  return [...byName.values()]
    .map(card => {
      const shifts = card.shifts.sort((a, b) => a.date.localeCompare(b.date))
      return {
        ...card,
        shifts,
        statusText: card.onDuty ? '值班中' : shifts[0].date === today ? '今日值班' : '待值班',
      }
    })
    .sort((a, b) => Number(b.onDuty) - Number(a.onDuty) || a.name.localeCompare(b.name))
})

const filteredPersons = computed(() => {
  const keyword = personSearch.value.trim()
  if (!keyword) return dutyPersonCards.value
  return dutyPersonCards.value.filter(p => p.name.includes(keyword))
})

async function loadStats() {
  try {
    const res = await request.get('/api/duty/stats')
    stats.value = res.data || {}
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

async function loadShifts() {
  try {
    const res = await request.get('/api/duty/shifts')
    shifts.value = res.data || []
  } catch (e) {
    console.error('加载值班班次失败', e)
  }
}

async function loadRecords() {
  try {
    const params = {
      page: recordsPage.value,
      page_size: recordsPageSize.value
    }
    if (logDateRange.value?.length === 2) {
      params.start_date = logDateRange.value[0]
      params.end_date = logDateRange.value[1]
    }
    const res = await request.get('/api/duty/records', { params })
    const data = res.data || {}
    recordsTotal.value = data.total || 0
    // 只映射库里真有的字段：「记录类型」「状态」在 duty_records 里并不存在，
    // 之前是本地编出来的（恒为「日常值班」、拿设备状态冒充），不再伪造
    dutyLogs.value = (data.list || []).map(item => ({
      id: item.id,
      record_date: item.recordDate,
      shift_id: item.shiftId,
      shift_name: item.shiftName || '',
      duty_person: item.dutyPerson || '',
      weather: item.weather || '',
      alarm_count: item.alarmCount ?? 0,
      handled_count: item.handledCount ?? 0,
      equipment_status: item.equipmentStatus || 'normal',
      content: item.content || ''
    }))
  } catch (e) {
    ElMessage.error('加载值班记录失败')
  }
}

async function loadHandovers() {
  try {
    const params = {
      page: handoversPage.value,
      page_size: handoversPageSize.value
    }
    const res = await request.get('/api/duty/handovers', { params })
    const data = res.data || {}
    handoversTotal.value = data.total || 0
    handoverRecords.value = (data.list || []).map(item => ({
      id: item.id,
      handover_time: item.handoverTime,
      shift_name: item.shiftName || '',
      from_person: item.fromPerson || '',
      to_person: item.toPerson || '',
      equipment_status: item.equipmentStatus || 'normal',
      status: item.status,
      pending_matters: item.pendingMatters || ''
    }))
  } catch (e) {
    ElMessage.error('加载交接班记录失败')
  }
}

function handleRecordsPageChange(page) {
  recordsPage.value = page
  loadRecords()
}

function handleHandoversPageChange(page) {
  handoversPage.value = page
  loadHandovers()
}

onMounted(() => {
  loadStats()
  loadShifts()
  loadRecords()
  loadHandovers()
  loadWeekShifts()
})

function openHandoverDialog() {
  handoverForm.value = { takeover_persons: [], equipment_status: 'normal', pending_matters: '' }
  showHandoverDialog.value = true
}

function openLogDialog(row) {
  // 只有真正的记录行才当编辑处理：模板里若写成 `@click="openLogDialog"`，
  // 传进来的会是点击事件对象，会被误判成编辑态
  const editing = row && typeof row === 'object' && row.id ? row : null
  if (editing) {
    logForm.value = {
      id: editing.id,
      record_date: editing.record_date,
      shift_id: editing.shift_id,
      duty_person: editing.duty_person,
      weather: editing.weather,
      equipment_status: editing.equipment_status,
      alarm_count: editing.alarm_count,
      handled_count: editing.handled_count,
      content: editing.content,
    }
  } else {
    logForm.value = emptyLogForm()
    // 新增时默认落在页面上正在显示的「当前值班信息」上：否则默认新增出来的记录
    // 班次恒为空，列表里那一列又变成摆设
    if (currentShift.value) {
      logForm.value.shift_id = currentShift.value.id
      applyShiftToLog(currentShift.value.id)
    }
  }
  showLogDialog.value = true
}

// 选班次时带出日期，并在只有一个人值班时顺手填上值班人
function applyShiftToLog(shiftId) {
  const shift = shifts.value.find(s => s.id === shiftId)
  if (!shift) return
  if (shift.dutyDate) logForm.value.record_date = shift.dutyDate
  const names = normalizePersons(shift.persons).map(p => p.name).filter(Boolean)
  if (!logForm.value.duty_person && names.length === 1) {
    logForm.value.duty_person = names[0]
  }
}

async function saveLog() {
  if (!logForm.value.record_date || !logForm.value.duty_person) {
    ElMessage.warning('值班日期与值班人不能为空')
    return
  }
  savingLog.value = true
  try {
    const payload = { ...logForm.value }
    if (logForm.value.id) {
      await request.put(`/api/duty/records/${logForm.value.id}`, payload)
    } else {
      await request.post('/api/duty/records', payload)
    }
    ElMessage.success('值班记录已保存')
    showLogDialog.value = false
    await Promise.all([loadRecords(), loadStats()])
  } catch (e) {
    // 失败原因由拦截器统一提示（例如日期格式、班次不存在）
  } finally {
    savingLog.value = false
  }
}

async function doHandover() {
  if (!currentShift.value) {
    ElMessage.warning('今日没有生效班次，无法交接班')
    return
  }
  if (!handoverForm.value.takeover_persons.length) {
    ElMessage.warning('请选择接班人')
    return
  }
  savingHandover.value = true
  try {
    await request.post('/api/duty/handovers', {
      shift_id: currentShift.value.id,
      from_person: currentShiftPersonNames.value,
      to_person: handoverForm.value.takeover_persons.join('、'),
      equipment_status: handoverForm.value.equipment_status,
      pending_matters: handoverForm.value.pending_matters,
    })
    ElMessage.success('交接班已记录')
    showHandoverDialog.value = false
    await loadHandovers()
  } catch (e) {
    // 失败原因由拦截器统一提示
  } finally {
    savingHandover.value = false
  }
}

async function removeRecord(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.record_date} ${row.duty_person}」的值班记录吗？`, '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await request.delete(`/api/duty/records/${row.id}`)
    ElMessage.success('值班记录已删除')
    await Promise.all([loadRecords(), loadStats()])
  } catch (e) {
    // 失败原因由拦截器统一提示
  }
}

async function removeHandover(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.from_person} → ${row.to_person}」的交接班记录吗？`, '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await request.delete(`/api/duty/handovers/${row.id}`)
    ElMessage.success('交接班记录已删除')
    await loadHandovers()
  } catch (e) {
    // 失败原因由拦截器统一提示
  }
}
</script>

<style scoped>
.duty-room-page {
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

.title-actions {
  display: flex;
  gap: 10px;
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
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.cyan { background: linear-gradient(135deg, #06b6d4, #0891b2); }

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

.duty-info-row {
  margin-bottom: 16px;
}

.module-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.card-header {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.card-subtitle {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.shift-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.shift-main {
  flex: 1;
}

.shift-badge {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.shift-name {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.shift-time {
  font-size: 14px;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 10px;
  border-radius: 6px;
}

.duty-persons {
  display: flex;
  gap: 20px;
}

.duty-person {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}

.person-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
}

.person-info {
  flex: 1;
}

.person-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.person-role {
  font-size: 12px;
  color: #64748b;
}

.shift-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rule-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
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
  position: relative;
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

.tab-item .badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
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

.toolbar-hint {
  font-size: 12px;
  color: #94a3b8;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.schedule-table :deep(.el-table__cell) {
  padding: 8px;
}

.schedule-cell {
  min-height: 60px;
  padding: 4px;
  border-radius: 6px;
}

/* 今天那一列单独标一下，周视图里好定位 */
.schedule-cell.is-today {
  background: #eff6ff;
}

.schedule-shift {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.schedule-person {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 4px;
  background: #f8fafc;
  border-radius: 6px;
  margin-bottom: 6px;
}

.schedule-person:last-child {
  margin-bottom: 0;
}

.p-name {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.p-role {
  font-size: 11px;
  color: #94a3b8;
}

.person-card {
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.person-card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e2e8f0;
}

.person-avatar-lg {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 600;
  flex-shrink: 0;
}

.person-card-info {
  flex: 1;
}

.person-card-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.person-card-post {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.person-card-body {
  padding: 12px 0;
}

.person-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  padding: 4px 0;
}

.person-row span:first-child {
  color: #94a3b8;
  flex-shrink: 0;
}

.person-row span:last-child {
  color: #334155;
  font-weight: 500;
  text-align: right;
}
</style>
