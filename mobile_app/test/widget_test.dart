import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fire_ai_agent_mobile/pages/dashboard_page.dart';
import 'package:fire_ai_agent_mobile/pages/login_page.dart';
import 'package:fire_ai_agent_mobile/services/api_client.dart';
import 'package:fire_ai_agent_mobile/services/api_service.dart';
import 'package:fire_ai_agent_mobile/services/app_services.dart';
import 'package:fire_ai_agent_mobile/widgets/common.dart';

const Map<String, String> _jsonHeaders = {
  'content-type': 'application/json; charset=utf-8',
};

http.Response _ok(Object body) =>
    http.Response(jsonEncode(body), 200, headers: _jsonHeaders);

/// 按路径分发的假后端，只覆盖测试用到的接口
MockClient _fakeBackend({
  Object? loginResponse,
  int loginStatus = 200,
  Object? homeResponse,
}) {
  return MockClient((request) async {
    switch (request.url.path) {
      case '/api/auth/login':
        return http.Response(
          jsonEncode(loginResponse ?? {'ok': true, 'message': '登录成功'}),
          loginStatus,
          headers: _jsonHeaders,
        );
      case '/api/auth/me':
        return _ok({
          'ok': true,
          'user': {
            'id': 1,
            'username': 'inspector',
            'real_name': '张三',
            'role': 'inspector',
            'role_name': '巡检员',
            'permissions': ['inspection:run'],
          },
        });
      case '/api/notifications/summary':
        return _ok({'total': 4, 'unread': 3});
      case '/api/mobile/home':
        return _ok(homeResponse ??
            {
              'user': {'id': 1, 'name': '张三', 'role': '巡检员'},
              'stats': {
                'pendingAlerts': 2,
                'claimableWorkorders': 1,
                'myWorkorders': 3,
                'todayInspections': 5,
                'todayAlerts': 2,
                'deviceCount': 42,
              },
              'pendingAlerts': [
                {
                  'type': 'alert',
                  'id': 11,
                  'code': 'AL-1',
                  'title': '烟感报警',
                  'severity': 'high',
                  'severityLabel': '高',
                  'status': 'pending',
                  'statusLabel': '待处置',
                  'location': '机房',
                  'createdAt': '2026-09-19T02:00:00',
                }
              ],
              'claimableWorkorders': [],
              'myWorkorders': [],
            });
      case '/api/mobile/tasks':
        return _ok({
          'total': 1,
          'workorderCount': 0,
          'alertCount': 1,
          'items': [
            {
              'type': 'alert',
              'id': 11,
              'code': 'AL-1',
              'title': '烟感报警',
              'severity': 'high',
              'severityLabel': '高',
              'status': 'pending',
              'statusLabel': '待处置',
              'location': '机房',
              'createdAt': '2026-09-19T02:00:00',
            }
          ],
        });
      default:
        return http.Response(jsonEncode({'detail': '未覆盖的接口'}), 404, headers: _jsonHeaders);
    }
  });
}

