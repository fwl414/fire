
<template>
  <div>
    <div class="page-title">故障闭环</div>
    <el-card>
      <el-table :data="rows" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="risk_level" label="风险等级" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button size="small" @click="setStatus(row, '待受理')">待受理</el-button>
            <el-button size="small" type="warning" @click="setStatus(row, '处理中')">处理中</el-button>
            <el-button size="small" type="success" @click="setStatus(row, '已完成')">已完成</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
<script setup>
import { ref, onMounted } from "vue"
import request from "../api"
const rows = ref([])
const load = async () => rows.value = (await request.get("/api/faults")).data
const setStatus = async (row, status) => { const fd = new FormData(); fd.append("status", status); await request.put(`/api/faults/${row.id}/status`, fd); load() }
onMounted(load)
</script>
