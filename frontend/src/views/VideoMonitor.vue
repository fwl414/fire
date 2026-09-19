<template>
  <div class="video-monitor-page">
    <div class="title-row">
      <div>
        <div class="page-title">视频监控</div>
        <p class="subtitle">消防视频监控 · 报警联动 · 火情复核 · 智能分析</p>
      </div>
      <div class="title-actions">
        <el-tag :type="snapshotReady ? 'success' : 'info'" effect="dark" size="large">
          <el-icon><VideoCamera /></el-icon>
          {{ snapshotReady ? `抓拍画面轮询中 · ${POLL_SECONDS}s` : '暂无可用画面' }}
        </el-tag>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><VideoCamera /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.totalPoints }}</div>
            <div class="stat-label">监控点位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.online }}</div>
            <div class="stat-label">在线数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon gray"><el-icon><CircleClose /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.offline }}</div>
            <div class="stat-label">离线数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.todayLinkage }}</div>
            <div class="stat-label">今日告警</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'video' }" @click="activeTab = 'video'">
          <el-icon><VideoCamera /></el-icon>
          视频监控
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'alarm' }" @click="activeTab = 'alarm'">
          <el-icon><Warning /></el-icon>
          告警联动
          <span v-if="pendingAlarmCount" class="badge">{{ pendingAlarmCount }}</span>
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'playback' }" @click="activeTab = 'playback'">
          <el-icon><Refresh /></el-icon>
          录像回放
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'gb28181' }" @click="activeTab = 'gb28181'">
          <el-icon><VideoCamera /></el-icon>
          国标视频
        </div>
      </div>

      <div v-if="activeTab === 'video'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="cameraBuildingFilter" placeholder="选择区域" clearable style="width: 180px">
              <el-option label="全部区域" value="" />
              <el-option v-for="area in cameraAreas" :key="area" :label="area" :value="area" />
            </el-select>
            <el-select v-model="cameraStatusFilter" placeholder="在线状态" clearable style="width: 140px">
              <el-option label="在线" value="online" />
              <el-option label="离线" value="offline" />
              <el-option label="未知" value="unknown" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-radio-group v-model="gridLayout" size="default">
              <el-radio-button value="2x2">2 × 2</el-radio-button>
              <el-radio-button value="3x3">3 × 3</el-radio-button>
            </el-radio-group>
            <el-input v-model="cameraSearch" placeholder="搜索摄像头" style="width: 200px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button :loading="probing" @click="refreshCameras(true)">
              <el-icon><Refresh /></el-icon>
              探测设备
            </el-button>
            <el-button @click="refreshCameras(false)">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
        <el-alert
          v-if="!loadingChannels && !cameras.length"
          type="info"
          show-icon
          :closable="false"
          title="尚未接入视频通道"
          description="请通过 /api/video/channels 维护摄像头或 NVR 通道（支持通用 HTTP 抓拍、海康 ISAPI、大华 CGI、本地模拟设备），保存后此处自动显示抓拍画面。"
          style="margin-bottom: 12px"
        />
        <div class="video-grid" :class="gridLayout">
          <div v-for="cam in displayedCameras" :key="cam.id" class="video-item">
            <div
              class="video-window"
              :class="{ offline: cam.status !== 'online' }"
              :ref="el => registerTile(cam.id, el)"
            >
              <img
                v-if="cam.status === 'online' && cam.snapshotUrl"
                class="video-frame"
                :src="cam.snapshotUrl"
                alt=""
                @error="onFrameError(cam)"
              />
              <div v-else class="video-placeholder">
                <el-icon class="video-icon"><VideoCamera /></el-icon>
                <span v-if="cam.status === 'offline'" class="offline-text">摄像头离线</span>
                <span v-else class="offline-text">状态未知，请点击「探测设备」</span>
              </div>
              <div class="video-overlay top">
                <div class="camera-name">{{ cam.name }}</div>
                <el-tag size="small" effect="dark" :type="statusTagType(cam.status)">
                  {{ statusText(cam.status) }}
                </el-tag>
              </div>
              <div class="video-overlay bottom">
                <span class="camera-location">{{ cam.location || '未填写位置' }}</span>
                <span class="video-time">{{ currentTime }}</span>
              </div>
              <div class="video-controls">
                <el-button circle size="small" title="全屏" @click="handleFullScreen(cam)">
                  <el-icon><FullScreen /></el-icon>
                </el-button>
                <el-button
                  circle
                  size="small"
                  title="抓拍识别"
                  :loading="analyzingId === cam.id"
                  @click="handleAnalyze(cam)"
                >
                  <el-icon><Search /></el-icon>
                </el-button>
                <el-button circle size="small" title="刷新画面" @click="refreshSingleFrame(cam)">
                  <el-icon><Refresh /></el-icon>
                </el-button>
              </div>
              <div v-if="cam.status === 'online' && cam.ptzEnabled" class="ptz-controls">
                <el-button circle size="small" class="ptz-btn ptz-top" @click="handlePtz(cam, 'up')">
                  <el-icon><Top /></el-icon>
                </el-button>
                <el-button circle size="small" class="ptz-btn ptz-bottom" @click="handlePtz(cam, 'down')">
                  <el-icon><Bottom /></el-icon>
                </el-button>
                <el-button circle size="small" class="ptz-btn ptz-left" @click="handlePtz(cam, 'left')">
                  <el-icon><Back /></el-icon>
                </el-button>
                <el-button circle size="small" class="ptz-btn ptz-right" @click="handlePtz(cam, 'right')">
                  <el-icon class="rotate-right"><Back /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'alarm'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="alarmTypeFilter" placeholder="告警类型" clearable style="width: 170px">
              <el-option v-for="item in alarmTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="alarmStatusFilter" placeholder="处置状态" clearable style="width: 140px">
              <el-option label="待处置" value="pending" />
              <el-option label="处置中" value="processing" />
              <el-option label="已处置" value="resolved" />
              <el-option label="已合并" value="merged" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="alarmSearch" placeholder="搜索告警" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table
          v-loading="alarmsLoading"
          :data="filteredAlarms"
          stripe
          style="width: 100%"
          empty-text="暂无告警记录"
        >
          <el-table-column prop="alarmTime" label="告警时间" width="170" />
          <el-table-column label="告警类型" width="140">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="severityTag(row.severity)">
                {{ row.alarmType }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关联摄像头" width="170">
            <template #default="{ row }">
              <span v-if="row.cameraName">{{ row.cameraName }}</span>
              <span v-else style="color: #94a3b8">未关联</span>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="位置" min-width="180" />
          <el-table-column label="处置状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="statusTag(row.status)">
                {{ row.handleStatus }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewLinkageVideo(row)">查看视频</el-button>
              <el-button link type="warning" @click="goAlertCenter(row)">处置</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'playback'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-date-picker
              v-model="playbackDate"
              type="date"
              placeholder="选择日期"
              value-format="YYYY-MM-DD"
              style="width: 180px"
            />
            <el-select v-model="playbackCamera" placeholder="选择摄像头" style="width: 200px">
              <el-option v-for="cam in cameras" :key="cam.id" :label="cam.name" :value="cam.id" />
            </el-select>
            <el-time-picker
              v-model="playbackStartTime"
              placeholder="开始时间"
              format="HH:mm"
              value-format="HH:mm"
              style="width: 120px"
            />
            <el-time-picker
              v-model="playbackEndTime"
              placeholder="结束时间"
              format="HH:mm"
              value-format="HH:mm"
              style="width: 120px"
            />
            <el-button type="primary" :loading="recordingLoading" @click="searchRecordings">
              <el-icon><Search /></el-icon>
              检索
            </el-button>
          </div>
          <div class="toolbar-right">
            <el-button @click="refreshRecordings">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <el-alert
          v-if="recordingNotice"
          :type="recordingSupported ? 'info' : 'warning'"
          :closable="false"
          show-icon
          :title="recordingNotice"
          style="margin-bottom: 12px"
        />

        <div class="timeline-section">
          <div class="timeline-header">
            <span class="timeline-title">录像时间轴</span>
            <span class="timeline-date">{{ playbackDateStr }}</span>
          </div>
          <div class="timeline-bar">
            <div class="timeline-scale">
              <span v-for="h in 25" :key="h" class="scale-mark">{{ (h - 1).toString().padStart(2, '0') }}</span>
            </div>
            <div class="timeline-track">
              <div
                v-for="(seg, idx) in recordingSegments"
                :key="idx"
                class="timeline-segment"
                :style="{ left: seg.left + '%', width: seg.width + '%', background: '#3b82f6' }"
                :title="seg.title"
              ></div>
            </div>
          </div>
          <div class="timeline-legend">
            <span class="legend-item">
              <span class="legend-dot normal"></span>
              设备返回的录像片段（{{ recordingSegments.length }} 段）
            </span>
          </div>
        </div>

        <div class="recording-list">
          <div class="list-header">
            <span class="list-title">录像片段列表</span>
            <span class="list-count">共 {{ recordingRows.length }} 个片段</span>
          </div>
          <el-table
            v-loading="recordingLoading"
            :data="recordingRows"
            stripe
            style="width: 100%"
            empty-text="未检索到录像片段"
          >
            <el-table-column prop="date" label="日期" width="130" />
            <el-table-column prop="startText" label="开始时间" width="120" />
            <el-table-column prop="endText" label="结束时间" width="120" />
            <el-table-column prop="duration" label="时长" width="140" />
            <el-table-column prop="playback_uri" label="取流地址" min-width="240" show-overflow-tooltip />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="copyPlaybackUri(row)">复制取流地址</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 国标视频：左侧设备通道列表 + 右侧 2×2 实时画面 -->
      <div v-if="activeTab === 'gb28181'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select
              v-model="gbDeviceId"
              placeholder="选择国标设备"
              style="width: 280px"
              @change="loadGbChannels"
            >
              <el-option
                v-for="item in gbDevices"
                :key="item.id"
                :label="`${item.name}（${item.gb_device_id}）`"
                :value="item.id"
              />
            </el-select>
            <el-button :disabled="!gbDeviceId" :loading="gbCatalogLoading" @click="refreshGbCatalog">
              <el-icon><Refresh /></el-icon>
              刷新目录
            </el-button>
            <el-tag :type="gbStatus.running ? 'success' : 'info'" effect="dark">
              {{ gbStatus.running ? `SIP 运行中 · ${gbStatus.listen}` : 'SIP 未启动' }}
            </el-tag>
            <el-tag v-if="gbMediaReady" type="success" effect="plain">媒体服务器已配置</el-tag>
            <el-tag v-else type="warning" effect="plain">未配置媒体服务器</el-tag>
          </div>
          <div class="toolbar-right">
            <el-button :loading="gbLoading" @click="loadGbDevices">
              <el-icon><Refresh /></el-icon>
              刷新设备
            </el-button>
          </div>
        </div>

        <el-alert
          v-if="!gbLoading && !gbDevices.length"
          type="info"
          show-icon
          :closable="false"
          title="暂无已注册的国标设备"
          description="在摄像机 / NVR 的国标接入里填写平台地址（本机 IP）、SIP 端口 5060、平台编码与口令；设备注册成功后会自动出现在这里，再点「刷新目录」拉取通道。"
          style="margin-bottom: 12px"
        />

        <div class="gb-layout">
          <div class="gb-list">
            <div class="gb-list-header">
              <span>通道列表</span>
              <span class="gb-list-count">{{ gbChannels.length }}</span>
            </div>
            <div v-if="!gbChannels.length" class="gb-empty">暂无通道，请点击「刷新目录」向设备索要</div>
            <div
              v-for="channel in gbChannels"
              :key="channel.id"
              class="gb-channel"
              :class="{ active: gbSlotChannelIds.includes(channel.id) }"
            >
              <div class="gb-channel-info">
                <div class="gb-channel-name">{{ channel.name }}</div>
                <div class="gb-channel-meta">{{ channel.gb_device_id }}</div>
              </div>
              <div class="gb-channel-actions">
                <el-tag size="small" effect="dark" :type="channel.status === 'online' ? 'success' : 'info'">
                  {{ channel.status === 'online' ? '在线' : '离线' }}
                </el-tag>
                <el-button link type="primary" :loading="gbPlayingId === channel.id" @click="playGbChannel(channel)">
                  播放
                </el-button>
                <el-button link type="danger" @click="stopGbChannel(channel)">停止</el-button>
              </div>
            </div>
          </div>

          <div class="gb-grid">
            <div v-for="(slot, index) in gbSlots" :key="index" class="gb-tile">
              <VideoPlayer
                :url="slot.url"
                :mode="slot.mode"
                :title="slot.title"
                @failed="onGbPlayFailed"
              />
              <div v-if="slot.url" class="gb-tile-actions">
                <el-button circle size="small" title="云台上" @click="gbPtz(slot, 'up')">
                  <el-icon><Top /></el-icon>
                </el-button>
                <el-button circle size="small" title="云台下" @click="gbPtz(slot, 'down')">
                  <el-icon><Bottom /></el-icon>
                </el-button>
                <el-button circle size="small" title="云台左" @click="gbPtz(slot, 'left')">
                  <el-icon><Back /></el-icon>
                </el-button>
                <el-button circle size="small" title="云台右" @click="gbPtz(slot, 'right')">
                  <el-icon class="rotate-right"><Back /></el-icon>
                </el-button>
                <el-button circle size="small" title="关闭画面" @click="clearGbSlot(index)">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import {
  VideoCamera, Warning, CircleCheck, CircleClose, Search, Refresh,
  FullScreen, Back, Top, Bottom, Close
} from '@element-plus/icons-vue'
import VideoPlayer from '../components/VideoPlayer.vue'
import {
  alertList, alertStatistics, searchVideoRecordings, videoChannels, videoSnapshotToken,
  probeVideoChannel, controlVideoPtz, analyzeVideoChannel,
  listGB28181Devices, listGB28181Channels, refreshGB28181Catalog,
  playGB28181Channel, stopGB28181Channel, gb28181Ptz, gb28181Status
} from '../api'

const router = useRouter()
const activeTab = ref('video')
const gridLayout = ref('2x2')
const currentTime = ref('')
let timer = null
let pollTimer = null
let tokenTimer = null

// 抓拍图轮询间隔（后端有短时缓存，前端不必过于频繁）
const POLL_SECONDS = 5
// 抓拍令牌有效期 1 小时，这里提前续签
const TOKEN_REFRESH_MS = 30 * 60 * 1000

const loadingChannels = ref(false)
const probing = ref(false)
const analyzingId = ref(null)
const todayAlerts = ref(0)
const tileRefs = {}

const stats = computed(() => ({
  totalPoints: cameras.value.length,
  online: cameras.value.filter(c => c.status === 'online').length,
  offline: cameras.value.filter(c => c.status === 'offline').length,
  todayLinkage: todayAlerts.value,
}))

const cameraBuildingFilter = ref('')
const cameraStatusFilter = ref('')
const cameraSearch = ref('')

const alarmTypeFilter = ref('')
const alarmStatusFilter = ref('')
const alarmSearch = ref('')

const playbackDate = ref(todayStr())
const playbackCamera = ref(null)
const playbackStartTime = ref('00:00')
const playbackEndTime = ref('23:59')

function todayStr() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const cameras = ref([])

function applyChannels(list) {
  const previous = new Map(cameras.value.map(item => [item.id, item]))
  cameras.value = list.map(channel => {
    const prev = previous.get(channel.id) || {}
    return {
      id: channel.id,
      code: channel.channel_code,
      name: `${channel.channel_code} ${channel.channel_name}`.trim(),
      // 告警表里没有摄像头字段，靠设备这一层把告警关联到通道
      deviceId: channel.device_id,
      location: channel.location || '',
      area: channel.location || '',
      status: channel.status || 'unknown',
      platformLabel: channel.platform_label || channel.platform,
      ptzEnabled: Boolean(channel.ptz_enabled),
      capabilities: channel.capabilities || [],
      lastError: channel.last_error || '',
      lastSnapshotAt: channel.last_snapshot_at || '',
      token: prev.token || '',
      snapshotUrl: prev.snapshotUrl || '',
    }
  })
}

const cameraAreas = computed(() =>
  [...new Set(cameras.value.map(c => c.location).filter(Boolean))]
)

const snapshotReady = computed(() => cameras.value.some(c => c.snapshotUrl))

// 告警联动的数据来自本租户的真实告警（GET /api/alert/list）。
// 改造前这里是 8 条写死的 2024-01 演示告警：摄像头名、联动状态、处置状态都是编的。
const alarmRows = ref([])
const alarmsLoading = ref(false)

// 告警记录里没有摄像头字段，用「设备」这一层做关联（VideoChannel.device_id === AlertRecord.device_id）；
// 关联不上就留空，由界面显示「未关联」，不编一个摄像头名出来。
function cameraNameOf(alert) {
  if (!alert.device_id) return ''
  const matched = cameras.value.find(cam => String(cam.deviceId) === String(alert.device_id))
  return matched ? matched.name : ''
}

function formatDateTime(value) {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value).replace('T', ' ').slice(0, 19)
  const pad = (n) => String(n).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} `
    + `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
}

