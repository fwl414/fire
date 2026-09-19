import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fire_ai_agent_mobile/services/api_client.dart';

const Map<String, String> _jsonHeaders = {
  'content-type': 'application/json; charset=utf-8',
};

/// 造一个只有 exp 的假 JWT：只用来验证「是否临近过期」，不做签名校验
String _jwt({required Duration expiresIn}) {
  String segment(Map<String, dynamic> value) => base64Url
      .encode(utf8.encode(jsonEncode(value)))
      .replaceAll('=', '');
  final payload = {
    'sub': '1',
    'exp': DateTime.now().toUtc().add(expiresIn).millisecondsSinceEpoch ~/ 1000,
  };
  return '${segment({'alg': 'HS256', 'typ': 'JWT'})}.${segment(payload)}.sig';
}

ApiClient _client(
  MockClient mock, {
  String? accessToken,
  String? refreshToken,
  void Function()? onUnauthorized,
}) {
  return ApiClient(
    client: mock,
    tokenStore: InMemoryTokenStore(accessToken: accessToken, refreshToken: refreshToken),
    baseUrl: 'http://test.local',
    onUnauthorized: onUnauthorized,
  );
}

void main() {
  group('响应解析：后端两种返回结构都要吃得下', () {
    test('裸数组原样返回（/api/records）', () async {
      final api = _client(
        MockClient((request) async =>
            http.Response(jsonEncode([{'id': 1}, {'id': 2}]), 200, headers: _jsonHeaders)),
        accessToken: 't',
      );

      final data = await api.get('/api/records');

      expect(data, isA<List<dynamic>>());
      expect((data as List).length, 2);
    });

    test('裸对象原样返回（/api/dashboard/stats）', () async {
      final api = _client(
        MockClient((request) async =>
            http.Response(jsonEncode({'total_devices': 7}), 200, headers: _jsonHeaders)),
        accessToken: 't',
      );

      final data = await api.get('/api/dashboard/stats');

      expect(data, isA<Map<String, dynamic>>());
      expect((data as Map)['total_devices'], 7);
    });

    test('{items,total} 分页结构原样返回', () async {
      final api = _client(
        MockClient((request) async => http.Response(
            jsonEncode({
              'items': [
                {'id': 3}
              ],
              'total': 1,
            }),
            200,
            headers: _jsonHeaders)),
        accessToken: 't',
      );

      final data = await api.get('/api/devices');

      expect((data as Map)['total'], 1);
      expect(asFirstId(data), 3);
    });

    test('{ok,code,message,data} 包装体拆出 data', () async {
      final api = _client(
        MockClient((request) async => http.Response(
            jsonEncode({
              'ok': true,
              'code': 0,
              'message': '成功',
              'data': {'total': 9},
            }),
            200,
            headers: _jsonHeaders)),
        accessToken: 't',
      );

      final data = await api.get('/api/wrapped');

      expect(data, isA<Map<String, dynamic>>());
      expect((data as Map)['total'], 9);
    });

    test('中文内容按 UTF-8 解码不乱码', () async {
      final api = _client(
        MockClient((request) async => http.Response(
            jsonEncode({'message': '设备不存在'}), 200, headers: _jsonHeaders)),
        accessToken: 't',
      );

      final data = await api.get('/api/anything');

      expect((data as Map)['message'], '设备不存在');
    });

    test('业务错误取后端 detail 作为提示文案', () async {
      final api = _client(
        MockClient((request) async =>
            http.Response(jsonEncode({'detail': '工单不存在'}), 404, headers: _jsonHeaders)),
        accessToken: 't',
      );

      expect(
        () => api.get('/api/workorders/1'),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', '工单不存在')
            .having((e) => e.statusCode, 'statusCode', 404)),
      );
    });

    test('无 detail 时按状态码给人话', () async {
      final api = _client(
        MockClient((request) async => http.Response('', 403)),
        accessToken: 't',
      );

      expect(
        () => api.get('/api/forbidden'),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', '当前账号没有该操作权限')),
      );
    });
  });

  group('鉴权', () {
    test('请求自动带 Authorization: Bearer', () async {
      String? seenAuth;
      final api = _client(
        MockClient((request) async {
          seenAuth = request.headers['Authorization'];
          return http.Response(jsonEncode({'ok': true}), 200, headers: _jsonHeaders);
        }),
        accessToken: 'token-abc',
      );

      await api.get('/api/auth/me');

      expect(seenAuth, 'Bearer token-abc');
    });

    test('登录接口不带令牌（auth: false）', () async {
      String? seenAuth;
      final api = _client(MockClient((request) async {
        seenAuth = request.headers['Authorization'];
        return http.Response(jsonEncode({'ok': true}), 200, headers: _jsonHeaders);
      }));

      await api.postForm('/api/auth/login', form: {'username': 'a'}, auth: false);

      expect(seenAuth, isNull);
    });

    test('401 且没有刷新令牌 → 清空令牌 + 触发回调 + 抛 401', () async {
      var notified = false;
      final store = InMemoryTokenStore(accessToken: 'expired');
      final api = ApiClient(
        client: MockClient((request) async => http.Response('', 401)),
        tokenStore: store,
        baseUrl: 'http://test.local',
        onUnauthorized: () => notified = true,
      );

      await expectLater(
        api.get('/api/devices'),
        throwsA(isA<ApiException>().having((e) => e.isUnauthorized, 'isUnauthorized', true)),
      );

      expect(notified, isTrue);
      expect(await store.readAccessToken(), isNull);
      expect(api.isLoggedIn, isFalse);
    });

    test('401 后自动用刷新令牌换新令牌并重放原请求', () async {
      final requests = <String>[];
      final authorizations = <String?>[];
      var protectedCalls = 0;

      final api = _client(
        MockClient((request) async {
          requests.add(request.url.path);
          authorizations.add(request.headers['Authorization']);
          if (request.url.path == '/api/auth/refresh') {
            return http.Response(
                jsonEncode({'ok': true, 'access_token': 'new-token'}), 200, headers: _jsonHeaders);
          }
          protectedCalls += 1;
          if (protectedCalls == 1) return http.Response('', 401);
          return http.Response(jsonEncode({'ok': true, 'total': 5}), 200, headers: _jsonHeaders);
        }),
        accessToken: 'old-token',
        refreshToken: 'refresh-1',
      );

      final data = await api.get('/api/devices');

      expect(requests, ['/api/devices', '/api/auth/refresh', '/api/devices']);
      expect(authorizations, ['Bearer old-token', 'Bearer old-token', 'Bearer new-token']);
      expect((data as Map)['total'], 5);
      expect(api.accessToken, 'new-token');
    });

    test('刷新接口也失败时不再重试，直接回登录', () async {
      var notified = false;
      final api = _client(
        MockClient((request) async => http.Response('', 401)),
        accessToken: 'old-token',
        refreshToken: 'bad-refresh',
        onUnauthorized: () => notified = true,
      );

      await expectLater(api.get('/api/devices'), throwsA(isA<ApiException>()));
      expect(notified, isTrue);
      expect(api.isLoggedIn, isFalse);
    });
  });

  group('提前续期', () {
    test('JWT exp 未临近时不刷新', () async {
      var refreshCalled = false;
      final api = _client(
        MockClient((request) async {
          if (request.url.path == '/api/auth/refresh') refreshCalled = true;
          return http.Response(jsonEncode({'ok': true}), 200, headers: _jsonHeaders);
        }),
        accessToken: _jwt(expiresIn: const Duration(hours: 6)),
        refreshToken: 'refresh-1',
      );

      expect(await api.refreshIfNeeded(), isFalse);
      expect(refreshCalled, isFalse);
    });

    test('JWT 临近过期时刷新并更新令牌', () async {
      final api = _client(
        MockClient((request) async {
          if (request.url.path == '/api/auth/refresh') {
            return http.Response(
                jsonEncode({'ok': true, 'access_token': 'refreshed'}), 200, headers: _jsonHeaders);
          }
          return http.Response('', 404);
        }),
        accessToken: _jwt(expiresIn: const Duration(minutes: 10)),
        refreshToken: 'refresh-1',
      );

      expect(await api.refreshIfNeeded(), isTrue);
      expect(api.accessToken, 'refreshed');
    });

    test('不是 JWT 的令牌不尝试续期（不误判）', () async {
      final api = _client(
        MockClient((request) async => http.Response('', 500)),
        accessToken: 'not-a-jwt',
        refreshToken: 'refresh-1',
      );

      expect(ApiClient.jwtExpiry('not-a-jwt'), isNull);
      expect(await api.refreshIfNeeded(), isFalse);
    });
  });
}

int asFirstId(Map<dynamic, dynamic> data) {
  final items = data['items'] as List<dynamic>;
  return (items.first as Map)['id'] as int;
}
