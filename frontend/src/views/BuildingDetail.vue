<template>
  <div class="building-detail-page">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" link @click="goBack">返回</el-button>
        <div class="title-group">
          <h2 class="page-title">{{ buildingInfo.name }}</h2>
          <div class="building-meta">
            <el-tag type="info" size="small">{{ buildingInfo.floors }}层</el-tag>
            <el-tag type="success" size="small">{{ buildingInfo.deviceCount }}台设备</el-tag>
            <span class="meta-text">{{ buildingInfo.address }}</span>
          </div>
        </div>
      </div>
      <div class="header-right">
        <el-button :icon="Upload" @click="uploadDialogVisible = true">上传CAD图纸</el-button>
        <el-button :icon="Delete" @click="openImportedDrawings">历史导入</el-button>
        <el-button :icon="Setting" @click="openBimUpload">BIM模型</el-button>
        <el-button type="primary" :icon="Plus" @click="openAddDevice">添加设备</el-button>
      </div>
    </div>

    <div class="main-content">
      <div class="left-panel">
        <div class="floor-nav">
          <div class="nav-title">
            <el-icon><OfficeBuilding /></el-icon>
            <span>楼层导航</span>
          </div>
          <div class="floor-list">
            <div
              v-for="floor in floors"
              :key="floor.id"
              class="floor-nav-item"
              :class="{ active: currentFloor === floor.id }"
              @click="selectFloor(floor.id)"
            >
              <div class="floor-icon">
                <span>{{ floor.number }}</span>
                <span class="floor-unit">F</span>
              </div>
              <div class="floor-info">
                <div class="floor-name">{{ floor.name }}</div>
                <div class="floor-stats">
                  <span class="stat-item"><i class="dot smoke"></i>{{ floor.smokeCount }}烟感</span>
                  <span class="stat-item"><i class="dot hydrant"></i>{{ floor.hydrantCount }}消火</span>
                </div>
              </div>
              <div class="floor-alarm" v-if="floor.alarmCount > 0">
                <span class="alarm-badge">{{ floor.alarmCount }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="device-panel">
          <div class="panel-title">
            <el-icon><Monitor /></el-icon>
            <span>本层设备</span>
            <el-tag type="primary" size="small" effect="dark">{{ currentFloorDevices.length }}</el-tag>
          </div>
          <div class="device-search">
            <el-input
              v-model="deviceKeyword"
              placeholder="搜索设备"
              :prefix-icon="Search"
              size="small"
            />
          </div>
          <div class="device-list">
            <div
              v-for="device in filteredDevices"
              :key="device.id"
              class="device-item"
              :class="{ active: selectedDevice?.id === device.id, alarm: device.status === 'alarm' }"
              @click="selectDevice(device)"
            >
              <div class="device-icon" :class="device.type">
                <el-icon v-if="device.type === 'smoke'"><Warning /></el-icon>
                <el-icon v-else-if="device.type === 'heat'"><ColdDrink /></el-icon>
                <el-icon v-else-if="device.type === 'hydrant'"><Watermelon /></el-icon>
                <el-icon v-else-if="device.type === 'sprinkler'"><ColdDrink /></el-icon>
                <el-icon v-else-if="device.type === 'manual'"><Tools /></el-icon>
                <el-icon v-else><Setting /></el-icon>
              </div>
              <div class="device-info">
                <div class="device-name">{{ device.name }}</div>
                <div class="device-code">{{ device.code }}</div>
              </div>
              <div class="device-status" :class="device.status">
                <span class="status-dot"></span>
                {{ statusMap[device.status] }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="center-panel">
        <div class="view-tabs">
          <div
            class="view-tab"
            :class="{ active: viewMode === '3d' }"
            @click="viewMode = '3d'"
          >
            <el-icon><Grid /></el-icon>
            3D视图
          </div>
          <div
            class="view-tab"
            :class="{ active: viewMode === 'plan' }"
            @click="viewMode = 'plan'"
          >
            <el-icon><Picture /></el-icon>
            平面视图
          </div>
          <div class="tab-divider"></div>
          <div
            class="view-tab"
            :class="{ active: navigationMode }"
            @click="toggleNavigation"
            :disabled="viewMode !== 'plan'"
          >
            <el-icon><Guide /></el-icon>
            室内导航
          </div>
          <div
            class="view-tab"
            :class="{ active: showEvacuation }"
            @click="showEvacuation ? closeEvacuation() : loadEvacuationPlan()"
          >
            <el-icon><Operation /></el-icon>
            疏散方案
          </div>
          <div class="tab-divider"></div>
          <div
            class="view-tab"
            @click="exportPlanImage"
            :disabled="viewMode !== 'plan'"
          >
            <el-icon><Download /></el-icon>
            导出图片
          </div>
        </div>

        <div class="view-container">
          <div v-show="viewMode === '3d'" class="scene-container" ref="sceneRef">
            <div class="scene-overlay">
              <div class="floor-indicator">
                <span class="floor-num">{{ currentFloorData?.number }}</span>
                <span class="floor-label">{{ currentFloorData?.name }}</span>
              </div>
            </div>
          </div>

          <div v-show="viewMode === 'plan'" class="plan-container">
            <canvas 
              ref="planCanvasRef" 
              class="plan-canvas"
              :class="{ 'nav-cursor': navigationMode }"
              @click="setNavPoint"
            ></canvas>
            <div class="plan-overlay">
              <div class="scale-bar">
                <span class="scale-value">0</span>
                <div class="scale-line"></div>
                <span class="scale-value">10m</span>
              </div>
              <div class="compass">
                <span class="north">N</span>
              </div>
            </div>
            <div v-if="navigationMode" class="nav-tip">
              <el-icon><Position /></el-icon>
              <span v-if="!navStartPoint">点击平面图选择起点</span>
              <span v-else-if="!navEndPoint">点击平面图选择终点</span>
              <span v-else>路径已生成</span>
            </div>
            <div v-if="navInfo" class="nav-info-panel">
              <div class="nav-info-title">
                <el-icon><Guide /></el-icon>
                导航信息
              </div>
              <div class="nav-info-row">
                <span class="label">距离</span>
                <span class="value">{{ navInfo.distance }} m</span>
              </div>
              <div class="nav-info-row">
                <span class="label">预计时间</span>
                <span class="value">{{ navInfo.estimatedTime }} 秒</span>
              </div>
              <div class="nav-info-row" v-if="navInfo.hazards?.length">
                <span class="label">危险区域</span>
                <span class="value warning">{{ navInfo.hazards.length }} 个</span>
              </div>
            </div>
            <div v-if="showEvacuation && evacuationData" class="evac-info-panel">
              <div class="evac-info-title">
                <el-icon><WarningFilled /></el-icon>
                疏散方案
                <el-button link type="primary" size="small" @click="closeEvacuation">关闭</el-button>
              </div>
              <div class="evac-info-row">
                <span class="label">疏散路线</span>
                <span class="value">{{ evacuationData.evacuationRoutes?.length || 0 }} 条</span>
              </div>
              <div class="evac-info-row">
                <span class="label">集合点</span>
                <span class="value">{{ evacuationData.assemblyPoints?.length || 0 }} 个</span>
              </div>
              <div class="evac-info-row danger">
                <span class="label">危险区域</span>
                <span class="value">{{ evacuationData.dangerZones?.length || 0 }} 个</span>
              </div>
            </div>
          </div>
        </div>

        <div class="plan-legend">
          <div class="legend-group">
            <span class="legend-title">设备类型：</span>
            <span v-for="(item, key) in deviceTypeLegend" :key="key" class="legend-item">
              <i class="legend-dot" :style="{ background: item.color }"></i>
              {{ item.name }}
            </span>
          </div>
          <div class="legend-group">
            <span class="legend-title">状态：</span>
            <span class="legend-item">
              <i class="legend-dot normal"></i>正常
            </span>
            <span class="legend-item">
              <i class="legend-dot warning"></i>预警
            </span>
            <span class="legend-item">
              <i class="legend-dot alarm"></i>告警
            </span>
            <span class="legend-item">
              <i class="legend-dot offline"></i>离线
            </span>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <div class="device-detail-panel" v-if="selectedDevice">
          <div class="panel-title">
            <el-icon><InfoFilled /></el-icon>
            <span>设备详情</span>
          </div>
          <div class="detail-section">
            <div class="detail-row">
              <span class="label">设备名称</span>
              <span class="value">{{ selectedDevice.name }}</span>
            </div>
            <div class="detail-row">
              <span class="label">设备编码</span>
              <span class="value">{{ selectedDevice.code }}</span>
            </div>
            <div class="detail-row">
              <span class="label">设备类型</span>
              <el-tag size="small" :type="getDeviceTagType(selectedDevice.type)">
                {{ deviceTypeLegend[selectedDevice.type]?.name }}
              </el-tag>
            </div>
            <div class="detail-row">
              <span class="label">所在位置</span>
              <span class="value">{{ buildingInfo.name }} {{ currentFloorData?.name }}</span>
            </div>
            <div class="detail-row">
              <span class="label">设备状态</span>
              <span class="value" :class="selectedDevice.status">
                <span class="status-dot"></span>
                {{ statusMap[selectedDevice.status] }}
              </span>
            </div>
          </div>
          <div class="detail-section">
            <div class="section-title">安装信息</div>
            <div class="detail-row">
              <span class="label">安装日期</span>
              <span class="value">{{ selectedDevice.installDate || '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="label">维保周期</span>
              <span class="value">{{ selectedDevice.maintenanceCycle || '每月' }}</span>
            </div>
            <div class="detail-row">
              <span class="label">下次维保</span>
              <span class="value text-warning">{{ selectedDevice.nextMaintenance || '2026-09-15' }}</span>
            </div>
          </div>
          <div class="detail-actions">
            <el-button size="small" type="primary" @click="focusDevice(selectedDevice)">定位</el-button>
            <el-button size="small" type="success" @click="handleDeviceDiagnose" :loading="deviceDiagnoseLoading">
              <el-icon><MagicStick /></el-icon>
              智能诊断
            </el-button>
            <el-button size="small" @click="openEditDevice(selectedDevice)">编辑</el-button>
            <el-button size="small" type="danger" @click="confirmDeleteDevice(selectedDevice)">删除</el-button>
          </div>
        </div>

        <div class="stat-panel">
          <div class="panel-title">
            <el-icon><DataBoard /></el-icon>
            <span>设备统计</span>
          </div>
          <div class="stat-grid">
            <div class="stat-card total">
              <div class="stat-num">{{ currentFloorDevices.length }}</div>
              <div class="stat-label">设备总数</div>
            </div>
            <div class="stat-card normal">
              <div class="stat-num">{{ getDeviceByStatus('normal') }}</div>
              <div class="stat-label">正常运行</div>
            </div>
            <div class="stat-card alarm">
              <div class="stat-num">{{ getDeviceByStatus('alarm') }}</div>
              <div class="stat-label">告警中</div>
            </div>
            <div class="stat-card offline">
              <div class="stat-num">{{ getDeviceByStatus('offline') }}</div>
              <div class="stat-label">离线</div>
            </div>
          </div>
        </div>

        <div class="recent-alarm-panel">
          <div class="panel-title">
            <el-icon><Warning /></el-icon>
            <span>近期告警</span>
          </div>
          <div class="alarm-list">
            <div v-for="alarm in recentAlarms" :key="alarm.id" class="alarm-item" :class="alarm.level">
              <div class="alarm-icon">
                <el-icon><WarningFilled /></el-icon>
              </div>
              <div class="alarm-content">
                <div class="alarm-title">{{ alarm.title }}</div>
                <div class="alarm-time">{{ alarm.time }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="uploadDialogVisible" title="上传CAD图纸" width="720px">
      <el-upload
        ref="cadUploadRef"
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        accept=".dxf"
        :show-file-list="false"
        :on-change="handleCadUpload"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将 DXF 文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            只支持 DXF：DWG 是 AutoCAD 的二进制格式，解析库读不了，请先用
            ODA File Converter 等工具转成 DXF。<br />
            解析按图层名识别构件 —— 墙体：WALL/墙；门窗：DOOR/门；
            消防设备：DEVICE/设备/消防/烟感/喷淋；房间文字：TEXT/房间/标注
          </div>
        </template>
      </el-upload>

      <div v-if="cadLoading" class="cad-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在解析CAD图纸...</span>
      </div>

      <div v-if="cadResult" class="cad-result">
        <div class="result-header">
          <span class="result-title">解析结果</span>
          <span class="result-file">{{ cadResult.fileName }}</span>
        </div>
        <div class="result-stats">
          <div class="stat-item">
            <span class="stat-number">{{ cadResult.stats?.wallCount || 0 }}</span>
            <span class="stat-label">墙体</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">{{ cadResult.stats?.doorCount || 0 }}</span>
            <span class="stat-label">门</span>
          </div>
          <div class="stat-item primary">
            <span class="stat-number">{{ cadResult.stats?.deviceCount || 0 }}</span>
            <span class="stat-label">设备</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">{{ cadResult.stats?.roomCount || 0 }}</span>
            <span class="stat-label">房间</span>
          </div>
        </div>

        <!-- 图层名是解析的唯一依据，直接摊开给用户看：认不出构件时能马上判断是命名不匹配 -->
        <div v-if="cadResult.layerCount" class="layer-summary">
          <span class="layer-count">图纸图层 {{ cadResult.layerCount }} 个</span>
          <span class="layer-names">{{ (cadResult.layers || []).join('、') }}</span>
        </div>

        <div v-if="cadResult.devices?.length" class="device-import-section">
          <div class="import-header">
            <span class="import-title">识别到的消防设备</span>
            <el-checkbox 
              :model-value="selectedCadDevices.length === cadResult.devices.length"
              :indeterminate="selectedCadDevices.length > 0 && selectedCadDevices.length < cadResult.devices.length"
              @change="selectAllCadDevices"
            >
              全选
            </el-checkbox>
            <span class="selected-count">已选 {{ selectedCadDevices.length }} 个</span>
          </div>
          <div class="device-check-list">
            <div 
              v-for="dev in cadResult.devices" 
              :key="dev.id"
              class="device-check-item"
              :class="{ checked: selectedCadDevices.includes(dev.id) }"
              @click="toggleCadDevice(dev.id)"
            >
              <el-checkbox :model-value="selectedCadDevices.includes(dev.id)" />
              <div class="dev-icon" :class="dev.type"></div>
              <span class="dev-type">{{ deviceTypeLegend[dev.type]?.name || dev.type }}</span>
              <span class="dev-pos">位置: ({{ dev.x.toFixed(1) }}, {{ dev.y.toFixed(1) }})</span>
            </div>
          </div>
        </div>

        <div v-if="cadResult.rooms?.length" class="room-section">
          <div class="section-header">
            <span class="section-title">识别到的房间 ({{ cadResult.rooms.length }})</span>
          </div>
          <div class="room-list">
            <div
              v-for="(room, idx) in cadResult.rooms"
              :key="idx"
              class="room-item"
            >
              <span class="room-name">{{ room.name || `房间${idx + 1}` }}</span>
              <span class="room-area">{{ room.area ? (room.area / 10000).toFixed(1) + '㎡' : '' }}</span>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="importCadDevices" 
          :disabled="!cadResult || selectedCadDevices.length === 0"
        >
          导入选中设备
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importedDialogVisible" title="历史导入的图纸" width="820px">
      <div class="imported-tip">
        这里列出本租户导入过的 CAD 图纸。删除会一并清掉该图纸对应的楼层及其上的设备，
        用于撤销一次错误的导入。
      </div>

      <el-table
        v-loading="importedLoading"
        :data="importedDrawings"
        size="small"
        empty-text="暂无导入记录"
        max-height="420"
      >
        <el-table-column prop="original_name" label="图纸文件" min-width="220" show-overflow-tooltip />
        <el-table-column label="关联楼层" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.floor_name">{{ row.floor_name }}</span>
            <el-tag v-else type="info" size="small">未关联楼层</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备数" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.floor_id">{{ row.device_count }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100" align="right">
          <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="导入时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button
              type="danger"
              link
              :loading="importedDeletingId === row.id"
              @click="confirmDeleteImported(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="importedDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="bimDialogVisible" title="BIM模型管理" width="560px">
      <el-upload
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        accept=".ifc,.glb,.gltf,.rvt"
        :show-file-list="false"
        :on-change="handleBimUpload"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将BIM模型文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 IFC / GLB / GLTF / RVT 格式的BIM模型文件
          </div>
        </template>
      </el-upload>

      <div v-if="bimUploading" class="cad-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在上传BIM模型...</span>
      </div>

      <div v-if="bimModelUrl" class="bim-info">
        <el-result icon="success" title="BIM模型已就绪" sub-title="可在3D视图中查看BIM模型">
          <template #extra>
            <el-button type="primary" size="medium">在3D视图中加载</el-button>
          </template>
        </el-result>
      </div>

      <div class="bim-features">
        <div class="feature-title">BIM模型支持功能</div>
        <div class="feature-list">
          <div class="feature-item">
            <el-icon color="#22c55e"><Position /></el-icon>
            <span>构件级精准定位</span>
          </div>
          <div class="feature-item">
            <el-icon color="#3b82f6"><Guide /></el-icon>
            <span>室内精准导航</span>
          </div>
          <div class="feature-item">
            <el-icon color="#f59e0b"><Warning /></el-icon>
            <span>疏散路径优化</span>
          </div>
          <div class="feature-item">
            <el-icon color="#8b5cf6"><Operation /></el-icon>
            <span>设备关联管理</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="bimDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deviceDiagnoseDialog" title="设备诊断" width="560px">
      <div v-loading="deviceDiagnoseLoading">
        <div v-if="deviceDiagnoseResult">
          <div class="diagnose-header">
            <div class="diagnose-status">
              <span class="status-label">设备状态：</span>
              <el-tag :type="deviceDiagnoseResult.device_status === '正常' ? 'success' : 'danger'" effect="dark">
                {{ deviceDiagnoseResult.device_status }}
              </el-tag>
            </div>
            <div class="diagnose-confidence">
              信息完整度 {{ (deviceDiagnoseResult.confidence * 100).toFixed(0) }}%
            </div>
          </div>

          <div v-if="deviceSignals.length" class="diagnose-signals">
            <span class="signals-label">设备台账数据：</span>
            <span v-for="item in deviceSignals" :key="item.label" class="signal-item">
              {{ item.label }} {{ item.value }}
            </span>
          </div>
          
          <div class="diagnose-section">
            <div class="diagnose-section-title">
              可能故障原因
              <el-tooltip :content="deviceDiagnoseResult.weight_note" placement="top">
                <span class="weight-hint">参考权重如何得出？</span>
              </el-tooltip>
            </div>
            <div class="fault-causes">
              <div v-for="(cause, idx) in deviceDiagnoseResult.fault_causes" :key="idx" class="fault-cause-item">
                <div class="cause-header">
                  <span class="cause-name">{{ cause.cause }}</span>
                  <el-tag size="small" type="warning" effect="plain">
                    参考权重 {{ (cause.weight * 100).toFixed(0) }}%
                  </el-tag>
                  <el-tag
                    size="small"
                    effect="plain"
                    :type="cause.basis === 'device_data' ? 'success' : 'info'"
                  >
                    {{ cause.basis === 'device_data' ? '按设备数据' : '知识库经验' }}
                  </el-tag>
                </div>
                <div class="cause-desc">{{ cause.description }}</div>
                <div class="cause-evidence">
                  <span class="evidence-label">判断依据：</span>
                  <div class="evidence-list">
                    <span v-for="(e, ei) in cause.evidence" :key="ei" class="evidence-item">{{ e }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="diagnose-section">
            <div class="diagnose-section-title">维修建议</div>
            <div class="repair-steps">
              <div v-for="(step, idx) in deviceDiagnoseResult.repair_suggestions" :key="idx" class="repair-step">
                <div class="repair-priority">{{ step.priority }}</div>
                <div class="repair-content">
                  <div class="repair-action">{{ step.action }}</div>
                  <div class="repair-detail">{{ step.detail }}</div>
                  <div class="repair-time">预计时间：{{ step.estimated_time }}</div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="diagnose-section">
            <div class="diagnose-section-title">日常维护建议</div>
            <ul class="maintenance-tips">
              <li v-for="(tip, idx) in deviceDiagnoseResult.maintenance_tips" :key="idx">{{ tip }}</li>
            </ul>
          </div>
        </div>
        <el-empty v-else description="点击智能诊断按钮开始分析" />
      </div>
      <template #footer>
        <el-button @click="deviceDiagnoseDialog = false">关闭</el-button>
        <el-button type="primary">生成维修工单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deviceDialogVisible" :title="deviceForm.id ? '编辑设备' : '新增设备'" width="500px">
      <el-form :model="deviceForm" label-width="90px" size="default">
        <el-form-item label="设备名称">
          <el-input v-model="deviceForm.name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="设备编码">
          <el-input v-model="deviceForm.code" placeholder="请输入设备编码" />
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="deviceForm.typeLabel" style="width: 100%">
            <el-option label="烟感探测器" value="烟感探测器" />
            <el-option label="温感探测器" value="温感探测器" />
            <el-option label="消火栓" value="消火栓" />
            <el-option label="喷淋头" value="喷淋头" />
            <el-option label="手报按钮" value="手报按钮" />
            <el-option label="灭火器" value="灭火器" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备状态">
          <el-select v-model="deviceForm.status" style="width: 100%">
            <el-option label="正常运行" value="normal" />
            <el-option label="预警" value="warning" />
            <el-option label="告警" value="alarm" />
            <el-option label="离线" value="offline" />
          </el-select>
        </el-form-item>
        <el-form-item label="X 坐标">
          <el-input-number v-model="deviceForm.x" :min="0" :max="100" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Y 坐标">
          <el-input-number v-model="deviceForm.y" :min="0" :max="100" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="位置描述">
          <el-input v-model="deviceForm.location" placeholder="请输入位置描述" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="deviceForm.description" type="textarea" :rows="2" placeholder="请输入备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="deviceSaving">
          {{ deviceForm.id ? '保存修改' : '创建设备' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import request from '../api'
import { ArrowLeft, Upload, Plus, OfficeBuilding, Monitor, Search, Warning, ColdDrink, Watermelon, Tools, Setting, Grid, Picture, InfoFilled, DataBoard, WarningFilled, UploadFilled, Location, Guide, Operation, Position, Loading, Download, MagicStick, Delete } from '@element-plus/icons-vue'
import { diagnoseDevice } from '@/api/intelligence'

const route = useRoute()
const router = useRouter()

const sceneRef = ref(null)
const planCanvasRef = ref(null)
let scene = null
let camera = null
let renderer = null
let controls = null
let animationId = null
let buildingMeshes = []
let currentFloorMesh = null
let deviceMarkers = []

const viewMode = ref('3d')
const uploadDialogVisible = ref(false)
const deviceKeyword = ref('')
const selectedDevice = ref(null)
const loading = ref(false)
const cadLoading = ref(false)

// 历史导入的图纸（用于撤销错误的导入）
const importedDialogVisible = ref(false)
const importedLoading = ref(false)
const importedDrawings = ref([])
const importedDeletingId = ref(null)

const deviceDiagnoseDialog = ref(false)
const deviceDiagnoseLoading = ref(false)
const deviceDiagnoseResult = ref(null)

// 诊断权重的真实依据：把设备台账里的信号摊平成几行展示
const deviceSignals = computed(() => {
  const signals = deviceDiagnoseResult.value?.device_signals || {}
  const rows = []
  if (signals.ageYears != null) rows.push({ label: '已投用', value: `${signals.ageYears} 年` })
  if (signals.daysSinceMaintenance != null) {
    rows.push({ label: '距上次维保', value: `${signals.daysSinceMaintenance} 天` })
  }
  if (signals.maintenanceOverdue) rows.push({ label: '维保计划', value: '已超期' })
  if (signals.daysSinceSeen != null) rows.push({ label: '距上次上报', value: `${signals.daysSinceSeen} 天` })
  return rows
})

const navigationMode = ref(false)
const navStartPoint = ref(null)
const navEndPoint = ref(null)
const navPath = ref(null)
const navInfo = ref(null)
const showEvacuation = ref(false)
const evacuationData = ref(null)

const cadResult = ref(null)
const selectedCadDevices = ref([])
const cadUploadRef = ref(null)

const buildingInfo = ref({
  id: 1,
  name: '综合办公楼A座',
  address: '科技园区1号楼',
  floors: 8,
  deviceCount: 186,
})

const floors = ref([
  { id: 8, number: 8, name: '8层', smokeCount: 12, hydrantCount: 4, alarmCount: 0 },
  { id: 7, number: 7, name: '7层', smokeCount: 12, hydrantCount: 4, alarmCount: 0 },
  { id: 6, number: 6, name: '6层', smokeCount: 12, hydrantCount: 4, alarmCount: 1 },
  { id: 5, number: 5, name: '5层', smokeCount: 12, hydrantCount: 4, alarmCount: 0 },
  { id: 4, number: 4, name: '4层', smokeCount: 12, hydrantCount: 4, alarmCount: 0 },
  { id: 3, number: 3, name: '3层', smokeCount: 12, hydrantCount: 4, alarmCount: 0 },
  { id: 2, number: 2, name: '2层', smokeCount: 12, hydrantCount: 4, alarmCount: 2 },
  { id: 1, number: 1, name: '1层大厅', smokeCount: 15, hydrantCount: 6, alarmCount: 0 },
  { id: 0, number: 'B1', name: '地下1层', smokeCount: 8, hydrantCount: 8, alarmCount: 0 },
])

const currentFloor = ref(1)

const currentFloorData = computed(() => {
  return floors.value.find(f => f.id === currentFloor.value)
})

const statusMap = {
  normal: '正常',
  warning: '预警',
  alarm: '告警',
  offline: '离线',
}

const deviceTypeLegend = {
  smoke: { name: '烟感探测器', color: '#ef4444' },
  heat: { name: '温感探测器', color: '#f97316' },
  hydrant: { name: '消火栓', color: '#3b82f6' },
  sprinkler: { name: '喷淋头', color: '#06b6d4' },
  manual: { name: '手报按钮', color: '#f59e0b' },
  extinguisher: { name: '灭火器', color: '#dc2626' },
}

const allDevices = ref([
  { id: 1, code: 'YG-101', name: '1层大厅烟感1号', type: 'smoke', status: 'normal', x: 20, y: 25, installDate: '2025-03-15', maintenanceCycle: '每月', nextMaintenance: '2026-09-20' },
  { id: 2, code: 'YG-102', name: '1层大厅烟感2号', type: 'smoke', status: 'normal', x: 55, y: 30, installDate: '2025-03-15', maintenanceCycle: '每月', nextMaintenance: '2026-09-20' },
  { id: 3, code: 'YG-103', name: '1层走廊烟感', type: 'smoke', status: 'alarm', x: 75, y: 50, installDate: '2025-03-16', maintenanceCycle: '每月', nextMaintenance: '2026-09-21' },
  { id: 4, code: 'YG-104', name: '1层机房烟感', type: 'smoke', status: 'warning', x: 85, y: 75, installDate: '2025-03-16', maintenanceCycle: '每月', nextMaintenance: '2026-09-21' },
  { id: 5, code: 'WG-101', name: '1层温感1号', type: 'heat', status: 'normal', x: 30, y: 60, installDate: '2025-03-20', maintenanceCycle: '每月', nextMaintenance: '2026-09-25' },
  { id: 6, code: 'WG-102', name: '1层温感2号', type: 'heat', status: 'normal', x: 65, y: 70, installDate: '2025-03-20', maintenanceCycle: '每月', nextMaintenance: '2026-09-25' },
  { id: 7, code: 'XHS-101', name: '1层消火栓1号', type: 'hydrant', status: 'normal', x: 10, y: 45, installDate: '2025-01-10', maintenanceCycle: '每季度', nextMaintenance: '2026-12-10' },
  { id: 8, code: 'XHS-102', name: '1层消火栓2号', type: 'hydrant', status: 'normal', x: 90, y: 45, installDate: '2025-01-10', maintenanceCycle: '每季度', nextMaintenance: '2026-12-10' },
  { id: 9, code: 'PL-101', name: '1层喷淋-01', type: 'sprinkler', status: 'normal', x: 25, y: 35, installDate: '2025-02-01', maintenanceCycle: '每半年', nextMaintenance: '2027-02-01' },
  { id: 10, code: 'PL-102', name: '1层喷淋-02', type: 'sprinkler', status: 'normal', x: 45, y: 45, installDate: '2025-02-01', maintenanceCycle: '每半年', nextMaintenance: '2027-02-01' },
  { id: 11, code: 'PL-103', name: '1层喷淋-03', type: 'sprinkler', status: 'offline', x: 65, y: 35, installDate: '2025-02-01', maintenanceCycle: '每半年', nextMaintenance: '2027-02-01' },
  { id: 12, code: 'SB-101', name: '1层手报按钮', type: 'manual', status: 'normal', x: 15, y: 20, installDate: '2025-03-01', maintenanceCycle: '每月', nextMaintenance: '2026-10-01' },
  { id: 13, code: 'MHQ-101', name: '1层灭火器1号', type: 'extinguisher', status: 'normal', x: 20, y: 80, installDate: '2025-04-01', maintenanceCycle: '每月', nextMaintenance: '2026-10-01' },
  { id: 14, code: 'MHQ-102', name: '1层灭火器2号', type: 'extinguisher', status: 'normal', x: 80, y: 80, installDate: '2025-04-01', maintenanceCycle: '每月', nextMaintenance: '2026-10-01' },
  { id: 15, code: 'YG-105', name: '1层会议室烟感', type: 'smoke', status: 'normal', x: 40, y: 20, installDate: '2025-03-18', maintenanceCycle: '每月', nextMaintenance: '2026-09-23' },
  { id: 16, code: 'YG-106', name: '1层办公区烟感', type: 'smoke', status: 'normal', x: 60, y: 55, installDate: '2025-03-18', maintenanceCycle: '每月', nextMaintenance: '2026-09-23' },
])

const currentFloorDevices = computed(() => {
  return allDevices.value
})

const filteredDevices = computed(() => {
  if (!deviceKeyword.value) return currentFloorDevices.value
  const kw = deviceKeyword.value.toLowerCase()
  return currentFloorDevices.value.filter(d =>
    d.name.toLowerCase().includes(kw) ||
    d.code.toLowerCase().includes(kw)
  )
})

const recentAlarms = ref([
  { id: 1, title: '1层走廊烟感报警', level: 'critical', time: '10分钟前' },
  { id: 2, title: '1层机房烟感预警', level: 'warning', time: '25分钟前' },
  { id: 3, title: '1层喷淋03离线', level: 'info', time: '1小时前' },
])

function goBack() {
  router.back()
}

async function selectFloor(floorId) {
  currentFloor.value = floorId
  selectedDevice.value = null
  navigationMode.value = false
  navPath.value = null
  navStartPoint.value = null
  navEndPoint.value = null
  showEvacuation.value = false
  cadResult.value = null
  await loadFloorDevices(floorId)
  updateFloorHighlight()
  if (scene) {
    addDeviceMarkers()
    clearNavPath3D()
  }
  drawPlan()
}

function selectDevice(device) {
  selectedDevice.value = device
  loadDeviceDetail(device.id)
  focusDevice(device)
}

function getDeviceByStatus(status) {
  return currentFloorDevices.value.filter(d => d.status === status).length
}

function getDeviceTagType(type) {
  const typeMap = {
    smoke: 'danger',
    heat: 'warning',
    hydrant: 'primary',
    sprinkler: 'info',
    manual: 'success',
    extinguisher: 'danger',
  }
  return typeMap[type] || 'info'
}

async function loadBuildingData() {
  const buildingId = route.params.id
  if (!buildingId) return
  
  try {
    loading.value = true
    const res = await request.get(`/api/buildings/${buildingId}/detail`)
    const data = res.data
    
    if (data.building) {
      buildingInfo.value = {
        id: data.building.id,
        name: data.building.name,
        address: data.building.address,
        floors: data.building.floors,
        deviceCount: data.building.deviceCount,
      }
    }
    
    if (data.floors && data.floors.length) {
      floors.value = data.floors.map(f => ({
        id: f.id,
        number: f.number,
        name: f.name,
        smokeCount: f.smokeCount || 0,
        hydrantCount: f.hydrantCount || 0,
        alarmCount: f.alarmCount || 0,
        status: f.status || 'normal',
        floorPlanImage: f.floorPlanImage || '',
      }))
      if (floors.value.length > 0) {
        currentFloor.value = floors.value[0].id
      }
    }
    
    if (data.stats) {
      deviceStats.value = data.stats
    }
    
    if (data.recentAlarms) {
      recentAlarms.value = data.recentAlarms
    }
    
    if (floors.value.length > 0) {
      await loadFloorDevices(floors.value[0].id)
    }
    
    if (scene && buildingGroup) {
      buildBuilding()
      addDeviceMarkers()
    }
  } catch (e) {
    console.warn('加载建筑详情失败，使用模拟数据', e)
  } finally {
    loading.value = false
  }
}

async function loadFloorDevices(floorId) {
  try {
    const res = await request.get(`/api/floors/${floorId}/devices`, {
      params: { keyword: deviceKeyword.value }
    })
    const data = res.data
    
    if (data.devices) {
      allDevices.value = data.devices.map(d => ({
        id: d.id,
        code: d.code,
        name: d.name,
        type: d.type,
        typeLabel: d.typeLabel,
        status: d.status,
        x: d.x,
        y: d.y,
        installDate: d.installDate,
        nextMaintenance: d.nextMaintenance,
        location: d.location,
        maintenanceCycle: '每月',
      }))
    }
  } catch (e) {
    console.warn('加载楼层设备失败', e)
  }
}

async function loadDeviceDetail(deviceId) {
  try {
    const res = await request.get(`/api/devices/${deviceId}/detail`)
    const data = res.data
    if (data.device) {
      selectedDevice.value = {
        ...selectedDevice.value,
        ...data.device,
        installDate: data.device.installDate,
        lastMaintenance: data.device.lastMaintenance,
        nextMaintenance: data.device.nextMaintenance,
      }
      if (data.recentAlarms) {
        deviceAlarms.value = data.recentAlarms
      }
    }
  } catch (e) {
    console.warn('加载设备详情失败', e)
  }
}

async function handleDeviceDiagnose() {
  if (!selectedDevice.value) return
  
  deviceDiagnoseResult.value = null
  deviceDiagnoseDialog.value = true
  deviceDiagnoseLoading.value = true
  
  try {
    const res = await diagnoseDevice({
      // 接口的 device_id 是字符串（也允许传设备编码），传数字会被 422 拒掉
      device_id: selectedDevice.value.id != null ? String(selectedDevice.value.id) : '',
      device_name: selectedDevice.value.name,
      device_type: selectedDevice.value.type,
      status: statusMap[selectedDevice.value.status] || '正常',
      building_name: buildingInfo.value?.name || '',
    })
    // 接口外层是 { ok, data }：以前只取到信封，弹窗里状态/原因全是空
    deviceDiagnoseResult.value = res.data?.data || null
  } catch (e) {
    ElMessage.error('设备诊断失败，请稍后重试')
  } finally {
    deviceDiagnoseLoading.value = false
  }
}

const deviceStats = ref({
  total: 0,
  normal: 0,
  alarm: 0,
  offline: 0,
})

const deviceAlarms = ref([])

async function handleCadUpload(uploadFile) {
  // el-upload 的 on-change 给的是 UploadFile 对象（原生文件在 .raw），
  // 不是 DOM 事件——以前按 event.target.files 取，选完文件就抛错、毫无反应。
  const file = uploadFile?.raw
  if (!file) return

  const name = file.name.toLowerCase()
  if (name.endsWith('.dwg')) {
    ElMessage.error('DWG 需要先转成 DXF 再上传（可用 ODA File Converter 批量转换）')
    cadUploadRef.value?.clearFiles()
    return
  }
  if (!name.endsWith('.dxf')) {
    ElMessage.error('请上传 DXF 格式的文件')
    cadUploadRef.value?.clearFiles()
    return
  }

  try {
    cadLoading.value = true
    const formData = new FormData()
    formData.append('file', file)

    const res = await request.post(`/api/cad/parse/${currentFloor.value}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // 失败原因要透传后端 detail，所以不让拦截器再弹一次
      silentError: true,
    })

    cadResult.value = res.data
    selectedCadDevices.value = res.data.devices?.map(d => d.id) || []
    ElMessage.success('CAD 图纸解析成功')
    drawPlan()
  } catch (e) {
    const data = e?.response?.data
    // 后端会把原因写清楚：DWG 需转换 / 未识别到构件 / DXF 解析报错
    ElMessage.error(data?.detail || data?.message || 'CAD 图纸解析失败')
  } finally {
    cadLoading.value = false
    // 清掉文件列表，否则 :limit="1" 会拦住下一次上传
    cadUploadRef.value?.clearFiles()
  }
}

async function importCadDevices() {
  if (!cadResult.value?.devices) return
  
  const devicesToImport = cadResult.value.devices.filter(d => 
    selectedCadDevices.value.includes(d.id)
  )
  
  if (devicesToImport.length === 0) {
    ElMessage.warning('请选择要导入的设备')
    return
  }
  
  try {
    await request.post(`/api/cad/import-devices/${currentFloor.value}`, devicesToImport)
    ElMessage.success(`成功导入 ${devicesToImport.length} 个设备`)
    uploadDialogVisible.value = false
    await loadFloorDevices(currentFloor.value)
    drawPlan()
  } catch (e) {
    console.error('设备导入失败', e)
    ElMessage.error('设备导入失败')
  }
}

function toggleCadDevice(id) {
  const idx = selectedCadDevices.value.indexOf(id)
  if (idx > -1) {
    selectedCadDevices.value.splice(idx, 1)
  } else {
    selectedCadDevices.value.push(id)
  }
}

function selectAllCadDevices() {
  if (cadResult.value?.devices) {
    if (selectedCadDevices.value.length === cadResult.value.devices.length) {
      selectedCadDevices.value = []
    } else {
      selectedCadDevices.value = cadResult.value.devices.map(d => d.id)
    }
  }
}

function toggleNavigation() {
  navigationMode.value = !navigationMode.value
  navStartPoint.value = null
  navEndPoint.value = null
  navPath.value = null
  navInfo.value = null
  if (!navigationMode.value) {
    drawPlan()
  }
}

function setNavPoint(e) {
  if (!navigationMode.value) return
  
  const canvas = planCanvasRef.value
  if (!canvas) return
  
  const rect = canvas.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  
  if (!navStartPoint.value) {
    navStartPoint.value = { x, y }
    ElMessage.info('请选择终点位置')
  } else if (!navEndPoint.value) {
    navEndPoint.value = { x, y }
    calculatePath()
  }
}

async function calculatePath() {
  try {
    const buildingId = route.params.id
    const res = await request.get(`/api/buildings/${buildingId}/navigation`, {
      params: {
        start_floor: currentFloorData.value?.number || 1,
        start_x: navStartPoint.value.x,
        start_y: navStartPoint.value.y,
        end_floor: currentFloorData.value?.number || 1,
        end_x: navEndPoint.value.x,
        end_y: navEndPoint.value.y,
      }
    })
    navPath.value = res.data.path
    navInfo.value = {
      distance: res.data.distance,
      estimatedTime: res.data.estimatedTime,
      exits: res.data.exits,
      hazards: res.data.hazards,
    }
    drawPlan()
    drawNavPath3D()
  } catch (e) {
    console.error('路径计算失败', e)
  }
}

let navPathMesh = null
let navPathPoints = null

function clearNavPath3D() {
  if (navPathMesh && scene) {
    scene.remove(navPathMesh)
    navPathMesh = null
  }
  if (navStartMarker3D && scene) {
    scene.remove(navStartMarker3D)
    navStartMarker3D = null
  }
  if (navEndMarker3D && scene) {
    scene.remove(navEndMarker3D)
    navEndMarker3D = null
  }
}

let navStartMarker3D = null
let navEndMarker3D = null

function drawNavPath3D() {
  if (!scene || !buildingGroup || !navPath.value?.waypoints) return
  clearNavPath3D()

  const floorHeight = 3.8
  const buildingW = 28
  const buildingD = 20
  const pathGroup = new THREE.Group()

  const waypoints = navPath.value.waypoints
  const points3D = []

  waypoints.forEach((wp, i) => {
    const floorIdx = (wp.floor || 1) - 1
    const x = (wp.x / 100 - 0.5) * buildingW
    const z = (wp.y / 100 - 0.5) * buildingD
    const y = floorIdx * floorHeight + 1.5
    points3D.push(new THREE.Vector3(x, y, z))

    if (wp.type === 'start') {
      const marker = createNavMarker3D(0x22c55e, '起')
      marker.position.set(x, y + 1, z)
      pathGroup.add(marker)
      navStartMarker3D = marker
    } else if (wp.type === 'end') {
      const marker = createNavMarker3D(0xef4444, '终')
      marker.position.set(x, y + 1, z)
      pathGroup.add(marker)
      navEndMarker3D = marker
    } else if (wp.type === 'stair') {
      const marker = createNavMarker3D(0xf59e0b, '梯')
      marker.position.set(x, y + 1, z)
      pathGroup.add(marker)
    }
  })

  for (let i = 0; i < points3D.length - 1; i++) {
    const p1 = points3D[i]
    const p2 = points3D[i + 1]

    const curve = new THREE.LineCurve3(p1, p2)
    const tubeGeom = new THREE.TubeGeometry(curve, 20, 0.12, 8, false)
    const tubeMat = new THREE.MeshBasicMaterial({
      color: 0x22c55e,
      transparent: true,
      opacity: 0.7,
    })
    const tube = new THREE.Mesh(tubeGeom, tubeMat)
    tube.userData.isNavPath = true
    pathGroup.add(tube)

    const glowGeom = new THREE.TubeGeometry(curve, 20, 0.25, 8, false)
    const glowMat = new THREE.MeshBasicMaterial({
      color: 0x22c55e,
      transparent: true,
      opacity: 0.15,
    })
    const glow = new THREE.Mesh(glowGeom, glowMat)
    pathGroup.add(glow)
  }

  navPathMesh = pathGroup
  buildingGroup.add(pathGroup)
}

function createNavMarker3D(color, label) {
  const group = new THREE.Group()

  const coneGeom = new THREE.ConeGeometry(0.5, 1.2, 8)
  const coneMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 })
  const cone = new THREE.Mesh(coneGeom, coneMat)
  cone.position.y = 0.6
  group.add(cone)

  const ringGeom = new THREE.RingGeometry(0.4, 0.7, 32)
  const ringMat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.5,
    side: THREE.DoubleSide,
  })
  const ring = new THREE.Mesh(ringGeom, ringMat)
  ring.rotation.x = -Math.PI / 2
  group.add(ring)

  return group
}

let bimDialogVisible = ref(false)
let bimUploading = ref(false)
let bimModelUrl = ref('')

// ---------------- 历史导入图纸 ----------------

function formatFileSize(bytes) {
  const size = Number(bytes) || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function formatDateTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadImportedDrawings() {
  const buildingId = route.params.id
  importedLoading.value = true
  try {
    const res = await request.get(`/api/buildings/${buildingId}/imported-drawings`)
    importedDrawings.value = res.data?.items || []
  } catch (e) {
    ElMessage.error('加载导入记录失败')
  } finally {
    importedLoading.value = false
  }
}

function openImportedDrawings() {
  importedDialogVisible.value = true
  loadImportedDrawings()
}

async function confirmDeleteImported(row) {
  const scope = row.floor_id
    ? `楼层「${row.floor_name}」及其上的 ${row.device_count} 个设备`
    : '该图纸的上传记录（未关联楼层）'
  try {
    await ElMessageBox.confirm(
      `确定删除图纸「${row.original_name}」吗？将一并删除${scope}，删除后不可恢复。`,
      '删除导入图纸',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) {
    return
  }

  const buildingId = route.params.id
  importedDeletingId.value = row.id
  try {
    await request.delete(`/api/buildings/${buildingId}/imported-drawings/${row.id}`)
    ElMessage.success('已删除')
    await loadImportedDrawings()
    await loadBuildingData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  } finally {
    importedDeletingId.value = null
  }
}

function openBimUpload() {
  bimDialogVisible.value = true
}

async function handleBimUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const ext = file.name.split('.').pop().toLowerCase()
  if (!['ifc', 'glb', 'gltf', 'rvt'].includes(ext)) {
    ElMessage.error('请上传 IFC/GLB/GLTF/RVT 格式的BIM模型')
    return
  }

  try {
    bimUploading.value = true
    const formData = new FormData()
    formData.append('file', file)

    const buildingId = route.params.id
    const res = await request.post(`/api/bim/upload/${buildingId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    bimModelUrl.value = res.data.modelUrl
    ElMessage.success('BIM模型上传成功')
    bimDialogVisible.value = false
    ElMessage.info('BIM模型加载功能开发中，敬请期待')
  } catch (e) {
    console.error('BIM上传失败', e)
    ElMessage.error('BIM模型上传失败')
  } finally {
    bimUploading.value = false
  }
}

const deviceDialogVisible = ref(false)
const deviceSaving = ref(false)
const deviceForm = ref({
  id: null,
  name: '',
  code: '',
  typeLabel: '烟感探测器',
  status: 'normal',
  x: 50,
  y: 50,
  location: '',
  description: '',
})

function openAddDevice() {
  deviceForm.value = {
    id: null,
    name: '',
    code: '',
    typeLabel: '烟感探测器',
    status: 'normal',
    x: 50,
    y: 50,
    location: '',
    description: '',
  }
  deviceDialogVisible.value = true
}

function openEditDevice(device) {
  deviceForm.value = {
    id: device.id,
    name: device.name,
    code: device.code,
    typeLabel: device.typeLabel || deviceTypeLegend[device.type]?.name || '烟感探测器',
    status: device.status,
    x: device.x,
    y: device.y,
    location: device.location || '',
    description: device.description || '',
  }
  deviceDialogVisible.value = true
}

async function saveDevice() {
  if (!deviceForm.value.name) {
    ElMessage.warning('请输入设备名称')
    return
  }

  try {
    deviceSaving.value = true
    const payload = {
      ...deviceForm.value,
      buildingId: route.params.id,
      floorId: currentFloor.value,
    }

    if (deviceForm.value.id) {
      await request.put(`/api/devices/${deviceForm.value.id}`, payload)
      ElMessage.success('设备更新成功')
    } else {
      await request.post('/api/devices', payload)
      ElMessage.success('设备创建成功')
    }

    deviceDialogVisible.value = false
    await loadFloorDevices(currentFloor.value)
    if (scene) {
      addDeviceMarkers()
    }
    drawPlan()
  } catch (e) {
    console.error('保存设备失败', e)
    ElMessage.error('保存设备失败')
  } finally {
    deviceSaving.value = false
  }
}

async function confirmDeleteDevice(device) {
  try {
    await ElMessageBox.confirm(
      `确定要删除设备"${device.name}"吗？`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await request.delete(`/api/devices/${device.id}`)
    ElMessage.success('设备删除成功')
    
    if (selectedDevice.value?.id === device.id) {
      selectedDevice.value = null
    }
    await loadFloorDevices(currentFloor.value)
    if (scene) {
      addDeviceMarkers()
    }
    drawPlan()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除设备失败', e)
      ElMessage.error('删除设备失败')
    }
  }
}

const focusHighlightTimer = ref(null)
const focusedDeviceId = ref(null)

function focusDevice(device) {
  focusedDeviceId.value = device.id
  
  if (viewMode.value === '3d') {
    const floorIndex = floors.value.findIndex(f => f.id === currentFloor.value)
    if (floorIndex < 0) return
    
    const floorHeight = 3.8
    const x = (device.x / 100 - 0.5) * 24
    const z = (device.y / 100 - 0.5) * 16
    const y = floorIndex * floorHeight + 1.8

    if (camera && controls) {
      const targetPos = new THREE.Vector3(x, y, z)
      const offset = new THREE.Vector3(8, 6, 8)
      const startPos = camera.position.clone()
      const startTarget = controls.target.clone()
      const endPos = offset.clone().add(targetPos)
      
      let progress = 0
      const duration = 800
      const startTime = Date.now()
      
      function animateCamera() {
        progress = Math.min((Date.now() - startTime) / duration, 1)
        const eased = 1 - Math.pow(1 - progress, 3)
        
        camera.position.lerpVectors(startPos, endPos, eased)
        controls.target.lerpVectors(startTarget, targetPos, eased)
        controls.update()
        
        if (progress < 1) {
          requestAnimationFrame(animateCamera)
        }
      }
      animateCamera()
    }
    
    updateDeviceMarkerHighlight(device.id)
  } else {
    drawPlan()
  }
  
  if (focusHighlightTimer.value) {
    clearTimeout(focusHighlightTimer.value)
  }
  focusHighlightTimer.value = setTimeout(() => {
    focusedDeviceId.value = null
    if (viewMode.value === '3d') {
      updateDeviceMarkerHighlight(null)
    }
  }, 3000)
  
  ElMessage.success(`已定位到设备：${device.name}`)
}

function updateDeviceMarkerHighlight(deviceId) {
  deviceMarkers.forEach(marker => {
    const isFocused = marker.userData.device?.id === deviceId
    if (isFocused) {
      marker.scale.setScalar(1.5)
      if (marker.children[0]) {
        marker.children[0].material.opacity = 0.8
      }
    } else {
      marker.scale.setScalar(1)
      if (marker.children[0]) {
        marker.children[0].material.opacity = 0.5
      }
    }
  })
}

function exportPlanImage() {
  if (!planCanvasRef.value) {
    ElMessage.warning('平面图未就绪')
    return
  }
  
  try {
    const canvas = planCanvasRef.value
    
    const exportCanvas = document.createElement('canvas')
    const scale = 2
    exportCanvas.width = canvas.width * scale
    exportCanvas.height = canvas.height * scale
    const ctx = exportCanvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.drawImage(canvas, 0, 0)
    
    const floorName = currentFloorData.value?.name || '平面图'
    const buildingName = buildingInfo.value?.name || '建筑'
    
    const padding = 60
    const finalCanvas = document.createElement('canvas')
    finalCanvas.width = exportCanvas.width + padding * 2
    finalCanvas.height = exportCanvas.height + padding * 2 + 80
    const fctx = finalCanvas.getContext('2d')
    
    fctx.fillStyle = '#0a1628'
    fctx.fillRect(0, 0, finalCanvas.width, finalCanvas.height)
    
    fctx.fillStyle = '#ffffff'
    fctx.font = 'bold 28px Microsoft YaHei'
    fctx.textAlign = 'center'
    fctx.fillText(`${buildingName} - ${floorName}平面图`, finalCanvas.width / 2, 45)
    
    fctx.fillStyle = '#64748b'
    fctx.font = '14px Microsoft YaHei'
    const now = new Date()
    const timeStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    fctx.fillText(`导出时间：${timeStr}`, finalCanvas.width / 2, 75)
    
    fctx.drawImage(exportCanvas, padding, padding + 60)
    
    fctx.strokeStyle = '#1e40af'
    fctx.lineWidth = 3
    fctx.strokeRect(padding - 5, padding + 55, exportCanvas.width + 10, exportCanvas.height + 10)
    
    const legendY = finalCanvas.height - 35
    fctx.font = '14px Microsoft YaHei'
    fctx.textAlign = 'left'
    
    const legends = [
      { color: '#22c55e', label: '正常' },
      { color: '#f59e0b', label: '预警' },
      { color: '#ef4444', label: '告警' },
      { color: '#64748b', label: '离线' },
    ]
    
    let lx = padding
    fctx.fillStyle = '#94a3b8'
    fctx.fillText('设备状态：', lx, legendY)
    lx += 80
    
    legends.forEach(l => {
      fctx.beginPath()
      fctx.arc(lx + 8, legendY - 5, 6, 0, Math.PI * 2)
      fctx.fillStyle = l.color
      fctx.fill()
      fctx.fillStyle = '#e2e8f0'
      fctx.fillText(l.label, lx + 20, legendY)
      lx += 70
    })
    
    const link = document.createElement('a')
    link.download = `${buildingName}_${floorName}_平面图_${Date.now()}.png`
    link.href = finalCanvas.toDataURL('image/png', 0.95)
    link.click()
    
    ElMessage.success('平面图导出成功')
  } catch (e) {
    console.error('导出图片失败', e)
    ElMessage.error('导出图片失败')
  }
}

async function loadEvacuationPlan() {
  try {
    const buildingId = route.params.id
    const res = await request.get(`/api/buildings/${buildingId}/evacuation-plan`, {
      params: { floor_id: currentFloor.value }
    })
    evacuationData.value = res.data
    showEvacuation.value = true
    drawPlan()
  } catch (e) {
    console.error('加载疏散方案失败', e)
  }
}

function closeEvacuation() {
  showEvacuation.value = false
  evacuationData.value = null
  drawPlan()
}

function handleUpload() {
  ElMessage.info('请选择CAD图纸文件上传解析')
}

function init3DScene() {
  if (!sceneRef.value) return
  const width = sceneRef.value.clientWidth
  const height = sceneRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x050d1a)
  scene.fog = new THREE.Fog(0x050d1a, 50, 200)

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000)
  camera.position.set(35, 40, 45)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  sceneRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.minDistance = 15
  controls.maxDistance = 150
  controls.maxPolarAngle = Math.PI / 2.1
  controls.target.set(0, 15, 0)

  const ambientLight = new THREE.AmbientLight(0x3366aa, 0.5)
  scene.add(ambientLight)

  const hemiLight = new THREE.HemisphereLight(0x00aaff, 0x003366, 0.4)
  scene.add(hemiLight)

  const directionalLight = new THREE.DirectionalLight(0xaaccff, 0.8)
  directionalLight.position.set(40, 60, 40)
  directionalLight.castShadow = true
  directionalLight.shadow.mapSize.set(2048, 2048)
  directionalLight.shadow.camera.left = -40
  directionalLight.shadow.camera.right = 40
  directionalLight.shadow.camera.top = 40
  directionalLight.shadow.camera.bottom = -40
  scene.add(directionalLight)

  const pointLight1 = new THREE.PointLight(0x00aaff, 0.6, 80)
  pointLight1.position.set(-20, 25, -20)
  scene.add(pointLight1)

  const pointLight2 = new THREE.PointLight(0x00ffaa, 0.4, 60)
  pointLight2.position.set(20, 30, 20)
  scene.add(pointLight2)

  buildGround()
  buildBuilding()
  addDeviceMarkers()
  animate()
}

function buildGround() {
  if (!scene) return

  const groundGeom = new THREE.PlaneGeometry(120, 120, 60, 60)
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x0a1628,
    roughness: 0.9,
    metalness: 0.1,
  })
  const ground = new THREE.Mesh(groundGeom, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  const gridHelper = new THREE.GridHelper(80, 40, 0x004477, 0x002244)
  gridHelper.position.y = 0.02
  scene.add(gridHelper)

  const roadGeom = new THREE.PlaneGeometry(8, 120)
  const roadMat = new THREE.MeshStandardMaterial({ color: 0x1a2a3a, roughness: 0.8 })
  const road1 = new THREE.Mesh(roadGeom, roadMat)
  road1.rotation.x = -Math.PI / 2
  road1.position.set(-35, 0.05, 0)
  scene.add(road1)

  const road2 = new THREE.Mesh(roadGeom, roadMat)
  road2.rotation.x = -Math.PI / 2
  road2.rotation.z = Math.PI / 2
  road2.position.set(0, 0.05, -35)
  scene.add(road2)

  for (let i = 0; i < 8; i++) {
    const treeX = -45 + Math.random() * 10
    const treeZ = -50 + i * 12
    addTree(treeX, treeZ)
  }
  for (let i = 0; i < 6; i++) {
    const treeX = 40 + Math.random() * 10
    const treeZ = -45 + i * 15
    addTree(treeX, treeZ)
  }
}

function addTree(x, z) {
  if (!scene) return
  const trunkGeom = new THREE.CylinderGeometry(0.2, 0.3, 2, 6)
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x3d2817, roughness: 0.9 })
  const trunk = new THREE.Mesh(trunkGeom, trunkMat)
  trunk.position.set(x, 1, z)
  trunk.castShadow = true
  scene.add(trunk)

  const leavesGeom = new THREE.SphereGeometry(1.2, 8, 8)
  const leavesMat = new THREE.MeshStandardMaterial({ color: 0x1d4a2d, roughness: 0.8 })
  const leaves = new THREE.Mesh(leavesGeom, leavesMat)
  leaves.position.set(x, 2.8, z)
  leaves.castShadow = true
  scene.add(leaves)
}

let buildingGroup = null

function buildBuilding() {
  if (!scene) return
  if (buildingGroup) {
    scene.remove(buildingGroup)
    buildingGroup = null
  }
  buildingMeshes = []
  currentFloorMesh = null

  buildingGroup = new THREE.Group()

  const buildingW = 28
  const buildingD = 20
  const floorHeight = 3.8

  const floorCount = floors.value.length > 0 ? floors.value.length : 8

  for (let i = 0; i < floorCount; i++) {
    const floorData = floors.value[i] || { number: i + 1, name: `${i + 1}层` }
    const floorY = i * floorHeight
    const isCurrent = floorData.id === currentFloor.value

    const floorGroup = new THREE.Group()
    floorGroup.userData.floorId = floorData.id
    floorGroup.userData.floorIndex = i

    const slabGeom = new THREE.BoxGeometry(buildingW, 0.3, buildingD)
    const slabMat = new THREE.MeshStandardMaterial({
      color: isCurrent ? 0x1e3a5f : 0x132237,
      roughness: 0.7,
      metalness: 0.2,
      transparent: true,
      opacity: isCurrent ? 1 : 0.55,
    })
    const slab = new THREE.Mesh(slabGeom, slabMat)
    slab.position.y = floorY
    slab.receiveShadow = true
    slab.castShadow = true
    floorGroup.add(slab)

    const wallHeight = floorHeight - 0.3
    const wallThickness = 0.4

    const wallMat = new THREE.MeshStandardMaterial({
      color: isCurrent ? 0x0088cc : 0x2a4a6a,
      roughness: 0.5,
      metalness: 0.3,
      transparent: true,
      opacity: isCurrent ? 0.8 : 0.35,
    })

    const glassMat = new THREE.MeshStandardMaterial({
      color: 0x88ccff,
      roughness: 0.1,
      metalness: 0.8,
      transparent: true,
      opacity: isCurrent ? 0.4 : 0.2,
      emissive: 0x003366,
      emissiveIntensity: 0.3,
    })

    const frontWall = new THREE.Mesh(new THREE.BoxGeometry(buildingW, wallHeight, wallThickness), wallMat)
    frontWall.position.set(0, floorY + wallHeight / 2 + 0.15, buildingD / 2 - wallThickness / 2)
    frontWall.castShadow = true
    floorGroup.add(frontWall)

    const backWall = new THREE.Mesh(new THREE.BoxGeometry(buildingW, wallHeight, wallThickness), wallMat)
    backWall.position.set(0, floorY + wallHeight / 2 + 0.15, -buildingD / 2 + wallThickness / 2)
    backWall.castShadow = true
    floorGroup.add(backWall)

    const leftWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, buildingD), wallMat)
    leftWall.position.set(-buildingW / 2 + wallThickness / 2, floorY + wallHeight / 2 + 0.15, 0)
    leftWall.castShadow = true
    floorGroup.add(leftWall)

    const rightWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, buildingD), wallMat)
    rightWall.position.set(buildingW / 2 - wallThickness / 2, floorY + wallHeight / 2 + 0.15, 0)
    rightWall.castShadow = true
    floorGroup.add(rightWall)

    const windowRows = 3
    const windowCols = 6
    const winW = 2.5
    const winH = 0.9
    const startX = -buildingW / 2 + 3
    const stepX = (buildingW - 6) / (windowCols - 1)

    for (let row = 0; row < windowRows; row++) {
      for (let col = 0; col < windowCols; col++) {
        const winGeom = new THREE.BoxGeometry(winW, winH, 0.1)
        const win = new THREE.Mesh(winGeom, glassMat)
        win.position.set(
          startX + col * stepX,
          floorY + 1 + row * 1.1,
          buildingD / 2 + 0.05
        )
        floorGroup.add(win)

        const winBack = win.clone()
        winBack.position.z = -buildingD / 2 - 0.05
        floorGroup.add(winBack)
      }
    }

    const stairWellGeom = new THREE.BoxGeometry(4, wallHeight, 3)
    const stairWellMat = new THREE.MeshStandardMaterial({
      color: 0x1a3a5c,
      transparent: true,
      opacity: 0.3,
      side: THREE.DoubleSide,
    })
    const stairWell = new THREE.Mesh(stairWellGeom, stairWellMat)
    stairWell.position.set(-buildingW / 2 + 4, floorY + wallHeight / 2 + 0.15, 0)
    floorGroup.add(stairWell)

    if (isCurrent) {
      const edgesGeom = new THREE.EdgesGeometry(new THREE.BoxGeometry(buildingW, wallHeight, buildingD))
      const edgesMat = new THREE.LineBasicMaterial({ color: 0x00ffff, transparent: true, opacity: 0.8 })
      const edges = new THREE.LineSegments(edgesGeom, edgesMat)
      edges.position.y = floorY + wallHeight / 2 + 0.15
      floorGroup.add(edges)
      currentFloorMesh = floorGroup

      const floorLight = new THREE.PointLight(0x00ffff, 0.5, 30)
      floorLight.position.set(0, floorY + wallHeight, 0)
      floorGroup.add(floorLight)
    }

    buildingMeshes.push(floorGroup)
    buildingGroup.add(floorGroup)
  }

  const roofGeom = new THREE.BoxGeometry(buildingW + 0.8, 0.6, buildingD + 0.8)
  const roofMat = new THREE.MeshStandardMaterial({
    color: 0x1a2a3a,
    roughness: 0.6,
    metalness: 0.4,
  })
  const roof = new THREE.Mesh(roofGeom, roofMat)
  roof.position.y = floorCount * floorHeight + 0.3
  roof.castShadow = true
  buildingGroup.add(roof)

  const antennaGeom = new THREE.CylinderGeometry(0.05, 0.1, 4, 6)
  const antennaMat = new THREE.MeshStandardMaterial({ color: 0x8899aa, metalness: 0.8 })
  const antenna = new THREE.Mesh(antennaGeom, antennaMat)
  antenna.position.set(5, floorCount * floorHeight + 2.5, -5)
  buildingGroup.add(antenna)

  const hvacGeom = new THREE.BoxGeometry(4, 1.2, 3)
  const hvacMat = new THREE.MeshStandardMaterial({ color: 0x334455, roughness: 0.7 })
  const hvac = new THREE.Mesh(hvacGeom, hvacMat)
  hvac.position.set(-6, floorCount * floorHeight + 1.2, 4)
  hvac.castShadow = true
  buildingGroup.add(hvac)

  scene.add(buildingGroup)

  const totalHeight = floorCount * floorHeight
  camera.position.set(35, totalHeight * 0.6 + 10, 45)
  controls.target.set(0, totalHeight / 2, 0)
  controls.update()
}

function clearDeviceMarkers() {
  deviceMarkers.forEach(m => {
    if (m.parent) m.parent.remove(m)
  })
  deviceMarkers = []
}

function addDeviceMarkers() {
  if (!scene) return
  clearDeviceMarkers()

  const floorIndex = floors.value.findIndex(f => f.id === currentFloor.value)
  if (floorIndex < 0) return

  const floorHeight = 3.8
  const floorY = floorIndex * floorHeight + 1.8

  currentFloorDevices.value.forEach(device => {
    const x = (device.x / 100 - 0.5) * 24
    const z = (device.y / 100 - 0.5) * 16

    const markerGroup = new THREE.Group()

    const beamGeom = new THREE.CylinderGeometry(0.05, 0.15, 2, 8)
    const beamColor = new THREE.Color(deviceTypeLegend[device.type]?.color || '#666')
    const beamMat = new THREE.MeshBasicMaterial({
      color: beamColor,
      transparent: true,
      opacity: 0.5,
    })
    const beam = new THREE.Mesh(beamGeom, beamMat)
    beam.position.y = 1
    markerGroup.add(beam)

    const geom = new THREE.SphereGeometry(0.45, 16, 16)
    const color = beamColor
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.5,
      metalness: 0.3,
      roughness: 0.4,
    })
    const sphere = new THREE.Mesh(geom, mat)
    markerGroup.add(sphere)

    const ringGeom = new THREE.RingGeometry(0.55, 0.75, 32)
    const ringMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.3,
      side: THREE.DoubleSide,
    })
    const ring = new THREE.Mesh(ringGeom, ringMat)
    ring.rotation.x = -Math.PI / 2
    markerGroup.add(ring)

    if (device.status === 'alarm') {
      const pulseGeom = new THREE.RingGeometry(0.8, 1.1, 32)
      const pulseMat = new THREE.MeshBasicMaterial({
        color: 0xff3333,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
      })
      const pulse = new THREE.Mesh(pulseGeom, pulseMat)
      pulse.rotation.x = -Math.PI / 2
      pulse.userData.isPulse = true
      markerGroup.add(pulse)

      const alarmBeamGeom = new THREE.CylinderGeometry(0.1, 0.5, 3, 12)
      const alarmBeamMat = new THREE.MeshBasicMaterial({
        color: 0xff0000,
        transparent: true,
        opacity: 0.4,
      })
      const alarmBeam = new THREE.Mesh(alarmBeamGeom, alarmBeamMat)
      alarmBeam.position.y = 1.5
      alarmBeam.userData.isAlarmBeam = true
      markerGroup.add(alarmBeam)
    }

    if (device.status === 'offline') {
      const offMat = new THREE.MeshBasicMaterial({
        color: 0x666666,
        transparent: true,
        opacity: 0.6,
      })
      sphere.material = offMat
    }

    markerGroup.position.set(x, floorY, z)
    markerGroup.userData = { device, time: Math.random() * Math.PI * 2 }
    deviceMarkers.push(markerGroup)
    if (buildingGroup) {
      buildingGroup.add(markerGroup)
    } else {
      scene.add(markerGroup)
    }
  })
}

