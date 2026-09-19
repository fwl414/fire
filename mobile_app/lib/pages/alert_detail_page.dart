import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 后端详情接口只返回英文枚举（`severity_label`/`status_label` 只有列表接口给），
/// 这里按后端字典兜底成中文，避免详情页显示原始英文值。
const Map<String, String> _severityLabels = {
  'critical': '严重',
  'high': '高',
  'medium': '中',
  'low': '低',
};

const Map<String, String> _statusLabels = {
  'pending': '待处置',
  'processing': '处置中',
  'resolved': '已处置',
  'merged': '已合并',
};

/// 告警详情：数据来自 `/api/alerts/{id}`，支持开始处置 / 填写处置结果结单。
class AlertDetailPage extends StatefulWidget {
  const AlertDetailPage({super.key, required this.id});

  final int id;

  @override
  State<AlertDetailPage> createState() => _AlertDetailPageState();
}

class _AlertDetailPageState extends State<AlertDetailPage> {
  late Future<Map<String, dynamic>> _future;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _future = api.alertDetail(widget.id);
  }

  void _reload() {
    setState(() => _future = api.alertDetail(widget.id));
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  /// 处置类操作统一入口：提交期间禁用按钮，成功后提示并重新拉取详情
  Future<void> _submit(Future<void> Function() action, String successMessage) async {
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      await action();
      if (!mounted) return;
      _toast(successMessage);
      _reload();
    } catch (error) {
      _toast(describeError(error, fallback: '操作失败，请稍后重试'));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _startProcessing() => _submit(
        () async {
          // 告警状态只认英文：pending / processing / resolved
          await api.updateAlertStatus(widget.id, 'processing');
        },
        '已开始处置',
      );

  Future<void> _handleAndClose() async {
    final result = await showDialog<String>(
      context: context,
      builder: (_) => const _HandleResultDialog(),
    );
    if (result == null) return;
    if (result.isEmpty) {
      _toast('请填写处置结果');
      return;
    }
    await _submit(
      () async {
        await api.handleAlert(widget.id, handleResult: result, status: 'resolved');
      },
      '已结单',
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('告警详情')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载告警详情…',
          emptyMessage: '告警不存在或已被删除',
          emptyIcon: Icons.notifications_off_outlined,
          isEmpty: (data) => data.isEmpty,
          builder: (context, data) => _buildContent(context, data),
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, Map<String, dynamic> data) {
    final severity = textOf(data['severity'], fallback: 'medium');
    final color = severityColor(severity);
    final severityLabel = textOf(
      data['severity_label'],
      fallback: _severityLabels[severity] ?? severity,
    );
    final status = textOf(data['status']);
    final statusLabel = textOf(
      data['status_label'],
      fallback: _statusLabels[status] ?? status,
    );
    final typeLabel = textOf(
      data['alert_type_label'],
      fallback: textOf(data['alert_type'], fallback: '告警'),
    );

    final handleResult = textOf(data['handle_result']);
    final workorderId = intOf(data['workorder_id']);
    final analysis = _buildAnalysis(data['agent_analysis']);

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _buildHeader(data, severityLabel, statusLabel, typeLabel, color),
        _buildInfo(data, severityLabel, statusLabel, typeLabel),
        if (analysis != null) analysis,
        if (handleResult.isNotEmpty) _buildHandleResult(data),
        if (workorderId > 0) _buildWorkOrderLink(context, workorderId),
        // 已有处置结果说明已闭环，不再提供处置按钮
        if (handleResult.isEmpty) _buildActions(status),
      ],
    );
  }

  Widget _buildHeader(
    Map<String, dynamic> data,
    String severityLabel,
    String statusLabel,
    String typeLabel,
    Color color,
  ) {
    final alertCode = textOf(data['alert_code']);
    final description = textOf(data['description']);

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              StatusChip(
                label: severityLabel,
                color: color,
                icon: Icons.warning_amber_rounded,
              ),
              const SizedBox(width: 8),
              if (statusLabel.isNotEmpty)
                StatusChip(label: statusLabel, color: const Color(0xFF64748B)),
              const Spacer(),
              if (alertCode.isNotEmpty)
                Text(
                  alertCode,
                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            typeLabel,
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: Color(0xFF1E293B),
            ),
          ),
          if (description.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              description,
              style: const TextStyle(fontSize: 13, color: Color(0xFF475569), height: 1.5),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInfo(
    Map<String, dynamic> data,
    String severityLabel,
    String statusLabel,
    String typeLabel,
  ) {
    final value = textOf(data['alert_value']);
    final unit = textOf(data['alert_unit']);
    final repeatCount = intOf(data['repeat_count']);
    final escalationReason = textOf(data['escalation_reason']);

    return SectionCard(
      title: '告警信息',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InfoRow(label: '告警类型', value: typeLabel),
          InfoRow(label: '级别', value: severityLabel),
          InfoRow(label: '状态', value: statusLabel),
          InfoRow(label: '设备', value: textOf(data['device_name'])),
          InfoRow(label: '设备编码', value: textOf(data['device_code'])),
          InfoRow(label: '位置', value: textOf(data['location'])),
          InfoRow(label: '建筑', value: textOf(data['building_name'])),
          InfoRow(label: '告警值', value: value.isEmpty ? '' : '$value$unit'),
          InfoRow(label: '重复次数', value: repeatCount > 1 ? '$repeatCount 次' : ''),
          if (data['escalated'] == true)
            const InfoRow(label: '升级状态', value: '已升级', valueColor: Color(0xFFDC2626)),
          if (escalationReason.isNotEmpty)
            InfoRow(label: '升级原因', value: escalationReason, valueColor: const Color(0xFFDC2626)),
          InfoRow(label: '首次发生', value: formatFullTime(data['first_seen_at'])),
          InfoRow(label: '最近发生', value: formatFullTime(data['last_seen_at'])),
          InfoRow(label: '创建时间', value: formatFullTime(data['created_at'])),
        ],
      ),
    );
  }

  /// 智能分析结构由后端给（trend / most_likely_causes / immediate_actions），
  /// 缺字段就整块不显示，不做崩溃式强转。
  Widget? _buildAnalysis(dynamic raw) {
    final analysis = asMap(raw);
    if (analysis.isEmpty) return null;

    final trend = textOf(asMap(analysis['trend'])['description']);
    final causes = asList(analysis['most_likely_causes'])
        .map((e) => textOf(e))
        .where((text) => text.isNotEmpty)
        .toList();
    final actions = asList(analysis['immediate_actions'])
        .map((e) => textOf(e))
        .where((text) => text.isNotEmpty)
        .toList();
    if (trend.isEmpty && causes.isEmpty && actions.isEmpty) return null;

    return SectionCard(
      title: '智能分析',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (trend.isNotEmpty) _analysisLine('趋势', trend),
          if (causes.isNotEmpty) _analysisLine('可能原因', causes.join('；')),
          if (actions.isNotEmpty) _analysisLine('处置建议', actions.join('；')),
        ],
      ),
    );
  }

  Widget _analysisLine(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
          const SizedBox(height: 3),
          Text(
            value,
            style: const TextStyle(fontSize: 13, color: Color(0xFF334155), height: 1.5),
          ),
        ],
      ),
    );
  }

  Widget _buildHandleResult(Map<String, dynamic> data) {
    final handledById = intOf(data['handled_by']);
    final handledBy = handledById > 0
        ? '用户 #$handledById'
        : textOf(data['handled_by']);

    return SectionCard(
      title: '处置结果',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            textOf(data['handle_result']),
            style: const TextStyle(fontSize: 13, color: Color(0xFF334155), height: 1.5),
          ),
          const SizedBox(height: 10),
          InfoRow(label: '处置人', value: handledBy),
          InfoRow(label: '处置时间', value: formatFullTime(data['handled_at'])),
        ],
      ),
    );
  }

  Widget _buildWorkOrderLink(BuildContext context, int workorderId) {
    return SectionCard(
      child: SizedBox(
        width: double.infinity,
        child: OutlinedButton.icon(
          onPressed: () => Navigator.of(context).pushNamed(
            '/workorder-detail',
            arguments: workorderId,
          ),
          icon: const Icon(Icons.assignment_outlined, size: 18),
          label: const Text('查看关联工单'),
        ),
      ),
    );
  }

  Widget _buildActions(String status) {
    // 已进入处置中就不必再点「开始处置」
    final canStart = status != 'processing' && status != 'resolved';

    return SectionCard(
      title: '处置操作',
      child: Column(
        children: [
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: (_submitting || !canStart) ? null : _startProcessing,
              icon: const Icon(Icons.play_arrow_outlined, size: 18),
              label: const Text('开始处置'),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _submitting ? null : _handleAndClose,
              icon: const Icon(Icons.check_circle_outline, size: 18),
              label: const Text('填写处置结果并结单'),
            ),
          ),
        ],
      ),
    );
  }
}

/// 独立成 StatefulWidget 是为了让 TextEditingController 随对话框一起销毁
class _HandleResultDialog extends StatefulWidget {
  const _HandleResultDialog();

  @override
  State<_HandleResultDialog> createState() => _HandleResultDialogState();
}

class _HandleResultDialogState extends State<_HandleResultDialog> {
  final TextEditingController _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('填写处置结果'),
      content: TextField(
        controller: _controller,
        maxLines: 4,
        autofocus: true,
        decoration: const InputDecoration(
          hintText: '描述现场核查与处置情况',
          border: OutlineInputBorder(),
          alignLabelWithHint: true,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _controller.text.trim()),
          child: const Text('提交并结单'),
        ),
      ],
    );
  }
}
