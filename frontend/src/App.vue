<template>
  <div class="global-loading" v-if="globalLoading">
    <div class="loading-spinner"></div>
    <div class="loading-text">加载中...</div>
  </div>
  <router-view v-if="isPublicPage" />
  <el-container v-else class="layout" :class="{ 'data-screen-layout': isDataScreen }">
    <el-aside v-if="!isDataScreen" :width="sidebarOpen ? '238px' : '0px'" class="aside">
      <div class="brand">智慧消防管理系统</div>
      <div class="user-panel" @click="goProfile" style="cursor: pointer">
        <div class="avatar">{{ userInitial }}</div>
        <div>
          <strong>{{ currentUser?.displayName || '未登录' }}</strong>
          <p>{{ currentUser?.roleName || '-' }} · {{ currentUser?.username || '' }}</p>
        </div>
      </div>
      <el-menu :default-active="$route.path" router background-color="#0f172a" text-color="#cbd5e1" active-text-color="#ffffff">
        <template v-for="section in visibleSections" :key="section.index">
          <el-menu-item v-if="!section.children" :index="section.path">{{ section.title }}</el-menu-item>
          <el-sub-menu v-else :index="section.index">
            <template #title>{{ section.title }}</template>
            <el-menu-item v-for="item in section.children" :key="item.path" :index="item.path">{{ item.title }}</el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header v-if="!isDataScreen" class="topbar">
        <div class="topbar-left">
          <el-button
            class="sidebar-toggle"
            text
            :title="sidebarOpen ? '收起侧边栏' : '展开侧边栏'"
            :aria-expanded="sidebarOpen"
            aria-label="收起或展开侧边栏"
            @click="toggleSidebar"
          >
            <el-icon :size="18">
              <Fold v-if="sidebarOpen" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <div>
            <strong>{{ pageTitle }}</strong>
            <span class="top-subtitle">{{ roleHint }}</span>
          </div>
        </div>
        <div class="top-actions">
          <el-button text @click="openNotifications">
            <el-badge :value="notificationSummary.unread || 0" :hidden="!notificationSummary.unread" class="badge">
              通知
            </el-badge>
          </el-button>
          <el-button @click="showLogoutDialog" type="danger">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main" :class="{ 'data-screen-main': isDataScreen }">
        <router-view />
      </el-main>
    </el-container>

    <el-drawer v-model="notifyDrawer" title="系统通知中心" size="420px">
      <div class="notify-summary">
        <div><span>未读通知</span><strong>{{ notificationSummary.unread || 0 }}</strong></div>
        <div><span>高优先级</span><strong>{{ notificationSummary.high_priority || 0 }}</strong></div>
        <div><span>待处理</span><strong>{{ notificationSummary.pending || 0 }}</strong></div>
      </div>
      <div class="drawer-actions">
        <el-button size="small" @click="loadNotifications">刷新</el-button>
        <el-button size="small" type="primary" @click="markAllRead">全部已读</el-button>
        <el-button size="small" @click="$router.push('/message-center'); notifyDrawer=false">查看全部</el-button>
      </div>
      <div class="notify-list">
        <div v-for="n in notifications" :key="n.id" class="notify-item" :class="n.level">
          <div class="notify-top"><strong>{{ n.title }}</strong><el-tag size="small" :type="notifyType(n.level)">{{ n.level_text }}</el-tag></div>
          <p>{{ n.content }}</p>
          <div class="notify-foot"><span>{{ n.source }} · {{ n.created_at }}</span><el-button link type="primary" @click="goNotification(n)">查看</el-button></div>
        </div>
        <el-empty v-if="!notifications.length" description="暂无系统通知" />
      </div>
    </el-drawer>
  </el-container>
  <SmartAssistant v-if="!isPublicPage" />
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import request from './api'
import { getCurrentUser, clearCurrentUser, hasPermission } from './auth'
import { globalLoading } from './api/core'
import { wsService } from './utils/websocket'
import SmartAssistant from './components/SmartAssistant.vue'
import { Expand, Fold } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const currentUser = ref(getCurrentUser())
const notifyDrawer = ref(false)
const notifications = ref([])
const notificationSummary = ref({})

