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
              itemBuilder: (context, index) => _NotificationTile(item: items[index]),
            );
          },
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item});

  final Map<String, dynamic> item;

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

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
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
    );
  }
}
