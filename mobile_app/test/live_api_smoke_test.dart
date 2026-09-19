// 联调冒烟测试：用**真实后端**验证 App 的接口层（不是 mock）。
//
//   1) 先在另一个终端起后端：cd backend && python -m uvicorn main:app --port 8000
//   2) flutter test test/live_api_smoke_test.dart
//
// 后端没起时会**整组跳过**（打印 SKIP），不会让 CI/本地测试变红。
// 账号可用 SMOKE_USER / SMOKE_PASSWORD 覆盖，默认用开发库的 admin/123456。
//
// 注意：这里只用 flutter_test 的 `test()`，不初始化 widget binding，
// 因此不会被 flutter_test 的 HttpOverrides 拦截，可以发真实请求。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:fire_ai_agent_mobile/services/api_client.dart';
import 'package:fire_ai_agent_mobile/services/api_service.dart';

const String _baseUrl = String.fromEnvironment('SMOKE_BASE_URL', defaultValue: 'http://127.0.0.1:8000');

Future<bool> _backendAlive() async {
  try {
    final response = await http
        .get(Uri.parse('$_baseUrl/health'))
        .timeout(const Duration(seconds: 3));
    return response.statusCode == 200;
  } catch (_) {
    return false;
  }
}

void main() {
  late ApiClient client;
  late ApiService api;
  var alive = false;

  setUpAll(() async {
    alive = await _backendAlive();
    if (!alive) {
      stdout.writeln('SKIP 后端未在 $_baseUrl 运行，跳过联调冒烟（先启动 uvicorn 再跑）');
    }
  });

  setUp(() {
    client = ApiClient(
      tokenStore: InMemoryTokenStore(),
      baseUrl: _baseUrl,
      timeout: const Duration(seconds: 30),
    );
    api = ApiService(client: client);
  });

  test('登录 → 各业务接口 → 登出（真实后端）', () async {
    if (!alive) return;

    final username = Platform.environment['SMOKE_USER'] ?? 'admin';
    final password = Platform.environment['SMOKE_PASSWORD'] ?? '123456';

    // 1. 登录（后端是 Form 参数）
    await api.login(username: username, password: password);
    expect(client.isLoggedIn, isTrue, reason: '登录后应保存令牌');
    expect(client.accessToken, isNotEmpty);
    stdout.writeln('  登录成功，令牌长度 ${client.accessToken!.length}');

    // 2. 当前用户
    final me = asMap((await api.me())['user']);
    expect(textOf(me['username']), isNotEmpty);
    stdout.writeln('  用户：${textOf(me['real_name'], fallback: textOf(me['username']))}'
        ' / ${textOf(me['role_name'], fallback: textOf(me['role']))}');

    // 3. 移动端首页（App 首页数据源）
    final home = await api.home();
    final stats = asMap(home['stats']);
    expect(home.containsKey('stats'), isTrue);
    stdout.writeln('  首页统计：待处理告警 ${intOf(stats['pendingAlerts'])}'
        '，我的在办 ${intOf(stats['myWorkorders'])}'
        '，可领取 ${intOf(stats['claimableWorkorders'])}'
        '，设备 ${intOf(stats['deviceCount'])}');

    // 4. 我的待办
    final tasks = await api.tasks(limit: 20);
    expect(tasks['items'], isA<List<dynamic>>());
    stdout.writeln('  待办 ${intOf(tasks['total'])} 条'
        '（工单 ${intOf(tasks['workorderCount'])} / 告警 ${intOf(tasks['alertCount'])}）');

    // 5. 告警列表 + 详情
    final alerts = await api.alerts(limit: 10);
    final alertItems = asMapList(alerts['items']);
    stdout.writeln('  告警 ${intOf(alerts['total'])} 条');
    if (alertItems.isNotEmpty) {
      final detail = await api.alertDetail(intOf(alertItems.first['id']));
      expect(textOf(detail['alert_code']), isNotEmpty);
      stdout.writeln('  告警详情：${textOf(detail['alert_code'])}（${textOf(detail['status'])}）');
    }

    // 6. 工单列表 + 详情
    final orders = await api.workorders(pageSize: 10);
    final orderItems = asMapList(orders['items']);
    stdout.writeln('  工单 ${intOf(orders['total'])} 条');
    if (orderItems.isNotEmpty) {
      final detail = await api.workorderDetail(intOf(orderItems.first['id']));
      expect(textOf(detail['title']), isNotEmpty);
      stdout.writeln('  工单详情：${textOf(detail['title'])}（${textOf(detail['status'])}）');
    }

    // 7. 设备台账 + 设备详情
    final devices = await api.devices(pageSize: 10);
    final deviceItems = asMapList(devices['items']);
    expect(devices['items'], isA<List<dynamic>>());
    stdout.writeln('  设备 ${intOf(devices['total'])} 台');
    if (deviceItems.isNotEmpty) {
      final detail = await api.deviceDetail(intOf(deviceItems.first['id']));
      final device = asMap(detail['device']);
      expect(textOf(device['name']), isNotEmpty);
      stdout.writeln('  设备详情：${textOf(device['name'])}，最近告警 ${asList(detail['recentAlarms']).length} 条');
    }

    // 8. 巡检记录（裸数组）+ 详情
    final records = await api.records();
    stdout.writeln('  巡检记录 ${records.length} 条');
    if (records.isNotEmpty) {
      final detail = await api.recordDetail(intOf(records.first['id']));
      expect(detail.containsKey('risk_score'), isTrue);
      stdout.writeln('  记录详情：风险分 ${textOf(detail['risk_score'])}，报告长度 ${textOf(detail['report']).length}');
    }

    // 9. 通知与未读数（铃铛角标数据源）
    final notifications = await api.notifications(limit: 10);
    final summary = await api.notificationSummary();
    expect(notifications['items'], isA<List<dynamic>>());
    stdout.writeln('  通知 ${asList(notifications['items']).length} 条，未读 ${intOf(summary['unread'])}');

    // 10. 登出应同时清掉本地令牌
    await api.logout();
    expect(client.isLoggedIn, isFalse, reason: '登出后本地令牌必须清除');
  });

  test('未登录时访问业务接口应被判为未授权', () async {
    if (!alive) return;

    await expectLater(
      api.home(),
      throwsA(isA<ApiException>().having((e) => e.isUnauthorized, 'isUnauthorized', isTrue)),
    );
  });

  test('错误的账号密码返回后端提示文案', () async {
    if (!alive) return;

    await expectLater(
      api.login(username: 'admin', password: 'definitely-wrong-password'),
      throwsA(isA<ApiException>()),
    );
  });
}
