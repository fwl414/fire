<template>
  <div class="data-screen">
    <div class="screen-header">
      <div class="header-left">
        <div class="time-display">
          <span class="date">{{ currentDate }}</span>
          <span class="time">{{ currentTime }}</span>
          <span class="weekday">{{ currentWeekday }}</span>
        </div>
      </div>
      <div class="header-title">
        <div class="title-main">
          <span class="decor left"></span>
          智慧消防综合指挥平台
          <span class="decor right"></span>
        </div>
      </div>
      <div class="header-right">
        <div class="alarm-brief">
          <el-icon><Bell /></el-icon>
          <span>今日告警 {{ todayAlarms }} 起</span>
        </div>
        <div class="system-status">
          <span class="status-dot" :class="{ 'status-dot-warn': onlineRate < 90 }"></span>
          设备在线率 {{ onlineRate }}%
        </div>
        <el-button class="ai-analyst-btn" type="primary" @click="showAIPanel = true">
          <el-icon><ChatDotRound /></el-icon>
          智能分析师
        </el-button>
      </div>
    </div>

    <div class="screen-toolbar">
      <nav class="screen-nav">
        <el-button class="screen-nav-item active" text @click="router.push('/dashboard')">综合态势</el-button>
        <el-button class="screen-nav-item" text @click="router.push('/alert-center')">
          告警中心
          <span v-if="todayAlarms" class="nav-badge">{{ todayAlarms }}</span>
        </el-button>
        <el-button class="screen-nav-item" text @click="router.push('/inspection')">巡检任务</el-button>
        <el-button class="screen-nav-item" text @click="router.push('/hazard-management')">隐患治理</el-button>
        <el-dropdown v-for="group in navGroups" :key="group.label" trigger="click" class="nav-group" @command="(path) => router.push(path)">
          <el-button class="screen-nav-item" text>{{ group.label }}<el-icon><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="item in group.items" :key="item.path" :command="item.path">
                <span class="nav-menu-icon"><el-icon><component :is="item.icon" /></el-icon></span>
                <span>{{ item.label }}</span>
                <small>{{ item.hint }}</small>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>
      <div class="toolbar-tip">实时数据 · 30秒自动刷新</div>
    </div>

    <div
      class="screen-body"
      v-loading="showLoadingMask"
      element-loading-text="正在加载实时数据"
      element-loading-background="rgba(5, 13, 26, 0.7)"
    >
      <div class="screen-col left">
        <div class="panel">
          <div class="panel-header">
            <el-icon><Odometer /></el-icon>
            <span>设备运行概览</span>
          </div>
          <div class="panel-body">
            <div class="device-stats-row">
              <div class="device-stat-item">
                <div class="stat-num">{{ totalDevices }}</div>
                <div class="stat-label">设备总数</div>
              </div>
              <div class="device-stat-item online">
                <div class="stat-num">{{ onlineDevices }}</div>
                <div class="stat-label">在线</div>
              </div>
              <div class="device-stat-item offline">
                <div class="stat-num">{{ offlineDevices }}</div>
                <div class="stat-label">离线</div>
              </div>
            </div>
            <div class="device-type-list">
              <div v-for="t in deviceTypes" :key="t.name" class="device-type-item">
                <span class="type-name">{{ t.name }}</span>
                <div class="type-bar">
                  <div class="type-fill" :style="{ width: t.percent + '%', background: t.color }"></div>
                </div>
                <span class="type-count">{{ t.count }}</span>
              </div>
              <div v-if="!deviceTypes.length" class="panel-empty">暂无设备数据</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><Warning /></el-icon>
            <span>告警统计</span>
          </div>
          <div class="panel-body">
            <div class="alarm-level-row">
              <div class="alarm-level-item critical">
                <div class="level-num">{{ alarmStats.critical }}</div>
                <div class="level-label">严重告警</div>
              </div>
              <div class="alarm-level-item high">
                <div class="level-num">{{ alarmStats.high }}</div>
                <div class="level-label">高危告警</div>
              </div>
              <div class="alarm-level-item medium">
                <div class="level-num">{{ alarmStats.medium }}</div>
                <div class="level-label">中危告警</div>
              </div>
              <div class="alarm-level-item low">
                <div class="level-num">{{ alarmStats.low }}</div>
                <div class="level-label">低危告警</div>
              </div>
            </div>
            <div class="alarm-trend">
              <div class="trend-title">近7日告警趋势</div>
              <div v-if="alarmTrend.length" class="trend-chart">
                <div v-for="d in alarmTrend" :key="d.date" class="trend-bar-wrap">
                  <div class="trend-bar">
                    <div class="bar-fill" :style="{ height: d.percent + '%' }"></div>
                  </div>
                  <span class="trend-date">{{ d.date }}</span>
                </div>
              </div>
              <div v-else class="panel-empty">暂无告警趋势数据</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><TrendCharts /></el-icon>
            <span>隐患治理</span>
          </div>
          <div class="panel-body">
            <div class="hazard-stats">
              <div class="hazard-item">
                <div class="hazard-ring">
                  <svg viewBox="0 0 36 36" class="circular-chart">
                    <path class="circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                    <path class="circle" :stroke-dasharray="`${hazardStats.rate}, 100`" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                    <text x="18" y="20.35" class="percentage">{{ hazardStats.rate }}%</text>
                  </svg>
                </div>
                <div class="hazard-info">
                  <div class="hazard-label">整改完成率</div>
                  <div class="hazard-desc">累计共 {{ hazardStats.total }} 项隐患</div>
                </div>
              </div>
            </div>
            <div class="hazard-type-list">
              <div v-for="h in hazardTypes" :key="h.name" class="hazard-type-item">
                <span class="dot" :style="{ background: h.color }"></span>
                <span class="name">{{ h.name }}</span>
                <span class="num">{{ h.count }}项</span>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><OfficeBuilding /></el-icon>
            <span>建筑分布</span>
          </div>
          <div class="panel-body">
            <div class="building-list">
              <div v-for="b in buildings.slice(0, 5)" :key="b.id" class="building-item" @click="selectBuilding(b)">
                <div class="building-info">
                  <span class="building-name">{{ b.building_name || b.name }}</span>
                  <span class="building-status" :class="getBuildingStatusClass(b)">{{ getBuildingStatus(b) }}</span>
                </div>
                <div class="building-detail">
                  <span>{{ b.deviceCount || b.device_count || 0 }} 台设备</span>
                  <span>{{ b.floors || b.floor_count || 0 }} 层</span>
                </div>
              </div>
              <el-empty v-if="!buildings.length" description="暂无建筑数据" :image-size="50" />
            </div>
          </div>
        </div>
      </div>

      <div class="screen-col center">
        <div class="gis-panel">
          <div class="gis-header">
            <div class="gis-tabs">
              <span class="gis-tab" :class="{ active: mapMode === '3d' }" @click="switchMapMode('3d')">3D GIS地图</span>
              <span class="gis-tab" :class="{ active: mapMode === 'heat' }" @click="switchMapMode('heat')">热力图</span>
              <span class="gis-tab" :class="{ active: mapMode === 'device' }" @click="switchMapMode('device')">设备分布</span>
            </div>
            <div class="gis-header-right">
              <div class="gis-legend">
                <span v-for="item in BUILDING_STATUS_LEGEND" :key="item.key">
                  <i class="legend-dot" :style="{ background: item.color }"></i>{{ item.label }}
                </span>
              </div>
              <div class="gis-tools">
                <el-button size="small" text @click="resetView">复位视角</el-button>
                <el-button size="small" text @click="toggleFullscreen">全屏</el-button>
              </div>
            </div>
          </div>
          <div class="gis-container" ref="gisContainerRef" :class="{ 'hide-webgl': mapMode !== '3d' }">
            <canvas ref="heatmapCanvasRef" class="map-canvas-layer" v-show="mapMode === 'heat'"></canvas>
            <canvas ref="deviceMapCanvasRef" class="map-canvas-layer" v-show="mapMode === 'device'"></canvas>
            <div class="gis-stats-overlay">
              <div class="gis-stat">
                <span class="gis-stat-num">{{ buildings.length }}</span>
                <span class="gis-stat-label">建筑</span>
              </div>
              <div class="gis-stat">
                <span class="gis-stat-num">{{ totalDevices }}</span>
                <span class="gis-stat-label">设备</span>
              </div>
              <div class="gis-stat">
                <span class="gis-stat-num">{{ todayAlarms }}</span>
                <span class="gis-stat-label">今日告警</span>
              </div>
            </div>
          </div>
        </div>

        <div class="center-bottom-panels">
          <div class="panel small">
            <div class="panel-header">
              <el-icon><Watermelon /></el-icon>
              <span>消防水源</span>
            </div>
            <div class="panel-body">
              <div class="water-mini-stats">
                <div class="water-mini-item">
                  <span class="water-val green">{{ waterSystem.runningPumps ?? '--' }}<span class="unit">台</span></span>
                  <span class="water-label">运行泵</span>
                </div>
                <div class="water-mini-item">
                  <span class="water-val">{{ waterSystem.online ?? '--' }}/{{ waterSystem.total ?? '--' }}</span>
                  <span class="water-label">在线水源设备</span>
                </div>
                <div class="water-mini-item">
                  <span class="water-val" :class="{ warning: waterSystem.offline > 0 }">{{ waterSystem.offline ?? '--' }}<span class="unit">台</span></span>
                  <span class="water-label">离线</span>
                </div>
              </div>
            </div>
          </div>
          <div class="panel small">
            <div class="panel-header">
              <el-icon><Lightning /></el-icon>
              <span>电气火灾</span>
            </div>
            <div class="panel-body">
              <div class="electric-mini-stats">
                <div class="electric-mini-item">
                  <span class="electric-val">{{ electricSystem.maxTemp ?? '--' }}<span class="unit">°C</span></span>
                  <span class="electric-label">最高温度</span>
                </div>
                <div class="electric-mini-item">
                  <span class="electric-val warning">{{ electricSystem.warningCircuits ?? '--' }}<span class="unit">路</span></span>
                  <span class="electric-label">异常设备</span>
                </div>
                <div class="electric-mini-item">
                  <span class="electric-val">{{ electricSystem.online ?? '--' }}/{{ electricSystem.total ?? '--' }}</span>
                  <span class="electric-label">在线电气设备</span>
                </div>
              </div>
            </div>
          </div>
          <div class="panel small">
            <div class="panel-header">
              <el-icon><User /></el-icon>
              <span>值班信息</span>
            </div>
            <div class="panel-body">
              <div class="duty-mini-info">
                <div class="duty-shift">
                  <el-tag :type="dutyInfo.hasDuty ? 'success' : 'info'" effect="dark" size="small">
                    {{ dutyInfo.shift || '暂无值班信息' }}
                  </el-tag>
                  <span v-if="dutyInfo.period" class="duty-period">{{ dutyInfo.period }}</span>
                </div>
                <div class="duty-persons">
                  <span v-for="(p, idx) in dutyInfo.persons" :key="idx">{{ p }}</span>
                  <span v-if="!dutyInfo.persons || dutyInfo.persons.length === 0" class="duty-empty">暂无值班人员</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="screen-col right">
        <div class="panel alarm-scroll-panel">
          <div class="panel-header">
            <el-icon><Bell /></el-icon>
            <span>实时告警</span>
            <span class="alarm-badge">{{ realtimeAlarms.length }}</span>
          </div>
          <div class="panel-body">
            <div class="alarm-scroll-list">
              <div
                v-for="a in realtimeAlarms"
                :key="a.id"
                class="alarm-scroll-item is-clickable"
                :class="a.level"
                @click="drillTo('/alert-center', '告警中心')"
              >
                <div class="alarm-icon">
                  <el-icon><WarningFilled /></el-icon>
                </div>
                <div class="alarm-content">
                  <div class="alarm-title">{{ a.title }}</div>
                  <div class="alarm-location">{{ a.location }}</div>
                  <div class="alarm-time">{{ a.time }}</div>
                </div>
                <div class="alarm-level-badge" :class="a.level">
                  {{ a.levelText }}
                </div>
              </div>
              <div v-if="!realtimeAlarms.length" class="panel-empty">暂无实时告警</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><List /></el-icon>
            <span>待办事项</span>
          </div>
          <div class="panel-body">
            <div class="todo-list">
              <div
                v-for="todo in todoList"
                :key="todo.id"
                class="todo-item is-clickable"
                @click="drillTo(`/workorders?order_id=${todo.id}`, '整改工单')"
              >
                <div class="todo-icon" :class="todo.level === 'high' ? 'urgent' : 'pending'">
                  <el-icon><Tools /></el-icon>
                </div>
                <div class="todo-content">
                  <div class="todo-title">{{ todo.title }}</div>
                  <div class="todo-desc">
                    {{ [todo.location, todo.deadline ? '截止 ' + todo.deadline : ''].filter(Boolean).join(' · ') || '—' }}
                  </div>
                </div>
                <span class="todo-status" :class="todo.level === 'high' ? 'urgent' : 'pending'">{{ todo.status }}</span>
              </div>
              <div v-if="todoList.length === 0" class="panel-empty">暂无待办工单</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><TrendCharts /></el-icon>
            <span>风险排名</span>
          </div>
          <div class="panel-body">
            <div class="rank-list">
              <div
                v-for="(item, idx) in riskRank"
                :key="item.id ?? item.name"
                class="rank-item"
                :class="{ 'is-clickable': item.id }"
                @click="item.id && drillTo(`/building-detail/${item.id}`, '建筑档案')"
              >
                <span class="rank-num" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</span>
                <span class="rank-name">{{ item.name }}</span>
                <div class="rank-bar">
                  <div class="rank-fill" :style="{ width: Math.min(item.value, 100) + '%', background: item.color }"></div>
                </div>
                <span class="rank-value">{{ item.value }}</span>
              </div>
              <div v-if="riskRank.length === 0" class="panel-empty">暂无建筑风险数据</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><VideoCamera /></el-icon>
            <span>重点区域视频</span>
          </div>
          <div class="panel-body">
            <div v-if="videoList.length" class="video-grid">
              <div
                v-for="v in videoList"
                :key="v.id"
                class="video-mini-item is-clickable"
                :class="{ offline: !v.online }"
                @click="drillTo('/video-monitor', '视频监控')"
              >
                <div class="video-thumbnail">
                  <img
                    v-if="v.snapshotUrl && v.online"
                    :src="v.snapshotUrl"
                    alt=""
                    class="video-frame"
                    @error="onVideoFrameError(v)"
                  >
                  <el-icon v-else class="video-icon"><VideoCamera /></el-icon>
                  <span v-if="!v.online" class="video-offline-tip">离线</span>
                </div>
                <div class="video-name">{{ v.name }}</div>
              </div>
            </div>
            <div v-else class="panel-empty">暂无视频通道</div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><List /></el-icon>
            <span>今日事件</span>
          </div>
          <div class="panel-body">
            <div class="event-timeline">
              <div
                v-for="e in todayEvents"
                :key="e.id"
                class="event-item is-clickable"
                :class="e.type"
                @click="openEvent(e)"
              >
                <div class="event-dot"></div>
                <div class="event-content">
                  <div class="event-title">{{ e.title }}</div>
                  <div class="event-time">{{ e.time }}</div>
                </div>
              </div>
              <div v-if="!todayEvents.length" class="panel-empty">今日暂无事件</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <el-icon><DataBoard /></el-icon>
            <span>运行指标</span>
          </div>
          <div class="panel-body">
            <div class="indicator-list">
              <div v-for="ind in indicators" :key="ind.name" class="indicator-item">
                <div class="indicator-header">
                  <span class="indicator-name">{{ ind.name }}</span>
                  <span class="indicator-value" :class="ind.status">{{ ind.value }}{{ ind.unit }}</span>
                </div>
                <div class="indicator-bar">
                  <div class="indicator-fill" :style="{ width: ind.percent + '%' }" :class="ind.status"></div>
                </div>
              </div>
              <div v-if="!indicators.length" class="panel-empty">暂无运行指标</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="screen-footer">
      <div class="footer-info">
        <span>数据更新时间：{{ lastUpdateTime || '--' }}</span>
        <span class="footer-divider">|</span>
        <span>数据来源：智慧消防物联网平台</span>
        <span v-if="loadError" class="footer-error">
          数据加载失败，当前展示的是上一次成功获取的数据（{{ loadError }}）
        </span>
      </div>
    </div>
    <el-drawer v-model="showAIPanel" direction="rtl" size="420px" class="screen-ai-drawer">
      <div class="ai-analyst-container">
        <div class="ai-analyst-header">
          <div class="ai-header-left">
            <div class="ai-avatar">
              <el-icon :size="22"><ChatDotRound /></el-icon>
            </div>
            <div>
              <div class="ai-title">数据分析师</div>
              <div class="ai-subtitle">自然语言查询 · 智能数据分析</div>
            </div>
          </div>
          <el-button text @click="showAIPanel = false">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>

        <div class="quick-questions">
          <div class="qq-title">快速提问</div>
          <div class="qq-grid">
            <div class="qq-item" @click="askAI('今日告警有多少？')">今日告警</div>
            <div class="qq-item" @click="askAI('哪个区域告警最多？')">告警最多区域</div>
            <div class="qq-item" @click="askAI('设备在线率是多少？')">设备在线率</div>
            <div class="qq-item" @click="askAI('当前有多少隐患？')">隐患统计</div>
          </div>
        </div>

        <div class="ai-chat-area" ref="aiChatRef">
          <div v-for="(msg, idx) in aiMessages" :key="idx" class="ai-msg-item" :class="msg.role">
            <div v-if="msg.role === 'assistant'" class="ai-msg-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="ai-msg-bubble">
              <div v-if="msg.type === 'typing'" class="ai-typing">
                <span></span><span></span><span></span>
              </div>
              <div v-else class="ai-msg-content">
                <p>{{ msg.content }}</p>
                <div v-if="msg.data" class="msg-data-preview">
                  <el-tag size="small" type="info">数据已更新</el-tag>
                </div>
                <div v-if="msg.relatedQuestions && msg.relatedQuestions.length" class="msg-related">
                  <div class="mr-title">相关问题：</div>
                  <div class="mr-tags">
                    <el-tag 
                      v-for="(q, qi) in msg.relatedQuestions" 
                      :key="qi" 
                      size="small" 
                      effect="plain"
                      class="mr-tag"
                      @click="askAI(q)"
                    >
                      {{ q }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="ai-input-area">
          <el-input
            v-model="aiInputText"
            placeholder="输入问题，如：今日告警趋势如何？"
            @keydown.enter.ctrl="sendAIQuestion"
            clearable
          >
            <template #append>
              <el-button type="primary" :loading="aiSending" @click="sendAIQuestion">
                发送
              </el-button>
            </template>
          </el-input>
          <div class="input-hint">Ctrl+Enter 快捷发送</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Odometer, Warning, TrendCharts, OfficeBuilding,
  Watermelon, Lightning, User, Bell, WarningFilled,
  VideoCamera, List, DataBoard, ChatDotRound,
  ArrowDown,
  Close,
  Tools
} from '@element-plus/icons-vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { getDataScreenData } from '@/api/overview'
import { queryData } from '@/api/intelligence'
import { videoSnapshotToken } from '@/api/video'
import { getCurrentUser, canAccessRoute } from '@/auth'
import { wsService } from '@/utils/websocket'

