import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 「我的」tab。
///
/// 用户信息与未读数读全局 `session`，统计数字来自 `/api/mobile/home`；
/// 之前的实现统计写死、菜单只弹「点击了 xxx」、退出登录只提示不办事，这里全部换成真实行为。
class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.home();
    unawaited(_bootstrap());
  }

  /// 刷新用户信息与未读数；失败不阻塞页面，先用已有数据渲染
  Future<void> _bootstrap() async {
    try {
      await session.loadProfile();
    } catch (_) {
      // 忽略：session 里可能已有上次登录留下的资料
    }
    await session.refreshUnread();
  }

  void _reload() => setState(() => _future = api.home());

  Future<void> _refresh() async {
    _reload();
    try {
      await _future;
    } catch (_) {
      // 忽略：错误态由 AsyncView 展示
    }
    await _bootstrap();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
        children: [
          _buildHeader(),
          _buildStats(),
          _buildMenu(),
          const SizedBox(height: 12),
          _buildMoreFeatures(),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _logout,
              icon: const Icon(Icons.logout, color: Color(0xFFDC2626)),
              label: const Text('退出登录', style: TextStyle(color: Color(0xFFDC2626))),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14),
                side: const BorderSide(color: Color(0xFFFECACA)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return ListenableBuilder(
      listenable: session,
      builder: (context, _) {
        final phone = session.phone;
        final department = session.department;
        final subtitle = [session.roleName, department]
            .where((text) => text.isNotEmpty)
            .join(' · ');

        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            gradient: const LinearGradient(
              colors: [Color(0xFFDC2626), Color(0xFF991B1B)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(30),
                ),
                child: const Icon(Icons.person, color: Colors.white, size: 30),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      session.displayName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 19,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle.isEmpty ? '—' : subtitle,
                      style: const TextStyle(color: Colors.white70, fontSize: 13),
                    ),
                    if (phone.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        phone,
                        style: const TextStyle(color: Colors.white60, fontSize: 12),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildStats() {
    return AsyncView<Map<String, dynamic>>(
      future: _future,
      onRetry: _reload,
      loadingMessage: '正在加载概览…',
      builder: (context, data) {
        final stats = asMap(data['stats']);
        return SectionCard(
          child: Row(
            children: [
              _statItem('待处理告警', intOf(stats['pendingAlerts']), const Color(0xFFDC2626)),
              _statItem('我的在办', intOf(stats['myWorkorders']), const Color(0xFF2563EB)),
              _statItem('今日巡检', intOf(stats['todayInspections']), const Color(0xFF15803D)),
              _statItem('设备总数', intOf(stats['deviceCount']), const Color(0xFF7C3AED)),
            ],
          ),
        );
      },
    );
  }

  Widget _statItem(String label, int value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(
            '$value',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: color),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }

  Widget _buildMenu() {
    return SectionCard(
      padding: EdgeInsets.zero,
      margin: EdgeInsets.zero,
      child: Column(
        children: [
          _menuTile(
            icon: Icons.precision_manufacturing_outlined,
            color: const Color(0xFF2563EB),
            title: '设备台账',
            onTap: () => Navigator.of(context).pushNamed('/devices'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.fact_check_outlined,
            color: const Color(0xFF15803D),
            title: '巡检记录',
            onTap: () => Navigator.of(context).pushNamed('/records'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.notifications_none,
            color: const Color(0xFFDC2626),
            title: '消息通知',
            trailing: ListenableBuilder(
              listenable: session,
              builder: (context, _) {
                final unread = session.unreadNotifications;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (unread > 0) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFDC2626),
                          borderRadius: BorderRadius.circular(9),
                        ),
                        child: Text(
                          '$unread',
                          style: const TextStyle(color: Colors.white, fontSize: 11),
                        ),
                      ),
                      const SizedBox(width: 4),
                    ],
                    const Icon(Icons.chevron_right, color: Color(0xFFCBD5E1)),
                  ],
                );
              },
            ),
            onTap: () async {
              await Navigator.of(context).pushNamed('/notifications');
              // 通知页里可能已读了一部分，回来同步角标
              await session.refreshUnread();
            },
          ),
          _divider(),
          _menuTile(
            icon: Icons.question_answer_outlined,
            color: const Color(0xFF7C3AED),
            title: '消防问答',
            onTap: () => Navigator.of(context).pushNamed('/qa'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.lock_outline,
            color: const Color(0xFFEA580C),
            title: '修改密码',
            onTap: _changePassword,
          ),
          _divider(),
          _menuTile(
            icon: Icons.info_outline,
            color: const Color(0xFF64748B),
            title: '关于',
            onTap: _showAbout,
          ),
        ],
      ),
    );
  }

  Widget _divider() => const Divider(height: 1, indent: 62);

  /// 更多功能：巡检档案 / 批量巡检 / 每日简报 / 设备 AI 诊断 / 报告验真。
  /// 每一项都是新页面，路由在 `main.dart` 的 `routes` 与 `onGenerateRoute` 里注册。
  Widget _buildMoreFeatures() {
    return SectionCard(
      title: '更多功能',
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          _menuTile(
            icon: Icons.inventory_2_outlined,
            color: const Color(0xFF2563EB),
            title: '巡检档案',
            onTap: () => Navigator.of(context).pushNamed('/archives'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.batch_prediction_outlined,
            color: const Color(0xFF15803D),
            title: '批量巡检',
            onTap: () => Navigator.of(context).pushNamed('/batch-inspections'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.summarize_outlined,
            color: const Color(0xFFEA580C),
            title: '每日简报',
            onTap: () => Navigator.of(context).pushNamed('/daily-brief'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.online_prediction_outlined,
            color: const Color(0xFF7C3AED),
            title: '设备 AI 诊断',
            onTap: () => Navigator.of(context).pushNamed('/device-diagnose'),
          ),
          _divider(),
          _menuTile(
            icon: Icons.verified_outlined,
            color: const Color(0xFF0E7490),
            title: '报告验真',
            onTap: () => Navigator.of(context).pushNamed('/report-verify'),
          ),
        ],
      ),
    );
  }

  Widget _menuTile({
    required IconData icon,
    required Color color,
    required String title,
    required VoidCallback onTap,
    Widget? trailing,
  }) {
    return ListTile(
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, color: color, size: 19),
      ),
      title: Text(title, style: const TextStyle(fontSize: 14)),
      trailing: trailing ?? const Icon(Icons.chevron_right, color: Color(0xFFCBD5E1)),
      onTap: onTap,
    );
  }

  Future<void> _changePassword() async {
    final changed = await showDialog<bool>(
      context: context,
      builder: (_) => const _ChangePasswordDialog(),
    );
    if (changed != true) return;
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('密码已修改')),
    );
  }

  void _showAbout() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('关于'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const InfoRow(label: '应用名称', value: '智慧消防巡检'),
            const InfoRow(label: '版本', value: '1.0.0'),
            InfoRow(label: '服务器', value: api.client.baseUrl),
            InfoRow(label: '当前账号', value: session.displayName),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('确定要退出当前账号吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('退出'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    try {
      await api.logout();
    } catch (_) {
      // 后端不可达也要让用户退出，令牌在 api.logout() 内部已清
    }
    session.clear();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/login', (route) => false);
  }
}

