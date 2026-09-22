import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// 后端返回的业务错误：4xx/5xx、超时、网络不可达都统一成这一类，
/// 页面只需要 `catch (ApiException e)` 就能拿到可直接展示的中文原因。
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.path});

  final String message;
  final int? statusCode;
  final String? path;

  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() => message;
}

/// 二进制资源（巡检现场照片等）的鉴权请求信息。
///
/// 这些接口只认 `Authorization` 头、不支持匿名访问，也没有静态目录，
/// 所以不能直接拼 URL 交给 `Image.network`，必须把 headers 一起带过去。
class BinaryRequest {
  const BinaryRequest(this.uri, this.headers);

  final Uri uri;
  final Map<String, String> headers;
}

/// 令牌存取抽象：真机用 SharedPreferences，单元测试用内存实现注入。
abstract class TokenStore {
  Future<String?> readAccessToken();

  Future<String?> readRefreshToken();

  Future<void> save({required String accessToken, required String refreshToken});

  Future<void> clear();
}

class SharedPreferencesTokenStore implements TokenStore {
  static const String _accessKey = 'auth.access_token';
  static const String _refreshKey = 'auth.refresh_token';

  @override
  Future<String?> readAccessToken() async =>
      (await SharedPreferences.getInstance()).getString(_accessKey);

  @override
  Future<String?> readRefreshToken() async =>
      (await SharedPreferences.getInstance()).getString(_refreshKey);

  @override
  Future<void> save({required String accessToken, required String refreshToken}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, accessToken);
    if (refreshToken.isNotEmpty) {
      await prefs.setString(_refreshKey, refreshToken);
    }
  }

  @override
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }
}

class InMemoryTokenStore implements TokenStore {
  InMemoryTokenStore({String? accessToken, String? refreshToken})
      : _access = accessToken,
        _refresh = refreshToken;

  String? _access;
  String? _refresh;

  @override
  Future<String?> readAccessToken() async => _access;

  @override
  Future<String?> readRefreshToken() async => _refresh;

  @override
  Future<void> save({required String accessToken, required String refreshToken}) async {
    _access = accessToken;
    if (refreshToken.isNotEmpty) _refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    _access = null;
    _refresh = null;
  }
}

/// HTTP 底座：统一鉴权头、超时、错误信息提取与「裸数据 / 包装体」两种响应结构。
///
/// 后端没有全局响应包装中间件，业务接口返回的是裸 dict 或裸 list
/// （如 `/api/dashboard/stats` 返回裸 dict、`/api/records` 返回裸 list），
/// 只有少数接口用 `{ok, code, message, data}` 包装，所以这里按「有 data 且有 ok/code 才拆包」处理。
class ApiClient {
  ApiClient({
    http.Client? client,
    TokenStore? tokenStore,
    String? baseUrl,
    Duration? timeout,
    this.onUnauthorized,
  })  : _client = client ?? http.Client(),
        _tokenStore = tokenStore ?? SharedPreferencesTokenStore(),
        baseUrl = baseUrl ?? defaultBaseUrl,
        timeout = timeout ?? const Duration(seconds: 20);

  /// 默认值面向 Android 模拟器；真机调试用
  /// `flutter run --dart-define=API_BASE_URL=http://<电脑局域网IP>:8000` 覆盖。
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  final http.Client _client;
  final TokenStore _tokenStore;
  final String baseUrl;
  final Duration timeout;

  /// 刷新也失败（或本来就没有令牌）时回调，App 层据此退回登录页
  void Function()? onUnauthorized;

  String? _accessToken;
  String? _refreshToken;
  bool _loaded = false;

  String? get accessToken => _accessToken;

  bool get isLoggedIn => (_accessToken ?? '').isNotEmpty;

  Future<void> loadTokens() async {
    if (_loaded) return;
    _accessToken = await _tokenStore.readAccessToken();
    _refreshToken = await _tokenStore.readRefreshToken();
    _loaded = true;
  }

