<template>
  <div>
    <h1 class="page-title">巡检任务</h1>
    <div class="page-desc">创建巡检任务，智能巡检完成后自动更新状态。</div>
    <div class="toolbar"><el-button type="primary" @click="dialog=true">新建任务</el-button><el-button @click="load">刷新</el-button></div>
    <el-card class="card">
      <el-table :data="tasks" stripe>
        <el-table-column prop="title" label="任务名称" />
        <el-table-column prop="device_name" label="关联设备" />
        <el-table-column prop="assignee" label="负责人" width="120" />
        <el-table-column prop="deadline" label="截止时间" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
      </el-table>
    </el-card>
    <el-dialog v-model="dialog" title="新建巡检任务" width="560px">
      <el-form label-width="90px">
        <el-form-item label="任务名称"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="关联设备"><el-select v-model="form.device_id" style="width:100%"><el-option v-for="d in devices" :key="d.id" :label="d.device_name" :value="d.id" /></el-select></el-form-item>
        <el-form-item label="负责人"><el-input v-model="form.assignee" /></el-form-item>
        <el-form-item label="截止时间"><el-input v-model="form.deadline" placeholder="例如：2026-05-30" /></el-form-item>
        <el-form-item label="任务说明"><el-input type="textarea" v-model="form.description" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'
const tasks = ref([]), devices = ref([]), dialog = ref(false)
const form = ref({ title:'', device_id:null, assignee:'巡检员', deadline:'', description:'' })
const load = async () => {
  tasks.value = []
  const [tasksRes, devRes] = await Promise.all([
    request.get('/api/tasks').catch(() => ({ data: [] })),
    request.get('/api/devices')
  ])
  tasks.value = tasksRes.data?.items || tasksRes.data || []
  devices.value = devRes.data?.items || devRes.data || []
}
const save = async () => { await request.post('/api/tasks', form.value); ElMessage.success('创建成功'); dialog.value=false; form.value={ title:'', device_id:null, assignee:'巡检员', deadline:'', description:'' }; load() }
onMounted(load)
</script>
