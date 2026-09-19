<template>
  <div class="ai-assistant-float">
    <div v-if="!expanded" class="float-btn" @click="toggleExpand">
      <el-icon :size="28"><ChatDotRound /></el-icon>
      <div class="float-badge" v-if="unreadCount > 0">{{ unreadCount > 99 ? '99+' : unreadCount }}</div>
    </div>

    <el-drawer
      v-model="expanded"
      direction="rtl"
      size="440px"
      :with-header="false"
      class="smart-assistant-drawer"
    >
      <div class="assistant-container">
        <div class="assistant-header">
          <div class="header-left">
            <div class="assistant-avatar">
              <el-icon :size="22"><ChatDotRound /></el-icon>
            </div>
            <div>
              <div class="assistant-title">智能助手</div>
              <div class="assistant-subtitle">智能问答 · 数据查询 · 业务辅助</div>
            </div>
          </div>
          <el-button text @click="toggleExpand">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>

        <div class="quick-actions">
          <div class="quick-title">数据查询</div>
          <div class="quick-grid">
            <div class="quick-item" @click="handleQuickAction('alert_today')">
              <el-icon><Bell /></el-icon>
              <span>今日告警</span>
            </div>
            <div class="quick-item" @click="handleQuickAction('device_online')">
              <el-icon><Monitor /></el-icon>
              <span>设备在线</span>
            </div>
            <div class="quick-item" @click="handleQuickAction('hazard')">
              <el-icon><Warning /></el-icon>
              <span>隐患统计</span>
            </div>
            <div class="quick-item" @click="handleQuickAction('daily_brief')">
              <el-icon><Document /></el-icon>
              <span>每日简报</span>
            </div>
          </div>
          <div class="quick-title mt16">智能分析</div>
          <div class="quick-grid">
            <div class="quick-item smart-item" @click="handleQuickAction('alert_analyze')">
              <el-icon><DataAnalysis /></el-icon>
              <span>告警分析</span>
            </div>
            <div class="quick-item ai-item" @click="handleQuickAction('inspection_risk')">
              <el-icon><Search /></el-icon>
              <span>巡检研判</span>
            </div>
            <div class="quick-item ai-item" @click="handleQuickAction('rectification')">
              <el-icon><Tools /></el-icon>
              <span>整改方案</span>
            </div>
            <div class="quick-item ai-item" @click="handleQuickAction('device_diagnose')">
              <el-icon><MagicStick /></el-icon>
              <span>设备诊断</span>
            </div>
          </div>
        </div>

        <div class="chat-area" ref="chatAreaRef">
          <div v-for="(msg, idx) in messages" :key="idx" class="msg-item" :class="msg.role">
            <div v-if="msg.role === 'assistant'" class="msg-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="msg-bubble">
              <div v-if="msg.type === 'typing'" class="typing-dots">
                <span></span><span></span><span></span>
              </div>
              <div v-else class="msg-content">
                <p>{{ msg.content }}</p>
                <div v-if="msg.chartType" class="msg-chart-mini">
                  <el-tag size="small" type="info">图表数据</el-tag>
                </div>
                <div v-if="msg.relatedQuestions && msg.relatedQuestions.length" class="related-questions">
                  <div class="related-title">相关问题：</div>
                  <div class="related-list">
                    <el-tag
                      v-for="(q, qi) in msg.relatedQuestions"
                      :key="qi"
                      size="small"
                      effect="plain"
                      class="related-tag"
                      @click="sendQuestion(q)"
                    >
                      {{ q }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="msg.role === 'user'" class="msg-avatar user">
              <el-icon><User /></el-icon>
            </div>
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入问题，如：今日告警有多少？哪个区域风险最高？"
            @keydown.enter.ctrl="handleSend"
            resize="none"
          />
          <div class="input-actions">
            <span class="input-hint">Ctrl+Enter 发送</span>
            <el-button type="primary" :loading="sending" @click="handleSend">
              发送
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound, Close, Bell, Monitor, Warning, Document,
  User, Promotion, MagicStick, Search, Tools, DataAnalysis
} from '@element-plus/icons-vue'
import { queryData, getDailyBrief } from '@/api/intelligence'

const expanded = ref(false)
const unreadCount = ref(0)
const inputText = ref('')
const sending = ref(false)
const chatAreaRef = ref(null)

const messages = ref([
  {
    role: 'assistant',
    content: '您好！我是消防智能助手，我可以帮您：\n• 查询告警、设备、隐患等数据\n• 分析风险和提供处置建议\n• 生成每日安全简报\n\n请直接输入您的问题，或点击上方快捷功能。',
    type: 'text',
  },
])

function toggleExpand() {
  expanded.value = !expanded.value
  if (expanded.value) {
    unreadCount.value = 0
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatAreaRef.value) {
      chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
    }
  })
}

async function sendQuestion(question) {
  inputText.value = question
  await handleSend()
}

