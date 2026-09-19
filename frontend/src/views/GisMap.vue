<template>
  <div class="gis-map-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">GIS 地图总览</h2>
        <p class="page-desc">建筑分布、设备位置、风险热力图、实时态势一览</p>
      </div>
      <div class="header-actions">
        <el-select v-model="mapLayer" placeholder="图层切换" style="width: 140px" @change="handleLayerChange">
          <el-option label="3D建筑分布" value="buildings" />
          <el-option label="设备位置" value="devices" />
          <el-option label="风险热力图" value="heatmap" />
        </el-select>
        <el-button type="primary" @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <el-row :gutter="12" class="stat-row">
      <el-col :xs="24" :sm="12" :md="4">
        <div class="stat-card blue">
          <div class="stat-icon-box"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboard.building_count || 0 }}</div>
            <div class="stat-label">建筑总数</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="4">
        <div class="stat-card indigo">
          <div class="stat-icon-box"><el-icon><Cpu /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboard.device_count || 0 }}</div>
            <div class="stat-label">设备总数</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="4">
        <div class="stat-card green">
          <div class="stat-icon-box"><el-icon><Connection /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboard.online_device_count || 0 }}</div>
            <div class="stat-label">在线设备</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="4">
        <div class="stat-card red">
          <div class="stat-icon-box"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboard.pending_alert_count || 0 }}</div>
            <div class="stat-label">待处理告警</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="4">
        <div class="stat-card orange">
          <div class="stat-icon-box"><el-icon><Tickets /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboard.pending_workorder_count || 0 }}</div>
            <div class="stat-label">待处理工单</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="4">
        <div class="stat-card danger">
          <div class="stat-icon-box"><el-icon><HotWater /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboard.high_risk_building_count || 0 }}</div>
            <div class="stat-label">高风险建筑数</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="main-row">
      <el-col :xs="24" :lg="6">
        <el-card class="building-list-card">
          <template #header>
            <div class="card-header">
              <strong>建筑列表</strong>
              <el-tag size="small" type="info">{{ buildings.length }} 栋</el-tag>
            </div>
          </template>
          <div class="building-search">
            <el-input v-model="searchKeyword" placeholder="搜索建筑名称" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
          <div class="building-list-scroll">
            <div
              v-for="b in filteredBuildings"
              :key="b.id"
              class="building-item"
              :class="{ active: selectedBuilding?.id === b.id }"
              @click="selectBuilding(b)"
            >
              <div class="building-item-header">
                <span class="building-item-name">{{ b.building_name || b.name }}</span>
                <el-tag :type="getRiskTagType(b.risk_level)" size="small">{{ getRiskLabel(b.risk_level) }}</el-tag>
              </div>
              <div class="building-item-meta">
                <span><el-icon><Location /></el-icon> {{ b.latitude?.toFixed(4) }}, {{ b.longitude?.toFixed(4) }}</span>
              </div>
              <div class="building-item-stats">
                <span>设备 {{ b.device_count || 0 }}</span>
                <span>告警 {{ b.alert_count || 0 }}</span>
              </div>
            </div>
            <el-empty v-if="!filteredBuildings.length" description="暂无建筑数据" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="18">
        <el-card class="map-card">
          <template #header>
            <div class="card-header">
              <span>
                <strong>{{ mapLayerTitle }}</strong>
                <span class="map-subtitle">鼠标拖拽旋转 · 滚轮缩放 · 右键平移</span>
              </span>
              <div class="map-legend">
                <span class="legend-item"><i class="legend-dot high"></i>高风险</span>
                <span class="legend-item"><i class="legend-dot medium"></i>中风险</span>
                <span class="legend-item"><i class="legend-dot low"></i>低风险</span>
              </div>
            </div>
          </template>
          <div class="map-container" ref="mapContainerRef">
            <div v-if="!sceneReady" class="map-loading">
              <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
              <p>3D场景加载中...</p>
            </div>
            <div v-if="hoveredBuilding" class="building-tooltip" :style="tooltipStyle">
              <div class="tooltip-title">{{ hoveredBuilding.building_name || hoveredBuilding.name }}</div>
              <div class="tooltip-row"><span>风险等级:</span><el-tag :type="getRiskTagType(hoveredBuilding.risk_level)" size="small">{{ getRiskLabel(hoveredBuilding.risk_level) }}</el-tag></div>
              <div class="tooltip-row"><span>风险分数:</span><strong>{{ hoveredBuilding.risk_score }}</strong></div>
              <div class="tooltip-row"><span>设备数量:</span>{{ hoveredBuilding.device_count || 0 }}</div>
              <div class="tooltip-row"><span>告警数量:</span>{{ hoveredBuilding.alert_count || 0 }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="alert-row">
      <el-col :xs="24" :lg="12">
        <el-card class="alert-card">
          <template #header>
            <div class="card-header">
              <span><strong>实时告警</strong><el-tag type="danger" size="small" style="margin-left: 8px">{{ realtimeAlerts.length }}</el-tag></span>
              <el-button link type="primary" size="small">查看全部</el-button>
            </div>
          </template>
          <div class="alert-list">
            <div v-for="a in realtimeAlerts" :key="a.id" class="alert-item" :class="getAlertClass(a.severity)">
              <div class="alert-icon">
                <el-icon v-if="a.severity === 'high' || a.severity === 'critical'"><WarningFilled /></el-icon>
                <el-icon v-else><InfoFilled /></el-icon>
              </div>
              <div class="alert-content">
                <div class="alert-title">{{ a.title }}</div>
                <div class="alert-desc">{{ a.building }} · {{ a.device }} · {{ a.time }}</div>
              </div>
              <el-button size="small" type="primary" link>处理</el-button>
            </div>
            <el-empty v-if="!realtimeAlerts.length" description="暂无实时告警" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card class="alert-card">
          <template #header>
            <div class="card-header">
              <span><strong>最近告警</strong></span>
              <el-button link type="primary" size="small">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentAlerts" size="small" stripe>
            <el-table-column prop="time" label="时间" width="150" />
            <el-table-column prop="building" label="建筑" width="130" />
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'info'" size="small">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="告警描述" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'pending' ? 'warning' : 'success'" size="small">{{ row.status === 'pending' ? '待处理' : '已处理' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh,
  OfficeBuilding,
  Cpu,
  Connection,
  Warning,
  Tickets,
  HotWater,
  Search,
  Location,
  WarningFilled,
  InfoFilled,
  Loading
} from '@element-plus/icons-vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { getGisBuildings, getGisDevices, getGisHeatmap, getGisDashboard } from '../api/gis'

const loading = ref(false)
const mapLayer = ref('buildings')
const searchKeyword = ref('')
const selectedBuilding = ref(null)
const sceneReady = ref(false)

const dashboard = ref({})
const buildings = ref([])
const devices = ref([])
const heatmapData = ref([])

const mapContainerRef = ref(null)
let scene = null
let camera = null
let renderer = null
let controls = null
let buildingMeshes = []
let deviceMeshes = []
let animationFrameId = null
let raycaster = null
let mouse = new THREE.Vector2()

const hoveredBuilding = ref(null)
const tooltipStyle = ref({ left: '0px', top: '0px' })

const realtimeAlerts = ref([
  { id: 1, title: '烟感探测器告警', building: '综合办公楼A座', device: '3F-烟感-02', severity: 'high', time: '10:32:15' },
  { id: 2, title: '温度传感器异常', building: '实验楼B座', device: 'B2-温感-05', severity: 'medium', time: '10:28:42' },
  { id: 3, title: '消防水压偏低', building: '学生宿舍C区', device: '水泵-01', severity: 'high', time: '10:15:30' },
  { id: 4, title: '防火门状态异常', building: '综合办公楼A座', device: '1F-防火门-03', severity: 'low', time: '10:05:18' },
])

const recentAlerts = ref([
  { time: '2026-07-30 10:32', building: '综合办公楼A座', type: '烟感告警', severity: 'high', description: '3层西侧烟感触发告警', status: 'pending' },
  { time: '2026-07-30 09:45', building: '实验楼B座', type: '温度异常', severity: 'medium', description: '实验室温度超阈值', status: 'pending' },
  { time: '2026-07-30 08:20', building: '学生宿舍C区', type: '水压告警', severity: 'high', description: '消防管网水压偏低', status: 'handled' },
  { time: '2026-07-29 22:15', building: '图书馆D座', type: '设备离线', severity: 'low', description: '地下层设备通信中断', status: 'handled' },
  { time: '2026-07-29 16:30', building: '食堂E区', type: '燃气告警', severity: 'high', description: '厨房燃气浓度异常', status: 'handled' },
])

const mapLayerTitle = computed(() => {
  const map = { buildings: '3D建筑分布图', devices: '设备位置图', heatmap: '风险热力图' }
  return map[mapLayer.value] || '3D建筑分布图'
})

const filteredBuildings = computed(() => {
  if (!searchKeyword.value) return buildings.value
  const kw = searchKeyword.value.toLowerCase()
  return buildings.value.filter(b => (b.building_name || b.name)?.toLowerCase().includes(kw))
})

function getRiskColor(level, score) {
  if (level === 'high' || level === '高风险' || level === 'critical' || score >= 60) return 0xef4444
  if (level === 'medium' || level === '中风险' || (score >= 35 && score < 60)) return 0xf59e0b
  return 0x22c55e
}

function getRiskTagType(level) {
  if (level === 'high' || level === 'critical' || level === '高风险') return 'danger'
  if (level === 'medium' || level === '中风险') return 'warning'
  return 'success'
}

function getRiskLabel(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险', critical: '严重', '高风险': '高风险', '中风险': '中风险', '低风险': '低风险' }
  return map[level] || '低风险'
}

function getAlertClass(severity) {
  if (severity === 'high' || severity === 'critical') return 'alert-high'
  if (severity === 'medium') return 'alert-medium'
  return 'alert-low'
}

function initScene() {
  if (!mapContainerRef.value) return

  const width = mapContainerRef.value.clientWidth
  const height = 520

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf1f5f9)
  scene.fog = new THREE.Fog(0xf1f5f9, 80, 300)

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000)
  camera.position.set(40, 50, 60)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  mapContainerRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 15
  controls.maxDistance = 200
  controls.maxPolarAngle = Math.PI / 2.1
  controls.target.set(0, 5, 0)

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.65)
  scene.add(ambientLight)

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.9)
  directionalLight.position.set(50, 80, 40)
  directionalLight.castShadow = true
  directionalLight.shadow.mapSize.width = 2048
  directionalLight.shadow.mapSize.height = 2048
  directionalLight.shadow.camera.near = 0.5
  directionalLight.shadow.camera.far = 500
  directionalLight.shadow.camera.left = -100
  directionalLight.shadow.camera.right = 100
  directionalLight.shadow.camera.top = 100
  directionalLight.shadow.camera.bottom = -100
  scene.add(directionalLight)

  const hemisphereLight = new THREE.HemisphereLight(0x87ceeb, 0x3d5c3d, 0.4)
  scene.add(hemisphereLight)

  const groundGeometry = new THREE.PlaneGeometry(200, 200, 50, 50)
  const groundMaterial = new THREE.MeshStandardMaterial({
    color: 0xe2e8f0,
    roughness: 0.9,
    metalness: 0.0,
  })
  const ground = new THREE.Mesh(groundGeometry, groundMaterial)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  const gridHelper = new THREE.GridHelper(200, 40, 0x94a3b8, 0xd1d5db)
  gridHelper.position.y = 0.01
  scene.add(gridHelper)

  raycaster = new THREE.Raycaster()

  renderer.domElement.addEventListener('mousemove', onMouseMove)
  renderer.domElement.addEventListener('click', onClick)
  window.addEventListener('resize', onWindowResize)

  animate()
  sceneReady.value = true
}

