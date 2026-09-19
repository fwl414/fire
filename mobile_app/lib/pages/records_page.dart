import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 巡检记录列表：`/api/records` 返回**裸数组**（`api.records()` 已解析成 List）。
/// 列表接口不返回 `report` 正文，正文只在详情接口里取。
class RecordsPage extends StatefulWidget {
  const RecordsPage({super.key});

  @override
  State<RecordsPage> createState() => _RecordsPageState();
}

class _RecordsPageState extends State<RecordsPage> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.records();
  }

  void _reload() {
    setState(() => _future = api.records());
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <Map<String, dynamic>>[]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('巡检记录')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<List<Map<String, dynamic>>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在加载巡检记录…',
          emptyMessage: '暂无巡检记录',
          emptyIcon: Icons.fact_check_outlined,
          isEmpty: (data) => data.isEmpty,
          builder: (context, data) => ListView.builder(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
            itemCount: data.length,
            itemBuilder: (context, index) => _RecordTile(item: data[index]),
          ),
        ),
      ),
    );
  }
}

class _RecordTile extends StatelessWidget {
  const _RecordTile({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final id = intOf(item['id']);
    final level = textOf(item['risk_level']);
    final color = riskColor(level);
    final name = textOf(
      item['device_name'],
      fallback: textOf(item['location'], fallback: '巡检点'),
    );
    final meta = [
      textOf(item['device_code']),
      textOf(item['location']),
    ].where((text) => text.isNotEmpty).join(' · ');
    final hazardCount = asList(item['hazards']).length;

    return SectionCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: id == 0
            ? null
            : () => Navigator.of(context).pushNamed('/record-detail', arguments: id),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    '${intOf(item['risk_score'])}',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: color,
                      height: 1.1,
                    ),
                  ),
                  Text(' 分', style: TextStyle(fontSize: 11, color: color)),
                  const SizedBox(width: 8),
                  if (level.isNotEmpty)
                    StatusChip(label: level, color: color, compact: true),
                  const Spacer(),
                  Text(
                    formatRelativeTime(item['created_at']),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF1E293B),
                ),
              ),
              if (meta.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  meta,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                ),
              ],
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.report_problem_outlined,
                      size: 13, color: Color(0xFFEA580C)),
                  const SizedBox(width: 4),
                  Text(
                    '隐患 $hazardCount 条',
                    style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