/// 修改密码弹窗：校验与请求都放在弹窗里，成功后 pop(true) 由页面弹提示。
class _ChangePasswordDialog extends StatefulWidget {
  const _ChangePasswordDialog();

  @override
  State<_ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends State<_ChangePasswordDialog> {
  final TextEditingController _oldCtrl = TextEditingController();
  final TextEditingController _newCtrl = TextEditingController();
  final TextEditingController _confirmCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _oldCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    // 密码不做 trim，首尾空格也算密码的一部分
    final oldPassword = _oldCtrl.text;
    final newPassword = _newCtrl.text;
    final confirm = _confirmCtrl.text;

    if (oldPassword.isEmpty || newPassword.isEmpty || confirm.isEmpty) {
      setState(() => _error = '请填写完整的密码');
      return;
    }
    if (newPassword != confirm) {
      setState(() => _error = '两次输入的新密码不一致');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await api.changePassword(oldPassword: oldPassword, newPassword: newPassword);
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = describeError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('修改密码'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _oldCtrl,
            obscureText: true,
            enabled: !_submitting,
            decoration: const InputDecoration(labelText: '原密码'),
          ),
          TextField(
            controller: _newCtrl,
            obscureText: true,
            enabled: !_submitting,
            decoration: const InputDecoration(labelText: '新密码'),
          ),
          TextField(
            controller: _confirmCtrl,
            obscureText: true,
            enabled: !_submitting,
            decoration: const InputDecoration(labelText: '确认新密码'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                _error!,
                style: const TextStyle(fontSize: 12, color: Color(0xFFDC2626)),
              ),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.pop(context, false),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: _submitting
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('确认修改'),
        ),
      ],
    );
  }
}