function updateFloorHighlight() {
  if (!buildingMeshes.length) return
  buildingMeshes.forEach((mesh, index) => {
    const isCurrent = index + 1 === currentFloor.value
    mesh.children.forEach(child => {
      if (child.material) {
        if (isCurrent) {
          child.material.opacity = child.geometry.type === 'EdgesGeometry' ? 0.8 : 0.85
        } else {
          child.material.opacity = 0.4
        }
      }
    })
  })

  deviceMarkers.forEach(m => scene.remove(m))
  deviceMarkers = []
  addDeviceMarkers()
}

function drawPlan() {
  if (!planCanvasRef.value) return
  const canvas = planCanvasRef.value
  const ctx = canvas.getContext('2d')
  const container = canvas.parentElement
  canvas.width = container.clientWidth
  canvas.height = container.clientHeight
  const w = canvas.width
  const h = canvas.height

  ctx.clearRect(0, 0, w, h)

  ctx.fillStyle = '#0a1628'
  ctx.fillRect(0, 0, w, h)

  ctx.strokeStyle = 'rgba(59, 130, 246, 0.1)'
  ctx.lineWidth = 1
  const gridSize = 40
  for (let x = 0; x < w; x += gridSize) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, h)
    ctx.stroke()
  }
  for (let y = 0; y < h; y += gridSize) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
  }

  const padding = 60
  const planW = w - padding * 2
  const planH = h - padding * 2
  const planX = padding
  const planY = padding

  ctx.fillStyle = 'rgba(15, 23, 42, 0.8)'
  ctx.strokeStyle = '#1e40af'
  ctx.lineWidth = 3
  ctx.beginPath()
  ctx.roundRect(planX, planY, planW, planH, 4)
  ctx.fill()
  ctx.stroke()

  ctx.strokeStyle = 'rgba(59, 130, 246, 0.3)'
  ctx.lineWidth = 2

  const rooms = [
    { x: 0.05, y: 0.05, w: 0.25, h: 0.25, name: '大厅' },
    { x: 0.32, y: 0.05, w: 0.2, h: 0.25, name: '会议室A' },
    { x: 0.54, y: 0.05, w: 0.2, h: 0.25, name: '会议室B' },
    { x: 0.76, y: 0.05, w: 0.19, h: 0.25, name: '接待室' },
    { x: 0.05, y: 0.33, w: 0.15, h: 0.3, name: '办公区1' },
    { x: 0.22, y: 0.33, w: 0.15, h: 0.3, name: '办公区2' },
    { x: 0.39, y: 0.33, w: 0.15, h: 0.3, name: '办公区3' },
    { x: 0.56, y: 0.33, w: 0.15, h: 0.3, name: '办公区4' },
    { x: 0.76, y: 0.33, w: 0.19, h: 0.14, name: '机房' },
    { x: 0.76, y: 0.49, w: 0.19, h: 0.14, name: '储藏室' },
    { x: 0.05, y: 0.66, w: 0.2, h: 0.29, name: '休息区' },
    { x: 0.27, y: 0.66, w: 0.2, h: 0.29, name: '茶水间' },
    { x: 0.49, y: 0.66, w: 0.2, h: 0.29, name: '卫生间' },
    { x: 0.76, y: 0.66, w: 0.19, h: 0.29, name: '走廊' },
  ]

  rooms.forEach(room => {
    const rx = planX + room.x * planW
    const ry = planY + room.y * planH
    const rw = room.w * planW
    const rh = room.h * planH

    ctx.fillStyle = 'rgba(30, 41, 59, 0.5)'
    ctx.fillRect(rx, ry, rw, rh)
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)'
    ctx.lineWidth = 1.5
    ctx.strokeRect(rx, ry, rw, rh)

    ctx.fillStyle = '#64748b'
    ctx.font = '12px Microsoft YaHei'
    ctx.textAlign = 'center'
    ctx.fillText(room.name, rx + rw / 2, ry + rh / 2 + 4)
  })

  currentFloorDevices.value.forEach(device => {
    const dx = planX + (device.x / 100) * planW
    const dy = planY + (device.y / 100) * planH
    const color = deviceTypeLegend[device.type]?.color || '#666'
    const isSelected = selectedDevice.value?.id === device.id
    const isFocused = focusedDeviceId.value === device.id

    if (device.status === 'alarm') {
      const time = Date.now() / 500
      const pulseSize = 12 + Math.sin(time) * 4
      ctx.beginPath()
      ctx.arc(dx, dy, pulseSize, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(239, 68, 68, 0.2)'
      ctx.fill()
    }

    if (isFocused) {
      const focusTime = Date.now() / 300
      const focusPulse = 20 + Math.sin(focusTime) * 6
      const grad = ctx.createRadialGradient(dx, dy, 0, dx, dy, focusPulse)
      grad.addColorStop(0, 'rgba(255, 255, 255, 0.4)')
      grad.addColorStop(0.5, 'rgba(96, 165, 250, 0.3)')
      grad.addColorStop(1, 'rgba(96, 165, 250, 0)')
      ctx.beginPath()
      ctx.arc(dx, dy, focusPulse, 0, Math.PI * 2)
      ctx.fillStyle = grad
      ctx.fill()
    }

    ctx.beginPath()
    ctx.arc(dx, dy, isSelected || isFocused ? 9 : 6, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    ctx.strokeStyle = isFocused ? '#60a5fa' : '#fff'
    ctx.lineWidth = isFocused ? 3 : 2
    ctx.stroke()

    if (isSelected) {
      ctx.beginPath()
      ctx.arc(dx, dy, 14, 0, Math.PI * 2)
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.setLineDash([4, 4])
      ctx.stroke()
      ctx.setLineDash([])
    }
  })

  if (cadResult.value?.walls) {
    cadResult.value.walls.forEach(wall => {
      const x1 = planX + wall.x1 / 100 * planW
      const y1 = planY + wall.y1 / 100 * planH
      const x2 = planX + wall.x2 / 100 * planW
      const y2 = planY + wall.y2 / 100 * planH

      ctx.beginPath()
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.strokeStyle = wall.type === 'wall' ? '#4a5568' : 'rgba(74, 85, 104, 0.4)'
      ctx.lineWidth = wall.type === 'wall' ? 3 : 1
      ctx.stroke()
    })
  }

  if (cadResult.value?.rooms) {
    cadResult.value.rooms.forEach(room => {
      if (room.x !== undefined) {
        const rx = planX + room.x / 100 * planW
        const ry = planY + room.y / 100 * planH
        const rw = room.w / 100 * planW
        const rh = room.h / 100 * planH

        ctx.fillStyle = 'rgba(30, 58, 95, 0.25)'
        ctx.fillRect(rx, ry, rw, rh)

        ctx.strokeStyle = 'rgba(59, 130, 246, 0.3)'
        ctx.lineWidth = 1
        ctx.setLineDash([4, 3])
        ctx.strokeRect(rx, ry, rw, rh)
        ctx.setLineDash([])

        if (room.name) {
          ctx.fillStyle = 'rgba(15, 23, 42, 0.7)'
          const textWidth = ctx.measureText(room.name).width
          ctx.fillRect(
            rx + rw / 2 - textWidth / 2 - 6,
            ry + rh / 2 - 9,
            textWidth + 12,
            18
          )
          ctx.fillStyle = '#93c5fd'
          ctx.font = '12px Microsoft YaHei'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'middle'
          ctx.fillText(room.name, rx + rw / 2, ry + rh / 2)
          ctx.textBaseline = 'alphabetic'
        }
      }
    })
  }

  if (showEvacuation.value && evacuationData.value) {
    evacuationData.value.dangerZones?.forEach(zone => {
      const zx = planX + zone.x / 100 * planW
      const zy = planY + zone.y / 100 * planH
      const zr = zone.radius / 100 * Math.min(planW, planH)
      const grad = ctx.createRadialGradient(zx, zy, 0, zx, zy, zr)
      grad.addColorStop(0, 'rgba(239, 68, 68, 0.4)')
      grad.addColorStop(1, 'rgba(239, 68, 68, 0)')
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(zx, zy, zr, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#ef4444'
      ctx.font = 'bold 12px Microsoft YaHei'
      ctx.textAlign = 'center'
      ctx.fillText(zone.name, zx, zy + 4)
    })

    evacuationData.value.evacuationRoutes?.forEach((route, idx) => {
      if (route.path && route.path.length >= 2) {
        ctx.beginPath()
        ctx.strokeStyle = idx === 0 ? '#22c55e' : idx === 1 ? '#3b82f6' : '#f59e0b'
        ctx.lineWidth = 3
        ctx.setLineDash([8, 4])
        route.path.forEach((p, i) => {
          const px = planX + p.x / 100 * planW
          const py = planY + p.y / 100 * planH
          if (i === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        })
        ctx.stroke()
        ctx.setLineDash([])
      }
    })

    evacuationData.value.assemblyPoints?.forEach(point => {
      const px = planX + Math.max(0, Math.min(100, point.x)) / 100 * planW
      const py = planY + Math.max(0, Math.min(100, point.y)) / 100 * planH
      ctx.beginPath()
      ctx.arc(px, py, 10, 0, Math.PI * 2)
      ctx.fillStyle = '#22c55e'
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.fillStyle = '#fff'
      ctx.font = 'bold 10px Microsoft YaHei'
      ctx.textAlign = 'center'
      ctx.fillText('集', px, py + 3)
    })
  }

  if (navPath.value?.waypoints) {
    const sameFloorPoints = navPath.value.waypoints.filter(
      (p, i, arr) => p.floor === (currentFloorData.value?.number || 1)
    )
    if (sameFloorPoints.length >= 2) {
      ctx.beginPath()
      ctx.strokeStyle = '#22c55e'
      ctx.lineWidth = 4
      ctx.setLineDash([10, 5])
      sameFloorPoints.forEach((p, i) => {
        const px = planX + p.x / 100 * planW
        const py = planY + p.y / 100 * planH
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      })
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  if (navStartPoint.value) {
    const sx = planX + navStartPoint.value.x / 100 * planW
    const sy = planY + navStartPoint.value.y / 100 * planH
    ctx.beginPath()
    ctx.arc(sx, sy, 10, 0, Math.PI * 2)
    ctx.fillStyle = '#22c55e'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 10px Microsoft YaHei'
    ctx.textAlign = 'center'
    ctx.fillText('起', sx, sy + 3)
  }

  if (navEndPoint.value) {
    const ex = planX + navEndPoint.value.x / 100 * planW
    const ey = planY + navEndPoint.value.y / 100 * planH
    ctx.beginPath()
    ctx.arc(ex, ey, 10, 0, Math.PI * 2)
    ctx.fillStyle = '#ef4444'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 10px Microsoft YaHei'
    ctx.textAlign = 'center'
    ctx.fillText('终', ex, ey + 3)
  }

  if (viewMode.value === 'plan') {
    requestAnimationFrame(drawPlan)
  }
}

function animate() {
  animationId = requestAnimationFrame(animate)
  controls?.update()

  const time = Date.now() * 0.001
  deviceMarkers.forEach((marker, i) => {
    const t = marker.userData.time + time
    marker.scale.setScalar(0.8 + Math.sin(t * 2 + i * 0.3) * 0.2)
    if (marker.children[2]) {
      marker.children[2].scale.setScalar(1 + Math.sin(t * 3) * 0.3)
      marker.children[2].material.opacity = 0.3 + Math.sin(t * 3) * 0.3
    }
  })

  renderer?.render(scene, camera)
}

function handleResize() {
  if (!sceneRef.value || !renderer || !camera) return
  const width = sceneRef.value.clientWidth
  const height = sceneRef.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

watch(viewMode, (val) => {
  if (val === 'plan') {
    nextTick(() => drawPlan())
  }
})

onMounted(async () => {
  await loadBuildingData()
  nextTick(() => {
    init3DScene()
    drawPlan()
  })
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (animationId) cancelAnimationFrame(animationId)
  if (renderer) {
    renderer.dispose()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }
  if (controls) controls.dispose()
  scene = null
  camera = null
  renderer = null
  controls = null
  buildingMeshes = []
  deviceMarkers = []
})
</script>

<style scoped>
.building-detail-page {
  height: calc(100vh - 60px - 44px);
  display: flex;
  flex-direction: column;
  background: #020617;
  color: #e2e8f0;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.5));
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  background: linear-gradient(180deg, #fff, #60a5fa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.building-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.meta-text {
  font-size: 13px;
  color: #64748b;
}

.header-right {
  display: flex;
  gap: 10px;
}

.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  gap: 12px;
  padding: 12px;
  overflow: hidden;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.floor-nav,
.device-panel,
.device-detail-panel,
.stat-panel,
.recent-alarm-panel {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.8), rgba(15, 23, 42, 0.6));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.floor-nav {
  flex-shrink: 0;
}

.nav-title,
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  border-bottom: 1px solid rgba(59, 130, 246, 0.15);
}

.nav-title :deep(.el-icon),
.panel-title :deep(.el-icon) {
  color: #3b82f6;
}

.floor-list {
  padding: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.floor-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.floor-nav-item:hover {
  background: rgba(59, 130, 246, 0.1);
}

.floor-nav-item.active {
  background: rgba(59, 130, 246, 0.2);
  border-left: 3px solid #3b82f6;
  padding-left: 9px;
}

.floor-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(59, 130, 246, 0.1));
  border-radius: 8px;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
  flex-shrink: 0;
}

.floor-icon span {
  font-size: 16px;
  font-weight: 700;
  color: #60a5fa;
}

.floor-icon .floor-unit {
  font-size: 11px;
  font-weight: 500;
}

.floor-info {
  flex: 1;
  min-width: 0;
}

.floor-name {
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
  margin-bottom: 2px;
}

.floor-stats {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 3px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.dot.smoke { background: #ef4444; }
.dot.hydrant { background: #3b82f6; }

.floor-alarm {
  flex-shrink: 0;
}

.alarm-badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
  animation: pulse-badge 2s infinite;
}

@keyframes pulse-badge {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
}

.device-panel {
  flex: 1;
  min-height: 0;
}

.device-search {
  padding: 10px 12px;
  flex-shrink: 0;
}

.device-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.device-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.device-item:hover {
  background: rgba(59, 130, 246, 0.1);
}

.device-item.active {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.device-item.alarm {
  border-left: 3px solid #ef4444;
}

.device-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.device-icon.smoke { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.device-icon.heat { background: rgba(249, 115, 22, 0.2); color: #f97316; }
.device-icon.hydrant { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.device-icon.sprinkler { background: rgba(6, 182, 212, 0.2); color: #06b6d4; }
.device-icon.manual { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
.device-icon.extinguisher { background: rgba(220, 38, 38, 0.2); color: #dc2626; }

.device-info {
  flex: 1;
  min-width: 0;
}

.device-name {
  font-size: 12px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.device-code {
  font-size: 11px;
  color: #64748b;
  font-family: Consolas, monospace;
}

.device-status {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.device-status.normal { color: #22c55e; }
.device-status.warning { color: #f59e0b; }
.device-status.alarm { color: #ef4444; }
.device-status.offline { color: #64748b; }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.center-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.view-tabs {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.view-tab {
  padding: 8px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.view-tab:hover {
  color: #94a3b8;
  background: rgba(59, 130, 246, 0.1);
}

.view-tab.active {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
  border-bottom-color: transparent;
}

.view-container {
  flex: 1;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.8), rgba(15, 23, 42, 0.6));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 0 8px 8px 8px;
  position: relative;
  overflow: hidden;
  min-height: 0;
}

.scene-container,
.plan-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.plan-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.scene-overlay,
.plan-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.floor-indicator {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  padding: 10px 16px;
  text-align: center;
}

.floor-num {
  font-size: 28px;
  font-weight: 700;
  color: #60a5fa;
  font-family: Consolas, monospace;
  line-height: 1;
}

.floor-label {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  display: block;
}

.scale-bar {
  position: absolute;
  bottom: 20px;
  left: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 11px;
}

.scale-line {
  width: 80px;
  height: 4px;
  background: linear-gradient(90deg, #3b82f6, #3b82f6 50%, transparent 50%, transparent);
  background-size: 10px 100%;
}

.compass {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(59, 130, 246, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.north {
  color: #ef4444;
  font-size: 14px;
  font-weight: 700;
}

.plan-legend {
  display: flex;
  justify-content: space-between;
  flex-shrink: 0;
  padding: 8px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 6px;
  font-size: 12px;
}

.legend-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.legend-title {
  color: #94a3b8;
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #cbd5e1;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot.normal { background: #22c55e; }
.legend-dot.warning { background: #f59e0b; }
.legend-dot.alarm { background: #ef4444; }
.legend-dot.offline { background: #64748b; }

.device-detail-panel {
  flex-shrink: 0;
}

.detail-section {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.detail-section:last-of-type {
  border-bottom: none;
}

.section-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
  font-size: 13px;
}

.detail-row .label {
  color: #64748b;
}

.detail-row .value {
  color: #e2e8f0;
  text-align: right;
}

.text-warning {
  color: #f59e0b !important;
}

.detail-actions {
  padding: 12px 14px;
  display: flex;
  gap: 8px;
  border-top: 1px solid rgba(59, 130, 246, 0.1);
}

.detail-actions .el-button {
  flex: 1;
}

.stat-panel {
  flex-shrink: 0;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 12px;
}

.stat-card {
  background: rgba(15, 23, 42, 0.5);
  border-radius: 6px;
  padding: 12px;
  text-align: center;
}

.stat-card .stat-num {
  font-size: 22px;
  font-weight: 700;
  font-family: Consolas, monospace;
  margin-bottom: 4px;
}

.stat-card .stat-label {
  font-size: 11px;
  color: #64748b;
}

.stat-card.total .stat-num { color: #60a5fa; }
.stat-card.normal .stat-num { color: #22c55e; }
.stat-card.alarm .stat-num { color: #ef4444; }
.stat-card.offline .stat-num { color: #64748b; }

.recent-alarm-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.alarm-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
}

.alarm-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.5);
  margin-bottom: 6px;
  border-left: 3px solid #64748b;
}

.alarm-item.critical {
  border-left-color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.alarm-item.warning {
  border-left-color: #f59e0b;
}

.alarm-icon {
  color: #ef4444;
  font-size: 16px;
  flex-shrink: 0;
}

.alarm-content {
  flex: 1;
  min-width: 0;
}

.alarm-title {
  font-size: 12px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}

.alarm-time {
  font-size: 11px;
  color: #475569;
}

::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.3);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.5);
}

::-webkit-scrollbar-track {
  background: transparent;
}

.tab-divider {
  width: 1px;
  height: 20px;
  background: rgba(59, 130, 246, 0.3);
  margin: 0 8px;
}

.view-tab[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.nav-cursor {
  cursor: crosshair;
}

.nav-tip {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(34, 197, 94, 0.9);
  color: #fff;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 10;
}

.nav-info-panel {
  position: absolute;
  bottom: 20px;
  right: 20px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  padding: 12px 16px;
  min-width: 160px;
  z-index: 10;
}

.nav-info-title {
  font-size: 14px;
  font-weight: 600;
  color: #22c55e;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
}

.nav-info-row .label {
  color: #64748b;
}

.nav-info-row .value {
  color: #e2e8f0;
  font-weight: 500;
}

.nav-info-row .value.warning {
  color: #f59e0b;
}

.evac-info-panel {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  padding: 12px 16px;
  min-width: 180px;
  z-index: 10;
}

.evac-info-title {
  font-size: 14px;
  font-weight: 600;
  color: #ef4444;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: space-between;
}

.evac-info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
}

.evac-info-row .label {
  color: #64748b;
}

.evac-info-row .value {
  color: #e2e8f0;
  font-weight: 500;
}

.evac-info-row.danger .value {
  color: #ef4444;
}

.imported-tip {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
  font-size: 13px;
  line-height: 1.6;
}

.cad-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 30px;
  color: #60a5fa;
  font-size: 14px;
}

.cad-result {
  margin-top: 16px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.result-title {
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
}

.result-file {
  font-size: 12px;
  color: #64748b;
}

.result-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.result-stats .stat-item {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.result-stats .stat-item.primary {
  border-color: rgba(34, 197, 94, 0.4);
  background: rgba(34, 197, 94, 0.1);
}

.layer-summary {
  margin-bottom: 16px;
  padding: 10px 12px;
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  font-size: 12px;
  line-height: 1.6;
}

.layer-summary .layer-count {
  color: #93c5fd;
  margin-right: 8px;
}

.layer-summary .layer-names {
  color: #94a3b8;
  word-break: break-all;
}

.stat-number {
  font-size: 22px;
  font-weight: 700;
  color: #60a5fa;
  display: block;
}

.result-stats .stat-item.primary .stat-number {
  color: #22c55e;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.device-import-section {
  border-top: 1px solid rgba(59, 130, 246, 0.2);
  padding-top: 12px;
}

.import-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.import-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  flex: 1;
}

.selected-count {
  font-size: 12px;
  color: #22c55e;
}

.device-check-list {
  max-height: 240px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.device-check-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.device-check-item:hover {
  background: rgba(59, 130, 246, 0.1);
}

.device-check-item.checked {
  background: rgba(34, 197, 94, 0.1);
}

.dev-icon {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dev-icon.smoke { background: #ef4444; }
.dev-icon.heat { background: #f97316; }
.dev-icon.hydrant { background: #3b82f6; }
.dev-icon.sprinkler { background: #06b6d4; }
.dev-icon.manual { background: #f59e0b; }
.dev-icon.extinguisher { background: #dc2626; }

.dev-type {
  font-size: 13px;
  color: #e2e8f0;
  flex: 1;
}

.dev-pos {
  font-size: 11px;
  color: #64748b;
}

.room-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(59, 130, 246, 0.2);
}

.section-header {
  margin-bottom: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
}

.room-list {
  max-height: 180px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.room-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: rgba(30, 58, 95, 0.3);
  border-radius: 4px;
  font-size: 12px;
}

.room-name {
  color: #93c5fd;
}

.room-area {
  color: #64748b;
  font-size: 11px;
}

.bim-info {
  margin-top: 16px;
}

.bim-features {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(59, 130, 246, 0.2);
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 12px;
}

.feature-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 6px;
  font-size: 13px;
  color: #94a3b8;
}

.header-right .el-button + .el-button {
  margin-left: 8px;
}

.diagnose-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}
.diagnose-status {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-label {
  color: #64748b;
  font-size: 13px;
}
.diagnose-confidence {
  font-size: 13px;
  color: #3b82f6;
  font-weight: 500;
}

.diagnose-section {
  margin-bottom: 20px;
}
.diagnose-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #3b82f6;
}

/* 设备台账数据：诊断权重的真实依据 */
.diagnose-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #475569;
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 12px;
}

.diagnose-signals .signals-label {
  color: #94a3b8;
}

.diagnose-signals .signal-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 1px 6px;
}

.weight-hint {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: #3b82f6;
  cursor: help;
}

.fault-causes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fault-cause-item {
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 3px solid #f59e0b;
}
.cause-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.cause-name {
  font-weight: 600;
  font-size: 13px;
  color: #1e293b;
}
.cause-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
  line-height: 1.5;
}
.cause-evidence {
  font-size: 11px;
}
.evidence-label {
  color: #94a3b8;
  margin-right: 4px;
}
.evidence-list {
  display: inline;
}
.evidence-item {
  display: inline-block;
  background: #fef3c7;
  color: #92400e;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  margin-right: 4px;
  margin-bottom: 4px;
}

.repair-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.repair-step {
  display: flex;
  gap: 12px;
  padding: 10px;
  background: #f0fdf4;
  border-radius: 8px;
}
.repair-priority {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #22c55e;
  color: white;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.repair-action {
  font-weight: 600;
  font-size: 13px;
  color: #166534;
  margin-bottom: 4px;
}
.repair-detail {
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
  line-height: 1.4;
}
.repair-time {
  font-size: 11px;
  color: #22c55e;
  font-weight: 500;
}

.maintenance-tips {
  margin: 0;
  padding-left: 18px;
}
.maintenance-tips li {
  margin-bottom: 6px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}
</style>
