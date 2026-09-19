<template>
  <h1 class="page-title">视觉 API 测试</h1>
  <div class="grid2">
    <div class="card">
      <h3>配置读取状态</h3>
      <el-button type="primary" @click="loadStatus">刷新配置状态</el-button>
      <el-descriptions :column="1" border style="margin-top:16px" v-if="status">
        <el-descriptions-item label="是否开启">{{ status.vision_enabled ? 'true' : 'false' }}</el-descriptions-item>
        <el-descriptions-item label="是否就绪">{{ status.ready ? 'ready' : 'not ready' }}</el-descriptions-item>
        <el-descriptions-item label="是否读取Key">{{ status.has_api_key ? '已读取' : '未读取' }}</el-descriptions-item>
        <el-descriptions-item label="Key预览">{{ status.api_key_preview || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Base URL">{{ status.base_url }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ status.model }}</el-descriptions-item>
      </el-descriptions>
    </div>
    <div class="card">
      <h3>上传图片真实调用测试</h3>
      <el-upload :auto-upload="false" :on-change="onFile" :limit="1">
        <el-button>选择图片</el-button>
      </el-upload>
      <el-button type="success" :loading="loading" @click="testApi" style="margin-top:12px">测试视觉模型</el-button>
      <p class="muted">该测试会直接调用 /api/system/vision-test，可判断智谱 API 是否真的可用。</p>
    </div>
  </div>
  <div class="card" v-if="result">
    <h3>测试结果</h3>
    <el-alert :type="result.ok ? 'success' : 'error'" :title="result.ok ? '调用成功' : '调用失败'" show-icon />
    <h4>模型输出</h4>
    <pre class="report">{{ result.raw_text || result.description || result.response_text || JSON.stringify(result, null, 2) }}</pre>
    <h4>完整响应</h4>
    <pre class="report">{{ JSON.stringify(result, null, 2) }}</pre>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
const status = ref(null)
const file = ref(null)
const result = ref(null)
const loading = ref(false)
const loadStatus = async()=>{ status.value = await api.visionStatus() }
const onFile = (f)=>{ file.value = f.raw }
const testApi = async()=>{
  if(!file.value) return ElMessage.warning('请先选择图片')
  loading.value = true
  try { result.value = await api.visionTest(file.value) } catch(e) { result.value = e.response?.data?.data || {ok:false, error:e.message}; ElMessage.error('调用失败') }
  finally { loading.value=false }
}
onMounted(loadStatus)
</script>
