import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';
import 'batch_inspections_page.dart' show batchStatusColor, batchStatusLabel;

/// 批量巡检任务详情 + 进度。
///
/// `GET /api/batch-inspection/{task_id}` 给任务信息、原始巡检点与逐点结果；
/// `GET /api/batch-inspection/{task_id}/progress` 给进度百分比 / 完成数 / 各风险等级计数。
/// 后端没有「成功/失败条数」字段，这里不编造；任务运行中才自动刷新（8 秒一次），
/// 进入终态或页面销毁时立刻停表。
typedef _BatchDetailData = ({Map<String, dynamic> detail, Map<String, dynamic> progress});

class BatchInspectionDetailPage extends StatefulWidget {
  const BatchInspectionDetailPage({super.key, required this.taskId});

  final String taskId;

  @override
  State<BatchInspectionDetailPage> createState() => _BatchInspectionDetailPageState();
}

class _BatchInspectionDetailPageState extends State<BatchInspectionDetailPage> {
  static const Duration _pollInterval = Duration(seconds: 8);

  late Future<_BatchDetailData> _future;
  Timer? _timer;

  /// 运行中轮询到的最新进度。单独存在这里，避免每 8 秒重建 future
  /// 导致 AsyncView 反复闪回「加载中」。
  Map<String, dynamic>? _liveProgress;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<_BatchDetailData> _load() async {
    final detail = await api.batchInspectionDetail(widget.taskId);
    final progress = await api.batchInspectionProgress(widget.taskId);
    return (detail: detail, progress: progress);
  }

  void _reload() {
    if (!mounted) return;
    setState(() {
      _liveProgress = null;
      _future = _load();
    });
  }

  Future<void> _refresh() async {
    _reload();
    try {
      await _future;
    } catch (_) {
      // 失败态交给 AsyncView 展示，这里只负责结束下拉动画
    }
  }

  /// 轮询只拉进度；拿到终态后做一次整页刷新，把逐条结果取回来
  Future<void> _pollOnce() async {
    final displayedStatus = textOf(_liveProgress?['status']);
    try {
      final progress = await api.batchInspectionProgress(widget.taskId);
      if (!mounted) return;
      final status = textOf(progress['status']);
      if (status != displayedStatus &&
          status != 'pending' &&
          status != 'running' &&
          displayedStatus.isNotEmpty) {
        _reload();
        return;
      }
      setState(() => _liveProgress = progress);
    } catch (_) {
      // 轮询失败不打扰用户，下一轮再试
    }
  }