function onMouseMove(event) {
  if (!renderer || !camera) return
  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(buildingMeshes, false)

  if (intersects.length > 0) {
    const mesh = intersects[0].object
    hoveredBuilding.value = mesh.userData.building
    tooltipStyle.value = {
      left: `${event.clientX - rect.left + 15}px`,
      top: `${event.clientY - rect.top + 15}px`
    }
    buildingMeshes.forEach(m => {
      if (m.userData.building?.id === mesh.userData.building?.id) {
        m.scale.set(1.05, 1.05, 1.05)
      } else {
        m.scale.set(1, 1, 1)
      }
    })
  } else {
    hoveredBuilding.value = null
    buildingMeshes.forEach(m => m.scale.set(1, 1, 1))
  }
}

function onClick(event) {
  if (!renderer || !camera) return
  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(buildingMeshes, false)

  if (intersects.length > 0) {
    const b = intersects[0].object.userData.building
    selectBuilding(b)
  }
}

function onWindowResize() {
  if (!mapContainerRef.value || !camera || !renderer) return
  const width = mapContainerRef.value.clientWidth
  const height = 520
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function animate() {
  animationFrameId = requestAnimationFrame(animate)
  controls?.update()
  renderer?.render(scene, camera)
}

function latLngToPosition(lat, lng) {
  const centerLat = 39.92
  const centerLng = 116.42
  const scale = 8000
  const x = (lng - centerLng) * scale
  const z = (centerLat - lat) * scale
  return { x, z }
}

function createBuildings() {
  buildingMeshes.forEach(m => scene.remove(m))
  buildingMeshes = []

  const baseHeight = 2
  const heightScale = 0.08

  buildings.value.forEach(b => {
    const pos = latLngToPosition(b.latitude || 0, b.longitude || 0)
    const floors = b.floors || Math.max(3, Math.round((b.risk_score || 30) / 10))
    const height = baseHeight + floors * heightScale
    const width = 3 + Math.random() * 2
    const depth = 3 + Math.random() * 2

    const color = getRiskColor(b.risk_level, b.risk_score)

    const geometry = new THREE.BoxGeometry(width, height, depth)
    const material = new THREE.MeshStandardMaterial({
      color: color,
      roughness: 0.5,
      metalness: 0.1,
      transparent: true,
      opacity: 0.92,
    })
    const building = new THREE.Mesh(geometry, material)
    building.position.set(pos.x, height / 2, pos.z)
    building.castShadow = true
    building.receiveShadow = true
    building.userData.building = b

    const edgeGeometry = new THREE.EdgesGeometry(geometry)
    const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.6 })
    const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial)
    building.add(edges)

    const roofGeometry = new THREE.BoxGeometry(width * 1.05, 0.3, depth * 1.05)
    const roofMaterial = new THREE.MeshStandardMaterial({
      color: 0x475569,
      roughness: 0.7,
    })
    const roof = new THREE.Mesh(roofGeometry, roofMaterial)
    roof.position.y = height / 2 + 0.15
    roof.castShadow = true
    building.add(roof)

    if (mapLayer.value === 'heatmap') {
      const glowGeometry = new THREE.CylinderGeometry(width * 0.8, width * 1.2, 0.1, 32)
      const glowColor = getRiskColor(b.risk_level, b.risk_score)
      const glowMaterial = new THREE.MeshBasicMaterial({
        color: glowColor,
        transparent: true,
        opacity: 0.35,
      })
      const glow = new THREE.Mesh(glowGeometry, glowMaterial)
      glow.position.y = 0.05
      building.add(glow)
    }

    scene.add(building)
    buildingMeshes.push(building)
  })
}