async function loadAlarms() {
  alarmsLoading.value = true
  try {
    const { data } = await alertList({ limit: 50 })
    alarmRows.value = (data.items || []).map(item => ({
      id: item.id,
      alertCode: item.alert_code,
      alarmTime: formatDateTime(item.created_at),
      alertType: item.alert_type,
      alarmType: item.alert_type_label || item.alert_type,
      severity: item.severity,
      cameraName: cameraNameOf(item),
      location: item.location || item.building_name || '',
      deviceName: item.device_name || '',
      handleStatus: item.status_label || item.status,
      status: item.status,
    }))
  } catch (error) {
    alarmRows.value = []
  } finally {
    alarmsLoading.value = false
  }
}

// 类型下拉按真实出现过的告警类型生成，不再写死五类
const alarmTypeOptions = computed(() => {
  const seen = new Map()
  alarmRows.value.forEach(item => {
    if (item.alertType && !seen.has(item.alertType)) seen.set(item.alertType, item.alarmType)
  })
  return [...seen.entries()].map(([value, label]) => ({ value, label }))
})

// 页签徽标：还没处置的告警数
const pendingAlarmCount = computed(() => alarmRows.value.filter(item => item.status === 'pending').length)

// 录像回放：片段来自设备的真实检索结果（后端按平台能力实现）。
// 改造前这里是写死的 7 段时间轴 + 8 条 2024-01 演示片段，「检索」只弹一句「当前版本未接入」。
const recordingLoading = ref(false)
const recordingSupported = ref(true)
const recordingNotice = ref('')
const recordingSegments = ref([])
const recordingRows = ref([])

