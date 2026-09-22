import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 站内通知：数据来自 `/api/notifications`，字段由后端
/// `notification_service.build_notifications()` 生成
/// （id/title/content/level/level_text/source/link/created_at/category/read…）。
class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  late Future<Map<String, dynamic>> _future;
  bool _marking = false;

  @override
  void initState() {
    super.initState();
    _future = api.notifications(limit: 50);
  }

  void _reload() => setState(() => _future = api.notifications(limit: 50));

  Future<void> _refresh() async {
    _reload();
    try {
      await _future;
    } catch (_) {
      // 忽略：错误态由 AsyncView 展示
    }
    await session.refreshUnread();
  }

  Future<void> _markAllRead() async {
    setState(() => _marking = true);
    try {
      await api.markAllNotificationsRead();
      if (!mounted) return;
      _reload();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已全部标记为已读')),
      );
      await session.refreshUnread();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(describeError(e))),
      );
    } finally {
      if (mounted) setState(() => _marking = false);
    }
  }

  /// 点击通知：先把这一条标记为已读（`POST /api/notifications/{id}/read`），
  /// 刷新未读角标，再按后端给的 link 跳转。
  Future<void> _openNotification(Map<String, dynamic> item) async {
    final id = textOf(item['id']);
    if (item['read'] != true && id.isNotEmpty) {
      try {
        await api.markNotificationRead(id);
        await session.refreshUnread();
        if (mounted) _reload();
      } catch (_) {
        // 标记已读失败不阻断跳转；下次进列表还能重试
      }
    }
    if (!mounted) return;
    _openLink(textOf(item['link']));
  }

  /// 把通知里的 link（形如 `/workorders?order_id=12`）映射到移动端已有路由。
  /// 移动端没有对应页面的（硬件事件 `/hardware?event_id=…` 等）明确提示去 Web 端查看，
  /// 不跳到空白页。
  void _openLink(String link) {
    final text = link.trim();
    if (text.isEmpty) return;

    final uri = Uri.tryParse(text);
    if (uri == null) {
      _tip('该内容请在 Web 端查看');
      return;
    }
    final query = uri.queryParameters;

    switch (uri.path) {
      case '/records':
        _openRecord(query['record_id']);
        return;
      case '/workorders':
        _openDetail(query['order_id'], '/workorder-detail', '工单');
        return;
      case '/alerts':
        _openDetail(query['alert_id'] ?? query['id'], '/alert-detail', '告警');
        return;
      case '/devices':
        _openDetail(query['device_id'], '/device-detail', '设备');
        return;
      case '/notifications':
        return; // 已经在通知中心
    }

    // 路径不认识时按 query 参数兜底
    if (query['order_id'] != null) {
      _openDetail(query['order_id'], '/workorder-detail', '工单');
      return;
    }
    if (query['alert_id'] != null) {
      _openDetail(query['alert_id'], '/alert-detail', '告警');
      return;
    }
    if (query['device_id'] != null) {
      _openDetail(query['device_id'], '/device-detail', '设备');
      return;
    }
    if (query['record_id'] != null) {
      _openRecord(query['record_id']);
      return;
    }
    _tip('该内容请在 Web 端查看');
  }

  /// 巡检 id 在主库是数字、在运行库档案里是字符串（如 `REC-M-1`）：
  /// 纯数字走 `/record-detail`，其余走新的 `/archive-detail`（档案详情支持字符串 id）。
  void _openRecord(String? rawValue) {
    final value = (rawValue ?? '').trim();
    if (value.isEmpty) {
      _tip('该通知没有可跳转的内容，请在 Web 端查看');
      return;
    }
    final id = int.tryParse(value);
    if (id != null && id > 0) {
      Navigator.of(context).pushNamed('/record-detail', arguments: id);
      return;
    }
    Navigator.of(context).pushNamed('/archive-detail', arguments: value);
  }

  void _openDetail(String? rawValue, String route, String label) {
    final value = (rawValue ?? '').trim();
    final id = int.tryParse(value);
    if (id == null || id <= 0) {
      _tip(value.isEmpty
          ? '该通知没有可跳转的内容，请在 Web 端查看'
          : '$label「$value」暂不支持在移动端打开，请在 Web 端查看');
      return;
    }
    Navigator.of(context).pushNamed(route, arguments: id);
  }

  void _tip(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('消息通知'),
        actions: [
          TextButton(
            onPressed: _marking ? null : _markAllRead,
            child: _marking
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('全部已读', style: TextStyle(fontSize: 13)),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载通知…',
          isEmpty: (data) => asMapList(data['items']).isEmpty,
          emptyMessage: '暂无通知',
          emptyIcon: Icons.notifications_none,
          builder: (context, data) {
            final items = asMapList(data['items']);
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: items.length,
              separatorBuilder: (context, index) => const SizedBox(height: 8),
              itemBuilder: (context, index) => _NotificationTile(
                item: items[index],
                onTap: () => _openNotification(items[index]),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item, required this.onTap});

  final Map<String, dynamic> item;
  final VoidCallback onTap;

  /// 后端 level：danger / warning / info / success
  static Color _levelColor(String level) {
    switch (level) {
      case 'danger':
        return const Color(0xFFB91C1C);
      case 'warning':
        return const Color(0xFFEA580C);
      case 'success':
        return const Color(0xFF15803D);
      default:
        return const Color(0xFF2563EB);
    }
  }

  @override
  Widget build(BuildContext context) {
    final level = textOf(item['level'], fallback: 'info');
    final color = _levelColor(level);
    final unread = item['read'] != true;
    final title = textOf(item['title'], fallback: '通知');
    final content = textOf(item['content']);
    final meta = [
      textOf(item['source']),
      textOf(item['category']),
      formatRelativeTime(item['created_at']),
    ].where((text) => text.isNotEmpty).join(' · ');

    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 未读标记
              Padding(
                padding: const EdgeInsets.only(top: 5, right: 8),
                child: Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: unread ? const Color(0xFFDC2626) : Colors.transparent,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              // 级别色块
              Container(
                width: 4,
                height: 38,
                margin: const EdgeInsets.only(top: 2, right: 10),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 14,
                              color: const Color(0xFF1E293B),
                              fontWeight: unread ? FontWeight.w600 : FontWeight.w500,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        StatusChip(
                          label: textOf(item['level_text'], fallback: level),
                          color: color,
                          compact: true,
                        ),
                      ],
                    ),
                    if (content.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        content,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12.5,
                          height: 1.5,
                          color: Color(0xFF475569),
                        ),
                      ),
                    ],
                    if (meta.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        meta,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
