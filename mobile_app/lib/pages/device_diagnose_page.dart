import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 设备 AI 故障诊断：`POST /api/intelligence/diagnose-device` → `{ok, data}`。
///
/// 入参就是后端 `DeviceDiagnoseRequest` 的五个字段
/// （`device_id/device_name/device_type/status/building_name`，其中 device_id 是字符串且可空）。
/// `fault_causes[].weight` 是**参考权重**不是故障概率，返回里 `weight_note` 已说明口径，
/// 页面原样展示、不额外解读。
class DeviceDiagnosePage extends StatefulWidget {
  const DeviceDiagnosePage({super.key, this.device = const <String, dynamic>{}});

  /// 从设备详情跳进来时带上设备台账信息（字段为详情接口的 camelCase）
  final Map<String, dynamic> device;

  @override
  State<DeviceDiagnosePage> createState() => _DeviceDiagnosePageState();
}

class _DeviceDiagnosePageState extends State<DeviceDiagnosePage> {
  static const List<String> _statuses = ['正常', '故障', '离线'];

  late final TextEditingController _idCtrl;
  late final TextEditingController _nameCtrl;
  late final TextEditingController _typeCtrl;
  late final TextEditingController _buildingCtrl;
  late String _status;

  Future<Map<String, dynamic>>? _future;

  @override
  void initState() {
    super.initState();
    final device = widget.device;
    _idCtrl = TextEditingController(text: textOf(device['id']));
    _nameCtrl = TextEditingController(text: textOf(device['name']));
    _typeCtrl = TextEditingController(text: textOf(device['type']));
    _buildingCtrl = TextEditingController(text: textOf(device['buildingName']));
    final status = textOf(device['status']);
    _status = _statuses.contains(status) ? status : '故障';
  }

  @override
  void dispose() {
    _idCtrl.dispose();
    _nameCtrl.dispose();
    _typeCtrl.dispose();
    _buildingCtrl.dispose();
    super.dispose();
  }