// 侧边栏默认收起（隐藏式：点顶栏按钮才展开），用户手动选过的状态记在本地，刷新后保持。
const SIDEBAR_KEY = 'fire.sidebar.open'
const sidebarOpen = ref(localStorage.getItem(SIDEBAR_KEY) === '1')

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
  localStorage.setItem(SIDEBAR_KEY, sidebarOpen.value ? '1' : '0')
}

const isPublicPage = computed(() => route.meta?.public)
const isDataScreen = computed(() => route.path === '/dashboard')
const userInitial = computed(() => (currentUser.value?.displayName || currentUser.value?.username || '用').slice(0, 1))
const pageTitle = computed(() => route.meta?.title || routeNameMap[route.path] || '工作台')
const roleHint = computed(() => {
  const role = currentUser.value?.roleName || '未登录'
  if (currentUser.value?.role === 'rectifier') return `${role}：重点关注待整改、即将逾期和待复查工单`
  if (currentUser.value?.role === 'inspector') return `${role}：巡检、档案和问答`
  if (currentUser.value?.role === 'viewer') return `${role}：重点查看总览、档案和报告验真`
  return `${role}：风险态势、硬件事件和工单管理`
})

const routeNameMap = {
  '/dashboard': '数据大屏',
  '/gis-map': 'GIS地图总览',
  '/floor-plan': '楼层平面图管理',
  '/inspection': '现场巡检',
  '/multimodal': '多模态分析',
  '/building-risk': '建筑风险总览',
  '/decision-logs': '分析日志',
  '/alert-center': '设备告警中心',
  '/batch-inspection': '批量巡检任务',
  '/report-center': '统计报表中心',
  '/records': '巡检档案',
  '/workorders': '整改工单',
  '/qa': '消防问答',
  '/agent-lab': '分析能力',
  '/notifications': '系统通知中心',
  '/operation-logs': '系统操作日志',
  '/evaluation': '实验评估',
  '/device-data': '设备数据表',
  '/settings': '系统设置',
  '/system-health': '系统状态',
  '/duty-room': '消防控制室',
  '/water-monitor': '消防水源监测',
  '/key-areas': '重点部位管理',
  '/fire-archives': '消防档案',
  '/electrical-fire': '电气火灾监测',
  '/emergency-command': '应急指挥',
  '/video-monitor': '视频监控',
  '/fire-training': '消防安全培训',
  '/grid-management': '网格化管理',
  '/fire-assessment': '消防安全评估',
  '/mini-fire-station': '微型消防站',
  '/hazard-management': '隐患排查治理',
  '/daily-brief': '每日安全简报',
  '/iot-device': '物联网设备',
  '/mobile-inspection': '现场协同',
  '/dict-management': '数据字典管理',
  '/org-management': '组织架构管理',
  '/message-center': '消息通知中心',
  '/profile': '个人中心',
  '/system-monitor': '系统监控中心',
  '/key-unit-management': '消防重点单位',
  '/facility-inspection': '设施检测管理',
  '/fire-accident': '火灾事故管理',
  '/fire-promotion': '消防宣传活动',
  '/system-announcement': '系统公告管理',
}

