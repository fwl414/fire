import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 告警统计：`GET /api/alert/statistics`。
///
/// 返回是**扁平**字段（没有 by_severity 之类的嵌套）：
/// `total/pending/processing/resolved/merged/escalated/critical/high/medium/low/
/// todayCount/thisWeek`，以及 `byType[{type,count}]`、`trend[{date,count}]`。
class AlertStatisticsPage extends StatefulWidget {
  const AlertStatisticsPage({super.key});

  @override
  State<AlertStatisticsPage> createState() => _AlertStatisticsPageState();
}

class _AlertStatisticsPageState extends State<AlertStatisticsPage> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = api.alertStatistics();
  }

  void _reload() => setState(() => _future = api.alertStatistics());

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <String, dynamic>{});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('告警统计')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: AsyncView<Map<String, dynamic>>(
          future: _future,
          onRetry: _reload,
          loadingMessage: '正在统计告警…',
          emptyMessage: '暂无告警统计数据',
          emptyIcon: Icons.insights_outlined,
          isEmpty: (data) => data.isEmpty,
          builder: (context, data) => _buildContent(data),
        ),
      ),
    );
  }

  Widget _buildContent(Map<String, dynamic> data) {
    final byType = asMapList(data['byType']);
    final trend = asMapList(data['trend']);

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        SectionCard(
          title: '处置状态',
          child: Wrap(
            spacing: 0,
            runSpacing: 14,
            children: [
              _statItem('告警总数', data['total'], const Color(0xFF2563EB)),
              _statItem('待处置', data['pending'], const Color(0xFFDC2626)),
              _statItem('处理中', data['processing'], const Color(0xFFEA580C)),
              _statItem('已处置', data['resolved'], const Color(0xFF15803D)),
              _statItem('已合并', data['merged'], const Color(0xFF64748B)),
              _statItem('已升级', data['escalated'], const Color(0xFF7C3AED)),
            ],
          ),
        ),
        SectionCard(
          title: '级别分布',
          child: Wrap(
            spacing: 0,
            runSpacing: 14,
            children: [
              _statItem('严重', data['critical'], const Color(0xFFB91C1C)),
              _statItem('高', data['high'], const Color(0xFFEA580C)),
              _statItem('中', data['medium'], const Color(0xFFCA8A04)),
              _statItem('低', data['low'], const Color(0xFF0E7490)),
            ],
          ),
        ),
        SectionCard(
          title: '时间维度',
          child: Row(
            children: [
              _statItem('今日新增', data['todayCount'], const Color(0xFF2563EB)),
              _statItem('本周新增', data['thisWeek'], const Color(0xFF7C3AED)),
            ],
          ),
        ),
        if (byType.isNotEmpty)
          SectionCard(
            title: '按告警类型',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in byType)
                  _barRow(
                    label: textOf(item['type'], fallback: '未知类型'),
                    count: intOf(item['count']),
                    maxCount: _maxCount(byType, 'count'),
                    color: const Color(0xFFDC2626),
                  ),
              ],
            ),
          ),
        if (trend.isNotEmpty)
          SectionCard(
            title: '近 7 日趋势',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in trend)
                  _barRow(
                    label: textOf(item['date']),
                    count: intOf(item['count']),
                    maxCount: _maxCount(trend, 'count'),
                    color: const Color(0xFF2563EB),
                  ),
              ],
            ),
          ),
      ],
    );
  }

  int _maxCount(List<Map<String, dynamic>> rows, String key) => rows
      .map((item) => intOf(item[key]))
      .fold<int>(1, (previous, value) => value > previous ? value : previous);

  Widget _barRow({
    required String label,
    required int count,
    required int maxCount,
    required Color color,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 96,
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11.5, color: Color(0xFF64748B)),
            ),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: count / maxCount,
                minHeight: 8,
                color: color,
                backgroundColor: const Color(0xFFF1F5F9),
              ),
            ),
          ),
          SizedBox(
            width: 44,
            child: Text(
              '$count',
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 11.5, color: Color(0xFF475569)),
            ),
          ),
        ],
      ),
    );
  }

  /// 六项一排会挤，这里固定宽度做 3 列布局
  Widget _statItem(String label, dynamic value, Color color) {
    return SizedBox(
      width: 100,
      child: Column(
        children: [
          Text(
            '${intOf(value)}',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: color),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }
}