const filteredCameras = computed(() => {
  let list = cameras.value
  if (cameraBuildingFilter.value) list = list.filter(c => c.area === cameraBuildingFilter.value)
  if (cameraStatusFilter.value) list = list.filter(c => c.status === cameraStatusFilter.value)
  if (cameraSearch.value) list = list.filter(c => c.name.includes(cameraSearch.value) || c.location.includes(cameraSearch.value))
  return list
})

const displayedCameras = computed(() => {
  const count = gridLayout.value === '2x2' ? 4 : 9
  return filteredCameras.value.slice(0, count)
})

const filteredAlarms = computed(() => {
  let list = alarmRows.value
  if (alarmTypeFilter.value) list = list.filter(a => a.alertType === alarmTypeFilter.value)
  if (alarmStatusFilter.value) list = list.filter(a => a.status === alarmStatusFilter.value)
  if (alarmSearch.value) {
    const keyword = alarmSearch.value
    list = list.filter(a =>
      (a.cameraName || '').includes(keyword)
      || (a.location || '').includes(keyword)
      || (a.alarmType || '').includes(keyword)
    )
  }
  return list
})

const playbackDateStr = computed(() => {
  const [year, month, day] = String(playbackDate.value || '').split('-')
  return year && month && day ? `${year}年${Number(month)}月${Number(day)}日` : ''
})

