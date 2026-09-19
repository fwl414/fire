<template>
  <div class="internal-demo-page">
    <el-card class="gate-card" v-if="!verified">
      <template #header>隐藏演示闭环入口</template>
      <p class="muted">这个页面不出现在左侧菜单，只能手动输入地址访问：/internal/closed-loop-demo。</p>
      <el-input v-model="secret" placeholder="输入隐藏口令" show-password style="max-width:360px" @keyup.enter="verify" />
      <div class="actions"><el-button type="primary" @click="verify">进入演示控制台</el-button></div>
    </el-card>

    <template v-else>
      <div class="page-head">
        <div>
          <div class="page-title">隐藏演示闭环控制台</div>
          <p class="subtitle">用于答辩前快速生成多场景数据，不在正式业务菜单展示。</p>
        </div>
        <el-tag type="warning" effect="dark">内部入口</el-tag>
      </div>

      <el-row :gutter="14">
        <el-col :xs="24" :lg="9">
          <el-card class="card control-card">
            <template #header>演示操作</template>
            <p>一键生成演示数据，覆盖硬件报警、巡检、知识引用、整改工单和复查记录。</p>
            <el-button type="primary" size="large" :loading="loading" @click="seed">生成真实多场景演示闭环</el-button>
            <el-button size="large" type="danger" plain :loading="cleaning" @click="clear">清理 DEMO 演示数据</el-button>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="15">
          <el-card class="card">
            <template #header>多场景数据覆盖</template>
            <div class="scenario-grid">
              <div v-for="s in scenarios" :key="s.title" class="scenario-card" :class="s.tone">
                <strong>{{ s.title }}</strong>
                <p>{{ s.desc }}</p>
                <div><el-tag v-for="t in s.tags" :key="t" size="small">{{ t }}</el-tag></div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card v-if="result" class="card">
        <template #header>执行结果</template>
        <pre>{{ JSON.stringify(result, null, 2) }}</pre>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref } from "vue"
import request from "../api"
import { ElMessage, ElMessageBox } from "element-plus"

const secret = ref("")
const verified = ref(false)
const loading = ref(false)
const cleaning = ref(false)
const result = ref(null)
const scenarios = [
  { title: "机房烟感报警", desc: "烟雾异常 + 配电箱周边可燃物，生成高风险巡检与紧急工单。", tags: ["烟感", "高风险", "立即处置"], tone: "red" },
  { title: "实验室电气过载", desc: "插排串联、线路温升、纸箱靠近电源，形成整改中待办。", tags: ["电气", "整改中", "24小时"], tone: "orange" },
  { title: "走廊通道堵塞", desc: "摄像头识别通道堆物和设施遮挡，进入待派单。", tags: ["摄像头", "通道", "派单"], tone: "blue" },
  { title: "消防水压异常", desc: "消防水系统压力不足，生成待复查工单。", tags: ["水压", "待复查", "设施"], tone: "blue" },
  { title: "电动车违规充电", desc: "宿舍楼道违规充电样本，演示已闭环记录。", tags: ["电动车", "已闭环", "复查"], tone: "green" },
]

const verify = () => {
  if (secret.value === "fire-v12-demo") verified.value = true
  else ElMessage.warning("口令不正确")
}
const seed = async () => {
  loading.value = true
  try {
    result.value = (await request.post("/api/internal/demo/seed-realistic-closed-loop", { token: secret.value })).data
    ElMessage.success("多场景演示闭环已生成")
  } finally { loading.value = false }
}
const clear = async () => {
  await ElMessageBox.confirm("确认清理以 DEMO 开头的演示数据？不会清理普通业务数据。", "清理演示数据", { type: "warning" })
  cleaning.value = true
  try {
    result.value = (await request.post("/api/internal/demo/clear", { token: secret.value })).data
    ElMessage.success("演示数据已清理")
  } finally { cleaning.value = false }
}
</script>

<style scoped>
.page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; }
.subtitle, .muted { color:#64748b; line-height:1.7; }
.gate-card { max-width:620px; margin:10vh auto; }
.actions { margin-top:14px; }
.control-card p { color:#475569; line-height:1.8; }
.control-card :deep(.el-button) { margin:8px 8px 0 0; }
.scenario-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.scenario-card { border:1px solid #e2e8f0; border-radius:16px; padding:14px; background:#fff; }
.scenario-card strong { font-size:16px; }
.scenario-card p { color:#475569; line-height:1.7; min-height:48px; }
.scenario-card :deep(.el-tag) { margin:0 6px 6px 0; }
.scenario-card.red { border-top:4px solid #dc2626; background:#fff7f7; }
.scenario-card.orange { border-top:4px solid #f59e0b; background:#fffbeb; }
.scenario-card.blue { border-top:4px solid #2563eb; background:#eff6ff; }
.scenario-card.green { border-top:4px solid #16a34a; background:#f0fdf4; }
pre { background:#0f172a; color:#e5e7eb; border-radius:12px; padding:14px; max-height:360px; overflow:auto; }
@media (max-width: 800px) { .scenario-grid { grid-template-columns:1fr; } }
</style>