const menuSections = [
  { index: 'dashboard', title: '数据大屏', path: '/dashboard', icon: 'DataBoard', permission: 'dashboard' },
  { index: 'device-monitor', title: '设备监测', children: [
    { title: '设备总览', path: '/devices', permission: 'dashboard' },
    { title: '物联网设备', path: '/iot-device', roles: ['admin'] },
    { title: '消防水源', path: '/water-monitor', roles: ['admin'] },
    { title: '电气火灾', path: '/electrical-fire', roles: ['admin'] },
    { title: '实时数据', path: '/device-data', roles: ['admin'] },
    { title: '设备告警', path: '/alert-center', roles: ['admin', 'inspector'] },
  ]},
  { index: 'alarm-center', title: '报警中心', children: [
    { title: '实时报警', path: '/alert-center', permission: 'dashboard' },
    { title: '视频联动', path: '/video-monitor', roles: ['admin'] },
    { title: '报警记录', path: '/faults', roles: ['admin', 'rectifier'] },
  ]},
  { index: 'duty-room', title: '消防控制室', children: [
    { title: '值班管理', path: '/duty-room', roles: ['admin'] },
    { title: '值班记录', path: '/duty-room', roles: ['admin'] },
  ]},
  { index: 'key-unit', title: '重点单位', children: [
    { title: '单位台账', path: '/key-unit-management', roles: ['admin'] },
    { title: '风险分级', path: '/key-unit-management', roles: ['admin'] },
    { title: '监督检查', path: '/key-unit-management', roles: ['admin'] },
  ]},
  { index: 'hazard', title: '隐患治理', children: [
    { title: '风险分级管控', path: '/hazard-management', roles: ['admin'] },
    { title: '隐患排查治理', path: '/hazard-management', roles: ['admin'] },
    { title: '整改工单', path: '/workorders', permission: 'workorders' },
  ]},
  { index: 'grid', title: '网格化管理', children: [
    { title: '网格区域', path: '/grid-management', roles: ['admin'] },
    { title: '网格员管理', path: '/grid-management', roles: ['admin'] },
    { title: '隐患上报', path: '/grid-management', roles: ['admin'] },
  ]},
  { index: 'inspection', title: '巡检管理', children: [
    { title: '巡检计划', path: '/batch-inspection', permission: 'batch:view' },
    { title: '现场巡检', path: '/inspection', permission: 'inspection' },
    { title: '巡检档案', path: '/records', permission: 'records' },
  ]},
  { index: 'maintenance', title: '维保管理', children: [
    { title: '维保总览', path: '/maintenance', permission: 'workorders' },
    { title: '设施检测', path: '/facility-inspection', roles: ['admin'] },
    { title: '整改工单', path: '/workorders', permission: 'workorders' },
  ]},
  { index: 'key-areas', title: '重点部位', children: [
    { title: '部位管理', path: '/key-areas', roles: ['admin'] },
    { title: '风险分级', path: '/key-areas', roles: ['admin'] },
  ]},
  { index: 'emergency', title: '应急指挥', children: [
    { title: '应急预案', path: '/emergency-command', roles: ['admin'] },
    { title: '疏散路线', path: '/emergency-command', roles: ['admin'] },
    { title: '应急资源', path: '/emergency-command', roles: ['admin'] },
    { title: '微型消防站', path: '/mini-fire-station', roles: ['admin'] },
  ]},
  { index: 'building', title: '建筑管理', children: [
    { title: '建筑信息', path: '/building-risk', permission: 'dashboard' },
    { title: '楼层平面图', path: '/floor-plan', roles: ['admin'] },
  ]},
  { index: 'assessment', title: '消防评估', children: [
    { title: '评估概览', path: '/fire-assessment', roles: ['admin'] },
    { title: '历史评估', path: '/fire-assessment', roles: ['admin'] },
    { title: '整改跟踪', path: '/fire-assessment', roles: ['admin'] },
  ]},
  { index: 'accident', title: '事故管理', children: [
    { title: '事故台账', path: '/fire-accident', roles: ['admin'] },
    { title: '事故调查', path: '/fire-accident', roles: ['admin'] },
    { title: '统计分析', path: '/fire-accident', roles: ['admin'] },
  ]},
  { index: 'statistics', title: '数据统计', children: [
    { title: '统计报表', path: '/report-center', roles: ['admin', 'inspector'] },
    { title: '趋势分析', path: '/building-risk', permission: 'dashboard' },
  ]},
  { index: 'archives', title: '消防档案', children: [
    { title: '档案总览', path: '/fire-archives', roles: ['admin'] },
    { title: '建筑档案', path: '/fire-archives', roles: ['admin'] },
  ]},
  { index: 'training', title: '消防培训', children: [
    { title: '培训课程', path: '/fire-training', roles: ['admin'] },
    { title: '考试考核', path: '/fire-training', roles: ['admin'] },
    { title: '培训档案', path: '/fire-training', roles: ['admin'] },
  ]},
  { index: 'promotion', title: '消防宣传', children: [
    { title: '活动计划', path: '/fire-promotion', roles: ['admin', 'inspector'] },
    { title: '宣传资料', path: '/fire-promotion', roles: ['admin', 'inspector'] },
    { title: '宣传效果', path: '/fire-promotion', roles: ['admin', 'inspector'] },
  ]},
  { index: 'mobile', title: '移动端', children: [
    { title: '现场协同', path: '/mobile-inspection', roles: ['admin', 'inspector'] },
  ]},
  { index: 'intelligence', title: '智能分析', children: [
    { title: '每日安全简报', path: '/daily-brief', roles: ['admin', 'inspector'] },
    { title: '智能问答', path: '/qa', permission: 'qa' },
    { title: '风险评估', path: '/building-risk', permission: 'dashboard' },
    { title: '多模态分析', path: '/multimodal', permission: 'inspection' },
    { title: '分析能力', path: '/agent-lab', roles: ['admin', 'inspector'] },
    { title: '分析日志', path: '/decision-logs', roles: ['admin', 'inspector'] },
  ]},
  { index: 'knowledge', title: '知识库', children: [
    { title: '消防知识库', path: '/knowledge', permission: 'knowledge' },
    { title: '知识图谱', path: '/knowledge-graph', permission: 'knowledge' },
    { title: '消防学习', path: '/learning', roles: ['admin', 'inspector'] },
  ]},
  { index: 'system', title: '系统管理', children: [
    { title: '组织架构', path: '/org-management', roles: ['admin'] },
    { title: '用户管理', path: '/user-management', roles: ['admin'], permission: 'system:users' },
    { title: '角色权限', path: '/role-management', roles: ['admin'], permission: 'system:roles' },
    { title: '数据字典', path: '/dict-management', roles: ['admin'] },
    { title: '系统公告', path: '/system-announcement', roles: ['admin'] },
    { title: '操作日志', path: '/operation-logs', roles: ['admin'], permission: 'logs:view' },
    { title: '系统监控', path: '/system-monitor', roles: ['admin'] },
    { title: '系统设置', path: '/settings', roles: ['admin'] },
  ]},
]

