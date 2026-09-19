<template>
  <div class="floor-plan-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">楼层平面图管理</h2>
        <p class="page-desc">建筑楼层管理、平面图上传、设备位置标注</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="5">
        <el-card class="side-card building-card">
          <template #header>
            <div class="card-header">
              <span>建筑选择</span>
            </div>
          </template>
          <el-select
            v-model="selectedBuildingId"
            placeholder="请选择建筑"
            style="width: 100%"
            @change="handleBuildingChange"
          >
            <el-option
              v-for="building in buildings"
              :key="building.id"
              :label="building.building_name || building.name"
              :value="building.id"
            />
          </el-select>
        </el-card>

        <el-card class="side-card floor-card">
          <template #header>
            <div class="card-header">
              <span>楼层列表</span>
              <el-button
                type="primary"
                size="small"
                :icon="Plus"
                @click="openFloorDialog()"
                :disabled="!selectedBuildingId"
              >
                新增
              </el-button>
            </div>
          </template>
          <div v-if="!selectedBuildingId" class="empty-tip">
            请先选择建筑
          </div>
          <div v-else-if="floors.length === 0" class="empty-tip">
            暂无楼层数据，点击新增添加
          </div>
          <div v-else class="floor-list">
            <div
              v-for="floor in floors"
              :key="floor.id"
              class="floor-item"
              :class="{ active: selectedFloorId === floor.id }"
              @click="selectFloor(floor)"
            >
              <div class="floor-info">
                <span class="floor-name">{{ floor.floor_name }}</span>
                <span class="floor-code">{{ floor.floor_number }}层</span>
              </div>
              <div class="floor-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click.stop="openFloorDialog(floor)"
                >
                  编辑
                </el-button>
                <el-button
                  type="danger"
                  link
                  size="small"
                  @click.stop="handleDeleteFloor(floor)"
                >
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="13">
        <el-card class="main-card plan-card">
          <template #header>
            <div class="card-header">
              <span>
                平面图
                <el-tag v-if="selectedFloor" type="info" size="small" style="margin-left: 8px;">
                  {{ selectedFloor.floor_name }}
                </el-tag>
              </span>
              <el-upload
                :show-file-list="false"
                :before-upload="beforeUploadPlan"
                :disabled="!selectedFloorId"
                accept="image/*"
              >
                <el-button size="small" type="primary" :icon="Upload" :disabled="!selectedFloorId">
                  上传平面图
                </el-button>
              </el-upload>
            </div>
          </template>
          <div class="plan-container" ref="planContainerRef">
            <div v-if="!selectedFloorId" class="plan-placeholder">
              <el-icon :size="48" color="#cbd5e1"><Picture /></el-icon>
              <p>请先选择建筑和楼层</p>
            </div>
            <div v-else-if="!floorPlanUrl" class="plan-placeholder">
              <el-icon :size="48" color="#cbd5e1"><Picture /></el-icon>
              <p>当前楼层暂无平面图</p>
              <p class="sub-tip">点击上方"上传平面图"按钮添加</p>
            </div>
            <div v-else class="plan-wrapper" ref="planWrapperRef">
              <img
                :src="floorPlanUrl"
                alt="楼层平面图"
                class="plan-image"
                ref="planImageRef"
                @load="handleImageLoad"
              />
              <div
                v-for="device in floorDevices"
                :key="device.id"
                class="device-marker"
                :class="{
                  active: highlightedDeviceId === device.id,
                  dragging: draggingDeviceId === device.id
                }"
                :style="getMarkerStyle(device)"
                @mousedown="startDrag($event, device)"
                @click="highlightDevice(device)"
              >
                <div class="marker-dot" :style="{ background: getDeviceColor(device.device_type) }">
                  <el-icon :size="12"><Monitor /></el-icon>
                </div>
                <div class="marker-tooltip">{{ device.device_name || device.device_code }}</div>
              </div>
            </div>
          </div>
          <div v-if="selectedFloor" class="plan-legend">
            <span class="legend-title">设备类型图例：</span>
            <span v-for="(color, type) in deviceTypeColors" :key="type" class="legend-item">
              <span class="legend-dot" :style="{ background: color }"></span>
              {{ type }}
            </span>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="side-card device-card">
          <template #header>
            <div class="card-header">
              <span>设备列表</span>
              <el-tag v-if="selectedFloor" type="info" size="small">
                {{ floorDevices.length }} 台
              </el-tag>
            </div>
          </template>
          <div class="device-search">
            <el-input
              v-model="deviceSearchKeyword"
              placeholder="搜索设备名称/编码"
              :prefix-icon="Search"
              clearable
            />
          </div>
          <div class="device-actions">
            <el-button
              type="primary"
              size="small"
              style="width: 100%"
              :icon="Plus"
              @click="openAddDeviceDialog"
              :disabled="!selectedFloorId"
            >
              添加设备到楼层
            </el-button>
          </div>
          <div v-if="!selectedFloorId" class="empty-tip">
            请先选择建筑和楼层
          </div>
          <div v-else-if="filteredDevices.length === 0" class="empty-tip">
            暂无设备数据
          </div>
          <div v-else class="device-list">
            <div
              v-for="device in filteredDevices"
              :key="device.id"
              class="device-item"
              :class="{ active: highlightedDeviceId === device.id }"
              @click="highlightDevice(device)"
            >
              <div class="device-icon" :style="{ background: getDeviceColor(device.device_type) }">
                <el-icon :size="14"><Monitor /></el-icon>
              </div>
              <div class="device-info">
                <div class="device-name">{{ device.device_name || device.device_code }}</div>
                <div class="device-type">{{ device.device_type }}</div>
              </div>
              <el-button
                type="danger"
                link
                size="small"
                @click.stop="handleRemoveDevice(device)"
              >
                移除
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="floorDialogVisible" :title="editingFloor ? '编辑楼层' : '新增楼层'" width="480px">
      <el-form :model="floorForm" label-width="100px">
        <el-form-item label="楼层名称" required>
          <el-input v-model="floorForm.name" placeholder="如：1层、2层、地下1层" />
        </el-form-item>
        <el-form-item label="楼层编码">
          <el-input v-model="floorForm.floor_code" placeholder="如：F1、F2、B1" />
        </el-form-item>
        <el-form-item label="楼层序号">
          <el-input-number v-model="floorForm.floor_number" :min="-10" :max="200" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="floorForm.description" type="textarea" :rows="3" placeholder="楼层描述信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="floorDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveFloor" :loading="floorSaving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addDeviceDialogVisible" title="添加设备到楼层" width="600px">
      <el-input
        v-model="allDeviceSearch"
        placeholder="搜索设备名称/编码"
        :prefix-icon="Search"
        clearable
        style="margin-bottom: 12px;"
      />
      <el-table
        :data="filteredAllDevices"
        height="400"
        @selection-change="handleDeviceSelectionChange"
        ref="deviceTableRef"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="device_code" label="设备编码" width="140" />
        <el-table-column prop="device_name" label="设备名称" />
        <el-table-column prop="device_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.device_type }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="addDeviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddDevices" :disabled="selectedDevicesToAdd.length === 0">
          确认添加 ({{ selectedDevicesToAdd.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, Upload, Search, Picture, Monitor } from '@element-plus/icons-vue'
import request, { fetchObjectUrl } from '../api'
import {
  listFloors,
  getFloorDetail,
  createFloor,
  updateFloor,
  deleteFloor,
  uploadFloorPlan,
  updateDevicePosition
} from '../api/floor'

const loading = ref(false)
const buildings = ref([])
const selectedBuildingId = ref(null)

const floors = ref([])
const selectedFloorId = ref(null)
const selectedFloor = ref(null)

const floorDialogVisible = ref(false)
const editingFloor = ref(null)
const floorSaving = ref(false)
const floorForm = ref({
  name: '',
  floor_code: '',
  floor_number: 1,
  description: ''
})

const floorPlanUrl = ref('')
const floorPlanObjectUrl = ref('')

/**
 * 设置楼层平面图地址：受控地址（/api/files/*）需先取回二进制再转 objectURL，
 * 外部链接则直接使用。
 */
async function setFloorPlanUrl(raw) {
  releaseFloorPlanUrl()
  if (!raw) {
    floorPlanUrl.value = ''
    return
  }
  try {
    floorPlanObjectUrl.value = await fetchObjectUrl(raw)
    floorPlanUrl.value = floorPlanObjectUrl.value
  } catch (e) {
    console.error('加载楼层平面图失败:', e)
    floorPlanUrl.value = ''
  }
}

function releaseFloorPlanUrl() {
  if (floorPlanObjectUrl.value) {
    URL.revokeObjectURL(floorPlanObjectUrl.value)
    floorPlanObjectUrl.value = ''
  }
}

onBeforeUnmount(releaseFloorPlanUrl)
const planContainerRef = ref(null)
const planWrapperRef = ref(null)
const planImageRef = ref(null)

const allDevices = ref([])
const floorDevices = ref([])
const deviceSearchKeyword = ref('')
const highlightedDeviceId = ref(null)

const addDeviceDialogVisible = ref(false)
const allDeviceSearch = ref('')
const selectedDevicesToAdd = ref([])
const deviceTableRef = ref(null)

const draggingDeviceId = ref(null)
const dragOffset = ref({ x: 0, y: 0 })

const deviceTypeColors = {
  '烟感探测器': '#dc2626',
  '温感探测器': '#f59e0b',
  '手动报警按钮': '#7c3aed',
  '消火栓': '#2563eb',
  '喷淋头': '#0891b2',
  '防火门': '#16a34a',
  '灭火器': '#dc2626',
  '应急照明': '#ca8a04',
  '疏散指示': '#059669',
  '消防水泵': '#0369a1',
  '稳压泵': '#0d9488',
  '水流指示器': '#4f46e5',
  '信号蝶阀': '#65a30d',
  '排烟风机': '#c2410c',
  '防火卷帘': '#be123c'
}

const filteredDevices = computed(() => {
  if (!deviceSearchKeyword.value) return floorDevices.value
  const keyword = deviceSearchKeyword.value.toLowerCase()
  return floorDevices.value.filter(d =>
    (d.device_name || '').toLowerCase().includes(keyword) ||
    (d.device_code || '').toLowerCase().includes(keyword)
  )
})

const filteredAllDevices = computed(() => {
  const floorDeviceIds = new Set(floorDevices.value.map(d => d.id))
  let devices = allDevices.value.filter(d => !floorDeviceIds.has(d.id))
  if (allDeviceSearch.value) {
    const keyword = allDeviceSearch.value.toLowerCase()
    devices = devices.filter(d =>
      (d.device_name || '').toLowerCase().includes(keyword) ||
      (d.device_code || '').toLowerCase().includes(keyword)
    )
  }
  return devices
})

function getDeviceColor(type) {
  return deviceTypeColors[type] || '#64748b'
}

function getMarkerStyle(device) {
  const x = device.floor_x ?? device.position_x ?? 50
  const y = device.floor_y ?? device.position_y ?? 50
  return {
    left: `${x}%`,
    top: `${y}%`
  }
}

async function loadBuildings() {
  try {
    const res = await request.get('/api/buildings')
    buildings.value = res.data || []
  } catch (e) {
    console.error('加载建筑列表失败:', e)
    // 不用模拟数据兜底：假的楼栋会让人以为选错了楼层
    buildings.value = []
    ElMessage.error('建筑列表加载失败，请稍后重试')
  }
}

async function loadFloors(buildingId) {
  if (!buildingId) {
    floors.value = []
    return
  }
  try {
    const res = await listFloors(buildingId)
    floors.value = res.data || []
  } catch (e) {
    console.error('加载楼层列表失败:', e)
    floors.value = []
  }
}

async function loadFloorDetail(floorId) {
  if (!floorId) {
    selectedFloor.value = null
    setFloorPlanUrl('')
    floorDevices.value = []
    return
  }
  try {
    const res = await getFloorDetail(floorId)
    selectedFloor.value = res.data
    await setFloorPlanUrl(
      res.data?.floor_plan_image || res.data?.plan_image_url || res.data?.plan_url || ''
    )
    floorDevices.value = res.data?.devices || []
  } catch (e) {
    console.error('加载楼层详情失败:', e)
    floorDevices.value = []
  }
}

async function loadAllDevices() {
  try {
    const res = await request.get('/api/devices')
    allDevices.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('加载设备列表失败:', e)
    // 不用模拟数据兜底：假设备会被当成真实设备拖到平面图上
    allDevices.value = []
    ElMessage.error('设备列表加载失败，请稍后重试')
  }
}

function handleBuildingChange(buildingId) {
  selectedFloorId.value = null
  selectedFloor.value = null
  setFloorPlanUrl('')
  floorDevices.value = []
  loadFloors(buildingId)
}

function selectFloor(floor) {
  selectedFloorId.value = floor.id
  loadFloorDetail(floor.id)
}

function openFloorDialog(floor = null) {
  editingFloor.value = floor
  if (floor) {
    floorForm.value = {
      name: floor.floor_name || '',
      floor_code: floor.floor_number || '',
      floor_number: floor.floor_number || 1,
      description: floor.description || ''
    }
  } else {
    floorForm.value = {
      name: '',
      floor_code: '',
      floor_number: 1,
      description: ''
    }
  }
  floorDialogVisible.value = true
}

async function handleSaveFloor() {
  if (!floorForm.value.name) {
    ElMessage.warning('请输入楼层名称')
    return
  }
  floorSaving.value = true
  try {
    const data = {
      building_id: selectedBuildingId.value,
      floor_name: floorForm.value.name,
      floor_number: floorForm.value.floor_number,
      description: floorForm.value.description,
    }
    if (editingFloor.value) {
      await updateFloor(editingFloor.value.id, data)
      ElMessage.success('编辑成功')
    } else {
      await createFloor(data)
      ElMessage.success('新增成功')
    }
    floorDialogVisible.value = false
    loadFloors(selectedBuildingId.value)
  } catch (e) {
    console.error('保存楼层失败:', e)
  } finally {
    floorSaving.value = false
  }
}

async function handleDeleteFloor(floor) {
  try {
    await ElMessageBox.confirm(`确定删除楼层"${floor.floor_name}"吗？`, '确认删除', {
      type: 'warning'
    })
    await deleteFloor(floor.id)
    ElMessage.success('删除成功')
    if (selectedFloorId.value === floor.id) {
      selectedFloorId.value = null
      selectedFloor.value = null
      setFloorPlanUrl('')
      floorDevices.value = []
    }
    loadFloors(selectedBuildingId.value)
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除楼层失败:', e)
    }
  }
}

async function beforeUploadPlan(file) {
  const isImage = file.type.startsWith('image/')
  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('图片大小不能超过 10MB')
    return false
  }
  try {
    loading.value = true
    await uploadFloorPlan(selectedFloorId.value, file)
    ElMessage.success('平面图上传成功')
    await loadFloorDetail(selectedFloorId.value)
  } catch (e) {
    console.error('上传平面图失败:', e)
  } finally {
    loading.value = false
  }
  return false
}

