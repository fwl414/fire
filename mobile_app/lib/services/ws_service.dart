import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

/// 通知 WebSocket（后端 `/ws/notifications`）。
///
/// 后端握手阶段拿不到 HTTP 令牌，改成「连上后首帧认证」：
/// 首帧发 `{"action":"auth","token":"<access_token>"}`，成功回 `{"type":"auth_ok"}`，
/// 令牌无效/无租户时后端以 4401/4403 关闭连接。心跳是客户端定期发
/// `{"action":"ping"}`、服务端回 `{"type":"pong"}`。推送帧形如
/// `{"type":"alert|workorder|system","timestamp":...,"data":{...}}`。
class NotificationSocket {
  NotificationSocket({
    required this.baseUrl,
    required this.tokenProvider,
    required this.onEvent,
    this.onStatus,
  });

  final String baseUrl;
  final Future<String?> Function() tokenProvider;
  final void Function(Map<String, dynamic> event) onEvent;
  final void Function(bool connected)? onStatus;

  static const Duration _pingInterval = Duration(seconds: 30);
  static const Duration _initialBackoff = Duration(seconds: 1);
  static const Duration _maxBackoff = Duration(seconds: 30);

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  Duration _backoff = _initialBackoff;
  bool _disposed = false;
  bool _connecting = false;
  bool _closing = false;
  bool _connected = false;

  void connect() {
    // 已有连接或正在连接时不重复发起，避免心跳与重连叠加出多条连接
    if (_disposed || _connecting || _channel != null) return;
    unawaited(_open());
  }

  void dispose() {
    _disposed = true;
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _pingTimer = null;
    _reconnectTimer = null;
    final subscription = _subscription;
    _subscription = null;
    unawaited(subscription?.cancel());
    final channel = _channel;
    _channel = null;
    unawaited(channel?.sink.close());
    _setConnected(false);
  }

  Future<void> _open() async {
    _connecting = true;
    _closing = false;
    try {
      // 令牌是异步取的，取不到就不连（未登录时连上也会被后端踢掉）
      final token = await tokenProvider();
      if (_disposed || token == null || token.isEmpty) return;
      final channel = WebSocketChannel.connect(Uri.parse(_endpoint()));
      _channel = channel;
      await channel.ready;
      if (_disposed) {
        await channel.sink.close();
        return;
      }
      // 首帧必须认证，后端等不到认证帧会在 10 秒后关闭连接
      channel.sink.add(jsonEncode({'action': 'auth', 'token': token}));
      _subscription = channel.stream.listen(
        _handleMessage,
        onError: (Object _) => _handleClose(),
        onDone: _handleClose,
        cancelOnError: true,
      );
      _startPing();
    } catch (_) {
      _handleClose();
    } finally {
      _connecting = false;
    }
  }

  void _handleClose() {
    if (_closing) return;
    _closing = true;
    _pingTimer?.cancel();
    _pingTimer = null;
    final subscription = _subscription;
    _subscription = null;
    unawaited(subscription?.cancel());
    final channel = _channel;
    _channel = null;
    unawaited(channel?.sink.close());
    _setConnected(false);
    _scheduleReconnect();
  }

  /// 指数退避：1s → 2s → 4s … 最大 30s；认证成功后重置
  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    final delay = _backoff;
    final next = _backoff.inSeconds * 2;
    _backoff = Duration(seconds: next > _maxBackoff.inSeconds ? _maxBackoff.inSeconds : next);
    _reconnectTimer = Timer(delay, () {
      _reconnectTimer = null;
      connect();
    });
  }

  void _startPing() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(_pingInterval, (_) => _send({'action': 'ping'}));
  }

  void _send(Map<String, dynamic> payload) {
    final sink = _channel?.sink;
    if (sink == null) return;
    try {
      sink.add(jsonEncode(payload));
    } catch (_) {
      // 连接刚好断开：交给 onDone/onError 触发重连
    }
  }

  void _handleMessage(dynamic raw) {
    if (raw is! String) return;
    dynamic decoded;
    try {
      decoded = jsonDecode(raw);
    } catch (_) {
      return;
    }
    if (decoded is! Map) return;
    final event = Map<String, dynamic>.from(decoded);
    final type = '${event['type'] ?? ''}';

    // 服务端目前不会主动 ping，但收到 ping 仍按对端心跳语义回 pong
    if ('${event['action'] ?? ''}' == 'ping') {
      _send({'action': 'pong'});
      return;
    }
    if (type == 'pong') return;
    if (type == 'auth_ok') {
      _backoff = _initialBackoff;
      _setConnected(true);
      return;
    }
    if (type == 'alert' || type == 'workorder' || type == 'system') {
      onEvent(event);
    }
  }

  void _setConnected(bool value) {
    if (_connected == value) return;
    _connected = value;
    onStatus?.call(value);
  }

  String _endpoint() {
    var base = baseUrl.trim();
    if (base.endsWith('/')) base = base.substring(0, base.length - 1);
    if (base.startsWith('https://')) {
      return 'wss://${base.substring('https://'.length)}/ws/notifications';
    }
    if (base.startsWith('http://')) {
      return 'ws://${base.substring('http://'.length)}/ws/notifications';
    }
    return '$base/ws/notifications';
  }
}
