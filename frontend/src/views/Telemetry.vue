
<template>
  <div>
    <div class="page-title">设备数据表</div>
    <el-card class="card">
      <el-button type="primary" @click="dialog=true">新增模拟数据</el-button>
      <el-table :data="rows" border style="margin-top:16px">
        <el-table-column prop="device_name" label="设备" />
        <el-table-column prop="temperature" label="温度" />
        <el-table-column prop="smoke" label="烟雾浓度" />
        <el-table-column prop="co" label="CO浓度" />
        <el-table-column prop="battery" label="电量" />
        <el-table-column label="在线">
          <template #default="{ row }"><el-tag :type="row.online ? 'success':'info'">{{ row.online ? '在线':'离线' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" />
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" title="新增模拟设备数据" width="520px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="设备"><el-select v-model="form.device_id" style="width:100%"><el-option v-for="d in devices" :key="d.id" :label="d.device_name" :value="d.id" /></el-select></el-form-item>
        <el-form-item label="温度"><el-input-number v-model="form.temperature" /></el-form-item>
        <el-form-item label="烟雾"><el-input-number v-model="form.smoke" :step="0.01" /></el-form-item>
        <el-form-item label="CO"><el-input-number v-model="form.co" :step="0.01" /></el-form-item>
        <el-form-item label="电量"><el-input-number v-model="form.battery" /></el-form-item>
        <el-form-item label="在线"><el-switch v-model="form.online" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, onMounted } from "vue"
import request from "../api"
const rows = ref([]), devices = ref([]), dialog = ref(false)
const form = ref({ device_id:null, temperature:26, smoke:0.02, co:0.01, battery:95, online:true })
const load = async () => {
  const [telemRes, devRes] = await Promise.all([
    request.get("/api/device-telemetry"),
    request.get("/api/devices")
  ])
  rows.value = telemRes.data?.items || telemRes.data || []
  devices.value = devRes.data?.items || devRes.data || []
}
const save = async () => { await request.post("/api/device-telemetry", form.value); dialog.value=false; load() }
onMounted(load)
</script>
