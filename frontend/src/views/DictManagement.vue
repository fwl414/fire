<template>
  <div class="dict-page">
    <div class="title-row">
      <div>
        <div class="page-title">数据字典管理</div>
        <p class="subtitle">系统字典配置 · 枚举值管理 · 业务参数配置</p>
      </div>
    </div>

    <el-row :gutter="14">
      <el-col :xs="24" :sm="24" :md="8" :lg="6">
        <el-card class="tree-card" shadow="never">
          <div class="tree-header">
            <div class="tree-title">
              <el-icon><Setting /></el-icon>
              字典类型
            </div>
            <el-button type="primary" size="small" @click="showTypeForm = true">
              <el-icon><Plus /></el-icon>
              新增
            </el-button>
          </div>
          <div class="tree-search">
            <el-input v-model="typeSearch" placeholder="搜索字典类型" clearable size="default">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
          <el-tree
            ref="treeRef"
            :data="dictTypeTree"
            :props="treeProps"
            :filter-node-method="filterNode"
            node-key="id"
            default-expand-all
            highlight-current
            @node-click="handleNodeClick"
            class="dict-tree"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <el-icon class="node-icon"><Folder v-if="data.children && data.children.length" /><Document v-else /></el-icon>
                <span class="node-label">{{ node.label }}</span>
                <span class="node-count" v-if="data.itemCount !== undefined">({{ data.itemCount }})</span>
              </div>
            </template>
          </el-tree>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="24" :md="16" :lg="18">
        <el-row :gutter="14" class="stats-row">
          <el-col :xs="8" :sm="8" :md="8" :lg="8">
            <el-card class="stat-card" shadow="never">
              <div class="stat-icon blue"><el-icon><Document /></el-icon></div>
              <div class="stat-info">
                <div class="stat-num">{{ dictStats.total }}</div>
                <div class="stat-label">字典项数量</div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="8" :sm="8" :md="8" :lg="8">
            <el-card class="stat-card" shadow="never">
              <div class="stat-icon green"><el-icon><Check /></el-icon></div>
              <div class="stat-info">
                <div class="stat-num">{{ dictStats.enabled }}</div>
                <div class="stat-label">启用数量</div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="8" :sm="8" :md="8" :lg="8">
            <el-card class="stat-card" shadow="never">
              <div class="stat-icon orange"><el-icon><Close /></el-icon></div>
              <div class="stat-info">
                <div class="stat-num">{{ dictStats.disabled }}</div>
                <div class="stat-label">停用数量</div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card class="module-card" shadow="never">
          <div class="card-header">
            <div class="current-type">
              <span class="label">当前字典：</span>
              <el-tag type="primary" effect="plain">{{ currentTypeName }}</el-tag>
            </div>
            <div class="header-actions">
              <el-button size="small" @click="refreshData">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </div>

          <div class="table-toolbar">
            <div class="toolbar-left">
              <el-button type="primary" @click="showItemForm = true">
                <el-icon><Plus /></el-icon>
                新增字典项
              </el-button>
              <el-button @click="handleBatchEnable" :disabled="selectedItems.length === 0">
                <el-icon><Check /></el-icon>
                启用
              </el-button>
              <el-button @click="handleBatchDisable" :disabled="selectedItems.length === 0">
                <el-icon><Close /></el-icon>
                停用
              </el-button>
              <el-button type="danger" @click="handleBatchDelete" :disabled="selectedItems.length === 0">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
            <div class="toolbar-right">
              <el-input v-model="itemSearch" placeholder="搜索字典标签/键值" style="width: 220px" clearable>
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <el-button @click="exportData">
                <el-icon><Download /></el-icon>
                导出
              </el-button>
            </div>
          </div>

          <el-table
            :data="filteredDictItems"
            stripe
            style="width: 100%"
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="label" label="字典标签" min-width="140" />
            <el-table-column prop="value" label="字典键值" width="120" />
            <el-table-column label="排序" width="100" align="center">
              <template #default="{ row }">
                <div class="sort-cell">
                  <el-icon><Sort /></el-icon>
                  <span>{{ row.sort }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="dark" :type="row.status === 'enabled' ? 'success' : 'info'">
                  {{ row.status === 'enabled' ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
            <el-table-column prop="create_time" label="创建时间" width="170" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="editItem(row)">编辑</el-button>
                <el-button link :type="row.status === 'enabled' ? 'warning' : 'success'" @click="toggleStatus(row)">
                  {{ row.status === 'enabled' ? '停用' : '启用' }}
                </el-button>
                <el-button link type="danger" @click="deleteItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showTypeForm" :title="typeFormTitle" width="500px">
      <el-form :model="typeForm" label-width="100px" :rules="typeFormRules" ref="typeFormRef">
        <el-form-item label="字典名称" prop="name">
          <el-input v-model="typeForm.name" placeholder="请输入字典名称" />
        </el-form-item>
        <el-form-item label="字典编码" prop="code">
          <el-input v-model="typeForm.code" placeholder="请输入字典编码（英文）" />
        </el-form-item>
        <el-form-item label="字典描述">
          <el-input v-model="typeForm.remark" type="textarea" :rows="3" placeholder="请输入字典描述" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="typeForm.status">
            <el-radio value="enabled">启用</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTypeForm = false">取消</el-button>
        <el-button type="primary" @click="submitTypeForm">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showItemForm" :title="itemFormTitle" width="550px">
      <el-form :model="itemForm" label-width="100px" :rules="itemFormRules" ref="itemFormRef">
        <el-form-item label="字典标签" prop="label">
          <el-input v-model="itemForm.label" placeholder="请输入字典标签" />
        </el-form-item>
        <el-form-item label="字典键值" prop="value">
          <el-input v-model="itemForm.value" placeholder="请输入字典键值" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="itemForm.sort" :min="0" :max="999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="itemForm.status">
            <el-radio value="enabled">启用</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="itemForm.remark" type="textarea" :rows="3" placeholder="请输入备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showItemForm = false">取消</el-button>
        <el-button type="primary" @click="submitItemForm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Setting, Plus, Search, Edit, Delete, Download, Refresh, Sort, Check, Close, Folder, Document
} from '@element-plus/icons-vue'

const treeRef = ref(null)
const typeFormRef = ref(null)
const itemFormRef = ref(null)

const typeSearch = ref('')
const itemSearch = ref('')
const currentTypeId = ref('alarm_level')
const currentTypeName = ref('告警级别')
const selectedItems = ref([])

const showTypeForm = ref(false)
const showItemForm = ref(false)
const isTypeEdit = ref(false)
const isItemEdit = ref(false)

const treeProps = {
  children: 'children',
  label: 'name'
}

const dictTypeTree = ref([
  {
    id: 'system',
    name: '系统字典',
    children: [
      { id: 'alarm_level', name: '告警级别', itemCount: 5 },
      { id: 'alarm_type', name: '告警类型', itemCount: 8 },
      { id: 'device_type', name: '设备类型', itemCount: 12 },
      { id: 'device_status', name: '设备状态', itemCount: 6 },
      { id: 'inspection_type', name: '巡检类型', itemCount: 4 },
      { id: 'hidden_danger_level', name: '隐患等级', itemCount: 4 },
      { id: 'maintenance_type', name: '维保类型', itemCount: 4 },
      { id: 'training_type', name: '培训类型', itemCount: 5 },
      { id: 'risk_level', name: '风险等级', itemCount: 4 },
    ]
  },
  {
    id: 'business',
    name: '业务字典',
    children: [
      { id: 'gender', name: '性别', itemCount: 3 },
      { id: 'position_type', name: '岗位类型', itemCount: 8 },
      { id: 'department_type', name: '部门类型', itemCount: 6 },
    ]
  }
])

const dictItemsData = ref({
  alarm_level: [
    { id: 1, label: '一级告警', value: '1', sort: 1, status: 'enabled', remark: '最严重级别，需立即处理', create_time: '2026-01-15 10:30:00' },
    { id: 2, label: '二级告警', value: '2', sort: 2, status: 'enabled', remark: '严重级别，需2小时内处理', create_time: '2026-01-15 10:30:00' },
    { id: 3, label: '三级告警', value: '3', sort: 3, status: 'enabled', remark: '一般级别，需24小时内处理', create_time: '2026-01-15 10:30:00' },
    { id: 4, label: '四级告警', value: '4', sort: 4, status: 'enabled', remark: '提示级别，可延后处理', create_time: '2026-01-15 10:30:00' },
    { id: 5, label: '五级告警', value: '5', sort: 5, status: 'disabled', remark: '预留级别', create_time: '2026-01-15 10:30:00' },
  ],
  alarm_type: [
    { id: 1, label: '火灾告警', value: 'fire', sort: 1, status: 'enabled', remark: '火灾探测器触发', create_time: '2026-01-15 11:00:00' },
    { id: 2, label: '故障告警', value: 'fault', sort: 2, status: 'enabled', remark: '设备故障告警', create_time: '2026-01-15 11:00:00' },
    { id: 3, label: '离线告警', value: 'offline', sort: 3, status: 'enabled', remark: '设备离线告警', create_time: '2026-01-15 11:00:00' },
    { id: 4, label: '水压异常', value: 'water_pressure', sort: 4, status: 'enabled', remark: '消防水压异常', create_time: '2026-01-15 11:00:00' },
    { id: 5, label: '门禁告警', value: 'access', sort: 5, status: 'enabled', remark: '门禁异常告警', create_time: '2026-01-15 11:00:00' },
    { id: 6, label: '视频遮挡', value: 'video_block', sort: 6, status: 'enabled', remark: '视频监控遮挡', create_time: '2026-01-15 11:00:00' },
    { id: 7, label: '气体泄漏', value: 'gas_leak', sort: 7, status: 'enabled', remark: '可燃气体泄漏', create_time: '2026-01-15 11:00:00' },
    { id: 8, label: '温度异常', value: 'temp_abnormal', sort: 8, status: 'disabled', remark: '环境温度异常', create_time: '2026-01-15 11:00:00' },
  ],
  device_type: [
    { id: 1, label: '烟感探测器', value: 'smoke_detector', sort: 1, status: 'enabled', remark: '烟雾火灾探测器', create_time: '2026-01-16 09:00:00' },
    { id: 2, label: '温感探测器', value: 'heat_detector', sort: 2, status: 'enabled', remark: '温度火灾探测器', create_time: '2026-01-16 09:00:00' },
    { id: 3, label: '手动报警按钮', value: 'manual_button', sort: 3, status: 'enabled', remark: '手动火灾报警按钮', create_time: '2026-01-16 09:00:00' },
    { id: 4, label: '声光报警器', value: 'sound_light_alarm', sort: 4, status: 'enabled', remark: '火灾声光警报器', create_time: '2026-01-16 09:00:00' },
    { id: 5, label: '消防水泵', value: 'fire_pump', sort: 5, status: 'enabled', remark: '消防供水泵', create_time: '2026-01-16 09:00:00' },
    { id: 6, label: '喷淋系统', value: 'sprinkler', sort: 6, status: 'enabled', remark: '自动喷水灭火系统', create_time: '2026-01-16 09:00:00' },
    { id: 7, label: '消火栓', value: 'fire_hydrant', sort: 7, status: 'enabled', remark: '室内消火栓', create_time: '2026-01-16 09:00:00' },
    { id: 8, label: '防火卷帘', value: 'fire_shutter', sort: 8, status: 'enabled', remark: '防火卷帘门', create_time: '2026-01-16 09:00:00' },
    { id: 9, label: '应急照明', value: 'emergency_light', sort: 9, status: 'enabled', remark: '消防应急照明', create_time: '2026-01-16 09:00:00' },
    { id: 10, label: '疏散指示', value: 'evacuation_sign', sort: 10, status: 'enabled', remark: '疏散指示标志', create_time: '2026-01-16 09:00:00' },
    { id: 11, label: '气体灭火', value: 'gas_extinguisher', sort: 11, status: 'enabled', remark: '气体灭火系统', create_time: '2026-01-16 09:00:00' },
    { id: 12, label: '消防电梯', value: 'fire_elevator', sort: 12, status: 'disabled', remark: '消防专用电梯', create_time: '2026-01-16 09:00:00' },
  ],
  device_status: [
    { id: 1, label: '在线', value: 'online', sort: 1, status: 'enabled', remark: '设备正常在线运行', create_time: '2026-01-16 14:00:00' },
    { id: 2, label: '离线', value: 'offline', sort: 2, status: 'enabled', remark: '设备离线', create_time: '2026-01-16 14:00:00' },
    { id: 3, label: '故障', value: 'fault', sort: 3, status: 'enabled', remark: '设备故障', create_time: '2026-01-16 14:00:00' },
    { id: 4, label: '维护中', value: 'maintenance', sort: 4, status: 'enabled', remark: '设备维护保养中', create_time: '2026-01-16 14:00:00' },
    { id: 5, label: '停用', value: 'disabled', sort: 5, status: 'enabled', remark: '设备已停用', create_time: '2026-01-16 14:00:00' },
    { id: 6, label: '待安装', value: 'pending', sort: 6, status: 'disabled', remark: '设备待安装', create_time: '2026-01-16 14:00:00' },
  ],
  inspection_type: [
    { id: 1, label: '日常巡检', value: 'daily', sort: 1, status: 'enabled', remark: '每日例行巡检', create_time: '2026-01-17 10:00:00' },
    { id: 2, label: '周检', value: 'weekly', sort: 2, status: 'enabled', remark: '每周定期检查', create_time: '2026-01-17 10:00:00' },
    { id: 3, label: '月检', value: 'monthly', sort: 3, status: 'enabled', remark: '每月全面检查', create_time: '2026-01-17 10:00:00' },
    { id: 4, label: '专项巡检', value: 'special', sort: 4, status: 'enabled', remark: '专项设施巡检', create_time: '2026-01-17 10:00:00' },
  ],
  hidden_danger_level: [
    { id: 1, label: '重大隐患', value: 'major', sort: 1, status: 'enabled', remark: '可能导致重大事故', create_time: '2026-01-17 14:30:00' },
    { id: 2, label: '较大隐患', value: 'large', sort: 2, status: 'enabled', remark: '可能导致较大事故', create_time: '2026-01-17 14:30:00' },
    { id: 3, label: '一般隐患', value: 'normal', sort: 3, status: 'enabled', remark: '一般性安全隐患', create_time: '2026-01-17 14:30:00' },
    { id: 4, label: '轻微隐患', value: 'minor', sort: 4, status: 'enabled', remark: '轻微安全问题', create_time: '2026-01-17 14:30:00' },
  ],
  maintenance_type: [
    { id: 1, label: '月度维保', value: 'monthly', sort: 1, status: 'enabled', remark: '每月例行维保', create_time: '2026-01-18 09:00:00' },
    { id: 2, label: '季度维保', value: 'quarterly', sort: 2, status: 'enabled', remark: '每季度维保', create_time: '2026-01-18 09:00:00' },
    { id: 3, label: '半年度维保', value: 'half_year', sort: 3, status: 'enabled', remark: '每半年维保', create_time: '2026-01-18 09:00:00' },
    { id: 4, label: '年度维保', value: 'yearly', sort: 4, status: 'enabled', remark: '每年全面维保', create_time: '2026-01-18 09:00:00' },
  ],
  training_type: [
    { id: 1, label: '消防知识培训', value: 'fire_knowledge', sort: 1, status: 'enabled', remark: '消防基础知识培训', create_time: '2026-01-18 14:00:00' },
    { id: 2, label: '灭火器使用培训', value: 'extinguisher_use', sort: 2, status: 'enabled', remark: '灭火器实操培训', create_time: '2026-01-18 14:00:00' },
    { id: 3, label: '疏散演练培训', value: 'evacuation_drill', sort: 3, status: 'enabled', remark: '应急疏散演练', create_time: '2026-01-18 14:00:00' },
    { id: 4, label: '设备操作培训', value: 'device_operation', sort: 4, status: 'enabled', remark: '消防设备操作培训', create_time: '2026-01-18 14:00:00' },
    { id: 5, label: '安全管理员培训', value: 'safety_manager', sort: 5, status: 'enabled', remark: '安全管理员资质培训', create_time: '2026-01-18 14:00:00' },
  ],
  risk_level: [
    { id: 1, label: '重大风险', value: 'major', sort: 1, status: 'enabled', remark: '红色风险等级', create_time: '2026-01-19 10:00:00' },
    { id: 2, label: '较大风险', value: 'large', sort: 2, status: 'enabled', remark: '橙色风险等级', create_time: '2026-01-19 10:00:00' },
    { id: 3, label: '一般风险', value: 'normal', sort: 3, status: 'enabled', remark: '黄色风险等级', create_time: '2026-01-19 10:00:00' },
    { id: 4, label: '低风险', value: 'low', sort: 4, status: 'enabled', remark: '蓝色风险等级', create_time: '2026-01-19 10:00:00' },
  ],
  gender: [
    { id: 1, label: '男', value: 'male', sort: 1, status: 'enabled', remark: '男性', create_time: '2026-01-15 08:00:00' },
    { id: 2, label: '女', value: 'female', sort: 2, status: 'enabled', remark: '女性', create_time: '2026-01-15 08:00:00' },
    { id: 3, label: '未知', value: 'unknown', sort: 3, status: 'disabled', remark: '性别未知', create_time: '2026-01-15 08:00:00' },
  ],
  position_type: [
    { id: 1, label: '系统管理员', value: 'admin', sort: 1, status: 'enabled', remark: '系统最高权限管理员', create_time: '2026-01-15 09:30:00' },
    { id: 2, label: '安全主管', value: 'safety_manager', sort: 2, status: 'enabled', remark: '安全管理部门负责人', create_time: '2026-01-15 09:30:00' },
    { id: 3, label: '消防专员', value: 'fire_specialist', sort: 3, status: 'enabled', remark: '消防专职人员', create_time: '2026-01-15 09:30:00' },
    { id: 4, label: '维保工程师', value: 'maintenance_engineer', sort: 4, status: 'enabled', remark: '设备维保工程师', create_time: '2026-01-15 09:30:00' },
    { id: 5, label: '巡检员', value: 'inspector', sort: 5, status: 'enabled', remark: '日常巡检人员', create_time: '2026-01-15 09:30:00' },
    { id: 6, label: '监控值班员', value: 'monitor_operator', sort: 6, status: 'enabled', remark: '监控中心值班人员', create_time: '2026-01-15 09:30:00' },
    { id: 7, label: '培训讲师', value: 'trainer', sort: 7, status: 'enabled', remark: '消防安全培训讲师', create_time: '2026-01-15 09:30:00' },
    { id: 8, label: '普通用户', value: 'user', sort: 8, status: 'enabled', remark: '普通员工用户', create_time: '2026-01-15 09:30:00' },
  ],
  department_type: [
    { id: 1, label: '安全管理部', value: 'safety_dept', sort: 1, status: 'enabled', remark: '负责消防安全管理', create_time: '2026-01-15 10:00:00' },
    { id: 2, label: '技术保障部', value: 'tech_dept', sort: 2, status: 'enabled', remark: '负责设备技术维护', create_time: '2026-01-15 10:00:00' },
    { id: 3, label: '监控中心', value: 'monitor_center', sort: 3, status: 'enabled', remark: '24小时监控值班', create_time: '2026-01-15 10:00:00' },
    { id: 4, label: '培训部', value: 'training_dept', sort: 4, status: 'enabled', remark: '负责消防培训', create_time: '2026-01-15 10:00:00' },
    { id: 5, label: '综合办公室', value: 'admin_office', sort: 5, status: 'enabled', remark: '行政综合管理', create_time: '2026-01-15 10:00:00' },
    { id: 6, label: '财务部', value: 'finance_dept', sort: 6, status: 'disabled', remark: '财务管理部门', create_time: '2026-01-15 10:00:00' },
  ],
})

const dictStats = computed(() => {
  const items = dictItemsData.value[currentTypeId.value] || []
  const total = items.length
  const enabled = items.filter(i => i.status === 'enabled').length
  const disabled = items.filter(i => i.status === 'disabled').length
  return { total, enabled, disabled }
})

const filteredDictItems = computed(() => {
  const items = dictItemsData.value[currentTypeId.value] || []
  if (!itemSearch.value) return items
  return items.filter(item =>
    item.label.includes(itemSearch.value) ||
    item.value.includes(itemSearch.value)
  )
})

const typeFormTitle = computed(() => isTypeEdit.value ? '编辑字典类型' : '新增字典类型')
const itemFormTitle = computed(() => isItemEdit.value ? '编辑字典项' : '新增字典项')

const typeForm = ref({
  id: '',
  name: '',
  code: '',
  remark: '',
  status: 'enabled'
})

const itemForm = ref({
  id: null,
  label: '',
  value: '',
  sort: 0,
  status: 'enabled',
  remark: ''
})

const typeFormRules = {
  name: [{ required: true, message: '请输入字典名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入字典编码', trigger: 'blur' }],
}

const itemFormRules = {
  label: [{ required: true, message: '请输入字典标签', trigger: 'blur' }],
  value: [{ required: true, message: '请输入字典键值', trigger: 'blur' }],
}

function filterNode(value, data) {
  if (!value) return true
  return data.name.includes(value)
}

watch(typeSearch, (val) => {
  treeRef.value.filter(val)
})

function handleNodeClick(data) {
  if (data.children && data.children.length) return
  currentTypeId.value = data.id
  currentTypeName.value = data.name
  selectedItems.value = []
}

function handleSelectionChange(selection) {
  selectedItems.value = selection
}

function editItem(row) {
  isItemEdit.value = true
  itemForm.value = { ...row }
  showItemForm.value = true
}

function toggleStatus(row) {
  const newStatus = row.status === 'enabled' ? 'disabled' : 'enabled'
  ElMessageBox.confirm(
    `确定要${newStatus === 'enabled' ? '启用' : '停用'}该字典项吗？`,
    '提示',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(() => {
    row.status = newStatus
    ElMessage.success(`字典项已${newStatus === 'enabled' ? '启用' : '停用'}`)
  }).catch(() => {})
}

function deleteItem(row) {
  ElMessageBox.confirm('确定要删除该字典项吗？删除后不可恢复。', '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'error'
  }).then(() => {
    const list = dictItemsData.value[currentTypeId.value]
    const index = list.findIndex(i => i.id === row.id)
    if (index > -1) {
      list.splice(index, 1)
    }
    ElMessage.success('删除成功')
  }).catch(() => {})
}

function handleBatchEnable() {
  ElMessageBox.confirm(`确定要启用选中的 ${selectedItems.value.length} 项吗？`, '提示', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
  }).then(() => {
    selectedItems.value.forEach(item => {
      item.status = 'enabled'
    })
    ElMessage.success('批量启用成功')
  }).catch(() => {})
}

function handleBatchDisable() {
  ElMessageBox.confirm(`确定要停用选中的 ${selectedItems.value.length} 项吗？`, '提示', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
  }).then(() => {
    selectedItems.value.forEach(item => {
      item.status = 'disabled'
    })
    ElMessage.success('批量停用成功')
  }).catch(() => {})
}

