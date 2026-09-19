import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 设备台账：`/api/devices` 返回 `{items, total, page, page_size}` 包装体，
/// 老代码直接对响应做 `List.from` 必然崩，这里统一按 items 解析并支持搜索/筛选/分页。
class DevicesPage extends StatefulWidget {
  const DevicesPage({super.key});

  @override
  State<DevicesPage> createState() => _DevicesPageState();
}

class _DevicesPageState extends State<DevicesPage> {
  static const int _pageSize = 20;

  final TextEditingController _keywordController = TextEditingController();
  Timer? _debounce;

  String _keyword = '';
  String _status = '';
  int _page = 1;
  int _total = 0;
  bool _loadingMore = false;
  List<Map<String, dynamic>> _items = [];
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = _loadFirstPage();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _keywordController.dispose();
    super.dispose();
  }

  bool get _hasMore => _items.length < _total;

  /// 首页加载同时刷新 `_items` / `_total`，供「加载更多」继续累加。
  Future<List<Map<String, dynamic>>> _loadFirstPage() async {
    final data = await api.devices(
      page: 1,
      pageSize: _pageSize,
      keyword: _keyword,
      status: _status,
    );
    _page = 1;
    _total = intOf(data['total']);
    _items = asMapList(data['items']);
    return _items;
  }

  void _reload() {
    setState(() => _future = _loadFirstPage());
  }

  Future<void> _refresh() async {
    _reload();
    await _future.catchError((_) => <Map<String, dynamic>>[]);
  }

  // 输入时 300ms 防抖，避免每敲一个字都打后端
  void _onKeywordChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (!mounted) return;
      _keyword = value.trim();
      _reload();
    });
  }

  void _onKeywordSubmitted(String value) {
    _debounce?.cancel();
    _keyword = value.trim();
    _reload();
  }

  void _changeStatus(String value) {
    if (value == _status) return;
    _status = value;
    _reload();
  }

  Future<void> _loadMore() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final nextPage = _page + 1;
      final data = await api.devices(
        page: nextPage,
        pageSize: _pageSize,
        keyword: _keyword,
        status: _status,
      );
      if (!mounted) return;
      setState(() {
        _page = nextPage;
        _total = intOf(data['total']);
        // 原地追加：AsyncView 持有的是同一个 List 引用，追加后重建即可看到新数据
        _items.addAll(asMapList(data['items']));
      });
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(describeError(error, fallback: '加载更多失败'))),
      );
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _openDetail(int id) {
    if (id == 0) return;
    Navigator.of(context).pushNamed('/device-detail', arguments: id);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设备台账')),
      body: Column(
        children: [
          _buildFilterBar(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: AsyncView<List<Map<String, dynamic>>>(
                future: _future,
                onRetry: _reload,
                loadingMessage: '正在加载设备…',
                builder: (context, data) {
                  if (data.isEmpty) {
                    // 空态也放进可滚动列表，保证仍能下拉刷新
                    return ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: const [
                        SizedBox(height: 120),
                        EmptyView(
                          message: '未找到设备',
                          icon: Icons.precision_manufacturing_outlined,
                        ),
                      ],
                    );
                  }
                  return ListView.builder(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                    itemCount: data.length + 1,
                    itemBuilder: (context, index) {
                      if (index == data.length) return _buildFooter();
                      return _DeviceTile(
                        item: data[index],
                        onTap: () => _openDetail(intOf(data[index]['id'])),
                      );
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar() {
    // 状态候选值从已加载数据里去重生成，避免写死后端状态枚举
    final statuses = <String>{''};
    for (final item in _items) {
      final status = textOf(item['status']);
      if (status.isNotEmpty) statuses.add(status);
    }
    // 当前选中值必须在候选里，否则 DropdownButton 会断言失败
    statuses.add(_status);

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Row(
        children: [
          Expanded(
            child: SizedBox(
              height: 38,
              child: TextField(
                controller: _keywordController,
                textInputAction: TextInputAction.search,
                onChanged: _onKeywordChanged,
                onSubmitted: _onKeywordSubmitted,
                style: const TextStyle(fontSize: 13),
                decoration: InputDecoration(
                  hintText: '搜索设备名称 / 编号 / 位置',
                  hintStyle: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                  prefixIcon:
                      const Icon(Icons.search, size: 18, color: Color(0xFF94A3B8)),
                  isDense: true,
                  filled: true,
                  fillColor: const Color(0xFFF1F5F9),
                  contentPadding: const EdgeInsets.symmetric(vertical: 8),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _status,
              isDense: true,
              borderRadius: BorderRadius.circular(8),
              style: const TextStyle(fontSize: 13, color: Color(0xFF334155)),
              items: [
                for (final status in statuses)
                  DropdownMenuItem(
                    value: status,
                    child: Text(status.isEmpty ? '全部状态' : status),
                  ),
              ],
              onChanged: (value) => _changeStatus(value ?? ''),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter() {
    if (_loadingMore) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Center(
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2.2),
          ),
        ),
      );
    }
    if (_hasMore) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Center(
          child: TextButton(onPressed: _loadMore, child: const Text('加载更多')),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: Text(
          '已加载全部 ${_items.length} 台设备',
          style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
        ),
      ),
    );
  }
}

class _DeviceTile extends StatelessWidget {
  const _DeviceTile({required this.item, required this.onTap});

  final Map<String, dynamic> item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final name = textOf(item['device_name'], fallback: '未命名设备');
    final status = textOf(item['status'], fallback: '未知');
    final meta = [
      textOf(item['device_code']),
      textOf(item['device_type']),
    ].where((text) => text.isNotEmpty).join(' · ');
    final location = textOf(item['location']);

    return SectionCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      name,
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
                  StatusChip(label: status, color: _deviceStatusColor(status), compact: true),
                ],
              ),
              if (meta.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  meta,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                ),
              ],
              if (location.isNotEmpty) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Icon(Icons.place_outlined, size: 13, color: Color(0xFF94A3B8)),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        location,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 6),
              Text(
                '最近巡检：${formatRelativeTime(item['last_inspection_time'])}',
                style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
              ),
            ],
          ),
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
