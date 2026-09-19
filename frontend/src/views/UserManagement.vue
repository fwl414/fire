<template>
  <div class="user-management">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增用户</el-button>
    </div>

    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="搜索用户名/姓名/邮箱" style="width: 240px" clearable @keyup.enter="loadData" />
      <el-select v-model="filters.role_id" placeholder="角色" style="width: 160px" clearable @change="loadData">
        <el-option v-for="r in roleOptions" :key="r.id" :label="r.role_name" :value="r.id" />
      </el-select>
      <el-select v-model="filters.status" placeholder="状态" style="width: 140px" clearable @change="loadData">
        <el-option label="启用" value="active" />
        <el-option label="禁用" value="inactive" />
      </el-select>
      <el-button @click="loadData">查询</el-button>
    </div>

    <el-table :data="tableData" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="real_name" label="姓名" width="120" />
      <el-table-column prop="role_name" label="角色" width="130" />
      <el-table-column prop="department" label="部门" width="140" />
      <el-table-column prop="email" label="邮箱" width="180" />
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
            {{ row.status === 'active' ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" width="170" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="openResetPassword(row)">重置密码</el-button>
          <el-button size="small" :type="row.status === 'active' ? 'info' : 'success'" @click="toggleStatus(row)">
            {{ row.status === 'active' ? '禁用' : '启用' }}
          </el-button>
          <el-button size="small" type="danger" @click="deleteUser(row)" :disabled="row.username === 'admin'">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_id" style="width: 100%">
            <el-option v-for="r in roleOptions" :key="r.id" :label="r.role_name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.department" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" active-value="active" inactive-value="inactive" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetPwdVisible" title="重置密码" width="400px">
      <el-form :model="resetForm" label-width="90px">
        <el-form-item label="新密码">
          <el-input v-model="resetForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="resetForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResetPassword" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userList, userCreate, userUpdate, userDelete, userResetPassword, userToggleStatus, roleAll } from '../api'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const total = ref(0)
const roleOptions = ref([])

const filters = reactive({
  keyword: '',
  role_id: 0,
  status: '',
  page: 1,
  page_size: 20,
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const form = reactive({
  id: 0,
  username: '',
  password: '',
  real_name: '',
  role_id: null,
  department: '',
  email: '',
  phone: '',
  status: 'active',
})

const resetPwdVisible = ref(false)
const resetForm = reactive({
  user_id: 0,
  new_password: '',
  confirm_password: '',
})

async function loadRoles() {
  try {
    const res = await roleAll()
    roleOptions.value = res.data.items || []
  } catch (e) {
    console.error('加载角色列表失败', e)
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = { ...filters }
    if (!params.role_id) delete params.role_id
    const res = await userList(params)
    tableData.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('加载用户列表失败', e)
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEdit.value = false
  Object.assign(form, {
    id: 0,
    username: '',
    password: '',
    real_name: '',
    role_id: roleOptions.value[0]?.id || null,
    department: '',
    email: '',
    phone: '',
    status: 'active',
  })
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    username: row.username,
    password: '',
    real_name: row.real_name,
    role_id: row.role_id,
    department: row.department,
    email: row.email,
    phone: row.phone,
    status: row.status,
  })
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.username) return ElMessage.warning('请输入用户名')
  if (!isEdit.value && !form.password) return ElMessage.warning('请输入密码')
  if (!isEdit.value && form.password.length < 6) return ElMessage.warning('密码长度不能少于6位')

  submitting.value = true
  try {
    const data = { ...form }
    if (!data.role_id) data.role_id = 0
    if (isEdit.value) {
      delete data.username
      delete data.password
      const res = await userUpdate(form.id, data)
      if (res.data.ok) {
        ElMessage.success('更新成功')
        dialogVisible.value = false
        loadData()
      }
    } else {
      const res = await userCreate(data)
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

function openResetPassword(row) {
  resetForm.user_id = row.id
  resetForm.new_password = ''
  resetForm.confirm_password = ''
  resetPwdVisible.value = true
}

async function submitResetPassword() {
  if (!resetForm.new_password) return ElMessage.warning('请输入新密码')
  if (resetForm.new_password.length < 6) return ElMessage.warning('密码长度不能少于6位')
  if (resetForm.new_password !== resetForm.confirm_password) return ElMessage.warning('两次密码输入不一致')

  submitting.value = true
  try {
    const res = await userResetPassword(resetForm.user_id, resetForm.new_password)
    if (res.data.ok) {
      ElMessage.success('密码重置成功')
      resetPwdVisible.value = false
    }
  } catch (e) {
    console.error('重置密码失败', e)
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row) {
  try {
    const res = await userToggleStatus(row.id)
    if (res.data.ok) {
      ElMessage.success(res.data.message)
      loadData()
    }
  } catch (e) {
    console.error('切换状态失败', e)
  }
}

async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 ${row.username} 吗？`, '提示', { type: 'warning' })
    const res = await userDelete(row.id)
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
  loadRoles()
  loadData()
})
</script>

<style scoped>
.user-management { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