// 颜色按告警严重度与真实状态码来定（文案由后端给，前端只负责配色）
const SEVERITY_TAGS = { critical: 'danger', high: 'danger', medium: 'warning', low: 'info' }
const STATUS_TAGS = { pending: 'danger', processing: 'warning', resolved: 'success', merged: 'info' }

function severityTag(severity) {
  return SEVERITY_TAGS[severity] || 'info'
}

function statusTag(status) {
  return STATUS_TAGS[status] || 'info'
}

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).replace(/\//g, '-')
}

function statusText(status) {
  const map = { online: '在线', offline: '离线', unknown: '未知' }
  return map[status] || '未知'
}

function statusTagType(status) {
  const map = { online: 'success', offline: 'info', unknown: 'warning' }
  return map[status] || 'info'
}

function registerTile(id, el) {
  if (el) tileRefs[id] = el
  else delete tileRefs[id]
}

function buildSnapshotUrl(cam, stamp) {
  return `/api/video/channels/${cam.id}/snapshot?token=${encodeURIComponent(cam.token)}&_t=${stamp}`
}

function tickFrames() {
  for (const cam of cameras.value) {
    if (cam.token && cam.status === 'online') {
      cam.snapshotUrl = buildSnapshotUrl(cam, Date.now())
    }
  }
}