const router = useRouter()
const gisContainerRef = ref(null)
const heatmapCanvasRef = ref(null)
const deviceMapCanvasRef = ref(null)
const mapMode = ref('3d')
const loading = ref(false)
let animationId = null
let clockTimer = null
let dataTimer = null
let videoFrameTimer = null
let videoTokenTimer = null
let scene = null
let camera = null
let renderer = null
let controls = null
let alarmMarkers = []
let deviceDots = []
// 已渲染场景对应的建筑台账指纹，用于判断是否需要重建
let renderedBuildingSignature = ''

// 3D 建筑点击下钻：只对建筑的大块（底座 / 楼体 / 屋顶）做射线检测，
// 不递归到窗格 —— 每栋楼的窗格有上百个面片，点击时遍历它们会很慢
const raycaster = new THREE.Raycaster()
const pointerNdc = new THREE.Vector2()
let buildingHitMeshes = []
// 拖动旋转视角后的松手不应算作点击
let pointerDownAt = null

const currentDate = ref('')
const currentTime = ref('')
const currentWeekday = ref('')
const lastUpdateTime = ref('')

const navGroups = [
  {
    label: '实时监测',
    items: [
      { label: '设备监测', hint: '设备状态与数据', path: '/devices', icon: DataBoard },
      { label: '消防水源', hint: '水压与水池', path: '/water-monitor', icon: Watermelon },
      { label: '电气火灾', hint: '漏电与温度', path: '/electrical-fire', icon: Lightning },
      { label: '视频监控', hint: '重点区域画面', path: '/video-monitor', icon: VideoCamera },
    ],
  },
  {
    label: '处置协同',
    items: [
      { label: '应急指挥', hint: '预案与应急资源', path: '/emergency-command', icon: Bell },
      { label: '维保工单', hint: '设施维保与工单', path: '/maintenance', icon: Tools },
      { label: '值班管理', hint: '值守与交接班', path: '/duty-room', icon: User },
    ],
  },
  {
    label: '分析管理',
    items: [
      { label: '建筑风险', hint: '风险分级与排名', path: '/building-risk', icon: TrendCharts },
      { label: '统计报表', hint: '趋势与分析报告', path: '/report-center', icon: DataBoard },
      { label: '消防档案', hint: '单位与建筑档案', path: '/fire-archives', icon: OfficeBuilding },
    ],
  },
]