void main() {
  setUp(() {
    session.clear();
  });

  testWidgets('登录页渲染账号密码与登录按钮', (tester) async {
    api = ApiService(
      client: ApiClient(
        client: _fakeBackend(),
        tokenStore: InMemoryTokenStore(),
        baseUrl: 'http://test.local',
      ),
    );

    await tester.pumpWidget(const MaterialApp(home: LoginPage()));

    expect(find.text('智慧消防巡检'), findsOneWidget);
    expect(find.text('账号'), findsOneWidget);
    expect(find.text('密码'), findsOneWidget);
    expect(find.text('登 录'), findsOneWidget);
    // 真机调试排查用：当前后端地址要显示出来
    expect(find.textContaining('http://test.local'), findsOneWidget);
  });

  testWidgets('空表单提交时给出校验提示，不发请求', (tester) async {
    var loginCalled = false;
    api = ApiService(
      client: ApiClient(
        client: MockClient((request) async {
          loginCalled = true;
          return _ok({'ok': true});
        }),
        tokenStore: InMemoryTokenStore(),
        baseUrl: 'http://test.local',
      ),
    );

    await tester.pumpWidget(const MaterialApp(home: LoginPage()));
    await tester.tap(find.text('登 录'));
    await tester.pump();

    expect(find.text('请输入账号'), findsOneWidget);
    expect(find.text('请输入密码'), findsOneWidget);
    expect(loginCalled, isFalse);
  });

  testWidgets('登录成功保存令牌并进入主界面', (tester) async {
    api = ApiService(
      client: ApiClient(
        client: _fakeBackend(
          loginResponse: {
            'ok': true,
            'access_token': 'access-1',
            'refresh_token': 'refresh-1',
            'message': '登录成功',
          },
        ),
        tokenStore: InMemoryTokenStore(),
        baseUrl: 'http://test.local',
      ),
    );

    await tester.pumpWidget(MaterialApp(
      routes: {
        '/login': (context) => const LoginPage(),
        '/main': (context) => const Scaffold(body: Text('主界面占位')),
      },
      home: const LoginPage(),
    ));

    await tester.enterText(find.byType(TextFormField).first, 'inspector');
    await tester.enterText(find.byType(TextFormField).last, 'Passw0rd!');
    await tester.tap(find.text('登 录'));
    await tester.pumpAndSettle();

    expect(api.client.isLoggedIn, isTrue);
    expect(api.client.accessToken, 'access-1');
    expect(find.text('主界面占位'), findsOneWidget);
    expect(session.displayName, '张三');
    expect(session.unreadNotifications, 3);
  });

  testWidgets('登录失败把后端原因显示在居中错误框里', (tester) async {
    api = ApiService(
      client: ApiClient(
        client: _fakeBackend(
          loginResponse: {'ok': false, 'message': '用户名或密码错误'},
          loginStatus: 401,
        ),
        tokenStore: InMemoryTokenStore(),
        baseUrl: 'http://test.local',
      ),
    );

    await tester.pumpWidget(const MaterialApp(home: LoginPage()));
    await tester.enterText(find.byType(TextFormField).first, 'inspector');
    await tester.enterText(find.byType(TextFormField).last, 'wrong');
    await tester.tap(find.text('登 录'));
    await tester.pump();

    expect(find.text('用户名或密码错误'), findsOneWidget);
    expect(api.client.isLoggedIn, isFalse);
  });

  testWidgets('首页用真实接口数据渲染统计与待办', (tester) async {
    api = ApiService(
      client: ApiClient(
        client: _fakeBackend(),
        tokenStore: InMemoryTokenStore(accessToken: 't'),
        baseUrl: 'http://test.local',
      ),
    );

    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: DashboardPage()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('张三，今日概览'), findsOneWidget);
    expect(find.text('待处理告警'), findsOneWidget);
    expect(find.text('2'), findsWidgets); // pendingAlerts
    expect(find.text('常用功能'), findsOneWidget);
    expect(find.text('今日待办'), findsOneWidget);
    expect(find.text('烟感报警'), findsOneWidget);
  });

  testWidgets('接口失败时显示错误态与重试按钮', (tester) async {
    api = ApiService(
      client: ApiClient(
        client: MockClient((request) async =>
            http.Response(jsonEncode({'detail': '数据库连接失败'}), 500, headers: _jsonHeaders)),
        tokenStore: InMemoryTokenStore(accessToken: 't'),
        baseUrl: 'http://test.local',
      ),
    );

    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: DashboardPage()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('数据库连接失败'), findsOneWidget);
    expect(find.text('重试'), findsOneWidget);
  });

  testWidgets('时间格式化把后端 UTC 时间转成本地时区', (tester) async {
    // 后端返回不带时区后缀的 UTC 时间，直接 parse 会被当成本地时间（差 8 小时）
    final parsed = parseServerTime('2026-09-19T02:00:00');
    expect(parsed, isNotNull);
    expect(parsed!.toUtc().hour, 2);
    expect(parsed.isUtc, isFalse);

    expect(formatFullTime(''), '—');
    expect(formatShortTime('not-a-time'), '—');
  });
}
