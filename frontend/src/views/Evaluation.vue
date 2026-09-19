<template>
  <div>
    <div class="page-title">实验评估</div>

    <el-alert
      title="项目展示 增强评估：对比规则识别、模拟智能模型识别和融合识别效果，用于论文实验与答辩展示。"
      type="success"
      show-icon
      style="margin-bottom:16px"
    />

    <el-card class="card">
      <template #header>
        <div class="header-row">
          <strong>融合识别评估</strong>
          <div>
            <el-button type="primary" :loading="loading" @click="loadEnhanced">运行增强评估</el-button>
            <el-button :loading="baselineLoading" @click="loadBaseline">规则基线</el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="error" :title="error" type="warning" show-icon style="margin-bottom:16px" />

      <el-row v-if="enhanced" :gutter="16">
        <el-col :span="6"><div class="metric"><span>测试样例</span><strong>{{ enhanced.case_count }}</strong></div></el-col>
        <el-col :span="6"><div class="metric"><span>规则 F1</span><strong>{{ enhanced.summary.avg_rule_f1 }}</strong></div></el-col>
        <el-col :span="6"><div class="metric"><span>智能模型 F1</span><strong>{{ enhanced.summary.avg_llm_f1 }}</strong></div></el-col>
        <el-col :span="6"><div class="metric"><span>融合 F1</span><strong>{{ enhanced.summary.avg_fusion_f1 }}</strong></div></el-col>
      </el-row>

      <el-alert v-if="enhanced" :title="enhanced.conclusion" type="info" show-icon style="margin:16px 0" />

      <el-table v-if="enhanced" :data="enhanced.rows" border>
        <el-table-column prop="scene" label="测试场景" width="150" />
        <el-table-column prop="description" label="场景描述" min-width="240" />
        <el-table-column label="期望隐患" width="220">
          <template #default="{ row }">{{ (row.expected || []).join("、") }}</template>
        </el-table-column>
        <el-table-column label="规则识别" width="220">
          <template #default="{ row }">{{ (row.rule_prediction || []).join("、") || "无" }}</template>
        </el-table-column>
        <el-table-column label="智能模型识别" width="220">
          <template #default="{ row }">{{ (row.llm_prediction || []).join("、") || "无" }}</template>
        </el-table-column>
        <el-table-column label="融合识别" width="220">
          <template #default="{ row }">{{ (row.fusion_prediction || []).join("、") || "无" }}</template>
        </el-table-column>
        <el-table-column prop="rule_f1" label="规则F1" width="90" />
        <el-table-column prop="llm_f1" label="模型F1" width="90" />
        <el-table-column prop="fusion_f1" label="融合F1" width="90" />
        <el-table-column prop="risk_level" label="风险等级" width="110" />
      </el-table>
    </el-card>

    <el-card v-if="baseline" class="card">
      <template #header>规则基线评估</template>
      <el-row :gutter="16">
        <el-col :span="6"><div class="metric"><span>测试样例</span><strong>{{ baseline.case_count }}</strong></div></el-col>
        <el-col :span="6"><div class="metric"><span>Precision</span><strong>{{ baseline.avg_precision }}</strong></div></el-col>
        <el-col :span="6"><div class="metric"><span>Recall</span><strong>{{ baseline.avg_recall }}</strong></div></el-col>
        <el-col :span="6"><div class="metric"><span>F1</span><strong>{{ baseline.avg_f1 }}</strong></div></el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import request from "../api"

const enhanced = ref(null)
const baseline = ref(null)
const loading = ref(false)
const baselineLoading = ref(false)
const error = ref("")

const loadEnhanced = async () => {
  loading.value = true
  error.value = ""
  try {
    enhanced.value = (await request.get("/api/evaluation/enhanced")).data
  } catch (e) {
    error.value = "实验评估暂时不可用，请稍后重试。"
  } finally {
    loading.value = false
  }
}

const loadBaseline = async () => {
  baselineLoading.value = true
  try {
    baseline.value = (await request.get("/api/evaluation/rule-baseline")).data
  } finally {
    baselineLoading.value = false
  }
}

onMounted(loadEnhanced)
</script>

<style scoped>
.header-row {
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.metric {
  background:#f8fafc;
  border:1px solid #e2e8f0;
  border-radius:10px;
  padding:12px;
  text-align:center;
}
.metric span {
  color:#64748b;
}
.metric strong {
  display:block;
  font-size:24px;
  color:#2563eb;
  margin-top:4px;
}
</style>
