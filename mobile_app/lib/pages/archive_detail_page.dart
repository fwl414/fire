import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/api_client.dart';
import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 巡检档案详情：`GET /api/inspection-archives/{record_id}`。
///
/// 与「巡检记录详情」的区别：这里 `record_id` 是**字符串**（`REC-M-1`），
/// 且多了 `quality / hazard_details / rag_references / closure_status /
/// before_after_images / archive_timeline` 等档案与闭环信息。
class ArchiveDetailPage extends StatefulWidget {
  const ArchiveDetailPage({super.key, required this.recordId});

  final String recordId;

  @override
  State<ArchiveDetailPage> createState() => _ArchiveDetailPageState();
}

class _ArchiveDetailPageState extends State<ArchiveDetailPage> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.archiveDetail(widget.recordId);
  }

  void _reload() {
    setState(() => _future = api.archiveDetail(widget.recordId));
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  Future<void> _copy(String label, String value) async {
    if (value.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$label已复制：$value')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('巡检档案详情')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载档案详情…',
          emptyMessage: '档案不存在或已被删除',
          emptyIcon: Icons.inventory_2_outlined,
          isEmpty: (data) => data.isEmpty,
          builder: (context, data) => _buildContent(data),
        ),
      ),
    );
  }

  Widget _buildContent(Map<String, dynamic> data) {
    final level = textOf(data['risk_level']);
    final color = riskColor(level);
    final sections = <Widget>[
      _buildHeader(data, level, color),
      _buildBasicInfo(data),
      _buildReportSection(data),
      _buildClosureSection(data),
      _buildQuality(data),
      _buildHazards(data),
      _buildEvidenceImages(data),
      _buildBeforeAfterImages(data),
      _buildTimeline(data),
      _buildRagReferences(data),
    ];

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: sections,
    );
  }

  Widget _buildHeader(Map<String, dynamic> data, String level, Color color) {
    final score = numOf(data['risk_score']);
    final scoreText = score.toStringAsFixed(score % 1 == 0 ? 0 : 1);

    return SectionCard(
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                scoreText,
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w700,
                  color: color,
                  height: 1.1,
                ),
              ),
              const Text('风险评分', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
            ],
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    if (level.isNotEmpty) StatusChip(label: level, color: color),
                    if (textOf(data['report_status']).isNotEmpty)
                      StatusChip(
                        label: textOf(data['report_status']),
                        color: const Color(0xFF15803D),
                      ),
                    if (textOf(data['review_status']).isNotEmpty)
                      StatusChip(
                        label: textOf(data['review_status']),
                        color: const Color(0xFF7C3AED),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  textOf(data['location'], fallback: '未标注地点'),
                  style: const TextStyle(fontSize: 13, color: Color(0xFF334155)),
                ),
                const SizedBox(height: 4),
                Text(
                  '巡检时间 ${formatFullTime(data['created_at'])}',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBasicInfo(Map<String, dynamic> data) {
    return SectionCard(
      title: '基本信息',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InfoRow(label: '档案编号', value: textOf(data['id'])),
          InfoRow(label: '巡检地点', value: textOf(data['location'])),
          InfoRow(label: '现场描述', value: textOf(data['description'])),
          InfoRow(label: '风险等级', value: textOf(data['risk_level'])),
          InfoRow(label: '来源类型', value: textOf(data['source_type'])),
          InfoRow(label: '巡检人', value: textOf(data['inspector'])),
          InfoRow(label: '档案状态', value: textOf(data['archive_status'])),
          InfoRow(label: '复查状态', value: textOf(data['review_status'])),
          InfoRow(label: '更新时间', value: formatFullTime(data['updated_at'])),
        ],
      ),
    );
  }

  /// 报告编号 + 报告验真 / 复制 / 分享入口
  Widget _buildReportSection(Map<String, dynamic> data) {
    final reportNo = textOf(data['report_no']);
    if (reportNo.isEmpty) {
      return const SectionCard(
        title: '报告',
        child: Text('该档案尚未生成报告编号', style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
      );
    }
    final verifyUrl = textOf(data['report_verify_url'], fallback: '/report-verify/$reportNo');
    final hash = textOf(data['report_hash']);

    return SectionCard(
      title: '报告与验真',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InfoRow(label: '报告编号', value: reportNo),
          InfoRow(label: '报告状态', value: textOf(data['report_status'])),
          if (hash.isNotEmpty) InfoRow(label: '报告指纹', value: hash),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: () => Navigator.of(context)
                      .pushNamed('/report-verify', arguments: reportNo),
                  icon: const Icon(Icons.verified_outlined, size: 18),
                  label: const Text('报告验真'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _copy('验真链接', verifyUrl),
                  icon: const Icon(Icons.share_outlined, size: 18),
                  label: const Text('分享'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// 闭环情况：`closure_status` 由后端拼好（如「0/116 工单已闭环」），
  /// 关联工单数取详情里的 `workorders` 列表长度。
  Widget _buildClosureSection(Map<String, dynamic> data) {
    final closure = textOf(data['closure_status']);
    final orders = asMapList(data['workorders']);
    if (closure.isEmpty && orders.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: '整改闭环',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InfoRow(label: '闭环情况', value: closure),
          InfoRow(label: '关联工单', value: '${orders.length} 张'),
          if (orders.isNotEmpty) ...[
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final order in orders.take(12))
                  StatusChip(
                    label: '${textOf(order['status'], fallback: '工单')}'
                        '· ${textOf(order['hazard'], fallback: '整改事项')}',
                    color: workorderStatusColor(textOf(order['status'])),
                    compact: true,
                  ),
              ],
            ),
            if (orders.length > 12)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '另有 ${orders.length - 12} 张工单未展示',
                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                ),
              ),
          ],
        ],
      ),
    );
  }

  /// 报告质量评分与检查项：`quality{score, checklist[{label, ok}]}`
  Widget _buildQuality(Map<String, dynamic> data) {
    final quality = asMap(data['quality']);
    final checklist = asMapList(quality['checklist']);
    if (quality.isEmpty || checklist.isEmpty) return const SizedBox.shrink();
    final score = numOf(quality['score']);

    return SectionCard(
      title: '报告质量',
      trailing: Text(
        '${score.toStringAsFixed(score % 1 == 0 ? 0 : 1)} 分',
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w700,
          color: Color(0xFF2563EB),
        ),
      ),
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (final item in checklist)
            StatusChip(
              label: textOf(item['label'], fallback: '检查项'),
              color: item['ok'] == true ? const Color(0xFF15803D) : const Color(0xFF94A3B8),
              icon: item['ok'] == true ? Icons.check_circle_outline : Icons.remove_circle_outline,
              compact: true,
            ),
        ],
      ),
    );
  }

  /// 隐患明细：`hazard_details[]`（hazard_name/risk_level/category/score/evidence/
  /// possible_consequence/suggestion/need_immediate_fix）
  Widget _buildHazards(Map<String, dynamic> data) {
    final details = asMapList(data['hazard_details']);
    final hazards = asList(data['hazards']).map((e) => textOf(e)).where((t) => t.isNotEmpty).toList();
    if (details.isEmpty && hazards.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: '隐患明细',
      child: details.isEmpty
          ? Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final hazard in hazards)
                  StatusChip(label: hazard, color: const Color(0xFFEA580C), compact: true),
              ],
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in details) _HazardDetailTile(item: item),
              ],
            ),
    );
  }

  /// 现场图片证据链：`image_paths` 有几张就按 `index` 取几张；
  /// 图片接口需要 Bearer token，文件缺失时后端 404，由 EvidenceImage 兜底成占位。
  Widget _buildEvidenceImages(Map<String, dynamic> data) {
    final requests = _imageRequests(data);
    if (requests.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: '现场图片证据（${requests.length} 张）',
      child: Column(
        children: [
          for (var i = 0; i < requests.length; i++) ...[
            if (i > 0) const SizedBox(height: 8),
            EvidenceImage(request: requests[i]),
          ],
        ],
      ),
    );
  }

  /// 整改前后图片：`before_after_images[]` 里给的是**磁盘相对路径**
  /// （如 `uploads/demo_scene_01.jpg`），后端没有「按路径取图」的接口，
  /// 只有 `GET /api/records/{id}/image?index=N`。
  /// 因此只有路径正好命中本档案 `image_paths` 的那张才按 index 加载，
  /// 其余（工单自带的 after/review 图）没有可访问入口，如实显示占位。
  Widget _buildBeforeAfterImages(Map<String, dynamic> data) {
    final groups = asMapList(data['before_after_images']);
    if (groups.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: '整改前后图片',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < groups.length; i++) ...[
            if (i > 0) const Divider(height: 24),
            _buildBeforeAfterGroup(data, groups[i]),
          ],
        ],
      ),
    );
  }

  Widget _buildBeforeAfterGroup(Map<String, dynamic> data, Map<String, dynamic> group) {
    final hazard = textOf(group['hazard'], fallback: '整改事项');
    final orderId = textOf(group['order_id']);
    final before = asList(group['before_images']).map((e) => textOf(e)).toList();
    final after = asList(group['after_images']).map((e) => textOf(e)).toList();
    final review = asList(group['review_images']).map((e) => textOf(e)).toList();
    final note = textOf(group['review_note']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          hazard,
          style: const TextStyle(
            fontSize: 13.5,
            fontWeight: FontWeight.w600,
            color: Color(0xFF1E293B),
          ),
        ),
        if (orderId.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              '关联工单 $orderId',
              style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
            ),
          ),
        const SizedBox(height: 8),
        if (before.isNotEmpty) _imageRow('整改前', data, before),
        if (after.isNotEmpty) ...[
          const SizedBox(height: 8),
          _imageRow('整改后', data, after),
        ],
        if (review.isNotEmpty) ...[
          const SizedBox(height: 8),
          _imageRow('复查', data, review),
        ],
        if (note.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text('复查说明：$note', style: const TextStyle(fontSize: 12, color: Color(0xFF475569))),
        ],
      ],
    );
  }

  Widget _imageRow(String label, Map<String, dynamic> data, List<String> paths) {
    final requests = [
      for (final path in paths) _pathRequest(data, path),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
        const SizedBox(height: 4),
        for (var i = 0; i < requests.length; i++) ...[
          if (i > 0) const SizedBox(height: 6),
          EvidenceImage(request: requests[i], height: 140),
        ],
      ],
    );
  }

  /// 时间线：`archive_timeline[{time,title,content}]`（后端把操作日志也合并进来了）
  Widget _buildTimeline(Map<String, dynamic> data) {
    final timeline = asMapList(data['archive_timeline']);
    if (timeline.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: '档案时间线',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < timeline.length; i++)
            _TimelineRow(
              item: timeline[i],
              isLast: i == timeline.length - 1,
            ),
        ],
      ),
    );
  }

  /// RAG 引用依据：`rag_references[{title,category,similarity,summary,source}]`
  Widget _buildRagReferences(Map<String, dynamic> data) {
    final refs = asMapList(data['rag_references']);
    if (refs.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: 'RAG 引用依据（${refs.length} 条）',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final ref in refs)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          textOf(ref['title'], fallback: '引用依据'),
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF1E293B),
                          ),
                        ),
                      ),
                      if (numOf(ref['similarity']) > 0)
                        StatusChip(
                          label: '相似度 ${numOf(ref['similarity']).toStringAsFixed(0)}',
                          color: const Color(0xFF2563EB),
                          compact: true,
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    [
                      textOf(ref['category']),
                      textOf(ref['source']),
                    ].where((t) => t.isNotEmpty).join(' · '),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    textOf(ref['summary'], fallback: textOf(ref['content_preview'])),
                    style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  /// 档案图片张数：优先 `image_paths` 长度，其次 `image_count`
  List<BinaryRequest> _imageRequests(Map<String, dynamic> data) {
    final count = _imageCount(data);
    return [
      for (var i = 0; i < count; i++) api.recordImageRequest(widget.recordId, index: i),
    ];
  }

  int _imageCount(Map<String, dynamic> data) {
    final paths = asList(data['image_paths']);
    if (paths.isNotEmpty) return paths.length;
    return intOf(data['image_count']);
  }

  /// 只有路径能在本档案 `image_paths` 里定位到下标时才能按 index 取图，否则返回 null（占位）
  BinaryRequest? _pathRequest(Map<String, dynamic> data, String path) {
    if (path.isEmpty) return null;
    final paths = asList(data['image_paths']).map((e) => textOf(e)).toList();
    final index = paths.indexOf(path);
    if (index < 0) return null;
    return api.recordImageRequest(widget.recordId, index: index);
  }
}