  /// 只在任务还在跑的时候轮询；status 由 progress 接口返回
  void _syncTimer(String status) {
    final active = status == 'pending' || status == 'running';
    final running = _timer != null;
    if (active && !running) {
      _timer = Timer.periodic(_pollInterval, (_) => _pollOnce());
    } else if (!active && running) {
      _timer?.cancel();
      _timer = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('批量巡检详情'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<_BatchDetailData>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载任务进度…',
          emptyMessage: '任务不存在或已被删除',
          emptyIcon: Icons.batch_prediction_outlined,
          isEmpty: (data) => data.detail['success'] == false,
          builder: (context, data) => _buildContent(data),
        ),
      ),
    );
  }

  Widget _buildContent(_BatchDetailData data) {
    final detail = data.detail;
    // 运行中时优先用轮询到的最新进度
    final progress = _liveProgress ?? data.progress;
    final status = textOf(progress['status'], fallback: textOf(detail['status']));
    WidgetsBinding.instance.addPostFrameCallback((_) => _syncTimer(status));

    final results = asMapList(detail['results']);
    final items = asMapList(detail['inspection_items']);

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _buildHeader(detail, progress, status),
        _buildProgressCard(progress, status),
        _buildInfoCard(detail, progress),
        _buildItemsCard(results, items),
      ],
    );
  }

  Widget _buildHeader(
    Map<String, dynamic> detail,
    Map<String, dynamic> progress,
    String status,
  ) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  textOf(detail['task_name'], fallback: '批量巡检任务'),
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF1E293B),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              StatusChip(label: batchStatusLabel(status), color: batchStatusColor(status)),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '任务编号 ${textOf(detail['id'], fallback: widget.taskId)}',
            style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }

  /// 进度卡：字段全部来自 `progress` 接口，不掺入前端推算
  Widget _buildProgressCard(Map<String, dynamic> progress, String status) {
    if (progress.isEmpty) {
      return const SectionCard(
        title: '执行进度',
        child: Text('暂无进度数据', style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
      );
    }
    final percent = intOf(progress['progress']);
    final message = textOf(progress['progress_message']);
    final currentItem = textOf(progress['current_item']);
    final error = textOf(progress['error']);

    return SectionCard(
      title: '执行进度',
      trailing: Text(
        '$percent%',
        style: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w700,
          color: Color(0xFF2563EB),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (percent.clamp(0, 100)) / 100,
              minHeight: 7,
              backgroundColor: const Color(0xFFE2E8F0),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _statItem('已完成', intOf(progress['completed_count']), const Color(0xFF15803D)),
              _statItem('总数', intOf(progress['total_count']), const Color(0xFF2563EB)),
              _statItem('高风险', intOf(progress['high_risk_count']), const Color(0xFFB91C1C)),
              _statItem('中风险', intOf(progress['medium_risk_count']), const Color(0xFFCA8A04)),
              _statItem('低风险', intOf(progress['low_risk_count']), const Color(0xFF0E7490)),
            ],
          ),
          if (message.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              message,
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569)),
            ),
          ],
          if (currentItem.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '当前点位：$currentItem',
              style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
            ),
          ],
          if (error.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              '失败原因：$error',
              style: const TextStyle(fontSize: 12.5, color: Color(0xFFB91C1C)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _statItem(String label, int value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(
            '$value',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: color),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCard(Map<String, dynamic> detail, Map<String, dynamic> progress) {
    final error = textOf(detail['error']);
    return SectionCard(
      title: '任务信息',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InfoRow(label: '所属建筑', value: textOf(detail['building_name'])),
          InfoRow(label: '建筑编号', value: textOf(detail['building_id'])),
          InfoRow(label: '巡检人', value: textOf(detail['inspector'])),
          InfoRow(label: '优先级', value: textOf(detail['priority'])),
          InfoRow(label: '计划时间', value: textOf(detail['scheduled_time'])),
          InfoRow(label: '创建时间', value: formatFullTime(detail['created_at'])),
          InfoRow(label: '开始时间', value: formatFullTime(detail['started_at'])),
          InfoRow(label: '结束时间', value: formatFullTime(detail['completed_at'])),
          if (error.isNotEmpty) InfoRow(label: '错误', value: error),
        ],
      ),
    );
  }

  /// 逐条子任务：任务完成后看 `results`（逐点真实结果），
  /// 还没跑完时 `results` 为空，此时用 `inspection_items` 显示待执行点位。
  Widget _buildItemsCard(
    List<Map<String, dynamic>> results,
    List<Map<String, dynamic>> items,
  ) {
    if (results.isEmpty && items.isEmpty) {
      return const SectionCard(
        title: '巡检点位',
        child: Text('该任务没有巡检点位记录', style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
      );
    }

    return SectionCard(
      title: results.isEmpty ? '待执行点位（${items.length}）' : '巡检结果（${results.length}）',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (results.isEmpty)
            for (final item in items)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    const Icon(Icons.radio_button_unchecked, size: 14, color: Color(0xFFCBD5E1)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        textOf(item['location'], fallback: textOf(item['description'])),
                        style: const TextStyle(fontSize: 13, color: Color(0xFF475569)),
                      ),
                    ),
                  ],
                ),
              )
          else
            for (final result in results) _ResultRow(result: result),
        ],
      ),
    );
  }
}

class _ResultRow extends StatelessWidget {
  const _ResultRow({required this.result});

  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final level = textOf(result['risk_level']);
    final hazards = asList(result['hazards']).map((e) => textOf(e)).where((t) => t.isNotEmpty).toList();
    final suggestion = textOf(result['suggestion']);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  textOf(result['location'], fallback: '巡检点'),
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1E293B),
                  ),
                ),
              ),
              if (level.isNotEmpty)
                StatusChip(
                  label: numOf(result['risk_score']) > 0
                      ? '$level · ${numOf(result['risk_score'])}分'
                      : level,
                  color: riskColor(level),
                  compact: true,
                ),
            ],
          ),
          const SizedBox(height: 3),
          Text(
            '巡检时间 ${formatFullTime(result['inspected_at'])}',
            style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
          ),
          if (hazards.isNotEmpty) ...[
            const SizedBox(height: 5),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final hazard in hazards)
                  StatusChip(label: hazard, color: const Color(0xFFEA580C), compact: true),
              ],
            ),
          ],
          if (suggestion.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              suggestion,
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}