function refreshSingleFrame(cam) {
  if (!cam.token) {
    ensureTokens().then(tickFrames)
    return
  }
  cam.snapshotUrl = buildSnapshotUrl(cam, Date.now())
}

function onFrameError(cam) {
  // 抓拍失败（设备离线 / 鉴权失败 / 返回非图片）时如实降级为占位，不显示坏图
  cam.snapshotUrl = ''
  cam.status = 'offline'
  cam.lastError = '抓拍失败：设备不可达或账号密码不正确'
}

async function loadChannels() {
  loadingChannels.value = true
  try {
    const { data } = await videoChannels({})
    applyChannels(data.items || [])
    // 录像回放默认选中第一个通道，避免下拉为空时点检索没有反应
    if (!playbackCamera.value && cameras.value.length) {
      playbackCamera.value = cameras.value[0].id
    }
  } catch (error) {
    // 拦截器已提示，这里只保证页面处于可读状态
  } finally {
    loadingChannels.value = false
  }
}

async function ensureTokens(force = false) {
  const targets = cameras.value.filter(cam => !cam.token || force)
  if (!targets.length) return
  const results = await Promise.allSettled(
    targets.map(async cam => {
      const { data } = await videoSnapshotToken(cam.id)
      cam.token = data.token
      cam.snapshotUrl = buildSnapshotUrl(cam, Date.now())
    })
  )
  if (results.every(item => item.status === 'rejected')) {
    ElMessage.warning('抓拍令牌获取失败，画面无法显示')
  }
}

async function loadTodayAlerts() {
  try {
    const { data } = await alertStatistics()
    todayAlerts.value = data.todayCount ?? data.total ?? 0
  } catch (error) {
    todayAlerts.value = 0
  }
}

async function refreshCameras(probe = false) {
  if (probe) {
    if (!cameras.value.length) {
      await loadChannels()
    }
    if (!cameras.value.length) {
      ElMessage.info('尚未配置视频通道，无法探测')
      return
    }
    probing.value = true
    let online = 0
    try {
      for (const cam of cameras.value) {
        try {
          const { data } = await probeVideoChannel(cam.id)
          if (data.online) online += 1
        } catch (error) {
          // 单个通道探测失败不影响其余通道
        }
      }
    } finally {
      probing.value = false
    }
    await loadChannels()
    await ensureTokens()
    tickFrames()
    ElMessage.success(`探测完成：${online}/${cameras.value.length} 个通道在线`)
    return
  }

  await loadChannels()
  await ensureTokens()
  tickFrames()
  ElMessage.success('画面已刷新')
}

async function handlePtz(cam, action) {
  try {
    const { data } = await controlVideoPtz(cam.id, action, 5)
    ElMessage.success(data.message || '云台指令已下发')
    setTimeout(() => refreshSingleFrame(cam), 800)
  } catch (error) {
    // 拦截器已提示具体原因
  }
}