const totalDevices = ref(0)
const onlineDevices = ref(0)
const offlineDevices = ref(0)
const todayAlarms = ref(0)

const deviceTypes = ref([])

const alarmStats = ref({
  critical: 0,
  high: 0,
  medium: 0,
  low: 0,
})

const alarmTrend = ref([])

const hazardStats = ref({
  total: 0,
  rate: 0,
})

const hazardTypes = ref([])

const buildings = ref([])

const todoList = ref([])

const riskRank = ref([])

// 加载失败时不再用编造的数字兜底，只提示状态并保留上一次成功的数据
const loadError = ref('')

// 只在「一次数据都没成功拿到过」时盖遮罩：30 秒轮询刷新如果再盖一层，
// 大屏会周期性闪一下，看起来像故障。
// `lastUpdateTime` 只在成功取到数据时赋值，可以当作「是否加载过」的标志
const showLoadingMask = computed(() => loading.value && !lastUpdateTime.value)

const onlineRate = computed(() => {
  const item = indicators.value.find(i => i.name === '设备在线率')
  return item ? item.value : 0
})

// 建筑状态色：后端 building_list[].status 只取 normal / warning / alarm
const BUILDING_STATUS_COLORS = {
  normal: '#0088cc',
  warning: '#cc7700',
  alarm: '#cc3333',
}

const BUILDING_STATUS_HEX = {
  normal: 0x0088cc,
  warning: 0xcc7700,
  alarm: 0xcc3333,
}

// GIS 图例直接从上面的状态色生成，避免图例与 3D/Canvas 各写一套颜色而对不上。
// 建筑只有 normal / warning / alarm 三态（没有「离线」），因此图例也只列这三项。
const BUILDING_STATUS_LEGEND = [
  { key: 'normal', label: '正常' },
  { key: 'warning', label: '预警' },
  { key: 'alarm', label: '告警' },
].map(item => ({ ...item, color: BUILDING_STATUS_COLORS[item.key] }))

// 场景尺度：最远的建筑映射到该半径，未录经纬度的建筑放在同半径的环形上
const LAYOUT_RADIUS = 55
// 每度纬度约 111.32 km
const METERS_PER_DEGREE = 111320

// 大屏的 3D 场景 / 热力图 / 设备分布图统一使用后端真实建筑台账。
// 后端只下发经纬度，这里换算到场景与画布坐标：
// - 经纬度**都**为 0 才算「未定位」；中心点与缩放比例只由已定位的建筑决定，
//   否则一栋未定位的建筑会被映射到离园区很远的位置
// - 经度要按 cos(纬度) 折算成与纬度同量纲，否则园区会被横向拉伸
//   （同一区域内经度跨度通常远大于纬度跨度，之前两者混在一起取最大值，纬度方向被压扁）
// - 未定位的建筑放到同半径的环形上，不会与已定位的建筑挤在一起
// 建筑的位置、数量、体量都是确定性的（同一份数据每次渲染位置一致）；
// 场景里的窗灯明暗与呼吸动画用到随机数，但那只是观感装饰，不影响数据呈现。
const buildingLayout = computed(() => {
  const list = buildings.value || []
  if (!list.length) return []

  const geo = list.map(b => {
    const lat = Number(b.latitude) || 0
    const lon = Number(b.longitude) || 0
    return lat || lon ? { lat, lon } : null
  })
  const located = geo.filter(Boolean)

  let centerLat = 0
  let centerLon = 0
  let cosLat = 1
  let scale = 0
  if (located.length) {
    centerLat = located.reduce((sum, g) => sum + g.lat, 0) / located.length
    centerLon = located.reduce((sum, g) => sum + g.lon, 0) / located.length
    cosLat = Math.cos((centerLat * Math.PI) / 180)
    const farthest = located.reduce((max, g) => {
      const dx = (g.lon - centerLon) * METERS_PER_DEGREE * cosLat
      const dz = (g.lat - centerLat) * METERS_PER_DEGREE
      return Math.max(max, Math.hypot(dx, dz))
    }, 0)
    scale = farthest > 0 ? LAYOUT_RADIUS / farthest : 0
  }

  return list.map((b, i) => {
    const angle = (i / list.length) * Math.PI * 2
    let x
    let z
    if (geo[i] && scale) {
      x = (geo[i].lon - centerLon) * METERS_PER_DEGREE * cosLat * scale
      z = (geo[i].lat - centerLat) * METERS_PER_DEGREE * scale
    } else {
      // 未录经纬度（或所有建筑都在同一坐标）：按序号等距环形排布
      x = Math.cos(angle) * LAYOUT_RADIUS
      z = Math.sin(angle) * LAYOUT_RADIUS
    }

    const floors = Number(b.floors) || 1
    const area = Number(b.area) || 0
    const footprint = area > 0 ? Math.min(Math.max(Math.sqrt(area) / 4, 9), 24) : 14

    return {
      id: b.id,
      name: b.name,
      type: b.type || 'office',
      status: BUILDING_STATUS_COLORS[b.status] ? b.status : 'normal',
      deviceCount: Number(b.deviceCount) || 0,
      alarmCount: Number(b.alarmCount) || 0,
      riskScore: Number(b.riskScore) || 0,
      floors,
      area,
      x,
      z,
      // 归一化画布坐标（热力图 / 设备分布图用），四周留边距
      nx: Math.min(Math.max(0.5 + (x / 70) * 0.34, 0.06), 0.94),
      ny: Math.min(Math.max(0.5 + (z / 70) * 0.34, 0.08), 0.92),
      w: footprint,
      d: footprint * 0.8,
      h: Math.min(Math.max(floors * 3, 8), 60),
    }
  })
})

const realtimeAlarms = ref([])

const videoList = ref([])

const todayEvents = ref([])

const indicators = ref([])

// 未加载到数据前显示 --，而不是 0（0 会被误读成「一台设备都没有」）
const waterSystem = ref({
  runningPumps: null,
  online: null,
  total: null,
  offline: null,
})

const electricSystem = ref({
  maxTemp: null,
  warningCircuits: null,
  online: null,
  total: null,
})

const dutyInfo = ref({
  shift: '',
  persons: [],
})

const showAIPanel = ref(false)
const aiInputText = ref('')
const aiSending = ref(false)
const aiChatRef = ref(null)
const aiMessages = ref([
  {
    role: 'assistant',
    type: 'text',
    content: '您好！我是数据分析师，可以为您查询告警、设备、隐患等数据。试试点击下方快速提问，或直接输入您的问题。',
  },
])

function scrollAIChat() {
  nextTick(() => {
    if (aiChatRef.value) {
      aiChatRef.value.scrollTop = aiChatRef.value.scrollHeight
    }
  })
}

function askAI(question) {
  aiInputText.value = question
  sendAIQuestion()
}

async function sendAIQuestion() {
  const text = aiInputText.value.trim()
  if (!text || aiSending.value) return

  aiMessages.value.push({
    role: 'user',
    type: 'text',
    content: text,
  })
  aiInputText.value = ''
  scrollAIChat()

  aiMessages.value.push({
    role: 'assistant',
    type: 'typing',
  })
  scrollAIChat()

  try {
    aiSending.value = true
    const res = await queryData(text)
    // 数据问答接口外层是 { ok, data }：以前只取到信封，回答内容全是 undefined
    const data = res.data?.data || {}

    aiMessages.value.pop()
    aiMessages.value.push({
      role: 'assistant',
      type: 'text',
      content: data.answer_text,
      data: data.result_data,
      relatedQuestions: data.related_questions,
    })
  } catch (e) {
    aiMessages.value.pop()
    aiMessages.value.push({
      role: 'assistant',
      type: 'text',
      content: '抱歉，暂时无法回答您的问题，请稍后重试。',
    })
  } finally {
    aiSending.value = false
    scrollAIChat()
  }
}

