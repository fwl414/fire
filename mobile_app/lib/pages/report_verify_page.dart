import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// 报告验真：`GET /api/reports/verify/{report_no}`（公开接口，不需要令牌）。
///
/// 支持传报告编号（`RPT-…`）或档案编号（`REC-M-1`）；
/// 二维码来自 `GET /api/reports/verify-qr/{report_no}`（PNG）。
/// 「分享」不引入三方依赖：复制验真链接到剪贴板 + SnackBar 提示。
class ReportVerifyPage extends StatefulWidget {
  const ReportVerifyPage({super.key, this.reportNo = ''});

  /// 从档案详情跳进来时带上报告编号，可直接自动验真
  final String reportNo;

  @override
  State<ReportVerifyPage> createState() => _ReportVerifyPageState();
}

class _ReportVerifyPageState extends State<ReportVerifyPage> {
  late final TextEditingController _controller;
  Future<Map<String, dynamic>>? _future;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.reportNo);
    if (widget.reportNo.trim().isNotEmpty) _verify();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _verify() {
    final value = _controller.text.trim();
    if (value.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入报告编号或档案编号')),
      );
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() => _future = api.verifyReport(value));
  }

  Future<void> _copy(String label, String value) async {
    if (value.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$label已复制：$value')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('报告验真')),
      body: Column(
        children: [
          Container(
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _verify(),
                    decoration: const InputDecoration(
                      isDense: true,
                      labelText: '报告编号 / 档案编号',
                      hintText: '例如 RPT-20260919221945-C3B5',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(onPressed: _verify, child: const Text('验真')),
              ],
            ),
          ),
          Expanded(
            child: _future == null
                ? const EmptyView(
                    message: '输入报告编号后点「验真」，可核验报告真伪与闭环情况',
                    icon: Icons.verified_outlined,
                  )
                : AsyncView<Map<String, dynamic>>(
                    future: _future!,
                    onRetry: _verify,
                    loadingMessage: '正在核验报告…',
                    emptyMessage: '未返回验真结果',
                    emptyIcon: Icons.verified_outlined,
                    isEmpty: (data) => data.isEmpty,
                    builder: (context, data) => _buildResult(data),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildResult(Map<String, dynamic> data) {
    final valid = data['valid'] == true;
    final reportNo = textOf(data['report_no'], fallback: _controller.text.trim());
    final verifyUrl = '/report-verify/$reportNo';

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        SectionCard(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                valid ? Icons.verified_outlined : Icons.gpp_bad_outlined,
                size: 30,
                color: valid ? const Color(0xFF15803D) : const Color(0xFFB91C1C),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    StatusChip(
                      label: valid ? '报告真实有效' : '未查询到该报告',
                      color: valid ? const Color(0xFF15803D) : const Color(0xFFB91C1C),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      textOf(data['message'], fallback: '—'),
                      style: const TextStyle(fontSize: 13, color: Color(0xFF334155), height: 1.6),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (valid) ...[
          SectionCard(
            title: '报告信息',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                InfoRow(label: '报告编号', value: reportNo),
                InfoRow(label: '档案编号', value: textOf(data['record_id'])),
                InfoRow(label: '巡检地点', value: textOf(data['location'])),
                InfoRow(label: '巡检时间', value: formatFullTime(data['created_at'])),
                InfoRow(label: '风险等级', value: textOf(data['risk_level'])),
                InfoRow(
                  label: '风险评分',
                  value: numOf(data['risk_score']).toStringAsFixed(
                    numOf(data['risk_score']) % 1 == 0 ? 0 : 1,
                  ),
                ),
                InfoRow(label: '闭环情况', value: textOf(data['closed_loop_status'])),
                InfoRow(label: '复查状态', value: textOf(data['review_status'])),
                InfoRow(label: '报告指纹', value: textOf(data['report_hash'])),
              ],
            ),
          ),
          SectionCard(
            title: '验真二维码',
            child: Center(child: _buildQr(reportNo)),
          ),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _copy('报告编号', reportNo),
                  icon: const Icon(Icons.copy_outlined, size: 18),
                  label: const Text('复制编号'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: () => _copy('验真链接', verifyUrl),
                  icon: const Icon(Icons.share_outlined, size: 18),
                  label: const Text('分享'),
                ),
              ),
            ],
          ),
        ] else ...[
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _copy('验真链接', verifyUrl),
                  icon: const Icon(Icons.share_outlined, size: 18),
                  label: const Text('分享'),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  /// 二维码是后端动态生成的 PNG（公开接口），这里仍按统一方式带上鉴权头加载
  Widget _buildQr(String reportNo) {
    final request = api.reportVerifyQrRequest(reportNo);
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Image.network(
        request.uri.toString(),
        headers: request.headers,
        width: 180,
        height: 180,
        fit: BoxFit.contain,
        errorBuilder: (context, error, stackTrace) => const SizedBox(
          width: 180,
          height: 180,
          child: Center(
            child: Text(
              '二维码加载失败，可改用报告编号核验',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
            ),
          ),
        ),
        loadingBuilder: (context, child, progress) => progress == null
            ? child
            : const SizedBox(
                width: 180,
                height: 180,
                child: Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2.2),
                  ),
                ),
              ),
      ),
    );
  }
}
