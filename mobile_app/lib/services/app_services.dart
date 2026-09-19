import 'package:flutter/material.dart';

import 'api_service.dart';

/// 全局接口实例：`main()` 里初始化；测试里替换成注入了 MockClient 的实例即可离线跑。
late ApiService api;

/// 全局导航 key：令牌失效时用它把用户送回登录页
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();

/// 当前登录用户与未读通知数，供「我的」页与首页角标共用。
///
/// 不引入额外状态管理依赖：页面用 `ListenableBuilder`/`AnimatedBuilder` 订阅即可。
class AppSession extends ChangeNotifier {
  Map<String, dynamic>? profile;
  int unreadNotifications = 0;

  bool get isLoggedIn => profile != null;

  String get displayName => textOf(
        profile?['real_name'],
        fallback: textOf(profile?['username'], fallback: '未登录'),
      );

  String get roleName => textOf(
        profile?['role_name'],
        fallback: textOf(profile?['role'], fallback: ''),
      );

  String get department => textOf(profile?['department']);

  String get phone => textOf(profile?['phone']);

  List<String> get permissions =>
      asList(profile?['permissions']).map((e) => '$e').toList();

  /// 权限判断：后端 `/api/auth/me` 返回的 permissions 里 `*` 表示全部
  bool can(String permission) {
    final list = permissions;
    if (list.isEmpty) return true; // 权限字段缺失时不拦人，交给后端 403 兜底
    return list.contains('*') || list.contains(permission);
  }

  /// 从 `/api/auth/me` 载入用户信息
  Future<void> loadProfile() async {
    final data = await api.me();
    profile = asMap(data['user']);
    notifyListeners();
  }

  /// 未读通知数（失败不影响主流程，角标不显示即可）
  Future<void> refreshUnread() async {
    try {
      final summary = await api.notificationSummary();
      unreadNotifications = intOf(summary['unread']);
      notifyListeners();
    } catch (_) {
      // 忽略：角标不是关键路径
    }
  }

  void updateProfile(Map<String, dynamic> value) {
    profile = {...?profile, ...value};
    notifyListeners();
  }

  void clear() {
    profile = null;
    unreadNotifications = 0;
    notifyListeners();
  }
}

final AppSession session = AppSession();

/// 告警实时推送计数：WebSocket 收到 alert 事件时 +1，告警列表页监听它自动刷新。
/// 用计数而不是布尔值，是为了「连续来两条推送」也能各触发一次刷新。
final ValueNotifier<int> alertPushTick = ValueNotifier<int>(0);
