import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../state/my_pills_store.dart';
import '../theme/app_colors.dart';
import '../widgets/category_badge.dart';

class AnalysisPage extends StatefulWidget {
  const AnalysisPage({Key? key}) : super(key: key);

  @override
  State<AnalysisPage> createState() => _AnalysisPageState();
}

class _AnalysisPageState extends State<AnalysisPage> {
  /// 체크된 알약의 drug_code 집합
  final Set<String> _selected = {};
  bool _initialized = false;

  @override
  Widget build(BuildContext context) {
    // scan_page에서 전달받은 데이터
    final args = ModalRoute.of(context)?.settings.arguments as Map?;
    final scan = (args?['scan'] as Map?) ?? const {};
    final imageBytes = args?['imageBytes'] as Uint8List?;
    final rawResults = (scan['results'] as List?) ?? const [];
    final results = rawResults.cast<Map<String, dynamic>>().toList();

    // 첫 진입 시 이미 추가된 알약을 제외하고 전부 체크
    if (!_initialized) {
      for (final r in results) {
        final code = r['drug_code'] as String?;
        if (code != null && !MyPillsStore.contains(code)) {
          _selected.add(code);
        }
      }
      _initialized = true;
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Stack(
          children: [
            Column(
          children: [
            // ==== 헤더 ====
            Container(
              color: AppColors.surface,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              child: Row(
                children: [
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.arrow_back),
                  ),
                  const Text(
                    '알약 분석',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),

            // ==== 결과 카드 ====
            Expanded(
              child: results.isEmpty
                  ? const Center(
                      child: Text(
                        '인식된 알약이 없습니다',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.all(20),
                      itemCount: results.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, i) {
                        final r = results[i];
                        final code = (r['drug_code'] ?? '') as String;
                        final isChecked = _selected.contains(code);
                        return _PillResultCard(
                          data: r,
                          fallbackImageBytes: imageBytes,
                          checked: isChecked,
                          onToggle: () {
                            setState(() {
                              if (isChecked) {
                                _selected.remove(code);
                              } else {
                                _selected.add(code);
                              }
                            });
                          },
                        );
                      },
                    ),
            ),

            // ==== 액션 버튼 ====
            if (results.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                child: Column(
                  children: [
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton.icon(
                        onPressed: _selected.isEmpty
                            ? null
                            : () => _addCheckedToMyPills(results),
                        icon: const Icon(Icons.add_circle_outline),
                        label: Text(
                          _selected.isEmpty
                              ? '선택된 알약 없음'
                              : '선택한 ${_selected.length}개 나의 알약에 추가',
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primarySoft,
                          foregroundColor: AppColors.textOnPrimary,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14)),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: OutlinedButton.icon(
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.camera_alt),
                        label: const Text('다시 스캔'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppColors.primary,
                          side: const BorderSide(color: AppColors.primarySoft),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
            ),
            // ==== 챗봇 FAB (액션 버튼 위에 떠 있음) ====
            Positioned(
              right: 16,
              bottom: 145,
              child: FloatingActionButton(
                onPressed: () => Navigator.pushNamed(context, '/chatbot'),
                backgroundColor: AppColors.accent,
                foregroundColor: AppColors.textOnPrimary,
                shape: const CircleBorder(),
                tooltip: 'AI 상담',
                child: const Icon(Icons.chat_bubble_outline),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _addCheckedToMyPills(List<Map<String, dynamic>> results) async {
    int added = 0;
    for (final r in results) {
      final code = r['drug_code'] as String?;
      if (code == null || !_selected.contains(code)) continue;
      if (MyPillsStore.contains(code)) continue;
      final ok = await MyPillsStore.add({
        'drug_code': code,
        'medicine_name': r['name'],
        'main_ingredient': r['ingredient'],
        'image': r['image'],
      });
      if (ok) added++;
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$added개를 나의 알약에 추가했습니다')),
    );
  }
}

/// 결과 카드: 왼쪽 = 이미지+체크박스, 오른쪽 = 이름/성분/확률
class _PillResultCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final Uint8List? fallbackImageBytes;
  final bool checked;
  final VoidCallback onToggle;

  const _PillResultCard({
    required this.data,
    required this.fallbackImageBytes,
    required this.checked,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final name = (data['name'] ?? data['drug_code'] ?? '알 수 없음') as String;
    final ingredient = (data['ingredient'] ?? '') as String;
    final image = data['image'] as String?;
    final category = (data['category'] ?? '') as String;
    final conf = data['confidence'];
    final confText =
        conf is num ? '${(conf * 100).toStringAsFixed(1)}%' : '-';

    return GestureDetector(
      onTap: onToggle,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: checked ? AppColors.primarySoft : AppColors.border,
            width: 2,
          ),
        ),
        child: Row(
          children: [
            // 왼쪽: 이미지 + 좌상단 체크박스
            SizedBox(
              width: 96,
              height: 96,
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: SizedBox(
                      width: 96,
                      height: 96,
                      child: (image != null && image.isNotEmpty)
                          ? Image.network(
                              ApiConfig.proxyImage(image),
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => _imageFallback(),
                            )
                          : (fallbackImageBytes != null
                              ? Image.memory(fallbackImageBytes!,
                                  fit: BoxFit.cover)
                              : _imageFallback()),
                    ),
                  ),
                  Positioned(
                    top: 4,
                    left: 4,
                    child: _Checkbox(checked: checked, onTap: onToggle),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),
            // 오른쪽: 이름 / 성분 / 확률
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  if (ingredient.isNotEmpty)
                    Text(
                      ingredient,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      if (category.isNotEmpty) CategoryBadge(text: category),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.success.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          confText,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: AppColors.success,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _imageFallback() => Container(
        color: AppColors.surfaceMuted,
        child: const Icon(Icons.medication,
            size: 36, color: AppColors.textSecondary),
      );
}

class _Checkbox extends StatelessWidget {
  final bool checked;
  final VoidCallback onTap;
  const _Checkbox({required this.checked, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: checked ? AppColors.primarySoft : AppColors.surface,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: checked ? AppColors.primarySoft : AppColors.borderStrong,
            width: 2,
          ),
        ),
        child: checked
            ? const Icon(Icons.check, size: 16, color: AppColors.textOnPrimary)
            : null,
      ),
    );
  }
}
