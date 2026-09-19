import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 批量巡检任务列表。
///
/// 数据源：`GET /api/batch-inspection/list?status=&limit=`（`{total, items}`）。
/// 后端列表**只**给 `id/task_name/building_name/total_count/completed_count/status/
/// priority/inspector/created_at/started_at/completed_at`——没有进度百分比、
/// 没有 scheduled_time，所以这里也不展示这些。
/// 任务 id 是**字符串**（如 `BATCINSP-20260919-54CB3DA3`）。
class BatchInspectionsPage extends StatefulWidget {
  const BatchInspectionsPage({super.key});

  @override
  State<BatchInspectionsPage> createState() => _BatchInspectionsPageState();
}

class _BatchInspectionsPageState extends State<BatchInspectionsPage> {
  /// 后端队列状态：pending / running / success（列表里映射成 completed）/ failed / canceled
  static const List<_BatchStatusFilter> _filters = [
    _BatchStatusFilter(value: '', label: '全部'),
    _BatchStatusFilter(value: 'pending', label: '待执行'),
    _BatchStatusFilter(value: 'running', label: '执行中'),
    _BatchStatusFilter(value: 'completed', label: '已完成'),
    _BatchStatusFilter(value: 'failed', label: '失败'),
    _BatchStatusFilter(value: 'canceled', label: '已取消'),
  ];

  String _status = '';
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.batchInspections(status: _status);
  }

  void _reload() => setState(() => _future = api.batchInspections(status: _status));

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  void _changeStatus(String value) {
    if (value == _status) return;
    setState(() {
      _status = value;
      _future = api.batchInspections(status: _status);
    });
  }

  Future<void> _create() async {
    final created = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const _CreateBatchDialog(),
    );
    if (created == null || !mounted) return;
    _reload();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '任务已创建：${textOf(created['task_id'])}'
          '（${intOf(created['total_count'])} 个点位）',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('批量巡检'),
        actions: [
          IconButton(
            tooltip: '新建批量巡检',
            icon: const Icon(Icons.add_task_outlined),
            onPressed: _create,
          ),
        ],
      ),
      body: Column(
        children: [
          _buildFilterBar(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: AsyncView<Map<String, dynamic>>(
                future: _future,
                onRetry: _reload,
                loadingMessage: '正在加载批量巡检任务…',
                emptyMessage: '暂无批量巡检任务',
                emptyIcon: Icons.batch_prediction_outlined,
                builder: (context, data) {
                  final items = asMapList(data['items']);
                  return ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                    children: [
                      if (items.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 40),
                          child: EmptyView(
                            message: '暂无批量巡检任务，点右下角新建',
                            icon: Icons.batch_prediction_outlined,
                          ),
                        )
                      else
                        for (final item in items) _BatchTaskTile(item: item),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _create,
        icon: const Icon(Icons.add),
        label: const Text('新建批量巡检'),
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
                  selected: _status == filter.value,
                  onSelected: (_) => _changeStatus(filter.value),
                  showCheckmark: false,
                  visualDensity: VisualDensity.compact,
                  backgroundColor: const Color(0xFFF1F5F9),
                  selectedColor: const Color(0xFFFEE2E2),
                  side: BorderSide.none,
                  labelStyle: TextStyle(
                    fontSize: 12,
                    color: _status == filter.value
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
}

/// 批量任务状态 → 颜色与中文名（后端：pending/running/completed/failed/canceled）
Color batchStatusColor(String status) {
  switch (status) {
    case 'completed':
      return const Color(0xFF15803D);
    case 'running':
      return const Color(0xFF2563EB);
    case 'pending':
      return const Color(0xFFCA8A04);
    case 'failed':
      return const Color(0xFFB91C1C);
    case 'canceled':
      return const Color(0xFF64748B);
    default:
      return const Color(0xFF64748B);
  }
}

String batchStatusLabel(String status) {
  switch (status) {
    case 'completed':
      return '已完成';
    case 'running':
      return '执行中';
    case 'pending':
      return '待执行';
    case 'failed':
      return '失败';
    case 'canceled':
      return '已取消';
    default:
      return status.isEmpty ? '未知' : status;
  }
}

class _BatchStatusFilter {
  const _BatchStatusFilter({required this.value, required this.label});

  final String value;
  final String label;
}

class _BatchTaskTile extends StatelessWidget {
  const _BatchTaskTile({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final id = textOf(item['id']);
    final status = textOf(item['status']);
    final total = intOf(item['total_count']);
    final done = intOf(item['completed_count']);
    final buildingName = textOf(item['building_name']);
    final inspector = textOf(item['inspector']);
    final meta = [
      if (buildingName.isNotEmpty) buildingName,
      if (inspector.isNotEmpty) inspector,
      '优先级 ${textOf(item['priority'], fallback: '中')}',
    ].join(' · ');

    return SectionCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: id.isEmpty
            ? null
            : () => Navigator.of(context).pushNamed('/batch-detail', arguments: id),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      textOf(item['task_name'], fallback: '批量巡检任务'),
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
                  StatusChip(label: batchStatusLabel(status), color: batchStatusColor(status), compact: true),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.checklist_outlined, size: 13, color: Color(0xFF94A3B8)),
                  const SizedBox(width: 4),
                  Text(
                    '完成 $done/$total',
                    style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
                  ),
                  const Spacer(),
                  Text(
                    formatRelativeTime(item['created_at']),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                meta,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 新建批量巡检：`POST /api/batch-inspection/create`。
/// 后端要求 body 是一个对象，字段全部可选（未传巡检点位时按楼宇通用清单生成 10 个点位），
/// 所以表单只收「任务名称 / 所属建筑 / 巡检人 / 优先级」这四项真实入参。
class _CreateBatchDialog extends StatefulWidget {
  const _CreateBatchDialog();

  @override
  State<_CreateBatchDialog> createState() => _CreateBatchDialogState();
}

class _CreateBatchDialogState extends State<_CreateBatchDialog> {
  final TextEditingController _nameCtrl = TextEditingController();
  final TextEditingController _buildingCtrl = TextEditingController();
  final TextEditingController _inspectorCtrl = TextEditingController();
  String _priority = '中';
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _inspectorCtrl.text = session.displayName == '未登录' ? '' : session.displayName;
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _buildingCtrl.dispose();
    _inspectorCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = '请填写任务名称');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final data = await api.createBatchInspection(
        taskName: name,
        buildingName: _buildingCtrl.text.trim(),
        inspector: _inspectorCtrl.text.trim(),
        priority: _priority,
      );
      if (!mounted) return;
      Navigator.pop(context, data);
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
      title: const Text('新建批量巡检'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _nameCtrl,
              enabled: !_submitting,
              decoration: const InputDecoration(
                labelText: '任务名称',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _buildingCtrl,
              enabled: !_submitting,
              decoration: const InputDecoration(
                labelText: '所属建筑（可选）',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _inspectorCtrl,
              enabled: !_submitting,
              decoration: const InputDecoration(
                labelText: '巡检人（可选）',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _priority,
              decoration: const InputDecoration(
                labelText: '优先级',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: '高', child: Text('高')),
                DropdownMenuItem(value: '中', child: Text('中')),
                DropdownMenuItem(value: '低', child: Text('低')),
              ],
              onChanged: _submitting ? null : (value) => setState(() => _priority = value ?? '中'),
            ),
            const SizedBox(height: 10),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '未指定巡检点位时，后端会按楼宇通用清单生成 10 个点位。',
                style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
              ),
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
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.pop(context),
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
              : const Text('创建'),
        ),
      ],
    );
  }
}
