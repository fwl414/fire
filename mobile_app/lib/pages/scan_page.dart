import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 扫码巡检：扫到设备二维码后按 device_code 反查设备，命中就进设备详情。
class ScanPage extends StatefulWidget {
  const ScanPage({super.key});

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> {
  final MobileScannerController _controller = MobileScannerController();

  /// 摄像头每秒会推多帧，同一个码 2 秒内只处理一次，避免重复请求
  String? _lastCode;
  DateTime? _lastAt;
  bool _handling = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_handling || capture.barcodes.isEmpty) return;
    final code = (capture.barcodes.first.rawValue ?? '').trim();
    if (code.isEmpty) return;

    final now = DateTime.now();
    if (_lastCode == code &&
        _lastAt != null &&
        now.difference(_lastAt!) < const Duration(seconds: 2)) {
      return;
    }
    _lastCode = code;
    _lastAt = now;

    _handling = true;
    try {
      final data = await api.devices(keyword: code, pageSize: 5);
      // 后端 keyword 是模糊匹配，必须再按 device_code 精确比对（忽略大小写）
      final target = asMapList(data['items']).firstWhere(
        (device) => textOf(device['device_code']).trim().toLowerCase() == code.toLowerCase(),
        orElse: () => <String, dynamic>{},
      );
      final deviceId = intOf(target['id']);
      if (!mounted) return;
      if (deviceId == 0) {
        _toast('未找到编号为 $code 的设备');
        return;
      }
      await _controller.stop();
      if (!mounted) return;
      // 把扫到的设备写入全局定位，进入设备台账时直接定位到它而不是全量列表
      focusedDeviceId.value = deviceId;
      Navigator.of(context).pushReplacementNamed('/device-detail', arguments: deviceId);
    } catch (e) {
      if (!mounted) return;
      _toast(describeError(e));
    } finally {
      _handling = false;
    }
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Widget _errorBuilder(BuildContext context, MobileScannerException error, Widget? child) {
    final denied = error.errorCode == MobileScannerErrorCode.permissionDenied;
    return Container(
      color: Colors.black,
      alignment: Alignment.center,
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            denied ? Icons.no_photography_outlined : Icons.error_outline,
            color: Colors.white54,
            size: 44,
          ),
          const SizedBox(height: 14),
          Text(
            denied ? '相机权限被拒绝，无法扫码' : '相机启动失败，请退出后重试',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white70, fontSize: 13, height: 1.5),
          ),
          if (denied) ...[
            const SizedBox(height: 8),
            const Text(
              '请在系统设置里允许本应用使用相机',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white38, fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('扫码巡检')),
      body: Stack(
        children: [
          Positioned.fill(
            child: MobileScanner(
              controller: _controller,
              onDetect: _onDetect,
              errorBuilder: _errorBuilder,
            ),
          ),
          SafeArea(
            child: Align(
              alignment: Alignment.topCenter,
              child: Container(
                margin: const EdgeInsets.only(top: 20),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                decoration: BoxDecoration(
                  color: Colors.black54,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  '对准设备二维码扫描',
                  style: TextStyle(color: Colors.white, fontSize: 13),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
