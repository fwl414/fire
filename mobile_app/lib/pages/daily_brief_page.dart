import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 每日安全简报：`GET /api/intelligence/daily-brief?date=YYYY-MM-DD` → `{ok, data}`。
///
/// 后端默认统计**昨天**，这里按需求默认显示今天并可切换日期。
/// 数据全部来自后端真实统计（无数据时就是 0 与空列表）。
class DailyBriefPage extends StatefulWidget {
  const DailyBriefPage({super.key});

  @override
  State<DailyBriefPage> createState() => _DailyBriefPageState();
}

class _DailyBriefPageState extends State<DailyBriefPage> {
  late DateTime _date;
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _date = DateTime.now();
    _future = _load();
  }

  String get _dateText =>
      '${_date.year.toString().padLeft(4, '0')}-'
      '${_date.month.toString().padLeft(2, '0')}-'
      '${_date.day.toString().padLeft(2, '0')}';

  Future<Map<String, dynamic>> _load() => api.dailyBrief(date: _dateText);

  void _reload() => setState(() => _future = _load());

  Future<void> _refresh() async {
    _reload();
    try {
      await _future;
    } catch (_) {
      // 失败态交给 AsyncView 展示，这里只负责结束下拉动画
    }
  }

  void _shift(int days) {
    setState(() {
      _date = _date.add(Duration(days: days));
      _future = _load();
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2024, 1, 1),
      lastDate: DateTime.now(),
    );
    if (picked == null || !mounted) return;
    setState(() {
      _date = picked;
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('每日安全简报'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: Column(
        children: [
          _buildDateBar(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: AsyncView<Map<String, dynamic>>(
                future: _future,
                onRetry: _reload,
                loadingMessage: '正在生成简报…',
                emptyMessage: '该日期暂无简报数据',
                emptyIcon: Icons.summarize_outlined,
                isEmpty: (data) => data.isEmpty,
                builder: (context, data) => _buildContent(data),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDateBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          IconButton(
            tooltip: '前一天',
            icon: const Icon(Icons.chevron_left),
            onPressed: () => _shift(-1),
          ),
          Expanded(
            child: TextButton.icon(
              onPressed: _pickDate,
              icon: const Icon(Icons.event_outlined, size: 18),
              label: Text(_dateText),
            ),
          ),
          IconButton(
            tooltip: '后一天',
            icon: const Icon(Icons.chevron_right),
            onPressed: () => _shift(1),
          ),
        ],
      ),
    );
  }

  Widget _buildContent(Map<String, dynamic> data) {
    final highlights = asMapList(data['key_highlights']);
    final alertStats = asMap(data['alert_stats']);
    final inspectionStats = asMap(data['inspection_stats']);
    final trend = asMapList(data['alarm_trend']);
    final focus = asMapList(data['today_focus']);
    final note = textOf(data['note']);

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        SectionCard(
          title: textOf(data['date'], fallback: _dateText),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                textOf(data['summary'], fallback: '暂无简报正文'),
                style: const TextStyle(fontSize: 13, color: Color(0xFF334155), height: 1.7),
              ),
              if (textOf(data['generated_at']).isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  '生成时间 ${textOf(data['generated_at'])} · 数据源 ${textOf(data['data_source'])}',
                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                ),
              ],
            ],
          ),
        ),
        if (highlights.isNotEmpty)
          SectionCard(
            title: '重点提示',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in highlights)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Icon(
                            _highlightIcon(textOf(item['type'])),
                            size: 15,
                            color: _highlightColor(textOf(item['type'])),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            textOf(item['content']),
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
        SectionCard(
          title: '告警统计',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  _statItem('告警总数', intOf(alertStats['total']), const Color(0xFF2563EB)),
                  _statItem('已处置', intOf(alertStats['resolved']), const Color(0xFF15803D)),
                  _statItem('待处理', intOf(alertStats['pending']), const Color(0xFFDC2626)),
                ],
              ),
              const Divider(height: 22),
              Row(
                children: [
                  _statItem('严重', intOf(alertStats['critical']), const Color(0xFFB91C1C)),
                  _statItem('高', intOf(alertStats['high']), const Color(0xFFEA580C)),
                  _statItem('中', intOf(alertStats['medium']), const Color(0xFFCA8A04)),
                  _statItem('低', intOf(alertStats['low']), const Color(0xFF0E7490)),
                ],
              ),
              const Divider(height: 22),
              Row(
                children: [
                  _statItem(
                    '完成巡检',
                    intOf(inspectionStats['inspection_count']),
                    const Color(0xFF7C3AED),
                  ),
                  _statItem(
                    '发现隐患',
                    intOf(inspectionStats['hazard_found']),
                    const Color(0xFFEA580C),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (trend.isNotEmpty) _buildTrend(trend),
        if (focus.isNotEmpty)
          SectionCard(
            title: '重点关注区域',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in focus)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                textOf(item['area'], fallback: '未标注区域'),
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF1E293B),
                                ),
                              ),
                            ),
                            StatusChip(
                              label: textOf(item['level']) == 'high' ? '高' : '中',
                              color: severityColor(
                                textOf(item['level']) == 'high' ? 'high' : 'medium',
                              ),
                              compact: true,
                            ),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          textOf(item['reason']),
                          style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569)),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (note.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '口径说明：$note',
              style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8), height: 1.5),
            ),
          ),
      ],
    );
  }

  /// 近 7 日告警趋势：`alarm_trend[{date,count,critical}]`
  Widget _buildTrend(List<Map<String, dynamic>> trend) {
    final maxCount = trend
        .map((item) => intOf(item['count']))
        .fold<int>(1, (previous, value) => value > previous ? value : previous);

    return SectionCard(
      title: '近 7 日告警趋势',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final item in trend)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  SizedBox(
                    width: 44,
                    child: Text(
                      textOf(item['date']),
                      style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
                    ),
                  ),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(3),
                      child: LinearProgressIndicator(
                        value: intOf(item['count']) / maxCount,
                        minHeight: 8,
                        backgroundColor: const Color(0xFFF1F5F9),
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 54,
                    child: Text(
                      '${intOf(item['count'])} 起',
                      textAlign: TextAlign.right,
                      style: const TextStyle(fontSize: 11, color: Color(0xFF475569)),
                    ),
                  ),
                ],
              ),
            ),
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
            style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: color),
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

  IconData _highlightIcon(String type) {
    switch (type) {
      case 'danger':
        return Icons.error_outline;
      case 'warning':
        return Icons.warning_amber_rounded;
      case 'success':
        return Icons.check_circle_outline;
      default:
        return Icons.info_outline;
    }
  }

  Color _highlightColor(String type) {
    switch (type) {
      case 'danger':
        return const Color(0xFFB91C1C);
      case 'warning':
        return const Color(0xFFEA580C);
      case 'success':
        return const Color(0xFF15803D);
      default:
        return const Color(0xFF2563EB);
    }
  }
}