function createDevices() {
  deviceMeshes.forEach(m => scene.remove(m))
  deviceMeshes = []

  if (mapLayer.value !== 'devices' && mapLayer.value !== 'heatmap') return

  const buildingMap = {}
  buildings.value.forEach(b => { buildingMap[b.id] = b })

  devices.value.forEach(d => {
    const lat = d.latitude || buildingMap[d.building_id]?.latitude || 0
    const lng = d.longitude || buildingMap[d.building_id]?.longitude || 0
    const pos = latLngToPosition(lat, lng)

    const s = (d.status || '').toLowerCase()
    let color = 0x94a3b8
    if (s === 'alarm' || s.includes('告警') || s.includes('故障') || s.includes('异常')) color = 0xef4444
    else if (s === 'online' || s.includes('在线') || s.includes('正常')) color = 0x22c55e

    let geometry
    if (s === 'alarm' || s.includes('告警')) {
      geometry = new THREE.ConeGeometry(0.4, 0.8, 4)
    } else {
      geometry = new THREE.SphereGeometry(0.3, 16, 16)
    }

    const material = new THREE.MeshStandardMaterial({
      color: color,
      emissive: color,
      emissiveIntensity: 0.4,
      roughness: 0.3,
      metalness: 0.5,
    })
    const deviceMesh = new THREE.Mesh(geometry, material)
    deviceMesh.position.set(pos.x + (Math.random() - 0.5) * 3, 1.5, pos.z + (Math.random() - 0.5) * 3)
    deviceMesh.castShadow = true
    deviceMesh.userData.device = d

    scene.add(deviceMesh)
    deviceMeshes.push(deviceMesh)
  })
}