function itemVisible(item) {
  const user = currentUser.value
  if (!user) return false
  if (item.roles?.length) return item.roles.includes(user.role)
  if (item.permission) return hasPermission(user, item.permission)
  return true
}
const visibleSections = computed(() => menuSections.map(section => {
  if (!section.children) return itemVisible(section) ? section : null
  const children = section.children.filter(itemVisible)
  return children.length ? { ...section, children } : null
}).filter(Boolean))

async function loadNotifications() {
  if (!currentUser.value) return
  try {
    notificationSummary.value = (await request.get('/api/notifications/summary', { silentError: true })).data
    notifications.value = (await request.get('/api/notifications', { params: { limit: 8 }, silentError: true })).data.items || []
  } catch { /* ignore notification errors */ }
}
function goProfile() { router.push('/profile') }
function openNotifications() { notifyDrawer.value = true; loadNotifications() }
function notifyType(level) { return level === 'danger' ? 'danger' : level === 'warning' ? 'warning' : level === 'success' ? 'success' : 'info' }
function goNotification(n) { if (n.link) { notifyDrawer.value = false; router.push(n.link) } }
async function markAllRead() { await request.post('/api/notifications/mark-all-read'); ElMessage.success('已标记为全部已读'); await loadNotifications() }
function showLogoutDialog() {
  ElMessageBox({
    // 标题不加 emoji：.logout-dialog 的 ::before 已经画了一个会跳动的门
    title: '退出登录',
    message: `您确定要退出 <strong>${currentUser.value?.displayName || currentUser.value?.username || '当前账号'}</strong> 吗？`,
    type: 'warning',
    showCancelButton: true,
    confirmButtonText: '确认退出',
    cancelButtonText: '再等等',
    confirmButtonClass: 'danger-button',
    cancelButtonClass: 'cancel-button',
    customClass: 'logout-dialog',
    showClose: true,
    closeOnClickModal: false,
    closeOnPressEscape: false,
    dangerouslyUseHTMLString: true
  }).then(() => {
    logout()
  }).catch(() => {
    // 用户取消操作
  })
}

