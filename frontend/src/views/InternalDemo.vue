<template>
  <div>
    <div class="page-title">隐藏演示闭环</div>
    <el-alert type="warning" show-icon class="card" title="该页面不会出现在左侧菜单，只能由管理员手动输入隐藏地址访问。" />
    <el-card class="card">
      <template #header>一键生成完整业务链路</template>
      <p class="muted">硬件报警 → Agent 风险研判 → 巡检档案 → 整改工单 → 待复查/闭环 → Dashboard 待办提醒。</p>
      <el-input v-model="secret" placeholder="隐藏口令" style="max-width:360px;margin-right:10px" show-password />
      <el-button type="primary" :loading="loading" @click="runDemo">运行隐藏演示闭环</el-button>
    </el-card>
    <el-card v-if="result" class="card">
      <template #header>生成结果</template>
      <el-alert :title="result.message" :type="result.ok ? 'success' : 'error'" show-icon style="margin-bottom:12px" />
      <el-descriptions v-if="result.ok" border :column="1">
        <el-descriptions-item label="硬件事件">{{ result.event?.id }} / {{ result.event?.event_name }}</el-descriptions-item>
        <el-descriptions-item label="巡检档案">{{ result.inspection?.id || result.inspection?.record_id }}</el-descriptions-item>
        <el-descriptions-item label="整改工单">{{ result.workorders?.length || 0 }} 条</el-descriptions-item>
      </el-descriptions>
      <div v-if="result.ok" style="margin-top:12px">
        <el-button type="primary" @click="$router.push('/dashboard')">查看 Dashboard</el-button>
        <el-button @click="$router.push('/records')">查看巡检档案</el-button>
        <el-button @click="$router.push('/workorders')">查看整改工单</el-button>
      </div>
      <el-collapse style="margin-top:12px"><el-collapse-item title="原始数据" name="raw"><pre>{{ JSON.stringify(result, null, 2) }}</pre></el-collapse-item></el-collapse>
    </el-card>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'
const secret=ref('fire-v12-demo'); const loading=ref(false); const result=ref(null)
const runDemo=async()=>{ loading.value=true; try{ result.value=(await request.post('/api/internal/closed-loop-demo',{secret:secret.value})).data; if(result.value.ok) ElMessage.success('隐藏演示闭环已生成'); else ElMessage.warning(result.value.message) } finally{ loading.value=false } }
</script>
<style scoped>.muted{color:#64748b;line-height:1.7}</style>
