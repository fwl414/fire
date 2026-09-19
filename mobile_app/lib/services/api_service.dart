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
}
