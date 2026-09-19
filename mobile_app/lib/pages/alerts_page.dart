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

  /// 多选合并：进入多选后点选若干条，按选中顺序的第一条作为主告警
  bool _selectionMode = false;
  final List<int> _selected = <int>[];
  bool _merging = false;

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

  void _enterSelection([int? id]) {
    setState(() {
      _selectionMode = true;
      _selected
        ..clear()
        ..addAll(id == null ? const <int>[] : <int>[id]);
    });
  }

  void _exitSelection() {
    setState(() {
      _selectionMode = false;
      _selected.clear();
    });
  }

  void _toggleSelect(int id) {
    setState(() {
      if (_selected.contains(id)) {
        _selected.remove(id);
      } else {
        _selected.add(id);
      }
    });
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  /// 合并告警：`POST /api/alerts/merge`，body `{primary_id, duplicate_ids}`。
  /// 主告警不存在时后端 404、参数缺失 400，错误原因在 `detail` 里，由 describeError 转成提示。
  Future<void> _merge() async {
    if (_selected.length < 2) {
      _toast('请至少选择 2 条告警再合并');
      return;
    }
    final ids = List<int>.from(_selected);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('合并告警'),
        content: Text(
          '将以第一条为主告警（告警 #${ids.first}），'
          '其余 ${ids.length - 1} 条会被合并到它下面：\n'
          '被合并告警会标记为「已合并」并累加重复次数，'
          '主告警取其中更高的级别。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认合并'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _merging = true);
    try {
      final data = await api.mergeAlerts(
        primaryId: ids.first,
        duplicateIds: ids.sublist(1),
      );
      if (!mounted) return;
      final mergedCount = asList(data['merged_ids']).length;
      _exitSelection();
      _reload();
      _toast('已合并 $mergedCount 条到主告警 #${intOf(data['primary_id'])}');
    } catch (e) {
      if (!mounted) return;
      _toast(describeError(e));
    } finally {
      if (mounted) setState(() => _merging = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildActionBar(),
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

  /// 顶部工具栏：「统计」入口 + 多选合并控制
  Widget _buildActionBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(4, 4, 8, 0),
      child: Row(
        children: [
          TextButton.icon(
            onPressed: _merging
                ? null
                : () => Navigator.of(context).pushNamed('/alert-statistics'),
            icon: const Icon(Icons.insights_outlined, size: 18),
            label: const Text('统计', style: TextStyle(fontSize: 13)),
          ),
          const Spacer(),
          if (_selectionMode) ...[
            Text(
              '已选 ${_selected.length}',
              style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
            ),
            const SizedBox(width: 4),
            TextButton(
              onPressed: _merging ? null : _merge,
              child: const Text('合并', style: TextStyle(fontSize: 13)),
            ),
            TextButton(
              onPressed: _merging ? null : _exitSelection,
              child: const Text('取消', style: TextStyle(fontSize: 13)),
            ),
          ] else
            TextButton.icon(
              onPressed: () => _enterSelection(),
              icon: const Icon(Icons.merge_type, size: 18),
              label: const Text('多选合并', style: TextStyle(fontSize: 13)),
            ),
        ],
      ),
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
            itemBuilder: (context, index) {
              final item = items[index];
              final id = intOf(item['id']);
              final selected = _selected.contains(id);
              return _AlertCard(
                item: item,
                selectionMode: _selectionMode,
                selected: selected,
                onTap: _selectionMode
                    ? () {
                        if (id != 0) _toggleSelect(id);
                      }
                    : null,
                onLongPress: _selectionMode || id == 0 ? null : () => _enterSelection(id),
              );
            },
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
/// 多选合并模式下左侧显示勾选框，点击切换选中。
class _AlertCard extends StatelessWidget {
  const _AlertCard({
    required this.item,
    this.selectionMode = false,
    this.selected = false,
    this.onTap,
    this.onLongPress,
  });

  final Map<String, dynamic> item;
  final bool selectionMode;
  final bool selected;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  void _openDetail(BuildContext context) {
    final id = intOf(item['id']);
    if (id == 0) return;
    Navigator.of(context).pushNamed('/alert-detail', arguments: id);
  }

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
        onTap: onTap ?? () => _openDetail(context),
        onLongPress: onLongPress,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (selectionMode) ...[
                    Icon(
                      selected ? Icons.check_circle : Icons.radio_button_unchecked,
                      size: 19,
                      color: selected ? const Color(0xFFDC2626) : const Color(0xFFCBD5E1),
                    ),
                    const SizedBox(width: 8),
                  ],
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
