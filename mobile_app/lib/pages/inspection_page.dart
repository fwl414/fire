import 'dart:io';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 「巡检」tab：现场拍照 + 描述 → `POST /api/mobile/report`（复用巡检 Agent）。
///
/// 位置上不再写死默认值：选设备会自动带出设备 location，位置或设备至少填一个；
/// 定位在点上报时才读一次，读不到只提示、不阻断提交。
class InspectionPage extends StatefulWidget {
  const InspectionPage({super.key});

  @override
  State<InspectionPage> createState() => _InspectionPageState();
}

class _InspectionPageState extends State<InspectionPage> {
  final ImagePicker _picker = ImagePicker();
  final TextEditingController _locationCtrl = TextEditingController();
  final TextEditingController _descCtrl = TextEditingController();

  late Future<Map<String, dynamic>> _devicesFuture;
  int? _deviceId;
  File? _image;
  bool _submitting = false;
  Map<String, dynamic>? _result;

  @override
  void initState() {
    super.initState();
    _devicesFuture = api.devices(pageSize: 50);
  }

  @override
  void dispose() {
    _locationCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  void _reloadDevices() => setState(() => _devicesFuture = api.devices(pageSize: 50));

  void _onDeviceChanged(int? value, List<Map<String, dynamic>> devices) {
    setState(() {
      _deviceId = value;
      // 选中设备后把设备位置预填到位置框，用户仍可手动改
      final device = devices.firstWhere(
        (item) => intOf(item['id']) == value,
        orElse: () => <String, dynamic>{},
      );
      final location = textOf(device['location']);
      if (location.isNotEmpty) _locationCtrl.text = location;
    });
  }

  Future<void> _pick(ImageSource source) async {
    try {
      final picked = await _picker.pickImage(
        source: source,
        maxWidth: 1600,
        imageQuality: 80,
      );
      if (picked == null || !mounted) return;
      setState(() => _image = File(picked.path));
    } catch (e) {
      if (!mounted) return;
      _toast(describeError(e));
    }
  }

  /// 读一次经纬度用于核对是否真的到了点位；任何失败都返回 null（降级为无定位上报）
  Future<String?> _readPosition() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return null;
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return null;
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(timeLimit: Duration(seconds: 10)),
      );
      return '${position.latitude.toStringAsFixed(6)},${position.longitude.toStringAsFixed(6)}';
    } catch (_) {
      return null;
    }
  }

  Future<void> _submit() async {
    final location = _locationCtrl.text.trim();
    if (location.isEmpty && _deviceId == null) {
      _toast('请选择设备或填写现场位置');
      return;
    }

    setState(() {
      _submitting = true;
      _result = null;
    });
    try {
      final base = _descCtrl.text.trim();
      final position = await _readPosition();
      if (!mounted) return;
      if (position == null) {
        _toast('未获取到定位，已按无定位提交');
      }
      final description =
          position == null ? base : (base.isEmpty ? '【定位】$position' : '$base\n【定位】$position');

      final data = await api.submitReport(
        deviceId: _deviceId,
        location: location,
        description: description,
        imagePath: _image?.path,
      );
      if (!mounted) return;
      setState(() => _result = data);
    } catch (e) {
      if (!mounted) return;
      _toast(describeError(e));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        SectionCard(
          title: '现场上报',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildDeviceField(),
              const SizedBox(height: 12),
              TextField(
                controller: _locationCtrl,
                decoration: const InputDecoration(
                  labelText: '现场位置',
                  hintText: '选设备会自动带出，也可手填',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _descCtrl,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: '现场描述',
                  hintText: '例如：消防通道堆放杂物、插排串联…',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: _submitting ? null : () => _pick(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera_outlined, size: 18),
                    label: const Text('拍照'),
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    onPressed: _submitting ? null : () => _pick(ImageSource.gallery),
                    icon: const Icon(Icons.photo_outlined, size: 18),
                    label: const Text('相册'),
                  ),
                ],
              ),
              if (_image != null) ...[
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.file(_image!, height: 170, width: double.infinity, fit: BoxFit.cover),
                ),
              ],
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _submitting ? null : _submit,
                  icon: _submitting
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.upload_outlined, size: 18),
                  label: Text(_submitting ? '分析中…' : '上报并分析'),
                ),
              ),
            ],
          ),
        ),
        if (_result != null) _buildResult(_result!),
      ],
    );
  }

  Widget _buildDeviceField() {
    return AsyncView<Map<String, dynamic>>(
      future: _devicesFuture,
      onRetry: _reloadDevices,
      loadingMessage: '正在加载设备…',
      isEmpty: (data) => asMapList(data['items']).isEmpty,
      emptyMessage: '暂无可选设备，可直接填写位置',
      emptyIcon: Icons.precision_manufacturing_outlined,
      builder: (context, data) {
        final devices = asMapList(data['items']);
        // 设备列表刷新后原选中项可能消失，不能让下拉框拿到不存在的值
        final selected =
            devices.any((device) => intOf(device['id']) == _deviceId) ? _deviceId : null;
        return DropdownButtonFormField<int>(
          initialValue: selected,
          isExpanded: true,
          decoration: const InputDecoration(
            labelText: '关联设备（可选）',
            border: OutlineInputBorder(),
          ),
          items: devices.map((device) {
            final code = textOf(device['device_code']);
            final name = textOf(device['device_name'], fallback: textOf(device['device_type']));
            return DropdownMenuItem<int>(
              value: intOf(device['id']),
              child: Text('$code $name', overflow: TextOverflow.ellipsis),
            );
          }).toList(),
          onChanged: _submitting ? null : (value) => _onDeviceChanged(value, devices),
        );
      },
    );
  }

  /// 后端 `/api/mobile/report` 返回 camelCase：ok/message/recordId/riskScore/…
  Widget _buildResult(Map<String, dynamic> data) {
    final riskLevel = textOf(data['riskLevel'], fallback: '未知');
    final riskScore = numOf(data['riskScore']);
    final scoreText = riskScore % 1 == 0
        ? '${riskScore.toInt()}'
        : riskScore.toStringAsFixed(1);
    final location = textOf(data['location']);
    final hazards = asList(data['hazards']).map((e) => '$e').where((e) => e.isNotEmpty).toList();
    final suggestion = textOf(data['suggestion']);
    final summary = textOf(data['executiveSummary']);
    final recordId = intOf(data['recordId']);

    return SectionCard(
      title: '分析结果',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                scoreText,
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: riskColor(riskLevel),
                ),
              ),
              const SizedBox(width: 4),
              const Padding(
                padding: EdgeInsets.only(bottom: 4),
                child: Text('分', style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
              ),
              const Spacer(),
              StatusChip(label: riskLevel, color: riskColor(riskLevel)),
            ],
          ),
          if (location.isNotEmpty) ...[
            const SizedBox(height: 6),
            InfoRow(label: '上报位置', value: location),
          ],
          if (hazards.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('识别到的隐患', style: _labelStyle),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: hazards
                  .map((hazard) => StatusChip(
                        label: hazard,
                        color: const Color(0xFFEA580C),
                        compact: true,
                      ))
                  .toList(),
            ),
          ],
          if (suggestion.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('处置建议', style: _labelStyle),
            const SizedBox(height: 4),
            Text(suggestion, style: _bodyStyle),
          ],
          if (summary.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('执行摘要', style: _labelStyle),
            const SizedBox(height: 4),
            Text(summary, style: _bodyStyle),
          ],
          if (recordId != 0) ...[
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton.tonalIcon(
                onPressed: () =>
                    Navigator.of(context).pushNamed('/record-detail', arguments: recordId),
                icon: const Icon(Icons.description_outlined, size: 18),
                label: const Text('查看记录详情'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

const TextStyle _labelStyle = TextStyle(
  fontSize: 12.5,
  fontWeight: FontWeight.w600,
  color: Color(0xFF64748B),
);

const TextStyle _bodyStyle = TextStyle(
  fontSize: 13,
  height: 1.6,
  color: Color(0xFF334155),
);
