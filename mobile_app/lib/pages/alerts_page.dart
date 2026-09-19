import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 告警列表：数据来自 `/api/alert/list`（真实告警，支持按级别筛选）。
/// 原先整页是写死的 6 条假数据，这里全部替换为后端数据。
class AlertsPage extends StatefulWidget {
  const AlertsPage({super.key});

  @override
  State<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends State<AlertsPage> {
  static const List<_SeverityFilter> _filters = [
    _SeverityFilter(value: '', label: '全部'),
    _SeverityFilter(value: 'critical', label: '严重'),
    _SeverityFilter(value: 'high', label: '高'),
    _SeverityFilter(value: 'medium', label: '中'),
    _SeverityFilter(value: 'low', label: '低'),
  ];

  String _severity = '';
  late Future<Map<String, dynamic>> _future;

  /// 已消费的推送计数：build 里发现 tick 变了才重新拉取，
  /// 避免在 build 期间直接 setState。
  late int _seenTick;

  @override
  void initState() {
    super.initState();
    _seenTick = alertPushTick.value;
    _future = api.alerts(severity: _severity);
  }

  void _reload() {
    setState(() => _future = api.alerts(severity: _severity));
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  void _changeSeverity(String value) {
    if (value == _severity) return;
    setState(() {
      _severity = value;
      _future = api.alerts(severity: _severity);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildFilterBar(),
        Expanded(
          // WebSocket 收到新告警时 alertPushTick +1，这里自动重新拉取列表
          child: ValueListenableBuilder<int>(
            valueListenable: alertPushTick,
            builder: (context, tick, _) {
              if (tick != _seenTick) {
                _seenTick = tick;
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted) _reload();
                });
              }
              return _buildList();
            },
          ),
        ),
      ],
    );
  }

  Widget _buildFilterBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final filter in _filters)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(filter.label),
                  selected: _severity == filter.value,
                  onSelected: (_) => _changeSeverity(filter.value),
                  showCheckmark: false,
                  visualDensity: VisualDensity.compact,
                  backgroundColor: const Color(0xFFF1F5F9),
                  selectedColor: const Color(0xFFFEE2E2),
                  side: BorderSide.none,
                  labelStyle: TextStyle(
                    fontSize: 12,
                    color: _severity == filter.value
                        ? const Color(0xFFDC2626)
                        : const Color(0xFF475569),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildList() {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: AsyncView<Map<String, dynamic>>(
        future: _future,
        onRetry: _reload,
        loadingMessage: '正在加载告警…',
        emptyMessage: '暂无告警',
        emptyIcon: Icons.notifications_off_outlined,
        builder: (context, data) {
          final items = asMapList(data['items']);
          // 空态也放进可滚动列表，保证还能下拉刷新
          if (items.isEmpty) {
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                SizedBox(height: 120),
                EmptyView(message: '暂无告警', icon: Icons.notifications_off_outlined),
              ],
            );
          }
          return ListView.builder(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
            itemCount: items.length,
            itemBuilder: (context, index) => _AlertCard(item: items[index]),
          );
        },
      ),
    );
  }
}

class _SeverityFilter {
  const _SeverityFilter({required this.value, required this.label});

  final String value;
  final String label;
}

/// 单条告警卡片：级别 chip + 类型 + 描述 + 位置/设备 + 相对时间，
/// 重复与升级状态单独提示（后端已经给了 repeat_count / escalated）。
class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final severity = textOf(item['severity'], fallback: 'medium');
    final color = severityColor(severity);
    final severityLabel = textOf(item['severity_label'], fallback: severity);
    final typeLabel = textOf(
      item['alert_type_label'],
      fallback: textOf(item['alert_type'], fallback: '告警'),
    );
    final description = textOf(item['description'], fallback: typeLabel);
    final place = [
      textOf(item['location'], fallback: textOf(item['building_name'])),
      textOf(item['device_name'], fallback: textOf(item['device_code'])),
    ].where((text) => text.isNotEmpty).join(' · ');

    final repeatCount = intOf(item['repeat_count']);
    final escalated = item['escalated'] == true;

    return SectionCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          final id = intOf(item['id']);
          if (id == 0) return;
          Navigator.of(context).pushNamed('/alert-detail', arguments: id);
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  StatusChip(
                    label: severityLabel,
                    color: color,
                    icon: Icons.warning_amber_rounded,
                    compact: true,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      typeLabel,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    formatRelativeTime(item['created_at']),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, color: Color(0xFF475569), height: 1.4),
              ),
              if (place.isNotEmpty) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(Icons.place_outlined, size: 13, color: Color(0xFF94A3B8)),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        place,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                      ),
                    ),
                  ],
                ),
              ],
              if (repeatCount > 1 || escalated) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    if (repeatCount > 1)
                      StatusChip(
                        label: '重复 $repeatCount 次',
                        color: const Color(0xFF64748B),
                        compact: true,
                      ),
                    if (repeatCount > 1 && escalated) const SizedBox(width: 8),
                    if (escalated)
                      const StatusChip(
                        label: '已升级',
                        color: Color(0xFFDC2626),
                        icon: Icons.trending_up,
                        compact: true,
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