async function handleAnalyze(cam) {
  analyzingId.value = cam.id
  try {
    const { data } = await analyzeVideoChannel(cam.id, true)
    if (!data.hazards.length) {
      ElMessage.success(`未识别到消防隐患（置信度：${data.confidence_label}）`)
      return
    }
    const hazards = data.hazards.join('、')
    if (data.review_required) {
      ElNotification({
        title: `识别到隐患，已转人工复核（置信度：${data.confidence_label}）`,
        message: `${hazards}\n${data.review_reason}`,
        type: 'warning',
        duration: 8000,
      })
    } else {
      ElNotification({
        title: `识别到隐患，已生成告警与工单`,
        message: `${hazards}\n告警号：${data.alert_code}｜工单号：${data.ticket_id ?? '—'}`,
        type: 'error',
        duration: 8000,
      })
    }
    loadTodayAlerts()
  } catch (error) {
    // 拦截器已提示具体原因
  } finally {
    analyzingId.value = null
  }
}

function handleFullScreen(cam) {
  const el = tileRefs[cam.id]
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen?.()
    return
  }
  if (el.requestFullscreen) {
    el.requestFullscreen().catch(() => ElMessage.warning('当前浏览器不支持全屏'))
  } else {
    ElMessage.warning('当前浏览器不支持全屏')
  }
}

// ---- 录像回放：按平台真实能力检索（后端 /api/video/channels/{id}/recordings/search）----

function dayRangeOf(dateStr) {
  const [year, month, day] = String(dateStr || '').split('-').map(Number)
  if (!year || !month || !day) return null
  const start = new Date(year, month - 1, day)
  return { start, end: new Date(start.getTime() + 24 * 3600 * 1000) }
}

function clockText(value) {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
}