async function logout() {
  clearCurrentUser()
  currentUser.value = null
  wsService.disconnect()
  router.push('/login')
}
function onAuthChange() { currentUser.value = getCurrentUser(); loadNotifications(); syncRealtimeConnection() }

// 实时推送：登录后建立连接，收到告警事件就刷新通知铃铛
function syncRealtimeConnection() {
  if (currentUser.value) {
    // 连不上由客户端自己退避重连；页面原有的「挂载/路由变化时拉取」不受影响
    wsService.connect().catch(() => {})
  } else {
    wsService.disconnect()
  }
}
function onAlertPush() { loadNotifications() }

watch(() => route.fullPath, () => { currentUser.value = getCurrentUser(); loadNotifications(); syncRealtimeConnection() })
onMounted(() => {
  window.addEventListener('fire-auth-change', onAuthChange)
  wsService.on('alert', onAlertPush)
  loadNotifications()
  syncRealtimeConnection()
})
onUnmounted(() => {
  window.removeEventListener('fire-auth-change', onAuthChange)
  wsService.off('alert', onAlertPush)
  wsService.disconnect()
})
</script>

<style>
:root {
  --fire-bg: #f5f7fb;
  --fire-card: #ffffff;
  --fire-text: #0f172a;
  --fire-muted: #64748b;
  --fire-border: #e2e8f0;
  --fire-blue: #2563eb;
  --fire-red: #ef4444;
  --fire-orange: #f59e0b;
  --fire-green: #22c55e;
}