function updateScene() {
  if (!scene) return
  createBuildings()
  createDevices()
}

function selectBuilding(b) {
  selectedBuilding.value = b
  if (scene && controls && buildingMeshes.length) {
    const pos = latLngToPosition(b.latitude || 0, b.longitude || 0)
    controls.target.set(pos.x, 5, pos.z)
    camera.position.set(pos.x + 25, 35, pos.z + 35)
  }
  ElMessage.info(`已定位：${b.building_name || b.name}`)
}

function handleLayerChange() {
  ElMessage.success(`已切换至：${mapLayerTitle.value}`)
  updateScene()
}

async function loadData() {
  loading.value = true
  try {
    const [dashRes, buildRes, devRes, heatRes] = await Promise.allSettled([
      getGisDashboard(),
      getGisBuildings(),
      getGisDevices(),
      getGisHeatmap(),
    ])

    if (dashRes.status === 'fulfilled') dashboard.value = dashRes.value?.data || {}
    if (buildRes.status === 'fulfilled') buildings.value = buildRes.value?.data?.buildings || buildRes.value?.data || fallbackBuildings()
    if (devRes.status === 'fulfilled') devices.value = devRes.value?.data?.devices || devRes.value?.data || fallbackDevices()
    if (heatRes.status === 'fulfilled') heatmapData.value = heatRes.value?.data?.heatmap || heatRes.value?.data || []

    if (!buildings.value.length) buildings.value = fallbackBuildings()
    if (!devices.value.length) devices.value = fallbackDevices()
    if (!dashboard.value.building_count) dashboard.value = {
      building_count: buildings.value.length,
      device_count: devices.value.length,
      online_device_count: devices.value.filter(d => {
        const s = (d.status || '').toLowerCase()
        return s === 'online' || s.includes('在线') || s.includes('正常')
      }).length,
      pending_alert_count: realtimeAlerts.value.length,
      pending_workorder_count: 8,
      high_risk_building_count: buildings.value.filter(b =>
        b.risk_level === 'high' || b.risk_level === '高风险' || b.risk_score >= 60
      ).length,
    }
  } catch (e) {
    buildings.value = fallbackBuildings()
    devices.value = fallbackDevices()
  } finally {
    loading.value = false
  }
}