async function loadScreenData() {
  try {
    loading.value = true
    const res = await getDataScreenData()
    const data = res.data

    if (data.devices) {
      totalDevices.value = data.devices.total || 0
      onlineDevices.value = data.devices.online || 0
      offlineDevices.value = data.devices.offline || 0
      deviceTypes.value = data.devices.types || []
    }

    if (data.alarms) {
      if (data.alarms.stats) {
        alarmStats.value = {
          critical: data.alarms.stats.critical || 0,
          high: data.alarms.stats.high || 0,
          medium: data.alarms.stats.medium || 0,
          low: data.alarms.stats.low || 0,
        }
        todayAlarms.value = data.alarms.stats.today || 0
      }
      alarmTrend.value = data.alarms.trend || []
      realtimeAlarms.value = data.alarms.realtime || []
    }

    if (data.buildings) {
      buildings.value = data.buildings.list || []
    }

    if (data.hazards) {
      hazardStats.value = {
        total: data.hazards.total || 0,
        rate: data.hazards.rate || 0,
      }
      hazardTypes.value = data.hazards.types || []
    }

    if (data.waterSystem) {
      waterSystem.value = data.waterSystem
    }

    if (data.electricSystem) {
      electricSystem.value = data.electricSystem
    }

    if (data.dutyInfo) {
      dutyInfo.value = data.dutyInfo
    }

    if (data.videoList) {
      // 30 秒轮询会整份替换 videoList：把已签发的令牌与画面按 id 继承过来，
      // 否则每次都要重新签令牌，画面还会闪一下
      const previous = new Map(videoList.value.map(item => [item.id, item]))
      videoList.value = data.videoList.map(item => {
        const old = previous.get(item.id)
        return old ? { ...item, token: old.token, snapshotUrl: old.snapshotUrl } : item
      })
      ensureVideoTokens()
      tickVideoFrames()
    }

    if (data.todayEvents) {
      todayEvents.value = data.todayEvents
    }

    if (data.indicators) {
      indicators.value = data.indicators
    }

    if (data.todos) {
      todoList.value = data.todos
    }

    if (data.riskRank) {
      riskRank.value = data.riskRank
    }

    loadError.value = ''
    updateLastUpdateTime()
    // 建筑台账（或建筑状态/设备数）变化时，按新数据重建 3D 场景与二维视图
    rebuild3DScene()
    if (mapMode.value === 'heat') drawHeatmap()
    if (mapMode.value === 'device') drawDeviceMap()
  } catch (e) {
    // 不用编造的数字兜底：保留上一次成功的数据，并在界面上标明加载失败
    loadError.value = e?.message || '数据加载失败'
    console.error('加载数据大屏数据失败:', e)
  } finally {
    loading.value = false
  }
}

// 后端推送新告警时立即刷新一次，不用等下一个 30 秒；
// 轮询保留作为兜底，推送丢了也不会停摆
function onAlertPush() {
  loadScreenData()
}

// 抓拍图刷新间隔（后端对同一通道有短时缓存，不必太频繁）
const VIDEO_FRAME_INTERVAL = 10000
// 抓拍令牌有效期 1 小时，这里提前续签
const VIDEO_TOKEN_REFRESH_MS = 30 * 60 * 1000

function buildSnapshotUrl(item, stamp) {
  // 画面走短时令牌：<img> 无法携带认证头，令牌只能看到该通道的一张图
  return `/api/video/channels/${item.id}/snapshot?token=${encodeURIComponent(item.token)}&_t=${stamp}`
}

// 给在线通道签抓拍令牌（离线通道没有画面可取）
async function ensureVideoTokens(force = false) {
  const targets = videoList.value.filter(item => item.online && (force || !item.token))
  if (!targets.length) return
  await Promise.allSettled(targets.map(async (item) => {
    const { data } = await videoSnapshotToken(item.id)
    item.token = data.token
    item.snapshotUrl = buildSnapshotUrl(item, Date.now())
  }))
}

function tickVideoFrames() {
  videoList.value.forEach((item) => {
    if (item.token && item.online) {
      item.snapshotUrl = buildSnapshotUrl(item, Date.now())
    }
  })
}

function onVideoFrameError(item) {
  // 抓拍失败（设备不可达 / 令牌失效）就如实降级为占位，不显示坏图
  item.snapshotUrl = ''
  item.online = false
}

function updateLastUpdateTime() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const h = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  const s = String(now.getSeconds()).padStart(2, '0')
  lastUpdateTime.value = `${y}-${m}-${d} ${h}:${min}:${s}`
}

function updateClock() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const h = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  const s = String(now.getSeconds()).padStart(2, '0')
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  
  currentDate.value = `${y}年${m}月${d}日`
  currentTime.value = `${h}:${min}:${s}`
  currentWeekday.value = weekdays[now.getDay()]
  // 这里不再写 lastUpdateTime：页脚写的是「数据更新时间」，
  // 只在真正取到数据时（updateLastUpdateTime）才该变，跟着秒针跳会让人以为一直在刷新
}

function getBuildingStatus(b) {
  if (b.status === 'alarm' || (b.alarmCount && b.alarmCount > 5)) return '高风险'
  if (b.status === 'warning' || (b.alarmCount && b.alarmCount > 0)) return '中风险'
  return '正常'
}

function getBuildingStatusClass(b) {
  if (b.status === 'alarm' || (b.alarmCount && b.alarmCount > 5)) return 'danger'
  if (b.status === 'warning' || (b.alarmCount && b.alarmCount > 0)) return 'warning'
  return 'normal'
}

// 统一的下钻出口：无权限时给出提示，而不是让路由守卫把人甩到 /no-access
function drillTo(path, label) {
  if (!canAccessRoute(getCurrentUser(), router.resolve(path))) {
    ElMessage.warning(`当前账号没有「${label}」的访问权限`)
    return
  }
  router.push(path)
}

// 今日事件的 id 形如 alert-12 / inspection-3 / ticket-7：
// 按类型跳到对应页面，并把记录 id 带上（这两个页面本来就支持按 query 打开详情）
function openEvent(event) {
  const recordId = String(event.id || '').replace(/^[a-z]+-/, '')
  if (event.type === 'alarm') {
    drillTo('/alert-center', '告警中心')
  } else if (event.type === 'inspection') {
    drillTo(`/records?record_id=${recordId}`, '巡检档案')
  } else if (event.type === 'maintenance') {
    drillTo(`/workorders?order_id=${recordId}`, '整改工单')
  }
}

function selectBuilding(b) {
  drillTo(`/building-detail/${b.id}`, '建筑档案')
}

// 屏幕坐标 → 命中的建筑 id（没命中返回 null）
function pickBuildingId(event) {
  if (!renderer || !camera || !buildingHitMeshes.length) return null
  const rect = renderer.domElement.getBoundingClientRect()
  pointerNdc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointerNdc.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointerNdc, camera)
  const hits = raycaster.intersectObjects(buildingHitMeshes, false)
  return hits.length ? hits[0].object.userData.buildingId : null
}

function onScenePointerDown(event) {
  pointerDownAt = { x: event.clientX, y: event.clientY }
}

function onScenePointerMove(event) {
  if (!renderer) return
  // 悬停在建筑上时给出可点的提示
  renderer.domElement.style.cursor = pickBuildingId(event) ? 'pointer' : ''
}

function onSceneClick(event) {
  if (pointerDownAt) {
    const moved = Math.hypot(event.clientX - pointerDownAt.x, event.clientY - pointerDownAt.y)
    if (moved > 5) return
  }
  const buildingId = pickBuildingId(event)
  if (buildingId) drillTo(`/building-detail/${buildingId}`, '建筑档案')
}

function resetView() {
  if (controls && camera) {
    camera.position.set(55, 50, 65)
    controls.target.set(0, 5, 0)
    controls.update()
  }
}

function switchMapMode(mode) {
  mapMode.value = mode
  nextTick(() => {
    if (mode === 'heat') drawHeatmap()
    if (mode === 'device') drawDeviceMap()
    if (mode === '3d') {
      // 非 3D 视图下数据刷新会释放渲染器，切回时按当前真实台账重建场景
      if (renderer) handleResize()
      else init3DScene()
    }
  })
}

function drawHeatmap() {
  if (!heatmapCanvasRef.value) return
  const canvas = heatmapCanvasRef.value
  const ctx = canvas.getContext('2d')
  const rect = canvas.parentElement.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height

  ctx.fillStyle = '#0a1628'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  const gridSize = 40
  ctx.strokeStyle = 'rgba(0, 102, 170, 0.3)'
  ctx.lineWidth = 1
  for (let x = 0; x < canvas.width; x += gridSize) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y < canvas.height; y += gridSize) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }

  const layout = buildingLayout.value
  if (!layout.length) {
    ctx.fillStyle = '#5a7f9f'
    ctx.font = '14px Arial'
    ctx.textAlign = 'center'
    ctx.fillText('暂无建筑数据', canvas.width / 2, canvas.height / 2)
    return
  }

  // 热度取建筑真实风险评分（0-100），风险分为 0 时统一按低风险冷色展示
  const heatPoints = layout.map(b => ({
    x: b.nx,
    y: b.ny,
    value: Math.min(b.riskScore / 100, 1),
    label: b.name,
  }))

  heatPoints.forEach(p => {
    const px = p.x * canvas.width
    const py = p.y * canvas.height
    const radius = Math.min(canvas.width, canvas.height) * (0.1 + 0.12 * p.value)

    const gradient = ctx.createRadialGradient(px, py, 0, px, py, radius)
    const alpha = 0.35 + p.value * 0.55
    if (p.value > 0.7) {
      gradient.addColorStop(0, `rgba(255, 59, 48, ${alpha})`)
      gradient.addColorStop(0.4, `rgba(255, 149, 0, ${alpha * 0.6})`)
      gradient.addColorStop(1, 'rgba(255, 149, 0, 0)')
    } else if (p.value > 0.4) {
      gradient.addColorStop(0, `rgba(255, 204, 0, ${alpha})`)
      gradient.addColorStop(0.5, `rgba(255, 149, 0, ${alpha * 0.5})`)
      gradient.addColorStop(1, 'rgba(255, 204, 0, 0)')
    } else {
      gradient.addColorStop(0, `rgba(0, 212, 255, ${alpha})`)
      gradient.addColorStop(0.5, `rgba(0, 136, 255, ${alpha * 0.5})`)
      gradient.addColorStop(1, 'rgba(0, 212, 255, 0)')
    }

    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(px, py, radius, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = '#e0f0ff'
    ctx.font = '12px Arial'
    ctx.textAlign = 'center'
    ctx.fillText(`${p.label} ${p.value > 0 ? Math.round(p.value * 100) : 0}分`, px, py - radius - 5)
  })

  // 建筑轮廓按真实占地（area）换算尺寸
  layout.forEach(b => {
    const bx = b.nx * canvas.width
    const by = b.ny * canvas.height
    const bw = Math.max(b.w * 2.2, 30)
    const bh = Math.max(b.d * 2.2, 24)
    ctx.strokeStyle = `${BUILDING_STATUS_COLORS[b.status]}99`
    ctx.lineWidth = 1.5
    ctx.strokeRect(bx - bw / 2, by - bh / 2, bw, bh)
  })
}

