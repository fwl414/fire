<template>
  <div class="message-center-page">
    <div class="title-row">
      <div>
        <div class="page-title">消息通知中心</div>
        <p class="subtitle">系统通知 · 告警推送 · 待办提醒 · 消息配置</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Bell /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.total }}</div>
            <div class="stat-label">全部消息</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Message /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.unread }}</div>
            <div class="stat-label">未读消息</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><InfoFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.system }}</div>
            <div class="stat-label">系统通知</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.alert }}</div>
            <div class="stat-label">告警通知</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">
          <el-icon><Bell /></el-icon>
          全部消息
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'system' }" @click="activeTab = 'system'">
          <el-icon><InfoFilled /></el-icon>
          系统通知
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'alert' }" @click="activeTab = 'alert'">
          <el-icon><Warning /></el-icon>
          告警通知
          <span v-if="stats.unreadAlert" class="badge">{{ stats.unreadAlert }}</span>
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'todo' }" @click="activeTab = 'todo'">
          <el-icon><SuccessFilled /></el-icon>
          待办提醒
          <span v-if="stats.unreadTodo" class="badge">{{ stats.unreadTodo }}</span>
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">
          <el-icon><Setting /></el-icon>
          通知设置
        </div>
      </div>

      <div v-if="activeTab !== 'settings'" class="tab-content">
        <div class="message-layout">
          <div class="message-list-panel">
            <div class="list-toolbar">
              <el-input v-model="searchKeyword" placeholder="搜索消息标题" style="width: 100%" clearable>
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </div>
            <div class="list-actions">
              <el-button size="small" @click="markAllRead">
                <el-icon><Check /></el-icon>
                全部已读
              </el-button>
              <el-button size="small" type="danger" @click="clearAll">
                <el-icon><Delete /></el-icon>
                清空
              </el-button>
              <el-button size="small" @click="refreshList">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
            <div class="message-list">
              <div
                v-for="msg in filteredMessages"
                :key="msg.id"
                class="message-item"
                :class="{ active: selectedMessage?.id === msg.id, unread: !msg.is_read }"
                @click="selectMessage(msg)"
              >
                <div class="msg-header">
                  <span class="msg-title">{{ msg.title }}</span>
                  <el-tag v-if="!msg.is_read" size="small" type="danger" effect="dark">未读</el-tag>
                </div>
                <div class="msg-meta">
                  <span class="msg-time">{{ msg.time }}</span>
                  <el-tag :type="msgTypeTag(msg.type)" size="small">{{ msgTypeText(msg.type) }}</el-tag>
                </div>
                <div class="msg-preview">{{ msg.content }}</div>
              </div>
              <el-empty v-if="filteredMessages.length === 0" description="暂无消息" :image-size="80" />
            </div>
          </div>

          <div class="message-detail-panel">
            <div v-if="selectedMessage" class="message-detail">
              <div class="detail-header">
                <h3 class="detail-title">{{ selectedMessage.title }}</h3>
                <div class="detail-meta">
                  <el-tag :type="msgTypeTag(selectedMessage.type)" effect="dark">
                    {{ msgTypeText(selectedMessage.type) }}
                  </el-tag>
                  <span class="detail-time">{{ selectedMessage.time }}</span>
                  <span class="detail-sender">发送人：{{ selectedMessage.sender }}</span>
                </div>
              </div>
              <div class="detail-content">
                <p v-for="(para, idx) in selectedMessage.content.split('\n')" :key="idx">{{ para }}</p>
              </div>
              <div v-if="selectedMessage.attachments && selectedMessage.attachments.length" class="detail-attachments">
                <div class="attachments-title">相关附件</div>
                <div class="attachment-list">
                  <div v-for="(file, idx) in selectedMessage.attachments" :key="idx" class="attachment-item">
                    <el-icon><Document /></el-icon>
                    <span class="file-name">{{ file.name }}</span>
                    <span class="file-size">{{ file.size }}</span>
                    <el-button link type="primary" size="small">下载</el-button>
                  </div>
                </div>
              </div>
              <div class="detail-actions">
                <el-button v-if="!selectedMessage.is_read" type="primary" @click="markAsRead">
                  <el-icon><Reading /></el-icon>
                  标记已读
                </el-button>
                <el-button type="success" v-if="selectedMessage.type === 'todo'">
                  <el-icon><Check /></el-icon>
                  立即处理
                </el-button>
                <el-button type="danger">
                  <el-icon><Delete /></el-icon>
                  删除消息
                </el-button>
                <el-button>
                  <el-icon><Refresh /></el-icon>
                  转发
                </el-button>
              </div>
            </div>
            <el-empty v-else description="请选择一条消息查看详情" :image-size="100" />
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'settings'" class="tab-content">
        <div class="settings-container">
          <el-alert
            title="站内通知已内置（WebSocket 实时推送 + 顶部铃铛）。这里配置的是「推到人」的外部通道：告警产生后按级别与类型匹配，自动发送到邮件 / 企业微信 / 钉钉 / 自定义 Webhook。"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 16px"
          />

          <div class="channel-toolbar">
            <div class="toolbar-left">
              <el-tag :type="notifyEnabled ? 'success' : 'info'" effect="dark">
                {{ notifyEnabled ? '外部通知已启用' : '外部通知已关闭（ALERT_NOTIFY_ENABLED=false）' }}
              </el-tag>
              <span class="channel-hint">共 {{ channels.length }} 个通道，启用 {{ enabledChannelCount }} 个</span>
            </div>
            <div class="toolbar-right">
              <el-button :loading="channelsLoading" @click="loadChannels">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
              <el-button type="primary" @click="openChannelDialog(null)">
                <el-icon><Plus /></el-icon>
                新增通道
              </el-button>
            </div>
          </div>

          <el-table
            v-loading="channelsLoading"
            :data="channels"
            stripe
            style="width: 100%"
            empty-text="尚未配置外部通知通道，新增后告警才会推送到邮箱或群机器人"
          >
            <el-table-column label="通道" min-width="170">
              <template #default="{ row }">
                <div class="channel-name">{{ row.name }}</div>
                <div class="channel-sub">{{ row.channel_type_label }}</div>
              </template>
            </el-table-column>
            <el-table-column label="推送条件" min-width="180">
              <template #default="{ row }">
                <div>级别 ≥ {{ row.min_severity_label }}</div>
                <div class="channel-sub">
                  {{ row.alert_types && row.alert_types.length ? row.alert_types.join('、') : '全部告警类型' }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="目标" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="channel-target">{{ channelTarget(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最近发送" width="190">
              <template #default="{ row }">
                <div v-if="row.last_success_at" class="channel-sub">成功：{{ formatTime(row.last_success_at) }}</div>
                <div v-if="row.last_error" class="channel-error">失败：{{ row.last_error }}</div>
                <div v-if="!row.last_success_at && !row.last_error" class="channel-sub">尚未发送</div>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="90" align="center">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" @update:model-value="value => toggleChannel(row, value)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="230" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" :loading="testingId === row.id" @click="testChannel(row)">
                  测试
                </el-button>
                <el-button link type="primary" size="small" @click="openChannelDialog(row)">编辑</el-button>
                <el-button link type="info" size="small" @click="openDeliveries(row)">记录</el-button>
                <el-button link type="danger" size="small" @click="removeChannel(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-dialog
          v-model="channelDialogVisible"
          :title="channelForm.id ? '编辑通知通道' : '新增通知通道'"
          width="580px"
        >
          <el-form label-width="120px">
            <el-form-item label="通道名称">
              <el-input v-model="channelForm.name" placeholder="例如：消防值班群" />
            </el-form-item>
            <el-form-item label="通道类型" required>
              <el-select v-model="channelForm.channel_type" style="width: 100%" @change="onChannelTypeChange">
                <el-option v-for="item in channelTypes" :key="item.channel_type" :label="item.label" :value="item.channel_type" />
              </el-select>
              <div v-if="currentTypeSpec" class="channel-sub">{{ currentTypeSpec.description }}</div>
            </el-form-item>
            <el-form-item
              v-for="field in currentTypeFields"
              :key="field.key"
              :label="field.label"
              :required="Boolean(field.required)"
            >
              <el-input
                v-model="channelForm.config[field.key]"
                :type="field.secret ? 'password' : 'text'"
                :placeholder="field.placeholder || ''"
                show-password
              />
            </el-form-item>
            <el-form-item label="最低级别">
              <el-select v-model="channelForm.min_severity" style="width: 100%">
                <el-option v-for="level in severityLevels" :key="level.value" :label="level.label" :value="level.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="告警类型">
              <el-input v-model="channelForm.alert_types_text" placeholder="留空表示全部类型；多个用逗号分隔，如 smoke_high,fault" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="channelForm.remark" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="channelDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="channelSaving" @click="saveChannel">保存</el-button>
          </template>
        </el-dialog>

        <el-dialog v-model="deliveryDialogVisible" :title="`通知投递记录 · ${deliveriesChannelName}`" width="760px">
          <el-table v-loading="deliveriesLoading" :data="deliveries" size="small" empty-text="暂无投递记录">
            <el-table-column prop="alert_code" label="告警编号" width="200" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.status === 'success' ? 'success' : (row.status === 'pending' ? 'info' : 'danger')"
                >
                  {{ row.status === 'success' ? '成功' : (row.status === 'pending' ? '待发送' : '失败') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="attempts" label="尝试" width="70" />
            <el-table-column label="结果" min-width="260">
              <template #default="{ row }">
                <span v-if="row.error" class="channel-error">{{ row.error }}</span>
                <span v-else class="channel-sub">{{ row.response_excerpt || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="170">
              <template #default="{ row }">{{ formatTime(row.updated_at || row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-dialog>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, Message, Warning, InfoFilled, SuccessFilled, Setting, Check, Close, Search, Delete, Refresh, Reading, Document, Plus } from '@element-plus/icons-vue'
import {
  listNotificationChannels,
  createNotificationChannel,
  updateNotificationChannel,
  deleteNotificationChannel,
  toggleNotificationChannel,
  testNotificationChannel,
  listNotificationDeliveries,
} from '../api'

const activeTab = ref('all')
const searchKeyword = ref('')
const selectedMessage = ref(null)

const stats = ref({
  total: 128,
  unread: 23,
  system: 45,
  alert: 32,
  unreadAlert: 8,
  unreadTodo: 12,
})

const messages = ref([
  {
    id: 1,
    title: '【紧急告警】综合办公楼A座3层烟感探测器触发报警',
    type: 'alert',
    time: '2026-09-09 14:32:15',
    sender: '消防报警系统',
    is_read: false,
    content: '告警设备：烟感探测器-3F走廊东\n设备编号：DEV-000123\n安装位置：综合办公楼A座3层东侧走廊\n告警时间：2026-09-09 14:32:15\n告警类型：烟雾报警\n告警级别：严重\n\n请立即安排人员前往现场确认情况，检查是否有真实火情发生。如确认误报，请在系统中进行复位操作。',
    attachments: [
      { name: '告警现场监控截图.jpg', size: '2.3 MB' },
      { name: '设备位置平面图.pdf', size: '856 KB' },
    ],
  },
  {
    id: 2,
    title: '系统升级通知：消防智能分析平台V2.5版本发布',
    type: 'system',
    time: '2026-09-09 10:00:00',
    sender: '系统管理员',
    is_read: false,
    content: '尊敬的用户：\n\n消防智能分析平台将于2026年9月10日凌晨02:00-04:00进行系统升级，升级至V2.5版本。\n\n本次升级内容：\n1. 新增视频火焰识别算法，识别准确率提升至98.5%\n2. 优化设备故障诊断模型，误报率降低30%\n3. 新增移动端消息推送功能\n4. 优化报表导出性能\n\n升级期间系统将暂停服务，请提前做好相关工作安排。如有疑问，请联系技术支持。',
    attachments: [
      { name: 'V2.5版本升级说明.docx', size: '1.2 MB' },
    ],
  },
  {
    id: 3,
    title: '【待办提醒】您有3条待处理的维保工单',
    type: 'todo',
    time: '2026-09-09 09:15:00',
    sender: '维保管理系统',
    is_read: false,
    content: '您好，您目前有3条待处理的维保工单：\n\n1. 工单编号：WO-20260909-001\n   设备：喷淋泵-主泵\n   位置：综合办公楼A座地下室泵房\n   类型：故障维修\n   优先级：高\n\n2. 工单编号：WO-20260908-003\n   设备：防火卷帘门-东出口\n   位置：实验楼B座1层\n   类型：日常维保\n   优先级：中\n\n3. 工单编号：WO-20260907-005\n   设备：应急照明集中电源\n   位置：学生宿舍C区配电间\n   类型：定期检测\n   优先级：中\n\n请及时处理以上工单。',
    attachments: [],
  },
  {
    id: 4,
    title: '【告警】地下车库B1层温感异常升温预警',
    type: 'alert',
    time: '2026-09-08 22:45:30',
    sender: '消防报警系统',
    is_read: false,
    content: '预警设备：温感探测器-B1车库东区\n设备编号：DEV-000234\n安装位置：地下车库B1层东区A12车位上方\n预警时间：2026-09-08 22:45:30\n当前温度：58.2℃\n预警阈值：55℃\n预警级别：警告\n\n系统检测到该区域温度持续上升，已触发高温预警。请安保人员前往现场查看，排除车辆自燃等安全隐患。',
    attachments: [
      { name: '温度趋势图.png', size: '560 KB' },
    ],
  },
  {
    id: 5,
    title: '消防培训通知：本月消防演练安排',
    type: 'system',
    time: '2026-09-08 16:30:00',
    sender: '安全管理部',
    is_read: true,
    content: '各部门：\n\n为提高全员消防安全意识和应急处置能力，定于2026年9月15日（星期二）下午14:00-16:00在综合办公楼前广场举行消防演练。\n\n演练内容：\n1. 火灾报警及初期处置\n2. 灭火器使用实操\n3. 疏散逃生演练\n4. 消防水带连接练习\n\n请各部门负责人组织本部门员工准时参加，提前熟悉疏散路线。演练期间请配合现场指挥，确保安全。',
    attachments: [
      { name: '消防演练方案.pdf', size: '2.1 MB' },
      { name: '疏散路线图.jpg', size: '1.5 MB' },
    ],
  },
  {
    id: 6,
    title: '【待办】设备巡检任务待完成：实验楼B座',
    type: 'todo',
    time: '2026-09-08 08:00:00',
    sender: '巡检管理系统',
    is_read: true,
    content: '巡检任务：实验楼B座周度消防巡检\n任务编号：INSP-20260908-002\n计划时间：2026-09-08 09:00 - 11:00\n巡检区域：实验楼B座1-5层\n巡检点数量：28个\n\n请按时完成巡检任务，如发现异常请及时上报。',
    attachments: [
      { name: '巡检清单.xlsx', size: '45 KB' },
    ],
  },
  {
    id: 7,
    title: '【系统通知】您的账号权限已更新',
    type: 'system',
    time: '2026-09-07 15:20:00',
    sender: '系统管理员',
    is_read: true,
    content: '您好，您的账号权限已由管理员更新。\n\n更新内容：\n- 新增：维保管理模块操作权限\n- 新增：报表导出权限\n- 调整：设备管理模块由查看权限调整为编辑权限\n\n如对权限调整有疑问，请联系系统管理员。',
    attachments: [],
  },
  {
    id: 8,
    title: '【告警恢复】综合办公楼A座3层烟感报警已复位',
    type: 'alert',
    time: '2026-09-07 11:20:00',
    sender: '消防报警系统',
    is_read: true,
    content: '告警设备：烟感探测器-3F走廊东\n设备编号：DEV-000123\n告警时间：2026-09-07 10:45:22\n复位时间：2026-09-07 11:20:00\n复位操作人：张安保（安保主管）\n\n处理结果：现场确认为厨房油烟误报，已对探测器进行清洁处理，系统已恢复正常运行。',
    attachments: [
      { name: '告警处理报告.pdf', size: '890 KB' },
    ],
  },
  {
    id: 9,
    title: '【待办】维保合同即将到期：安恒消防设备公司',
    type: 'todo',
    time: '2026-09-06 10:00:00',
    sender: '合同管理系统',
    is_read: true,
    content: '维保单位：安恒消防设备公司\n合同编号：HT-2025-003\n合同到期日：2026-09-30\n剩余天数：24天\n\n该维保单位合同即将到期，请提前评估合作情况，及时办理合同续签或重新招标事宜。',
    attachments: [
      { name: '维保服务评估表.xlsx', size: '128 KB' },
    ],
  },
  {
    id: 10,
    title: '月度消防安全报告已生成',
    type: 'system',
    time: '2026-09-01 09:00:00',
    sender: '报表中心',
    is_read: true,
    content: '2026年8月消防安全月度报告已生成，主要内容包括：\n\n一、火情告警统计\n- 本月共接告警42次，其中真实火情0次，误报42次\n- 误报率100%，较上月下降12%\n\n二、设备运行状态\n- 在线设备：1256台，在线率98.7%\n- 故障设备：16台，已修复12台\n\n三、维保工作完成\n- 计划维保：24次，已完成22次\n- 完成率：91.7%\n\n四、下月重点工作\n1. 完成剩余故障设备维修\n2. 安排季度全面检测\n3. 组织消防演练',
    attachments: [
      { name: '2026年8月消防安全报告.pdf', size: '3.8 MB' },
      { name: '8月告警统计明细.xlsx', size: '520 KB' },
    ],
  },
])

// ---- 告警外部通知通道：配置在数据库里，密钥字段后端只回掩码 ----

const notifyEnabled = ref(true)
const channels = ref([])
const channelTypes = ref([])
const severityLevels = ref([])
const channelsLoading = ref(false)
const testingId = ref(null)
const channelDialogVisible = ref(false)
const channelSaving = ref(false)
const channelForm = ref(emptyChannelForm())
const deliveryDialogVisible = ref(false)
const deliveries = ref([])
const deliveriesLoading = ref(false)
const deliveriesChannelName = ref('')

const enabledChannelCount = computed(() => channels.value.filter(item => item.enabled).length)
const currentTypeSpec = computed(() =>
  channelTypes.value.find(item => item.channel_type === channelForm.value.channel_type) || null
)
const currentTypeFields = computed(() => currentTypeSpec.value?.fields || [])

function emptyChannelForm() {
  return {
    id: null,
    name: '',
    channel_type: 'webhook',
    config: {},
    min_severity: 'high',
    alert_types_text: '',
    remark: '',
  }
}

function channelTarget(row) {
  if (row.channel_type === 'email') {
    return row.config?.recipients ? `邮件 → ${row.config.recipients}` : '未配置收件人'
  }
  const url = row.config?.url || ''
  if (url === '******') return '已配置（密钥字段不回显）'
  return url || '未配置'
}

function formatTime(value) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value).replace('T', ' ').slice(0, 19)
  const pad = n => String(n).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} `
    + `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
}

async function loadChannels() {
  channelsLoading.value = true
  try {
    const { data } = await listNotificationChannels()
    channels.value = data.items || []
    channelTypes.value = data.types || []
    severityLevels.value = data.severity_levels || []
    notifyEnabled.value = data.notify_enabled !== false
  } catch (error) {
    // 非管理员访问会被拦截器提示，这里保持空列表
  } finally {
    channelsLoading.value = false
  }
}

function openChannelDialog(row) {
  if (row) {
    channelForm.value = {
      id: row.id,
      name: row.name,
      channel_type: row.channel_type,
      config: { ...(row.config || {}) },
      min_severity: row.min_severity || 'high',
      alert_types_text: (row.alert_types || []).join(','),
      remark: row.remark || '',
    }
  } else {
    channelForm.value = emptyChannelForm()
  }
  channelDialogVisible.value = true
}

function onChannelTypeChange() {
  // 不同类型的字段完全不同，切换时清空避免串值
  channelForm.value.config = {}
}

async function saveChannel() {
  const form = channelForm.value
  const payload = {
    name: form.name,
    channel_type: form.channel_type,
    config: form.config,
    min_severity: form.min_severity,
    alert_types: form.alert_types_text
      ? form.alert_types_text.split(/[,，]/).map(item => item.trim()).filter(Boolean)
      : [],
    remark: form.remark,
  }
  channelSaving.value = true
  try {
    if (form.id) {
      await updateNotificationChannel(form.id, payload)
    } else {
      await createNotificationChannel(payload)
    }
    ElMessage.success('通知通道已保存')
    channelDialogVisible.value = false
    await loadChannels()
  } catch (error) {
    // 校验失败原因由拦截器提示（如缺少回调地址、收件人不合法）
  } finally {
    channelSaving.value = false
  }
}

async function toggleChannel(row, value) {
  const previous = row.enabled
  row.enabled = value
  try {
    await toggleNotificationChannel(row.id, value)
    ElMessage.success(value ? '通道已启用' : '通道已停用')
  } catch (error) {
    row.enabled = previous
  }
}

async function testChannel(row) {
  testingId.value = row.id
  try {
    const { data } = await testNotificationChannel(row.id)
    ElMessage.success(data.message || '测试消息已发送')
    await loadChannels()
  } catch (error) {
    // 失败原因由拦截器提示，并已记录到通道的最近错误
    await loadChannels()
  } finally {
    testingId.value = null
  }
}

async function removeChannel(row) {
  try {
    await ElMessageBox.confirm(`确认删除通道「${row.name}」？历史投递记录会保留。`, '删除确认', { type: 'warning' })
  } catch (error) {
    return
  }
  try {
    await deleteNotificationChannel(row.id)
    ElMessage.success('通道已删除')
    await loadChannels()
  } catch (error) {
    // 拦截器已提示
  }
}

async function openDeliveries(row) {
  deliveriesChannelName.value = row.name
  deliveryDialogVisible.value = true
  deliveriesLoading.value = true
  try {
    const { data } = await listNotificationDeliveries({ channel_id: row.id, limit: 50 })
    deliveries.value = data.items || []
  } catch (error) {
    deliveries.value = []
  } finally {
    deliveriesLoading.value = false
  }
}

// 首次切到「通知设置」页签时才拉数据
watch(activeTab, tab => {
  if (tab === 'settings' && !channels.value.length) loadChannels()
})

const filteredMessages = computed(() => {
  let list = messages.value
  if (activeTab.value === 'system') {
    list = list.filter(m => m.type === 'system')
  } else if (activeTab.value === 'alert') {
    list = list.filter(m => m.type === 'alert')
  } else if (activeTab.value === 'todo') {
    list = list.filter(m => m.type === 'todo')
  }
  if (searchKeyword.value) {
    list = list.filter(m => m.title.includes(searchKeyword.value) || m.content.includes(searchKeyword.value))
  }
  return list
})

function msgTypeText(type) {
  const map = { system: '系统通知', alert: '告警通知', todo: '待办提醒' }
  return map[type] || '系统通知'
}

function msgTypeTag(type) {
  const map = { system: 'primary', alert: 'danger', todo: 'warning' }
  return map[type] || 'primary'
}

function selectMessage(msg) {
  selectedMessage.value = msg
  if (!msg.is_read) {
    msg.is_read = true
    stats.value.unread--
    if (msg.type === 'alert') stats.value.unreadAlert--
    if (msg.type === 'todo') stats.value.unreadTodo--
  }
}

function markAsRead() {
  if (selectedMessage.value && !selectedMessage.value.is_read) {
    selectedMessage.value.is_read = true
    stats.value.unread--
    if (selectedMessage.value.type === 'alert') stats.value.unreadAlert--
    if (selectedMessage.value.type === 'todo') stats.value.unreadTodo--
    ElMessage.success('已标记为已读')
  }
}

function markAllRead() {
  let count = 0
  filteredMessages.value.forEach(msg => {
    if (!msg.is_read) {
      msg.is_read = true
      count++
    }
  })
  stats.value.unread = Math.max(0, stats.value.unread - count)
  stats.value.unreadAlert = 0
  stats.value.unreadTodo = 0
  ElMessage.success(`已将 ${count} 条消息标记为已读`)
}

function clearAll() {
  ElMessage.info('清空功能演示中...')
}

function refreshList() {
  ElMessage.success('消息列表已刷新')
}
</script>

<style scoped>
.message-center-page {
  color: #0f172a;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.subtitle {
  margin: -4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.stats-row {
  margin-bottom: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 4px;
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

.stat-info .stat-num {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: #0f172a;
}

.stat-info .stat-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  margin-bottom: 12px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 20px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px;
  cursor: pointer;
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
  position: relative;
}

.tab-item:hover {
  color: #334155;
}

.tab-item.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 600;
}

.tab-item .badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  line-height: 18px;
}

.tab-content {
  padding-top: 4px;
}

.message-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 320px);
  min-height: 500px;
}

.message-list-panel {
  width: 380px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e2e8f0;
  padding-right: 16px;
}

.list-toolbar {
  margin-bottom: 10px;
}

.list-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-item {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.message-item:hover {
  border-color: #93c5fd;
  background: #f0f7ff;
}

.message-item.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.message-item.unread {
  background: #fefce8;
  border-color: #fde68a;
}

.message-item.unread:hover {
  background: #fef9c3;
}

.message-item.unread.active {
  background: #fef9c3;
  border-color: #2563eb;
}

.msg-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  gap: 8px;
}

.msg-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.msg-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
}

.msg-time {
  color: #94a3b8;
}

.msg-preview {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.5;
}

.message-detail-panel {
  flex: 1;
  overflow-y: auto;
  padding-left: 4px;
}

.message-detail {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.detail-header {
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 16px;
}

.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 10px 0;
  line-height: 1.4;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: #64748b;
  flex-wrap: wrap;
}

.detail-time, .detail-sender {
  display: flex;
  align-items: center;
  gap: 4px;
}

.detail-content {
  flex: 1;
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
  margin-bottom: 20px;
}

.detail-content p {
  margin: 0 0 12px 0;
}

.detail-content p:last-child {
  margin-bottom: 0;
}

.detail-attachments {
  margin-bottom: 20px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.attachments-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 12px;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
}

.attachment-item .el-icon {
  color: #3b82f6;
  font-size: 18px;
}

.file-name {
  flex: 1;
  color: #0f172a;
}

.file-size {
  color: #94a3b8;
  font-size: 12px;
}

.detail-actions {
  display: flex;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.settings-container {
  max-width: 1000px;
  margin: 0 auto;
}

.channel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.channel-toolbar .toolbar-left,
.channel-toolbar .toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.channel-hint {
  font-size: 12px;
  color: #64748b;
}

.channel-name {
  font-weight: 600;
  color: #0f172a;
}

.channel-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.channel-error {
  font-size: 12px;
  color: #b91c1c;
  margin-top: 2px;
  word-break: break-all;
}

.channel-target {
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #334155;
  word-break: break-all;
}
</style>
