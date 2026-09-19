<template>
  <div class="fire-archives-page">
    <div class="title-row">
      <div>
        <div class="page-title">消防档案</div>
        <p class="subtitle">建筑消防档案 · 设施设备档案 · 法律文书 · 符合GB25201标准</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Folder /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.total }}</div>
            <div class="stat-label">档案总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.buildings }}</div>
            <div class="stat-label">建筑档案</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><SetUp /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.facilities }}</div>
            <div class="stat-label">设施档案</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.legalDocs }}</div>
            <div class="stat-label">法律文书</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'buildings' }" @click="activeTab = 'buildings'">
          <el-icon><OfficeBuilding /></el-icon>
          建筑档案
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'facilities' }" @click="activeTab = 'facilities'">
          <el-icon><SetUp /></el-icon>
          设施档案
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'legal' }" @click="activeTab = 'legal'">
          <el-icon><Document /></el-icon>
          法律文书
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'drawings' }" @click="activeTab = 'drawings'">
          <el-icon><Picture /></el-icon>
          图纸资料
        </div>
      </div>

      <div v-if="activeTab === 'buildings'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              新建档案
            </el-button>
            <el-select v-model="buildingTypeFilter" placeholder="建筑类型" clearable style="width: 140px">
              <el-option label="办公楼" value="office" />
              <el-option label="教学楼" value="teaching" />
              <el-option label="宿舍楼" value="dormitory" />
              <el-option label="图书馆" value="library" />
              <el-option label="食堂" value="canteen" />
              <el-option label="车库" value="garage" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="buildingSearch" placeholder="搜索建筑名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="b in filteredBuildings" :key="b.id">
            <el-card class="building-card" shadow="hover">
              <div class="building-header">
                <div class="building-icon"><el-icon><OfficeBuilding /></el-icon></div>
                <div class="building-info">
                  <div class="building-name">{{ b.name }}</div>
                  <div class="building-type">
                    <el-tag size="small" :type="buildingTypeTag(b.type)">{{ buildingTypeText(b.type) }}</el-tag>
                  </div>
                </div>
              </div>
              <div class="building-detail">
                <div class="detail-row">
                  <span class="label">档案编号</span>
                  <span class="value">{{ b.archive_no }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">建筑面积</span>
                  <span class="value">{{ b.area }} ㎡</span>
                </div>
                <div class="detail-row">
                  <span class="label">建筑层数</span>
                  <span class="value">{{ b.floors }} 层</span>
                </div>
                <div class="detail-row">
                  <span class="label">消防验收日期</span>
                  <span class="value">{{ b.acceptance_date }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">消防安全责任人</span>
                  <span class="value">{{ b.responsible_person }}</span>
                </div>
              </div>
              <div class="building-actions">
                <el-button size="small">查看详情</el-button>
                <el-button size="small" type="primary">编辑档案</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'facilities'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              添加设施
            </el-button>
            <el-select v-model="facilityTypeFilter" placeholder="设施类型" clearable style="width: 150px">
              <el-option label="火灾自动报警系统" value="fire_alarm" />
              <el-option label="自动喷水灭火系统" value="sprinkler" />
              <el-option label="消火栓系统" value="hydrant" />
              <el-option label="防排烟系统" value="ventilation" />
              <el-option label="防火分隔设施" value="fire_separation" />
              <el-option label="应急照明系统" value="emergency_lighting" />
            </el-select>
            <el-select v-model="facilityStatusFilter" placeholder="档案状态" clearable style="width: 140px">
              <el-option label="正常" value="normal" />
              <el-option label="待更新" value="pending" />
              <el-option label="已过期" value="expired" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="facilitySearch" placeholder="搜索设施名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredFacilities" stripe style="width: 100%">
          <el-table-column prop="facility_name" label="设施名称" min-width="180" />
          <el-table-column label="类型" width="150">
            <template #default="{ row }">
              <el-tag size="small">{{ facilityTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="spec_model" label="规格型号" width="160" />
          <el-table-column prop="install_location" label="安装位置" min-width="180" />
          <el-table-column prop="install_date" label="安装日期" width="120" />
          <el-table-column prop="maintenance_company" label="维保单位" width="180" />
          <el-table-column label="档案状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'normal' ? 'success' : row.status === 'pending' ? 'warning' : 'danger'">
                {{ row.status === 'normal' ? '正常' : row.status === 'pending' ? '待更新' : '已过期' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default>
              <el-button link type="primary">查看</el-button>
              <el-button link type="warning">编辑</el-button>
              <el-button link type="success">维保记录</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'legal'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              新增文书
            </el-button>
            <el-select v-model="legalTypeFilter" placeholder="文书类型" clearable style="width: 150px">
              <el-option label="消防验收" value="acceptance" />
              <el-option label="安全检查" value="safety_inspection" />
              <el-option label="行政处罚" value="penalty" />
              <el-option label="行政许可" value="permit" />
              <el-option label="备案凭证" value="record" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="legalSearch" placeholder="搜索文书名称/编号" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredLegalDocs" stripe style="width: 100%">
          <el-table-column prop="doc_name" label="文书名称" min-width="200" />
          <el-table-column prop="doc_no" label="编号" width="180" />
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="legalTypeTag(row.type)">{{ legalTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="issued_by" label="出具单位" width="200" />
          <el-table-column prop="issue_date" label="出具日期" width="120" />
          <el-table-column label="有效期" width="140">
            <template #default="{ row }">
              <span :class="row.days_left < 30 ? 'danger-text' : ''">{{ row.valid_until }} ({{ row.days_left }}天)</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default>
              <el-button link type="primary">查看</el-button>
              <el-button link type="success">下载</el-button>
              <el-button link type="warning">续期</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'drawings'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary">
              <el-icon><Plus /></el-icon>
              上传图纸
            </el-button>
            <el-select v-model="drawingTypeFilter" placeholder="图纸类型" clearable style="width: 140px">
              <el-option label="平面图" value="floor_plan" />
              <el-option label="系统图" value="system_diagram" />
              <el-option label="布置图" value="layout" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="drawingSearch" placeholder="搜索图纸名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredDrawings" stripe style="width: 100%">
          <el-table-column prop="drawing_name" label="图纸名称" min-width="220" />
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="drawingTypeTag(row.type)">{{ drawingTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="building_name" label="所属建筑" width="180" />
          <el-table-column prop="version" label="版本号" width="100" align="center" />
          <el-table-column prop="update_date" label="更新日期" width="120" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default>
              <el-button link type="primary">预览</el-button>
              <el-button link type="success">下载</el-button>
              <el-button link type="warning">更新版本</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  Folder, OfficeBuilding, SetUp, Document, Picture, Plus, Search
} from '@element-plus/icons-vue'

const activeTab = ref('buildings')
const buildingSearch = ref('')
const buildingTypeFilter = ref('')
const facilitySearch = ref('')
const facilityTypeFilter = ref('')
const facilityStatusFilter = ref('')
const legalSearch = ref('')
const legalTypeFilter = ref('')
const drawingSearch = ref('')
const drawingTypeFilter = ref('')

const stats = ref({
  total: 156,
  buildings: 8,
  facilities: 128,
  legalDocs: 20,
})

const buildings = ref([
  { id: 1, name: '综合办公楼A座', type: 'office', area: 28500, floors: 18, acceptance_date: '2020-06-15', responsible_person: '张建国', archive_no: 'JY-2020-001' },
  { id: 2, name: '实验楼B座', type: 'teaching', area: 15600, floors: 8, acceptance_date: '2019-09-01', responsible_person: '李明华', archive_no: 'JY-2019-002' },
  { id: 3, name: '学生宿舍C区', type: 'dormitory', area: 32000, floors: 12, acceptance_date: '2021-03-20', responsible_person: '王大伟', archive_no: 'JY-2021-003' },
  { id: 4, name: '图书馆D馆', type: 'library', area: 18800, floors: 5, acceptance_date: '2018-12-10', responsible_person: '赵雪梅', archive_no: 'JY-2018-004' },
  { id: 5, name: '学生第一食堂', type: 'canteen', area: 6500, floors: 2, acceptance_date: '2020-08-25', responsible_person: '刘志强', archive_no: 'JY-2020-005' },
  { id: 6, name: '地下车库B1层', type: 'garage', area: 12000, floors: 1, acceptance_date: '2020-06-15', responsible_person: '陈卫东', archive_no: 'JY-2020-006' },
  { id: 7, name: '体育馆E馆', type: 'teaching', area: 9800, floors: 3, acceptance_date: '2022-05-18', responsible_person: '孙海涛', archive_no: 'JY-2022-007' },
  { id: 8, name: '行政办公楼F座', type: 'office', area: 12500, floors: 10, acceptance_date: '2017-11-30', responsible_person: '周建国', archive_no: 'JY-2017-008' },
])

const facilities = ref([
  { id: 1, facility_name: '火灾自动报警系统-1#主机', type: 'fire_alarm', spec_model: 'JB-QB-GST200', install_location: '综合办公楼A座消防控制室', install_date: '2020-05-10', maintenance_company: '永安消防维保有限公司', status: 'normal' },
  { id: 2, facility_name: '自动喷水灭火系统-喷淋泵', type: 'sprinkler', spec_model: 'XBD8/30-HY', install_location: '综合办公楼A座地下室泵房', install_date: '2020-05-15', maintenance_company: '永安消防维保有限公司', status: 'normal' },
  { id: 3, facility_name: '室内消火栓系统-消防泵', type: 'hydrant', spec_model: 'XBD10/40-HY', install_location: '实验楼B座地下室泵房', install_date: '2019-08-20', maintenance_company: '中信消防技术服务公司', status: 'normal' },
  { id: 4, facility_name: '机械排烟系统-风机', type: 'ventilation', spec_model: 'HTF-I-12', install_location: '学生宿舍C区屋顶', install_date: '2021-02-28', maintenance_company: '永安消防维保有限公司', status: 'pending' },
  { id: 5, facility_name: '防火卷帘门-东出口', type: 'fire_separation', spec_model: 'FJM3000×3000', install_location: '实验楼B座1层东出口', install_date: '2019-08-15', maintenance_company: '安恒消防设备公司', status: 'normal' },
  { id: 6, facility_name: '应急照明集中电源', type: 'emergency_lighting', spec_model: 'EPS-10KVA', install_location: '图书馆D馆配电间', install_date: '2018-11-20', maintenance_company: '中信消防技术服务公司', status: 'expired' },
  { id: 7, facility_name: '火灾自动报警系统-2#主机', type: 'fire_alarm', spec_model: 'JB-QB-GST5000', install_location: '图书馆D馆消防控制室', install_date: '2018-11-15', maintenance_company: '中信消防技术服务公司', status: 'normal' },
  { id: 8, facility_name: '气体灭火系统-配电室', type: 'sprinkler', spec_model: 'QMP100/2.5', install_location: '综合办公楼A座10层配电室', install_date: '2020-05-20', maintenance_company: '永安消防维保有限公司', status: 'normal' },
])

const legalDocs = ref([
  { id: 1, doc_name: '建设工程消防验收意见书', doc_no: '消验字[2020]第0125号', type: 'acceptance', issued_by: '市消防救援支队', issue_date: '2020-06-15', valid_until: '长期有效', days_left: 9999 },
  { id: 2, doc_name: '消防安全检查合格证', doc_no: '消安检字[2025]第0089号', type: 'safety_inspection', issued_by: '区消防救援大队', issue_date: '2025-03-10', valid_until: '2028-03-09', days_left: 547 },
  { id: 3, doc_name: '建设工程消防验收意见书', doc_no: '消验字[2019]第0286号', type: 'acceptance', issued_by: '市消防救援支队', issue_date: '2019-09-01', valid_until: '长期有效', days_left: 9999 },
  { id: 4, doc_name: '公众聚集场所投入使用、营业前消防安全检查合格证', doc_no: '消安检字[2026]第0032号', type: 'safety_inspection', issued_by: '区消防救援大队', issue_date: '2026-01-15', valid_until: '2029-01-14', days_left: 858 },
  { id: 5, doc_name: '建设工程消防验收意见书', doc_no: '消验字[2021]第0078号', type: 'acceptance', issued_by: '市消防救援支队', issue_date: '2021-03-20', valid_until: '长期有效', days_left: 9999 },
  { id: 6, doc_name: '消防行政处罚决定书', doc_no: '消行罚字[2025]第0056号', type: 'penalty', issued_by: '区消防救援大队', issue_date: '2025-08-20', valid_until: '2025-09-05', days_left: -369 },
  { id: 7, doc_name: '消防行政许可决定书', doc_no: '消行许字[2026]第0012号', type: 'permit', issued_by: '市消防救援支队', issue_date: '2026-04-10', valid_until: '2029-04-09', days_left: 943 },
  { id: 8, doc_name: '建设工程竣工验收消防备案凭证', doc_no: '消竣备字[2022]第0156号', type: 'record', issued_by: '市消防救援支队', issue_date: '2022-05-18', valid_until: '长期有效', days_left: 9999 },
])

const drawings = ref([
  { id: 1, drawing_name: '综合办公楼A座-1层消防平面图', type: 'floor_plan', building_name: '综合办公楼A座', version: 'V3.2', update_date: '2025-11-20' },
  { id: 2, drawing_name: '综合办公楼A座-火灾自动报警系统图', type: 'system_diagram', building_name: '综合办公楼A座', version: 'V2.1', update_date: '2024-06-15' },
  { id: 3, drawing_name: '实验楼B座-消防设施布置图', type: 'layout', building_name: '实验楼B座', version: 'V1.5', update_date: '2023-08-10' },
  { id: 4, drawing_name: '学生宿舍C区-标准层消防平面图', type: 'floor_plan', building_name: '学生宿舍C区', version: 'V4.0', update_date: '2026-02-28' },
  { id: 5, drawing_name: '图书馆D馆-自动喷水灭火系统图', type: 'system_diagram', building_name: '图书馆D馆', version: 'V2.0', update_date: '2025-04-18' },
  { id: 6, drawing_name: '地下车库B1层-消防设施布置图', type: 'layout', building_name: '地下车库B1层', version: 'V3.1', update_date: '2025-09-05' },
  { id: 7, drawing_name: '体育馆E馆-消防总平面图', type: 'floor_plan', building_name: '体育馆E馆', version: 'V1.0', update_date: '2022-05-18' },
  { id: 8, drawing_name: '行政办公楼F座-防排烟系统图', type: 'system_diagram', building_name: '行政办公楼F座', version: 'V2.3', update_date: '2024-12-10' },
])

const filteredBuildings = computed(() => {
  let list = buildings.value
  if (buildingSearch.value) {
    list = list.filter(b => b.name.includes(buildingSearch.value) || b.archive_no.includes(buildingSearch.value))
  }
  if (buildingTypeFilter.value) {
    list = list.filter(b => b.type === buildingTypeFilter.value)
  }
  return list
})

const filteredFacilities = computed(() => {
  let list = facilities.value
  if (facilitySearch.value) {
    list = list.filter(f => f.facility_name.includes(facilitySearch.value) || f.spec_model.includes(facilitySearch.value))
  }
  if (facilityTypeFilter.value) {
    list = list.filter(f => f.type === facilityTypeFilter.value)
  }
  if (facilityStatusFilter.value) {
    list = list.filter(f => f.status === facilityStatusFilter.value)
  }
  return list
})

const filteredLegalDocs = computed(() => {
  let list = legalDocs.value
  if (legalSearch.value) {
    list = list.filter(l => l.doc_name.includes(legalSearch.value) || l.doc_no.includes(legalSearch.value))
  }
  if (legalTypeFilter.value) {
    list = list.filter(l => l.type === legalTypeFilter.value)
  }
  return list
})

const filteredDrawings = computed(() => {
  let list = drawings.value
  if (drawingSearch.value) {
    list = list.filter(d => d.drawing_name.includes(drawingSearch.value))
  }
  if (drawingTypeFilter.value) {
    list = list.filter(d => d.type === drawingTypeFilter.value)
  }
  return list
})

function buildingTypeText(type) {
  const map = { office: '办公楼', teaching: '教学楼', dormitory: '宿舍楼', library: '图书馆', canteen: '食堂', garage: '车库' }
  return map[type] || '其他'
}

function buildingTypeTag(type) {
  const map = { office: 'primary', teaching: 'success', dormitory: 'warning', library: 'info', canteen: 'danger', garage: '' }
  return map[type] || ''
}

function facilityTypeText(type) {
  const map = { fire_alarm: '火灾自动报警系统', sprinkler: '自动喷水灭火系统', hydrant: '消火栓系统', ventilation: '防排烟系统', fire_separation: '防火分隔设施', emergency_lighting: '应急照明系统' }
  return map[type] || '其他'
}

function legalTypeText(type) {
  const map = { acceptance: '消防验收', safety_inspection: '安全检查', penalty: '行政处罚', permit: '行政许可', record: '备案凭证' }
  return map[type] || '其他'
}

function legalTypeTag(type) {
  const map = { acceptance: 'success', safety_inspection: 'primary', penalty: 'danger', permit: 'warning', record: 'info' }
  return map[type] || ''
}

function drawingTypeText(type) {
  const map = { floor_plan: '平面图', system_diagram: '系统图', layout: '布置图' }
  return map[type] || '其他'
}

function drawingTypeTag(type) {
  const map = { floor_plan: 'primary', system_diagram: 'success', layout: 'warning' }
  return map[type] || ''
}
</script>

<style scoped>
.fire-archives-page {
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

.building-card {
  margin-bottom: 16px;
}

.building-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.building-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.building-info {
  flex: 1;
  min-width: 0;
}

.building-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 4px;
}

.building-detail {
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

.building-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