function handleImageLoad() {
  nextTick(() => {
  })
}

function highlightDevice(device) {
  highlightedDeviceId.value = highlightedDeviceId.value === device.id ? null : device.id
}

function startDrag(event, device) {
  if (!planWrapperRef.value) return
  event.preventDefault()
  draggingDeviceId.value = device.id

  const rect = planWrapperRef.value.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * 100
  const y = ((event.clientY - rect.top) / rect.height) * 100
  dragOffset.value = {
    x: x - (device.floor_x ?? device.position_x ?? 50),
    y: y - (device.floor_y ?? device.position_y ?? 50)
  }

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(event) {
  if (!draggingDeviceId.value || !planWrapperRef.value) return
  const rect = planWrapperRef.value.getBoundingClientRect()
  let x = ((event.clientX - rect.left) / rect.width) * 100 - dragOffset.value.x
  let y = ((event.clientY - rect.top) / rect.height) * 100 - dragOffset.value.y
  x = Math.max(0, Math.min(100, x))
  y = Math.max(0, Math.min(100, y))

  const device = floorDevices.value.find(d => d.id === draggingDeviceId.value)
  if (device) {
    device.floor_x = x
    device.floor_y = y
  }
}

async function stopDrag() {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)

  if (draggingDeviceId.value) {
    const device = floorDevices.value.find(d => d.id === draggingDeviceId.value)
    if (device) {
      try {
        await updateDevicePosition(device.id, {
          floor_x: device.floor_x,
          floor_y: device.floor_y
        })
      } catch (e) {
        console.error('更新设备位置失败:', e)
      }
    }
  }
  draggingDeviceId.value = null
}

