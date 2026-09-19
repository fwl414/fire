import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 新建工单：独立页面表单，提交后真实落库。
/// 老实现是个 bottom sheet，点提交只弹「创建成功」，压根没调接口。
class WorkorderCreatePage extends StatefulWidget {
  const WorkorderCreatePage({super.key});

  @override
  State<WorkorderCreatePage> createState() => _WorkorderCreatePageState();
}

class _WorkorderCreatePageState extends State<WorkorderCreatePage> {
  /// 与 web 端创建表单一致的中文取值（后端 priority 原样存字符串）
  static const List<String> _priorities = ['高', '中', '低'];

  final TextEditingController _titleCtrl = TextEditingController();
  final TextEditingController _descriptionCtrl = TextEditingController();
  final TextEditingController _locationCtrl = TextEditingController();

  String _priority = '中';
  int? _deviceId;
  List<Map<String, dynamic>> _devices = [];
  bool _loadingDevices = true;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _loadDevices();
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descriptionCtrl.dispose();
    _locationCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadDevices() async {
    try {
      final data = await api.devices(page: 1, pageSize: 50);
      if (!mounted) return;
      setState(() {
        _devices = asMapList(data['items']);
        _loadingDevices = false;
      });
    } catch (_) {
      // 设备只是可选的关联项，拉不到也不能挡住手工填单
      if (!mounted) return;
      setState(() => _loadingDevices = false);
    }
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _submit() async {
    if (_submitting) return;
    final title = _titleCtrl.text.trim();
    final description = _descriptionCtrl.text.trim();
    if (title.isEmpty) {
      _toast('请填写工单标题');
      return;
    }
    if (description.isEmpty) {
      _toast('请填写问题描述');
      return;
    }

    setState(() => _submitting = true);
    try {
      await api.createWorkorder(
        title: title,
        description: description,
        deviceId: _deviceId,
        location: _locationCtrl.text.trim(),
        priority: _priority,
        ticketType: '现场上报',
      );
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _submitting = false);
      _toast(describeError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('新建工单')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _titleCtrl,
                  decoration: const InputDecoration(
                    labelText: '标题 *',
                    hintText: '例：3 层配电室烟感报警',
                  ),
                  textInputAction: TextInputAction.next,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _descriptionCtrl,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: '问题描述 *',
                    alignLabelWithHint: true,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _locationCtrl,
                  decoration: const InputDecoration(
                    labelText: '位置',
                    hintText: '可手填，选中设备后会自动带出',
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _priority,
                  decoration: const InputDecoration(labelText: '优先级'),
                  items: _priorities
                      .map((value) =>
                          DropdownMenuItem(value: value, child: Text(value)))
                      .toList(),
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => _priority = value);
                  },
                ),
                const SizedBox(height: 12),
                _buildDeviceField(),
              ],
            ),
          ),
          const SizedBox(height: 4),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('提交工单'),
          ),
        ],
      ),
    );
  }

  Widget _buildDeviceField() {
    if (_loadingDevices) {
      return const InputDecorator(
        decoration: InputDecoration(labelText: '关联设备'),
        child: Row(
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 8),
            Text(
              '正在加载设备…',
              style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
            ),
          ],
        ),
      );
    }

    return DropdownButtonFormField<int?>(
      initialValue: _deviceId,
      decoration: const InputDecoration(labelText: '关联设备', hintText: '不关联设备'),
      isExpanded: true,
      items: [
        const DropdownMenuItem<int?>(value: null, child: Text('不关联设备')),
        ..._devices.map((device) {
          final label = [
            textOf(device['device_code']),
            textOf(device['device_name'], fallback: textOf(device['device_type'])),
          ].where((text) => text.isNotEmpty).join(' ');
          return DropdownMenuItem<int?>(
            value: intOf(device['id']),
            child: Text(
              label.isEmpty ? '未命名设备' : label,
              overflow: TextOverflow.ellipsis,
            ),
          );
        }),
      ],
      onChanged: (value) {
        setState(() {
          _deviceId = value;
          if (value == null) return;
          // 选中设备后把位置预填成设备的 location，用户仍可改
          final device = _devices.firstWhere(
            (item) => intOf(item['id']) == value,
            orElse: () => const <String, dynamic>{},
          );
          final location = textOf(device['location']);
          if (location.isNotEmpty) _locationCtrl.text = location;
        });
      },
    );
  }
}