function drawDeviceMap() {
  if (!deviceMapCanvasRef.value) return
  const canvas = deviceMapCanvasRef.value
  const ctx = canvas.getContext('2d')
  const rect = canvas.parentElement.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height

  ctx.fillStyle = '#0a1628'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  const gridSize = 40
  ctx.strokeStyle = 'rgba(0, 102, 170, 0.3)'
  ctx.lineWidth = 1
  for (let x = 0; x < canvas.width; x += gridSize) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y < canvas.height; y += gridSize) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }

  const layout = buildingLayout.value
  if (!layout.length) {
    ctx.fillStyle = '#5a7f9f'
    ctx.font = '14px Arial'
    ctx.textAlign = 'center'
    ctx.fillText('暂无建筑数据', canvas.width / 2, canvas.height / 2)
    return
  }

  // 建筑轮廓：位置来自真实经纬度换算，尺寸来自真实占地，底色来自真实告警状态
  const boxes = layout.map(b => ({
    ...b,
    bx: b.nx * canvas.width,
    by: b.ny * canvas.height,
    bw: Math.max(b.w * 2.2, 36),
    bh: Math.max(b.d * 2.2, 28),
  }))

  boxes.forEach(b => {
    ctx.fillStyle = `${BUILDING_STATUS_COLORS[b.status]}4d`
    ctx.fillRect(b.bx - b.bw / 2, b.by - b.bh / 2, b.bw, b.bh)
    ctx.strokeStyle = `${BUILDING_STATUS_COLORS[b.status]}cc`
    ctx.lineWidth = 1
    ctx.strokeRect(b.bx - b.bw / 2, b.by - b.bh / 2, b.bw, b.bh)

    ctx.fillStyle = '#8ab6d6'
    ctx.font = '11px Arial'
    ctx.textAlign = 'center'
    ctx.fillText(b.name, b.bx, b.by + b.bh / 2 + 14)
  })

  // 设备点位：数量取各建筑真实 deviceCount，位置为框内确定性排布（大屏是园区级视图，非楼层平面图）
  const typeColors = (deviceTypes.value || []).map(t => t.color)
  let dotIndex = 0
  boxes.forEach(b => {
    const total = Math.min(b.deviceCount, 60)
    for (let i = 0; i < total; i++) {
      const angle = i * 2.399963
      const radius = Math.sqrt(i / Math.max(total, 1))
      const dx = b.bx + Math.cos(angle) * radius * b.bw * 0.42
      const dy = b.by + Math.sin(angle) * radius * b.bh * 0.42
      const color = typeColors.length ? typeColors[i % typeColors.length] : '#00d4ff'

      ctx.beginPath()
      ctx.arc(dx, dy, 3, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      dotIndex++
    }

    // 告警点位：数量取该建筑真实 alarmCount
    for (let i = 0; i < Math.min(b.alarmCount, 8); i++) {
      const angle = i * 2.399963
      const radius = Math.sqrt(i / Math.max(b.alarmCount, 1))
      const dx = b.bx + Math.cos(angle) * radius * b.bw * 0.42
      const dy = b.by + Math.sin(angle) * radius * b.bh * 0.42
      ctx.strokeStyle = 'rgba(255, 59, 48, 0.8)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(dx, dy, 8, 0, Math.PI * 2)
      ctx.stroke()
    }
  })

  if (dotIndex === 0) {
    ctx.fillStyle = '#5a7f9f'
    ctx.font = '12px Arial'
    ctx.textAlign = 'center'
    ctx.fillText('暂无设备数据', canvas.width / 2, canvas.height / 2)
  }

  const legendY = canvas.height - 40
  let lx = 20
  ;(deviceTypes.value || []).forEach(d => {
    ctx.fillStyle = d.color
    ctx.beginPath()
    ctx.arc(lx + 6, legendY, 4, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#8ab6d6'
    ctx.font = '11px Arial'
    ctx.textAlign = 'left'
    ctx.fillText(`${d.name}(${d.count})`, lx + 16, legendY + 4)
    lx += 92
  })
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    const el = gisContainerRef.value?.parentElement
    if (el?.requestFullscreen) {
      el.requestFullscreen().catch(() => {
        ElMessage.warning('全屏模式不可用')
      })
    }
  } else {
    document.exitFullscreen()
  }
}

function handleResize() {
  if (gisContainerRef.value && renderer && camera) {
    const width = gisContainerRef.value.clientWidth
    const height = gisContainerRef.value.clientHeight
    if (width && height) {
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
  }
  if (mapMode.value === 'heat') drawHeatmap()
  if (mapMode.value === 'device') drawDeviceMap()
}

function dispose3DScene() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  if (controls) {
    controls.dispose()
    controls = null
  }
  if (renderer) {
    renderer.dispose()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
    renderer = null
  }
  scene = null
  camera = null
  alarmMarkers = []
  deviceDots = []
  buildingHitMeshes = []
  pointerDownAt = null
}

// 建筑台账的指纹：只有台账真的变化时才重建场景，避免 30 秒轮询把用户旋转好的视角复位
function buildingSignature() {
  return buildingLayout.value
    .map(b => `${b.id}:${b.status}:${b.deviceCount}:${b.alarmCount}:${b.w}:${b.h}`)
    .join('|')
}

function rebuild3DScene() {
  if (buildingSignature() === renderedBuildingSignature) return
  const wasIn3D = mapMode.value === '3d'
  dispose3DScene()
  if (wasIn3D) {
    renderedBuildingSignature = buildingSignature()
    nextTick(() => init3DScene())
  }
}

