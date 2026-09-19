import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 工单列表：4 个 Tab 全部走**服务端** `status` 过滤
/// （老实现是拉全量再在客户端用中文 contains 过滤，既不准也分页不了）。
class WorkOrdersPage extends StatefulWidget {
  const WorkOrdersPage({super.key});

  @override
  State<WorkOrdersPage> createState() => _WorkOrdersPageState();
}

class _WorkOrdersPageState extends State<WorkOrdersPage>
    with SingleTickerProviderStateMixin {
  /// 与后端状态机一致的中文取值，空串代表「全部」
  static const List<String> _tabLabels = ['全部', '待受理', '处理中', '待复查', '已完成', '已关闭'];
  static const List<String> _tabStatuses = ['', '待受理', '处理中', '待复查', '已完成', '已关闭'];
  static const int _pageSize = 20;

  late final TabController _tabController;
  late Future<int> _future;

  final List<Map<String, dynamic>> _items = [];
  int _page = 1;
  int _total = 0;
  bool _loadingMore = false;

  /// 请求序号：切 Tab / 刷新后旧请求的结果必须丢弃，否则会把别的 Tab 数据拼进来
  int _seq = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabLabels.length, vsync: this);
    _tabController.addListener(_onTabChanged);
    _future = _fetchFirstPage();
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  String get _currentStatus => _tabStatuses[_tabController.index];

  String get _emptyMessage {
    switch (_currentStatus) {
      case '待受理':
        return '暂无待受理工单';
      case '处理中':
        return '暂无处理中工单';
      case '待复查':
        return '暂无待复查工单';
      case '已完成':
        return '暂无已完成工单';
      case '已关闭':
        return '暂无已关闭工单';
      default:
        return '暂无工单';
    }
  }

  void _onTabChanged() {
    if (_tabController.indexIsChanging) return;
    _reload();
  }

  /// 拉第一页，并同步本地分页游标；返回总数供 AsyncView 判断空态。
  Future<int> _fetchFirstPage() async {
    final seq = ++_seq;
    final status = _currentStatus;
    final data = await api.workorders(
      status: status.isEmpty ? null : status,
      page: 1,
      pageSize: _pageSize,
    );
    if (seq != _seq) return _total;
    _items
      ..clear()
      ..addAll(asMapList(data['items']));
    _page = 1;
    _total = intOf(data['total']);
    return _total;
  }

  void _reload() {
    setState(() => _future = _fetchFirstPage());
  }

  Future<void> _refresh() async {
    final future = _fetchFirstPage();
    setState(() => _future = future);
    try {
      await future;
    } catch (_) {
      // 失败态交给 AsyncView 展示，这里只负责结束下拉动画
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || _items.length >= _total) return;
    final seq = _seq;
    final status = _currentStatus;
    setState(() => _loadingMore = true);
    try {
      final data = await api.workorders(
        status: status.isEmpty ? null : status,
        page: _page + 1,
        pageSize: _pageSize,
      );
      if (!mounted || seq != _seq) return;
      setState(() {
        _items.addAll(asMapList(data['items']));
        _page += 1;
        _total = intOf(data['total']);
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _openCreate() async {
    final created = await Navigator.of(context).pushNamed('/workorder-create');
    if (!mounted) return;
    if (created == true) _reload();
  }

  void _openDetail(Map<String, dynamic> item) {
    final id = intOf(item['id']);
    if (id == 0) return;
    Navigator.of(context).pushNamed('/workorder-detail', arguments: id);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          Container(
            color: Colors.white,
            child: TabBar(
              controller: _tabController,
              // 6 个状态 Tab 在窄屏上会挤在一起，允许横向滚动
              isScrollable: true,
              tabAlignment: TabAlignment.start,
              labelColor: const Color(0xFFDC2626),
              unselectedLabelColor: const Color(0xFF64748B),
              indicatorColor: const Color(0xFFDC2626),
              tabs: _tabLabels.map((label) => Tab(text: label)).toList(),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: AsyncView<int>(
                future: _future,
                onRetry: _reload,
                loadingMessage: '正在加载工单…',
                isEmpty: (_) => _items.isEmpty,
                emptyMessage: _emptyMessage,
                emptyIcon: Icons.assignment_outlined,
                builder: (context, _) => ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                  itemCount: _items.length + 1,
                  itemBuilder: (context, index) {
                    if (index >= _items.length) return _buildFooter();
                    return _buildCard(_items[index]);
                  },
                ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCreate,
        icon: const Icon(Icons.add),
        label: const Text('新建工单'),
      ),
    );
  }

  Widget _buildCard(Map<String, dynamic> item) {
    final status = textOf(item['status'], fallback: '未知状态');
    final risk = textOf(item['risk_level']);
    final title = textOf(item['title'], fallback: '未命名工单');
    final location = [textOf(item['location']), textOf(item['building_name'])]
        .where((text) => text.isNotEmpty)
        .join(' · ');
    final assignee = textOf(item['assignee_name']);

    return SectionCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: () => _openDetail(item),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                StatusChip(
                  label: status,
                  color: workorderStatusColor(status),
                  compact: true,
                ),
                if (risk.isNotEmpty) ...[
                  const SizedBox(width: 6),
                  StatusChip(label: risk, color: riskColor(risk), compact: true),
                ],
                const Spacer(),
                Text(
                  formatRelativeTime(item['created_at']),
                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF1E293B),
              ),
            ),
            const SizedBox(height: 8),
            _iconLine(Icons.place_outlined, location.isEmpty ? '未填写位置' : location),
            const SizedBox(height: 4),
            _iconLine(
              Icons.person_outline,
              '负责人：${assignee.isEmpty ? '未指派' : assignee}',
            ),
          ],
        ),
      ),
    );
  }

  Widget _iconLine(IconData icon, String text) {
    return Row(
      children: [
        Icon(icon, size: 13, color: const Color(0xFF94A3B8)),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
          ),
        ),
      ],
    );
  }

  Widget _buildFooter() {
    if (_items.isEmpty) return const SizedBox.shrink();
    if (_items.length >= _total) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 14),
        child: Center(
          child: Text(
            '已显示全部工单',
            style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Center(
        child: _loadingMore
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : OutlinedButton(onPressed: _loadMore, child: const Text('加载更多')),
      ),
    );
  }
}
