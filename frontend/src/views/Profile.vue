<template>
  <div class="profile-page">
    <div class="title-row">
      <div>
        <div class="page-title">个人中心</div>
        <p class="subtitle">个人信息 · 安全设置 · 我的消息 · 操作记录</p>
      </div>
    </div>

    <el-row :gutter="14">
      <el-col :xs="24" :sm="24" :md="8" :lg="7">
        <el-card class="profile-card" shadow="never">
          <div class="avatar-section">
            <div class="avatar-circle">
              <span class="avatar-text">张</span>
            </div>
            <div class="user-name">{{ userInfo.name }}</div>
            <el-tag type="primary" effect="dark" size="small" class="position-tag">
              <el-icon><User /></el-icon>
              {{ userInfo.position }}
            </el-tag>
          </div>
          <div class="info-list">
            <div class="info-item">
              <span class="info-label">部门</span>
              <span class="info-value">{{ userInfo.department }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">工号</span>
              <span class="info-value">{{ userInfo.employeeId }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">
                <el-icon><Phone /></el-icon>
                手机号
              </span>
              <span class="info-value">{{ userInfo.phone }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">
                <el-icon><MessageBox /></el-icon>
                邮箱
              </span>
              <span class="info-value">{{ userInfo.email }}</span>
            </div>
          </div>
          <el-button type="primary" style="width: 100%" @click="activeTab = 'basic'">
            <el-icon><Edit /></el-icon>
            编辑资料
          </el-button>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="24" :md="16" :lg="17">
        <el-card class="module-card" shadow="never">
          <div class="tab-bar">
            <div class="tab-item" :class="{ active: activeTab === 'basic' }" @click="activeTab = 'basic'">
              <el-icon><User /></el-icon>
              基本资料
            </div>
            <div class="tab-item" :class="{ active: activeTab === 'security' }" @click="activeTab = 'security'">
              <el-icon><Lock /></el-icon>
              安全设置
            </div>
            <div class="tab-item" :class="{ active: activeTab === 'messages' }" @click="activeTab = 'messages'">
              <el-icon><Message /></el-icon>
              我的消息
              <span v-if="unreadCount" class="badge">{{ unreadCount }}</span>
            </div>
            <div class="tab-item" :class="{ active: activeTab === 'logs' }" @click="activeTab = 'logs'">
              <el-icon><List /></el-icon>
              操作记录
            </div>
          </div>

          <div v-if="activeTab === 'basic'" class="tab-content">
            <div class="section-header">
              <span class="section-title">基本资料</span>
              <el-button link type="primary" @click="toggleEditBasic">
                <el-icon><Edit /></el-icon>
                {{ isEditingBasic ? '取消编辑' : '编辑资料' }}
              </el-button>
            </div>
            <el-form :model="basicForm" label-width="100px" class="profile-form">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="姓名">
                    <el-input v-model="basicForm.name" :disabled="!isEditingBasic" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="工号">
                    <el-input v-model="basicForm.employeeId" disabled />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="部门">
                    <el-input v-model="basicForm.department" disabled />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="岗位">
                    <el-input v-model="basicForm.position" disabled />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="手机号">
                    <el-input v-model="basicForm.phone" :disabled="!isEditingBasic" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="邮箱">
                    <el-input v-model="basicForm.email" :disabled="!isEditingBasic" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="入职日期">
                    <el-date-picker v-model="basicForm.joinDate" type="date" style="width: 100%" disabled />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="性别">
                    <el-radio-group v-model="basicForm.gender" :disabled="!isEditingBasic">
                      <el-radio value="male">男</el-radio>
                      <el-radio value="female">女</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
              </el-row>
              <div v-if="isEditingBasic" class="form-actions">
                <el-button @click="cancelEditBasic">取消</el-button>
                <el-button type="primary" @click="saveBasic">
                  <el-icon><Check /></el-icon>
                  保存
                </el-button>
              </div>
            </el-form>
          </div>

          <div v-if="activeTab === 'security'" class="tab-content">
            <div class="section-header">
              <span class="section-title">修改密码</span>
            </div>
            <el-form :model="passwordForm" label-width="100px" class="profile-form">
              <el-row :gutter="20">
                <el-col :span="16">
                  <el-form-item label="原密码">
                    <el-input v-model="passwordForm.oldPassword" type="password" show-password placeholder="请输入原密码" />
                  </el-form-item>
                  <el-form-item label="新密码">
                    <el-input v-model="passwordForm.newPassword" type="password" show-password placeholder="请输入新密码（至少8位）" />
                  </el-form-item>
                  <el-form-item label="确认密码">
                    <el-input v-model="passwordForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
                  </el-form-item>
                </el-col>
              </el-row>
              <div class="form-actions">
                <el-button type="primary" @click="changePassword">
                  <el-icon><Lock /></el-icon>
                  修改密码
                </el-button>
              </div>
            </el-form>

            <el-divider />

            <div class="section-header">
              <span class="section-title">账号绑定</span>
            </div>
            <el-row :gutter="14" class="bind-row">
              <el-col :span="12">
                <el-card class="bind-card" shadow="hover">
                  <div class="bind-icon phone">
                    <el-icon><Phone /></el-icon>
                  </div>
                  <div class="bind-info">
                    <div class="bind-title">绑定手机</div>
                    <div class="bind-desc">已绑定：138****8888</div>
                  </div>
                  <el-button type="primary" link>更换</el-button>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card class="bind-card" shadow="hover">
                  <div class="bind-icon email">
                    <el-icon><MessageBox /></el-icon>
                  </div>
                  <div class="bind-info">
                    <div class="bind-title">绑定邮箱</div>
                    <div class="bind-desc">已绑定：zhang***@company.com</div>
                  </div>
                  <el-button type="primary" link>更换</el-button>
                </el-card>
              </el-col>
            </el-row>

            <el-divider />

            <div class="section-header">
              <span class="section-title">登录日志</span>
              <el-button link type="primary" @click="refreshLoginLogs">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
            <el-table :data="loginLogs" stripe style="width: 100%">
              <el-table-column prop="time" label="登录时间" width="180" />
              <el-table-column prop="device" label="设备" min-width="180" />
              <el-table-column prop="ip" label="IP地址" width="140" />
              <el-table-column prop="location" label="登录地点" width="140" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" effect="dark" :type="row.status === 'success' ? 'success' : 'danger'">
                    {{ row.status === 'success' ? '成功' : '失败' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div v-if="activeTab === 'messages'" class="tab-content">
            <div class="messages-toolbar">
              <div class="toolbar-left">
                <el-radio-group v-model="messageFilter" size="default">
                  <el-radio-button value="all">全部消息</el-radio-button>
                  <el-radio-button value="unread">
                    未读消息
                    <span v-if="unreadCount" class="unread-dot">{{ unreadCount }}</span>
                  </el-radio-button>
                  <el-radio-button value="read">已读消息</el-radio-button>
                </el-radio-group>
              </div>
              <div class="toolbar-right">
                <el-button @click="markAllRead">
                  <el-icon><Check /></el-icon>
                  全部已读
                </el-button>
                <el-button @click="refreshMessages">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
            </div>

            <div class="message-list">
              <div
                v-for="msg in filteredMessages"
                :key="msg.id"
                class="message-item"
                :class="{ unread: !msg.read }"
                @click="toggleMessageRead(msg)"
              >
                <div class="msg-icon" :class="msg.type">
                  <el-icon v-if="msg.type === 'system'"><Setting /></el-icon>
                  <el-icon v-else-if="msg.type === 'warning'"><MessageBox /></el-icon>
                  <el-icon v-else><User /></el-icon>
                </div>
                <div class="msg-content">
                  <div class="msg-header">
                    <span class="msg-title">{{ msg.title }}</span>
                    <span class="msg-time">{{ msg.time }}</span>
                  </div>
                  <div class="msg-desc">{{ msg.content }}</div>
                </div>
                <div v-if="!msg.read" class="unread-badge"></div>
                <el-button link type="primary" class="msg-action">详情</el-button>
              </div>
            </div>
          </div>

          <div v-if="activeTab === 'logs'" class="tab-content">
            <div class="table-toolbar">
              <div class="toolbar-left">
                <el-select v-model="logModuleFilter" placeholder="操作模块" clearable style="width: 160px">
                  <el-option label="设备管理" value="device" />
                  <el-option label="巡检管理" value="inspection" />
                  <el-option label="维保管理" value="maintenance" />
                  <el-option label="系统设置" value="system" />
                  <el-option label="用户管理" value="user" />
                </el-select>
                <el-select v-model="logResultFilter" placeholder="操作结果" clearable style="width: 140px">
                  <el-option label="成功" value="success" />
                  <el-option label="失败" value="fail" />
                </el-select>
                <el-date-picker
                  v-model="logDateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  style="width: 260px"
                />
              </div>
              <div class="toolbar-right">
                <el-button @click="refreshLogs">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
            </div>

            <el-table :data="filteredOperationLogs" stripe style="width: 100%">
              <el-table-column prop="time" label="操作时间" width="180" />
              <el-table-column prop="module" label="操作模块" width="130">
                <template #default="{ row }">
                  <el-tag size="small" :type="moduleTagType(row.module)">{{ moduleText(row.module) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="content" label="操作内容" min-width="250" />
              <el-table-column prop="ip" label="IP地址" width="140" />
              <el-table-column label="操作结果" width="100">
                <template #default="{ row }">
                  <el-tag size="small" effect="dark" :type="row.result === 'success' ? 'success' : 'danger'">
                    {{ row.result === 'success' ? '成功' : '失败' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Setting, Lock, Message, List, Edit, Check, Close, Refresh, Phone, MessageBox, Calendar } from '@element-plus/icons-vue'

const activeTab = ref('basic')
const isEditingBasic = ref(false)

const userInfo = ref({
  name: '张明远',
  position: '消防工程师',
  department: '安全管理部',
  employeeId: 'EMP-2023-0156',
  phone: '138****8888',
  email: 'zhangmy@company.com',
  joinDate: '2023-03-15',
  gender: 'male',
})

const basicForm = ref({ ...userInfo.value })

const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const messageFilter = ref('all')

const messages = ref([
  { id: 1, type: 'system', title: '系统维护通知', content: '系统将于本周六（2026年9月12日）凌晨2:00-4:00进行例行维护，请提前做好相关工作安排。', time: '2026-09-09 10:30', read: false },
  { id: 2, type: 'warning', title: '设备故障预警', content: '综合办公楼A座3层烟感探测器（DEV-000123）检测到异常信号，请及时安排巡检排查。', time: '2026-09-08 16:45', read: false },
  { id: 3, type: 'notice', title: '巡检任务提醒', content: '您有一项新的巡检任务：实验楼B座消防设施巡检，请于今日17:00前完成。', time: '2026-09-08 09:00', read: false },
  { id: 4, type: 'system', title: '密码修改成功', content: '您的账号密码已于2026年9月7日14:30修改成功，如非本人操作请及时联系管理员。', time: '2026-09-07 14:30', read: true },
  { id: 5, type: 'notice', title: '维保工单确认', content: '永安消防维保有限公司提交的维保工单（WO-20260905-001）已完成，请您确认验收。', time: '2026-09-06 11:20', read: true },
  { id: 6, type: 'system', title: '账号登录提醒', content: '您的账号于2026年9月5日08:30在Windows设备（IP: 192.168.1.100）登录成功。', time: '2026-09-05 08:30', read: true },
  { id: 7, type: 'warning', title: '超期维保预警', content: '地下车库B1层温感探测器已超期20天未维保，请及时安排维保工作。', time: '2026-09-04 15:00', read: true },
  { id: 8, type: 'notice', title: '培训通知', content: '2026年度消防安全培训将于9月15日下午2点在会议室A举行，请准时参加。', time: '2026-09-03 09:15', read: true },
])

const loginLogs = ref([
  { time: '2026-09-09 08:30:15', device: 'Windows 11 - Chrome 128', ip: '192.168.1.100', location: '公司内网', status: 'success' },
  { time: '2026-09-08 18:45:22', device: 'iPhone 15 - Safari 17', ip: '223.104.38.12', location: '北京市朝阳区', status: 'success' },
  { time: '2026-09-08 08:25:08', device: 'Windows 11 - Chrome 128', ip: '192.168.1.100', location: '公司内网', status: 'success' },
  { time: '2026-09-07 09:10:33', device: 'Windows 11 - Chrome 128', ip: '192.168.1.100', location: '公司内网', status: 'success' },
  { time: '2026-09-06 22:15:47', device: 'iPad Pro - Safari 17', ip: '114.247.50.123', location: '北京市海淀区', status: 'success' },
  { time: '2026-09-06 22:14:02', device: 'iPad Pro - Safari 17', ip: '114.247.50.123', location: '北京市海淀区', status: 'fail' },
  { time: '2026-09-05 08:30:00', device: 'Windows 11 - Chrome 128', ip: '192.168.1.100', location: '公司内网', status: 'success' },
])

const logModuleFilter = ref('')
const logResultFilter = ref('')
const logDateRange = ref([])

const operationLogs = ref([
  { id: 1, time: '2026-09-09 14:30:25', module: 'inspection', content: '提交巡检记录：实验楼B座消防设施巡检，共检查设备89台，发现问题2处', ip: '192.168.1.100', result: 'success' },
  { id: 2, time: '2026-09-09 10:15:08', module: 'device', content: '查看设备详情：烟感探测器-3F走廊（DEV-000123）', ip: '192.168.1.100', result: 'success' },
  { id: 3, time: '2026-09-08 16:42:33', module: 'maintenance', content: '确认维保工单：WO-20260905-001，维保结果：有故障', ip: '192.168.1.100', result: 'success' },
  { id: 4, time: '2026-09-08 11:20:15', module: 'system', content: '修改个人信息：更新手机号', ip: '192.168.1.100', result: 'success' },
  { id: 5, time: '2026-09-07 14:30:00', module: 'system', content: '修改登录密码', ip: '192.168.1.100', result: 'success' },
  { id: 6, time: '2026-09-07 09:45:22', module: 'inspection', content: '创建巡检任务：学生宿舍C区月度安全巡检', ip: '192.168.1.100', result: 'success' },
  { id: 7, time: '2026-09-06 15:10:48', module: 'device', content: '导出设备列表：消防水泵设备清单', ip: '192.168.1.100', result: 'success' },
  { id: 8, time: '2026-09-06 10:25:30', module: 'maintenance', content: '查看维保计划：综合办公楼月度消防维保（MP-2026-001）', ip: '192.168.1.100', result: 'success' },
  { id: 9, time: '2026-09-05 16:08:12', module: 'user', content: '登录系统失败：密码错误', ip: '223.104.38.12', result: 'fail' },
  { id: 10, time: '2026-09-05 16:05:30', module: 'user', content: '登录系统', ip: '223.104.38.12', result: 'success' },
  { id: 11, time: '2026-09-05 11:30:45', module: 'device', content: '编辑设备信息：喷淋泵-备用泵（DEV-000456）', ip: '192.168.1.100', result: 'success' },
  { id: 12, time: '2026-09-04 14:22:18', module: 'inspection', content: '删除巡检记录：IR-20260903-002', ip: '192.168.1.100', result: 'fail' },
])

const unreadCount = computed(() => messages.value.filter(m => !m.read).length)

const filteredMessages = computed(() => {
  if (messageFilter.value === 'all') return messages.value
  if (messageFilter.value === 'unread') return messages.value.filter(m => !m.read)
  if (messageFilter.value === 'read') return messages.value.filter(m => m.read)
  return messages.value
})

const filteredOperationLogs = computed(() => {
  let list = operationLogs.value
  if (logModuleFilter.value) {
    list = list.filter(l => l.module === logModuleFilter.value)
  }
  if (logResultFilter.value) {
    list = list.filter(l => l.result === logResultFilter.value)
  }
  return list
})

function toggleEditBasic() {
  if (isEditingBasic.value) {
    basicForm.value = { ...userInfo.value }
  }
  isEditingBasic.value = !isEditingBasic.value
}

function cancelEditBasic() {
  basicForm.value = { ...userInfo.value }
  isEditingBasic.value = false
}

function saveBasic() {
  userInfo.value = { ...basicForm.value }
  isEditingBasic.value = false
  ElMessage.success('资料保存成功')
}

function changePassword() {
  if (!passwordForm.value.oldPassword) {
    ElMessage.warning('请输入原密码')
    return
  }
  if (!passwordForm.value.newPassword) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (passwordForm.value.newPassword.length < 8) {
    ElMessage.warning('新密码至少8位')
    return
  }
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  ElMessage.success('密码修改成功')
  passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
}

function toggleMessageRead(msg) {
  if (!msg.read) {
    msg.read = true
  }
}

function markAllRead() {
  messages.value.forEach(m => (m.read = true))
  ElMessage.success('已全部标记为已读')
}

function refreshMessages() {
  ElMessage.success('消息已刷新')
}

function refreshLoginLogs() {
  ElMessage.success('登录日志已刷新')
}

function refreshLogs() {
  ElMessage.success('操作记录已刷新')
}

function moduleText(module) {
  const map = {
    device: '设备管理',
    inspection: '巡检管理',
    maintenance: '维保管理',
    system: '系统设置',
    user: '用户管理',
  }
  return map[module] || module
}

function moduleTagType(module) {
  const map = {
    device: 'primary',
    inspection: 'success',
    maintenance: 'warning',
    system: 'info',
    user: 'danger',
  }
  return map[module] || ''
}
</script>

<style scoped>
.profile-page {
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
  font-size: 14px;
}

.profile-card {
  margin-bottom: 14px;
}

.avatar-section {
  text-align: center;
  padding: 8px 0 18px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 16px;
}

.avatar-circle {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  font-size: 36px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.user-name {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 10px;
}

.position-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.info-list {
  margin-bottom: 18px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f8fafc;
  font-size: 13px;
}

.info-item:last-of-type {
  border-bottom: none;
}

.info-label {
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.info-value {
  color: #0f172a;
  font-weight: 500;
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  position: relative;
  padding-left: 12px;
}

.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 16px;
  background: #2563eb;
  border-radius: 2px;
}

.profile-form {
  max-width: 720px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 10px;
}

.bind-row {
  margin-bottom: 10px;
}

.bind-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 6px 4px;
}

.bind-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
}

.bind-icon.phone { background: linear-gradient(135deg, #22c55e, #16a34a); }
.bind-icon.email { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

.bind-info {
  flex: 1;
  min-width: 0;
}

.bind-title {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
  margin-bottom: 2px;
}

.bind-desc {
  font-size: 12px;
  color: #64748b;
}

.messages-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
}

.unread-dot {
  display: inline-block;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  padding: 0 5px;
  border-radius: 8px;
  min-width: 14px;
  text-align: center;
  line-height: 14px;
  margin-left: 4px;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.message-item:hover {
  background: #f1f5f9;
}

.message-item.unread {
  background: #eff6ff;
  border-left: 3px solid #2563eb;
}

.msg-icon {
  width: 44px;
  height: 44px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  flex-shrink: 0;
}

.msg-icon.system { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.msg-icon.warning { background: linear-gradient(135deg, #f97316, #ea580c); }
.msg-icon.notice { background: linear-gradient(135deg, #22c55e, #16a34a); }

.msg-content {
  flex: 1;
  min-width: 0;
}

.msg-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.msg-title {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
}

.msg-time {
  font-size: 12px;
  color: #94a3b8;
  flex-shrink: 0;
  margin-left: 10px;
}

.msg-desc {
  font-size: 13px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.unread-badge {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  flex-shrink: 0;
}

.msg-action {
  flex-shrink: 0;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.danger-text {
  color: #dc2626;
  font-weight: 600;
}
</style>
