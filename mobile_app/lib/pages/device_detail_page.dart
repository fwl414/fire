import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 后端 `/api/devices/{id}/detail` 返回的告警只有英文 level，这里兜底成中文。
const Map<String, String> _alertLevelLabels = {
  'critical': '严重',
  'high': '高',
  'medium': '中',
  'low': '低',
  'info': '提示',
};

/// 设备详情：`/api/devices/{id}/detail` 返回 `{device: {...}, recentAlarms: [...]}`，
/// 注意 device 是 camelCase（与列表接口的 snake_case 不同）。
class DeviceDetailPage extends StatefulWidget {
  const DeviceDetailPage({super.key, required this.id});

  final int id;

  @override
  State<DeviceDetailPage> createState() => _DeviceDetailPageState();
}

class _DeviceDetailPageState extends State<DeviceDetailPage> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.deviceDetail(widget.id);
  }

  void _reload() {
    setState(() => _future = api.deviceDetail(widget.id));
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  /// 去设备台账：先把当前设备写入全局定位，台账页会只显示这台设备
  void _openInLedger() {
    focusedDeviceId.value = widget.id;
    Navigator.of(context).pushNamed('/devices');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设备详情')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载设备详情…',
          emptyMessage: '设备不存在或已被删除',
          emptyIcon: Icons.precision_manufacturing_outlined,
          isEmpty: (data) => asMap(data['device']).isEmpty,
          builder: (context, data) => _buildContent(data),
        ),
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        // 诊断要带上设备台账信息（名称/类型/状态/建筑），所以复用同一个 future 取 device
        child: FutureBuilder<Map<String, dynamic>>(
          future: _future,
          builder: (context, snapshot) {
            final device = asMap(snapshot.data?['device']);
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: device.isEmpty
                        ? null
                        : () => Navigator.of(context)
                            .pushNamed('/device-diagnose', arguments: device),
                    icon: const Icon(Icons.online_prediction_outlined, size: 18),
                    label: const Text('AI 故障诊断'),
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => Navigator.of(context).pushNamed('/records'),
                        icon: const Icon(Icons.fact_check_outlined, size: 18),
                        label: const Text('查看巡检记录'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton.tonalIcon(
                        onPressed: _openInLedger,
                        icon: const Icon(Icons.list_alt_outlined, size: 18),
                        label: const Text('设备台账'),
                      ),
                    ),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildContent(Map<String, dynamic> data) {
    final device = asMap(data['device']);
    final alarms = asMapList(data['recentAlarms']);
    final status = textOf(device['status'], fallback: '未知');

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      textOf(device['name'], fallback: '未命名设备'),
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  StatusChip(label: status, color: _deviceStatusColor(status)),
                ],
              ),
              const SizedBox(height: 12),
              InfoRow(label: '设备编号', value: textOf(device['code'])),
              InfoRow(label: '设备类型', value: textOf(device['type'])),
              InfoRow(label: '安装日期', value: formatFullTime(device['installDate'])),
              InfoRow(label: '上次维保', value: formatFullTime(device['lastMaintenance'])),
              InfoRow(label: '下次维保', value: formatFullTime(device['nextMaintenance'])),
              InfoRow(label: '设备描述', value: textOf(device['description'])),
            ],
          ),
        ),
        SectionCard(
          title: '位置信息',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              InfoRow(label: '楼栋', value: textOf(device['buildingName'])),
              InfoRow(label: '楼层', value: textOf(device['floorName'])),
              InfoRow(label: '位置', value: textOf(device['location'])),
            ],
          ),
        ),
        SectionCard(
          title: '最近告警',
          child: alarms.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    '近期无告警',
                    style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                  ),
                )
              : Column(
                  children: [for (final alarm in alarms) _AlarmRow(alarm: alarm)],
                ),
        ),
      ],
    );
  }
}

class _AlarmRow extends StatelessWidget {
  const _AlarmRow({required this.alarm});

  final Map<String, dynamic> alarm;

  @override
  Widget build(BuildContext context) {
    final id = intOf(alarm['id']);
    final level = textOf(alarm['level'], fallback: 'info');

    return InkWell(
      onTap: id == 0
          ? null
          : () => Navigator.of(context).pushNamed('/alert-detail', arguments: id),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            StatusChip(
              label: _alertLevelLabels[level] ?? level,
              color: severityColor(level),
              compact: true,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                textOf(alarm['title'], fallback: '设备告警'),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, color: Color(0xFF1E293B)),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              formatShortTime(alarm['time']),
              style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
            ),
          ],
        ),
      ),
    );
  }
}

Color _deviceStatusColor(String status) {
  if (status == '正常' || status == '在线' || status == 'online') {
    return const Color(0xFF15803D);
  }
  if (status == '离线' || status == 'offline') {
    return const Color(0xFF64748B);
  }
  return const Color(0xFFEA580C);
}
