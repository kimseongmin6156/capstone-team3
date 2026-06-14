import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../state/my_pills_store.dart';
import '../theme/app_colors.dart';
import '../widgets/bottom_nav_bar.dart';
import '../widgets/category_badge.dart';

class SearchPage extends StatefulWidget {
  const SearchPage({Key? key}) : super(key: key);

  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final _searchController = TextEditingController();
  Timer? _debounce;
  bool _isLoading = false;
  String _query = '';
  List<Map<String, dynamic>> _results = [];

  static const String _apiBase = ApiConfig.apiBase;

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      _runSearch(value.trim());
    });
  }

  Future<void> _runSearch(String q) async {
    setState(() {
      _query = q;
      _isLoading = q.isNotEmpty;
      if (q.isEmpty) _results = [];
    });
    if (q.isEmpty) return;

    try {
      final uri = Uri.parse('$_apiBase/api/medicines/search?q=${Uri.encodeQueryComponent(q)}');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        if (!mounted) return;
        setState(() {
          _results = List<Map<String, dynamic>>.from(data['results'] ?? []);
          _isLoading = false;
        });
      } else {
        if (mounted) setState(() => _isLoading = false);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('검색 실패: $e')),
        );
      }
    }
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
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '약품 검색',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _searchController,
                      onChanged: _onSearchChanged,
                      onSubmitted: (v) => _runSearch(v.trim()),
                      decoration: InputDecoration(
                        hintText: '약품명 또는 성분을 입력하세요',
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: _searchController.text.isEmpty
                            ? null
                            : IconButton(
                                icon: const Icon(Icons.clear),
                                onPressed: () {
                                  _searchController.clear();
                                  _runSearch('');
                                },
                              ),
                        filled: true,
                        fillColor: AppColors.surfaceMuted,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(16),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
      bottomNavigationBar: const BottomNavBar(currentIndex: 1),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_query.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.search, size: 64, color: AppColors.borderStrong),
            SizedBox(height: 16),
            Text(
              '약품명 또는 성분을 검색하세요',
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
    }
    if (_results.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.search_off, size: 64, color: AppColors.borderStrong),
            const SizedBox(height: 16),
            Text(
              '"$_query" 에 대한 검색 결과가 없습니다',
              style: const TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _results.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, i) => _ResultCard(item: _results[i]),
    );
  }
}

class _ResultCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _ResultCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final name = (item['medicine_name'] ?? '') as String;
    final ingredient = (item['main_ingredient'] ?? '') as String;
    final imageUrl = item['image'] as String?;
    final code = (item['drug_code'] ?? '') as String;
    final category = (item['category'] ?? '') as String;

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
          const SizedBox(width: 8),
          ValueListenableBuilder<List<Map<String, dynamic>>>(
            valueListenable: MyPillsStore.pills,
            builder: (context, _, __) {
              final added = MyPillsStore.contains(code);
              return IconButton(
                onPressed: added
                    ? null
                    : () async {
                        final ok = await MyPillsStore.add(item);
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(ok
                                ? '"$name" 을(를) 나의 알약에 추가했습니다'
                                : '추가 실패 (서버 연결 확인)'),
                            duration: const Duration(seconds: 2),
                          ),
                        );
                      },
                icon: Icon(
                  added ? Icons.check_circle : Icons.add_circle_outline,
                  color: added ? AppColors.success : AppColors.primarySoft,
                  size: 28,
                ),
                tooltip: added ? '이미 추가됨' : '나의 알약에 추가',
              );
            },
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
