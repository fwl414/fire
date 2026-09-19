<template>
  <div>
    <h1 class="page-title">消防问答</h1>
    <div class="page-desc">基于消防知识库的应急辅助问答。</div>
    <el-card class="card">
      <el-input v-model="question" type="textarea" rows="4" placeholder="例如：电气火灾可以直接用水扑灭吗？" />
      <el-button type="primary" :loading="loading" style="margin-top:14px" @click="ask">提交问题</el-button>
      <div v-if="answer" class="report-box" style="margin-top:18px">{{ answer }}</div>
    </el-card>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'
const question=ref('电气火灾可以直接用水扑灭吗？'), answer=ref(''), loading=ref(false)
const ask=async()=>{ if(!question.value) return ElMessage.warning('请输入问题'); loading.value=true; try{ const res=await request.post('/api/qa/fire',{question:question.value}); answer.value=res.data.answer } finally{ loading.value=false } }
</script>
