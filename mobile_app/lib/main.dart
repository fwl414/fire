import 'package:flutter/material.dart';

import 'pages/alert_detail_page.dart';
import 'pages/alerts_page.dart';
import 'pages/dashboard_page.dart';
import 'pages/device_detail_page.dart';
import 'pages/devices_page.dart';
import 'pages/fire_qa_page.dart';
import 'pages/inspection_page.dart';
import 'pages/login_page.dart';
import 'pages/notifications_page.dart';
import 'pages/profile_page.dart';
import 'pages/record_detail_page.dart';
import 'pages/records_page.dart';
import 'pages/scan_page.dart';
import 'pages/workorder_create_page.dart';
import 'pages/workorder_detail_page.dart';
import 'pages/workorders_page.dart';
import 'services/api_client.dart';
import 'services/api_service.dart';
import 'services/app_services.dart';
import 'services/ws_service.dart';
import 'widgets/common.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  api = ApiService();
  // 令牌彻底失效（刷新也失败）时，把用户送回登录页
  api.client.onUnauthorized = _handleUnauthorized;
  runApp(const FireMobileApp());
}

void _handleUnauthorized() {
  session.clear();
  appNavigatorKey.currentState?.pushNamedAndRemoveUntil('/login', (route) => false);
}

class FireMobileApp extends StatelessWidget {
  const FireMobileApp({super.key, this.home});

  /// 测试可注入首屏，跳过真实鉴权流程
  final Widget? home;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '智慧消防巡检',
      debugShowCheckedModeBanner: false,
      navigatorKey: appNavigatorKey,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFDC2626),
          primary: const Color(0xFFDC2626),
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: Color(0xFF1E293B),
          elevation: 0,
          centerTitle: true,
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          color: Colors.white,
        ),
      ),
      home: home ?? const AuthGate(),
      routes: {
        '/login': (context) => const LoginPage(),
        '/main': (context) => const MainTabPage(),
        '/devices': (context) => const DevicesPage(),
        '/records': (context) => const RecordsPage(),
        '/qa': (context) => const FireQaPage(),
        '/notifications': (context) => const NotificationsPage(),
        '/scan': (context) => const ScanPage(),
        '/workorder-create': (context) => const WorkorderCreatePage(),
      },
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case '/alert-detail':
            return _detailRoute(settings, AlertDetailPage(id: _idArg(settings.arguments)));
          case '/workorder-detail':
            return _detailRoute(settings, WorkorderDetailPage(id: _idArg(settings.arguments)));
          case '/device-detail':
            return _detailRoute(settings, DeviceDetailPage(id: _idArg(settings.arguments)));
          case '/record-detail':
            return _detailRoute(settings, RecordDetailPage(id: _idArg(settings.arguments)));
          default:
            return null;
        }
      },
    );
  }

  MaterialPageRoute<void> _detailRoute(RouteSettings settings, Widget page) {
    return MaterialPageRoute<void>(builder: (_) => page, settings: settings);
  }

  int _idArg(Object? arguments) {
    if (arguments is int) return arguments;
    return int.tryParse('${arguments ?? ''}') ?? 0;
  }
}

/// 启动门：先判断本地有没有令牌，有则续期 + 拉取用户信息，再决定进主界面还是登录页。
///
/// 后端刷新令牌的接口本身要求 access token 仍然有效，所以这里只能「提前续期」；
/// 一旦 access token 过期就只能重新登录，这是后端契约决定的。
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  String? _error;

  @override
  void initState() {
    super.initState();
    // 导航要在首帧之后做，否则 Navigator 还没挂载
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    setState(() => _error = null);
    try {
      await api.client.loadTokens();
      if (!api.client.isLoggedIn) {
        _goTo('/login');
        return;
      }

      await api.client.refreshIfNeeded();
      try {
        await session.loadProfile();
        await session.refreshUnread();
      } on ApiException catch (error) {
        if (error.isUnauthorized) rethrow;
        // 网络不通之类：用户已经登录过，先进主界面，由各页面自己给「重试」
      }
      _goTo('/main');
    } on ApiException catch (error) {
      if (error.isUnauthorized) {
        await api.client.clearTokens();
        _goTo('/login');
      } else if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (error) {
      if (mounted) setState(() => _error = describeError(error));
    }
  }

  void _goTo(String route) {
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil(route, (existing) => false);
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Scaffold(
        body: ErrorRetryView(message: _error!, onRetry: _bootstrap),
      );
    }
    return const Scaffold(
      body: LoadingView(message: '正在进入…'),
    );
  }
}

class MainTabPage extends StatefulWidget {
  const MainTabPage({super.key});

  @override
  State<MainTabPage> createState() => _MainTabPageState();
}

class _MainTabPageState extends State<MainTabPage> {
  int _currentIndex = 0;
  NotificationSocket? _socket;

  late final List<Widget> _pages = [
    DashboardPage(onOpenTab: _openTab),
    const InspectionPage(),
    const WorkOrdersPage(),
    const AlertsPage(),
    const ProfilePage(),
  ];

  static const List<String> _titles = ['首页', '巡检', '工单', '告警', '我的'];

  @override
  void initState() {
    super.initState();
    // 登录后才进到这里，此时令牌已就绪；断线会自动重连
    _socket = NotificationSocket(
      baseUrl: api.client.baseUrl,
      tokenProvider: () async => api.client.accessToken,
      onEvent: _onPushEvent,
    );
    _socket!.connect();
  }

  @override
  void dispose() {
    _socket?.dispose();
    super.dispose();
  }

  void _openTab(int index) {
    if (index < 0 || index >= _pages.length) return;
    setState(() => _currentIndex = index);
  }

  void _onPushEvent(Map<String, dynamic> event) {
    final type = textOf(event['type']);
    if (type == 'alert') {
      // 告警列表页监听这个计数自动刷新
      alertPushTick.value += 1;
    }
    if (type == 'alert' || type == 'workorder') {
      session.refreshUnread();
    }
  }

  Future<void> _openNotifications() async {
    await Navigator.of(context).pushNamed('/notifications');
    await session.refreshUnread();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_titles[_currentIndex]),
        actions: [
          if (_currentIndex == 0) ...[
            IconButton(
              tooltip: '扫码巡检',
              icon: const Icon(Icons.qr_code_scanner),
              onPressed: () => Navigator.of(context).pushNamed('/scan'),
            ),
            ListenableBuilder(
              listenable: session,
              builder: (context, _) => IconButton(
                tooltip: '消息通知',
                icon: Badge(
                  isLabelVisible: session.unreadNotifications > 0,
                  label: Text('${session.unreadNotifications}'),
                  child: const Icon(Icons.notifications_outlined),
                ),
                onPressed: _openNotifications,
              ),
            ),
          ],
        ],
      ),
      body: IndexedStack(index: _currentIndex, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: _openTab,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: '首页',
          ),
          NavigationDestination(
            icon: Icon(Icons.fact_check_outlined),
            selectedIcon: Icon(Icons.fact_check),
            label: '巡检',
          ),
          NavigationDestination(
            icon: Icon(Icons.assignment_outlined),
            selectedIcon: Icon(Icons.assignment),
            label: '工单',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_active_outlined),
            selectedIcon: Icon(Icons.notifications_active),
            label: '告警',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: '我的',
          ),
        ],
      ),
    );
  }
}
