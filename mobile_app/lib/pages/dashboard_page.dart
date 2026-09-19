import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 首页：统计数据来自 `/api/mobile/home`，待办列表来自 `/api/mobile/tasks`（后端按当前用户真实统计，不编造数字）。
///
/// 之前的实现里「建筑风险」「最近巡检」都是写死的假数据、快捷操作全部空实现，
/// 这里全部换成真实数据与真实跳转。
typedef _DashboardData = ({Map<String, dynamic> home, List<Map<String, dynamic>> tasks});

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, this.onOpenTab});

  /// 切到主框架的其它 tab（0 首页 / 1 巡检 / 2 工单 / 3 告警 / 4 我的）
  final void Function(int index)? onOpenTab;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  late Future<_DashboardData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_DashboardData> _load() async {
    final home = await api.home();
    // 待办改用专为此设计的 /api/mobile/tasks（最多 50 条），而 home 里每类只给最近 5 条。
    // tasks 只返回「已指派给我」的工单，所以可领取工单仍从 home 取，避免漏掉待认领的活。
    final tasks = await api.tasks();
    return (home: home, tasks: asMapList(tasks['items']));
  }

  void _reload() {
    setState(() => _future = _load());
  }

  Future<void> _refresh() async {
    _reload();
    try {
      await _future;
    } catch (_) {
      // 失败态交给 AsyncView 展示，这里只负责结束下拉动画
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: AsyncView<_DashboardData>(
        future: _future,
        onRetry: _reload,
        loadingMessage: '正在加载今日概览…',
        builder: (context, data) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            _buildOverview(data.home),
            _buildQuickActions(context),
            _buildTodo(data.home, data.tasks),
          ],
        ),
      ),
    );
  }

  Widget _buildOverview(Map<String, dynamic> data) {
    final stats = asMap(data['stats']);
    final userName = textOf(asMap(data['user'])['name'], fallback: '同事');

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: const LinearGradient(
          colors: [Color(0xFFDC2626), Color(0xFFB91C1C)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '$userName，今日概览',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Icon(Icons.local_fire_department, color: Colors.white70, size: 20),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _statItem('待处理告警', intOf(stats['pendingAlerts'])),
              _statItem('我的在办', intOf(stats['myWorkorders'])),
              _statItem('可领取', intOf(stats['claimableWorkorders'])),
            ],
          ),
          const SizedBox(height: 14),
          Container(height: 1, color: Colors.white24),
          const SizedBox(height: 12),
          Row(
            children: [
              _miniStat('今日巡检', intOf(stats['todayInspections'])),
              _miniStat('今日告警', intOf(stats['todayAlerts'])),
              _miniStat('设备总数', intOf(stats['deviceCount'])),
            ],
          ),
        ],
      ),
    );
  }

  Widget _statItem(String label, int value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$value',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w700,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _miniStat(String label, int value) {
    return Expanded(
      child: Text(
        '$label $value',
        style: const TextStyle(color: Colors.white, fontSize: 12),
      ),
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    final actions = <_QuickAction>[
      _QuickAction(
        icon: Icons.photo_camera_outlined,
        label: '拍照巡检',
        onTap: () => widget.onOpenTab?.call(1),
      ),
      _QuickAction(
        icon: Icons.add_task_outlined,
        label: '新建工单',
        onTap: () => Navigator.of(context).pushNamed('/workorder-create'),
      ),
      _QuickAction(
        icon: Icons.precision_manufacturing_outlined,
        label: '设备台账',
        onTap: () => Navigator.of(context).pushNamed('/devices'),
      ),
      _QuickAction(
        icon: Icons.question_answer_outlined,
        label: '消防问答',
        onTap: () => Navigator.of(context).pushNamed('/qa'),
      ),
    ];

    return SectionCard(
      title: '常用功能',
      child: Row(
        children: actions
            .map((action) => Expanded(
                  child: InkWell(
                    onTap: action.onTap,
                    borderRadius: BorderRadius.circular(10),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Column(
                        children: [
                          Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              color: const Color(0xFFFEF2F2),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(action.icon, color: const Color(0xFFDC2626), size: 22),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            action.label,
                            style: const TextStyle(fontSize: 12, color: Color(0xFF334155)),
                          ),
                        ],
                      ),
                    ),
                  ),
                ))
            .toList(),
      ),
    );
  }

  Widget _buildTodo(Map<String, dynamic> home, List<Map<String, dynamic>> tasks) {
    final items = <Map<String, dynamic>>[
      // tasks 是「已指派给我的工单 + 待处理告警」，不含待认领的，所以再补上可领取工单
      ...asMapList(home['claimableWorkorders']),
      ...tasks,
    ];

    return SectionCard(
      title: '今日待办',
      trailing: TextButton(
        onPressed: () => widget.onOpenTab?.call(3),
        child: const Text('查看全部', style: TextStyle(fontSize: 12)),
      ),
      child: items.isEmpty
          ? const Padding(
              padding: EdgeInsets.symmetric(vertical: 18),
              child: EmptyView(
                message: '暂无待办，一切正常',
                icon: Icons.verified_outlined,
              ),
            )
          : Column(
              children: items.take(6).map((item) => _TodoTile(item: item, onChanged: _reload)).toList(),
            ),
    );
  }
}

class _QuickAction {
  const _QuickAction({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;
}

/// 待办项：告警与工单一共两种形态，字段来自 `/api/mobile/*` 的驼峰结构
class _TodoTile extends StatelessWidget {
  const _TodoTile({required this.item, required this.onChanged});

  final Map<String, dynamic> item;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final isAlert = textOf(item['type']) == 'alert';
    final severity = textOf(item['severity'], fallback: 'medium');
    final title = textOf(item['title'], fallback: isAlert ? '告警' : '工单');
    final statusLabel = textOf(item['statusLabel'], fallback: textOf(item['status']));
    final color = isAlert ? severityColor(severity) : workorderStatusColor(textOf(item['status']));

    return InkWell(
      onTap: () {
        final id = intOf(item['id']);
        if (id == 0) return;
        Navigator.of(context).pushNamed(isAlert ? '/alert-detail' : '/workorder-detail', arguments: id);
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 9),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            StatusChip(
              label: isAlert
                  ? textOf(item['severityLabel'], fallback: '告警')
                  : textOf(item['status'], fallback: '工单'),
              color: color,
              compact: true,
              icon: isAlert ? Icons.warning_amber_rounded : Icons.assignment_outlined,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      color: Color(0xFF1E293B),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    [
                      textOf(item['location'], fallback: textOf(item['buildingName'])),
                      textOf(item['code']),
                    ].where((t) => t.isNotEmpty).join(' · '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  formatRelativeTime(item['createdAt']),
                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                ),
                if (statusLabel.isNotEmpty && statusLabel != textOf(item['status']))
                  Text(
                    statusLabel,
                    style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