class _HazardDetailTile extends StatelessWidget {
  const _HazardDetailTile({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final level = textOf(item['risk_level']);
    final color = riskColor(level);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  textOf(item['hazard_name'], fallback: '隐患'),
                  style: const TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1E293B),
                  ),
                ),
              ),
              if (item['need_immediate_fix'] == true)
                const StatusChip(
                  label: '需立即整改',
                  color: Color(0xFFB91C1C),
                  compact: true,
                ),
              if (item['need_immediate_fix'] == true) const SizedBox(width: 6),
              if (level.isNotEmpty)
                StatusChip(
                  label: numOf(item['score']) > 0 ? '$level · ${numOf(item['score'])}分' : level,
                  color: color,
                  compact: true,
                ),
            ],
          ),
          if (textOf(item['category']).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(
                '类别：${textOf(item['category'])}',
                style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
              ),
            ),
          if (textOf(item['evidence']).isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '判定依据：${textOf(item['evidence'])}',
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
            ),
          ],
          if (textOf(item['possible_consequence']).isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              '可能后果：${textOf(item['possible_consequence'])}',
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
            ),
          ],
          if (textOf(item['suggestion']).isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              '整改建议：${textOf(item['suggestion'])}',
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.item, required this.isLast});

  final Map<String, dynamic> item;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 8,
                height: 8,
                margin: const EdgeInsets.only(top: 4),
                decoration: const BoxDecoration(
                  color: Color(0xFFDC2626),
                  shape: BoxShape.circle,
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(width: 1.5, color: const Color(0xFFE2E8F0)),
                ),
            ],
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    textOf(item['title'], fallback: '事件'),
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF1E293B),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    formatFullTime(item['time']),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                  if (textOf(item['content']).isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      textOf(item['content']),
                      style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569), height: 1.5),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
