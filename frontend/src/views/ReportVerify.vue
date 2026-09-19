<template>
  <div class="verify-page">
    <el-card class="verify-card">
      <template #header>
        <div class="header-row"><strong>报告验真</strong><el-tag :type="result.valid ? 'success' : 'danger'">{{ result.valid ? '真实有效' : '未查到' }}</el-tag></div>
      </template>
      <el-skeleton v-if="loading" animated />
      <template v-else>
        <div v-if="result.valid" class="valid-box">
          <div class="seal">验真通过</div>
          <h2>{{ result.report_no }}</h2>
          <p>{{ result.message }}</p>
          <el-descriptions border :column="1">
            <el-descriptions-item label="档案编号">{{ result.record_id }}</el-descriptions-item>
            <el-descriptions-item label="巡检地点">{{ result.location }}</el-descriptions-item>
            <el-descriptions-item label="巡检时间">{{ result.created_at }}</el-descriptions-item>
            <el-descriptions-item label="风险等级">{{ result.risk_level }}</el-descriptions-item>
            <el-descriptions-item label="闭环状态">{{ result.closed_loop_status }}</el-descriptions-item>
            <el-descriptions-item label="报告摘要哈希">{{ result.report_hash }}</el-descriptions-item>
          </el-descriptions>
          <div class="btn-row"><el-button type="primary" @click="$router.push(`/report-print/${result.record_id}`)">查看报告</el-button><el-button @click="$router.push('/dashboard')">返回系统</el-button></div>
        </div>
        <el-result v-else icon="error" title="未查询到报告" :sub-title="result.message || '请核验报告编号或二维码来源。'">
          <template #extra><el-button @click="$router.push('/dashboard')">返回首页</el-button></template>
        </el-result>
      </template>
    </el-card>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import request from '../api'
const route = useRoute()
const loading = ref(false)
const result = ref({})
async function load(){ loading.value=true; try{ result.value=(await request.get(`/api/reports/verify/${route.params.reportNo}`)).data } finally{ loading.value=false } }
onMounted(load)
</script>
<style scoped>
.verify-page{min-height:100vh;background:linear-gradient(135deg,#eff6ff,#f8fafc);display:flex;align-items:center;justify-content:center;padding:24px}.verify-card{width:min(720px,100%)}.header-row{display:flex;justify-content:space-between;align-items:center}.valid-box{text-align:center}.seal{display:inline-flex;align-items:center;justify-content:center;width:108px;height:108px;border:4px solid #22c55e;border-radius:50%;color:#16a34a;font-weight:900;transform:rotate(-12deg);margin:10px auto 8px}.valid-box p{color:#64748b;line-height:1.8}.btn-row{margin-top:18px;display:flex;gap:10px;justify-content:center}
</style>
