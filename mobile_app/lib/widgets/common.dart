import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/api_service.dart';

/// 后端时间统一是 UTC 的 ISO 字符串，且常常不带时区后缀
/// （如 `2026-09-19T04:55:01.854600`）。直接 `DateTime.parse` 会被当成本地时间，
/// 展示会差 8 小时，所以这里补 `Z` 后再转本地时区。
DateTime? parseServerTime(dynamic value) {
  final text = textOf(value);
  if (text.isEmpty) return null;
  final normalized = text.endsWith('Z') || text.contains('+') ? text : '${text}Z';
  final parsed = DateTime.tryParse(normalized);
  return parsed?.toLocal();
}

/// `09-19 12:30` 这类紧凑格式，列表里够用
String formatShortTime(dynamic value, {String fallback = '—'}) {
  final time = parseServerTime(value);
  if (time == null) return fallback;
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(time.month)}-${two(time.day)} ${two(time.hour)}:${two(time.minute)}';
}

/// `2026-09-19 12:30`，详情页用
String formatFullTime(dynamic value, {String fallback = '—'}) {
  final time = parseServerTime(value);
  if (time == null) return fallback;
  String two(int n) => n.toString().padLeft(2, '0');
  return '${time.year}-${two(time.month)}-${two(time.day)} '
      '${two(time.hour)}:${two(time.minute)}';
}

/// 相对时间：刚刚 / 12 分钟前 / 3 天前
String formatRelativeTime(dynamic value, {String fallback = '—'}) {
  final time = parseServerTime(value);
  if (time == null) return fallback;
  final diff = DateTime.now().difference(time);
  if (diff.inMinutes < 1) return '刚刚';
  if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟前';
  if (diff.inHours < 24) return '${diff.inHours} 小时前';
  if (diff.inDays < 30) return '${diff.inDays} 天前';
  return formatShortTime(value, fallback: fallback);
}

/// 把异常转成可以直接给用户看的一句话
String describeError(Object? error, {String fallback = '加载失败，请稍后重试'}) {
  if (error == null) return fallback;
  if (error is ApiException) return error.message;
  return error.toString().replaceFirst('Exception: ', '');
}

/// 告警严重度 → 颜色（后端给的是 critical/high/medium/low）
Color severityColor(String severity) {
  switch (severity) {
    case 'critical':
      return const Color(0xFFB91C1C);
    case 'high':
      return const Color(0xFFEA580C);
    case 'medium':
      return const Color(0xFFCA8A04);
    case 'low':
      return const Color(0xFF0E7490);
    default:
      return const Color(0xFF64748B);
  }
}

/// 工单状态 → 颜色（中文状态值）
Color workorderStatusColor(String status) {
  switch (status) {
    case '待受理':
      return const Color(0xFFB91C1C);
    case '处理中':
      return const Color(0xFFEA580C);
    case '待复查':
      return const Color(0xFF7C3AED);
    case '已完成':
      return const Color(0xFF15803D);
    case '已关闭':
      return const Color(0xFF64748B);
    default:
      return const Color(0xFF64748B);
  }
}

Color riskColor(String level) {
  if (level.contains('严重') || level.contains('高')) return const Color(0xFFB91C1C);
  if (level.contains('中')) return const Color(0xFFCA8A04);
  if (level.contains('低')) return const Color(0xFF15803D);
  return const Color(0xFF64748B);
}

/// 白色圆角卡片，页面里统一用它包内容
class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.child,
    this.title,
    this.trailing,
    this.padding = const EdgeInsets.all(16),
    this.margin = const EdgeInsets.only(bottom: 12),
  });

  final Widget child;
  final String? title;
  final Widget? trailing;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry margin;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null) ...[
            Row(
              children: [
                Expanded(
                  child: Text(
                    title!,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF1E293B),
                    ),
                  ),
                ),
                if (trailing != null) trailing!,
              ],
            ),
            const SizedBox(height: 12),
          ],
          child,
        ],
      ),
    );
  }
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key, this.message = '加载中…'});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(
            width: 26,
            height: 26,
            child: CircularProgressIndicator(strokeWidth: 2.4),
          ),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
        ],
      ),
    );
  }
}

/// 错误态：带「重试」按钮。之前的实现只有一行文字，用户没法自救。
class ErrorRetryView extends StatelessWidget {
  const ErrorRetryView({super.key, required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 40, color: Color(0xFFCBD5E1)),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 13, color: Color(0xFF475569), height: 1.5),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('重试'),
            ),
          ],
        ),
      ),
    );
  }
}

class EmptyView extends StatelessWidget {
  const EmptyView({
    super.key,
    this.message = '暂无数据',
    this.icon = Icons.inbox_outlined,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 40, color: const Color(0xFFCBD5E1)),
          const SizedBox(height: 10),
          Text(message, style: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: 14),
            FilledButton.tonal(onPressed: onAction, child: Text(actionLabel!)),
          ],
        ],
      ),
    );
  }
}

/// 状态标签：告警级别、工单状态、风险等级都用它，颜色由调用方给
class StatusChip extends StatelessWidget {
  const StatusChip({
    super.key,
    required this.label,
    required this.color,
    this.icon,
    this.compact = false,
  });

  final String label;
  final Color color;
  final IconData? icon;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 6 : 8, vertical: compact ? 2 : 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: compact ? 11 : 13, color: color),
            const SizedBox(width: 3),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: compact ? 11 : 12,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

/// 详情页的「标签 : 值」一行
class InfoRow extends StatelessWidget {
  const InfoRow({super.key, required this.label, required this.value, this.valueColor});

  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 76,
            child: Text(
              label,
              style: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
            ),
          ),
          Expanded(
            child: Text(
              value.isEmpty ? '—' : value,
              style: TextStyle(fontSize: 13, color: valueColor ?? const Color(0xFF1E293B)),
            ),
          ),
        ],
      ),
    );
  }
}

/// 数据加载的统一外壳：加载中 / 失败可重试 / 空态 三态一次处理，
/// 页面只需提供 `future` 与「有数据时怎么画」。
class AsyncView<T> extends StatelessWidget {
  const AsyncView({
    super.key,
    required this.future,
    required this.onRetry,
    required this.builder,
    this.loadingMessage,
    this.isEmpty,
    this.emptyMessage = '暂无数据',
    this.emptyIcon = Icons.inbox_outlined,
  });

  final Future<T> future;
  final VoidCallback onRetry;
  final Widget Function(BuildContext context, T data) builder;
  final String? loadingMessage;
  final bool Function(T data)? isEmpty;
  final String emptyMessage;
  final IconData emptyIcon;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return LoadingView(message: loadingMessage ?? '加载中…');
        }
        if (snapshot.hasError) {
          return ErrorRetryView(message: describeError(snapshot.error), onRetry: onRetry);
        }
        final data = snapshot.data;
        if (data == null) {
          return EmptyView(message: emptyMessage, icon: emptyIcon);
        }
        if (isEmpty != null && isEmpty!(data)) {
          return EmptyView(message: emptyMessage, icon: emptyIcon);
        }
        return builder(context, data);
      },
    );
  }
}