function init3DScene() {
  if (!gisContainerRef.value) return
  // 幂等：挂载与数据到达都可能触发，先释放已有场景，避免叠加出多个 canvas
  dispose3DScene()
  const width = gisContainerRef.value.clientWidth
  const height = gisContainerRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x050d1a)
  scene.fog = new THREE.Fog(0x050d1a, 80, 250)

  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 2000)
  camera.position.set(55, 50, 65)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.domElement.classList.add('webgl-layer')
  gisContainerRef.value.appendChild(renderer.domElement)

  // 建筑可点（下钻到建筑档案）：监听挂在 canvas 上，canvas 重建时随之失效
  renderer.domElement.addEventListener('pointerdown', onScenePointerDown)
  renderer.domElement.addEventListener('pointermove', onScenePointerMove)
  renderer.domElement.addEventListener('click', onSceneClick)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.minDistance = 25
  controls.maxDistance = 120
  controls.maxPolarAngle = Math.PI / 2.3
  controls.target.set(0, 5, 0)

  const ambientLight = new THREE.AmbientLight(0x3366aa, 0.5)
  scene.add(ambientLight)

  const hemiLight = new THREE.HemisphereLight(0x00aaff, 0x003366, 0.4)
  scene.add(hemiLight)

  const directionalLight = new THREE.DirectionalLight(0xaaccff, 0.8)
  directionalLight.position.set(60, 100, 60)
  directionalLight.castShadow = true
  directionalLight.shadow.mapSize.width = 2048
  directionalLight.shadow.mapSize.height = 2048
  scene.add(directionalLight)

  const pointLight1 = new THREE.PointLight(0x00aaff, 1.5, 120)
  pointLight1.position.set(35, 25, 25)
  scene.add(pointLight1)

  const pointLight2 = new THREE.PointLight(0x00ffaa, 0.8, 100)
  pointLight2.position.set(-30, 15, -25)
  scene.add(pointLight2)

  const groundGeometry = new THREE.PlaneGeometry(300, 300, 60, 60)
  const groundMaterial = new THREE.MeshStandardMaterial({
    color: 0x0a1628,
    roughness: 0.95,
    metalness: 0.05,
  })
  const ground = new THREE.Mesh(groundGeometry, groundMaterial)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  const gridHelper = new THREE.GridHelper(200, 50, 0x004477, 0x002244)
  gridHelper.position.y = 0.02
  scene.add(gridHelper)

  function createRoad(x1, z1, x2, z2, width) {
    const dx = x2 - x1
    const dz = z2 - z1
    const length = Math.sqrt(dx * dx + dz * dz)
    const roadGeom = new THREE.PlaneGeometry(width, length)
    const roadMat = new THREE.MeshStandardMaterial({
      color: 0x1a2a3a,
      roughness: 0.8,
      metalness: 0.1,
    })
    const road = new THREE.Mesh(roadGeom, roadMat)
    road.rotation.x = -Math.PI / 2
    road.position.set((x1 + x2) / 2, 0.03, (z1 + z2) / 2)
    road.rotation.z = Math.atan2(dx, dz)
    road.receiveShadow = true
    scene.add(road)

    const lineGeom = new THREE.PlaneGeometry(0.3, length)
    const lineMat = new THREE.MeshBasicMaterial({ color: 0xffff00, transparent: true, opacity: 0.6 })
    const line = new THREE.Mesh(lineGeom, lineMat)
    line.rotation.x = -Math.PI / 2
    line.position.set((x1 + x2) / 2, 0.05, (z1 + z2) / 2)
    line.rotation.z = Math.atan2(dx, dz)
    scene.add(line)
  }

  createRoad(-60, 0, 60, 0, 8)
  createRoad(0, -60, 0, 60, 8)
  createRoad(-60, 35, 60, 35, 6)
  createRoad(-60, -35, 60, -35, 6)
  createRoad(-40, -60, -40, 60, 6)
  createRoad(40, -60, 40, 60, 6)

  function createBuilding(buildingData) {
    const { id, x, z, w, d, h, name, color, floors, type } = buildingData
    const buildingGroup = new THREE.Group()
    buildingGroup.position.set(x, 0, z)

    const baseGeom = new THREE.BoxGeometry(w, 1.5, d)
    const baseMat = new THREE.MeshStandardMaterial({
      color: 0x1a2a3a,
      roughness: 0.7,
      metalness: 0.3,
    })
    const base = new THREE.Mesh(baseGeom, baseMat)
    base.position.y = 0.75
    base.castShadow = true
    base.receiveShadow = true
    buildingGroup.add(base)

    const bodyGeom = new THREE.BoxGeometry(w - 1, h - 2, d - 1)
    const bodyMat = new THREE.MeshStandardMaterial({
      color: color,
      roughness: 0.4,
      metalness: 0.5,
      transparent: true,
      opacity: 0.75,
    })
    const body = new THREE.Mesh(bodyGeom, bodyMat)
    body.position.y = 1 + (h - 2) / 2
    body.castShadow = true
    body.receiveShadow = true
    buildingGroup.add(body)

    const edgesGeometry = new THREE.EdgesGeometry(bodyGeom)
    const edgesMaterial = new THREE.LineBasicMaterial({ 
      color: new THREE.Color(color).offsetHSL(0, 0, 0.3),
      transparent: true,
      opacity: 0.8
    })
    const edges = new THREE.LineSegments(edgesGeometry, edgesMaterial)
    edges.position.y = 1 + (h - 2) / 2
    buildingGroup.add(edges)

    const windowRows = Math.floor(floors)
    const windowCols = Math.max(3, Math.floor(w / 3))
    const windowDepthCols = Math.max(2, Math.floor(d / 3))
    
    for (let floor = 0; floor < windowRows; floor++) {
      for (let col = 0; col < windowCols; col++) {
        const winGeom = new THREE.PlaneGeometry(1.2, 1.5)
        const isLit = Math.random() > 0.35
        const winMat = new THREE.MeshBasicMaterial({
          color: isLit ? 0xffdd66 : 0x0a1628,
          transparent: true,
          opacity: isLit ? 0.8 : 0.3,
        })
        
        const winFront = new THREE.Mesh(winGeom, winMat)
        winFront.position.set(
          -w / 2 + 1 + col * ((w - 2) / windowCols),
          3 + floor * ((h - 4) / windowRows),
          d / 2 - 0.4
        )
        buildingGroup.add(winFront)

        const winBack = new THREE.Mesh(winGeom, winMat.clone())
        winBack.position.set(
          -w / 2 + 1 + col * ((w - 2) / windowCols),
          3 + floor * ((h - 4) / windowRows),
          -d / 2 + 0.4
        )
        winBack.rotation.y = Math.PI
        buildingGroup.add(winBack)
      }
      
      for (let col = 0; col < windowDepthCols; col++) {
        const winGeomSide = new THREE.PlaneGeometry(1.2, 1.5)
        const isLit = Math.random() > 0.35
        const winMatSide = new THREE.MeshBasicMaterial({
          color: isLit ? 0xffdd66 : 0x0a1628,
          transparent: true,
          opacity: isLit ? 0.8 : 0.3,
        })
        
        const winLeft = new THREE.Mesh(winGeomSide, winMatSide)
        winLeft.position.set(
          -w / 2 + 0.4,
          3 + floor * ((h - 4) / windowRows),
          -d / 2 + 1 + col * ((d - 2) / windowDepthCols)
        )
        winLeft.rotation.y = -Math.PI / 2
        buildingGroup.add(winLeft)

        const winRight = new THREE.Mesh(winGeomSide, winMatSide.clone())
        winRight.position.set(
          w / 2 - 0.4,
          3 + floor * ((h - 4) / windowRows),
          -d / 2 + 1 + col * ((d - 2) / windowDepthCols)
        )
        winRight.rotation.y = Math.PI / 2
        buildingGroup.add(winRight)
      }
    }

    const roofGeom = new THREE.BoxGeometry(w + 0.5, 0.8, d + 0.5)
    const roofMat = new THREE.MeshStandardMaterial({
      color: 0x1a2a3a,
      roughness: 0.6,
      metalness: 0.4,
    })
    const roof = new THREE.Mesh(roofGeom, roofMat)
    roof.position.y = h - 0.4
    roof.castShadow = true
    buildingGroup.add(roof)

    // 航障灯按建筑真实状态色：蓝=正常、橙=预警、红=告警。
    // 之前一律红灯，等于把所有楼栋都画成「正在报警」，与图例和告警锥标冲突
    const roofLightGeom = new THREE.SphereGeometry(0.3, 8, 8)
    const roofLightMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(color).offsetHSL(0, 0, 0.25),
    })
    const roofLight = new THREE.Mesh(roofLightGeom, roofLightMat)
    roofLight.position.set(0, h + 1, 0)
    buildingGroup.add(roofLight)

    buildingGroup.userData = { id, name, type }
    // 底座 / 楼体 / 屋顶作为点击热区（不含窗格，避免点击时遍历上百个面片）
    for (const mesh of [base, body, roof]) {
      mesh.userData.buildingId = id
      buildingHitMeshes.push(mesh)
    }
    scene.add(buildingGroup)
    return buildingGroup
  }

  // 建筑体、告警标记、设备点位全部来自后端真实台账（buildingLayout 由经纬度与占地换算）
  const layout = buildingLayout.value
  renderedBuildingSignature = buildingSignature()
  if (!layout.length) {
    const emptyCanvas = document.createElement('canvas')
    emptyCanvas.width = 512
    emptyCanvas.height = 64
    const emptyCtx = emptyCanvas.getContext('2d')
    emptyCtx.fillStyle = '#5a7f9f'
    emptyCtx.font = '28px Arial'
    emptyCtx.textAlign = 'center'
    emptyCtx.fillText('暂无建筑数据，请先在建筑台账中录入', 256, 40)
    const emptySprite = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(emptyCanvas), transparent: true })
    )
    emptySprite.scale.set(70, 9, 1)
    emptySprite.position.set(0, 20, 0)
    scene.add(emptySprite)
    animate()
    return
  }

  layout.forEach(b => createBuilding({ ...b, color: BUILDING_STATUS_HEX[b.status] || 0x0088cc }))

  // 告警标记：只在该建筑真实存在告警（alarmCount > 0）时出现，标签用真实建筑名
  const alarmData = []
  layout.forEach(b => {
    const count = Math.min(b.alarmCount, 2)
    for (let i = 0; i < count; i++) {
      alarmData.push({
        x: b.x,
        y: b.h + 4 + i * 7,
        z: b.z,
        building: b.name,
      })
    }
  })

  alarmData.forEach(a => {
    const markerGroup = new THREE.Group()
    
    const markerGeom = new THREE.ConeGeometry(1.2, 2.5, 6)
    const markerMat = new THREE.MeshBasicMaterial({
      color: 0xff3333,
      transparent: true,
      opacity: 0.9,
    })
    const marker = new THREE.Mesh(markerGeom, markerMat)
    marker.position.set(a.x, a.y + 3, a.z)
    markerGroup.add(marker)

    const ringGeom = new THREE.RingGeometry(1.5, 2, 32)
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xff3333,
      transparent: true,
      opacity: 0.4,
      side: THREE.DoubleSide,
    })
    const ring = new THREE.Mesh(ringGeom, ringMat)
    ring.rotation.x = -Math.PI / 2
    ring.position.set(a.x, a.y + 0.5, a.z)
    markerGroup.add(ring)

    markerGroup.userData = { baseY: a.y + 3, ringBaseY: a.y + 0.5, time: Math.random() * Math.PI * 2 }
    alarmMarkers.push(markerGroup)
    scene.add(markerGroup)
  })

  // 设备光点：数量取各建筑真实 deviceCount，围绕建筑体确定性排布；
  // 颜色与「设备分布」二维视图、左侧「设备运行概览」同源（都用 deviceTypes[].color 循环取用），
  // 之前 3D 统一是一种绿色，看不出设备类型构成
  const typeColors = (deviceTypes.value || []).map(t => t.color)
  const devicePositions = []
  layout.forEach(b => {
    const total = Math.min(b.deviceCount, 40)
    for (let i = 0; i < total; i++) {
      const angle = i * 2.399963
      const radius = Math.max(b.w, b.d) * 0.6 + Math.sqrt(i / Math.max(total, 1)) * 4
      // 层高按 3 个场景单位，光点按真实层数分布在对应楼层高度
      devicePositions.push({
        x: b.x + Math.cos(angle) * radius,
        y: 2 + (i % Math.max(b.floors, 1)) * Math.min(3, b.h / Math.max(b.floors, 1)),
        z: b.z + Math.sin(angle) * radius,
        color: typeColors.length ? typeColors[i % typeColors.length] : '#00ff88',
      })
    }
  })

  devicePositions.forEach(pos => {
    const dotGeom = new THREE.SphereGeometry(0.5, 8, 8)
    const dotMat = new THREE.MeshBasicMaterial({ 
      color: pos.color,
      transparent: true,
      opacity: 0.9,
    })
    const dot = new THREE.Mesh(dotGeom, dotMat)
    dot.position.set(pos.x, pos.y, pos.z)
    dot.userData = { baseOpacity: 0.9, time: Math.random() * Math.PI * 2 }
    deviceDots.push(dot)
    scene.add(dot)
  })

  function createStreetLight(x, z) {
    const poleGeom = new THREE.CylinderGeometry(0.1, 0.15, 4, 6)
    const poleMat = new THREE.MeshStandardMaterial({ color: 0x333333 })
    const pole = new THREE.Mesh(poleGeom, poleMat)
    pole.position.set(x, 2, z)
    scene.add(pole)

    const lightGeom = new THREE.SphereGeometry(0.4, 8, 8)
    const lightMat = new THREE.MeshBasicMaterial({ color: 0xffdd88 })
    const light = new THREE.Mesh(lightGeom, lightMat)
    light.position.set(x, 4.2, z)
    scene.add(light)

    const pl = new THREE.PointLight(0xffdd88, 0.5, 15)
    pl.position.set(x, 4, z)
    scene.add(pl)
  }

  const lightPositions = [
    [-50, -10], [-50, 10], [50, -10], [50, 10],
    [-20, -50], [20, -50], [-20, 50], [20, 50],
  ]
  lightPositions.forEach(([x, z]) => createStreetLight(x, z))

  animate()
}

