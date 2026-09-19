<template>
  <div>
    <div class="page-title">系统状态</div>

    <el-card class="card">
      <template #header>
        <div class="header-row">
          <strong>运行状态检测</strong>
          <div>
            <el-button @click="load">刷新</el-button>
            <el-button type="primary" @click="seedDemo">一键生成演示数据</el-button>
          </div>
        </div>
      </template>

      <el-alert
        :title="health.suggestion || '系统状态检测中'"
        :type="health.overall === '异常' ? 'error' : health.overall === '警告' ? 'warning' : 'success'"
        show-icon
        style="margin-bottom:12px"
      />

      <el-table :data="health.checks || []" border>
        <el-table-column prop="name" label="检查项" width="160" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="说明" />
      </el-table>
    </el-card>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card class="card">
          <template #header>核心模块状态</template>
          <el-table :data="core.interfaces || []" border height="360">
            <el-table-column prop="module" label="模块" width="120" />
            <el-table-column prop="path" label="服务" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }"><el-tag :type="row.status === '可访问' ? 'success' : 'danger'">{{ row.status }}</el-tag></template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="card">
          <template #header>闭环模块状态</template>
          <el-descriptions border :column="1">
            <el-descriptions-item label="页面模块">{{ core.summary?.page_routes || 0 }} 项</el-descriptions-item>
            <el-descriptions-item label="系统服务">{{ core.summary?.api_routes || 0 }} 项</el-descriptions-item>
            <el-descriptions-item label="巡检记录">{{ core.summary?.records || 0 }} 条</el-descriptions-item>
            <el-descriptions-item label="整改工单">{{ core.summary?.workorders || 0 }} 条</el-descriptions-item>
            <el-descriptions-item label="硬件事件">{{ core.summary?.hardware_events || 0 }} 条</el-descriptions-item>
            <el-descriptions-item label="闭环说明">{{ core.summary?.closed_loop || '待检测' }}</el-descriptions-item>
          </el-descriptions>

          <el-divider />
          <el-alert type="info" show-icon :closable="false" title="建议路径：首页总览 → 现场巡检 → 巡检记录 → 整改工单 → 硬件事件 → 系统状态。" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import request from "../api"
import { ElMessage } from "element-plus"

const health = ref({})
const core = ref({})

const statusType = status => {
  if (status === "异常" || status === "不可访问") return "danger"
  if (status === "未配置" || status === "警告" || status === "部分配置") return "warning"
  return "success"
}

const load = async () => {
  health.value = (await request.get("/api/system/health")).data
  core.value = (await request.get("/api/system/core-check")).data
}

const seedDemo = async () => {
  const res = await request.post("/api/demo/seed-all")
  ElMessage.success(res.data?.message || "演示数据已生成")
  await load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display:flex; justify-content:space-between; align-items:center; }
.card{ margin-bottom:12px; }
</style>
