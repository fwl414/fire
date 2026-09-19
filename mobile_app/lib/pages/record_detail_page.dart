import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 巡检记录详情：只有这个接口返回 `report` 正文与 `agent_steps`。
class RecordDetailPage extends StatefulWidget {
  const RecordDetailPage({super.key, required this.id});

  final int id;

  @override
  State<RecordDetailPage> createState() => _RecordDetailPageState();
}

class _RecordDetailPageState extends State<RecordDetailPage> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.recordDetail(widget.id);
  }

  void _reload() {
    setState(() => _future = api.recordDetail(widget.id));
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('巡检记录详情')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载巡检详情…',
          emptyMessage: '记录不存在或已被删除',
          emptyIcon: Icons.fact_check_outlined,
          isEmpty: (data) => data.isEmpty,
          builder: (context, data) => _buildContent(data),
        ),
      ),
    );
  }

  Widget _buildContent(Map<String, dynamic> data) {
    final level = textOf(data['risk_level']);
    final color = riskColor(level);
    final hazards = asList(data['hazards'])
        .map((item) => textOf(item))
        .where((text) => text.isNotEmpty)
        .toList();
    final steps = _agentSteps(data['agent_steps']);
    final suggestion = textOf(data['suggestion']);
    final report = textOf(data['report']);
    final images = _imageRequests(data);
    final model = [
      textOf(data['model_provider']),
      textOf(data['model_name']),
    ].where((text) => text.isNotEmpty).join(' / ');

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        SectionCard(
          child: Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${intOf(data['risk_score'])}',
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: color,
                      height: 1.1,
                    ),
                  ),
                  const Text(
                    '风险评分',
                    style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (level.isNotEmpty) StatusChip(label: level, color: color),
                    const SizedBox(height: 8),
                    Text(
                      formatFullTime(data['created_at']),
                      style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        SectionCard(
          title: '基本信息',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              InfoRow(label: '设备名称', value: textOf(data['device_name'])),
              InfoRow(label: '设备编号', value: textOf(data['device_code'])),
              InfoRow(label: '位置', value: textOf(data['location'])),
              InfoRow(label: '现场描述', value: textOf(data['description'])),
              InfoRow(
                label: '视觉模型',
                value: data['used_vision_api'] == true ? '已调用' : '未调用',
              ),
              InfoRow(label: '模型', value: model),
            ],
          ),
        ),
        SectionCard(
          title: '识别到的隐患',
          child: hazards.isEmpty
              ? const Text(
                  '未识别到隐患',
                  style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final hazard in hazards)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Padding(
                              padding: EdgeInsets.only(top: 5),
                              child: Icon(Icons.circle,
                                  size: 6, color: Color(0xFFEA580C)),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                hazard,
                                style: const TextStyle(
                                  fontSize: 13,
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
        if (suggestion.isNotEmpty)
          SectionCard(
            title: '处置建议',
            child: Text(
              suggestion,
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xFF334155),
                height: 1.6,
              ),
            ),
          ),
        if (report.isNotEmpty)
          SectionCard(
            title: 'AI 巡检报告',
            child: SelectableText(
              report,
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xFF334155),
                height: 1.6,
              ),
            ),
          ),
        if (steps.isNotEmpty)
          SectionCard(
            title: 'Agent 步骤',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < steps.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Text(
                      '${i + 1}. ${steps[i]}',
                      style: const TextStyle(
                        fontSize: 13,
                        color: Color(0xFF475569),
                        height: 1.5,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        SectionCard(
          title: '现场照片',
          child: images.isEmpty
              ? const EvidencePlaceholder(height: 120)
              : Column(
                  children: [
                    for (var i = 0; i < images.length; i++) ...[
                      if (i > 0) const SizedBox(height: 8),
                      EvidenceImage(request: images[i]),
                    ],
                  ],
                ),
        ),
      ],
    );
  }

  /// 记录里可能有多张图：主库巡检记录只有单张 `image_path`，
  /// 运行库档案带 `image_paths` 列表，多张时按 index 依次取。
  /// 图片接口需要 Bearer token，没有图片/文件缺失时返回 404，交给 EvidenceImage 兜底。
  List<BinaryRequest> _imageRequests(Map<String, dynamic> data) {
    final paths = asList(data['image_paths']);
    final count = paths.isNotEmpty
        ? paths.length
        : (intOf(data['image_count']) > 0
            ? intOf(data['image_count'])
            : (textOf(data['image_path']).isNotEmpty ? 1 : 0));
    return [
      for (var i = 0; i < count; i++) api.recordImageRequest(widget.id, index: i),
    ];
  }
}

/// `agent_steps` 结构不稳定：可能是字符串数组，也可能是 `{step/name/description}` map 数组。
String _stepText(dynamic raw) {
  if (raw is Map) {
    for (final key in const ['step', 'name', 'description', 'title', 'content']) {
      final text = textOf(raw[key]);
      if (text.isNotEmpty) return text;
    }
    return '';
  }
  return textOf(raw);
}

List<String> _agentSteps(dynamic raw) =>
    asList(raw).map(_stepText).where((text) => text.isNotEmpty).toList();