.global-loading {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(2px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  margin-top: 16px;
  color: #e2e8f0;
  font-size: 14px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
body { margin:0; background:var(--fire-bg); font-family: Arial, 'Microsoft YaHei', sans-serif; color:var(--fire-text); }
.layout { min-height:100vh; }
.data-screen-layout { height:100vh; min-height:100vh; background:#050d1a; }
.data-screen-layout > .el-container { min-width:0; height:100%; }
.data-screen-main { padding:0 !important; height:100vh; min-height:0; overflow:hidden; }
.aside { background:#0f172a; color:#fff; box-shadow:2px 0 16px rgba(15,23,42,.08); overflow:hidden; transition:width .22s cubic-bezier(.4,0,.2,1); }
/* 收起过程中 el-aside 会不断变窄，内层保持原始宽度，避免菜单文字被反复挤压换行（收起动画更平滑） */
.aside > * { width:238px; }
.brand { height:64px; line-height:64px; text-align:center; font-weight:800; font-size:18px; border-bottom:1px solid #1e293b; letter-spacing:.2px; }
.user-panel { display:flex; gap:10px; align-items:center; padding:14px 16px; border-bottom:1px solid #1e293b; }
.avatar { width:38px; height:38px; border-radius:12px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,#2563eb,#60a5fa); color:white; font-weight:800; }
.user-panel strong { display:block; font-size:14px; }
.user-panel p { margin:4px 0 0; color:#94a3b8; font-size:12px; }
.topbar { height:60px; background:white; border-bottom:1px solid var(--fire-border); display:flex; align-items:center; justify-content:space-between; padding:0 22px; }
.topbar strong { font-size:18px; }
.top-subtitle { color:var(--fire-muted); font-size:13px; margin-left:12px; }
.top-actions { display:flex; gap:12px; align-items:center; }

/* 顶栏左侧：侧边栏开关 + 页面标题 */
.topbar-left { display:flex; align-items:center; gap:10px; min-width:0; }
.sidebar-toggle { padding:6px 8px; border-radius:10px; color:#64748b; }
.sidebar-toggle:hover { color:#2563eb; background:#eff6ff; }

/* 退出登录按钮样式优化 */
.top-actions .el-button {
  border-radius: 12px;
  padding: 10px 20px;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.top-actions .el-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.top-actions .el-button:hover::before {
  left: 100%;
}

.top-actions .el-button--text {
  color: #64748b;
  font-weight: 500;
}

.top-actions .el-button--text:hover {
  color: #3b82f6;
  transform: translateY(-1px);
}

.top-actions .el-button--danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  border: none;
  color: white;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
}

.top-actions .el-button--danger:hover {
  background: linear-gradient(135deg, #dc2626, #b91c1c);
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(239, 68, 68, 0.3);
}
.main { padding:22px; }
.page-title { font-size:24px; font-weight:800; margin-bottom:14px; color:var(--fire-text); }
.card, .el-card { border-radius:16px; }
.el-card { border-color:var(--fire-border); box-shadow:0 10px 26px rgba(15,23,42,.045); }
.el-card__header { font-weight:700; }
.el-button { border-radius:10px; }
.el-table { border-radius:12px; overflow:hidden; }
.el-alert { border-radius:12px; }
pre { white-space:pre-wrap; word-break:break-word; }
.notify-summary { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:12px; }
.notify-summary div { background:#f8fafc; border:1px solid var(--fire-border); border-radius:14px; padding:10px; }
.notify-summary span { display:block; color:var(--fire-muted); font-size:12px; }
.notify-summary strong { font-size:22px; }
.drawer-actions { display:flex; gap:8px; margin-bottom:12px; }
.notify-list { display:flex; flex-direction:column; gap:10px; }
.notify-item { border:1px solid var(--fire-border); border-left:4px solid #94a3b8; border-radius:14px; padding:12px; background:#fff; }
.notify-item.danger { border-left-color:var(--fire-red); background:#fffafa; }
.notify-item.warning { border-left-color:var(--fire-orange); background:#fffaf2; }
.notify-item.success { border-left-color:var(--fire-green); }
.notify-top, .notify-foot { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.notify-item p { color:#475569; line-height:1.6; margin:8px 0; }
.notify-foot span { color:#94a3b8; font-size:12px; }

/* 退出登录对话框样式 - 现代化设计 */
.logout-dialog {
  border-radius: 20px !important;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.2) !important;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%) !important;
  border: 1px solid rgba(226, 232, 240, 0.8) !important;
  overflow: hidden !important;
}

.logout-dialog .el-message-box__header {
  padding: 28px 28px 20px 28px;
  border-bottom: 2px solid #f1f5f9;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
}

.logout-dialog .el-message-box__title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 10px;
}

.logout-dialog .el-message-box__title::before {
  content: '🚪';
  font-size: 24px;
  animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-5px); }
  60% { transform: translateY(-3px); }
}

.logout-dialog .el-message-box__content {
  padding: 28px;
  font-size: 16px;
  line-height: 1.7;
  color: #475569;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
}

.logout-dialog .el-message-box__content strong {
  color: #1e293b;
  font-weight: 600;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logout-dialog .el-message-box__btns {
  padding: 20px 28px 28px 28px;
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border-top: 1px solid #f1f5f9;
}

.logout-dialog .el-button {
  border-radius: 12px;
  padding: 12px 24px;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.logout-dialog .el-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  transition: left 0.5s;
}

.logout-dialog .el-button:hover::before {
  left: 100%;
}

.cancel-button {
  background: linear-gradient(135deg, #f8fafc, #e2e8f0) !important;
  border: 2px solid #e2e8f0 !important;
  color: #475569 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
}

.cancel-button:hover {
  background: linear-gradient(135deg, #e2e8f0, #cbd5e1) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1) !important;
}

.danger-button {
  background: linear-gradient(135deg, #ef4444, #dc2626) !important;
  border: none !important;
  color: white !important;
  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.3) !important;
  position: relative;
}

.danger-button:hover {
  background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 10px 25px rgba(239, 68, 68, 0.4) !important;
}

.danger-button:active {
  transform: translateY(0) !important;
  box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3) !important;
}

/* 添加动画效果 */
.logout-dialog .el-message-box {
  animation: slideInScale 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideInScale {
  from {
    opacity: 0;
    transform: translateY(-30px) scale(0.85);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 添加背景装饰 */
.logout-dialog::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.03) 0%, transparent 70%);
  animation: rotate 20s linear infinite;
  z-index: 0;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.logout-dialog .el-message-box__header,
.logout-dialog .el-message-box__content,
.logout-dialog .el-message-box__btns {
  position: relative;
  z-index: 1;
}

@media (max-width: 980px) {
  .aside { width: 210px !important; }
  .top-subtitle { display:none; }
  .main { padding:14px; }
}
</style>
