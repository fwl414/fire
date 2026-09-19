<template>
  <div class="org-management-page">
    <div class="title-row">
      <div>
        <div class="page-title">组织架构管理</div>
        <p class="subtitle">部门管理 · 岗位管理 · 人员管理</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.departments }}</div>
            <div class="stat-label">部门数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.employees }}</div>
            <div class="stat-label">在职员工</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><UserFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.positions }}</div>
            <div class="stat-label">岗位数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><Setting /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.leaders }}</div>
            <div class="stat-label">管理层</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'dept' }" @click="activeTab = 'dept'">
          <el-icon><OfficeBuilding /></el-icon>
          部门结构
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'personnel' }" @click="activeTab = 'personnel'">
          <el-icon><User /></el-icon>
          人员列表
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'position' }" @click="activeTab = 'position'">
          <el-icon><UserFilled /></el-icon>
          岗位管理
        </div>
      </div>

      <div v-if="activeTab === 'dept'" class="tab-content">
        <div class="dept-layout">
          <div class="dept-tree-panel">
            <div class="panel-header">
              <span class="panel-title">组织架构</span>
              <el-button type="primary" size="small" @click="showDeptForm = true; deptFormData = { name: '', code: '', type: 'department', parent_id: null, manager: '', phone: '', description: '', sort: 1 }">
                <el-icon><Plus /></el-icon>
                新增部门
              </el-button>
            </div>
            <el-input v-model="deptTreeSearch" placeholder="搜索部门" size="small" clearable style="margin-bottom: 12px">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-tree
              :data="deptTree"
              :props="{ label: 'name', children: 'children' }"
              node-key="id"
              default-expand-all
              highlight-current
              :expand-on-click-node="false"
              @node-click="handleDeptNodeClick"
              ref="deptTreeRef"
            >
              <template #default="{ node, data }">
                <div class="tree-node">
                  <span class="node-label">{{ data.name }}</span>
                  <span class="node-count">({{ data.count || 0 }})</span>
                </div>
              </template>
            </el-tree>
          </div>
          <div class="dept-detail-panel">
            <div class="panel-header">
              <span class="panel-title">部门详情</span>
              <div class="panel-actions">
                <el-button size="small" @click="handleDeptEdit(currentDept)">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-button>
                <el-button size="small" type="danger" @click="handleDeptDelete(currentDept)">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </div>
            </div>
            <div v-if="currentDept" class="dept-detail">
              <div class="dept-main-info">
                <div class="dept-logo">{{ currentDept.name.charAt(0) }}</div>
                <div class="dept-info">
                  <div class="dept-name">{{ currentDept.name }}</div>
                  <div class="dept-code">编码：{{ currentDept.code }}</div>
                </div>
                <el-tag :type="currentDept.type === 'company' ? 'primary' : currentDept.type === 'department' ? 'success' : 'warning'" size="small">
                  {{ currentDept.type === 'company' ? '公司' : currentDept.type === 'department' ? '部门' : '班组' }}
                </el-tag>
              </div>
              <el-descriptions :column="2" border size="default" style="margin-top: 16px">
                <el-descriptions-item label="部门负责人">{{ currentDept.manager || '未设置' }}</el-descriptions-item>
                <el-descriptions-item label="联系电话">{{ currentDept.phone || '未设置' }}</el-descriptions-item>
                <el-descriptions-item label="人员数量">{{ currentDept.count || 0 }} 人</el-descriptions-item>
                <el-descriptions-item label="排序">{{ currentDept.sort }}</el-descriptions-item>
                <el-descriptions-item label="部门描述" :span="2">{{ currentDept.description || '暂无描述' }}</el-descriptions-item>
              </el-descriptions>

              <div class="sub-dept-section">
                <div class="section-header">
                  <span class="section-title">子部门 / 班组</span>
                  <el-button type="primary" size="small" @click="handleAddSubDept(currentDept)">
                    <el-icon><Plus /></el-icon>
                    新增子部门
                  </el-button>
                </div>
                <el-table :data="currentSubDepts" stripe style="width: 100%" size="default">
                  <el-table-column prop="name" label="部门名称" min-width="160" />
                  <el-table-column prop="code" label="部门编码" width="140" />
                  <el-table-column label="类型" width="100">
                    <template #default="{ row }">
                      <el-tag size="small" :type="row.type === 'department' ? 'success' : 'warning'">
                        {{ row.type === 'department' ? '部门' : '班组' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="manager" label="负责人" width="100" />
                  <el-table-column prop="count" label="人数" width="80" align="center" />
                  <el-table-column prop="sort" label="排序" width="80" align="center" />
                  <el-table-column label="操作" width="160" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="primary" size="small" @click="handleDeptEdit(row)">编辑</el-button>
                      <el-button link type="danger" size="small" @click="handleDeptDelete(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
            <el-empty v-else description="请选择左侧部门查看详情" />
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'personnel'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showEmployeeForm = true; employeeFormData = { name: '', emp_no: '', dept_id: '', position_id: '', phone: '', email: '', entry_date: '', status: 'active' }">
              <el-icon><Plus /></el-icon>
              新增人员
            </el-button>
            <el-button type="success" @click="handleImport">
              <el-icon><Upload /></el-icon>
              批量导入
            </el-button>
            <el-button @click="handleExport">
              <el-icon><Download /></el-icon>
              批量导出
            </el-button>
            <el-select v-model="personnelDeptFilter" placeholder="部门筛选" clearable style="width: 160px">
              <el-option label="全部部门" value="" />
              <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-select v-model="personnelStatusFilter" placeholder="人员状态" clearable style="width: 140px">
              <el-option label="在职" value="active" />
              <el-option label="离职" value="resigned" />
              <el-option label="休假" value="vacation" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button @click="refreshPersonnel">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-input v-model="personnelSearch" placeholder="搜索姓名/工号" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredPersonnel" stripe style="width: 100%">
          <el-table-column type="selection" width="50" />
          <el-table-column prop="emp_no" label="工号" width="120" />
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column prop="dept_name" label="部门" width="140" />
          <el-table-column prop="position_name" label="岗位" width="140" />
          <el-table-column prop="phone" label="手机号" width="140" />
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="entry_date" label="入职日期" width="120" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'active' ? 'success' : row.status === 'vacation' ? 'warning' : 'info'">
                {{ row.status === 'active' ? '在职' : row.status === 'vacation' ? '休假' : '离职' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small">查看</el-button>
              <el-button link type="warning" size="small" @click="handleEmployeeEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="handleEmployeeDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'position'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" @click="showPositionForm = true; positionFormData = { name: '', code: '', dept_id: '', type: '', sort: 1, status: 'active', description: '' }">
              <el-icon><Plus /></el-icon>
              新增岗位
            </el-button>
            <el-select v-model="positionDeptFilter" placeholder="所属部门" clearable style="width: 160px">
              <el-option label="全部部门" value="" />
              <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-select v-model="positionTypeFilter" placeholder="岗位类型" clearable style="width: 140px">
              <el-option label="管理岗" value="management" />
              <el-option label="技术岗" value="technical" />
              <el-option label="操作岗" value="operation" />
              <el-option label="支持岗" value="support" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button @click="refreshPositions">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-input v-model="positionSearch" placeholder="搜索岗位名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-table :data="filteredPositions" stripe style="width: 100%">
          <el-table-column prop="name" label="岗位名称" min-width="160" />
          <el-table-column prop="code" label="岗位编码" width="140" />
          <el-table-column prop="dept_name" label="所属部门" width="160" />
          <el-table-column label="岗位类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="positionTypeTag(row.type)">
                {{ positionTypeText(row.type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="head_count" label="人数" width="80" align="center" />
          <el-table-column prop="sort" label="排序" width="80" align="center" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.status === 'active' ? 'success' : 'info'">
                {{ row.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small">查看</el-button>
              <el-button link type="warning" size="small" @click="handlePositionEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="handlePositionDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="showDeptForm" :title="deptFormTitle" width="560px">
      <el-form :model="deptFormData" label-width="100px" ref="deptFormRef">
        <el-form-item label="部门名称" required>
          <el-input v-model="deptFormData.name" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="部门编码" required>
          <el-input v-model="deptFormData.code" placeholder="请输入部门编码" />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-tree-select v-model="deptFormData.parent_id" :data="deptTree" :props="{ label: 'name', value: 'id', children: 'children' }" check-strictly placeholder="请选择上级部门" style="width: 100%" :render-after-expand="false" />
        </el-form-item>
        <el-form-item label="部门类型">
          <el-select v-model="deptFormData.type" style="width: 100%">
            <el-option label="公司" value="company" />
            <el-option label="部门" value="department" />
            <el-option label="班组" value="team" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门负责人">
          <el-input v-model="deptFormData.manager" placeholder="请输入负责人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="deptFormData.phone" placeholder="请输入联系电话" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="deptFormData.sort" :min="1" :max="999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="部门描述">
          <el-input v-model="deptFormData.description" type="textarea" :rows="3" placeholder="请输入部门描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeptForm = false">取消</el-button>
        <el-button type="primary" @click="submitDeptForm">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEmployeeForm" :title="employeeFormTitle" width="600px">
      <el-form :model="employeeFormData" label-width="100px">
        <el-form-item label="姓名" required>
          <el-input v-model="employeeFormData.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="工号" required>
          <el-input v-model="employeeFormData.emp_no" placeholder="请输入工号" />
        </el-form-item>
        <el-form-item label="所属部门" required>
          <el-tree-select v-model="employeeFormData.dept_id" :data="deptTree" :props="{ label: 'name', value: 'id', children: 'children' }" check-strictly placeholder="请选择部门" style="width: 100%" :render-after-expand="false" />
        </el-form-item>
        <el-form-item label="岗位">
          <el-select v-model="employeeFormData.position_id" placeholder="请选择岗位" style="width: 100%">
            <el-option v-for="p in positions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="employeeFormData.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="employeeFormData.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="入职日期">
          <el-date-picker v-model="employeeFormData.entry_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="employeeFormData.status" style="width: 100%">
            <el-option label="在职" value="active" />
            <el-option label="休假" value="vacation" />
            <el-option label="离职" value="resigned" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEmployeeForm = false">取消</el-button>
        <el-button type="primary" @click="submitEmployeeForm">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPositionForm" :title="positionFormTitle" width="560px">
      <el-form :model="positionFormData" label-width="100px">
        <el-form-item label="岗位名称" required>
          <el-input v-model="positionFormData.name" placeholder="请输入岗位名称" />
        </el-form-item>
        <el-form-item label="岗位编码" required>
          <el-input v-model="positionFormData.code" placeholder="请输入岗位编码" />
        </el-form-item>
        <el-form-item label="所属部门" required>
          <el-tree-select v-model="positionFormData.dept_id" :data="deptTree" :props="{ label: 'name', value: 'id', children: 'children' }" check-strictly placeholder="请选择所属部门" style="width: 100%" :render-after-expand="false" />
        </el-form-item>
        <el-form-item label="岗位类型">
          <el-select v-model="positionFormData.type" placeholder="请选择岗位类型" style="width: 100%">
            <el-option label="管理岗" value="management" />
            <el-option label="技术岗" value="technical" />
            <el-option label="操作岗" value="operation" />
            <el-option label="支持岗" value="support" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="positionFormData.sort" :min="1" :max="999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="positionFormData.status" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位描述">
          <el-input v-model="positionFormData.description" type="textarea" :rows="3" placeholder="请输入岗位描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPositionForm = false">取消</el-button>
        <el-button type="primary" @click="submitPositionForm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  OfficeBuilding, User, UserFilled, Plus, Search, Edit, Delete, Download, Upload, Refresh, Setting
} from '@element-plus/icons-vue'

const activeTab = ref('dept')
const deptTreeSearch = ref('')
const currentDept = ref(null)
const deptTreeRef = ref(null)

const showDeptForm = ref(false)
const showEmployeeForm = ref(false)
const showPositionForm = ref(false)

const deptFormData = ref({})
const employeeFormData = ref({})
const positionFormData = ref({})

const isEditDept = ref(false)
const isEditEmployee = ref(false)
const isEditPosition = ref(false)

const personnelSearch = ref('')
const personnelDeptFilter = ref('')
const personnelStatusFilter = ref('')

const positionSearch = ref('')
const positionDeptFilter = ref('')
const positionTypeFilter = ref('')

const stats = ref({
  departments: 12,
  employees: 86,
  positions: 24,
  leaders: 8,
})

const deptTree = ref([
  {
    id: 1,
    name: '消防科技集团有限公司',
    code: 'FIRE-GROUP',
    type: 'company',
    manager: '张总',
    phone: '13800138000',
    count: 86,
    sort: 1,
    description: '集团总部，负责整体战略规划与运营管理',
    children: [
      {
        id: 2,
        name: '技术研发部',
        code: 'TECH-RD',
        type: 'department',
        manager: '李经理',
        phone: '13900139001',
        count: 28,
        sort: 1,
        description: '负责产品研发与技术创新',
        children: [
          { id: 21, name: '软件开发组', code: 'DEV-SOFT', type: 'team', manager: '王组长', phone: '13700137001', count: 12, sort: 1, description: '负责软件产品开发' },
          { id: 22, name: '硬件开发组', code: 'DEV-HW', type: 'team', manager: '陈组长', phone: '13700137002', count: 10, sort: 2, description: '负责硬件产品开发' },
          { id: 23, name: '测试组', code: 'DEV-TEST', type: 'team', manager: '刘组长', phone: '13700137003', count: 6, sort: 3, description: '负责产品质量测试' },
        ]
      },
      {
        id: 3,
        name: '工程运维部',
        code: 'ENG-OPS',
        type: 'department',
        manager: '赵经理',
        phone: '13900139002',
        count: 24,
        sort: 2,
        description: '负责项目实施与运维服务',
        children: [
          { id: 31, name: '项目一组', code: 'PROJ-1', type: 'team', manager: '孙组长', phone: '13700137004', count: 8, sort: 1, description: '负责华东区项目' },
          { id: 32, name: '项目二组', code: 'PROJ-2', type: 'team', manager: '周组长', phone: '13700137005', count: 8, sort: 2, description: '负责华南区项目' },
          { id: 33, name: '运维组', code: 'OPS-TEAM', type: 'team', manager: '吴组长', phone: '13700137006', count: 8, sort: 3, description: '负责系统运维支持' },
        ]
      },
      {
        id: 4,
        name: '市场营销部',
        code: 'MKT-DEPT',
        type: 'department',
        manager: '钱经理',
        phone: '13900139003',
        count: 16,
        sort: 3,
        description: '负责市场推广与销售',
        children: [
          { id: 41, name: '销售组', code: 'SALES', type: 'team', manager: '郑组长', phone: '13700137007', count: 10, sort: 1, description: '负责产品销售' },
          { id: 42, name: '市场组', code: 'MARKETING', type: 'team', manager: '冯组长', phone: '13700137008', count: 6, sort: 2, description: '负责市场推广' },
        ]
      },
      {
        id: 5,
        name: '综合管理部',
        code: 'ADMIN-DEPT',
        type: 'department',
        manager: '陈经理',
        phone: '13900139004',
        count: 12,
        sort: 4,
        description: '负责行政、人事、财务',
        children: [
          { id: 51, name: '人事组', code: 'HR-TEAM', type: 'team', manager: '褚组长', phone: '13700137009', count: 4, sort: 1, description: '负责人力资源' },
          { id: 52, name: '行政组', code: 'ADMIN-TEAM', type: 'team', manager: '卫组长', phone: '13700137010', count: 4, sort: 2, description: '负责行政管理' },
          { id: 53, name: '财务组', code: 'FIN-TEAM', type: 'team', manager: '蒋组长', phone: '13700137011', count: 4, sort: 3, description: '负责财务管理' },
        ]
      },
      {
        id: 6,
        name: '质量安全部',
        code: 'QA-DEPT',
        type: 'department',
        manager: '韩经理',
        phone: '13900139005',
        count: 6,
        sort: 5,
        description: '负责质量管理与安全监督',
        children: []
      },
    ]
  }
])

const personnel = ref([
  { id: 1, emp_no: 'EMP001', name: '张伟', dept_id: 1, dept_name: '消防科技集团', position_id: 1, position_name: '总经理', phone: '13800138001', email: 'zhangwei@fire.com', entry_date: '2018-03-15', status: 'active' },
  { id: 2, emp_no: 'EMP002', name: '李娜', dept_id: 2, dept_name: '技术研发部', position_id: 2, position_name: '技术总监', phone: '13900139001', email: 'lina@fire.com', entry_date: '2019-01-20', status: 'active' },
  { id: 3, emp_no: 'EMP003', name: '王强', dept_id: 21, dept_name: '软件开发组', position_id: 3, position_name: '高级工程师', phone: '13700137001', email: 'wangqiang@fire.com', entry_date: '2020-06-10', status: 'active' },
  { id: 4, emp_no: 'EMP004', name: '陈静', dept_id: 21, dept_name: '软件开发组', position_id: 4, position_name: '前端工程师', phone: '13700137002', email: 'chenjing@fire.com', entry_date: '2021-03-08', status: 'active' },
  { id: 5, emp_no: 'EMP005', name: '刘洋', dept_id: 21, dept_name: '软件开发组', position_id: 5, position_name: '后端工程师', phone: '13700137003', email: 'liuyang@fire.com', entry_date: '2021-07-15', status: 'vacation' },
  { id: 6, emp_no: 'EMP006', name: '杨帆', dept_id: 22, dept_name: '硬件开发组', position_id: 6, position_name: '硬件工程师', phone: '13700137004', email: 'yangfan@fire.com', entry_date: '2020-09-20', status: 'active' },
  { id: 7, emp_no: 'EMP007', name: '黄磊', dept_id: 22, dept_name: '硬件开发组', position_id: 6, position_name: '硬件工程师', phone: '13700137005', email: 'huanglei@fire.com', entry_date: '2022-02-14', status: 'active' },
  { id: 8, emp_no: 'EMP008', name: '周婷', dept_id: 23, dept_name: '测试组', position_id: 7, position_name: '测试工程师', phone: '13700137006', email: 'zhouting@fire.com', entry_date: '2021-11-01', status: 'active' },
  { id: 9, emp_no: 'EMP009', name: '吴昊', dept_id: 23, dept_name: '测试组', position_id: 7, position_name: '测试工程师', phone: '13700137007', email: 'wuhao@fire.com', entry_date: '2022-05-20', status: 'active' },
  { id: 10, emp_no: 'EMP010', name: '赵明', dept_id: 3, dept_name: '工程运维部', position_id: 8, position_name: '工程总监', phone: '13900139002', email: 'zhaoming@fire.com', entry_date: '2019-05-10', status: 'active' },
  { id: 11, emp_no: 'EMP011', name: '孙磊', dept_id: 31, dept_name: '项目一组', position_id: 9, position_name: '项目经理', phone: '13700137008', email: 'sunlei@fire.com', entry_date: '2020-04-15', status: 'active' },
  { id: 12, emp_no: 'EMP012', name: '马超', dept_id: 31, dept_name: '项目一组', position_id: 10, position_name: '运维工程师', phone: '13700137009', email: 'machao@fire.com', entry_date: '2021-08-10', status: 'active' },
  { id: 13, emp_no: 'EMP013', name: '朱琳', dept_id: 32, dept_name: '项目二组', position_id: 9, position_name: '项目经理', phone: '13700137010', email: 'zhulin@fire.com', entry_date: '2020-10-20', status: 'resigned' },
  { id: 14, emp_no: 'EMP014', name: '胡军', dept_id: 32, dept_name: '项目二组', position_id: 10, position_name: '运维工程师', phone: '13700137011', email: 'hujun@fire.com', entry_date: '2021-06-01', status: 'active' },
  { id: 15, emp_no: 'EMP015', name: '林芳', dept_id: 33, dept_name: '运维组', position_id: 10, position_name: '运维工程师', phone: '13700137012', email: 'linfang@fire.com', entry_date: '2022-03-15', status: 'active' },
  { id: 16, emp_no: 'EMP016', name: '何涛', dept_id: 33, dept_name: '运维组', position_id: 10, position_name: '运维工程师', phone: '13700137013', email: 'hetao@fire.com', entry_date: '2022-07-01', status: 'active' },
  { id: 17, emp_no: 'EMP017', name: '钱丽', dept_id: 4, dept_name: '市场营销部', position_id: 11, position_name: '销售总监', phone: '13900139003', email: 'qianli@fire.com', entry_date: '2019-08-25', status: 'active' },
  { id: 18, emp_no: 'EMP018', name: '郑伟', dept_id: 41, dept_name: '销售组', position_id: 12, position_name: '销售经理', phone: '13700137014', email: 'zhengwei@fire.com', entry_date: '2020-12-10', status: 'active' },
  { id: 19, emp_no: 'EMP019', name: '冯雪', dept_id: 41, dept_name: '销售组', position_id: 13, position_name: '销售代表', phone: '13700137015', email: 'fengxue@fire.com', entry_date: '2022-01-10', status: 'active' },
  { id: 20, emp_no: 'EMP020', name: '韩梅', dept_id: 42, dept_name: '市场组', position_id: 14, position_name: '市场专员', phone: '13700137016', email: 'hanmei@fire.com', entry_date: '2021-04-20', status: 'active' },
  { id: 21, emp_no: 'EMP021', name: '陈刚', dept_id: 5, dept_name: '综合管理部', position_id: 15, position_name: '行政总监', phone: '13900139004', email: 'chengang@fire.com', entry_date: '2019-03-01', status: 'active' },
  { id: 22, emp_no: 'EMP022', name: '褚红', dept_id: 51, dept_name: '人事组', position_id: 16, position_name: 'HR经理', phone: '13700137017', email: 'chuhong@fire.com', entry_date: '2020-07-15', status: 'active' },
  { id: 23, emp_no: 'EMP023', name: '卫青', dept_id: 52, dept_name: '行政组', position_id: 17, position_name: '行政专员', phone: '13700137018', email: 'weiqing@fire.com', entry_date: '2021-09-10', status: 'active' },
  { id: 24, emp_no: 'EMP024', name: '蒋明', dept_id: 53, dept_name: '财务组', position_id: 18, position_name: '财务主管', phone: '13700137019', email: 'jiangming@fire.com', entry_date: '2020-02-20', status: 'active' },
  { id: 25, emp_no: 'EMP025', name: '沈悦', dept_id: 6, dept_name: '质量安全部', position_id: 19, position_name: '质量经理', phone: '13900139005', email: 'shenyue@fire.com', entry_date: '2020-11-05', status: 'active' },
])

const positions = ref([
  { id: 1, name: '总经理', code: 'POS-001', dept_id: 1, dept_name: '消防科技集团', type: 'management', head_count: 1, sort: 1, status: 'active', description: '公司最高管理岗位' },
  { id: 2, name: '技术总监', code: 'POS-002', dept_id: 2, dept_name: '技术研发部', type: 'management', head_count: 1, sort: 2, status: 'active', description: '负责技术研发团队管理' },
  { id: 3, name: '高级工程师', code: 'POS-003', dept_id: 21, dept_name: '软件开发组', type: 'technical', head_count: 3, sort: 3, status: 'active', description: '高级软件开发工程师' },
  { id: 4, name: '前端工程师', code: 'POS-004', dept_id: 21, dept_name: '软件开发组', type: 'technical', head_count: 4, sort: 4, status: 'active', description: '前端开发工程师' },
  { id: 5, name: '后端工程师', code: 'POS-005', dept_id: 21, dept_name: '软件开发组', type: 'technical', head_count: 5, sort: 5, status: 'active', description: '后端开发工程师' },
  { id: 6, name: '硬件工程师', code: 'POS-006', dept_id: 22, dept_name: '硬件开发组', type: 'technical', head_count: 2, sort: 6, status: 'active', description: '硬件开发工程师' },
  { id: 7, name: '测试工程师', code: 'POS-007', dept_id: 23, dept_name: '测试组', type: 'technical', head_count: 2, sort: 7, status: 'active', description: '软件测试工程师' },
  { id: 8, name: '工程总监', code: 'POS-008', dept_id: 3, dept_name: '工程运维部', type: 'management', head_count: 1, sort: 8, status: 'active', description: '负责工程项目团队管理' },
  { id: 9, name: '项目经理', code: 'POS-009', dept_id: 31, dept_name: '项目一组', type: 'management', head_count: 2, sort: 9, status: 'active', description: '负责项目管理与协调' },
  { id: 10, name: '运维工程师', code: 'POS-010', dept_id: 33, dept_name: '运维组', type: 'operation', head_count: 4, sort: 10, status: 'active', description: '系统运维工程师' },
  { id: 11, name: '销售总监', code: 'POS-011', dept_id: 4, dept_name: '市场营销部', type: 'management', head_count: 1, sort: 11, status: 'active', description: '负责销售团队管理' },
  { id: 12, name: '销售经理', code: 'POS-012', dept_id: 41, dept_name: '销售组', type: 'management', head_count: 2, sort: 12, status: 'active', description: '销售经理' },
  { id: 13, name: '销售代表', code: 'POS-013', dept_id: 41, dept_name: '销售组', type: 'operation', head_count: 8, sort: 13, status: 'active', description: '销售代表' },
  { id: 14, name: '市场专员', code: 'POS-014', dept_id: 42, dept_name: '市场组', type: 'support', head_count: 3, sort: 14, status: 'active', description: '市场推广专员' },
  { id: 15, name: '行政总监', code: 'POS-015', dept_id: 5, dept_name: '综合管理部', type: 'management', head_count: 1, sort: 15, status: 'active', description: '负责行政管理工作' },
  { id: 16, name: 'HR经理', code: 'POS-016', dept_id: 51, dept_name: '人事组', type: 'management', head_count: 1, sort: 16, status: 'active', description: '人力资源经理' },
  { id: 17, name: '行政专员', code: 'POS-017', dept_id: 52, dept_name: '行政组', type: 'support', head_count: 2, sort: 17, status: 'active', description: '行政专员' },
  { id: 18, name: '财务主管', code: 'POS-018', dept_id: 53, dept_name: '财务组', type: 'support', head_count: 2, sort: 18, status: 'active', description: '财务主管' },
  { id: 19, name: '质量经理', code: 'POS-019', dept_id: 6, dept_name: '质量安全部', type: 'management', head_count: 1, sort: 19, status: 'active', description: '质量安全经理' },
])

const deptOptions = computed(() => {
  const result = []
  function flatten(nodes) {
    nodes.forEach(node => {
      result.push({ id: node.id, name: node.name, type: node.type })
      if (node.children && node.children.length > 0) {
        flatten(node.children)
      }
    })
  }
  flatten(deptTree.value)
  return result
})

const deptFormTitle = computed(() => isEditDept.value ? '编辑部门' : '新增部门')
const employeeFormTitle = computed(() => isEditEmployee.value ? '编辑人员' : '新增人员')
const positionFormTitle = computed(() => isEditPosition.value ? '编辑岗位' : '新增岗位')

const currentSubDepts = computed(() => {
  if (!currentDept.value) return []
  return currentDept.value.children || []
})

const filteredPersonnel = computed(() => {
  let list = personnel.value
  if (personnelSearch.value) {
    list = list.filter(p =>
      p.name.includes(personnelSearch.value) ||
      p.emp_no.includes(personnelSearch.value)
    )
  }
  if (personnelDeptFilter.value) {
    list = list.filter(p => p.dept_id === personnelDeptFilter.value)
  }
  if (personnelStatusFilter.value) {
    list = list.filter(p => p.status === personnelStatusFilter.value)
  }
  return list
})

const filteredPositions = computed(() => {
  let list = positions.value
  if (positionSearch.value) {
    list = list.filter(p =>
      p.name.includes(positionSearch.value) ||
      p.code.includes(positionSearch.value)
    )
  }
  if (positionDeptFilter.value) {
    list = list.filter(p => p.dept_id === positionDeptFilter.value)
  }
  if (positionTypeFilter.value) {
    list = list.filter(p => p.type === positionTypeFilter.value)
  }
  return list
})

function positionTypeText(type) {
  const map = { management: '管理岗', technical: '技术岗', operation: '操作岗', support: '支持岗' }
  return map[type] || '未分类'
}

function positionTypeTag(type) {
  const map = { management: 'primary', technical: 'success', operation: 'warning', support: 'info' }
  return map[type] || ''
}

function handleDeptNodeClick(data) {
  currentDept.value = data
}

function handleDeptEdit(row) {
  isEditDept.value = true
  deptFormData.value = { ...row }
  showDeptForm.value = true
}

function handleAddSubDept(parent) {
  isEditDept.value = false
  deptFormData.value = {
    name: '',
    code: '',
    type: 'team',
    parent_id: parent.id,
    manager: '',
    phone: '',
    description: '',
    sort: 1,
  }
  showDeptForm.value = true
}

function handleDeptDelete(row) {
  ElMessageBox.confirm(`确定要删除部门"${row.name}"吗？`, '删除确认', {
    type: 'warning',
  }).then(() => {
    ElMessage.success('删除成功')
  }).catch(() => {})
}

function handleEmployeeEdit(row) {
  isEditEmployee.value = true
  employeeFormData.value = { ...row }
  showEmployeeForm.value = true
}

function handleEmployeeDelete(row) {
  ElMessageBox.confirm(`确定要删除人员"${row.name}"吗？`, '删除确认', {
    type: 'warning',
  }).then(() => {
    ElMessage.success('删除成功')
  }).catch(() => {})
}

function handlePositionEdit(row) {
  isEditPosition.value = true
  positionFormData.value = { ...row }
  showPositionForm.value = true
}

function handlePositionDelete(row) {
  ElMessageBox.confirm(`确定要删除岗位"${row.name}"吗？`, '删除确认', {
    type: 'warning',
  }).then(() => {
    ElMessage.success('删除成功')
  }).catch(() => {})
}

function submitDeptForm() {
  ElMessage.success(isEditDept.value ? '部门编辑成功' : '部门创建成功')
  showDeptForm.value = false
}

function submitEmployeeForm() {
  ElMessage.success(isEditEmployee.value ? '人员编辑成功' : '人员创建成功')
  showEmployeeForm.value = false
}

function submitPositionForm() {
  ElMessage.success(isEditPosition.value ? '岗位编辑成功' : '岗位创建成功')
  showPositionForm.value = false
}

function handleImport() {
  ElMessage.success('正在打开批量导入...')
}

function handleExport() {
  ElMessage.success('正在导出人员列表...')
}

function refreshPersonnel() {
  ElMessage.success('刷新成功')
}

function refreshPositions() {
  ElMessage.success('刷新成功')
}
</script>

<style scoped>
.org-management-page {
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

.dept-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 340px);
  min-height: 500px;
}

.dept-tree-panel {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  padding-right: 16px;
  display: flex;
  flex-direction: column;
}

.dept-detail-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 2px 0;
}

.node-label {
  flex: 1;
  font-size: 13px;
}

.node-count {
  font-size: 12px;
  color: #94a3b8;
}

.dept-detail {
  flex: 1;
  overflow-y: auto;
}

.dept-main-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.dept-logo {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dept-info {
  flex: 1;
}

.dept-name {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.dept-code {
  font-size: 13px;
  color: #64748b;
}

.sub-dept-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}
</style>
