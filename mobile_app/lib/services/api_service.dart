import 'api_client.dart';

/// 解析辅助：后端字段命名有 snake_case 也有 camelCase（`/api/mobile/*` 用 camelCase），
/// 页面里统一用这些函数取值，避免到处写 `as Map` 导致运行时崩溃。
Map<String, dynamic> asMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<dynamic> asList(dynamic value) => value is List ? value : const <dynamic>[];

List<Map<String, dynamic>> asMapList(dynamic value) =>
    asList(value).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();

String textOf(dynamic value, {String fallback = ''}) {
  if (value == null) return fallback;
  final text = '$value';
  return text.isEmpty ? fallback : text;
}

double numOf(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? 0;
}

int intOf(dynamic value) {
  if (value is num) return value.toInt();
  return int.tryParse('$value') ?? 0;
}

/// 业务接口层：所有后端调用集中在这里，页面不拼 URL、不管鉴权。
///
/// 契约要点（都是踩过的坑）：
/// - 登录 / 刷新 / 改密 / 问答 / 故障状态在后端是 **Form**，不是 JSON
/// - `/api/records`、`/api/faults` 返回**裸数组**，`/api/dashboard/stats` 返回**裸对象**
/// - `/api/devices`、`/api/workorders`、`/api/alert/list` 返回 `{items, total, ...}`
/// - 工单状态机只认中文值：待受理 / 处理中 / 待复查 / 已完成 / 已关闭
/// - 告警状态只认英文值：pending / processing / resolved
class ApiService {
  ApiService({ApiClient? client}) : client = client ?? ApiClient();

  final ApiClient client;

