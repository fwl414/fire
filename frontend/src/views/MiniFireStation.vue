<template>
  <div class="mini-fire-station-page">
    <div class="title-row">
      <div>
        <div class="page-title">微型消防站</div>
        <p class="subtitle">人员队伍 · 装备器材 · 训练演练 · 出警记录</p>
      </div>
    </div>

    <el-row :gutter="14" class="stats-row">
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon blue"><el-icon><User /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.teamMembers }}</div>
            <div class="stat-label">队员人数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon red"><el-icon><Tools /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.equipmentTypes }}</div>
            <div class="stat-label">装备种类</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon orange"><el-icon><Trophy /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.trainingCount }}</div>
            <div class="stat-label">训练次数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" :md="6" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon yellow"><el-icon><Bell /></el-icon></div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.dispatchCount }}</div>
            <div class="stat-label">出警次数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="module-card" shadow="never">
      <div class="tab-bar">
        <div class="tab-item" :class="{ active: activeTab === 'team' }" @click="activeTab = 'team'">
          <el-icon><UserFilled /></el-icon>
          队伍建设
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'equipment' }" @click="activeTab = 'equipment'">
          <el-icon><Tools /></el-icon>
          装备器材
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'training' }" @click="activeTab = 'training'">
          <el-icon><Trophy /></el-icon>
          训练演练
        </div>
        <div class="tab-item" :class="{ active: activeTab === 'dispatch' }" @click="activeTab = 'dispatch'">
          <el-icon><Bell /></el-icon>
          出警记录
        </div>
      </div>

      <div v-if="activeTab === 'team'" class="tab-content">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="24" :md="8" :lg="7">
            <el-card class="station-info-card" shadow="hover">
              <div class="station-header">
                <div class="station-icon"><el-icon><OfficeBuilding /></el-icon></div>
                <div class="station-title">{{ stationInfo.name }}</div>
              </div>
              <div class="station-detail">
                <div class="detail-row">
                  <span class="label">站点地址</span>
                  <span class="value">{{ stationInfo.address }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">站长</span>
                  <span class="value">{{ stationInfo.leader }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">联系电话</span>
                  <span class="value">{{ stationInfo.phone }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">建成时间</span>
                  <span class="value">{{ stationInfo.buildDate }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">站点等级</span>
                  <span class="value">
                    <el-tag size="small" type="success">一级微型站</el-tag>
                  </span>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :sm="24" :md="16" :lg="17">
            <div class="table-toolbar">
              <div class="toolbar-left">
                <el-radio-group v-model="teamGroupFilter" size="default">
                  <el-radio-button value="all">全部</el-radio-button>
                  <el-radio-button value="站长">站长</el-radio-button>
                  <el-radio-button value="队员">队员</el-radio-button>
                  <el-radio-button value="通讯员">通讯员</el-radio-button>
                  <el-radio-button value="驾驶员">驾驶员</el-radio-button>
                </el-radio-group>
              </div>
              <div class="toolbar-right">
                <el-input v-model="memberSearch" placeholder="搜索队员姓名" style="width: 200px" clearable>
                  <template #prefix><el-icon><Search /></el-icon></template>
                </el-input>
              </div>
            </div>

            <el-table :data="filteredMembers" stripe style="width: 100%">
              <el-table-column prop="name" label="姓名" width="100" />
              <el-table-column label="职务" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="getPositionTagType(row.position)">
                    {{ row.position }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="birthday" label="出生日期" width="120" />
              <el-table-column prop="phone" label="联系电话" width="140" />
              <el-table-column prop="joinDate" label="入队时间" width="120" />
              <el-table-column label="是否在岗" width="100">
                <template #default="{ row }">
                  <el-tag size="small" effect="dark" :type="row.onDuty ? 'success' : 'info'">
                    {{ row.onDuty ? '在岗' : '离岗' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120" fixed="right">
                <template #default>
                  <el-button link type="primary">详情</el-button>
                  <el-button link type="warning">排班</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'equipment'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-radio-group v-model="equipmentCategoryFilter" size="default">
              <el-radio-button value="all">全部分类</el-radio-button>
              <el-radio-button value="灭火器材">灭火器材</el-radio-button>
              <el-radio-button value="防护装备">防护装备</el-radio-button>
              <el-radio-button value="破拆工具">破拆工具</el-radio-button>
              <el-radio-button value="通讯设备">通讯设备</el-radio-button>
              <el-radio-button value="急救器材">急救器材</el-radio-button>
            </el-radio-group>
          </div>
          <div class="toolbar-right">
            <el-input v-model="equipmentSearch" placeholder="搜索装备名称" style="width: 200px" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="item in filteredEquipment" :key="item.id">
            <el-card class="equipment-card" shadow="hover">
              <div class="equipment-header">
                <div class="equipment-icon" :class="getCategoryClass(item.category)">
                  <el-icon><component :is="getCategoryIcon(item.category)" /></el-icon>
                </div>
                <div class="equipment-title">
                  <div class="equipment-name">{{ item.name }}</div>
                  <el-tag size="small" :type="getCategoryTagType(item.category)">{{ item.category }}</el-tag>
                </div>
              </div>
              <div class="equipment-detail">
                <div class="detail-row">
                  <span class="label">规格型号</span>
                  <span class="value">{{ item.model }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">数量</span>
                  <span class="value num">{{ item.quantity }} 件</span>
                </div>
                <div class="detail-row">
                  <span class="label">存放位置</span>
                  <span class="value">{{ item.location }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">检查状态</span>
                  <span class="value">
                    <el-tag size="small" effect="dark" :type="item.checkStatus === '正常' ? 'success' : item.checkStatus === '待检查' ? 'warning' : 'danger'">
                      {{ item.checkStatus }}
                    </el-tag>
                  </span>
                </div>
                <div class="detail-row">
                  <span class="label">有效期</span>
                  <span class="value" :class="{ expired: item.isExpired }">{{ item.validUntil }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-if="activeTab === 'training'" class="tab-content">
        <div class="training-section">
          <div class="section-title">
            <el-icon><Calendar /></el-icon>
            训练计划
          </div>
          <el-table :data="trainingPlans" stripe style="width: 100%; margin-bottom: 24px">
            <el-table-column prop="planName" label="计划名称" min-width="180" />
            <el-table-column label="训练类型" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="getTrainingTypeTagType(row.type)">
                  {{ row.type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="content" label="训练内容" min-width="240" show-overflow-tooltip />
            <el-table-column prop="planDate" label="计划时间" width="160" />
            <el-table-column prop="participants" label="参训人数" width="100" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="dark" :type="row.status === '已完成' ? 'success' : row.status === '进行中' ? 'primary' : 'warning'">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default>
                <el-button link type="primary">查看</el-button>
                <el-button link type="success">签到</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="training-section">
          <div class="section-title">
            <el-icon><Document /></el-icon>
            训练记录
          </div>
          <div class="table-toolbar">
            <div class="toolbar-left">
              <el-select v-model="trainingTypeFilter" placeholder="训练类型" clearable style="width: 140px">
                <el-option label="理论学习" value="理论学习" />
                <el-option label="技能训练" value="技能训练" />
                <el-option label="实战演练" value="实战演练" />
              </el-select>
              <el-date-picker
                v-model="trainingDateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                style="width: 260px"
              />
            </div>
            <div class="toolbar-right">
              <el-button>
                <el-icon><Download /></el-icon>
                导出记录
              </el-button>
            </div>
          </div>
          <el-table :data="filteredTrainingRecords" stripe style="width: 100%">
            <el-table-column prop="trainingDate" label="训练时间" width="160" />
            <el-table-column prop="trainingName" label="训练名称" min-width="180" />
            <el-table-column label="训练类型" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="getTrainingTypeTagType(row.type)">
                  {{ row.type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="content" label="训练内容" min-width="200" show-overflow-tooltip />
            <el-table-column prop="participants" label="参训人数" width="100" />
            <el-table-column prop="instructor" label="教官" width="100" />
            <el-table-column label="考核结果" width="110">
              <template #default="{ row }">
                <el-tag size="small" effect="dark" :type="row.result === '优秀' ? 'success' : row.result === '良好' ? 'primary' : row.result === '合格' ? 'warning' : 'danger'">
                  {{ row.result }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default>
                <el-button link type="primary">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div v-if="activeTab === 'dispatch'" class="tab-content">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-select v-model="fireLevelFilter" placeholder="火警等级" clearable style="width: 140px">
              <el-option label="一般火灾" value="一般火灾" />
              <el-option label="较大火灾" value="较大火灾" />
              <el-option label="重大火灾" value="重大火灾" />
              <el-option label="特别重大" value="特别重大" />
            </el-select>
            <el-date-picker
              v-model="dispatchDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
            />
          </div>
          <div class="toolbar-right">
            <el-button>
              <el-icon><Download /></el-icon>
              导出记录
            </el-button>
          </div>
        </div>

        <el-table :data="filteredDispatchRecords" stripe style="width: 100%">
          <el-table-column prop="dispatchTime" label="出警时间" width="160" />
          <el-table-column label="火警等级" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="getFireLevelTagType(row.fireLevel)">
                {{ row.fireLevel }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="fireLocation" label="起火部位" min-width="160" />
          <el-table-column prop="firefighters" label="出动人数" width="100" />
          <el-table-column prop="vehicles" label="出动车辆" width="120" />
          <el-table-column prop="arriveTime" label="到达时间" width="160" />
          <el-table-column label="处置结果" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="row.result === '成功处置' ? 'success' : row.result === '增援处置' ? 'warning' : 'info'">
                {{ row.result }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="returnTime" label="归队时间" width="160" />
          <el-table-column prop="duration" label="战斗时长" width="110" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default>
              <el-button link type="primary">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { User, Tools, Trophy, Bell, UserFilled, OfficeBuilding, Search, Calendar, Document, Download, WarnTriangleFilled, Phone, FirstAidKit, Avatar } from '@element-plus/icons-vue'

const activeTab = ref('team')
const memberSearch = ref('')
const teamGroupFilter = ref('all')
const equipmentSearch = ref('')
const equipmentCategoryFilter = ref('all')
const trainingTypeFilter = ref('')
const trainingDateRange = ref([])
const fireLevelFilter = ref('')
const dispatchDateRange = ref([])

const stats = ref({
  teamMembers: 18,
  equipmentTypes: 42,
  trainingCount: 86,
  dispatchCount: 23,
})

const stationInfo = ref({
  name: '科技园区微型消防站',
  address: '科技园区A座1层东侧',
  leader: '张建国',
  phone: '138****8888',
  buildDate: '2024-03-15',
})

const teamMembers = ref([
  { id: 1, name: '张建国', position: '站长', birthday: '1985-06-12', phone: '138****8888', joinDate: '2024-03-15', onDuty: true },
  { id: 2, name: '李明华', position: '副站长', birthday: '1988-09-20', phone: '139****6666', joinDate: '2024-03-20', onDuty: true },
  { id: 3, name: '王消防', position: '队员', birthday: '1992-03-15', phone: '137****9999', joinDate: '2024-04-01', onDuty: true },
  { id: 4, name: '赵安全', position: '队员', birthday: '1994-07-08', phone: '136****7777', joinDate: '2024-04-10', onDuty: true },
  { id: 5, name: '孙志强', position: '队员', birthday: '1990-11-25', phone: '135****5555', joinDate: '2024-05-01', onDuty: false },
  { id: 6, name: '周晓燕', position: '通讯员', birthday: '1995-02-18', phone: '134****4444', joinDate: '2024-05-15', onDuty: true },
  { id: 7, name: '吴大勇', position: '驾驶员', birthday: '1987-08-30', phone: '133****3333', joinDate: '2024-03-25', onDuty: true },
  { id: 8, name: '郑海涛', position: '队员', birthday: '1993-12-10', phone: '132****2222', joinDate: '2024-06-01', onDuty: true },
  { id: 9, name: '冯美玲', position: '通讯员', birthday: '1996-04-22', phone: '131****1111', joinDate: '2024-06-15', onDuty: false },
  { id: 10, name: '陈志强', position: '驾驶员', birthday: '1989-10-05', phone: '130****0000', joinDate: '2024-04-20', onDuty: true },
  { id: 11, name: '褚卫民', position: '队员', birthday: '1991-01-15', phone: '159****1234', joinDate: '2024-07-01', onDuty: true },
  { id: 12, name: '卫国强', position: '队员', birthday: '1997-05-08', phone: '158****5678', joinDate: '2024-07-10', onDuty: true },
  { id: 13, name: '蒋英勇', position: '队员', birthday: '1994-09-18', phone: '157****9012', joinDate: '2024-08-01', onDuty: true },
  { id: 14, name: '沈无畏', position: '队员', birthday: '1992-12-25', phone: '156****3456', joinDate: '2024-08-15', onDuty: false },
  { id: 15, name: '韩救火', position: '队员', birthday: '1995-06-30', phone: '155****7890', joinDate: '2024-09-01', onDuty: true },
  { id: 16, name: '杨冲锋', position: '驾驶员', birthday: '1988-04-12', phone: '154****2345', joinDate: '2024-05-20', onDuty: true },
  { id: 17, name: '朱迅达', position: '通讯员', birthday: '1996-11-08', phone: '153****6789', joinDate: '2024-09-10', onDuty: true },
  { id: 18, name: '秦守护', position: '队员', birthday: '1993-03-20', phone: '152****0123', joinDate: '2024-10-01', onDuty: true },
])

const equipmentList = ref([
  { id: 1, name: '干粉灭火器', category: '灭火器材', model: 'MFZ/ABC4', quantity: 50, location: '器材柜A1', checkStatus: '正常', validUntil: '2027-06-15', isExpired: false },
  { id: 2, name: '二氧化碳灭火器', category: '灭火器材', model: 'MT/3', quantity: 20, location: '器材柜A2', checkStatus: '正常', validUntil: '2026-12-20', isExpired: false },
  { id: 3, name: '消防水带', category: '灭火器材', model: '8型65mm', quantity: 30, location: '器材架B1', checkStatus: '正常', validUntil: '2028-03-10', isExpired: false },
  { id: 4, name: '消防水枪', category: '灭火器材', model: 'QZ3.5/7.5', quantity: 15, location: '器材架B2', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 5, name: '室内消火栓', category: '灭火器材', model: 'SN65', quantity: 25, location: '各楼层', checkStatus: '待检查', validUntil: '长期', isExpired: false },
  { id: 6, name: '消防头盔', category: '防护装备', model: 'FTK-B/A', quantity: 20, location: '器材柜C1', checkStatus: '正常', validUntil: '2027-01-15', isExpired: false },
  { id: 7, name: '消防服', category: '防护装备', model: 'ZFMH-JT', quantity: 20, location: '器材柜C2', checkStatus: '正常', validUntil: '2026-11-30', isExpired: false },
  { id: 8, name: '消防手套', category: '防护装备', model: 'RFT-1', quantity: 40, location: '器材柜C3', checkStatus: '正常', validUntil: '2027-04-20', isExpired: false },
  { id: 9, name: '消防安全腰带', category: '防护装备', model: 'FZL-YD', quantity: 20, location: '器材柜C4', checkStatus: '已过期', validUntil: '2026-08-10', isExpired: true },
  { id: 10, name: '消防靴', category: '防护装备', model: 'RJX-25', quantity: 20, location: '器材架C5', checkStatus: '正常', validUntil: '2027-08-15', isExpired: false },
  { id: 11, name: '正压式空气呼吸器', category: '防护装备', model: 'RHZK6.8/30', quantity: 10, location: '器材柜D1', checkStatus: '正常', validUntil: '2028-05-20', isExpired: false },
  { id: 12, name: '消防斧', category: '破拆工具', model: 'GF-1', quantity: 5, location: '器材架E1', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 13, name: '破门器', category: '破拆工具', model: 'PMQ-1', quantity: 3, location: '器材架E2', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 14, name: '液压剪扩器', category: '破拆工具', model: 'JK-3', quantity: 2, location: '器材柜E3', checkStatus: '待检查', validUntil: '长期', isExpired: false },
  { id: 15, name: '无齿锯', category: '破拆工具', model: 'WCJ-1', quantity: 2, location: '器材柜E4', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 16, name: '手持对讲机', category: '通讯设备', model: 'GP328D+', quantity: 15, location: '通讯柜F1', checkStatus: '正常', validUntil: '2027-09-01', isExpired: false },
  { id: 17, name: '消防应急广播', category: '通讯设备', model: 'YX-1', quantity: 1, location: '控制室', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 18, name: '消防电话', category: '通讯设备', model: 'DH-1', quantity: 10, location: '各楼层', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 19, name: '强光手电筒', category: '通讯设备', model: 'SG-1', quantity: 20, location: '器材柜F2', checkStatus: '正常', validUntil: '2026-12-31', isExpired: false },
  { id: 20, name: '急救箱', category: '急救器材', model: 'JJX-1', quantity: 5, location: '器材柜G1', checkStatus: '待检查', validUntil: '2026-10-15', isExpired: false },
  { id: 21, name: '担架', category: '急救器材', model: 'DJ-1', quantity: 2, location: '器材架G2', checkStatus: '正常', validUntil: '长期', isExpired: false },
  { id: 22, name: '氧气呼吸器', category: '急救器材', model: 'AYH-1', quantity: 4, location: '器材柜G3', checkStatus: '正常', validUntil: '2027-06-30', isExpired: false },
  { id: 23, name: '灭火毯', category: '灭火器材', model: 'MHT-1', quantity: 15, location: '器材架A3', checkStatus: '正常', validUntil: '2028-12-01', isExpired: false },
  { id: 24, name: '防烟面罩', category: '防护装备', model: 'TZL30', quantity: 30, location: '器材柜D2', checkStatus: '正常', validUntil: '2027-03-15', isExpired: false },
])

const trainingPlans = ref([
  { id: 1, planName: '9月第二周训练计划', type: '技能训练', content: '灭火器使用、水带连接、室内消火栓操作', planDate: '2026-09-10 14:00', participants: 15, status: '待开始' },
  { id: 2, planName: '消防法律法规学习', type: '理论学习', content: '《消防法》《机关团体企业事业单位消防安全管理规定》', planDate: '2026-09-12 09:00', participants: 18, status: '待开始' },
  { id: 3, planName: '高层疏散实战演练', type: '实战演练', content: '模拟办公楼高层火灾，开展人员疏散、初期火灾扑救演练', planDate: '2026-09-15 15:00', participants: 50, status: '待开始' },
  { id: 4, planName: '装备器材操作培训', type: '技能训练', content: '破拆工具、防护装备、通讯设备使用操作', planDate: '2026-09-18 14:00', participants: 12, status: '待开始' },
])

const trainingRecords = ref([
  { id: 1, trainingDate: '2026-09-05 14:00', trainingName: '灭火器操作训练', type: '技能训练', content: '干粉、二氧化碳灭火器使用方法及注意事项实操训练', participants: 15, instructor: '张建国', result: '优秀' },
  { id: 2, trainingDate: '2026-09-03 09:00', trainingName: '消防安全知识讲座', type: '理论学习', content: '火灾预防、初期火灾处置、逃生自救知识', participants: 18, instructor: '李明华', result: '良好' },
  { id: 3, trainingDate: '2026-08-28 15:00', trainingName: '地下车库火灾演练', type: '实战演练', content: '模拟地下车库车辆起火，开展火情侦察、灭火救援演练', participants: 45, instructor: '张建国', result: '良好' },
  { id: 4, trainingDate: '2026-08-25 14:00', trainingName: '水带连接训练', type: '技能训练', content: '一人两盘水带连接、三人五盘水带连接训练', participants: 14, instructor: '王消防', result: '合格' },
  { id: 5, trainingDate: '2026-08-20 09:00', trainingName: '消防设施操作培训', type: '理论学习', content: '火灾自动报警系统、自动喷水灭火系统操作', participants: 16, instructor: '赵安全', result: '良好' },
  { id: 6, trainingDate: '2026-08-15 15:00', trainingName: '人员疏散演练', type: '实战演练', content: '办公楼全员疏散演练，检验疏散路线和应急指挥体系', participants: 200, instructor: '张建国', result: '优秀' },
  { id: 7, trainingDate: '2026-08-10 14:00', trainingName: '破拆工具使用训练', type: '技能训练', content: '消防斧、破门器、液压剪扩器操作训练', participants: 10, instructor: '孙志强', result: '合格' },
  { id: 8, trainingDate: '2026-08-05 09:00', trainingName: '应急通信培训', type: '理论学习', content: '对讲机使用、应急通信组网、指挥调度流程', participants: 12, instructor: '周晓燕', result: '优秀' },
  { id: 9, trainingDate: '2026-07-28 14:00', trainingName: '防护服穿戴训练', type: '技能训练', content: '消防服、空气呼吸器穿戴速度训练', participants: 15, instructor: '王消防', result: '良好' },
  { id: 10, trainingDate: '2026-07-20 15:00', trainingName: '消防水泵操作演练', type: '实战演练', content: '消防水泵启动、切换、故障排除实操演练', participants: 8, instructor: '张建国', result: '优秀' },
])

const dispatchRecords = ref([
  { id: 1, dispatchTime: '2026-09-06 14:23:00', fireLevel: '一般火灾', fireLocation: '实验楼B座3层化学实验室', firefighters: 8, vehicles: 1, arriveTime: '2026-09-06 14:26:00', result: '成功处置', returnTime: '2026-09-06 15:10:00', duration: '47分钟' },
  { id: 2, dispatchTime: '2026-09-02 10:15:00', fireLevel: '一般火灾', fireLocation: '学生食堂厨房', firefighters: 6, vehicles: 1, arriveTime: '2026-09-02 10:18:00', result: '成功处置', returnTime: '2026-09-02 10:45:00', duration: '30分钟' },
  { id: 3, dispatchTime: '2026-08-28 16:40:00', fireLevel: '一般火灾', fireLocation: '综合办公楼A座15层办公室', firefighters: 10, vehicles: 2, arriveTime: '2026-08-28 16:43:00', result: '成功处置', returnTime: '2026-08-28 17:20:00', duration: '40分钟' },
  { id: 4, dispatchTime: '2026-08-20 09:30:00', fireLevel: '较大火灾', fireLocation: '学生宿舍C区3号楼', firefighters: 15, vehicles: 3, arriveTime: '2026-08-20 09:33:00', result: '增援处置', returnTime: '2026-08-20 11:00:00', duration: '1小时30分' },
  { id: 5, dispatchTime: '2026-08-15 22:10:00', fireLevel: '一般火灾', fireLocation: '地下车库B区', firefighters: 8, vehicles: 2, arriveTime: '2026-08-15 22:13:00', result: '成功处置', returnTime: '2026-08-15 22:55:00', duration: '45分钟' },
  { id: 6, dispatchTime: '2026-08-08 14:55:00', fireLevel: '一般火灾', fireLocation: '图书馆D馆2层', firefighters: 6, vehicles: 1, arriveTime: '2026-08-08 14:58:00', result: '成功处置', returnTime: '2026-08-08 15:30:00', duration: '35分钟' },
  { id: 7, dispatchTime: '2026-07-30 11:20:00', fireLevel: '一般火灾', fireLocation: '配电房', firefighters: 10, vehicles: 2, arriveTime: '2026-07-30 11:22:00', result: '成功处置', returnTime: '2026-07-30 12:00:00', duration: '40分钟' },
  { id: 8, dispatchTime: '2026-07-22 13:40:00', fireLevel: '一般火灾', fireLocation: '危险品仓库', firefighters: 12, vehicles: 2, arriveTime: '2026-07-22 13:42:00', result: '成功处置', returnTime: '2026-07-22 14:15:00', duration: '35分钟' },
  { id: 9, dispatchTime: '2026-07-15 17:25:00', fireLevel: '较大火灾', fireLocation: '锅炉房', firefighters: 15, vehicles: 3, arriveTime: '2026-07-15 17:27:00', result: '增援处置', returnTime: '2026-07-15 19:10:00', duration: '1小时45分' },
  { id: 10, dispatchTime: '2026-07-08 08:50:00', fireLevel: '一般火灾', fireLocation: '计算机机房', firefighters: 8, vehicles: 2, arriveTime: '2026-07-08 08:53:00', result: '成功处置', returnTime: '2026-07-08 09:30:00', duration: '40分钟' },
  { id: 11, dispatchTime: '2026-06-28 20:15:00', fireLevel: '一般火灾', fireLocation: '档案室', firefighters: 6, vehicles: 1, arriveTime: '2026-06-28 20:18:00', result: '成功处置', returnTime: '2026-06-28 20:50:00', duration: '35分钟' },
  { id: 12, dispatchTime: '2026-06-20 16:30:00', fireLevel: '一般火灾', fireLocation: '食堂排烟管道', firefighters: 8, vehicles: 2, arriveTime: '2026-06-20 16:33:00', result: '成功处置', returnTime: '2026-06-20 17:15:00', duration: '45分钟' },
])

const filteredMembers = computed(() => {
  let list = teamMembers.value
  if (memberSearch.value) {
    list = list.filter(m => m.name.includes(memberSearch.value))
  }
  if (teamGroupFilter.value !== 'all') {
    list = list.filter(m => {
      if (teamGroupFilter.value === '站长') {
        return m.position === '站长' || m.position === '副站长'
      }
      return m.position === teamGroupFilter.value
    })
  }
  return list
})

const filteredEquipment = computed(() => {
  let list = equipmentList.value
  if (equipmentSearch.value) {
    list = list.filter(e => e.name.includes(equipmentSearch.value) || e.model.includes(equipmentSearch.value))
  }
  if (equipmentCategoryFilter.value !== 'all') {
    list = list.filter(e => e.category === equipmentCategoryFilter.value)
  }
  return list
})

const filteredTrainingRecords = computed(() => {
  let list = trainingRecords.value
  if (trainingTypeFilter.value) {
    list = list.filter(t => t.type === trainingTypeFilter.value)
  }
  return list
})

const filteredDispatchRecords = computed(() => {
  let list = dispatchRecords.value
  if (fireLevelFilter.value) {
    list = list.filter(d => d.fireLevel === fireLevelFilter.value)
  }
  return list
})

const getPositionTagType = (position) => {
  const map = {
    '站长': 'danger',
    '副站长': 'warning',
    '队员': 'primary',
    '通讯员': 'success',
    '驾驶员': 'info',
  }
  return map[position] || 'info'
}

const getCategoryClass = (category) => {
  const map = {
    '灭火器材': 'cat-fire',
    '防护装备': 'cat-protect',
    '破拆工具': 'cat-tool',
    '通讯设备': 'cat-comm',
    '急救器材': 'cat-med',
  }
  return map[category] || 'cat-fire'
}

const getCategoryIcon = (category) => {
  const map = {
    '灭火器材': WarnTriangleFilled,
    '防护装备': Avatar,
    '破拆工具': Tools,
    '通讯设备': Phone,
    '急救器材': FirstAidKit,
  }
  return map[category] || WarnTriangleFilled
}

const getCategoryTagType = (category) => {
  const map = {
    '灭火器材': 'danger',
    '防护装备': 'warning',
    '破拆工具': 'info',
    '通讯设备': 'primary',
    '急救器材': 'success',
  }
  return map[category] || 'info'
}

const getTrainingTypeTagType = (type) => {
  const map = {
    '理论学习': 'primary',
    '技能训练': 'success',
    '实战演练': 'warning',
  }
  return map[type] || 'info'
}

const getFireLevelTagType = (level) => {
  const map = {
    '一般火灾': 'success',
    '较大火灾': 'warning',
    '重大火灾': 'danger',
    '特别重大': 'danger',
  }
  return map[level] || 'info'
}
</script>

<style scoped>
.mini-fire-station-page {
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
.stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.stat-icon.orange { background: linear-gradient(135deg, #f97316, #ea580c); }
.stat-icon.yellow { background: linear-gradient(135deg, #eab308, #ca8a04); }

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

.tab-content {
  padding-top: 4px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
}

.station-info-card {
  margin-bottom: 16px;
}

.station-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}

.station-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: #fff;
  font-size: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.station-title {
  font-weight: 700;
  font-size: 17px;
  color: #0f172a;
}

.station-detail {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
  font-size: 13px;
  align-items: center;
}

.detail-row .label {
  color: #64748b;
}

.detail-row .value {
  color: #0f172a;
  font-weight: 500;
  text-align: right;
}

.detail-row .value.num {
  color: #ef4444;
  font-weight: 700;
}

.detail-row .value.expired {
  color: #ef4444;
  font-weight: 600;
}

.equipment-card {
  margin-bottom: 16px;
}

.equipment-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.equipment-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  color: #fff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.equipment-icon.cat-fire { background: linear-gradient(135deg, #ef4444, #dc2626); }
.equipment-icon.cat-protect { background: linear-gradient(135deg, #f97316, #ea580c); }
.equipment-icon.cat-tool { background: linear-gradient(135deg, #64748b, #475569); }
.equipment-icon.cat-comm { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.equipment-icon.cat-med { background: linear-gradient(135deg, #22c55e, #16a34a); }

.equipment-title {
  flex: 1;
  min-width: 0;
}

.equipment-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 4px;
}

.equipment-detail {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px;
}

.training-section {
  margin-bottom: 24px;
}

.training-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 14px;
  padding-left: 8px;
  border-left: 4px solid #2563eb;
}
</style>