function openAddDeviceDialog() {
  allDeviceSearch.value = ''
  selectedDevicesToAdd.value = []
  addDeviceDialogVisible.value = true
}

function handleDeviceSelectionChange(selection) {
  selectedDevicesToAdd.value = selection
}

async function handleAddDevices() {
  try {
    for (const device of selectedDevicesToAdd.value) {
      await request.put(`/api/devices/${device.id}`, {
        floor_id: selectedFloorId.value,
        floor_x: 50,
        floor_y: 50
      })
    }
    ElMessage.success(`成功添加 ${selectedDevicesToAdd.value.length} 台设备`)
    addDeviceDialogVisible.value = false
    loadFloorDetail(selectedFloorId.value)
  } catch (e) {
    console.error('添加设备失败:', e)
  }
}

async function handleRemoveDevice(device) {
  try {
    await ElMessageBox.confirm(`确定将设备"${device.device_name || device.device_code}"从当前楼层移除吗？`, '确认移除', {
      type: 'warning'
    })
    await request.put(`/api/devices/${device.id}`, {
      floor_id: null,
      floor_x: 0,
      floor_y: 0
    })
    ElMessage.success('移除成功')
    loadFloorDetail(selectedFloorId.value)
  } catch (e) {
    if (e !== 'cancel') {
      console.error('移除设备失败:', e)
    }
  }
}