function durationText(start, end) {
  const from = new Date(start).getTime()
  const to = new Date(end).getTime()
  if (Number.isNaN(from) || Number.isNaN(to) || to <= from) return '--'
  const minutes = Math.round((to - from) / 60000)
  if (minutes >= 60) return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`
  return `${minutes} 分钟`
}

async function searchRecordings() {
  if (!playbackCamera.value) {
    ElMessage.warning('请先选择摄像头通道')
    return
  }
  recordingLoading.value = true
  try {
    const { data } = await searchVideoRecordings(playbackCamera.value, {
      start_time: `${playbackDate.value} ${playbackStartTime.value}:00`,
      end_time: `${playbackDate.value} ${playbackEndTime.value}:00`,
    })
    recordingSupported.value = Boolean(data.supported)
    const items = data.items || []
    const range = dayRangeOf(playbackDate.value)

    // 时间轴按「所选日期 0 点~24 点」换算百分比，完全由设备返回的起止时间算出
    recordingSegments.value = items.map(item => {
      if (!range) return null
      const from = new Date(item.start_time).getTime()
      const to = new Date(item.end_time).getTime()
      if (Number.isNaN(from) || Number.isNaN(to)) return null
      const total = range.end - range.start
      const left = Math.max(0, Math.min(100, (from - range.start) / total * 100))
      const right = Math.max(0, Math.min(100, (to - range.start) / total * 100))
      return {
        left,
        width: Math.max(0.4, right - left),
        title: `${clockText(item.start_time)} - ${clockText(item.end_time)}`,
      }
    }).filter(Boolean)

    recordingRows.value = items.map(item => ({
      ...item,
      date: String(item.start_time || '').slice(0, 10),
      startText: clockText(item.start_time),
      endText: clockText(item.end_time),
      duration: durationText(item.start_time, item.end_time),
    }))

    if (!data.supported) {
      recordingNotice.value = data.message || '该平台未提供录像检索'
    } else if (!items.length) {
      recordingNotice.value = data.message || '该时间段没有录像'
    } else {
      recordingNotice.value = ''
    }
  } catch (error) {
    // 失败原因由拦截器统一提示
    recordingSupported.value = false
    recordingSegments.value = []
    recordingRows.value = []
  } finally {
    recordingLoading.value = false
  }
}

function refreshRecordings() {
  searchRecordings()
}

// 设备给的是 RTSP 取流地址，浏览器不能直接播，但可以复制给支持 RTSP 的播放器 / 流媒体网关
async function copyPlaybackUri(row) {
  const uri = row?.playback_uri || ''
  if (!uri) {
    ElMessage.warning('该片段没有可用的取流地址')
    return
  }
  try {
    await navigator.clipboard.writeText(uri)
    ElMessage.success('取流地址已复制（浏览器不能直接播放 RTSP，请用支持 RTSP 的播放器或流媒体网关打开）')
  } catch (error) {
    ElMessage.warning(`复制失败，请手工复制：${uri}`)
  }
}

function viewLinkageVideo(row) {
  const matched = cameras.value.find(cam => cam.name && cam.name === row.cameraName)
  if (!matched) {
    // 告警设备没有绑定视频通道，如实说明，不去编一个画面出来
    ElMessage.warning('该告警未关联到视频通道（告警设备与通道未绑定同一设备）')
    return
  }
  activeTab.value = 'video'
  cameraSearch.value = matched.name
  ElMessage.success(`已定位到通道 ${matched.name}`)
}

function goAlertCenter() {
  router.push('/alert-center')
}

// ---- 国标视频（GB28181）：设备/通道来自 SIP 注册与目录应答，画面由 ZLMediaKit 提供 ----

const gbLoading = ref(false)
const gbCatalogLoading = ref(false)
const gbPlayingId = ref(null)
const gbDevices = ref([])
const gbDeviceId = ref(null)
const gbChannels = ref([])
const gbStatus = ref({})

function createGbSlot() {
  return { channelId: null, url: '', mode: 'auto', title: '' }
}

// 4 宫格：点「播放」依次占用空位，占满后替换第一格
const gbSlots = ref([createGbSlot(), createGbSlot(), createGbSlot(), createGbSlot()])
const gbSlotChannelIds = computed(() => gbSlots.value.map(slot => slot.channelId).filter(Boolean))
const gbMediaReady = computed(() => Boolean(gbStatus.value?.media?.api_base))

async function loadGbStatus() {
  try {
    const { data } = await gb28181Status()
    gbStatus.value = data
  } catch (error) {
    gbStatus.value = {}
  }
}

async function loadGbDevices() {
  gbLoading.value = true
  try {
    const { data } = await listGB28181Devices()
    gbDevices.value = data.items || []
    if (!gbDeviceId.value && gbDevices.value.length) {
      gbDeviceId.value = gbDevices.value[0].id
      await loadGbChannels()
    }
  } catch (error) {
    // 拦截器已提示
  } finally {
    gbLoading.value = false
    loadGbStatus()
  }
}

async function loadGbChannels() {
  if (!gbDeviceId.value) {
    gbChannels.value = []
    return
  }
  try {
    const { data } = await listGB28181Channels(gbDeviceId.value)
    gbChannels.value = data.items || []
  } catch (error) {
    gbChannels.value = []
  }
}

async function refreshGbCatalog() {
  if (!gbDeviceId.value) return
  gbCatalogLoading.value = true
  try {
    const { data } = await refreshGB28181Catalog(gbDeviceId.value)
    ElMessage.success(data.message || '目录查询已下发')
    await loadGbChannels()
  } catch (error) {
    // 拦截器已提示（设备离线、地址未登记等）
  } finally {
    gbCatalogLoading.value = false
  }
}

async function playGbChannel(channel) {
  gbPlayingId.value = channel.id
  try {
    const { data } = await playGB28181Channel(channel.id, 'flv')
    const urls = data.urls || {}
    const url = data.preferred_url || urls.flv || urls.hls || ''
    if (!url) {
      ElMessage.warning('设备已应答但未返回可用播放地址，请检查媒体服务器配置')
      return
    }
    const empty = gbSlots.value.findIndex(slot => !slot.url)
    const target = empty >= 0 ? empty : 0
    gbSlots.value[target] = { channelId: channel.id, url, mode: 'auto', title: channel.name }
    ElMessage.success('已发起点播，媒体流到达后即可播放')
  } catch (error) {
    // 拦截器已提示（设备未注册、INVITE 被拒等）
  } finally {
    gbPlayingId.value = null
  }
}

async function stopGbChannel(channel) {
  try {
    await stopGB28181Channel(channel.id)
    gbSlots.value = gbSlots.value.map(slot =>
      slot.channelId === channel.id ? createGbSlot() : slot
    )
    ElMessage.success('已停止点播')
  } catch (error) {
    // 拦截器已提示
  }
}

function clearGbSlot(index) {
  const slot = gbSlots.value[index]
  if (slot?.channelId) {
    stopGbChannel({ id: slot.channelId })
    return
  }
  gbSlots.value[index] = createGbSlot()
}

function onGbPlayFailed(message) {
  console.warn('[国标视频] 播放失败：', message)
}

async function gbPtz(slot, action) {
  if (!slot?.channelId) return
  try {
    const { data } = await gb28181Ptz(slot.channelId, action, 5)
    ElMessage.success(data.message || '云台指令已下发')
  } catch (error) {
    // 拦截器已提示
  }
}

// 首次切到该页签时才拉数据，避免每次进页面都请求
watch(activeTab, tab => {
  if (tab !== 'gb28181') return
  loadGbStatus()
  if (!gbDevices.value.length) loadGbDevices()
})

onMounted(async () => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  await loadChannels()
  await ensureTokens()
  tickFrames()
  loadTodayAlerts()
  loadAlarms()
  pollTimer = setInterval(tickFrames, POLL_SECONDS * 1000)
  tokenTimer = setInterval(() => {
    ensureTokens(true).then(tickFrames)
  }, TOKEN_REFRESH_MS)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (pollTimer) clearInterval(pollTimer)
  if (tokenTimer) clearInterval(tokenTimer)
})
</script>

<style scoped>
.video-monitor-page {
  padding: 0;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.el-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.gray { background: linear-gradient(135deg, #94a3b8, #64748b); }
.stat-icon.orange { background: linear-gradient(135deg, #f59e0b, #d97706); }

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e2e8f0;
}

.tab-item {
  padding: 8px 18px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.tab-item:hover {
  background: #f1f5f9;
  color: #334155;
}

.tab-item.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.tab-item .badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.video-grid {
  display: grid;
  gap: 12px;
}

.video-grid.\32 x2 {
  grid-template-columns: repeat(2, 1fr);
}

.video-grid.\33 x3 {
  grid-template-columns: repeat(3, 1fr);
}

.video-item {
  aspect-ratio: 16 / 9;
}

.video-window {
  width: 100%;
  height: 100%;
  background: #0f172a;
  border-radius: 8px;
  position: relative;
  overflow: hidden;
  border: 1px solid #1e293b;
}

.video-window.offline {
  background: #1e293b;
}

.video-frame {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.video-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #475569;
}

.video-icon {
  font-size: 48px;
  opacity: 0.5;
}

.offline-text {
  font-size: 14px;
  color: #64748b;
}

.live-text {
  font-size: 14px;
  font-weight: 600;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
  padding: 2px 8px;
  border-radius: 4px;
  position: absolute;
  top: 10px;
  right: 10px;
}

.video-overlay {
  position: absolute;
  left: 0;
  right: 0;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #fff;
  font-size: 12px;
}

.video-overlay.top {
  top: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.7) 0%, transparent 100%);
}

.video-overlay.bottom {
  bottom: 0;
  background: linear-gradient(0deg, rgba(0,0,0,0.7) 0%, transparent 100%);
}

.camera-name {
  font-weight: 600;
  font-size: 13px;
}

.camera-location {
  color: #cbd5e1;
}

.video-time {
  font-family: 'Courier New', monospace;
  color: #e2e8f0;
}

.video-controls {
  position: absolute;
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-window:hover .video-controls {
  opacity: 1;
}

.ptz-controls {
  position: absolute;
  bottom: 40px;
  right: 8px;
  width: 80px;
  height: 80px;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-window:hover .ptz-controls {
  opacity: 1;
}

.ptz-btn {
  position: absolute;
  background: rgba(255, 255, 255, 0.9) !important;
}

.ptz-top { top: 0; left: 50%; transform: translateX(-50%); }
.ptz-bottom { bottom: 0; left: 50%; transform: translateX(-50%); }
.ptz-left { left: 0; top: 50%; transform: translateY(-50%); }
.ptz-right { right: 0; top: 50%; transform: translateY(-50%); }

.rotate-right {
  transform: rotate(180deg);
}

.timeline-section {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.timeline-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.timeline-date {
  font-size: 13px;
  color: #64748b;
}

.timeline-bar {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
}

.timeline-scale {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.scale-mark {
  flex: 1;
  text-align: center;
}

.timeline-track {
  position: relative;
  height: 24px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.timeline-segment {
  position: absolute;
  top: 3px;
  bottom: 3px;
  border-radius: 3px;
  cursor: pointer;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.timeline-segment:hover {
  opacity: 1;
}

.timeline-legend {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #64748b;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.legend-dot.alarm { background: #ef4444; }
.legend-dot.motion { background: #f59e0b; }
.legend-dot.normal { background: #3b82f6; }

.recording-list {
  margin-top: 8px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.list-count {
  font-size: 12px;
  color: #64748b;
}

.danger-text {
  color: #ef4444;
  font-weight: 600;
}

/* ---- 国标视频（GB28181） ---- */

.gb-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 14px;
  align-items: start;
}

.gb-list {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  max-height: 560px;
  overflow-y: auto;
}

.gb-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  position: sticky;
  top: 0;
}

.gb-list-count {
  font-size: 12px;
  color: #64748b;
  font-weight: 400;
}

.gb-empty {
  padding: 18px 12px;
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
}

.gb-channel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.2s;
}

.gb-channel:hover {
  background: #f8fafc;
}

.gb-channel.active {
  background: #eff6ff;
}

.gb-channel-info {
  min-width: 0;
}

.gb-channel-name {
  font-size: 13px;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gb-channel-meta {
  font-size: 11px;
  color: #94a3b8;
  font-family: 'Courier New', monospace;
}

.gb-channel-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.gb-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.gb-tile {
  position: relative;
  aspect-ratio: 16 / 9;
}

.gb-tile-actions {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.gb-tile:hover .gb-tile-actions {
  opacity: 1;
}

.warning-text {
  color: #f59e0b;
  font-weight: 600;
}
</style>
