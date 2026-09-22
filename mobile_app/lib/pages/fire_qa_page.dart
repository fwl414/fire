import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/app_services.dart';
import '../widgets/common.dart';

/// UI 引导用的常见问题（只是按钮文案，不预填进输入框）
const List<String> _quickQuestions = [
  '电气火灾可以直接用水扑灭吗？',
  '灭火器多久需要检查一次？',
  '消防通道被堵塞要如何处理？',
];

/// 消防问答：`POST /api/qa/fire`（后端要求 Form 参数），
/// 返回 `{answer, references, retrieval_count, used_text_model_api, model_provider, model_name, agent_steps}`。
class FireQaPage extends StatefulWidget {
  const FireQaPage({super.key});

  @override
  State<FireQaPage> createState() => _FireQaPageState();
}

class _FireQaPageState extends State<FireQaPage> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_QaMessage> _messages = [];
  bool _sending = false;

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _ask(
    String question, {
    bool withUserBubble = true,
    _QaMessage? failed,
  }) async {
    final text = question.trim();
    if (text.isEmpty || _sending) return;

    setState(() {
      if (failed != null) _messages.remove(failed);
      if (withUserBubble) {
        _messages.add(_QaMessage(text: text, fromUser: true));
        _inputController.clear();
      }
      _sending = true;
    });
    _scrollToBottom();

    try {
      final data = await api.askFire(text);
      if (!mounted) return;
      setState(() {
        _messages.add(_QaMessage(
          text: _extractAnswer(data),
          fromUser: false,
          references: asMapList(data['references']),
        ));
        _sending = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _messages.add(_QaMessage(
          text: '回答失败：${describeError(error)}',
          fromUser: false,
          failed: true,
          question: text,
        ));
        _sending = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(describeError(error))),
      );
    }
    _scrollToBottom();
  }

  /// 后端真实字段是 `answer`；再兼容 `data.answer` 与 `result` 两种历史形态。
  String _extractAnswer(Map<String, dynamic> data) {
    final direct = textOf(data['answer']);
    if (direct.isNotEmpty) return direct;
    final nested = textOf(asMap(data['data'])['answer']);
    if (nested.isNotEmpty) return nested;
    final result = textOf(data['result']);
    if (result.isNotEmpty) return result;
    return '未获取到答案';
  }

  void _scrollToBottom() {
    // 等新气泡完成布局后再滚，否则 maxScrollExtent 还是旧值
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('消防问答')),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _buildGuide()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final message = _messages[index];
                      return _MessageBubble(
                        message: message,
                        onRetry: message.failed
                            ? () => _ask(
                                  message.question,
                                  withUserBubble: false,
                                  failed: message,
                                )
                            : null,
                      );
                    },
                  ),
          ),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildGuide() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 40, 20, 20),
      children: [
        const Icon(Icons.local_fire_department_outlined,
            size: 44, color: Color(0xFFFCA5A5)),
        const SizedBox(height: 12),
        const Center(
          child: Text(
            '消防知识问答',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Color(0xFF1E293B),
            ),
          ),
        ),
        const SizedBox(height: 6),
        const Center(
          child: Text(
            '基于消防知识库与智能模型，回答法规、隐患排查与处置问题',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8), height: 1.5),
          ),
        ),
        const SizedBox(height: 24),
        for (final question in _quickQuestions)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: OutlinedButton(
              onPressed: _sending ? null : () => _ask(question),
              style: OutlinedButton.styleFrom(
                alignment: Alignment.centerLeft,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                side: const BorderSide(color: Color(0xFFE2E8F0)),
              ),
              child: Text(
                question,
                style: const TextStyle(fontSize: 13, color: Color(0xFF334155)),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildInputBar() {
    return SafeArea(
      top: false,
      child: Container(
        color: Colors.white,
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: _inputController,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: _ask,
                decoration: InputDecoration(
                  hintText: '输入消防问题…',
                  hintStyle: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                  isDense: true,
                  filled: true,
                  fillColor: const Color(0xFFF1F5F9),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 44,
              height: 40,
              child: FilledButton(
                onPressed: _sending ? null : () => _ask(_inputController.text),
                style: FilledButton.styleFrom(padding: EdgeInsets.zero),
                child: _sending
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.send, size: 18),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 一条问答消息；失败时保留原始问题以便重试。
class _QaMessage {
  _QaMessage({
    required this.text,
    required this.fromUser,
    this.failed = false,
    this.question = '',
    this.references = const [],
  });

  final String text;
  final bool fromUser;
  final bool failed;
  final String question;

  /// 后端 `references` 是 RAG 检索到的知识片段（字段见 `_buildReferences`）
  final List<Map<String, dynamic>> references;
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message, this.onRetry});

  final _QaMessage message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final fromUser = message.fromUser;
    final name = session.displayName;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            fromUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!fromUser) ...[
            const _BubbleAvatar(
              icon: Icons.smart_toy_outlined,
              color: Color(0xFFDC2626),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment:
                  fromUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                if (!fromUser)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 4),
                    child: Text(
                      '消防助手',
                      style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                    ),
                  ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: fromUser ? const Color(0xFF2563EB) : Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: fromUser
                        ? null
                        : Border.all(color: const Color(0xFFE2E8F0)),
                  ),
                  child: SelectableText(
                    message.text,
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.55,
                      color: fromUser ? Colors.white : const Color(0xFF1E293B),
                    ),
                  ),
                ),
                if (!fromUser && message.references.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  _ReferencePanel(references: message.references),
                ],
                if (message.failed && onRetry != null) ...[
                  const SizedBox(height: 2),
                  TextButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh, size: 15),
                    label: const Text('重试', style: TextStyle(fontSize: 12)),
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 6),
                      minimumSize: const Size(0, 28),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (fromUser) ...[
            const SizedBox(width: 8),
            _BubbleAvatar(text: name.isEmpty ? '我' : name.substring(0, 1)),
          ],
        ],
      ),
    );
  }
}

