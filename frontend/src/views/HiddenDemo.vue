<template>
  <div class="hidden-page">
    <div class="page-title">隐藏演示闭环</div>
    <el-alert title="该页面不会出现在系统菜单中，只能由管理员手动访问。演示数据会带 DEMO 标记，可一键清理。" type="warning" show-icon class="card" />
    <el-card class="card auth-card" v-if="!unlocked">
      <template #header>输入隐藏口令</template>
      <el-input v-model="secret" type="password" show-password placeholder="请输入隐藏口令" style="max-width:360px" @keyup.enter="unlock" />
      <el-button type="primary" style="margin-left:10px" @click="unlock">解锁</el-button>
    </el-card>
    <el-row v-else :gutter="12">
      <el-col :xs="24" :md="12"><el-card class="card"><template #header>一键生成完整演示闭环</template><p>自动生成：硬件报警 → Agent 分析 → 巡检档案 → 整改工单 → 待复查/已闭环状态 → Dashboard 统计。</p><el-button type="primary" :loading="loading" @click="generate">生成完整演示闭环</el-button></el-card></el-col>
      <el-col :xs="24" :md="12"><el-card class="card"><template #header>清理演示数据</template><p>仅清除带 DEMO 标记的演示数据，不影响你手动录入的数据。</p><el-button type="danger" plain :loading="loading" @click="clearDemo">清除演示数据</el-button></el-card></el-col>
      <el-col :span="24"><el-card v-if="result" class="card"><template #header>执行结果</template><pre>{{ JSON.stringify(result, null, 2) }}</pre></el-card></el-col>
    </el-row>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'
const secret = ref('')
const unlocked = ref(false)
const loading = ref(false)
const result = ref(null)
const unlock = () => { if (secret.value === 'fire-v12-demo') { unlocked.value = true; ElMessage.success('隐藏入口已解锁') } else ElMessage.error('口令不正确') }
const generate = async () => { loading.value=true; try { result.value = (await request.post('/api/internal/demo/closed-loop', { secret: secret.value })).data; ElMessage.success('演示闭环已生成') } finally { loading.value=false } }
const clearDemo = async () => { loading.value=true; try { result.value = (await request.post('/api/internal/demo/clear', { secret: secret.value })).data; ElMessage.success('演示数据已清理') } finally { loading.value=false } }
</script>
<style scoped>.card{margin-bottom:12px}.auth-card p{color:#64748b}pre{white-space:pre-wrap;background:#0f172a;color:#e5e7eb;padding:14px;border-radius:12px;max-height:500px;overflow:auto}</style>