function handleBatchDelete() {
  ElMessageBox.confirm(`确定要删除选中的 ${selectedItems.value.length} 项吗？删除后不可恢复。`, '删除确认', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'error'
  }).then(() => {
    const list = dictItemsData.value[currentTypeId.value]
    selectedItems.value.forEach(item => {
      const index = list.findIndex(i => i.id === item.id)
      if (index > -1) list.splice(index, 1)
    })
    selectedItems.value = []
    ElMessage.success('批量删除成功')
  }).catch(() => {})
}

function refreshData() {
  ElMessage.success('数据已刷新')
}

function exportData() {
  ElMessage.success('正在导出字典数据...')
}

function submitTypeForm() {
  typeFormRef.value.validate((valid) => {
    if (valid) {
      ElMessage.success(isTypeEdit.value ? '字典类型编辑成功' : '字典类型新增成功')
      showTypeForm.value = false
    }
  })
}

function submitItemForm() {
  itemFormRef.value.validate((valid) => {
    if (valid) {
      if (isItemEdit.value) {
        const list = dictItemsData.value[currentTypeId.value]
        const index = list.findIndex(i => i.id === itemForm.value.id)
        if (index > -1) {
          list[index] = { ...itemForm.value }
        }
        ElMessage.success('字典项编辑成功')
      } else {
        const list = dictItemsData.value[currentTypeId.value]
        const maxId = list.length > 0 ? Math.max(...list.map(i => i.id)) : 0
        list.push({
          ...itemForm.value,
          id: maxId + 1,
          create_time: new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
        })
        ElMessage.success('字典项新增成功')
      }
      showItemForm.value = false
    }
  })
}

onMounted(() => {
  watch(showTypeForm, (val) => {
    if (!val) {
      isTypeEdit.value = false
      typeForm.value = { id: '', name: '', code: '', remark: '', status: 'enabled' }
    }
  })
  watch(showItemForm, (val) => {
    if (!val) {
      isItemEdit.value = false
      itemForm.value = { id: null, label: '', value: '', sort: 0, status: 'enabled', remark: '' }
    }
  })
})
</script>

<style scoped>
.dict-page {
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

.tree-card {
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.tree-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
}

.tree-search {
  margin-bottom: 12px;
}

.dict-tree {
  flex: 1;
  overflow-y: auto;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.node-icon {
  color: #60a5fa;
  font-size: 14px;
}

.node-label {
  flex: 1;
}

.node-count {
  color: #94a3b8;
  font-size: 12px;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.current-type {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-type .label {
  color: #64748b;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 8px;
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

.sort-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #64748b;
}
</style>
