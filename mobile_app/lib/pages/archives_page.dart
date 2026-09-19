import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 巡检档案列表。
///
/// 数据源：`GET /api/inspection-archives`（**裸数组**，不是分页对象），
/// 关键词 / 风险等级 / 复查状态全部走**后端查询参数**过滤，前端不做假筛；
/// 顶部概览来自 `GET /api/inspection-archives/dashboard`。
/// 档案 id 是**字符串**（`REC-M-1`、`DEMO-INSPECTION-001`），跳转时按字符串传。
typedef _ArchivesData = ({Map<String, dynamic> dashboard, List<Map<String, dynamic>> items});

class ArchivesPage extends StatefulWidget {
  const ArchivesPage({super.key});

  @override
  State<ArchivesPage> createState() => _ArchivesPageState();
}

class _ArchivesPageState extends State<ArchivesPage> {
  /// 风险等级取值来自后端真实数据（`risk_level` 原样比较，不做模糊匹配）
  static const List<_ArchiveFilter> _riskFilters = [
    _ArchiveFilter(value: '', label: '全部风险'),
    _ArchiveFilter(value: '严重风险', label: '严重风险'),
    _ArchiveFilter(value: '高风险', label: '高风险'),
    _ArchiveFilter(value: '中风险', label: '中风险'),
    _ArchiveFilter(value: '低风险', label: '低风险'),
  ];

  /// 复查状态取值同后端 `review_status` 原值
  static const List<_ArchiveFilter> _reviewFilters = [
    _ArchiveFilter(value: '', label: '全部复查'),
    _ArchiveFilter(value: '待复查', label: '待复查'),
    _ArchiveFilter(value: '持续跟踪', label: '持续跟踪'),
    _ArchiveFilter(value: '已通过', label: '已通过'),
  ];

  final TextEditingController _keywordCtrl = TextEditingController();
  String _keyword = '';
  String _riskLevel = '';
  String _reviewStatus = '';
  late Future<_ArchivesData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void dispose() {
    _keywordCtrl.dispose();
    super.dispose();
  }

  Future<_ArchivesData> _load() async {
    final dashboard = await api.archiveDashboard();
    final items = await api.archives(
      keyword: _keyword,
      riskLevel: _riskLevel,
      reviewStatus: _reviewStatus,
    );
    return (dashboard: dashboard, items: items);
  }

  void _reload() => setState(() => _future = _load());

  Future<void> _refresh() async {
    _reload();
    try {
      await _future;
    } catch (_) {
      // 失败态交给 AsyncView 展示，这里只负责结束下拉动画
    }
  }

  void _applyKeyword() {
    final value = _keywordCtrl.text.trim();
    if (value == _keyword) return;
    setState(() {
      _keyword = value;
      _future = _load();
    });
  }

  void _changeRisk(String value) {
    if (value == _riskLevel) return;
    setState(() {
      _riskLevel = value;
      _future = _load();
    });
  }

