<template>
  <div>
    <div class="page-title">设备数据表</div>

    <el-alert
      title="设备数据表已接入设备档案、遥测数据和演示数据。"
      type="success"
      show-icon
      style="margin-bottom:12px"
    />

    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :span="6"><el-card class="metric-card"><span>设备数量</span><strong>{{ stats.deviceCount }}</strong></el-card></el-col>
      <el-col :span="6"><el-card class="metric-card"><span>遥测记录</span><strong>{{ stats.telemetryCount }}</strong></el-card></el-col>
      <el-col :span="6"><el-card class="metric-card"><span>在线设备</span><strong>{{ stats.onlineCount }}</strong></el-card></el-col>
      <el-col :span="6"><el-card class="metric-card"><span>平均温度</span><strong>{{ stats.avgTemp }}℃</strong></el-card></el-col>
    </el-row>

    <el-card class="card">
      <template #header>
        <div class="header-row">
          <strong>设备运行数据</strong>
          <div>
            <el-button @click="load">刷新</el-button>
            <el-button type="primary" @click="seedDemo">生成演示数据</el-button>
          </div>
        </div>
      </template>

      <el-table :data="telemetry" border height="360">
        <el-table-column prop="created_at" label="采集时间" width="180" />
        <el-table-column prop="device_name" label="设备名称" width="170" />
        <el-table-column prop="temperature" label="温度℃" width="90">
          <template #default="{ row }"><el-tag :type="row.temperature >= 50 ? 'danger' : row.temperature >= 38 ? 'warning' : 'success'">{{ row.temperature }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="smoke" label="烟雾" width="90">
          <template #default="{ row }"><el-tag :type="row.smoke >= 0.45 ? 'danger' : row.smoke >= 0.2 ? 'warning' : 'success'">{{ row.smoke }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="co" label="CO" width="90">
          <template #default="{ row }"><el-tag :type="row.co >= 0.15 ? 'danger' : row.co >= 0.08 ? 'warning' : 'success'">{{ row.co }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="battery" label="电量%" width="100">
          <template #default="{ row }"><el-progress :percentage="Number(row.battery || 0)" :status="row.battery < 20 ? 'exception' : row.battery < 50 ? 'warning' : 'success'" /></template>
        </el-table-column>
        <el-table-column prop="online" label="在线" width="90">
          <template #default="{ row }"><el-tag :type="row.online ? 'success' : 'danger'">{{ row.online ? '在线' : '离线' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="异常判断">
          <template #default="{ row }">
            <el-tag v-for="a in anomaly(row)" :key="a" :type="a.includes('正常') ? 'success' : 'danger'" effect="plain" style="margin-right:6px">{{ a }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!telemetry.length" description="暂无设备采集数据。点击右上角“生成演示数据”即可初始化。" />
    </el-card>

    <el-card class="card">
      <template #header>设备档案参考表</template>
      <el-table :data="devices" border>
        <el-table-column prop="device_code" label="设备编号" width="130" />
        <el-table-column prop="device_name" label="设备名称" width="170" />
        <el-table-column prop="device_type" label="类型" width="110" />
        <el-table-column prop="location" label="位置" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag :type="row.status === '正常' ? 'success' : 'warning'">{{ row.status }}</el-tag></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue"
import request from "../api"
import { ElMessage } from "element-plus"

const devices = ref([])
const telemetry = ref([])

const stats = computed(() => {
  const temps = telemetry.value.map(i => Number(i.temperature || 0)).filter(v => !Number.isNaN(v))
  return {
    deviceCount: devices.value.length,
    telemetryCount: telemetry.value.length,
    onlineCount: telemetry.value.filter(i => i.online).length,
    avgTemp: temps.length ? (temps.reduce((a,b)=>a+b,0)/temps.length).toFixed(1) : 0,
  }
})

const anomaly = row => {
  const arr = []
  if (!row.online) arr.push("设备离线")
  if (Number(row.temperature || 0) >= 50) arr.push("温度异常")
  if (Number(row.smoke || 0) >= 0.45) arr.push("烟雾异常")
  if (Number(row.co || 0) >= 0.15) arr.push("CO异常")
  if (Number(row.battery || 0) < 20) arr.push("低电量")
  return arr.length ? arr : ["正常"]
}

const load = async () => {
  const [devRes, telRes] = await Promise.all([
    request.get("/api/devices"),
    request.get("/api/device-telemetry")
  ])
  devices.value = devRes.data?.items || devRes.data || []
  telemetry.value = telRes.data?.items || telRes.data || []
}

const seedDemo = async () => {
  await request.post("/api/demo/seed-all")
  ElMessage.success("演示数据已生成")
  await load()
}

onMounted(load)
</script>

<style scoped>
.metric-card { border-radius:14px; }
.metric-card :deep(.el-card__body){ display:flex; justify-content:space-between; align-items:center; }
.metric-card span{ color:#64748b; }
.metric-card strong{ font-size:28px; color:#2563eb; }
.header-row{ display:flex; justify-content:space-between; align-items:center; }
.card{ margin-bottom:12px; }
</style>
