<template>
  <div class="role-management">
    <div class="page-header">
      <h2>角色与权限管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增角色</el-button>
    </div>

    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="搜索角色名称/编码" style="width: 240px" clearable @keyup.enter="loadData" />
      <el-button @click="loadData">查询</el-button>
    </div>

    <el-table :data="tableData" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="role_code" label="角色编码" width="140" />
      <el-table-column prop="role_name" label="角色名称" width="140" />
      <el-table-column prop="description" label="描述" min-width="200" />
      <el-table-column label="权限数量" width="100">
        <template #default="{ row }">
          <el-tag type="info">{{ row.permissions?.length || 0 }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="系统内置" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_system ? 'warning' : 'info'">
            {{ row.is_system ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" type="primary" @click="openPermissionDialog(row)">权限配置</el-button>
          <el-button size="small" type="danger" @click="deleteRole(row)" :disabled="row.is_system">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadData"
        @size-change="loadData"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新增角色'" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="角色编码">
          <el-input v-model="form.role_code" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="角色名称">
          <el-input v-model="form.role_name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="permDialogVisible" title="权限配置" width="640px">
      <div class="perm-header">
        <span>角色：<strong>{{ currentRole?.role_name }}</strong></span>
        <el-checkbox v-model="selectAll" :indeterminate="isIndeterminate" @change="handleSelectAll">
          全选
        </el-checkbox>
      </div>
      <div class="perm-groups">
        <div v-for="group in permissionGroups" :key="group.group" class="perm-group">
          <div class="group-title">
            <el-checkbox v-model="group.checked" :indeterminate="group.indeterminate" @change="handleGroupChange(group)">
              {{ group.group }}
            </el-checkbox>
          </div>
          <div class="group-items">
            <el-checkbox v-for="item in group.items" :key="item.code" v-model="item.checked" @change="handleItemChange(group, item)">
              {{ item.name }}
            </el-checkbox>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPermissions" :loading="submitting">保存配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { roleList, roleCreate, roleUpdate, roleDelete, permissionList } from '../api'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const total = ref(0)
const permissionGroups = ref([])
const currentRole = ref(null)

const filters = reactive({
  keyword: '',
  page: 1,
  page_size: 20,
})

const dialogVisible = ref(false)
const permDialogVisible = ref(false)
const isEdit = ref(false)
const form = reactive({
  id: 0,
  role_code: '',
  role_name: '',
  description: '',
  permissions: [],
})

const selectAll = ref(false)

const isIndeterminate = computed(() => {
  const allItems = permissionGroups.value.flatMap(g => g.items)
  const checkedCount = allItems.filter(i => i.checked).length
  return checkedCount > 0 && checkedCount < allItems.length
})

async function loadData() {
  loading.value = true
  try {
    const res = await roleList(filters)
    tableData.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('加载角色列表失败', e)
  } finally {
    loading.value = false
  }
}

async function loadPermissions() {
  try {
    const res = await permissionList()
    const groups = res.data.groups || []
    permissionGroups.value = groups.map(g => ({
      group: g.group,
      checked: false,
      indeterminate: false,
      items: g.items.map(i => ({ ...i, checked: false }))
    }))
  } catch (e) {
    console.error('加载权限清单失败', e)
  }
}

function openCreateDialog() {
  isEdit.value = false
  Object.assign(form, {
    id: 0,
    role_code: '',
    role_name: '',
    description: '',
    permissions: [],
  })
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    role_code: row.role_code,
    role_name: row.role_name,
    description: row.description,
    permissions: row.permissions || [],
  })
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.role_code) return ElMessage.warning('请输入角色编码')
  if (!form.role_name) return ElMessage.warning('请输入角色名称')

  submitting.value = true
  try {
    if (isEdit.value) {
      const res = await roleUpdate(form.id, {
        role_name: form.role_name,
        description: form.description,
      })
      if (res.data.ok) {
        ElMessage.success('更新成功')
        dialogVisible.value = false
        loadData()
      }
    } else {
      const res = await roleCreate({
        role_code: form.role_code,
        role_name: form.role_name,
        description: form.description,
        permissions: [],
      })
      if (res.data.ok) {
        ElMessage.success('创建成功')
        dialogVisible.value = false
        loadData()
      }
    }
  } catch (e) {
    console.error('提交失败', e)
  } finally {
    submitting.value = false
  }
}

function openPermissionDialog(row) {
  currentRole.value = row
  const perms = row.permissions || []
  permissionGroups.value.forEach(g => {
    g.items.forEach(i => {
      i.checked = perms.includes(i.code) || perms.includes('*')
    })
    updateGroupState(g)
  })
  updateSelectAllState()
  permDialogVisible.value = true
}

function updateGroupState(group) {
  const total = group.items.length
  const checked = group.items.filter(i => i.checked).length
  group.checked = checked === total && total > 0
  group.indeterminate = checked > 0 && checked < total
}

function updateSelectAllState() {
  const allItems = permissionGroups.value.flatMap(g => g.items)
  const total = allItems.length
  const checked = allItems.filter(i => i.checked).length
  selectAll.value = checked === total && total > 0
}

function handleSelectAll(val) {
  permissionGroups.value.forEach(g => {
    g.items.forEach(i => { i.checked = val })
    g.checked = val
    g.indeterminate = false
  })
}

function handleGroupChange(group) {
  group.items.forEach(i => { i.checked = group.checked })
  group.indeterminate = false
  updateSelectAllState()
}

function handleItemChange(group, item) {
  updateGroupState(group)
  updateSelectAllState()
}

async function submitPermissions() {
  if (!currentRole.value) return

  const checkedPerms = []
  permissionGroups.value.forEach(g => {
    g.items.forEach(i => {
      if (i.checked) checkedPerms.push(i.code)
    })
  })

  submitting.value = true
  try {
    const res = await roleUpdate(currentRole.value.id, {
      permissions: checkedPerms,
    })
    if (res.data.ok) {
      ElMessage.success('权限配置保存成功')
      permDialogVisible.value = false
      loadData()
    }
  } catch (e) {
    console.error('保存权限失败', e)
  } finally {
    submitting.value = false
  }
}

async function deleteRole(row) {
  try {
    await ElMessageBox.confirm(`确定要删除角色 ${row.role_name} 吗？`, '提示', { type: 'warning' })
    const res = await roleDelete(row.id)
    if (res.data.ok) {
      ElMessage.success('删除成功')
      loadData()
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除失败', e)
    }
  }
}

onMounted(() => {
  loadData()
  loadPermissions()
})
</script>

<style scoped>
.role-management { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }

.perm-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #eee; }
.perm-groups { max-height: 400px; overflow-y: auto; }
.perm-group { margin-bottom: 16px; }
.group-title { margin-bottom: 8px; font-weight: 600; }
.group-items { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding-left: 24px; }
</style>