function fallbackBuildings() {
  return [
    { id: 'b1', building_name: '综合办公楼A座', latitude: 39.9042, longitude: 116.4074, risk_level: 'high', risk_score: 87, device_count: 42, alert_count: 3, floors: 12 },
    { id: 'b2', building_name: '实验楼B座', latitude: 39.9200, longitude: 116.4400, risk_level: 'high', risk_score: 72, device_count: 58, alert_count: 2, floors: 6 },
    { id: 'b3', building_name: '学生宿舍C区', latitude: 39.9500, longitude: 116.4100, risk_level: 'medium', risk_score: 58, device_count: 36, alert_count: 1, floors: 8 },
    { id: 'b4', building_name: '图书馆D座', latitude: 39.9100, longitude: 116.3800, risk_level: 'low', risk_score: 35, device_count: 24, alert_count: 0, floors: 4 },
    { id: 'b5', building_name: '食堂E区', latitude: 39.9350, longitude: 116.4250, risk_level: 'medium', risk_score: 48, device_count: 30, alert_count: 1, floors: 3 },
    { id: 'b6', building_name: '地下车库F区', latitude: 39.9000, longitude: 116.3950, risk_level: 'low', risk_score: 28, device_count: 18, alert_count: 0, floors: 2 },
    { id: 'b7', building_name: '体育馆G座', latitude: 39.9450, longitude: 116.4500, risk_level: 'low', risk_score: 32, device_count: 28, alert_count: 0, floors: 2 },
    { id: 'b8', building_name: '行政楼H座', latitude: 39.9150, longitude: 116.4200, risk_level: 'medium', risk_score: 52, device_count: 34, alert_count: 1, floors: 5 },
  ]
}

function fallbackDevices() {
  const arr = []
  const types = ['烟感探测器', '温感探测器', '手动报警按钮', '消火栓', '喷淋头', '防火门']
  const builds = fallbackBuildings()
  for (let i = 0; i < 50; i++) {
    const b = builds[i % builds.length]
    const latOffset = (Math.random() - 0.5) * 0.008
    const lngOffset = (Math.random() - 0.5) * 0.008
    arr.push({
      id: `d${i+1}`,
      device_name: `${types[i % types.length]}-${String(i+1).padStart(3,'0')}`,
      building_id: b.id,
      building_name: b.building_name || b.name,
      latitude: b.latitude + latOffset,
      longitude: b.longitude + lngOffset,
      status: i < 3 ? 'alarm' : i < 45 ? 'online' : 'offline'
    })
  }
  return arr
}