function refreshData() {
  loading.value = true
  Promise.all([
    loadBuildings(),
    loadAllDevices()
  ]).then(() => {
    if (selectedBuildingId.value) {
      loadFloors(selectedBuildingId.value)
    }
    if (selectedFloorId.value) {
      loadFloorDetail(selectedFloorId.value)
    }
  }).finally(() => {
    setTimeout(() => {
      loading.value = false
      ElMessage.success('数据已刷新')
    }, 500)
  })
}

onMounted(() => {
  loadBuildings()
  loadAllDevices()
})
</script>

<style scoped>
.floor-plan-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 6px;
}

.page-desc {
  color: var(--fire-muted, #667085);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.side-card {
  margin-bottom: 16px;
}

.building-card :deep(.el-select) {
  width: 100%;
}

.empty-tip {
  text-align: center;
  padding: 30px 10px;
  color: #94a3b8;
  font-size: 13px;
}

.floor-list {
  max-height: 420px;
  overflow-y: auto;
}

.floor-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 6px;
  border: 1px solid transparent;
}

.floor-item:hover {
  background: #f8fafc;
}

.floor-item.active {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-color: #bfdbfe;
}

.floor-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.floor-name {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.floor-code {
  font-size: 12px;
  color: #64748b;
}

.floor-actions {
  display: flex;
  gap: 4px;
}

.plan-card {
  min-height: 600px;
}

.plan-container {
  min-height: 500px;
  background: #f8fafc;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}

.plan-placeholder {
  min-height: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  gap: 10px;
}

.plan-placeholder p {
  margin: 0;
  font-size: 14px;
}

.plan-placeholder .sub-tip {
  font-size: 12px;
  color: #cbd5e1;
}

.plan-wrapper {
  position: relative;
  width: 100%;
  min-height: 500px;
  display: inline-block;
}

.plan-image {
  width: 100%;
  display: block;
  user-select: none;
  -webkit-user-drag: none;
}

.device-marker {
  position: absolute;
  transform: translate(-50%, -50%);
  cursor: move;
  z-index: 10;
}

.marker-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  border: 3px solid white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  transition: all 0.2s;
}

.device-marker:hover .marker-dot {
  transform: scale(1.15);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.device-marker.active .marker-dot {
  transform: scale(1.2);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.4), 0 4px 12px rgba(0, 0, 0, 0.3);
}

.device-marker.dragging .marker-dot {
  opacity: 0.8;
}

.marker-tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: #1e293b;
  color: white;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  margin-bottom: 6px;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s;
  pointer-events: none;
}

.device-marker:hover .marker-tooltip,
.device-marker.active .marker-tooltip {
  opacity: 1;
  visibility: visible;
}

.plan-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  padding-top: 14px;
  margin-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.legend-title {
  font-size: 13px;
  font-weight: 600;
  color: #475467;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.device-card {
  max-height: 680px;
  display: flex;
  flex-direction: column;
}

.device-search {
  margin-bottom: 10px;
}

.device-actions {
  margin-bottom: 12px;
}

.device-list {
  flex: 1;
  overflow-y: auto;
  max-height: 500px;
}

.device-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 6px;
  border: 1px solid transparent;
}

.device-item:hover {
  background: #f8fafc;
}

.device-item.active {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-color: #bfdbfe;
}

.device-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.device-info {
  flex: 1;
  min-width: 0;
}

.device-name {
  font-weight: 600;
  font-size: 13px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-type {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

:deep(.el-card__body) {
  display: flex;
  flex-direction: column;
}
</style>