function animate() {
  animationId = requestAnimationFrame(animate)
  controls?.update()
  
  const time = Date.now() * 0.001
  alarmMarkers.forEach((m, i) => {
    const t = m.userData.time + time
    m.position.y = m.userData.baseY + Math.sin(t * 2 + i) * 1.5
    m.children[1].scale.setScalar(1 + Math.sin(t * 3 + i) * 0.3)
    m.children[1].material.opacity = 0.2 + Math.sin(t * 3 + i) * 0.2
  })

  deviceDots.forEach((dot, i) => {
    const t = dot.userData.time + time
    dot.material.opacity = 0.6 + Math.sin(t * 2 + i * 0.5) * 0.4
    dot.scale.setScalar(0.8 + Math.sin(t * 3 + i * 0.3) * 0.2)
  })

  renderer?.render(scene, camera)
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  loadScreenData()
  dataTimer = setInterval(loadScreenData, 30000)
  videoFrameTimer = setInterval(tickVideoFrames, VIDEO_FRAME_INTERVAL)
  videoTokenTimer = setInterval(() => {
    ensureVideoTokens(true).then(tickVideoFrames)
  }, VIDEO_TOKEN_REFRESH_MS)
  wsService.on('alert', onAlertPush)
  window.addEventListener('resize', handleResize)
  document.addEventListener('fullscreenchange', handleResize)
  nextTick(() => {
    init3DScene()
  })
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (dataTimer) clearInterval(dataTimer)
  if (videoFrameTimer) clearInterval(videoFrameTimer)
  if (videoTokenTimer) clearInterval(videoTokenTimer)
  wsService.off('alert', onAlertPush)
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', handleResize)
  dispose3DScene()
})
</script>

<style scoped>
.data-screen {
  width: 100%;
  height: 100vh;
  min-height: 0;
  background: #050d1a;
  background-image: 
    radial-gradient(ellipse at top, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse at bottom, rgba(139, 92, 246, 0.08) 0%, transparent 50%);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: 'Microsoft YaHei', sans-serif;
}

.screen-header {
  height: 70px;
  flex: 0 0 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 30px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.9) 0%, rgba(15, 23, 42, 0) 100%);
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
  position: relative;
}

.header-title {
  text-align: center;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.title-main {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(180deg, #fff 0%, #60a5fa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 4px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.decor {
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3b82f6, transparent);
}

.title-sub {
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
  letter-spacing: 2px;
}

.screen-toolbar {
  min-height: 46px;
  padding: 0 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.16);
  background: rgba(5, 13, 26, 0.82);
}

.toolbar-tip {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.screen-toolbar .screen-nav {
  border: 0;
  padding: 3px 0;
  background: transparent;
}

.screen-toolbar .screen-nav-item {
  padding: 6px 14px !important;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
  width: auto;
}

.screen-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border: 1px solid rgba(96, 165, 250, 0.18);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.7);
}

.screen-nav-item {
  color: #94a3b8 !important;
  font-size: 13px;
  padding: 7px 10px !important;
  border-radius: 5px;
}

.screen-nav-item:hover,
.screen-nav-item.active {
  color: #dbeafe !important;
  background: rgba(59, 130, 246, 0.2) !important;
}

.nav-badge {
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  margin-left: 5px;
  padding: 0 4px;
  border-radius: 8px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  text-align: center;
}

.nav-group .screen-nav-item {
  display: inline-flex;
  align-items: center;
}

.nav-group .screen-nav-item :deep(.el-icon) {
  margin-left: 5px;
}

.nav-menu-icon {
  display: inline-flex;
  width: 22px;
  color: #60a5fa;
}

:deep(.el-dropdown-menu__item) {
  min-width: 190px;
  display: flex;
  align-items: center;
  gap: 4px;
}

:deep(.el-dropdown-menu__item small) {
  margin-left: auto;
  color: #94a3b8;
  font-size: 11px;
}

.screen-nav-item.more :deep(.el-icon) {
  margin-left: 4px;
}

.header-right {
  justify-content: flex-end;
  gap: 12px;
}

.time-display {
  display: flex;
  flex-direction: column;
}

.time-display .date {
  font-size: 14px;
  color: #94a3b8;
}

.time-display .time {
  font-size: 20px;
  font-weight: 600;
  color: #60a5fa;
  font-family: 'Consolas', monospace;
}

.time-display .weekday {
  font-size: 12px;
  color: #64748b;
}

.alarm-brief {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #94a3b8;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #22c55e;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
  animation: pulse 2s ease-in-out infinite;
}

/* 设备在线率低于阈值时用告警色，不再是无条件显示"运行正常" */
.status-dot-warn {
  background: #f59e0b;
  box-shadow: 0 0 8px #f59e0b;
}

/* 面板为空时的占位文案（无数据时不再显示编造内容） */
.panel-empty {
  padding: 12px 4px;
  font-size: 12px;
  color: #475569;
  text-align: center;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@media (max-width: 1280px) {
  .screen-toolbar { padding: 0 18px; }
  .screen-toolbar .screen-nav-item { padding: 6px 9px !important; font-size: 12px; }
  .toolbar-tip { display: none; }
}

@media (max-width: 980px) {
  .screen-header { padding: 0 16px; }
  .header-left { display: none; }
  .title-main { font-size: 21px; letter-spacing: 2px; }
  .decor { width: 28px; }
  .screen-toolbar { overflow-x: auto; }
  .screen-toolbar .screen-nav { flex: 0 0 max-content; }
}

@media (max-width: 720px) {
  .header-title { position: static; transform: none; margin: 0 auto; }
  .header-right { display: none; }
}

.screen-body {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr 320px;
  gap: 14px;
  padding: 14px 20px;
  overflow: hidden;
}

.screen-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: hidden;
  min-height: 0;
}

.screen-col.left,
.screen-col.right {
  overflow-y: auto;
  padding-right: 4px;
}

.screen-col.left::-webkit-scrollbar,
.screen-col.right::-webkit-scrollbar,
.alarm-scroll-list::-webkit-scrollbar {
  width: 4px;
}

.screen-col.left::-webkit-scrollbar-thumb,
.screen-col.right::-webkit-scrollbar-thumb,
.alarm-scroll-list::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.3);
  border-radius: 2px;
}

.screen-col.left::-webkit-scrollbar-track,
.screen-col.right::-webkit-scrollbar-track,
.alarm-scroll-list::-webkit-scrollbar-track {
  background: transparent;
}

.screen-col.center {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.8) 0%, rgba(15, 23, 42, 0.6) 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 6px;
  position: relative;
}

.panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3b82f6, transparent);
}

.panel-header {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.panel-header :deep(.el-icon) {
  color: #3b82f6;
}

.panel-body {
  padding: 12px 14px;
}

.building-list,
.todo-list,
.rank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.building-item,
.todo-item {
  display: flex;
  align-items: center;
  padding: 9px 10px;
  border: 1px solid rgba(59, 130, 246, 0.12);
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.5);
}

.building-item {
  display: block;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.building-item:hover {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(30, 64, 175, 0.16);
}

.building-info,
.building-detail {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.building-name,
.todo-title,
.rank-name {
  color: #e2e8f0;
  font-size: 12px;
}

.building-status,
.todo-status {
  padding: 2px 6px;
  border-radius: 8px;
  font-size: 10px;
}

.building-status.normal,
.todo-status.processing {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
}

.building-status.warning,
.todo-status.pending {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.12);
}

.building-status.danger,
.todo-status.urgent {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.12);
}

.building-detail {
  margin-top: 6px;
  color: #64748b;
  font-size: 11px;
}

.todo-item {
  gap: 9px;
}

.todo-icon {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.12);
  flex-shrink: 0;
}

.todo-icon.hazard {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.12);
}

.todo-icon.inspection {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-desc {
  color: #64748b;
  font-size: 10px;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-status {
  flex-shrink: 0;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
}

.rank-num {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  color: #94a3b8;
  background: rgba(100, 116, 139, 0.15);
  font-size: 11px;
}

.rank-num.rank-1 {
  color: #fff;
  background: #ef4444;
}

.rank-num.rank-2 {
  color: #fff;
  background: #f59e0b;
}

.rank-num.rank-3 {
  color: #0f172a;
  background: #facc15;
}

.rank-name {
  width: 88px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-bar {
  flex: 1;
  height: 5px;
  border-radius: 3px;
  overflow: hidden;
  background: rgba(100, 116, 139, 0.18);
}

.rank-fill {
  height: 100%;
  border-radius: 3px;
}

.rank-value {
  width: 30px;
  color: #94a3b8;
  font: 11px 'Consolas', monospace;
  text-align: right;
}

.device-stats-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 14px;
}

.device-stat-item {
  text-align: center;
}

.device-stat-item .stat-num {
  font-size: 26px;
  font-weight: 700;
  color: #e2e8f0;
  font-family: 'Consolas', monospace;
}

.device-stat-item .stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.device-stat-item.online .stat-num {
  color: #22c55e;
  text-shadow: 0 0 10px rgba(34, 197, 94, 0.5);
}

.device-stat-item.offline .stat-num {
  color: #94a3b8;
}

.device-type-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.device-type-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.type-name {
  width: 70px;
  color: #94a3b8;
  flex-shrink: 0;
}

.type-bar {
  flex: 1;
  height: 6px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.type-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.type-count {
  width: 36px;
  text-align: right;
  color: #e2e8f0;
  font-weight: 500;
}

.alarm-level-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}

.alarm-level-item {
  text-align: center;
  padding: 8px 4px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 6px;
}

.alarm-level-item.critical .level-num {
  color: #ef4444;
  text-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
}

.alarm-level-item.high .level-num {
  color: #f97316;
  text-shadow: 0 0 10px rgba(249, 115, 22, 0.5);
}

.alarm-level-item.medium .level-num {
  color: #f59e0b;
  text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
}

.alarm-level-item.low .level-num {
  color: #3b82f6;
  text-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
}

.level-num {
  font-size: 22px;
  font-weight: 700;
  font-family: 'Consolas', monospace;
}

.level-label {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.alarm-trend .trend-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 80px;
  gap: 4px;
}

.trend-bar-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
}

.trend-bar {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
}

.bar-fill {
  width: 100%;
  background: linear-gradient(180deg, #3b82f6, rgba(59, 130, 246, 0.2));
  border-radius: 2px 2px 0 0;
  min-height: 4px;
}

.trend-date {
  font-size: 10px;
  color: #64748b;
}

.hazard-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.circular-chart {
  width: 80px;
  height: 80px;
}

.circle-bg {
  fill: none;
  stroke: rgba(59, 130, 246, 0.1);
  stroke-width: 3;
}

.circle {
  fill: none;
  stroke: #22c55e;
  stroke-width: 3;
  stroke-linecap: round;
  transform: rotate(-90deg);
  transform-origin: center;
  transition: stroke-dasharray 0.5s;
}

.percentage {
  fill: #e2e8f0;
  font-size: 9px;
  font-weight: 600;
  text-anchor: middle;
}

.hazard-info .hazard-label {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
}

.hazard-info .hazard-desc {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.hazard-type-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hazard-type-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.hazard-type-item .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.hazard-type-item .name {
  flex: 1;
  color: #94a3b8;
}

.hazard-type-item .num {
  color: #e2e8f0;
  font-weight: 500;
}

.gis-panel {
  flex: 1;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.8) 0%, rgba(15, 23, 42, 0.6) 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  position: relative;
}

.gis-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3b82f6, transparent);
}

