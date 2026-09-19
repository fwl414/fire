<template>
  <div>
    <div class="page-title">系统能力说明</div>

    <el-alert
      title="本页用于说明系统能力、技术路线和智能分析流程。"
      type="success"
      show-icon
      style="margin-bottom:12px"
    />

    <el-card class="card hero-card">
      <h2>{{ overview.project_name }}</h2>
      <p class="one-sentence">{{ overview.one_sentence }}</p>
      <el-row :gutter="12">
        <el-col :span="8">
          <div class="hero-item">
            <span>竞赛方向</span>
            <strong>{{ overview.competition_track }}</strong>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="hero-item">
            <span>系统定位</span>
            <strong>智能模型 Agent 软件系统</strong>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="hero-item">
            <span>当前系统</span>
            <strong>{{ overview.version }}</strong>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="项目定位" name="overview">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-card class="card">
              <template #header>核心价值</template>
              <el-timeline>
                <el-timeline-item v-for="v in overview.core_value || []" :key="v">{{ v }}</el-timeline-item>
              </el-timeline>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card class="card">
              <template #header>避免方向跑偏</template>
              <el-alert
                v-for="v in overview.not_positioning || []"
                :key="v"
                :title="v"
                type="warning"
                show-icon
                style="margin-bottom:8px"
              />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="技术路线" name="route">
        <el-card class="card">
          <template #header>Agent 技术流程</template>
          <el-steps :active="route.pipeline?.length || 0" finish-status="success" align-center>
            <el-step v-for="s in route.pipeline || []" :key="s.step" :title="s.name" />
          </el-steps>
          <el-table :data="route.pipeline || []" border style="margin-top:18px">
            <el-table-column prop="step" label="步骤" width="80" />
            <el-table-column prop="name" label="环节" width="180" />
            <el-table-column prop="description" label="说明" />
          </el-table>
        </el-card>

        <el-card class="card">
          <template #header>系统分层架构</template>
          <el-row :gutter="12">
            <el-col :span="8" v-for="layer in route.architecture_layers || []" :key="layer.layer">
              <div class="layer-card">
                <h3>{{ layer.layer }}</h3>
                <el-tag v-for="item in layer.items" :key="item" style="margin:0 6px 6px 0">{{ item }}</el-tag>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="创新点" name="innovation">
        <el-row :gutter="12">
          <el-col :span="8" v-for="item in innovations" :key="item.title">
            <el-card class="innovation-card">
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
              <div>
                <el-tag v-for="e in item.evidence" :key="e" type="success" style="margin:0 6px 6px 0">{{ e }}</el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="演示脚本" name="demo">
        <el-card class="card">
          <template #header>系统演示流程</template>
          <el-timeline>
            <el-timeline-item v-for="item in demoScript" :key="item.order" :timestamp="`第 ${item.order} 步：${item.page}`" placement="top">
              <h3>{{ item.title }}</h3>
              <ul>
                <li v-for="p in item.talking_points" :key="p">{{ p }}</li>
              </ul>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="Agent评估" name="eval">
        <el-card class="card">
          <template #header>{{ agentEval.title }}</template>
          <el-alert :title="agentEval.conclusion" type="info" show-icon style="margin-bottom:12px" />
          <el-table :data="agentEval.rows || []" border>
            <el-table-column prop="capability" label="能力" width="140" />
            <el-table-column prop="baseline" label="传统做法" />
            <el-table-column prop="agent" label="系统做法" />
            <el-table-column prop="value" label="价值" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="技术材料" name="paper">
        <el-card class="card">
          <template #header>论文摘要</template>
          <p class="paper-text">{{ paper.abstract }}</p>
          <h3>关键词</h3>
          <el-tag v-for="k in paper.keywords || []" :key="k" style="margin:0 6px 6px 0">{{ k }}</el-tag>
        </el-card>

        <el-card class="card">
          <template #header>论文大纲</template>
          <el-timeline>
            <el-timeline-item v-for="(item, index) in paper.outline || []" :key="item" :timestamp="`${index + 1}`">{{ item }}</el-timeline-item>
          </el-timeline>
        </el-card>

        <el-card class="card">
          <template #header>创新点摘要</template>
          <ul>
            <li v-for="item in paper.innovation_summary || []" :key="item">{{ item }}</li>
          </ul>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import request from "../api"

const activeTab = ref("overview")
const overview = ref({})
const route = ref({})
const innovations = ref([])
const demoScript = ref([])
const agentEval = ref({})
const paper = ref({})

const load = async () => {
  overview.value = (await request.get("/api/competition/overview")).data
  route.value = (await request.get("/api/competition/technical-route")).data
  innovations.value = (await request.get("/api/competition/innovations")).data
  demoScript.value = (await request.get("/api/competition/demo-script")).data
  agentEval.value = (await request.get("/api/competition/agent-evaluation")).data
  paper.value = (await request.get("/api/competition/paper-materials")).data
}

onMounted(load)
</script>

<style scoped>
.hero-card {
  background: linear-gradient(135deg, #eff6ff, #ffffff);
}
.hero-card h2 {
  margin:0 0 8px;
  font-size:26px;
}
.one-sentence {
  color:#475569;
  line-height:1.8;
  font-size:16px;
}
.hero-item {
  border:1px solid #dbeafe;
  border-radius:12px;
  padding:14px;
  background:#fff;
}
.hero-item span {
  color:#64748b;
}
.hero-item strong {
  display:block;
  margin-top:8px;
  font-size:18px;
  color:#2563eb;
}
.layer-card,
.innovation-card {
  border:1px solid #e2e8f0;
  border-radius:12px;
  padding:14px;
  min-height:180px;
  margin-bottom:12px;
  background:#fff;
}
.innovation-card p,
.paper-text {
  color:#475569;
  line-height:1.8;
}
</style>