  void _diagnose() {
    FocusScope.of(context).unfocus();
    setState(() {
      _future = api.diagnoseDevice(
        deviceId: _idCtrl.text.trim(),
        deviceName: _nameCtrl.text.trim(),
        deviceType: _typeCtrl.text.trim(),
        status: _status,
        buildingName: _buildingCtrl.text.trim(),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设备 AI 诊断')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          SectionCard(
            title: '诊断输入',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _idCtrl,
                  decoration: const InputDecoration(
                    labelText: '设备编号（台账 id，可留空）',
                    helperText: '填写且属于本租户时，后端会用台账数据调整权重',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _nameCtrl,
                  decoration: const InputDecoration(
                    labelText: '设备名称',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _typeCtrl,
                  decoration: const InputDecoration(
                    labelText: '设备类型',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _status,
                  decoration: const InputDecoration(
                    labelText: '设备状态',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final status in _statuses)
                      DropdownMenuItem(value: status, child: Text(status)),
                  ],
                  onChanged: (value) => setState(() => _status = value ?? '故障'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _buildingCtrl,
                  decoration: const InputDecoration(
                    labelText: '所属建筑',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _diagnose,
                    icon: const Icon(Icons.online_prediction_outlined, size: 18),
                    label: const Text('开始诊断'),
                  ),
                ),
              ],
            ),
          ),
          if (_future == null)
            const Padding(
              padding: EdgeInsets.only(top: 24),
              child: EmptyView(
                message: '填写设备信息后点「开始诊断」，将给出故障原因参考与维修建议',
                icon: Icons.build_outlined,
              ),
            )
          else
            AsyncView<Map<String, dynamic>>(
              future: _future!,
              onRetry: _diagnose,
              loadingMessage: '正在诊断…',
              emptyMessage: '未返回诊断结果',
              emptyIcon: Icons.build_outlined,
              isEmpty: (data) => data.isEmpty,
              builder: (context, data) => _buildResult(data),
            ),
        ],
      ),
    );
  }

  Widget _buildResult(Map<String, dynamic> data) {
    final causes = asMapList(data['fault_causes']);
    final suggestions = asMapList(data['repair_suggestions']);
    final tips = asList(data['maintenance_tips']).map((e) => textOf(e)).where((t) => t.isNotEmpty).toList();
    final signals = asMap(data['device_signals']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionCard(
          title: '诊断结论',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      textOf(data['most_likely_cause'], fallback: '暂无法定位'),
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFFB91C1C),
                      ),
                    ),
                  ),
                  StatusChip(
                    label: '信息完整度 ${(numOf(data['confidence']) * 100).toStringAsFixed(0)}%',
                    color: const Color(0xFF2563EB),
                    compact: true,
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                '设备状态：${textOf(data['device_status'], fallback: '未知')}'
                '｜预计维修工时 ${textOf(data['estimated_repair_time'], fallback: '—')}',
                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
              ),
              if (textOf(data['weight_note']).isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  textOf(data['weight_note']),
                  style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8), height: 1.5),
                ),
              ],
            ],
          ),
        ),
        if (signals.isNotEmpty) _buildSignals(signals),
        if (causes.isNotEmpty)
          SectionCard(
            title: '可能原因（参考权重）',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final cause in causes) _CauseRow(cause: cause),
              ],
            ),
          ),
        if (suggestions.isNotEmpty)
          SectionCard(
            title: '维修建议',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in suggestions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        StatusChip(
                          label: '${intOf(item['priority'])}',
                          color: const Color(0xFF2563EB),
                          compact: true,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                textOf(item['action'], fallback: '处置措施'),
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF1E293B),
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                textOf(item['detail']),
                                style: const TextStyle(
                                  fontSize: 12.5,
                                  color: Color(0xFF475569),
                                  height: 1.5,
                                ),
                              ),
                              if (textOf(item['estimated_time']).isNotEmpty)
                                Text(
                                  '预计 ${textOf(item['estimated_time'])}',
                                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (tips.isNotEmpty)
          SectionCard(
            title: '日常维护提示',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final tip in tips)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 5),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(top: 6),
                          child: Icon(Icons.circle, size: 5, color: Color(0xFF94A3B8)),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            tip,
                            style: const TextStyle(
                              fontSize: 12.5,
                              color: Color(0xFF334155),
                              height: 1.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }

  /// `device_signals` 只在能拿到设备台账时才有值，null 的项不显示
  Widget _buildSignals(Map<String, dynamic> signals) {
    final rows = <Widget>[];
    if (signals['ageYears'] != null) {
      rows.add(InfoRow(label: '投用年限', value: '${numOf(signals['ageYears'])} 年'));
    }
    if (signals['daysSinceMaintenance'] != null) {
      rows.add(InfoRow(label: '距上次维保', value: '${intOf(signals['daysSinceMaintenance'])} 天'));
    }
    if (signals['maintenanceOverdue'] != null) {
      rows.add(InfoRow(label: '维保是否超期', value: signals['maintenanceOverdue'] == true ? '是' : '否'));
    }
    if (signals['daysSinceSeen'] != null) {
      rows.add(InfoRow(label: '距最近上报', value: '${intOf(signals['daysSinceSeen'])} 天'));
    }
    if (rows.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: '设备台账信号',
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: rows),
    );
  }
}

class _CauseRow extends StatelessWidget {
  const _CauseRow({required this.cause});

  final Map<String, dynamic> cause;

  @override
  Widget build(BuildContext context) {
    final weight = numOf(cause['weight']);
    final evidence = asList(cause['evidence']).map((e) => textOf(e)).where((t) => t.isNotEmpty).toList();
    final fromDevice = textOf(cause['basis']) == 'device_data';

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  textOf(cause['cause'], fallback: '原因'),
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1E293B),
                  ),
                ),
              ),
              StatusChip(
                label: fromDevice ? '台账数据' : '知识库经验',
                color: fromDevice ? const Color(0xFF15803D) : const Color(0xFF94A3B8),
                compact: true,
              ),
              const SizedBox(width: 6),
              Text(
                '${(weight * 100).toStringAsFixed(0)}%',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFFDC2626),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: weight.clamp(0, 1).toDouble(),
              minHeight: 6,
              backgroundColor: const Color(0xFFF1F5F9),
            ),
          ),
          if (textOf(cause['description']).isNotEmpty) ...[
            const SizedBox(height: 5),
            Text(
              textOf(cause['description']),
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
            ),
          ],
          for (final item in evidence)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(
                '· $item',
                style: const TextStyle(fontSize: 11.5, color: Color(0xFF94A3B8), height: 1.5),
              ),
            ),
        ],
      ),
    );
  }
}
