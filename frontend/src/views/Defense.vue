<template>
  <div>
    <div class="page-title">项目展示</div>

    <el-alert
      title="本页面用于项目展示前的流程梳理，帮助你讲清楚系统功能：消防风险评估与应急辅助决策。"
      type="success"
      show-icon
      style="margin-bottom:16px"
    />

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="warning"
      show-icon
      style="margin-bottom:16px"
    />

    <el-card class="card" v-if="flow">
      <template #header>{{ flow.title }}</template>
      <p class="goal">{{ flow.goal }}</p>

      <el-timeline>
        <el-timeline-item
          v-for="item in flow.steps"
          :key="item.step"
          :timestamp="`步骤 ${item.step}`"
          placement="top"
        >
          <el-card>
            <h3>{{ item.name }}</h3>
            <p>{{ item.talk }}</p>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <el-card class="card">
      <template #header>答辩讲解重点</template>
      <el-descriptions border :column="1">
        <el-descriptions-item label="项目定位">
          基于Agent的智慧消防风险评估与应急辅助决策系统。
        </el-descriptions-item>
        <el-descriptions-item label="不是普通后台">
          系统核心不是 CRUD，而是 Agent 任务规划、工具调用、RAG 检索、多源融合、风险解释和应急决策。
        </el-descriptions-item>
        <el-descriptions-item label="创新点 1">
          面向消防巡检任务的智能模型 Agent 工作流。
        </el-descriptions-item>
        <el-descriptions-item label="创新点 2">
          规则识别、文本智能模型、视觉智能模型的多源隐患融合。
        </el-descriptions-item>
        <el-descriptions-item label="创新点 3">
          结合消防知识库的 RAG 检索增强机制。
        </el-descriptions-item>
        <el-descriptions-item label="创新点 4">
          可解释风险评分和分级应急辅助决策。
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import request from "../api"

const fallbackFlow = {
  title: "项目展示流程",
  goal: "展示系统功能，包括任务调度、工具调用、知识检索、风险评估和应急辅助决策。",
  steps: [
    { step: 1, name: "首页仪表盘", talk: "展示系统整体数据概览，说明系统具备设备、巡检、隐患、工单闭环等基础业务能力。" },
    { step: 2, name: "智能巡检", talk: "选择实验室综合高风险案例，输入现场描述并上传图片，启动分析。" },
    { step: 3, name: "一页看懂", talk: "展示风险等级、风险评分、主要隐患和立即处置建议，让普通用户先理解结论。" },
    { step: 4, name: "识别来源", talk: "展示规则识别、文本智能模型、视觉智能模型和最终融合结果，证明系统不是单一规则系统。" },
    { step: 5, name: "风险解释", talk: "展示每项隐患的风险分值、判断原因和处置措施，说明风险评分具备可解释性。" },
    { step: 6, name: "知识依据", talk: "展示 RAG 检索到的消防知识条目、来源文件和匹配关键词，说明建议不是凭空生成。" },
    { step: 7, name: "Agent技术细节", talk: "展示 Agent 任务规划和工具调用记录，突出方向一“智能模型与智能体系统”的核心。" },
    { step: 8, name: "实验评估", talk: "展示规则基线测试样例、Precision、Recall、F1，为论文实验部分提供数据支撑。" }
  ]
}

const flow = ref(fallbackFlow)
const loadError = ref("")

const load = async () => {
  try {
    const res = await request.get("/api/defense/demo-flow")
    flow.value = res.data
    loadError.value = ""
  } catch (e) {
    flow.value = fallbackFlow
    loadError.value = "当前显示内置演示流程。"
  }
}

onMounted(load)
</script>

<style scoped>
.goal {
  line-height: 1.8;
  color: #374151;
  background: #f8fafc;
  padding: 14px;
  border-radius: 10px;
}
h3 {
  margin-top: 0;
}
</style>
