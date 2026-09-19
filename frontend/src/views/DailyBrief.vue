<template>
  <div class="daily-brief-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">每日安全简报</h2>
        <p class="page-desc">自动生成每日消防安全简报，一览全局态势</p>
      </div>
      <div class="header-actions">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          :max-date="new Date()"
          @change="loadBriefData"
        />
        <el-button type="primary" :loading="loading" @click="loadBriefData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="exportBrief">
          <el-icon><Download /></el-icon>
          导出简报
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="brief-content">
      <div v-if="briefData" class="brief-main">
        <div class="brief-header-card">
          <div class="brief-date">{{ briefData.date }}</div>
          <div class="brief-summary">
            <el-icon :size="24"><Document /></el-icon>
            <div class="summary-text">{{ briefData.summary }}</div>
          </div>
          <div class="generated-info">
            <el-tag type="info" effect="plain">
              自动生成 · {{ briefData.generated_at }}
            </el-tag>
          </div>
        </div>

        <div class="highlight-section">
          <div class="section-title">关键要点</div>
          <div class="highlight-cards">
            <div 
              v-for="(h, idx) in briefData.key_highlights" 
              :key="idx" 
              class="highlight-card"
              :class="h.type"
            >
              <div class="highlight-icon">
                <el-icon v-if="h.type === 'danger'"><WarningFilled /></el-icon>
                <el-icon v-else-if="h.type === 'warning'"><Warning /></el-icon>
                <el-icon v-else><CircleCheckFilled /></el-icon>
              </div>
              <div class="highlight-content">{{ h.content }}</div>
            </div>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :span="12">
            <div class="data-card">
              <div class="card-title">
                <el-icon><Bell /></el-icon>
                告警统计
              </div>
              <div class="stat-grid">
                <div class="stat-item">
                  <div class="stat-num total">{{ briefData.alert_stats?.total || 0 }}</div>
                  <div class="stat-label">告警总数</div>
                </div>
                <div class="stat-item">
                  <div class="stat-num critical">{{ briefData.alert_stats?.critical || 0 }}</div>
                  <div class="stat-label">严重告警</div>
                </div>
                <div class="stat-item">
                  <div class="stat-num high">{{ briefData.alert_stats?.high || 0 }}</div>
                  <div class="stat-label">高级告警</div>
                </div>
                <div class="stat-item">
                  <div class="stat-num medium">{{ briefData.alert_stats?.medium || 0 }}</div>
                  <div class="stat-label">中级告警</div>
                </div>
              </div>
              <div class="stat-row">
                <div class="stat-row-item">
                  <span class="label">已处置</span>
                  <span class="value success">{{ briefData.alert_stats?.resolved || 0 }} 起</span>
                </div>
                <div class="stat-row-item">
                  <span class="label">处置率</span>
                  <span class="value primary">
                    {{ (briefData.alert_stats?.total || 0) > 0 ? ((briefData.alert_stats?.resolved || 0) / briefData.alert_stats.total * 100).toFixed(1) : 0 }}%
                  </span>
                </div>
                <div class="stat-row-item">
                  <span class="label">待处理</span>
                  <span class="value warning">{{ briefData.alert_stats?.pending || 0 }} 起</span>
                </div>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="data-card">
              <div class="card-title">
                <el-icon><Search /></el-icon>
                巡检统计
              </div>
              <div class="inspection-stats">
                <div class="inspection-main">
                  <div class="inspection-num">{{ briefData.inspection_stats?.inspection_count || 0 }}</div>
                  <div class="inspection-label">巡检次数</div>
                </div>
                <div class="inspection-divider"></div>
                <div class="inspection-main">
                  <div class="inspection-num warning">{{ briefData.inspection_stats?.hazard_found || 0 }}</div>
                  <div class="inspection-label">发现隐患</div>
                </div>
              </div>
              <div class="inspection-progress">
                <div class="progress-label">隐患发现率</div>
                <el-progress 
                  :percentage="(briefData.inspection_stats?.inspection_count || 0) > 0 
                    ? Math.round(briefData.inspection_stats?.hazard_found / briefData.inspection_stats.inspection_count * 100) 
                    : 0" 
                  :stroke-width="12"
                  status="warning"
                />
              </div>
            </div>
          </el-col>
        </el-row>

        <div class="data-card">
          <div class="card-title">
            <el-icon><TrendCharts /></el-icon>
            近7日告警趋势
          </div>
          <div class="trend-chart">
            <div class="trend-bars">
              <div v-for="(item, idx) in briefData.alarm_trend || []" :key="idx" class="trend-bar-item">
                <div class="bar-wrapper">
                  <div 
                    class="bar-fill"
                    :style="{ height: `${((item.count || 0) / maxTrendCount) * 100}%` }"
                  >
                    <div class="bar-count">{{ item.count || 0 }}</div>
                  </div>
                </div>
                <div class="bar-label">{{ item.date || '未知' }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="data-card focus-card">
          <div class="card-title">
            <el-icon><Position /></el-icon>
            今日重点关注区域
          </div>
          <div class="focus-list">
            <div 
              v-for="(item, idx) in briefData.today_focus || []" 
              :key="idx" 
              class="focus-item"
              :class="item.level || 'normal'"
            >
              <div class="focus-rank">{{ idx + 1 }}</div>
              <div class="focus-info">
                <div class="focus-area">{{ item.area || '未知区域' }}</div>
                <div class="focus-reason">{{ item.reason || '暂无特殊原因' }}</div>
              </div>
              <el-tag 
                size="small" 
                :type="(item.level === 'high' ? 'danger' : item.level === 'medium' ? 'warning' : 'success') || 'info'"
                effect="light"
              >
                {{ item.level === 'high' ? '高关注' : item.level === 'medium' ? '中关注' : '常规' }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <el-empty v-else description="暂无简报数据" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Download, Document, WarningFilled, Warning,
  CircleCheckFilled, Bell, Search, TrendCharts, Position
} from '@element-plus/icons-vue'
import { getDailyBrief } from '@/api/intelligence'

const loading = ref(false)
const selectedDate = ref(null)
const briefData = ref(null)

const maxTrendCount = computed(() => {
  if (!briefData.value?.alarm_trend?.length) return 10
  return Math.max(...briefData.value.alarm_trend.map(t => t.count), 10)
})

async function loadBriefData() {
  loading.value = true
  try {
    const res = await getDailyBrief(selectedDate.value)
    // 接口的外层信封是 { ok, data }：以前这里只取到 res.data（信封本身），
    // 于是 date/summary 全是 undefined、各统计项被下面那段「补默认值」悄悄补成 0，
    // 页面看起来正常，其实一直显示全 0。
    briefData.value = res.data?.data || null
    if (!briefData.value) {
      ElMessage.error('简报数据为空')
    }
  } catch (e) {
    // 接口失败就如实显示失败，不再塞一份「系统运行状态良好」的假简报
    console.error('加载简报失败:', e)
    ElMessage.error('加载简报失败')
    briefData.value = null
  } finally {
    loading.value = false
  }
}

function exportBrief() {
  if (!briefData.value) {
    ElMessage.warning('暂无简报数据可导出')
    return
  }
  
  let content = `消防安全每日简报\n`
  content += `日期：${briefData.value.date || new Date().toISOString().split('T')[0]}\n`
  content += `生成时间：${briefData.value.generated_at || new Date().toLocaleString()}\n`
  content += '='.repeat(50) + '\n\n'
  content += `一、总体概况\n${briefData.value.summary || '今日系统运行正常，各项指标均在正常范围内。'}\n\n`
  
  content += `二、关键要点\n`
  (briefData.value.key_highlights || []).forEach((h, i) => {
    content += `${i + 1}. ${h.content || '无特殊要点'}\n`
  })
  content += '\n'
  
  content += `三、告警统计\n`
  content += `  告警总数：${briefData.value.alert_stats?.total || 0} 起\n`
  content += `  严重告警：${briefData.value.alert_stats?.critical || 0} 起\n`
  content += `  高级告警：${briefData.value.alert_stats?.high || 0} 起\n`
  content += `  中级告警：${briefData.value.alert_stats?.medium || 0} 起\n`
  content += `  低级告警：${briefData.value.alert_stats?.low || 0} 起\n`
  content += `  已处置：${briefData.value.alert_stats?.resolved || 0} 起\n`
  content += `  待处理：${briefData.value.alert_stats?.pending || 0} 起\n\n`
  
  content += `四、今日重点关注\n`
  (briefData.value.today_focus || []).forEach((f, i) => {
    content += `${i + 1}. ${f.area || '未知区域'} - ${f.reason || '暂无特殊原因'}\n`
  })
  
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `消防安全简报_${briefData.value.date || new Date().toISOString().split('T')[0]}.txt`
  link.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('简报导出成功')
}

onMounted(() => {
  loadBriefData()
})
</script>

<style scoped>
.daily-brief-page {
  padding: 20px;
  min-height: 100%;
  background: #f5f7fb;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-title {
  font-size: 24px;
  font-weight: 800;
  margin: 0 0 6px;
  color: #0f172a;
}
.page-desc {
  color: #64748b;
  margin: 0;
  font-size: 14px;
}
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.brief-content {
  max-width: 1000px;
  margin: 0 auto;
}

.brief-header-card {
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  color: white;
  border-radius: 16px;
  padding: 28px 32px;
  margin-bottom: 20px;
}
.brief-date {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 16px;
}
.brief-summary {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.brief-summary .el-icon {
  margin-top: 2px;
  flex-shrink: 0;
  opacity: 0.9;
}
.summary-text {
  font-size: 14px;
  line-height: 1.8;
  opacity: 0.95;
}
.generated-info {
  text-align: right;
}
.generated-info .el-tag {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: white;
}

.highlight-section {
  margin-bottom: 20px;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.highlight-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}
.highlight-card {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.highlight-card.danger {
  border-left: 4px solid #ef4444;
}
.highlight-card.warning {
  border-left: 4px solid #f59e0b;
}
.highlight-card.success {
  border-left: 4px solid #22c55e;
}
.highlight-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.highlight-card.danger .highlight-icon {
  background: #fef2f2;
  color: #dc2626;
}
.highlight-card.warning .highlight-icon {
  background: #fffbeb;
  color: #d97706;
}
.highlight-card.success .highlight-icon {
  background: #f0fdf4;
  color: #16a34a;
}
.highlight-content {
  font-size: 14px;
  color: #334155;
  line-height: 1.6;
}

.data-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 16px;
}
.card-title .el-icon {
  color: #3b82f6;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-item {
  text-align: center;
  padding: 12px 8px;
  background: #f8fafc;
  border-radius: 8px;
}
.stat-num {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 4px;
}
.stat-num.total { color: #0f172a; }
.stat-num.critical { color: #dc2626; }
.stat-num.high { color: #ea580c; }
.stat-num.medium { color: #ca8a04; }
.stat-label {
  font-size: 12px;
  color: #64748b;
}

.stat-row {
  display: flex;
  justify-content: space-around;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}
.stat-row-item {
  text-align: center;
}
.stat-row-item .label {
  font-size: 12px;
  color: #94a3b8;
  margin-right: 8px;
}
.stat-row-item .value {
  font-size: 14px;
  font-weight: 600;
}
.value.success { color: #16a34a; }
.value.primary { color: #2563eb; }
.value.warning { color: #d97706; }

.inspection-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  margin-bottom: 20px;
}
.inspection-main {
  text-align: center;
}
.inspection-num {
  font-size: 36px;
  font-weight: 700;
  color: #2563eb;
  line-height: 1;
  margin-bottom: 6px;
}
.inspection-num.warning {
  color: #f59e0b;
}
.inspection-label {
  font-size: 13px;
  color: #64748b;
}
.inspection-divider {
  width: 1px;
  height: 50px;
  background: #e2e8f0;
}

.trend-chart {
  padding: 20px 10px 0;
}
.trend-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 180px;
  gap: 8px;
}
.trend-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.bar-wrapper {
  flex: 1;
  width: 100%;
  max-width: 36px;
  display: flex;
  align-items: flex-end;
}
.bar-fill {
  width: 100%;
  background: linear-gradient(180deg, #3b82f6, #93c5fd);
  border-radius: 4px 4px 0 0;
  position: relative;
  min-height: 4px;
  transition: height 0.5s ease;
}
.bar-count {
  position: absolute;
  top: -20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
  white-space: nowrap;
}
.bar-label {
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
}

.focus-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.focus-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  background: #f8fafc;
  border-left: 4px solid #94a3b8;
}
.focus-item.high {
  border-left-color: #ef4444;
  background: #fef2f2;
}
.focus-item.medium {
  border-left-color: #f59e0b;
  background: #fffbeb;
}
.focus-rank {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #475569;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.focus-item.high .focus-rank {
  background: #ef4444;
  color: white;
}
.focus-item.medium .focus-rank {
  background: #f59e0b;
  color: white;
}
.focus-info {
  flex: 1;
}
.focus-area {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}
.focus-reason {
  font-size: 12px;
  color: #64748b;
}
</style>