/// 「引用依据」折叠面板：数据完全来自后端 `/api/qa/fire` 返回的 `references`。
class _ReferencePanel extends StatelessWidget {
  const _ReferencePanel({required this.references});

  final List<Map<String, dynamic>> references;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 10),
          childrenPadding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          shape: const Border(),
          collapsedShape: const Border(),
          iconColor: const Color(0xFF64748B),
          collapsedIconColor: const Color(0xFF94A3B8),
          title: Text(
            '引用依据（${references.length}）',
            style: const TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: Color(0xFF475569),
            ),
          ),
          children: [
            for (var i = 0; i < references.length; i++)
              Padding(
                padding: EdgeInsets.only(top: i == 0 ? 0 : 10),
                child: _ReferenceItem(index: i + 1, item: references[i]),
              ),
          ],
        ),
      ),
    );
  }
}

/// 单条引用：后端字段为
/// `title / category / source / content / score / citation / matched_keywords …`
class _ReferenceItem extends StatelessWidget {
  const _ReferenceItem({required this.index, required this.item});

  final int index;
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final title = textOf(item['title'], fallback: '未命名知识条目');
    final meta = [
      textOf(item['source']),
      textOf(item['category']),
      if (numOf(item['score']) > 0)
        '相关度 ${numOf(item['score']).toStringAsFixed(2)}',
    ].where((text) => text.isNotEmpty).join(' · ');
    final content = textOf(item['content']).trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '【引用$index】$title',
          style: const TextStyle(
            fontSize: 12.5,
            fontWeight: FontWeight.w600,
            color: Color(0xFF334155),
          ),
        ),
        if (meta.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(meta, style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
        ],
        if (content.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            content,
            maxLines: 4,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 12,
              height: 1.5,
              color: Color(0xFF475569),
            ),
          ),
        ],
      ],
    );
  }
}

class _BubbleAvatar extends StatelessWidget {
  const _BubbleAvatar({this.text, this.icon, this.color});

  final String? text;
  final IconData? icon;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        color: color ?? const Color(0xFFE0E7FF),
        borderRadius: BorderRadius.circular(8),
      ),
      alignment: Alignment.center,
      child: icon != null
          ? Icon(icon, size: 17, color: Colors.white)
          : Text(
              text ?? '我',
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xFF1E293B),
                fontWeight: FontWeight.w600,
              ),
            ),
    );
  }
}
