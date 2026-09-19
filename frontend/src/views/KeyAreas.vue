<template>
  <div class="key-areas-page">
    <div class="title-row">
      <div>
        <div class="page-title">重点部位管理</div>
        <p class="subtitle">重点防火部位 · 危险源管控 · 消防安全重点区域</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><LocationInformation /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalAreas }}</div>
            <div class="stat-label">部位总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.level1 }}</div>
            <div class="stat-label">一级部位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Bell /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.level2 }}</div>
            <div class="stat-label">二级部位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon yellow"><el-icon><InfoFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.level3 }}</div>
            <div class="stat-label">三级部位</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'list' }" @click="activeTab = 'list'">
          <el-icon><List /></el-icon>
          部位列表
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'risk' }" @click="activeTab = 'risk'">
          <el-icon><DataAnalysis /></el-icon>
          风险分级
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">
          <el-icon><Document /></el-icon>
          检查记录
        </div>
      </div>

      <div v-if="activeTab === 'list'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              新增部位
            </el-button>
            <el-select v-model="levelFilter" placeholder="部位等级" clearable style="width: 140px">
              <el-option label="一级部位" value="1" />
              <el-option label="二级部位" value="2" />
              <el-option label="三级部位" value="3" />
            </el-select>
            <el-select v-model="buildingFilter" placeholder="所属建筑" clearable style="width: 160px">
              <el-option label="综合办公楼A座" value="综合办公楼A座" />
              <el-option label="实验楼B座" value="实验楼B座" />
              <el-option label="学生宿舍C区" value="学生宿舍C区" />
              <el-option label="图书馆D馆" value="图书馆D馆" />
              <el-option label="学生食堂" value="学生食堂" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="areaSearch" placeholder="搜索部位名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="area in filteredAreas" :key="area.id">
            <el-card class="area-card" shadow="hover">
              <div class="area-header">
                <div class="area-icon" :class="'level' + area.level">
                  <el-icon><LocationInformation /></el-icon>
                </div>
                <div class="area-title">
                  <div class="area-name">{{ area.name }}</div>
                  <div class="area-building">{{ area.building }}</div>
                </div>
                <el-tag size="small" effect="dark" :type="area.level === 1 ? 'danger' : area.level === 2 ? 'warning' : 'info'">
                  {{ area.level === 1 ? '一级' : area.level === 2 ? '二级' : '三级' }}
                </el-tag>
              </div>
              <div class="area-detail">
                <div class="detail-row">
                  <span class="label">责任人</span>
                  <span class="value">{{ area.person }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">联系电话</span>
                  <span class="value">{{ area.phone }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">最近检查</span>
                  <span class="value">{{ area.lastCheck }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">状态</span>
                  <span class="value">
                    <el-tag size="small" :type="area.status === 'normal' ? 'success' : 'danger'">
                      {{ area.status === 'normal' ? '正常' : '有隐患' }}
                    </el-tag>
                  </span>
                </div>
              </div>
              <div class="area-actions">
                <el-button size="small">查看详情</el-button>
                <el-button size="small" type="primary">检查记录</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'risk'" class="tab-content">
        <div class="risk-intro">
          <el-alert
            title="按建筑维度展示各等级重点部位分布情况，一级部位为最高风险等级，需重点关注。"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 20px"
          />
        </div>
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" v-for="building in buildingRisk" :key="building.name">
            <el-card class="risk-card" shadow="hover">
              <div class="risk-header">
                <div class="building-icon"><el-icon><OfficeBuilding /></el-icon></div>
                <div class="building-info">
                  <div class="building-name">{{ building.name }}</div>
                  <div class="building-total">共 {{ building.total }} 个重点部位</div>
                </div>
              </div>
              <div class="risk-bars">
                <div class="risk-bar-item">
                  <div class="bar-label">
                    <span class="level-dot level1"></span>
                    <span>一级部位</span>
                    <span class="bar-count">{{ building.level1 }} 个</span>
                  </div>
                  <el-progress :percentage="building.level1Percent" :color="'#ef4444'" :stroke-width="10" :show-text="false" />
                </div>
                <div class="risk-bar-item">
                  <div class="bar-label">
                    <span class="level-dot level2"></span>
                    <span>二级部位</span>
                    <span class="bar-count">{{ building.level2 }} 个</span>
                  </div>
                  <el-progress :percentage="building.level2Percent" :color="'#f97316'" :stroke-width="10" :show-text="false" />
                </div>
                <div class="risk-bar-item">
                  <div class="bar-label">
                    <span class="level-dot level3"></span>
                    <span>三级部位</span>
                    <span class="bar-count">{{ building.level3 }} 个</span>
                  </div>
                  <el-progress :percentage="building.level3Percent" :color="'#eab308'" :stroke-width="10" :show-text="false" />
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'records'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="recordResultFilter" placeholder="检查结果" clearable style="width: 140px">
              <el-option label="正常" value="normal" />
              <el-option label="有隐患" value="danger" />
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
          <el-table-column prop="check_date" label="检查时间" width="140" />
          <el-table-column prop="area_name" label="部位名称" min-width="180" />
          <el-table-column prop="building" label="所属建筑" width="160" />
          <el-table-column label="部位等级" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.level === 1 ? 'danger' : row.level === 2 ? 'warning' : 'info'">
                {{ row.level === 1 ? '一级' : row.level === 2 ? '二级' : '三级' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="inspector" label="检查人" width="100" />
          <el-table-column label="检查结果" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.result === 'normal' ? 'success' : 'danger'">
                {{ row.result === 'normal' ? '正常' : '有隐患' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="danger_desc" label="隐患描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
              <el-button link type="warning">整改</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { LocationInformation, Warning, Bell, InfoFilled, List, DataAnalysis, Document, Plus, Search, Download, OfficeBuilding } from '@element-plus/icons-vue'

const activeTab = ref('list')
const areaSearch = ref('')
const levelFilter = ref('')
const buildingFilter = ref('')
const recordResultFilter = ref('')
const recordDateRange = ref([])

const stats = ref({
  totalAreas: 28,
  level1: 6,
  level2: 10,
  level3: 12,
})

const areas = ref([
  { id: 1, name: '消防水泵房', building: '综合办公楼A座', level: 1, person: '张建国', phone: '138****8888', lastCheck: '2026-09-05', status: 'normal' },
  { id: 2, name: '配电房', building: '综合办公楼A座', level: 1, person: '李明华', phone: '139****6666', lastCheck: '2026-09-03', status: 'normal' },
  { id: 3, name: '档案室', building: '综合办公楼A座', level: 2, person: '王淑芬', phone: '137****9999', lastCheck: '2026-09-01', status: 'normal' },
  { id: 4, name: '化学实验室', building: '实验楼B座', level: 1, person: '赵文博', phone: '136****7777', lastCheck: '2026-09-06', status: 'danger' },
  { id: 5, name: '危险品仓库', building: '实验楼B座', level: 1, person: '孙志强', phone: '135****5555', lastCheck: '2026-09-04', status: 'normal' },
  { id: 6, name: '计算机机房', building: '实验楼B座', level: 2, person: '周晓燕', phone: '134****4444', lastCheck: '2026-09-02', status: 'normal' },
  { id: 7, name: '学生宿舍配电室', building: '学生宿舍C区', level: 2, person: '吴大勇', phone: '133****3333', lastCheck: '2026-09-05', status: 'normal' },
  { id: 8, name: '锅炉房', building: '学生宿舍C区', level: 1, person: '郑海涛', phone: '132****2222', lastCheck: '2026-09-06', status: 'normal' },
  { id: 9, name: '图书珍藏室', building: '图书馆D馆', level: 2, person: '冯美玲', phone: '131****1111', lastCheck: '2026-09-03', status: 'normal' },
  { id: 10, name: '古籍阅览室', building: '图书馆D馆', level: 3, person: '陈志强', phone: '130****0000', lastCheck: '2026-09-01', status: 'normal' },
  { id: 11, name: '食堂厨房', building: '学生食堂', level: 2, person: '褚大厨', phone: '159****1234', lastCheck: '2026-09-06', status: 'danger' },
  { id: 12, name: '燃气调压间', building: '学生食堂', level: 1, person: '卫安全', phone: '158****5678', lastCheck: '2026-09-05', status: 'normal' },
])

const buildingRisk = ref([
  { name: '综合办公楼A座', total: 6, level1: 2, level2: 1, level3: 3, level1Percent: 33, level2Percent: 17, level3Percent: 50 },
  { name: '实验楼B座', total: 8, level1: 2, level2: 4, level3: 2, level1Percent: 25, level2Percent: 50, level3Percent: 25 },
  { name: '学生宿舍C区', total: 7, level1: 1, level2: 3, level3: 3, level1Percent: 14, level2Percent: 43, level3Percent: 43 },
  { name: '图书馆D馆', total: 4, level1: 0, level2: 1, level3: 3, level1Percent: 0, level2Percent: 25, level3Percent: 75 },
  { name: '学生食堂', total: 3, level1: 1, level2: 1, level3: 1, level1Percent: 33, level2Percent: 33, level3Percent: 34 },
])

const records = ref([
  { check_date: '2026-09-06 14:30', area_name: '化学实验室', building: '实验楼B座', level: 1, inspector: '李安全', result: 'danger', danger_desc: '发现2具灭火器压力不足，应急照明灯具故障1处' },
  { check_date: '2026-09-06 10:15', area_name: '食堂厨房', building: '学生食堂', level: 2, inspector: '王消防', result: 'danger', danger_desc: '油烟管道积油严重，燃气报警器测试不灵敏' },
  { check_date: '2026-09-05 16:00', area_name: '消防水泵房', building: '综合办公楼A座', level: 1, inspector: '张维保', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-05 11:20', area_name: '燃气调压间', building: '学生食堂', level: 1, inspector: '赵检查', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-05 09:30', area_name: '学生宿舍配电室', building: '学生宿舍C区', level: 2, inspector: '孙工', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-04 15:45', area_name: '危险品仓库', building: '实验楼B座', level: 1, inspector: '周安全员', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-03 14:00', area_name: '配电房', building: '综合办公楼A座', level: 1, inspector: '吴电工', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-03 10:30', area_name: '图书珍藏室', building: '图书馆D馆', level: 2, inspector: '郑管理', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-02 16:15', area_name: '计算机机房', building: '实验楼B座', level: 2, inspector: '冯IT', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-01 13:45', area_name: '档案室', building: '综合办公楼A座', level: 2, inspector: '陈档案', result: 'normal', danger_desc: '' },
  { check_date: '2026-09-01 09:00', area_name: '古籍阅览室', building: '图书馆D馆', level: 3, inspector: '褚馆员', result: 'normal', danger_desc: '' },
])

const filteredAreas = computed(() => {
  let list = areas.value
  if (areaSearch.value) {
    list = list.filter(a => a.name.includes(areaSearch.value) || a.building.includes(areaSearch.value))
  }
  if (levelFilter.value) {
    list = list.filter(a => String(a.level) === levelFilter.value)
  }
  if (buildingFilter.value) {
    list = list.filter(a => a.building === buildingFilter.value)
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
</script>

<style scoped>
.key-areas-page {
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
  font-size: 22px;
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
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.yellow { background: linear-gradient(135deg, #eab308, #ca8a04); }

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

.area-card {
  margin-bottom: 16px;
}

.area-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.area-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  color: #fff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.area-icon.level1 { background: linear-gradient(135deg, #ef4444, #dc2626); }
.area-icon.level2 { background: linear-gradient(135deg, #f97316, #ea580c); }
.area-icon.level3 { background: linear-gradient(135deg, #eab308, #ca8a04); }

.area-title {
  flex: 1;
  min-width: 0;
}

.area-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 2px;
}

.area-building {
  font-size: 12px;
  color: #64748b;
}

.area-detail {
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

.area-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.risk-intro {
  margin-bottom: 8px;
}

.risk-card {
  margin-bottom: 16px;
}

.risk-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.building-icon {
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

.building-info {
  flex: 1;
}

.building-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 2px;
}

.building-total {
  font-size: 12px;
  color: #64748b;
}

.risk-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.risk-bar-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bar-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}

.level-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.level-dot.level1 { background-color: #ef4444; }
.level-dot.level2 { background-color: #f97316; }
.level-dot.level3 { background-color: #eab308; }

.bar-count {
  margin-left: auto;
  font-weight: 600;
  color: #0f172a;
}
</style>