function refreshData() {
  loadData().then(() => {
    updateScene()
    ElMessage.success('数据已刷新')
  })
}

watch(buildings, () => {
  nextTick(() => {
    if (sceneReady.value) updateScene()
  })
}, { deep: true })

onMounted(() => {
  loadData().then(() => {
    nextTick(() => {
      initScene()
      updateScene()
    })
  })
})

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  window.removeEventListener('resize', onWindowResize)
  if (renderer?.domElement) {
    renderer.domElement.removeEventListener('mousemove', onMouseMove)
    renderer.domElement.removeEventListener('click', onClick)
  }
  controls?.dispose()
  renderer?.dispose()
  scene = null
  camera = null
  renderer = null
  controls = null
})
</script>

<style scoped>
.gis-map-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 6px;
}

.page-desc {
  color: #64748b;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.stat-row {
  margin-bottom: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px 16px;
  border-top: 4px solid;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
  min-height: 84px;
}

.stat-card.blue { border-top-color: #2563eb; }
.stat-card.indigo { border-top-color: #4f46e5; }
.stat-card.green { border-top-color: #22c55e; }
.stat-card.red { border-top-color: #ef4444; }
.stat-card.orange { border-top-color: #f97316; }
.stat-card.danger { border-top-color: #dc2626; }

.stat-icon-box {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}

.blue .stat-icon-box { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.indigo .stat-icon-box { background: linear-gradient(135deg, #6366f1, #4f46e5); }
.green .stat-icon-box { background: linear-gradient(135deg, #4ade80, #22c55e); }
.red .stat-icon-box { background: linear-gradient(135deg, #f87171, #ef4444); }
.orange .stat-icon-box { background: linear-gradient(135deg, #fb923c, #f97316); }
.danger .stat-icon-box { background: linear-gradient(135deg, #ef4444, #dc2626); }

.stat-info { flex: 1; }

.stat-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.15;
  color: #0f172a;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.main-row {
  margin-bottom: 12px;
}

.building-list-card {
  height: 580px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.building-search {
  margin-bottom: 10px;
}

.building-list-scroll {
  height: calc(100% - 90px);
  overflow-y: auto;
  padding-right: 4px;
}

.building-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.building-item:hover {
  border-color: #3b82f6;
  background: #f8fafc;
}

.building-item.active {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15);
}

.building-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.building-item-name {
  font-weight: 600;
  font-size: 13px;
}

.building-item-meta {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.building-item-stats {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #475569;
  padding-top: 6px;
  border-top: 1px dashed #e2e8f0;
}

.map-card {
  height: 580px;
}

.map-subtitle {
  font-size: 12px;
  color: #64748b;
  font-weight: 400;
  margin-left: 8px;
}

.map-legend {
  display: flex;
  gap: 14px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #475569;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.legend-dot.high { background: #ef4444; }
.legend-dot.medium { background: #f59e0b; }
.legend-dot.low { background: #22c55e; }

.map-container {
  width: 100%;
  height: 520px;
  position: relative;
  background: #f1f5f9;
  border-radius: 12px;
  overflow: hidden;
}

.map-container :deep(canvas) {
  display: block;
}

.map-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  gap: 10px;
  background: #f1f5f9;
}

.loading-icon {
  animation: spin 1s linear infinite;
  color: #2563eb;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.building-tooltip {
  position: absolute;
  background: rgba(15, 23, 42, 0.95);
  color: #fff;
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 12px;
  pointer-events: none;
  z-index: 100;
  min-width: 180px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(8px);
}

.tooltip-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  gap: 10px;
}

.tooltip-row span {
  color: #94a3b8;
}

.tooltip-row strong {
  color: #fff;
}

.alert-row {
  margin-bottom: 12px;
}

.alert-card {
  min-height: 320px;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  border-left: 4px solid;
  background: #f8fafc;
}

.alert-item.alert-high {
  border-left-color: #ef4444;
  background: #fff5f5;
}

.alert-item.alert-medium {
  border-left-color: #f59e0b;
  background: #fffbeb;
}

.alert-item.alert-low {
  border-left-color: #22c55e;
  background: #f0fdf4;
}

.alert-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.alert-high .alert-icon { color: #ef4444; }
.alert-medium .alert-icon { color: #f59e0b; }
.alert-low .alert-icon { color: #22c55e; }

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 3px;
}

.alert-desc {
  font-size: 12px;
  color: #64748b;
}
</style>