  void _changeReview(String value) {
    if (value == _reviewStatus) return;
    setState(() {
      _reviewStatus = value;
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('巡检档案')),
      body: Column(
        children: [
          _buildSearchBar(),
          _buildFilterRow(
            filters: _riskFilters,
            selected: _riskLevel,
            onSelected: _changeRisk,
          ),
          _buildFilterRow(
            filters: _reviewFilters,
            selected: _reviewStatus,
            onSelected: _changeReview,
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: AsyncView<_ArchivesData>(
                future: _future,
                onRetry: _reload,
                loadingMessage: '正在加载巡检档案…',
                emptyMessage: '没有符合条件的巡检档案',
                emptyIcon: Icons.inventory_2_outlined,
                builder: (context, data) => ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                  children: [
                    _buildDashboard(data.dashboard),
                    if (data.items.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 40),
                        child: EmptyView(
                          message: '没有符合条件的巡检档案',
                          icon: Icons.inventory_2_outlined,
                        ),
                      )
                    else
                      for (final item in data.items) _ArchiveTile(item: item),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      child: TextField(
        controller: _keywordCtrl,
        textInputAction: TextInputAction.search,
        onSubmitted: (_) => _applyKeyword(),
        decoration: InputDecoration(
          isDense: true,
          hintText: '搜索地点 / 描述 / 报告编号',
          prefixIcon: const Icon(Icons.search, size: 20),
          suffixIcon: IconButton(
            tooltip: '搜索',
            icon: const Icon(Icons.arrow_forward, size: 20),
            onPressed: _applyKeyword,
          ),
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  Widget _buildFilterRow({
    required List<_ArchiveFilter> filters,
    required String selected,
    required void Function(String value) onSelected,
  }) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 2),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final filter in filters)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(filter.label),
                  selected: selected == filter.value,
                  onSelected: (_) => onSelected(filter.value),
                  showCheckmark: false,
                  visualDensity: VisualDensity.compact,
                  backgroundColor: const Color(0xFFF1F5F9),
                  selectedColor: const Color(0xFFFEE2E2),
                  side: BorderSide.none,
                  labelStyle: TextStyle(
                    fontSize: 12,
                    color: selected == filter.value
                        ? const Color(0xFFDC2626)
                        : const Color(0xFF475569),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// 顶部概览：字段来自 `/api/inspection-archives/dashboard`
  Widget _buildDashboard(Map<String, dynamic> dashboard) {
    if (dashboard.isEmpty) return const SizedBox.shrink();
    return SectionCard(
      title: '档案概览',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _statItem('档案总数', intOf(dashboard['archive_count']), const Color(0xFF2563EB)),
              _statItem('已生成报告', intOf(dashboard['report_count']), const Color(0xFF15803D)),
              _statItem('高风险档案', intOf(dashboard['high_risk_count']), const Color(0xFFB91C1C)),
              _statItem('待复查', intOf(dashboard['pending_review_count']), const Color(0xFFCA8A04)),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '关联工单 ${intOf(dashboard['workorder_count'])} 张，'
            '已闭环 ${intOf(dashboard['closed_workorder_count'])} 张，'
            '闭环率 ${numOf(dashboard['closed_loop_rate'])}%',
            style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
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
}

class _ArchiveFilter {
  const _ArchiveFilter({required this.value, required this.label});

  final String value;
  final String label;
}

/// 单条档案：地点 / 风险等级 / 时间 / 报告编号与状态 / 复查状态 / 工单闭环情况
class _ArchiveTile extends StatelessWidget {
  const _ArchiveTile({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final id = textOf(item['id']);
    final level = textOf(item['risk_level']);
    final color = riskColor(level);
    final location = textOf(item['location'], fallback: textOf(item['record_no'], fallback: '未标注地点'));
    final reportNo = textOf(item['report_no']);
    final reportStatus = textOf(item['report_status']);
    final reviewStatus = textOf(item['review_status']);
    final archiveStatus = textOf(item['archive_status']);
    final workorderCount = intOf(item['workorder_count']);
    final closedLoopRate = numOf(item['closed_loop_rate']);

    return SectionCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: id.isEmpty
            ? null
            : () => Navigator.of(context).pushNamed('/archive-detail', arguments: id),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (level.isNotEmpty)
                    StatusChip(label: level, color: color, compact: true),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      location,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    formatRelativeTime(item['created_at']),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.description_outlined, size: 13, color: Color(0xFF94A3B8)),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      reportNo.isEmpty ? '暂无报告编号' : reportNo,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
                    ),
                  ),
                  if (reportStatus.isNotEmpty)
                    Text(
                      reportStatus,
                      style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  if (archiveStatus.isNotEmpty)
                    StatusChip(label: archiveStatus, color: const Color(0xFF2563EB), compact: true),
                  if (reviewStatus.isNotEmpty)
                    StatusChip(label: reviewStatus, color: const Color(0xFF7C3AED), compact: true),
                  StatusChip(
                    label: workorderCount == 0
                        ? '暂无关联工单'
                        : '工单 $workorderCount 张 · 闭环 $closedLoopRate%',
                    color: const Color(0xFF64748B),
                    compact: true,
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
