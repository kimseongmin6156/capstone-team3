import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../state/my_pills_store.dart';
import '../theme/app_colors.dart';
import '../widgets/bottom_nav_bar.dart';

class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  static const int _previewCount = 2;

  @override
  void initState() {
    super.initState();
    // 진입 시 서버에서 최신 알약 목록 새로고침
    WidgetsBinding.instance.addPostFrameCallback((_) {
      MyPillsStore.refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ==== 인사 ====
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '안녕하세요!',
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                      ),
                      SizedBox(height: 2),
                      Text('오늘도 안전한 하루 되세요',
                          style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: const BoxDecoration(
                      color: AppColors.surfaceMuted,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.notifications, size: 22),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // ==== 4 액션 박스 (2x2) ====
              Row(
                children: [
                  Expanded(
                    child: _buildActionBox(
                        context, Icons.search, '약품 검색', '/search', AppColors.primary),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildActionBox(
                        context, Icons.camera_alt, '약품 스캔', '/scan', AppColors.primarySoft),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _buildActionBox(
                        context, Icons.medication, '나의 알약', '/my-pills', AppColors.accent),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildActionBox(
                        context, Icons.chat, 'AI 상담', '/chatbot', AppColors.accentLight),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // ==== 나의 알약 (실데이터 미리보기 N개) ====
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '나의 알약',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  GestureDetector(
                    onTap: () => Navigator.pushNamed(context, '/my-pills'),
                    child: const Text(
                      '전체보기',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Expanded(
                child: ValueListenableBuilder<List<Map<String, dynamic>>>(
                  valueListenable: MyPillsStore.pills,
                  builder: (context, allPills, _) {
                    if (allPills.isEmpty) {
                      return _buildEmptyPills(context);
                    }
                    final preview = allPills.take(_previewCount).toList();
                    return Column(
                      children: preview
                          .map((p) => Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: _PillPreviewCard(pill: p),
                              ))
                          .toList(),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: const BottomNavBar(currentIndex: 0),
    );
  }

  Widget _buildEmptyPills(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/search'),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.medication, size: 36, color: AppColors.borderStrong),
            SizedBox(height: 8),
            Text(
              '등록된 약품이 없습니다',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            SizedBox(height: 4),
            Text(
              '약품 검색에서 추가해보세요',
              style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  /// 4가지 그린 하이라이트 박스 (빠른 메뉴 형식: 아이콘 + 제목).
  Widget _buildActionBox(
    BuildContext context,
    IconData icon,
    String title,
    String route,
    Color color,
  ) {
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, route),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.textOnPrimary.withValues(alpha: 0.20),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, size: 24, color: AppColors.textOnPrimary),
            ),
            const SizedBox(height: 10),
            Text(
              title,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textOnPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PillPreviewCard extends StatelessWidget {
  final Map<String, dynamic> pill;
  const _PillPreviewCard({required this.pill});

  @override
  Widget build(BuildContext context) {
    final name = (pill['medicine_name'] ?? '') as String;
    final imageUrl = pill['image'] as String?;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: SizedBox(
              width: 44,
              height: 44,
              child: (imageUrl != null && imageUrl.isNotEmpty)
                  ? Image.network(
                      ApiConfig.proxyImage(imageUrl),
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _fallbackIcon(),
                      loadingBuilder: (_, child, prog) =>
                          prog == null ? child : _fallbackIcon(loading: true),
                    )
                  : _fallbackIcon(),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              name,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _fallbackIcon({bool loading = false}) {
    return Container(
      color: AppColors.surfaceMuted,
      child: loading
          ? const Center(
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          : const Icon(Icons.medication, color: AppColors.textSecondary, size: 22),
    );
  }
}