  // ---------------- 认证 ----------------

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    final data = await client.postForm(
      '/api/auth/login',
      form: {'username': username, 'password': password},
      auth: false,
    );
    final map = asMap(data);
    final accessToken = textOf(map['access_token']);
    if (accessToken.isEmpty) {
      throw ApiException('登录响应异常：未返回访问令牌');
    }
    await client.saveTokens(
      accessToken: accessToken,
      refreshToken: textOf(map['refresh_token']),
    );
    return map;
  }

  Future<Map<String, dynamic>> me() async => asMap(await client.get('/api/auth/me'));

  /// 登出：先去后端把当前令牌拉黑，再清本地令牌（后端失败也要清，否则用户卡在登录态）
  Future<void> logout() async {
    try {
      await client.postJson('/api/auth/logout');
    } finally {
      await client.clearTokens();
    }
  }

  Future<Map<String, dynamic>> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    return asMap(await client.postForm(
      '/api/auth/change-password',
      form: {'old_password': oldPassword, 'new_password': newPassword},
    ));
  }

  // ---------------- 移动端协同（/api/mobile/*，为一线人员聚合的接口） ----------------

  /// 首页概览：真实待办统计 + 待处理告警 / 我的工单 / 可领取工单
  Future<Map<String, dynamic>> home() async => asMap(await client.get('/api/mobile/home'));

  /// 我的待办：指派给我的工单 + 待处理告警合成一个列表
  Future<Map<String, dynamic>> tasks({int limit = 50}) async =>
      asMap(await client.get('/api/mobile/tasks', query: {'limit': limit}));

  /// 领取工单：指派给自己并进入「处理中」；已被别人领走时后端会返回原因
  Future<Map<String, dynamic>> claimWorkorder(int orderId) async =>
      asMap(await client.postJson('/api/mobile/workorders/$orderId/claim'));

  /// 现场上报：拍照 + 描述 → 巡检 Agent 分析 → 落巡检记录
  Future<Map<String, dynamic>> submitReport({
    int? buildingId,
    int? deviceId,
    String location = '',
    String description = '',
    String? imagePath,
  }) async {
    final fields = <String, String>{
      'location': location,
      'description': description,
    };
    if (buildingId != null) fields['building_id'] = '$buildingId';
    if (deviceId != null) fields['device_id'] = '$deviceId';
    return asMap(await client.multipart(
      '/api/mobile/report',
      fields: fields,
      files: {if (imagePath != null) 'file': imagePath},
    ));
  }

  // ---------------- 设备 / 巡检记录 ----------------

  /// 建筑列表：后端 `/api/buildings` 返回**裸数组**（不是 `{items,...}` 分页体），
  /// 字段为 `id / building_code / building_name / building_type / address / risk_level …`。
  Future<List<Map<String, dynamic>>> buildings() async =>
      asMapList(await client.get('/api/buildings'));

  Future<Map<String, dynamic>> devices({
    int page = 1,
    int pageSize = 50,
    String? keyword,
    String? status,
  }) async {
    return asMap(await client.get('/api/devices', query: {
      'page': page,
      'page_size': pageSize,
      if (keyword != null && keyword.isNotEmpty) 'keyword': keyword,
      if (status != null && status.isNotEmpty) 'status': status,
    }));
  }

  Future<Map<String, dynamic>> deviceDetail(int deviceId) async =>
      asMap(await client.get('/api/devices/$deviceId/detail'));

  /// 巡检记录列表（后端返回裸数组）
  Future<List<Map<String, dynamic>>> records() async =>
      asMapList(await client.get('/api/records'));

  /// 巡检记录详情（含 report 正文，列表接口不返回）
  Future<Map<String, dynamic>> recordDetail(int recordId) async =>
      asMap(await client.get('/api/records/$recordId'));

  /// 巡检记录现场照片的下载请求（**需要 Bearer token**，不做匿名访问）。
  ///
  /// 主库巡检记录（数字 id）与运行库巡检档案（字符串 id，如 `REC-M-1`）都支持；
  /// `index` 用于取第 N 张图；记录没有图片或文件缺失时后端返回 404，
  /// 调用方必须用 `errorBuilder` 兜底成「暂无图片证据」占位。
  BinaryRequest recordImageRequest(Object recordId, {int index = 0}) =>
      client.binaryRequest('/api/records/$recordId/image', query: {'index': index});

  // ---------------- 告警 ----------------

  Future<Map<String, dynamic>> alerts({
    String? severity,
    String? alertType,
    int limit = 50,
  }) async {
    return asMap(await client.get('/api/alert/list', query: {
      'limit': limit,
      if (severity != null && severity.isNotEmpty) 'severity': severity,
      if (alertType != null && alertType.isNotEmpty) 'alert_type': alertType,
    }));
  }

  Future<Map<String, dynamic>> alertDetail(int alertId) async =>
      asMap(await client.get('/api/alerts/$alertId'));

  /// 告警状态：pending / processing / resolved
  Future<Map<String, dynamic>> updateAlertStatus(int alertId, String status) async =>
      asMap(await client.putJson('/api/alerts/$alertId/status', body: {'status': status}));

  /// 告警处置：填写处置结果并结单
  Future<Map<String, dynamic>> handleAlert(
    int alertId, {
    required String handleResult,
    String status = 'resolved',
  }) async {
    return asMap(await client.postJson('/api/alerts/$alertId/handle', body: {
      'handle_result': handleResult,
      'status': status,
    }));
  }

  // ---------------- 工单 ----------------

  Future<Map<String, dynamic>> workorders({
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    return asMap(await client.get('/api/workorders', query: {
      'page': page,
      'page_size': pageSize,
      if (status != null && status.isNotEmpty) 'status': status,
    }));
  }

  Future<Map<String, dynamic>> workorderDetail(int orderId) async =>
      asMap(await client.get('/api/workorders/$orderId'));

  /// 新建工单（需要 workorders:create 权限）
  Future<Map<String, dynamic>> createWorkorder({
    required String title,
    required String description,
    int? deviceId,
    int? buildingId,
    String buildingName = '',
    String riskLevel = '',
    String priority = '中',
    String location = '',
    String ticketType = '现场上报',
  }) async {
    return asMap(await client.postJson('/api/workorders', body: {
      'title': title,
      'description': description,
      'device_id': deviceId,
      'building_id': buildingId,
      'building_name': buildingName,
      'risk_level': riskLevel,
      'priority': priority,
      'location': location,
      'ticket_type': ticketType,
      'status': '待受理',
    }));
  }

  /// 工单状态流转：待受理 / 处理中 / 待复查 / 已完成 / 已关闭
  Future<Map<String, dynamic>> updateWorkorderStatus(int orderId, String status) async =>
      asMap(await client.postJson('/api/workorders/$orderId/status', body: {'status': status}));

  // ---------------- 消防知识问答 ----------------

  /// 后端要求 Form 参数（老代码用 JSON body，必然 422）
  Future<Map<String, dynamic>> askFire(String question) async =>
      asMap(await client.postForm('/api/qa/fire', form: {'question': question}));

  // ---------------- 站内通知 ----------------

  Future<Map<String, dynamic>> notifications({int limit = 20}) async =>
      asMap(await client.get('/api/notifications', query: {'limit': limit}));

  Future<Map<String, dynamic>> notificationSummary() async =>
      asMap(await client.get('/api/notifications/summary'));

  Future<void> markAllNotificationsRead() async {
    await client.postJson('/api/notifications/mark-all-read');
  }

  /// 单条通知已读：`POST /api/notifications/{id}/read`，
  /// 返回 `{message, id, read_count}`；通知 id 是字符串（如 `high-order-WO-…`）。
  Future<Map<String, dynamic>> markNotificationRead(String notificationId) async =>
      asMap(await client.postJson(
        '/api/notifications/${Uri.encodeComponent(notificationId)}/read',
      ));

  // ---------------- 巡检档案（V1.0.0 报告与档案） ----------------

  /// 档案列表：后端返回**裸数组**（不是 `{items,total}`），
  /// 关键词 / 风险等级 / 复查状态 / 归档状态 / 日期区间都**由服务端过滤**。
  Future<List<Map<String, dynamic>>> archives({
    String keyword = '',
    String riskLevel = '',
    String reviewStatus = '',
    String archiveStatus = '',
    String startDate = '',
    String endDate = '',
    int limit = 200,
  }) async =>
      asMapList(await client.get('/api/inspection-archives', query: {
        'keyword': keyword,
        'risk_level': riskLevel,
        'review_status': reviewStatus,
        'archive_status': archiveStatus,
        'start_date': startDate,
        'end_date': endDate,
        'limit': limit,
      }));

  /// 档案概览：`archive_count / report_count / high_risk_count / pending_review_count /
  /// workorder_count / closed_workorder_count / closed_loop_rate /
  /// risk_distribution / review_distribution / top_hazards / monthly_trend`
  Future<Map<String, dynamic>> archiveDashboard() async =>
      asMap(await client.get('/api/inspection-archives/dashboard'));

  /// 档案详情。`record_id` 是**字符串**（`REC-M-1`、`DEMO-INSPECTION-001`），
  /// 字段比列表多了 `quality / hazard_details / rag_references / closure_status /
  /// archive_timeline / before_after_images` 等。
  Future<Map<String, dynamic>> archiveDetail(String recordId) async =>
      asMap(await client.get('/api/inspection-archives/${Uri.encodeComponent(recordId)}'));

  // ---------------- 批量巡检任务 ----------------

  /// 批量巡检任务列表。注意后端**只**返回
  /// `id/task_name/building_name/total_count/completed_count/status/priority/
  /// inspector/created_at/started_at/completed_at`（没有进度百分比、没有 scheduled_time）。
  Future<Map<String, dynamic>> batchInspections({
    String status = '',
    String buildingId = '',
    int limit = 50,
  }) async =>
      asMap(await client.get('/api/batch-inspection/list', query: {
        'status': status,
        'building_id': buildingId,
        'limit': limit,
      }));

  /// 批量巡检任务详情：含 `inspection_items`（原始巡检点）与 `results`（逐点结果）、`progress`。
  Future<Map<String, dynamic>> batchInspectionDetail(String taskId) async =>
      asMap(await client.get('/api/batch-inspection/${Uri.encodeComponent(taskId)}'));

  /// 批量巡检任务进度：`progress / progress_message / current_item / completed_count /
  /// total_count / high_risk_count / medium_risk_count / low_risk_count / error`
  /// （后端没有「成功/失败条数」字段，前端不编造）。
  Future<Map<String, dynamic>> batchInspectionProgress(String taskId) async =>
      asMap(await client.get(
        '/api/batch-inspection/${Uri.encodeComponent(taskId)}/progress',
      ));

  /// 新建批量巡检任务（需要 `batch:create` 权限）。
  /// 后端所有字段都有默认值：不传 `inspection_items` 时按楼宇通用清单生成 10 个点位。
  Future<Map<String, dynamic>> createBatchInspection({
    required String taskName,
    String buildingName = '',
    String inspector = '',
    String priority = '中',
  }) async =>
      asMap(await client.postJson('/api/batch-inspection/create', body: {
        'task_name': taskName,
        'building_name': buildingName,
        'inspector': inspector,
        'priority': priority,
      }));

  // ---------------- 智能分析 ----------------

  /// 每日安全简报；`date` 传 `YYYY-MM-DD`，不传时后端默认统计**昨天**。
  Future<Map<String, dynamic>> dailyBrief({String date = ''}) async =>
      asMap(await client.get('/api/intelligence/daily-brief', query: {'date': date}));

  /// 设备故障诊断。`device_id` 是字符串且可空：带了（且属于本租户）后端会用设备台账
  /// （投用年限 / 维保 / 最近上报）调整权重，`weight_basis` 为 `device_data`，否则退回知识库先验。
  Future<Map<String, dynamic>> diagnoseDevice({
    String deviceId = '',
    String deviceName = '',
    String deviceType = '',
    String status = '故障',
    String buildingName = '',
  }) async =>
      asMap(await client.postJson('/api/intelligence/diagnose-device', body: {
        'device_id': deviceId,
        'device_name': deviceName,
        'device_type': deviceType,
        'status': status,
        'building_name': buildingName,
      }));

  // ---------------- 报告验真 ----------------

  /// 报告验真：公开接口（`auth: false`），传报告编号或档案编号都可以。
  Future<Map<String, dynamic>> verifyReport(String reportNo) async => asMap(
        await client.get(
          '/api/reports/verify/${Uri.encodeComponent(reportNo)}',
          auth: false,
        ),
      );

  /// 报告验真二维码：后端返回 PNG（同样是公开接口），
  /// 交给 `Image.network` 时带上鉴权头没有副作用（`widgets/common.dart` 的用法一致）。
  BinaryRequest reportVerifyQrRequest(String reportNo) => client.binaryRequest(
        '/api/reports/verify-qr/${Uri.encodeComponent(reportNo)}',
      );

  // ---------------- 告警统计与合并 ----------------

  /// 告警统计：**扁平**字段（没有 by_severity 之类的嵌套）——
  /// `total/pending/processing/resolved/merged/escalated/critical/high/medium/low/
  /// todayCount/thisWeek`，外加 `byType[{type,count}]` 与 `trend[{date,count}]`。
  Future<Map<String, dynamic>> alertStatistics() async =>
      asMap(await client.get('/api/alert/statistics'));

  /// 合并告警：以 `primary_id` 为主告警，`duplicate_ids` 被合并（累加重复次数并标记 merged）。
  /// 主告警不存在时后端返回 404，参数缺失返回 400，错误原因在 `detail` 里。
  Future<Map<String, dynamic>> mergeAlerts({
    required int primaryId,
    required List<int> duplicateIds,
  }) async =>
      asMap(await client.postJson('/api/alerts/merge', body: {
        'primary_id': primaryId,
        'duplicate_ids': duplicateIds,
      }));
}
