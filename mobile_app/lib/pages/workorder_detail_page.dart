import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 工单详情：展示真实字段，并按当前状态给出可执行的流转按钮。
class WorkorderDetailPage extends StatefulWidget {
  const WorkorderDetailPage({super.key, required this.id});

  final int id;

  @override
  State<WorkorderDetailPage> createState() => _WorkorderDetailPageState();
}

class _WorkorderDetailPageState extends State<WorkorderDetailPage> {
  late Future<Map<String, dynamic>> _future;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _future = api.workorderDetail(widget.id);
  }

  void _reload() {
    setState(() => _future = api.workorderDetail(widget.id));
  }

  Future<void> _refresh() async {
    final future = api.workorderDetail(widget.id);
    setState(() => _future = future);
    try {
      await future;
    } catch (_) {
      // 失败态交给 AsyncView 展示，这里只负责结束下拉动画
    }
  }

  /// 所有流转操作共用：串行执行、成功提示并重拉详情、失败提示原因。
  Future<void> _run(Future<void> Function() action, String successMessage) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(successMessage)));
      _reload();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(describeError(e))));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('工单详情')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载工单详情…',
          isEmpty: (data) => data.isEmpty,
          emptyMessage: '工单不存在或已删除',
          emptyIcon: Icons.assignment_outlined,
          builder: (context, data) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              _buildHeader(data),
              _buildInfo(data),
              _buildDescription(data),
              _buildSourceRecord(context, data),
              _buildSourceAlert(context, data),
              _buildProcessResult(data),
              _buildActions(data),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(Map<String, dynamic> data) {
    final status = textOf(data['status'], fallback: '未知状态');
    final risk = textOf(data['risk_level']);

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            textOf(data['title'], fallback: '未命名工单'),
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w600,
              color: Color(0xFF1E293B),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              StatusChip(label: status, color: workorderStatusColor(status)),
              if (risk.isNotEmpty) StatusChip(label: risk, color: riskColor(risk)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfo(Map<String, dynamic> data) {
    final assignee = textOf(data['assignee_name']);
    final deviceId = intOf(data['device_id']);
    final ticketType = textOf(data['ticket_type']);
    final source = textOf(data['source']);

    return SectionCard(
      title: '工单信息',
      child: Column(
        children: [
          InfoRow(label: '优先级', value: textOf(data['priority'])),
          if (ticketType.isNotEmpty) InfoRow(label: '工单类型', value: ticketType),
          InfoRow(label: '位置', value: textOf(data['location'])),
          InfoRow(label: '楼栋', value: textOf(data['building_name'])),
          if (deviceId != 0) InfoRow(label: '关联设备', value: '设备 #$deviceId'),
          InfoRow(label: '负责人', value: assignee.isEmpty ? '未指派' : assignee),
          InfoRow(label: '上报人', value: textOf(data['reporter_name'])),
          if (source.isNotEmpty) InfoRow(label: '来源', value: source),
          InfoRow(
            label: '整改时限',
            value: formatFullTime(data['deadline'], fallback: '未设置'),
          ),
          InfoRow(label: '创建时间', value: formatFullTime(data['created_at'])),
          InfoRow(label: '更新时间', value: formatFullTime(data['updated_at'])),
          InfoRow(label: '备注', value: textOf(data['remark'])),
        ],
      ),
    );
  }

  /// 来源巡检记录：后端 `record_id` 是主库巡检记录 id，可直接跳记录详情
  Widget _buildSourceRecord(BuildContext context, Map<String, dynamic> data) {
    final recordId = intOf(data['record_id']);
    if (recordId == 0) return const SizedBox.shrink();

    return SectionCard(
      title: '来源巡检记录',
      child: InkWell(
        onTap: () => Navigator.of(context)
            .pushNamed('/record-detail', arguments: recordId),
        child: Row(
          children: [
            const Icon(Icons.fact_check_outlined, size: 18, color: Color(0xFF2563EB)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '巡检记录 #$recordId',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF1E293B),
                ),
              ),
            ),
            const Icon(Icons.chevron_right, size: 18, color: Color(0xFFCBD5E1)),
          ],
        ),
      ),
    );
  }

  /// 处理结果与复查信息：待受理阶段这些字段都是空的，此时不展示整块
  Widget _buildProcessResult(Map<String, dynamic> data) {
    final handleResult = textOf(data['handle_result']);
    final reviewResult = textOf(data['review_result']);
    final reviewNote = textOf(data['review_note']);
    final reviewedAt = textOf(data['reviewed_at']);
    if (handleResult.isEmpty &&
        reviewResult.isEmpty &&
        reviewNote.isEmpty &&
        reviewedAt.isEmpty) {
      return const SizedBox.shrink();
    }

    return SectionCard(
      title: '处理与复查',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (handleResult.isNotEmpty) ...[
            const Text('处理结果', style: _labelStyle),
            const SizedBox(height: 4),
            Text(handleResult, style: _bodyStyle),
          ],
          if (reviewResult.isNotEmpty) ...[
            const SizedBox(height: 10),
            InfoRow(label: '复查结论', value: reviewResult),
          ],
          if (reviewedAt.isNotEmpty)
            InfoRow(
              label: '复查时间',
              value: formatFullTime(reviewedAt, fallback: '未复查'),
            ),
          if (reviewNote.isNotEmpty) ...[
            const SizedBox(height: 6),
            const Text('复查意见', style: _labelStyle),
            const SizedBox(height: 4),
            Text(reviewNote, style: _bodyStyle),
          ],
        ],
      ),
    );
  }

  Widget _buildDescription(Map<String, dynamic> data) {
    return SectionCard(
      title: '问题描述',
      child: Text(
        textOf(data['description'], fallback: '暂无描述'),
        style: const TextStyle(
          fontSize: 13,
          color: Color(0xFF334155),
          height: 1.6,
        ),
      ),
    );
  }

  Widget _buildSourceAlert(BuildContext context, Map<String, dynamic> data) {
    final alert = asMap(data['source_alert']);
    if (alert.isEmpty) return const SizedBox.shrink();

    final severity = textOf(alert['severity']);
    final alertType = textOf(alert['alert_type']);
    final repeatCount = intOf(alert['repeat_count']);
    // 后端 source_alert 不带描述字段，这里用类型/级别/重复次数拼一句可读说明
    final summary = [
      if (alertType.isNotEmpty) alertType,
      if (severity.isNotEmpty) '级别 $severity',
      if (repeatCount > 1) '重复 $repeatCount 次',
      if (alert['escalated'] == true) '已升级',
    ].join(' · ');

    return SectionCard(
      title: '关联告警',
      child: InkWell(
        onTap: () {
          final id = intOf(alert['id']);
          if (id == 0) return;
          Navigator.of(context).pushNamed('/alert-detail', arguments: id);
        },
        child: Row(
          children: [
            Icon(
              Icons.warning_amber_rounded,
              size: 18,
              color: severityColor(severity),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '告警编号 ${textOf(alert['alert_code'], fallback: '未知')}',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF1E293B),
                    ),
                  ),
                  if (summary.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      summary,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF64748B),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const Icon(Icons.chevron_right, size: 18, color: Color(0xFFCBD5E1)),
          ],
        ),
      ),
    );
  }

  Widget _buildActions(Map<String, dynamic> data) {
    final status = textOf(data['status']);
    // 已闭环（已完成 / 已关闭）不再提供流转入口
    if (status == '已完成' || status == '已关闭') return const SizedBox.shrink();

    final buttons = <Widget>[];
    if (status == '待受理' && intOf(data['assignee_id']) == 0) {
      buttons.add(_actionButton(
        '领取工单',
        () => api.claimWorkorder(widget.id),
        '已领取工单',
        primary: true,
      ));
    }
    switch (status) {
      case '待受理':
        buttons.add(_actionButton(
          '开始处理',
          () => api.updateWorkorderStatus(widget.id, '处理中'),
          '工单已进入处理中',
          primary: true,
        ));
        break;
      case '处理中':
        buttons.add(_actionButton(
          '提交复查',
          () => api.updateWorkorderStatus(widget.id, '待复查'),
          '工单已提交复查',
          primary: true,
        ));
        break;
      case '待复查':
        buttons.add(_actionButton(
          '完成',
          () => api.updateWorkorderStatus(widget.id, '已完成'),
          '工单已完成',
          primary: true,
        ));
        break;
    }
    buttons.add(_actionButton(
      '关闭',
      () => api.updateWorkorderStatus(widget.id, '已关闭'),
      '工单已关闭',
      primary: false,
    ));

    return SectionCard(
      title: '工单操作',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 10, runSpacing: 10, children: buttons),
          if (_busy) ...[
            const SizedBox(height: 12),
            const SizedBox(
              height: 2,
              child: LinearProgressIndicator(minHeight: 2),
            ),
          ],
        ],
      ),
    );
  }

  Widget _actionButton(
    String label,
    Future<dynamic> Function() action,
    String successMessage, {
    required bool primary,
  }) {
    final onPressed = _busy
        ? null
        : () => _run(() async {
              await action();
            }, successMessage);
    return primary
        ? FilledButton(onPressed: onPressed, child: Text(label))
        : OutlinedButton(onPressed: onPressed, child: Text(label));
  }
}

const TextStyle _labelStyle = TextStyle(
  fontSize: 12.5,
  fontWeight: FontWeight.w600,
  color: Color(0xFF64748B),
);

const TextStyle _bodyStyle = TextStyle(
  fontSize: 13,
  height: 1.6,
  color: Color(0xFF334155),
);