  Future<void> saveTokens({required String accessToken, String? refreshToken}) async {
    _accessToken = accessToken;
    if (refreshToken != null && refreshToken.isNotEmpty) {
      _refreshToken = refreshToken;
    }
    _loaded = true;
    await _tokenStore.save(
      accessToken: accessToken,
      refreshToken: _refreshToken ?? '',
    );
  }

  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
    _loaded = true;
    await _tokenStore.clear();
  }

  // ---------------- 请求入口 ----------------

  Future<dynamic> get(String path, {Map<String, dynamic>? query, bool auth = true}) =>
      request('GET', path, query: query, auth: auth);

  Future<dynamic> postJson(String path, {Object? body, bool auth = true}) =>
      request('POST', path, jsonBody: body ?? const <String, dynamic>{}, auth: auth);

  Future<dynamic> putJson(String path, {Object? body, bool auth = true}) =>
      request('PUT', path, jsonBody: body ?? const <String, dynamic>{}, auth: auth);

  Future<dynamic> patchJson(String path, {Object? body, bool auth = true}) =>
      request('PATCH', path, jsonBody: body ?? const <String, dynamic>{}, auth: auth);

  /// 表单提交（`application/x-www-form-urlencoded`）：
  /// 后端的登录、刷新、改密、问答、故障状态都要求 Form 而非 JSON。
  Future<dynamic> postForm(String path, {Map<String, String> form = const {}, bool auth = true}) =>
      request('POST', path, form: form, auth: auth);

  Future<dynamic> delete(String path, {bool auth = true}) => request('DELETE', path, auth: auth);

  /// 拼一个带鉴权的二进制资源请求，交给 `Image.network(r.uri, headers: r.headers)` 使用。
  /// 与普通 JSON 接口一样会带上当前 access token。
  BinaryRequest binaryRequest(String path, {Map<String, dynamic>? query}) =>
      BinaryRequest(_buildUri(path, query), _headers(auth: true, json: false));

  Future<dynamic> request(
    String method,
    String path, {
    Map<String, dynamic>? query,
    Object? jsonBody,
    Map<String, String>? form,
    bool auth = true,
    bool retryOnUnauthorized = true,
  }) async {
    await loadTokens();
    final uri = _buildUri(path, query);
    final hasJson = jsonBody != null && form == null;
    final headers = _headers(auth: auth, json: hasJson);

    http.Response res;
    try {
      res = await _send(method, uri, headers, jsonBody, form).timeout(timeout);
    } on TimeoutException {
      throw ApiException('请求超时，请检查网络后重试', path: path);
    } on SocketException catch (e) {
      throw ApiException('无法连接服务器（$baseUrl）：${e.message}', path: path);
    } on http.ClientException catch (e) {
      throw ApiException('网络请求失败：${e.message}', path: path);
    }

    if (res.statusCode == 401 && auth && retryOnUnauthorized) {
      if (await _tryRefresh()) {
        return request(
          method,
          path,
          query: query,
          jsonBody: jsonBody,
          form: form,
          auth: auth,
          retryOnUnauthorized: false,
        );
      }
      await clearTokens();
      onUnauthorized?.call();
      throw ApiException('登录已过期，请重新登录', statusCode: 401, path: path);
    }

    return _decode(res, path: path);
  }

  /// 文件上传（multipart）。`files` 是「表单字段名 → 本地文件路径」。
  Future<dynamic> multipart(
    String path, {
    Map<String, String> fields = const {},
    Map<String, String> files = const {},
    bool auth = true,
  }) async {
    await loadTokens();
    final uri = _buildUri(path, null);

    for (var attempt = 0; attempt < 2; attempt++) {
      http.Response res;
      try {
        res = await _sendMultipart(uri, fields, files, auth: auth).timeout(timeout);
      } on TimeoutException {
        throw ApiException('上传超时，请检查网络后重试', path: path);
      } on SocketException catch (e) {
        throw ApiException('无法连接服务器（$baseUrl）：${e.message}', path: path);
      } on http.ClientException catch (e) {
        throw ApiException('上传失败：${e.message}', path: path);
      }

      if (res.statusCode == 401 && auth && attempt == 0) {
        if (await _tryRefresh()) continue;
        await clearTokens();
        onUnauthorized?.call();
        throw ApiException('登录已过期，请重新登录', statusCode: 401, path: path);
      }
      return _decode(res, path: path);
    }
    throw ApiException('上传失败', path: path);
  }

  /// 访问令牌临近过期时主动续期（默认剩余不足 60 分钟就续）。
  ///
  /// 注意后端 `/api/auth/refresh` 自身也挂了 `get_current_user`，
  /// 也就是**必须带着仍然有效的 access token 才能刷新**；
  /// 一旦 access token 过期就只能重新登录，所以续期只能「提前做」。
  Future<bool> refreshIfNeeded({Duration threshold = const Duration(minutes: 60)}) async {
    await loadTokens();
    final token = _accessToken;
    if (token == null || token.isEmpty) return false;
    final expiry = jwtExpiry(token);
    if (expiry == null) return false;
    if (expiry.difference(DateTime.now().toUtc()) > threshold) return false;
    return _tryRefresh();
  }

  /// 解析 JWT 的 exp（只读载荷、不验签，用于判断是否临近过期）
  static DateTime? jwtExpiry(String token) {
    final parts = token.split('.');
    if (parts.length < 2) return null;
    try {
      final payload = utf8.decode(base64Url.decode(base64Url.normalize(parts[1])));
      final data = jsonDecode(payload);
      if (data is Map && data['exp'] is num) {
        return DateTime.fromMillisecondsSinceEpoch(
          (data['exp'] as num).toInt() * 1000,
          isUtc: true,
        );
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  // ---------------- 内部实现 ----------------

  Future<bool> _tryRefresh() async {
    final refresh = _refreshToken;
    if (refresh == null || refresh.isEmpty) return false;
    try {
      final res = await _client
          .post(
            _buildUri('/api/auth/refresh', null),
            headers: {
              'Accept': 'application/json',
              if ((_accessToken ?? '').isNotEmpty) 'Authorization': 'Bearer $_accessToken',
            },
            body: {'refresh_token': refresh},
          )
          .timeout(timeout);
      if (res.statusCode != 200) return false;
      final decoded = jsonDecode(utf8.decode(res.bodyBytes));
      if (decoded is! Map || decoded['access_token'] == null) return false;
      // 后端刷新接口不回新的 refresh_token，沿用旧的
      await saveTokens(accessToken: '${decoded['access_token']}', refreshToken: refresh);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<http.Response> _send(
    String method,
    Uri uri,
    Map<String, String> headers,
    Object? jsonBody,
    Map<String, String>? form,
  ) {
    final body = jsonBody == null ? null : jsonEncode(jsonBody);
    switch (method.toUpperCase()) {
      case 'GET':
        return _client.get(uri, headers: headers);
      case 'POST':
        return _client.post(uri, headers: headers, body: form ?? body);
      case 'PUT':
        return _client.put(uri, headers: headers, body: form ?? body);
      case 'PATCH':
        return _client.patch(uri, headers: headers, body: form ?? body);
      case 'DELETE':
        return _client.delete(uri, headers: headers, body: form ?? body);
      default:
        throw ArgumentError('不支持的请求方法：$method');
    }
  }

  Future<http.Response> _sendMultipart(
    Uri uri,
    Map<String, String> fields,
    Map<String, String> files, {
    required bool auth,
  }) async {
    final request = http.MultipartRequest('POST', uri);
    request.headers['Accept'] = 'application/json';
    if (auth && (_accessToken ?? '').isNotEmpty) {
      request.headers['Authorization'] = 'Bearer $_accessToken';
    }
    request.fields.addAll(fields);
    for (final entry in files.entries) {
      if (entry.value.isEmpty) continue;
      final file = File(entry.value);
      if (!await file.exists()) continue;
      request.files.add(await http.MultipartFile.fromPath(entry.key, entry.value));
    }
    final streamed = await request.send();
    return http.Response.fromStream(streamed);
  }

  Map<String, String> _headers({required bool auth, required bool json}) {
    final headers = <String, String>{'Accept': 'application/json'};
    if (json) headers['Content-Type'] = 'application/json; charset=utf-8';
    if (auth && (_accessToken ?? '').isNotEmpty) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    return headers;
  }

  Uri _buildUri(String path, Map<String, dynamic>? query) {
    final base = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    final uri = Uri.parse('$base$path');
    if (query == null || query.isEmpty) return uri;
    final params = <String, String>{};
    query.forEach((key, value) {
      if (value == null) return;
      final text = '$value';
      if (text.isEmpty) return;
      params[key] = text;
    });
    if (params.isEmpty) return uri;
    return uri.replace(queryParameters: {...uri.queryParameters, ...params});
  }

  dynamic _decode(http.Response res, {required String path}) {
    // 后端返回中文，必须按 UTF-8 解码字节，直接用 res.body 在部分平台会乱码
    final text = utf8.decode(res.bodyBytes);
    dynamic decoded;
    if (text.isNotEmpty) {
      try {
        decoded = jsonDecode(text);
      } catch (_) {
        decoded = null;
      }
    }
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiException(
        _errorMessage(decoded, res.statusCode),
        statusCode: res.statusCode,
        path: path,
      );
    }
    return _unwrap(decoded);
  }

  /// 只有同时带 `data` 与 `ok`/`code` 才认定是包装体；业务接口的裸 dict
  /// 里若恰好有 data 字段也不会被误拆。
  dynamic _unwrap(dynamic decoded) {
    if (decoded is Map &&
        decoded.containsKey('data') &&
        (decoded.containsKey('ok') || decoded.containsKey('code'))) {
      return decoded['data'];
    }
    return decoded;
  }

  String _errorMessage(dynamic decoded, int status) {
    if (decoded is Map) {
      final detail = decoded['detail'];
      if (detail is String && detail.isNotEmpty) return detail;
      if (detail is List && detail.isNotEmpty) {
        final first = detail.first;
        if (first is Map && first['msg'] != null) return '${first['msg']}';
      }
      for (final key in const ['message', 'error', 'msg']) {
        final value = decoded[key];
        if (value is String && value.isNotEmpty) return value;
      }
    }
    switch (status) {
      case 401:
        return '登录已过期，请重新登录';
      case 403:
        return '当前账号没有该操作权限';
      case 404:
        return '请求的数据不存在';
      case 422:
        return '提交的参数不合法';
      default:
        return status >= 500 ? '服务器异常（$status），请稍后重试' : '请求失败（$status）';
    }
  }
}
