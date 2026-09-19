<template>
  <div class="system-announcement-page">
    <div class="title-row">
      <div>
        <div class="page-title">系统公告管理</div>
        <p class="subtitle">通知公告 · 紧急通知 · 定时发布 · 接收人群管理 · 全平台公告统一发布</p>
      </div>
      <div class="actions">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="openPublishDialog">
          <el-icon><Plus /></el-icon>
          发布公告
        </el-button>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.total }}</div>
            <div class="stat-label">公告总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon green"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.published }}</div>
            <div class="stat-label">已发布</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><EditPen /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.draft }}</div>
            <div class="stat-label">草稿</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon purple"><el-icon><Calendar /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.monthPublished }}</div>
            <div class="stat-label">本月发布</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">
          <el-icon><List /></el-icon>
          全部公告
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'notice' }" @click="activeTab = 'notice'">
          <el-icon><Bell /></el-icon>
          通知公告
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'urgent' }" @click="activeTab = 'urgent'">
          <el-icon><Warning /></el-icon>
          紧急通知
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'manage' }" @click="activeTab = 'manage'">
          <el-icon><Setting /></el-icon>
          公告管理
        </div>
      </div>

      <div v-if="activeTab === 'all'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="allTypeFilter" placeholder="公告类型" clearable style="width: 140px">
              <el-option label="通知公告" value="notice" />
              <el-option label="紧急通知" value="urgent" />
              <el-option label="系统通知" value="system" />
              <el-option label="活动通知" value="activity" />
            </el-select>
            <el-select v-model="allStatusFilter" placeholder="发布状态" clearable style="width: 140px">
              <el-option label="已发布" value="published" />
              <el-option label="草稿" value="draft" />
              <el-option label="已撤回" value="withdrawn" />
              <el-option label="定时发布" value="scheduled" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-input v-model="allSearch" placeholder="搜索公告标题" style="width: 220px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
        <el-table :data="filteredAllAnnouncements" stripe style="width: 100%">
          <el-table-column label="标题" min-width="260">
            <template #default="{ row }">
              <div class="announcement-title">
                <el-icon v-if="row.type === 'urgent'" class="urgent-icon"><WarningFilled /></el-icon>
                <el-icon v-else-if="row.type === 'notice'" class="notice-icon"><Bell /></el-icon>
                <el-icon v-else-if="row.type === 'system'" class="system-icon"><InfoFilled /></el-icon>
                <el-icon v-else class="activity-icon"><Flag /></el-icon>
                <span>{{ row.title }}</span>
                <el-tag v-if="row.is_top" size="small" type="danger" effect="dark" class="top-tag">置顶</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="announcementTypeTag(row.type)">{{ announcementTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="publish_time" label="发布时间" width="170" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="announcementStatusTag(row.status)">
                {{ announcementStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="read_count" label="阅读量" width="90" align="center" />
          <el-table-column prop="author" label="发布人" width="100" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewAnnouncement(row)">查看</el-button>
              <el-button link type="warning" @click="editAnnouncement(row)">编辑</el-button>
              <el-button link type="danger" @click="deleteAnnouncement(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap">
          <el-pagination
            layout="prev, pager, next, total"
            :total="filteredAllAnnouncements.length"
            :page-size="10"
            background
          />
        </div>
      </div>

      <div v-if="activeTab === 'notice'" class="tab-content">
        <div class="announcement-list">
          <div v-for="item in noticeList" :key="item.id" class="announcement-item notice" @click="viewAnnouncement(item)">
            <div class="item-header">
              <div class="item-icon notice-icon">
                <el-icon><Bell /></el-icon>
              </div>
              <div class="item-title-wrap">
                <div class="item-title">
                  {{ item.title }}
                  <el-tag v-if="item.is_top" size="small" type="danger" effect="dark" class="top-tag">置顶</el-tag>
                </div>
                <div class="item-meta">
                  <span>{{ item.author }}</span>
                  <span>·</span>
                  <span>{{ item.publish_time }}</span>
                  <span>·</span>
                  <span>{{ item.read_count }} 阅读</span>
                </div>
              </div>
            </div>
            <div class="item-summary">{{ item.summary }}</div>
          </div>
        </div>
        <el-empty v-if="!noticeList.length" description="暂无通知公告" />
      </div>

      <div v-if="activeTab === 'urgent'" class="tab-content">
        <div class="announcement-list">
          <div v-for="item in urgentList" :key="item.id" class="announcement-item urgent" @click="viewAnnouncement(item)">
            <div class="urgent-badge">
              <el-icon><WarningFilled /></el-icon>
              <span>紧急通知</span>
            </div>
            <div class="item-header">
              <div class="item-icon urgent-icon">
                <el-icon><WarningFilled /></el-icon>
              </div>
              <div class="item-title-wrap">
                <div class="item-title">
                  {{ item.title }}
                  <el-tag size="small" type="danger" effect="dark" class="top-tag">置顶</el-tag>
                </div>
                <div class="item-meta">
                  <span>{{ item.author }}</span>
                  <span>·</span>
                  <span>{{ item.publish_time }}</span>
                  <span>·</span>
                  <span>{{ item.read_count }} 阅读</span>
                </div>
              </div>
            </div>
            <div class="item-summary">{{ item.summary }}</div>
            <div class="urgent-footer">
              <el-button type="danger" size="small" link>
                立即查看 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <el-empty v-if="!urgentList.length" description="暂无紧急通知" />
      </div>

      <div v-if="activeTab === 'manage'" class="tab-content">
        <el-card class="publish-card" shadow="never">
          <div class="card-header">
            <div class="card-title">
              <el-icon><EditPen /></el-icon>
              发布公告
            </div>
            <p class="card-subtitle">填写公告信息，选择接收人群，设置发布时间</p>
          </div>
          <el-form :model="publishForm" label-width="100px">
            <el-form-item label="公告标题">
              <el-input v-model="publishForm.title" placeholder="请输入公告标题" maxlength="100" show-word-limit />
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="公告类型">
                  <el-select v-model="publishForm.type" placeholder="请选择公告类型" style="width: 100%">
                    <el-option label="通知公告" value="notice" />
                    <el-option label="紧急通知" value="urgent" />
                    <el-option label="系统通知" value="system" />
                    <el-option label="活动通知" value="activity" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="优先级">
                  <el-radio-group v-model="publishForm.priority">
                    <el-radio value="normal">普通</el-radio>
                    <el-radio value="important">重要</el-radio>
                    <el-radio value="urgent">紧急</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="公告内容">
              <div class="rich-editor-toolbar">
                <el-button-group>
                  <el-button size="small" :icon="Edit">加粗</el-button>
                  <el-button size="small" :icon="EditPen">斜体</el-button>
                  <el-button size="small" :icon="Document">下划线</el-button>
                </el-button-group>
                <el-button-group>
                  <el-button size="small">无序列表</el-button>
                  <el-button size="small">有序列表</el-button>
                </el-button-group>
                <el-button-group>
                  <el-button size="small">左对齐</el-button>
                  <el-button size="small">居中</el-button>
                  <el-button size="small">右对齐</el-button>
                </el-button-group>
                <el-button size="small">插入图片</el-button>
                <el-button size="small">插入链接</el-button>
              </div>
              <el-input
                v-model="publishForm.content"
                type="textarea"
                :rows="8"
                placeholder="请输入公告正文内容..."
              />
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="发布方式">
                  <el-radio-group v-model="publishForm.publish_type">
                    <el-radio value="immediate">立即发布</el-radio>
                    <el-radio value="scheduled">定时发布</el-radio>
                    <el-radio value="draft">存为草稿</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item v-if="publishForm.publish_type === 'scheduled'" label="定时时间">
                  <el-date-picker
                    v-model="publishForm.scheduled_time"
                    type="datetime"
                    placeholder="选择发布时间"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="接收人群">
              <el-checkbox-group v-model="publishForm.receivers">
                <el-checkbox value="all">全体人员</el-checkbox>
                <el-checkbox value="admin">行政部</el-checkbox>
                <el-checkbox value="tech">技术部</el-checkbox>
                <el-checkbox value="security">安保部</el-checkbox>
                <el-checkbox value="logistics">后勤部</el-checkbox>
                <el-checkbox value="sales">销售部</el-checkbox>
                <el-checkbox value="warehouse">仓储部</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="通知方式">
              <el-checkbox-group v-model="publishForm.notify_methods">
                <el-checkbox value="system">系统消息</el-checkbox>
                <el-checkbox value="email">邮件通知</el-checkbox>
                <el-checkbox value="sms">短信通知</el-checkbox>
                <el-checkbox value="app">APP推送</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="是否置顶">
              <el-switch v-model="publishForm.is_top" />
              <span style="margin-left: 10px; color: #64748b; font-size: 13px;">开启后公告将在列表顶部显示</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" @click="publishAnnouncement">
                <el-icon><Promotion /></el-icon>
                {{ publishForm.publish_type === 'draft' ? '保存草稿' : publishForm.publish_type === 'scheduled' ? '设置定时' : '立即发布' }}
              </el-button>
              <el-button size="large" @click="resetPublishForm">重置</el-button>
              <el-button size="large">预览</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </el-card>

    <el-dialog v-model="viewDialogVisible" title="公告详情" width="700px">
      <template v-if="currentAnnouncement">
        <div class="detail-header">
          <h2 class="detail-title">{{ currentAnnouncement.title }}</h2>
          <div class="detail-meta">
            <el-tag :type="announcementTypeTag(currentAnnouncement.type)" size="small">
              {{ announcementTypeText(currentAnnouncement.type) }}
            </el-tag>
            <span>发布人：{{ currentAnnouncement.author }}</span>
            <span>发布时间：{{ currentAnnouncement.publish_time }}</span>
            <span>阅读量：{{ currentAnnouncement.read_count }}</span>
          </div>
        </div>
        <el-divider />
        <div class="detail-content" v-html="safeAnnouncementContent"></div>
        <el-divider />
        <div class="detail-footer">
          <span style="color: #94a3b8; font-size: 13px;">接收人群：{{ currentAnnouncement.receiver_text || '全体人员' }}</span>
          <div class="detail-actions">
            <el-button @click="viewDialogVisible = false">关闭</el-button>
            <el-button type="primary">转发</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Document, CircleCheck, EditPen, Calendar, List, Bell, Warning, Setting, Plus, Search, Refresh, WarningFilled, InfoFilled, Flag, ArrowRight, Edit, Promotion } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sanitizeHtml } from '@/utils/xss'

const activeTab = ref('all')
const allTypeFilter = ref('')
const allStatusFilter = ref('')
const allSearch = ref('')
const viewDialogVisible = ref(false)
const currentAnnouncement = ref(null)

const safeAnnouncementContent = computed(() => {
  if (!currentAnnouncement.value?.content) return ''
  return sanitizeHtml(currentAnnouncement.value.content)
})

const stats = ref({
  total: 156,
  published: 128,
  draft: 18,
  monthPublished: 24
})

const publishForm = ref({
  title: '',
  type: 'notice',
  priority: 'normal',
  content: '',
  publish_type: 'immediate',
  scheduled_time: '',
  receivers: ['all'],
  notify_methods: ['system'],
  is_top: false
})

const announcements = ref([
  {
    id: 1,
    title: '关于2024年第三季度消防演练的通知',
    type: 'notice',
    status: 'published',
    publish_time: '2024-09-05 09:30:00',
    read_count: 256,
    author: '安保部',
    is_top: false,
    summary: '为提高全员消防安全意识和应急处置能力，定于2024年9月20日组织第三季度消防应急演练，请各部门提前做好准备...',
    content: '<p>各部门：</p><p>为提高全员消防安全意识和应急处置能力，检验消防应急预案的可行性，经研究决定，定于2024年9月20日组织第三季度消防应急演练。现将有关事项通知如下：</p><p><strong>一、演练时间</strong></p><p>2024年9月20日（星期五）下午14:00-15:30</p><p><strong>二、演练地点</strong></p><p>园区办公楼、生产车间、仓储区域</p><p><strong>三、参加人员</strong></p><p>全体在岗员工</p><p><strong>四、注意事项</strong></p><p>1. 请各部门负责人提前通知本部门员工，确保全员参与；</p><p>2. 演练时请保持冷静，按照指定路线有序疏散；</p><p>3. 请勿乘坐电梯，务必走消防通道；</p><p>4. 到达指定集合点后，请各部门及时清点人数。</p>',
    receiver_text: '全体人员'
  },
  {
    id: 2,
    title: '【紧急】关于加强园区消防安全管理的紧急通知',
    type: 'urgent',
    status: 'published',
    publish_time: '2024-09-08 16:20:00',
    read_count: 486,
    author: '安保部',
    is_top: true,
    summary: '近期周边地区火灾事故频发，为切实做好园区消防安全工作，严防火灾事故发生，现就加强消防安全管理有关事项紧急通知如下...',
    content: '<p>各部门、各单位：</p><p>近期周边地区火灾事故频发，给人民群众生命财产造成了严重损失。为切实做好园区消防安全工作，严防火灾事故发生，现就加强消防安全管理有关事项紧急通知如下：</p><p><strong>一、立即开展消防安全隐患大排查</strong></p><p>各部门要立即组织开展消防安全隐患大排查，重点排查电气线路、消防设施、安全出口、疏散通道等关键部位，对发现的隐患要立即整改。</p><p><strong>二、严格落实消防安全责任</strong></p><p>各部门主要负责人是本部门消防安全第一责任人，要切实履行职责，加强日常消防安全管理。</p><p><strong>三、加强值班值守</strong></p><p>各部门要加强值班值守，确保通讯畅通，遇有火情要第一时间上报并妥善处置。</p>',
    receiver_text: '全体人员'
  },
  {
    id: 3,
    title: '消防设施月度检测维护通知',
    type: 'system',
    status: 'published',
    publish_time: '2024-09-01 10:00:00',
    read_count: 128,
    author: '技术部',
    is_top: false,
    summary: '为确保消防设施正常运行，定于9月3日-9月5日对园区消防设施进行月度检测维护，请各部门配合...',
    content: '<p>各部门：</p><p>为确保消防设施正常运行，根据《消防设施维护管理规定》，定于9月3日-9月5日对园区消防设施进行月度检测维护。</p><p>检测内容包括：火灾自动报警系统、自动喷水灭火系统、消火栓系统、防排烟系统、应急照明和疏散指示标志等。</p><p>请各部门予以配合。</p>',
    receiver_text: '全体人员'
  },
  {
    id: 4,
    title: '关于举办消防安全知识竞赛活动的通知',
    type: 'activity',
    status: 'published',
    publish_time: '2024-08-28 14:30:00',
    read_count: 342,
    author: '行政部',
    is_top: false,
    summary: '为普及消防安全知识，提高全员消防安全意识，决定举办消防安全知识竞赛活动，现将有关事项通知如下...',
    content: '<p>各部门：</p><p>为普及消防安全知识，提高全员消防安全意识，营造"人人关注消防、人人参与消防"的良好氛围，决定举办消防安全知识竞赛活动。</p><p><strong>一、活动时间</strong></p><p>2024年9月15日-9月25日</p><p><strong>二、参赛对象</strong></p><p>全体员工</p><p><strong>三、竞赛内容</strong></p><p>消防法律法规、消防安全知识、火灾预防、火场逃生、消防设施使用等。</p><p><strong>四、奖项设置</strong></p><p>一等奖1名，二等奖3名，三等奖5名，优秀奖10名。</p>',
    receiver_text: '全体人员'
  },
  {
    id: 5,
    title: '关于完善消防档案资料的通知',
    type: 'notice',
    status: 'published',
    publish_time: '2024-08-20 09:00:00',
    read_count: 89,
    author: '安保部',
    is_top: false,
    summary: '为进一步规范消防档案管理，迎接上级消防部门检查，请各部门于8月31日前完善相关消防档案资料...',
    content: '<p>各部门：</p><p>为进一步规范消防档案管理，迎接上级消防部门检查，请各部门于8月31日前完善相关消防档案资料。</p><p>需完善的档案包括：消防培训记录、消防演练记录、消防设施维护记录、隐患排查整改记录等。</p>',
    receiver_text: '安保部、技术部'
  },
  {
    id: 6,
    title: '新入职员工消防安全培训安排',
    type: 'notice',
    status: 'scheduled',
    publish_time: '2024-09-10 08:00:00',
    read_count: 0,
    author: '人力资源部',
    is_top: false,
    summary: '定于9月12日对新入职员工进行消防安全培训，请相关人员准时参加...',
    content: '<p>各相关部门：</p><p>定于9月12日对新入职员工进行消防安全培训。</p><p>培训时间：9月12日上午9:00-11:30</p><p>培训地点：培训中心一楼会议室</p><p>培训内容：消防安全基础知识、灭火器使用、火场逃生等。</p>',
    receiver_text: '新入职员工'
  },
  {
    id: 7,
    title: '关于调整消防控制室值班安排的通知',
    type: 'system',
    status: 'draft',
    publish_time: '',
    read_count: 0,
    author: '安保部',
    is_top: false,
    summary: '因人员变动，拟对消防控制室值班安排进行调整，具体方案待确认后发布...',
    content: '',
    receiver_text: '安保部'
  },
  {
    id: 8,
    title: '【紧急】关于立即开展电气安全检查的通知',
    type: 'urgent',
    status: 'published',
    publish_time: '2024-08-15 17:30:00',
    read_count: 512,
    author: '技术部',
    is_top: true,
    summary: '因近期高温天气，用电负荷剧增，为防止电气火灾事故发生，决定立即开展全园区电气安全检查...',
    content: '<p>各部门：</p><p>因近期持续高温天气，园区用电负荷剧增，电气火灾风险加大。为防止电气火灾事故发生，决定立即开展全园区电气安全检查。</p><p><strong>一、检查时间</strong></p><p>即日起至8月18日</p><p><strong>二、检查内容</strong></p><p>1. 电气线路是否老化、破损；</p><p>2. 用电设备是否超负荷运行；</p><p>3. 配电箱、开关是否正常；</p><p>4. 空调、电脑等设备是否人走断电。</p>',
    receiver_text: '全体人员'
  },
  {
    id: 9,
    title: '志愿消防队招新通知',
    type: 'activity',
    status: 'published',
    publish_time: '2024-08-10 10:00:00',
    read_count: 267,
    author: '安保部',
    is_top: false,
    summary: '为加强园区消防安全工作，现面向全体员工招募志愿消防队队员，欢迎踊跃报名...',
    content: '<p>各部门：</p><p>为加强园区消防安全工作，提高初期火灾处置能力，现面向全体员工招募志愿消防队队员。</p><p><strong>一、招募人数</strong></p><p>20人</p><p><strong>二、招募条件</strong></p><p>1. 身体健康，热爱消防工作；</p><p>2. 具有一定的消防安全知识；</p><p>3. 自愿参加，服从安排。</p><p><strong>三、报名方式</strong></p><p>请到安保部报名，截止日期8月25日。</p>',
    receiver_text: '全体人员'
  },
  {
    id: 10,
    title: '关于119消防宣传日活动方案的通知',
    type: 'notice',
    status: 'withdrawn',
    publish_time: '2024-07-20 09:00:00',
    read_count: 156,
    author: '安保部',
    is_top: false,
    summary: '原119消防宣传日活动方案因需调整，已撤回，新方案另行通知...',
    content: '<p>该公告已撤回。</p>',
    receiver_text: '全体人员'
  },
])

function announcementTypeText(type) {
  const map = { notice: '通知公告', urgent: '紧急通知', system: '系统通知', activity: '活动通知' }
  return map[type] || type
}
function announcementTypeTag(type) {
  const map = { notice: 'primary', urgent: 'danger', system: 'info', activity: 'success' }
  return map[type] || 'info'
}
function announcementStatusText(status) {
  const map = { published: '已发布', draft: '草稿', withdrawn: '已撤回', scheduled: '定时发布' }
  return map[status] || status
}
function announcementStatusTag(status) {
  const map = { published: 'success', draft: 'warning', withdrawn: 'info', scheduled: 'primary' }
  return map[status] || 'info'
}

const filteredAllAnnouncements = computed(() => {
  let list = announcements.value
  if (allTypeFilter.value) list = list.filter(a => a.type === allTypeFilter.value)
  if (allStatusFilter.value) list = list.filter(a => a.status === allStatusFilter.value)
  if (allSearch.value) list = list.filter(a => a.title.includes(allSearch.value))
  return list.sort((a, b) => {
    if (a.is_top && !b.is_top) return -1
    if (!a.is_top && b.is_top) return 1
    return 0
  })
})

const noticeList = computed(() => {
  return announcements.value
    .filter(a => a.type === 'notice' && a.status === 'published')
    .sort((a, b) => {
      if (a.is_top && !b.is_top) return -1
      if (!a.is_top && b.is_top) return 1
      return 0
    })
})

const urgentList = computed(() => {
  return announcements.value
    .filter(a => a.type === 'urgent' && a.status === 'published')
    .sort((a, b) => {
      if (a.is_top && !b.is_top) return -1
      if (!a.is_top && b.is_top) return 1
      return 0
    })
})

function viewAnnouncement(row) {
  currentAnnouncement.value = row
  viewDialogVisible.value = true
}

function editAnnouncement(row) {
  ElMessage.info('编辑公告：' + row.title)
}

function deleteAnnouncement(row) {
  ElMessageBox.confirm('确定要删除该公告吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    const index = announcements.value.findIndex(a => a.id === row.id)
    if (index > -1) {
      announcements.value.splice(index, 1)
    }
    ElMessage.success('删除成功')
  }).catch(() => {})
}

function openPublishDialog() {
  activeTab.value = 'manage'
}

function publishAnnouncement() {
  if (!publishForm.value.title) {
    ElMessage.warning('请输入公告标题')
    return
  }
  if (!publishForm.value.content) {
    ElMessage.warning('请输入公告内容')
    return
  }
  
  const newAnnouncement = {
    id: Date.now(),
    title: publishForm.value.title,
    type: publishForm.value.type,
    status: publishForm.value.publish_type === 'draft' ? 'draft' : (publishForm.value.publish_type === 'scheduled' ? 'scheduled' : 'published'),
    publish_time: publishForm.value.publish_type === 'immediate' ? new Date().toLocaleString() : (publishForm.value.publish_type === 'scheduled' ? publishForm.value.scheduled_time : ''),
    read_count: 0,
    author: '当前用户',
    is_top: publishForm.value.is_top,
    summary: publishForm.value.content.substring(0, 100) + '...',
    content: publishForm.value.content,
    receiver_text: publishForm.value.receivers.includes('all') ? '全体人员' : publishForm.value.receivers.join('、')
  }
  
  announcements.value.unshift(newAnnouncement)
  
  if (publishForm.value.publish_type === 'draft') {
    ElMessage.success('草稿保存成功')
  } else if (publishForm.value.publish_type === 'scheduled') {
    ElMessage.success('定时发布设置成功')
  } else {
    ElMessage.success('公告发布成功')
  }
  
  activeTab.value = 'all'
  resetPublishForm()
}

function resetPublishForm() {
  publishForm.value = {
    title: '',
    type: 'notice',
    priority: 'normal',
    content: '',
    publish_type: 'immediate',
    scheduled_time: '',
    receivers: ['all'],
    notify_methods: ['system'],
    is_top: false
  }
}

function loadData() {
  ElMessage.success('刷新成功')
}
</script>

<style scoped>
.system-announcement-page {
  padding: 0;
}

.title-row {
  margin-bottom: 18px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.actions {
  display: flex;
  gap: 10px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}

.stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.stat-icon.green { background: linear-gradient(135deg, #22c55e, #16a34a); }
.stat-icon.orange { background: linear-gradient(135deg, #f59e0b, #d97706); }
.stat-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.module-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e2e8f0;
}

.tab-item {
  padding: 8px 18px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-item:hover {
  background: #f1f5f9;
  color: #334155;
}

.tab-item.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.announcement-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.announcement-title span {
  color: #0f172a;
  font-weight: 500;
}

.urgent-icon { color: #ef4444; }
.notice-icon { color: #3b82f6; }
.system-icon { color: #64748b; }
.activity-icon { color: #22c55e; }

.top-tag {
  margin-left: 8px;
}

.announcement-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.announcement-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 18px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.announcement-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #cbd5e1;
}

.announcement-item.notice {
  border-left: 4px solid #3b82f6;
}

.announcement-item.urgent {
  border-left: 4px solid #ef4444;
  background: #fffafa;
  position: relative;
}

.urgent-badge {
  position: absolute;
  top: 0;
  right: 20px;
  background: #ef4444;
  color: #fff;
  padding: 4px 12px;
  border-radius: 0 0 8px 8px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.item-header {
  display: flex;
  gap: 14px;
  margin-bottom: 12px;
}

.item-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.item-icon.notice-icon {
  background: #eff6ff;
  color: #3b82f6;
}

.item-icon.urgent-icon {
  background: #fef2f2;
  color: #ef4444;
}

.item-title-wrap {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-meta {
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.item-summary {
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.urgent-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #fee2e2;
  display: flex;
  justify-content: flex-end;
}

.publish-card {
  border: 1px solid #e2e8f0;
}

.card-header {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.card-subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.rich-editor-toolbar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px 8px 0 0;
  border-bottom: none;
  flex-wrap: wrap;
}

.rich-editor-toolbar + :deep(.el-textarea__inner) {
  border-radius: 0 0 8px 8px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.detail-header {
  text-align: center;
}

.detail-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 12px 0;
}

.detail-meta {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  color: #64748b;
  font-size: 13px;
  flex-wrap: wrap;
}

.detail-content {
  color: #334155;
  line-height: 1.8;
  font-size: 14px;
}

.detail-content :deep(p) {
  margin: 0 0 12px 0;
}

.detail-content :deep(strong) {
  color: #0f172a;
}

.detail-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-actions {
  display: flex;
  gap: 10px;
}
</style>
