import { createRouter, createWebHistory } from 'vue-router'
import { getCurrentUser, canAccessRoute } from '../auth'

const Inspection = () => import('../views/Inspection.vue')
const Records = () => import('../views/Records.vue')
const Devices = () => import('../views/Devices.vue')
const DeviceData = () => import('../views/DeviceData.vue')
const Faults = () => import('../views/Faults.vue')
const QA = () => import('../views/QA.vue')
const Settings = () => import('../views/Settings.vue')
const Evaluation = () => import('../views/Evaluation.vue')
const AgentLab = () => import('../views/AgentLab.vue')
const WorkOrders = () => import('../views/WorkOrders.vue')
const Hardware = () => import('../views/Hardware.vue')
const SystemHealth = () => import('../views/SystemHealth.vue')
const KnowledgeBase = () => import('../views/KnowledgeBase.vue')
const KnowledgeGraph = () => import('../views/KnowledgeGraph.vue')
const Learning = () => import('../views/Learning.vue')
const LearningApp = () => import('../views/LearningApp.vue')
const ReportPrint = () => import('../views/ReportPrint.vue')
const ReportVerify = () => import('../views/ReportVerify.vue')
const Telemetry = () => import('../views/Telemetry.vue')
const Defense = () => import('../views/Defense.vue')
const Competition = () => import('../views/Competition.vue')
const Login = () => import('../views/Login.vue')
const NoAccess = () => import('../views/NoAccess.vue')
const NotificationCenter = () => import('../views/NotificationCenter.vue')
const OperationLogs = () => import('../views/OperationLogs.vue')
const MultimodalAnalysis = () => import('../views/MultimodalAnalysis.vue')
const BuildingRisk = () => import('../views/BuildingRisk.vue')
const BuildingDetail = () => import('../views/BuildingDetail.vue')
const DecisionLogs = () => import('../views/DecisionLogs.vue')
const AlertCenter = () => import('../views/AlertCenter.vue')
const BatchInspection = () => import('../views/BatchInspection.vue')
const ReportCenter = () => import('../views/ReportCenter.vue')
const UserManagement = () => import('../views/UserManagement.vue')
const RoleManagement = () => import('../views/RoleManagement.vue')
const GisMap = () => import('../views/GisMap.vue')
const FloorPlan = () => import('../views/FloorPlan.vue')
const Maintenance = () => import('../views/Maintenance.vue')
const DutyRoom = () => import('../views/DutyRoom.vue')
const WaterMonitor = () => import('../views/WaterMonitor.vue')
const KeyAreas = () => import('../views/KeyAreas.vue')
const FireArchives = () => import('../views/FireArchives.vue')
const ElectricalFire = () => import('../views/ElectricalFire.vue')
const EmergencyCommand = () => import('../views/EmergencyCommand.vue')
const VideoMonitor = () => import('../views/VideoMonitor.vue')
const FireTraining = () => import('../views/FireTraining.vue')
const GridManagement = () => import('../views/GridManagement.vue')
const FireAssessment = () => import('../views/FireAssessment.vue')
const MiniFireStation = () => import('../views/MiniFireStation.vue')
const HazardManagement = () => import('../views/HazardManagement.vue')
const DataScreen = () => import('../views/DataScreen.vue')
const DailyBrief = () => import('../views/DailyBrief.vue')
const IotDevice = () => import('../views/IotDevice.vue')
const MobileInspection = () => import('../views/MobileInspection.vue')
const DictManagement = () => import('../views/DictManagement.vue')
const OrgManagement = () => import('../views/OrgManagement.vue')
const MessageCenter = () => import('../views/MessageCenter.vue')
const Profile = () => import('../views/Profile.vue')
const SystemMonitor = () => import('../views/SystemMonitor.vue')
const KeyUnitManagement = () => import('../views/KeyUnitManagement.vue')
const FacilityInspection = () => import('../views/FacilityInspection.vue')
const FireAccident = () => import('../views/FireAccident.vue')
const FirePromotion = () => import('../views/FirePromotion.vue')
const SystemAnnouncement = () => import('../views/SystemAnnouncement.vue')

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/no-access', component: NoAccess, meta: { public: true } },
  { path: '/dashboard', component: DataScreen, meta: { permission: 'dashboard' } },
  { path: '/notifications', component: NotificationCenter, meta: { permission: 'notifications' } },
  { path: '/operation-logs', component: OperationLogs, meta: { roles: ['admin'] } },
  { path: '/inspection', component: Inspection, meta: { permission: 'inspection' } },
  { path: '/records', component: Records, meta: { permission: 'records' } },
  { path: '/workorders', component: WorkOrders, meta: { permission: 'workorders' } },
  { path: '/qa', component: QA, meta: { permission: 'qa' } },
  { path: '/learning', component: Learning, meta: { roles: ['admin', 'inspector'] } },
  { path: '/learning-app', component: LearningApp, meta: { roles: ['admin', 'inspector'] } },
  { path: '/knowledge', component: KnowledgeBase, meta: { permission: 'knowledge' } },
  { path: '/knowledge-graph', component: KnowledgeGraph, meta: { permission: 'knowledge' } },
  { path: '/agent-lab', component: AgentLab, meta: { roles: ['admin', 'inspector'] } },
  { path: '/multimodal', component: MultimodalAnalysis, meta: { permission: 'inspection' } },
  { path: '/building-risk', component: BuildingRisk, meta: { permission: 'dashboard' } },
  { path: '/building-detail/:id', component: BuildingDetail, meta: { permission: 'dashboard' } },
  { path: '/gis-map', component: GisMap, meta: { permission: 'dashboard' } },
  { path: '/floor-plan', component: FloorPlan, meta: { roles: ['admin'] } },
  { path: '/maintenance', component: Maintenance, meta: { roles: ['admin'] } },
  { path: '/duty-room', component: DutyRoom, meta: { roles: ['admin'] } },
  { path: '/water-monitor', component: WaterMonitor, meta: { roles: ['admin'] } },
  { path: '/key-areas', component: KeyAreas, meta: { roles: ['admin'] } },
  { path: '/fire-archives', component: FireArchives, meta: { roles: ['admin'] } },
  { path: '/electrical-fire', component: ElectricalFire, meta: { roles: ['admin'] } },
  { path: '/emergency-command', component: EmergencyCommand, meta: { roles: ['admin'] } },
  { path: '/video-monitor', component: VideoMonitor, meta: { roles: ['admin'] } },
  { path: '/fire-training', component: FireTraining, meta: { roles: ['admin'] } },
  { path: '/grid-management', component: GridManagement, meta: { roles: ['admin'] } },
  { path: '/fire-assessment', component: FireAssessment, meta: { roles: ['admin'] } },
  { path: '/mini-fire-station', component: MiniFireStation, meta: { roles: ['admin'] } },
  { path: '/hazard-management', component: HazardManagement, meta: { roles: ['admin'] } },
  { path: '/data-screen', redirect: '/dashboard' },
  { path: '/daily-brief', component: DailyBrief, meta: { roles: ['admin', 'inspector'] } },
  { path: '/iot-device', component: IotDevice, meta: { roles: ['admin'] } },
  { path: '/mobile-inspection', component: MobileInspection, meta: { roles: ['admin', 'inspector'] } },
  { path: '/dict-management', component: DictManagement, meta: { roles: ['admin'] } },
  { path: '/org-management', component: OrgManagement, meta: { roles: ['admin'] } },
  { path: '/message-center', component: MessageCenter, meta: { roles: ['admin', 'inspector', 'rectifier'] } },
  { path: '/profile', component: Profile, meta: { roles: ['admin', 'inspector', 'rectifier', 'viewer'] } },
  { path: '/system-monitor', component: SystemMonitor, meta: { roles: ['admin'] } },
  { path: '/key-unit-management', component: KeyUnitManagement, meta: { roles: ['admin'] } },
  { path: '/facility-inspection', component: FacilityInspection, meta: { roles: ['admin'] } },
  { path: '/fire-accident', component: FireAccident, meta: { roles: ['admin'] } },
  { path: '/fire-promotion', component: FirePromotion, meta: { roles: ['admin', 'inspector'] } },
  { path: '/system-announcement', component: SystemAnnouncement, meta: { roles: ['admin'] } },
  { path: '/decision-logs', component: DecisionLogs, meta: { roles: ['admin', 'inspector'] } },
  { path: '/alert-center', component: AlertCenter, meta: { roles: ['admin', 'inspector'] } },
  { path: '/batch-inspection', component: BatchInspection, meta: { permission: 'batch:view' } },
  { path: '/report-center', component: ReportCenter, meta: { roles: ['admin', 'inspector'] } },
  { path: '/hardware', component: Hardware, meta: { roles: ['admin'] } },
  { path: '/devices', component: Devices, meta: { roles: ['admin'] } },
  { path: '/device-data', component: DeviceData, meta: { roles: ['admin'] } },
  { path: '/telemetry', component: Telemetry, meta: { roles: ['admin'] } },
  { path: '/faults', component: Faults, meta: { roles: ['admin', 'rectifier'] } },
  { path: '/settings', component: Settings, meta: { roles: ['admin'] } },
  { path: '/user-management', component: UserManagement, meta: { roles: ['admin'], permission: 'system:users' } },
  { path: '/role-management', component: RoleManagement, meta: { roles: ['admin'], permission: 'system:roles' } },
  { path: '/evaluation', component: Evaluation, meta: { roles: ['admin'] } },
  { path: '/system-health', component: SystemHealth, meta: { roles: ['admin'] } },
  { path: '/report-print/:id', component: ReportPrint, meta: { permission: 'report' } },
  { path: '/report-verify/:reportNo', component: ReportVerify, meta: { public: true } },
  { path: '/defense', component: Defense, meta: { roles: ['admin'], hidden: true } },
  { path: '/competition', component: Competition, meta: { roles: ['admin'], hidden: true } },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (to.meta?.public) return true
  const user = getCurrentUser()
  if (!user) return { path: '/login', query: { redirect: to.fullPath } }
  if (!canAccessRoute(user, to)) return { path: '/no-access', query: { from: to.fullPath } }
  return true
})

export default router