async function handleQuickAction(action) {
  const questionMap = {
    alert_today: '今日告警有多少？',
    device_online: '设备在线率是多少？',
    hazard: '当前有多少隐患？',
    alert_analyze: '请分析一下当前告警情况',
    inspection_risk: '如何进行巡检风险研判？',
    rectification: '如何生成整改方案？',
    device_diagnose: '设备故障怎么诊断？',
  }
  
  if (action === 'daily_brief') {
    await loadDailyBrief()
    return
  }
  
  const question = questionMap[action]
  if (question) {
    inputText.value = question
    await handleSend()
  }
}

async function loadDailyBrief() {
  messages.value.push({
    role: 'user',
    content: '生成今日安全简报',
    type: 'text',
  })
  scrollToBottom()
  
  messages.value.push({
    role: 'assistant',
    type: 'typing',
  })
  scrollToBottom()
  
  try {
    sending.value = true
    const res = await getDailyBrief()
    // 简报接口外层是 { ok, data }
    const data = res.data?.data || {}
    
    const briefMsg = {
      role: 'assistant',
      type: 'text',
      content: data.summary,
      data: data,
    }
    
    messages.value.pop()
    messages.value.push(briefMsg)
    
    if (data.key_highlights && data.key_highlights.length) {
      messages.value.push({
        role: 'assistant',
        type: 'text',
        content: '关键要点：\n' + data.key_highlights.map((h, i) => `${i+1}. ${h.content}`).join('\n'),
      })
    }
    
    if (data.today_focus && data.today_focus.length) {
      messages.value.push({
        role: 'assistant',
        type: 'text',
        content: '今日重点关注区域：\n' + data.today_focus.map((f, i) => `${i+1}. ${f.area} — ${f.reason}`).join('\n'),
      })
    }
    
  } catch (e) {
    messages.value.pop()
    messages.value.push({
      role: 'assistant',
      content: '抱歉，生成简报时出现错误，请稍后重试。',
      type: 'text',
    })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  if (sending.value) return
  
  messages.value.push({
    role: 'user',
    content: text,
    type: 'text',
  })
  inputText.value = ''
  scrollToBottom()
  
  messages.value.push({
    role: 'assistant',
    type: 'typing',
  })
  scrollToBottom()
  
  try {
    sending.value = true
    // 这里以前调用的是 queryAIData —— 一个并不存在的函数，每次提问都会走到 catch
    // 显示「暂时无法回答」。正确入口是导入的 queryData（/api/intelligence/query-data）。
    const res = await queryData(text)
    const data = res.data?.data || {}
    
    messages.value.pop()
    messages.value.push({
      role: 'assistant',
      content: data.answer_text,
      type: 'text',
      chartType: data.chart_type,
      relatedQuestions: data.related_questions,
      data: data.result_data,
    })
    
  } catch (e) {
    messages.value.pop()
    messages.value.push({
      role: 'assistant',
      content: '抱歉，我暂时无法回答这个问题，请稍后重试。',
      type: 'text',
    })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

defineExpose({
  toggleExpand,
  sendQuestion,
})
</script>

<style scoped>
.smart-assistant-float {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2000;
}

.float-btn {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.4);
  transition: all 0.3s ease;
  position: relative;
}

.float-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 12px 32px rgba(59, 130, 246, 0.5);
}

.float-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  background: #ef4444;
  color: white;
  border-radius: 10px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  border: 2px solid white;
}

.ai-assistant-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.assistant-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.assistant-header {
  padding: 16px 20px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.assistant-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.assistant-title {
  font-size: 16px;
  font-weight: 600;
}

.assistant-subtitle {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 2px;
}

.assistant-header .el-button {
  color: white;
}

.quick-actions {
  padding: 12px 16px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
}

.quick-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  color: #475569;
  font-size: 12px;
}

.quick-item:hover {
  background: #eff6ff;
  color: #2563eb;
}

.quick-item .el-icon {
  font-size: 20px;
}

.mt16 {
  margin-top: 14px;
}

.quick-item.ai-item {
  background: linear-gradient(135deg, #f0f9ff, #ecfeff);
  color: #0369a1;
}
.quick-item.ai-item:hover {
  background: linear-gradient(135deg, #e0f2fe, #cffafe);
  color: #0284c7;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.msg-item {
  display: flex;
  gap: 10px;
  max-width: 85%;
}

.msg-item.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #dbeafe;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.msg-avatar.user {
  background: #e2e8f0;
  color: #475569;
}

.msg-bubble {
  background: white;
  border-radius: 12px;
  padding: 10px 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.msg-item.user .msg-bubble {
  background: #3b82f6;
  color: white;
}

.msg-content p {
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-chart-mini {
  margin-top: 8px;
}

.related-questions {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.related-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}

.related-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.related-tag {
  cursor: pointer;
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  background: #94a3b8;
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out both;
}

.typing-dots span:nth-child(1) {
  animation-delay: -0.32s;
}
.typing-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typingBounce {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1.2);
    opacity: 1;
  }
}

.input-area {
  padding: 12px 16px;
  background: white;
  border-top: 1px solid #e2e8f0;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.input-hint {
  font-size: 12px;
  color: #94a3b8;
}
</style>
