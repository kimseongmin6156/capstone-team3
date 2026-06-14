import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../state/my_pills_store.dart';
import '../theme/app_colors.dart';
import '../widgets/bottom_nav_bar.dart';
import '../widgets/category_badge.dart';

class MyPillsPage extends StatefulWidget {
  const MyPillsPage({Key? key}) : super(key: key);

  @override
  State<MyPillsPage> createState() => _MyPillsPageState();
}

class _MyPillsPageState extends State<MyPillsPage> {
  @override
  void initState() {
    super.initState();
    // 화면 진입 시 서버에서 최신 목록 새로고침
    WidgetsBinding.instance.addPostFrameCallback((_) {
      MyPillsStore.refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Column(
        children: [
          Container(
            color: AppColors.surface,
            child: SafeArea(
              bottom: false,
              child: const Padding(
                padding: EdgeInsets.all(24),
                child: Row(
                  children: [
                    Text(
                      '나의 알약',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: ValueListenableBuilder<List<Map<String, dynamic>>>(
              valueListenable: MyPillsStore.pills,
              builder: (context, pills, _) {
                if (pills.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: const [
                        Icon(Icons.medication, size: 64, color: AppColors.borderStrong),
                        SizedBox(height: 16),
                        Text(
                          '등록된 약품이 없습니다',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        SizedBox(height: 8),
                        Text(
                          '검색 페이지에서 + 버튼으로 약품을 추가하세요',
                          style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
                        ),
                      ],
                    ),
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: pills.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, i) => _PillCard(pill: pills[i]),
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => Navigator.pushNamed(context, '/search'),
        backgroundColor: AppColors.primarySoft,
        foregroundColor: AppColors.textOnPrimary,
        shape: const CircleBorder(),
        child: const Icon(Icons.add),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.startFloat,
      bottomNavigationBar: const BottomNavBar(currentIndex: 3),
    );
  }
}

class _PillCard extends StatelessWidget {
  final Map<String, dynamic> pill;
  const _PillCard({required this.pill});

  @override
  Widget build(BuildContext context) {
    final name = (pill['medicine_name'] ?? '') as String;
    final ingredient = (pill['main_ingredient'] ?? '') as String;
    final imageUrl = pill['image'] as String?;
    final code = (pill['drug_code'] ?? '') as String;
    final category = (pill['category'] ?? '') as String;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: SizedBox(
              width: 56,
              height: 56,
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  ingredient.isEmpty ? code : ingredient,
                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (category.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  CategoryBadge(text: category),
                ],
              ],
            ),
          ),
          IconButton(
            onPressed: () => MyPillsStore.remove(code),
            icon: const Icon(Icons.delete_outline, color: AppColors.danger),
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
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          : const Icon(Icons.medication, color: AppColors.textSecondary),
    );
  }
}
