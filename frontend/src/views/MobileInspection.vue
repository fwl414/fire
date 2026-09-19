<template>
  <div class="mobile-page">
    <!-- 顶部：当前登录人 + 关键时刻 -->
    <div class="mobile-header">
      <div class="header-top">
        <div>
          <div class="header-title">现场协同</div>
          <div class="header-sub">{{ user.name }}<span v-if="user.role"> · {{ user.role }}</span></div>
        </div>
        <el-button circle size="small" :loading="loading" @click="reloadAll">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
      <div class="header-time">{{ nowText }}</div>
    </div>

    <div class="mobile-body">
      <!-- ---------------- 首页 ---------------- -->
      <template v-if="activeTab === 'home'">
        <div class="stat-grid">
          <div class="stat-cell alert">
            <div class="stat-num">{{ home.stats?.pendingAlerts ?? 0 }}</div>
            <div class="stat-label">待处理告警</div>
          </div>
          <div class="stat-cell workorder">
            <div class="stat-num">{{ home.stats?.claimableWorkorders ?? 0 }}</div>
            <div class="stat-label">可领取工单</div>
          </div>
          <div class="stat-cell mine">
            <div class="stat-num">{{ home.stats?.myWorkorders ?? 0 }}</div>
            <div class="stat-label">我的在办</div>
          </div>
          <div class="stat-cell inspection">
            <div class="stat-num">{{ home.stats?.todayInspections ?? 0 }}</div>
            <div class="stat-label">今日巡检</div>
          </div>
        </div>

        <div class="section-title">
          <span>可领取工单</span>
          <span class="section-tip">共 {{ home.stats?.claimableWorkorders ?? 0 }} 条</span>
        </div>
        <div v-if="home.claimableWorkorders?.length" class="card-list">
          <div v-for="item in home.claimableWorkorders" :key="`claim-${item.id}`" class="task-card">
            <div class="task-main">
              <div class="task-title">{{ item.title }}</div>
              <div class="task-meta">
                <el-tag size="small" type="warning" effect="plain">{{ item.status }}</el-tag>
                <span v-if="item.riskLevel" class="meta-text">风险：{{ item.riskLevel }}</span>
                <span class="meta-text">{{ item.location || '未填位置' }}</span>
              </div>
            </div>
            <el-button size="small" type="primary" :loading="claimingId === item.id" @click="claim(item)">
              领取
            </el-button>
          </div>
        </div>
        <el-empty v-else description="暂时没有待领取的工单" :image-size="70" />

        <div class="section-title">
          <span>待处理告警</span>
          <span class="section-tip">今日新增 {{ home.stats?.todayAlerts ?? 0 }} 条</span>
        </div>
        <div v-if="home.pendingAlerts?.length" class="card-list">
          <div v-for="item in home.pendingAlerts" :key="`alert-${item.id}`" class="task-card">
            <div class="task-main">
              <div class="task-title">{{ item.title }}</div>
              <div class="task-meta">
                <el-tag size="small" :type="severityType(item.severity)" effect="dark">
                  {{ item.severityLabel }}
                </el-tag>
                <el-tag v-if="item.escalated" size="small" type="danger" effect="plain">已升级</el-tag>
                <span class="meta-text">{{ item.location || '未填位置' }}</span>
              </div>
            </div>
            <el-button
              size="small"
              :loading="handlingId === item.id"
              @click="handleAlert(item)"
            >
              标记已处置
            </el-button>
          </div>
        </div>
        <el-empty v-else description="没有待处理的告警" :image-size="70" />
      </template>

      <!-- ---------------- 我的待办 ---------------- -->
      <template v-else-if="activeTab === 'tasks'">
        <div class="section-title">
          <span>我的待办</span>
          <span class="section-tip">
            工单 {{ tasks.workorderCount ?? 0 }} · 告警 {{ tasks.alertCount ?? 0 }}
          </span>
        </div>
        <div v-if="tasks.items?.length" class="card-list">
          <div v-for="item in tasks.items" :key="`${item.type}-${item.id}`" class="task-card">
            <div class="task-main">
              <div class="task-title">
                <el-tag size="small" :type="item.type === 'workorder' ? 'warning' : 'danger'" effect="plain">
                  {{ item.type === 'workorder' ? '工单' : '告警' }}
                </el-tag>
                {{ item.title }}
              </div>
              <div class="task-meta">
                <span class="meta-text">{{ item.statusLabel || item.status }}</span>
                <span v-if="item.riskLevel" class="meta-text">风险：{{ item.riskLevel }}</span>
                <span class="meta-text">{{ formatTime(item.createdAt) }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="没有分配给你的待办" :image-size="70" />
      </template>

      <!-- ---------------- 现场上报 ---------------- -->
      <template v-else-if="activeTab === 'report'">
        <div class="section-title"><span>现场上报</span></div>
        <el-form label-position="top" class="report-form">
          <el-form-item label="建筑">
            <el-select v-model="reportForm.building_id" placeholder="选择建筑" clearable style="width: 100%" @change="onBuildingChange">
              <el-option v-for="b in buildings" :key="b.id" :label="b.buildingName || b.building_name" :value="b.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="设备（可选）">
            <el-select v-model="reportForm.device_id" placeholder="选择设备" clearable filterable style="width: 100%">
              <el-option
                v-for="d in devices"
                :key="d.id"
                :label="`${d.device_name || d.deviceName}（${d.device_code || d.deviceCode}）`"
                :value="d.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="现场位置">
            <el-input v-model="reportForm.location" placeholder="如：2 层东侧走廊" />
          </el-form-item>
          <el-form-item label="现场描述">
            <el-input
              v-model="reportForm.description"
              type="textarea"
              :rows="3"
              placeholder="如：消防通道被纸箱堵塞，旁边有电动车充电"
            />
          </el-form-item>
          <el-form-item label="现场照片">
            <input ref="fileInput" class="file-input" type="file" accept="image/*" @change="onFileChange" />
            <div class="photo-row">
              <el-button size="small" @click="fileInput?.click()">
                <el-icon><Camera /></el-icon>
                拍照 / 选图
              </el-button>
              <span class="meta-text">{{ photoName || '未选择图片' }}</span>
            </div>
          </el-form-item>
        </el-form>

        <el-button
          type="primary"
          class="submit-btn"
          :loading="reporting"
          @click="submitReport"
        >
          提交上报
        </el-button>

        <el-card v-if="reportResult" class="result-card" shadow="never">
          <div class="result-header">
            <span>分析结果</span>
            <el-tag :type="severityType(levelToSeverity(reportResult.riskLevel))" effect="dark">
              {{ reportResult.riskLevel }} · {{ reportResult.riskScore }} 分
            </el-tag>
          </div>
          <div class="result-row">巡检记录 #{{ reportResult.recordId }}（{{ reportResult.location }}）</div>
          <div v-if="reportResult.hazards?.length" class="hazard-tags">
            <el-tag v-for="(hazard, index) in reportResult.hazards" :key="index" size="small" effect="plain">
              {{ hazard }}
            </el-tag>
          </div>
          <div v-else class="meta-text">未识别到明确隐患</div>
          <div class="result-suggestion">{{ reportResult.suggestion }}</div>
        </el-card>
      </template>

      <!-- ---------------- 我的 ---------------- -->
      <template v-else>
        <div class="section-title"><span>我的</span></div>
        <el-card class="profile-card" shadow="never">
          <div class="profile-row"><span>姓名</span><b>{{ user.name }}</b></div>
          <div class="profile-row"><span>角色</span><b>{{ user.role || '--' }}</b></div>
          <div class="profile-row"><span>本租户设备</span><b>{{ home.stats?.deviceCount ?? 0 }}</b></div>
          <div class="profile-row"><span>我的在办工单</span><b>{{ home.stats?.myWorkorders ?? 0 }}</b></div>
          <div class="profile-row"><span>今日巡检</span><b>{{ home.stats?.todayInspections ?? 0 }}</b></div>
        </el-card>
        <el-button class="submit-btn" @click="doLogout">退出登录</el-button>
      </template>
    </div>

    <!-- 底部导航 -->
    <div class="mobile-tabbar">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        class="tabbar-item"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <span>{{ tab.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera, HomeFilled, List, Refresh, Upload, User } from '@element-plus/icons-vue'
import request from '../api'
import { getCurrentUser, logout } from '../auth'

// 这一页是移动端协同（现场人员用）：数据全部来自 /api/mobile/* 与既有业务接口，
// 改造前这里是纯写死的手机壳 Mock（待办、通知、巡检任务、报警列表全是常量，提交按钮也没有事件）。
const router = useRouter()

const tabs = [
  { key: 'home', label: '首页', icon: HomeFilled },
  { key: 'tasks', label: '待办', icon: List },
  { key: 'report', label: '上报', icon: Upload },
  { key: 'profile', label: '我的', icon: User },
]

const activeTab = ref('home')
const loading = ref(false)
const claimingId = ref(null)
const handlingId = ref(null)
const reporting = ref(false)

const home = ref({ stats: {} })
const tasks = ref({})
const buildings = ref([])
const devices = ref([])
const reportResult = ref(null)
const photoName = ref('')
const fileInput = ref(null)

const reportForm = reactive({
  building_id: null,
  device_id: null,
  location: '',
  description: '',
  file: null,
})

// 用户信息取登录态；未登录时给空对象，不编造姓名
const user = computed(() => {
  const current = getCurrentUser() || {}
  return {
    name: current.realName || current.real_name || current.username || '未登录',
    role: current.roleName || current.role_name || current.role || '',
  }
})

const nowText = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

function severityType(severity) {
  if (severity === 'critical') return 'danger'
  if (severity === 'high') return 'warning'
  if (severity === 'medium') return 'info'
  return ''
}

function levelToSeverity(level) {
  if (level === '严重风险') return 'critical'
  if (level === '高风险') return 'high'
  if (level === '中风险') return 'medium'
  return 'low'
}

function formatTime(text) {
  if (!text) return ''
  return String(text).replace('T', ' ').slice(5, 16)
}

async function loadHome() {
  const res = await request.get('/api/mobile/home')
  home.value = res.data || { stats: {} }
}

async function loadTasks() {
  const res = await request.get('/api/mobile/tasks')
  tasks.value = res.data || {}
}

async function loadBuildings() {
  const res = await request.get('/api/buildings')
  buildings.value = res.data || []
}

async function loadDevices(buildingId) {
  const res = await request.get('/api/devices', {
    params: { page_size: 100, ...(buildingId ? { building_id: buildingId } : {}) },
  })
  devices.value = res.data?.items || []
}

async function reloadAll() {
  loading.value = true
  try {
    await Promise.all([loadHome(), loadTasks()])
  } catch (e) {
    // 失败原因由请求拦截器提示
  } finally {
    loading.value = false
  }
}

function switchTab(key) {
  activeTab.value = key
  if (key === 'report' && !buildings.value.length) {
    loadBuildings().catch(() => {})
  }
}

function onBuildingChange(buildingId) {
  reportForm.device_id = null
  loadDevices(buildingId).catch(() => {})
}

function onFileChange(event) {
  const file = event.target.files?.[0] || null
  reportForm.file = file
  photoName.value = file ? file.name : ''
}

async function claim(item) {
  claimingId.value = item.id
  try {
    const res = await request.post(`/api/mobile/workorders/${item.id}/claim`)
    ElMessage.success(res.data?.message || '已领取')
    await Promise.all([loadHome(), loadTasks()])
  } catch (e) {
    // 已被别人领走等原因由拦截器提示
  } finally {
    claimingId.value = null
  }
}

async function handleAlert(item) {
  handlingId.value = item.id
  try {
    await request.post(`/api/alerts/${item.id}/handle`, { status: 'resolved', handle_result: '移动端现场处置完成' })
    ElMessage.success('已标记为已处置')
    await Promise.all([loadHome(), loadTasks()])
  } catch (e) {
    // 失败原因由拦截器提示
  } finally {
    handlingId.value = null
  }
}

async function submitReport() {
  if (!reportForm.building_id && !reportForm.device_id && !reportForm.location.trim()) {
    ElMessage.warning('请至少选择建筑/设备，或填写现场位置')
    return
  }
  reporting.value = true
  try {
    const form = new FormData()
    if (reportForm.building_id) form.append('building_id', reportForm.building_id)
    if (reportForm.device_id) form.append('device_id', reportForm.device_id)
    form.append('location', reportForm.location)
    form.append('description', reportForm.description)
    if (reportForm.file) form.append('image', reportForm.file)

    const res = await request.post('/api/mobile/report', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    reportResult.value = res.data
    ElMessage.success('上报成功，已完成分析')
    await loadHome()
  } catch (e) {
    // 失败原因由拦截器提示
  } finally {
    reporting.value = false
  }
}

async function doLogout() {
  try {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  await logout()
  router.push('/login')
}

onMounted(async () => {
  await reloadAll()
  loadBuildings().catch(() => {})
})
</script>

<style scoped>
/* 移动优先：手机上铺满，桌面上居中成一条手机宽度的列 */
.mobile-page {
  max-width: 480px;
  margin: 0 auto;
  min-height: 100vh;
  background: #f1f5f9;
  display: flex;
  flex-direction: column;
  position: relative;
}

.mobile-header {
  background: linear-gradient(135deg, #1d4ed8, #2563eb);
  color: #fff;
  padding: 18px 16px;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: 19px;
  font-weight: 600;
}

.header-sub {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 4px;
}

.header-time {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 10px;
}

.mobile-body {
  flex: 1;
  padding: 14px 14px 76px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.stat-cell {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  border-left: 4px solid #e2e8f0;
}

.stat-cell.alert {
  border-left-color: #ef4444;
}

.stat-cell.workorder {
  border-left-color: #f59e0b;
}

.stat-cell.mine {
  border-left-color: #3b82f6;
}

.stat-cell.inspection {
  border-left-color: #22c55e;
}

.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 16px 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.section-tip {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 400;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-card {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-main {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 14px;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 6px;
  word-break: break-all;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  align-items: center;
}

.meta-text {
  font-size: 12px;
  color: #94a3b8;
}

.report-form {
  background: #fff;
  border-radius: 10px;
  padding: 12px 12px 0;
}

.file-input {
  display: none;
}

.photo-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.submit-btn {
  width: 100%;
  margin-top: 14px;
}

.result-card {
  margin-top: 14px;
  border-radius: 10px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #334155;
}

.result-row {
  font-size: 12px;
  color: #64748b;
  margin: 8px 0;
}

.hazard-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.result-suggestion {
  margin-top: 10px;
  font-size: 12px;
  color: #334155;
  line-height: 1.7;
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px 10px;
}

.profile-card {
  border-radius: 10px;
}

.profile-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 8px 0;
  border-bottom: 1px dashed #f1f5f9;
  color: #64748b;
}

.profile-row b {
  color: #334155;
}

.mobile-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  max-width: 480px;
  margin: 0 auto;
  background: #fff;
  border-top: 1px solid #e2e8f0;
  display: flex;
}

.tabbar-item {
  flex: 1;
  padding: 8px 0 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
}

.tabbar-item.active {
  color: #2563eb;
}
</style>
