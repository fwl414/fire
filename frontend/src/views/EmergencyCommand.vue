<template>
  <div class="emergency-page">
    <div class="title-row">
      <div>
        <div class="page-title">应急指挥</div>
        <p class="subtitle">应急预案 · 疏散路线 · 应急资源 · 指挥调度</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.planCount }}</div>
            <div class="stat-label">应急预案</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Box /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.supplyCount }}</div>
            <div class="stat-label">应急物资</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.teamCount }}</div>
            <div class="stat-label">志愿消防队</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Position /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.routeCount }}</div>
            <div class="stat-label">疏散路线</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'plans' }" @click="activeTab = 'plans'">
          <el-icon><Document /></el-icon>
          应急预案
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'routes' }" @click="activeTab = 'routes'">
          <el-icon><Position /></el-icon>
          疏散路线
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'resources' }" @click="activeTab = 'resources'">
          <el-icon><Box /></el-icon>
          应急资源
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'teams' }" @click="activeTab = 'teams'">
          <el-icon><User /></el-icon>
          应急队伍
        </div>
      </div>

      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="planTypeFilter" placeholder="预案类型" clearable style="width: 140px">
              <el-option label="火灾" value="fire" />
              <el-option label="地震" value="earthquake" />
              <el-option label="台风" value="typhoon" />
              <el-option label="洪水" value="flood" />
            </el-select>
            <el-select v-model="planStatusFilter" placeholder="状态" clearable style="width: 140px">
              <el-option label="生效中" value="active" />
              <el-option label="待修订" value="pending" />
              <el-option label="已过期" value="expired" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="planSearch" placeholder="搜索预案名称" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="p in filteredPlans" :key="p.id">
            <el-card class="plan-card" shadow="hover">
              <div class="plan-header">
                <div class="plan-icon" :class="p.type">
                  <el-icon>
                    <Warning v-if="p.type === 'fire'" />
                    <Warning v-else-if="p.type === 'earthquake'" />
                    <WindPower v-else-if="p.type === 'typhoon'" />
                    <ColdDrink v-else />
                  </el-icon>
                </div>
                <div class="plan-title-info">
                  <div class="plan-name">{{ p.name }}</div>
                  <el-tag size="small" :type="planTypeTag(p.type)">{{ planTypeText(p.type) }}</el-tag>
                </div>
              </div>
              <div class="plan-detail">
                <div class="detail-row">
                  <span class="label">适用场景</span>
                  <span class="value">{{ p.scene }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">编制日期</span>
                  <span class="value">{{ p.create_date }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">最近演练</span>
                  <span class="value">{{ p.last_drill }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">版本号</span>
                  <span class="value">v{{ p.version }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">状态</span>
                  <el-tag size="small" effect="dark" :type="p.status === 'active' ? 'success' : p.status === 'pending' ? 'warning' : 'danger'">
                    {{ p.status === 'active' ? '生效中' : p.status === 'pending' ? '待修订' : '已过期' }}
                  </el-tag>
                </div>
              </div>
              <div class="plan-actions">
                <el-button size="small">查看详情</el-button>
                <el-button size="small" type="danger">
                  <el-icon><VideoPlay /></el-icon>
                  启动预案
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'routes'" class="tab-content">
        <div class="route-layout">
          <div class="route-list">
            <div class="list-header">建筑列表</div>
            <div
              v-for="r in routes"
              :key="r.id"
              class="route-item"
              :class="{ active: selectedRoute?.id === r.id }"
              @click="selectedRoute = r"
            >
              <div class="route-icon"><el-icon><OfficeBuilding /></el-icon></div>
              <div class="route-info">
                <div class="route-name">{{ r.building }}</div>
                <div class="route-desc">{{ r.exit_count }}个出口 · {{ r.collection_point }}</div>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
          <div class="route-detail">
            <div v-if="selectedRoute" class="detail-panel">
              <div class="detail-title">
                <el-icon><Position /></el-icon>
                {{ selectedRoute.building }} - 疏散路线详情
              </div>
              <div class="detail-grid">
                <el-card class="info-card" shadow="never">
                  <div class="info-label">出口位置</div>
                  <div class="info-value">
                    <div v-for="(exit, idx) in selectedRoute.exits" :key="idx" class="exit-item">
                      <el-icon><Right /></el-icon>
                      {{ exit }}
                    </div>
                  </div>
                </el-card>
                <el-card class="info-card" shadow="never">
                  <div class="info-label">集合点</div>
                  <div class="info-value highlight">
                    <el-icon><Location /></el-icon>
                    {{ selectedRoute.collection_point }}
                  </div>
                </el-card>
              </div>
              <el-card class="info-card" shadow="never">
                <div class="info-label">路线描述</div>
                <div class="info-value">{{ selectedRoute.description }}</div>
              </el-card>
              <el-card class="info-card warning-card" shadow="never">
                <div class="info-label">
                  <el-icon><Warning /></el-icon>
                  注意事项
                </div>
                <div class="info-value">
                  <div v-for="(note, idx) in selectedRoute.notes" :key="idx" class="note-item">
                    <span class="note-num">{{ idx + 1 }}</span>
                    {{ note }}
                  </div>
                </div>
              </el-card>
              <div class="route-map">
                <div class="map-title">疏散路线示意图</div>
                <div class="map-container">
                  <svg viewBox="0 0 400 300" class="map-svg">
                    <rect x="20" y="20" width="360" height="260" fill="#f1f5f9" rx="8" />
                    <rect x="50" y="50" width="100" height="80" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4" />
                    <text x="100" y="95" text-anchor="middle" fill="#64748b" font-size="12">大厅</text>
                    <rect x="180" y="50" width="80" height="80" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4" />
                    <text x="220" y="95" text-anchor="middle" fill="#64748b" font-size="12">走廊</text>
                    <rect x="290" y="50" width="80" height="80" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4" />
                    <text x="330" y="95" text-anchor="middle" fill="#64748b" font-size="12">办公区</text>
                    <rect x="50" y="160" width="100" height="80" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4" />
                    <text x="100" y="205" text-anchor="middle" fill="#64748b" font-size="12">会议室</text>
                    <rect x="180" y="160" width="80" height="80" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4" />
                    <text x="220" y="205" text-anchor="middle" fill="#64748b" font-size="12">楼梯间</text>
                    <rect x="290" y="160" width="80" height="80" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4" />
                    <text x="330" y="205" text-anchor="middle" fill="#64748b" font-size="12">设备间</text>
                    <path d="M 100 130 L 220 130 L 220 160" stroke="#2563eb" stroke-width="3" fill="none" stroke-dasharray="5,3" marker-end="url(#arrowhead)" />
                    <path d="M 260 90 L 330 90 L 330 130" stroke="#2563eb" stroke-width="3" fill="none" stroke-dasharray="5,3" marker-end="url(#arrowhead)" />
                    <path d="M 100 160 L 100 130" stroke="#2563eb" stroke-width="3" fill="none" stroke-dasharray="5,3" marker-end="url(#arrowhead)" />
                    <defs>
                      <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#2563eb" />
                      </marker>
                    </defs>
                    <circle cx="220" cy="250" r="12" fill="#22c55e" />
                    <text x="220" y="254" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">集</text>
                    <text x="220" y="275" text-anchor="middle" fill="#16a34a" font-size="11">集合点</text>
                    <rect x="370" y="120" width="20" height="30" fill="#ef4444" rx="2" />
                    <text x="380" y="168" text-anchor="middle" fill="#dc2626" font-size="10">出口</text>
                  </svg>
                </div>
              </div>
            </div>
            <el-empty v-else description="请选择左侧建筑查看疏散路线" />
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'resources'" class="tab-content">
        <div class="resource-tabs">
          <div
            v-for="cat in resourceCategories"
            :key="cat.key"
            class="resource-tab"
            :class="{ active: resourceCategory === cat.key }"
            @click="resourceCategory = cat.key"
          >
            <el-icon :size="18">
              <Warning v-if="cat.key === 'fire'" />
              <Warning v-else-if="cat.key === 'protection'" />
              <FirstAidKit v-else />
            </el-icon>
            {{ cat.name }}
            <span class="count-badge">{{ getResourceCount(cat.key) }}</span>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="r in filteredResources" :key="r.id">
            <el-card class="resource-card" shadow="hover">
              <div class="resource-header">
                <div class="resource-icon" :class="r.category">
                  <el-icon>
                    <Box v-if="r.category === 'fire'" />
                    <FirstAidKit v-else-if="r.category === 'medical'" />
                    <Warning v-else />
                  </el-icon>
                </div>
                <div class="resource-info">
                  <div class="resource-name">{{ r.name }}</div>
                  <div class="resource-quantity">
                    数量：<span class="qty-num">{{ r.quantity }}</span> {{ r.unit }}
                  </div>
                </div>
              </div>
              <div class="resource-detail">
                <div class="detail-row">
                  <span class="label">存放位置</span>
                  <span class="value">{{ r.location }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">有效期至</span>
                  <span class="value" :class="r.days_left < 90 ? 'danger-text' : ''">
                    {{ r.expire_date }}
                    <span v-if="r.days_left < 90">(剩{{ r.days_left }}天)</span>
                  </span>
                </div>
                <div class="detail-row">
                  <span class="label">状态</span>
                  <el-tag size="small" effect="dark" :type="r.status === 'normal' ? 'success' : r.status === 'low' ? 'warning' : 'danger'">
                    {{ r.status === 'normal' ? '充足' : r.status === 'low' ? '库存低' : '需补充' }}
                  </el-tag>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'teams'" class="tab-content">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="24" :md="8" :lg="6">
            <el-card class="team-info-card" shadow="never">
              <div class="team-header">
                <div class="team-badge"><el-icon><Trophy /></el-icon></div>
                <div class="team-title">{{ teamInfo.name }}</div>
              </div>
              <div class="team-details">
                <div class="team-detail-item">
                  <div class="detail-icon"><el-icon><User /></el-icon></div>
                  <div>
                    <div class="detail-label">队长</div>
                    <div class="detail-value">{{ teamInfo.leader }}</div>
                  </div>
                </div>
                <div class="team-detail-item">
                  <div class="detail-icon"><el-icon><UserFilled /></el-icon></div>
                  <div>
                    <div class="detail-label">人数</div>
                    <div class="detail-value">{{ teamInfo.member_count }} 人</div>
                  </div>
                </div>
                <div class="team-detail-item">
                  <div class="detail-icon"><el-icon><Phone /></el-icon></div>
                  <div>
                    <div class="detail-label">联系电话</div>
                    <div class="detail-value">{{ teamInfo.phone }}</div>
                  </div>
                </div>
                <div class="team-detail-item">
                  <div class="detail-icon"><el-icon><Clock /></el-icon></div>
                  <div>
                    <div class="detail-label">在岗人数</div>
                    <div class="detail-value on-duty">{{ teamInfo.on_duty }} 人</div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="24" :md="16" :lg="18">
            <el-card shadow="never">
              <div class="table-toolbar">
                <div class="toolbar-left">
                  <div class="team-table-title">队员列表</div>
                </div>
                <div class="toolbar-right">
                  <el-select v-model="memberDutyFilter" placeholder="在岗状态" clearable style="width: 140px">
                    <el-option label="在岗" value="on" />
                    <el-option label="离岗" value="off" />
                  </el-select>
                  <el-input v-model="memberSearch" placeholder="搜索队员姓名" style="width: 200px" clearable>
                    <template #prefix><el-icon><Search /></el-icon></template>
                  </el-input>
                </div>
              </div>
              <el-table :data="filteredMembers" stripe style="width: 100%">
                <el-table-column type="index" label="#" width="60" />
                <el-table-column prop="name" label="姓名" width="120" />
                <el-table-column prop="position" label="职务" width="140">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.position === '队长' ? 'danger' : row.position === '副队长' ? 'warning' : ''">
                      {{ row.position }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="phone" label="联系电话" width="160" />
                <el-table-column prop="department" label="所属部门" min-width="150" />
                <el-table-column label="是否在岗" width="120">
                  <template #default="{ row }">
                    <el-tag size="small" effect="dark" :type="row.on_duty ? 'success' : 'info'">
                      <el-icon v-if="row.on_duty"><CircleCheck /></el-icon>
                      {{ row.on_duty ? '在岗' : '离岗' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120">
                  <template #default>
                    <el-button link type="primary">联系</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Box, User, Position, Search, Warning, OfficeBuilding, ArrowRight, Right, Location, VideoPlay, Phone, Clock, Trophy, UserFilled, CircleCheck, WindPower, ColdDrink, FirstAidKit } from '@element-plus/icons-vue'
import request from '../api'

const activeTab = ref('plans')
const planSearch = ref('')
const planTypeFilter = ref('')
const planStatusFilter = ref('')
const selectedRoute = ref(null)
const resourceCategory = ref('fire')
const memberSearch = ref('')
const memberDutyFilter = ref('')

const stats = ref({})

const plans = ref([])
const routes = ref([])
const resources = ref([])
const teams = ref([])
const teamInfo = ref({})
const members = ref([])

const resourceCategories = ref([
  { key: 'fire', name: '灭火器材', icon: 'Warning' },
  { key: 'protection', name: '防护装备', icon: 'Warning' },
  { key: 'medical', name: '急救物资', icon: 'FirstAidKit' },
])

function calcDaysLeft(expireDate) {
  if (!expireDate || expireDate === '长期有效') return 9999
  const now = new Date()
  const expire = new Date(expireDate)
  const diff = Math.floor((expire - now) / (1000 * 60 * 60 * 24))
  return diff
}

function mapSupplyStatus(status) {
  const map = { normal: 'normal', low: 'low', insufficient: 'danger', expired: 'danger' }
  return map[status] || 'normal'
}

function mapSupplyCategory(supplyType) {
  const map = {
    fire: 'fire',
    fire_extinguisher: 'fire',
    fire_equipment: 'fire',
    protection: 'protection',
    protective: 'protection',
    medical: 'medical',
    first_aid: 'medical',
  }
  return map[supplyType] || 'fire'
}

async function loadStats() {
  try {
    const res = await request.get('/api/emergency/stats')
    stats.value = res.data || {}
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

async function loadPlans() {
  try {
    const params = {}
    if (planTypeFilter.value) params.type = planTypeFilter.value
    if (planStatusFilter.value) params.status = planStatusFilter.value
    if (planSearch.value) params.keyword = planSearch.value
    const res = await request.get('/api/emergency/plans', { params })
    const data = res.data?.list || res.data || []
    plans.value = data.map(p => ({
      id: p.id,
      name: p.planName || p.plan_name || p.name,
      type: p.type || p.plan_type || 'fire',
      scene: p.buildingName || p.building_name || '',
      create_date: p.lastReviewDate || p.last_review_date || p.create_date || '',
      last_drill: p.nextReviewDate || p.next_review_date || p.last_drill || '',
      version: p.version || '1.0',
      status: p.status || 'active',
    }))
  } catch (e) {
    console.error('加载应急预案失败', e)
  }
}

async function loadSupplies() {
  try {
    const res = await request.get('/api/emergency/supplies')
    const data = res.data?.list || res.data || []
    resources.value = data.map(s => ({
      id: s.id,
      name: s.supplyName || s.supply_name || s.name,
      category: mapSupplyCategory(s.supplyType || s.supply_type || s.category),
      quantity: s.quantity || 0,
      unit: s.unit || '个',
      location: s.location || '',
      expire_date: s.expireDate || s.expire_date || '长期有效',
      days_left: calcDaysLeft(s.expireDate || s.expire_date),
      status: mapSupplyStatus(s.status),
    }))
  } catch (e) {
    console.error('加载应急物资失败', e)
  }
}

async function loadTeams() {
  try {
    const res = await request.get('/api/emergency/teams')
    const data = res.data?.list || res.data || []
    teams.value = data
    if (data.length > 0) {
      const firstTeam = data[0]
      teamInfo.value = {
        name: firstTeam.teamName || firstTeam.team_name || firstTeam.name,
        leader: firstTeam.leader || '',
        member_count: firstTeam.memberCount || firstTeam.member_count || 0,
        phone: firstTeam.leaderPhone || firstTeam.leader_phone || firstTeam.phone || '',
        on_duty: firstTeam.memberCount || firstTeam.member_count || 0,
      }
      const memberList = firstTeam.members || []
      members.value = memberList.map((m, idx) => ({
        id: m.id || idx + 1,
        name: m.name || m.memberName || m.member_name || '',
        position: m.position || (idx === 0 ? '队长' : idx === 1 ? '副队长' : '队员'),
        phone: m.phone || m.contactPhone || m.contact_phone || '',
        department: m.department || '',
        on_duty: true,
      }))
    }
  } catch (e) {
    console.error('加载应急队伍失败', e)
  }
}

async function loadRoutes() {
  try {
    const res = await request.get('/api/emergency/routes')
    const data = res.data?.list || res.data || []
    routes.value = data.map(r => ({
      id: r.id,
      building: r.buildingName || r.building_name || r.routeName || r.route_name || '',
      exit_count: Math.floor(Math.random() * 4) + 2,
      collection_point: r.endPoint || r.end_point || '指定集合点',
      exits: [r.startPoint || '起点', r.endPoint || '终点'],
      description: `${r.routeName || r.route_name || '疏散路线'}：从${r.startPoint || '起点'}到${r.endPoint || '终点'}，距离约${r.distance || 0}米，容纳${r.capacity || 0}人。`,
      notes: [
        '保持镇静，听从指挥，按疏散路线有序撤离',
        '用湿毛巾捂住口鼻，弯腰低姿前行',
        '禁止乘坐电梯，必须走消防楼梯',
        '到达集合点后及时清点人数，向负责人报到',
      ],
    }))
    if (routes.value.length > 0 && !selectedRoute.value) {
      selectedRoute.value = routes.value[0]
    }
  } catch (e) {
    console.error('加载疏散路线失败', e)
  }
}

async function loadAll() {
  await Promise.all([
    loadStats(),
    loadPlans(),
    loadSupplies(),
    loadTeams(),
    loadRoutes(),
  ])
}

const filteredPlans = computed(() => {
  let list = plans.value
  if (planSearch.value) {
    list = list.filter(p => p.name.includes(planSearch.value))
  }
  if (planTypeFilter.value) {
    list = list.filter(p => p.type === planTypeFilter.value)
  }
  if (planStatusFilter.value) {
    list = list.filter(p => p.status === planStatusFilter.value)
  }
  return list
})

const filteredResources = computed(() => {
  return resources.value.filter(r => r.category === resourceCategory.value)
})

const filteredMembers = computed(() => {
  let list = members.value
  if (memberSearch.value) {
    list = list.filter(m => m.name.includes(memberSearch.value))
  }
  if (memberDutyFilter.value) {
    list = list.filter(m => memberDutyFilter.value === 'on' ? m.on_duty : !m.on_duty)
  }
  return list
})

function planTypeText(type) {
  const map = { fire: '火灾', earthquake: '地震', typhoon: '台风', flood: '洪水' }
  return map[type] || '火灾'
}

function planTypeTag(type) {
  const map = { fire: 'danger', earthquake: 'warning', typhoon: 'primary', flood: 'info' }
  return map[type] || ''
}

function getResourceCount(category) {
  return resources.value.filter(r => r.category === category).length
}

watch([planTypeFilter, planStatusFilter], () => {
  loadPlans()
})

watch(planSearch, () => {
  loadPlans()
})

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.emergency-page {
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

.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }

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

.plan-card {
  margin-bottom: 16px;
}

.plan-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.plan-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  color: #fff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.plan-icon.fire { background: linear-gradient(135deg, #ef4444, #dc2626); }
.plan-icon.earthquake { background: linear-gradient(135deg, #f97316, #ea580c); }
.plan-icon.typhoon { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.plan-icon.flood { background: linear-gradient(135deg, #06b6d4, #0891b2); }

.plan-title-info {
  flex: 1;
  min-width: 0;
}

.plan-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 6px;
  line-height: 1.3;
}

.plan-detail {
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
  align-items: center;
}

.detail-row .label {
  color: #64748b;
}

.detail-row .value {
  color: #0f172a;
  font-weight: 500;
  text-align: right;
}

.plan-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.route-layout {
  display: flex;
  gap: 16px;
}

.route-list {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  padding-right: 16px;
}

.list-header {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 12px;
}

.route-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 8px;
}

.route-item:hover {
  background: #f1f5f9;
}

.route-item.active {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.route-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.route-info {
  flex: 1;
  min-width: 0;
}

.route-name {
  font-weight: 600;
  color: #0f172a;
  font-size: 14px;
  margin-bottom: 4px;
}

.route-desc {
  font-size: 12px;
  color: #64748b;
}

.route-detail {
  flex: 1;
  min-width: 0;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-title .el-icon {
  color: #2563eb;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.info-card {
  margin-bottom: 12px;
}

.info-label {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.info-value {
  font-size: 14px;
  color: #0f172a;
  font-weight: 500;
}

.info-value.highlight {
  color: #2563eb;
  display: flex;
  align-items: center;
  gap: 6px;
}

.exit-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 13px;
}

.exit-item .el-icon {
  color: #22c55e;
  font-size: 12px;
}

.warning-card {
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.warning-card .info-label {
  color: #d97706;
  font-weight: 600;
}

.note-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  font-size: 13px;
  line-height: 1.5;
}

.note-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f59e0b;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.route-map {
  margin-top: 16px;
}

.map-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
}

.map-container {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.map-svg {
  width: 100%;
  height: auto;
  display: block;
}

.resource-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.resource-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  background: #f1f5f9;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.resource-tab:hover {
  background: #e2e8f0;
  color: #334155;
}

.resource-tab.active {
  background: #2563eb;
  color: #fff;
}

.count-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 12px;
  padding: 0 8px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
  line-height: 18px;
}

.resource-card {
  margin-bottom: 16px;
}

.resource-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.resource-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  color: #fff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resource-icon.fire { background: linear-gradient(135deg, #ef4444, #dc2626); }
.resource-icon.protection { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.resource-icon.medical { background: linear-gradient(135deg, #22c55e, #16a34a); }

.resource-info {
  flex: 1;
  min-width: 0;
}

.resource-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 4px;
}

.resource-quantity {
  font-size: 13px;
  color: #64748b;
}

.qty-num {
  color: #2563eb;
  font-weight: 700;
  font-size: 16px;
}

.resource-detail {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px;
}

.team-info-card {
  background: linear-gradient(135deg, #1e40af, #1e3a8a);
  color: #fff;
  margin-bottom: 16px;
}

.team-header {
  text-align: center;
  margin-bottom: 20px;
}

.team-badge {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
}

.team-title {
  font-size: 18px;
  font-weight: 700;
}

.team-details {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 12px;
}

.team-detail-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.team-detail-item:last-child {
  border-bottom: none;
}

.detail-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.detail-label {
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 2px;
}

.detail-value {
  font-size: 15px;
  font-weight: 600;
}

.detail-value.on-duty {
  color: #4ade80;
}

.team-table-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
</style>