.gis-header {
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.gis-tabs {
  display: flex;
  gap: 12px;
}

.gis-tab {
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.gis-tab.active {
  color: #60a5fa;
  border-bottom-color: #3b82f6;
}

.gis-header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.gis-tools {
  display: flex;
  gap: 4px;
}

.gis-tools :deep(.el-button) {
  color: #94a3b8;
  padding: 4px 8px;
  margin-left: 0;
}

.gis-tools :deep(.el-button:hover) {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
}

.gis-legend {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #94a3b8;
}

.map-canvas-layer {
  position: absolute;
  top: 0;
  left: 0;
  display: block;
}

.webgl-layer {
  position: absolute;
  top: 0;
  left: 0;
}

.gis-container.hide-webgl .webgl-layer {
  display: none;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
}

.gis-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.gis-canvas {
  width: 100%;
  height: 100%;
}

.gis-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.building-marker {
  position: absolute;
  transform: translate(-50%, -50%);
  text-align: center;
}

.marker-pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.2);
  animation: marker-pulse 2s ease-in-out infinite;
}

.building-marker.warning .marker-pulse {
  background: rgba(245, 158, 11, 0.2);
}

.building-marker.alarm .marker-pulse {
  background: rgba(239, 68, 68, 0.3);
  animation-duration: 1s;
}

@keyframes marker-pulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  50% { transform: translate(-50%, -50%) scale(1.5); opacity: 0.5; }
}

.marker-icon {
  position: relative;
  z-index: 2;
  width: 32px;
  height: 32px;
  margin: 0 auto;
  background: linear-gradient(135deg, #22c55e, #16a34a);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.4);
}

.building-marker.warning .marker-icon {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
}

.building-marker.alarm .marker-icon {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
}

.marker-label {
  position: relative;
  z-index: 2;
  font-size: 11px;
  color: #e2e8f0;
  margin-top: 4px;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
  background: rgba(15, 23, 42, 0.8);
  padding: 2px 6px;
  border-radius: 3px;
  display: inline-block;
}

.gis-stats-overlay {
  position: absolute;
  bottom: 14px;
  left: 14px;
  display: flex;
  gap: 16px;
}

.gis-stat {
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 4px;
  padding: 8px 14px;
  text-align: center;
}

.gis-stat-num {
  font-size: 20px;
  font-weight: 700;
  color: #60a5fa;
  font-family: 'Consolas', monospace;
  display: block;
}

.gis-stat-label {
  font-size: 11px;
  color: #64748b;
}

.center-bottom-panels {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.panel.small .panel-body {
  padding: 10px 12px;
}

.water-mini-stats,
.electric-mini-stats {
  display: flex;
  justify-content: space-around;
}

.water-mini-item,
.electric-mini-item {
  text-align: center;
}

.water-val,
.electric-val {
  font-size: 18px;
  font-weight: 700;
  color: #e2e8f0;
  font-family: 'Consolas', monospace;
}

.water-val.green { color: #22c55e; }
.electric-val.warning { color: #f59e0b; }

.unit {
  font-size: 11px;
  color: #64748b;
  font-weight: 400;
  margin-left: 2px;
}

.water-label,
.electric-label {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.duty-mini-info {
  text-align: center;
}

.duty-shift {
  margin-bottom: 8px;
}

.duty-persons {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #94a3b8;
}

.duty-period {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
}

.duty-empty {
  font-size: 12px;
  color: #475569;
}

.footer-error {
  color: #f59e0b;
}

.alarm-scroll-panel {
  max-height: 280px;
  display: flex;
  flex-direction: column;
}

.alarm-badge {
  margin-left: auto;
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.alarm-scroll-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alarm-scroll-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 6px;
  border-left: 3px solid #64748b;
}

.alarm-scroll-item.critical {
  border-left-color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.alarm-scroll-item.high {
  border-left-color: #f97316;
}

.alarm-scroll-item.medium {
  border-left-color: #f59e0b;
}

.alarm-scroll-item.low {
  border-left-color: #3b82f6;
}

.alarm-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.alarm-scroll-item.critical .alarm-icon { color: #ef4444; }
.alarm-scroll-item.high .alarm-icon { color: #f97316; }
.alarm-scroll-item.medium .alarm-icon { color: #f59e0b; }
.alarm-scroll-item.low .alarm-icon { color: #3b82f6; }

.alarm-content {
  flex: 1;
  min-width: 0;
}

.alarm-title {
  font-size: 13px;
  color: #e2e8f0;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alarm-location {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 2px;
}

.alarm-time {
  font-size: 10px;
  color: #475569;
}

.alarm-level-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}

.alarm-level-badge.critical {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.alarm-level-badge.high {
  background: rgba(249, 115, 22, 0.2);
  color: #fb923c;
}

.alarm-level-badge.medium {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.alarm-level-badge.low {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.video-mini-item {
  text-align: center;
}

.video-thumbnail {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #0f172a;
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}

.video-icon {
  font-size: 24px;
  color: #3b82f6;
  opacity: 0.5;
}

.video-mini-item.offline .video-thumbnail {
  background: #1e293b;
  opacity: 0.5;
}

.video-offline-tip {
  position: absolute;
  font-size: 11px;
  color: #ef4444;
  background: rgba(0, 0, 0, 0.6);
  padding: 2px 6px;
  border-radius: 3px;
}

.video-name {
  font-size: 11px;
  color: #94a3b8;
}

.event-timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
  padding-left: 14px;
}

.event-item {
  position: relative;
}

.event-dot {
  position: absolute;
  left: -14px;
  top: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
  box-shadow: 0 0 6px currentColor;
}

.event-item.alarm .event-dot { background: #ef4444; color: #ef4444; }
.event-item.inspection .event-dot { background: #3b82f6; color: #3b82f6; }
.event-item.normal .event-dot { background: #22c55e; color: #22c55e; }
.event-item.maintenance .event-dot { background: #f59e0b; color: #f59e0b; }
.event-item.drill .event-dot { background: #8b5cf6; color: #8b5cf6; }

.event-title {
  font-size: 12px;
  color: #e2e8f0;
}

.event-time {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.indicator-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.indicator-item .indicator-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}

.indicator-name {
  color: #94a3b8;
}

.indicator-value {
  font-weight: 600;
  font-family: 'Consolas', monospace;
}

.indicator-value.good { color: #22c55e; }
.indicator-value.warning { color: #f59e0b; }

.indicator-bar {
  height: 4px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.indicator-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.indicator-fill.good { background: linear-gradient(90deg, #22c55e, #16a34a); }
.indicator-fill.warning { background: linear-gradient(90deg, #f59e0b, #d97706); }

.screen-footer {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(0deg, rgba(15, 23, 42, 0.9) 0%, rgba(15, 23, 42, 0) 100%);
  border-top: 1px solid rgba(59, 130, 246, 0.1);
}

.footer-info {
  font-size: 12px;
  color: #475569;
  display: flex;
  align-items: center;
  gap: 16px;
}

.footer-divider {
  color: #334155;
}

.ai-analyst-btn {
  background: linear-gradient(135deg, #0ea5e9, #22c55e);
  border: none;
  box-shadow: 0 0 12px rgba(14, 165, 233, 0.4);
}

.screen-ai-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 0;
  display: none;
}
.screen-ai-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.ai-analyst-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8fafc;
}
.ai-analyst-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  color: white;
}
.ai-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ai-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ai-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 2px;
}
.ai-subtitle {
  font-size: 12px;
  opacity: 0.85;
}

.quick-questions {
  padding: 14px 20px;
  background: white;
  border-bottom: 1px solid #f1f5f9;
}
.qq-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
}
.qq-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.qq-item {
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.qq-item:hover {
  background: #dbeafe;
  color: #2563eb;
}

.ai-chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.ai-msg-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.ai-msg-item.user {
  justify-content: flex-end;
}
.ai-msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #eff6ff;
  color: #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ai-msg-bubble {
  max-width: 75%;
}
.ai-msg-item.user .ai-msg-bubble {
  background: #3b82f6;
  color: white;
  border-radius: 12px 12px 0 12px;
  padding: 10px 14px;
}
.ai-msg-item.assistant .ai-msg-bubble {
  background: white;
  border-radius: 12px 12px 12px 0;
  padding: 10px 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.ai-msg-content p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.7;
}
.ai-msg-content p:last-child {
  margin-bottom: 0;
}
.msg-data-preview {
  margin-bottom: 8px;
}
.msg-related {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}
.mr-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}
.mr-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.mr-tag {
  cursor: pointer;
}

.ai-typing {
  display: flex;
  gap: 4px;
  padding: 8px 4px;
}
.ai-typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  animation: typing 1.4s infinite ease-in-out;
}
.ai-typing span:nth-child(2) {
  animation-delay: 0.2s;
}
.ai-typing span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

.ai-input-area {
  padding: 12px 20px 16px;
  background: white;
  border-top: 1px solid #f1f5f9;
}
.input-hint {
  margin-top: 6px;
  font-size: 11px;
  color: #94a3b8;
  text-align: right;
}

/* 可下钻的行：给出可点提示。放在样式表最后，覆盖各列表自身的背景/边框 */
.is-clickable {
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.is-clickable:hover {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(30, 64, 175, 0.16);
}

/* 抓拍画面铺满缩略框 */
.video-frame {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 3px;
}
</style>
