import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../state/my_pills_store.dart';
import '../state/user_store.dart';
import '../theme/app_colors.dart';
import '../widgets/bottom_nav_bar.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({Key? key}) : super(key: key);

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  static const String _apiBase = ApiConfig.apiBase;

  bool _isEditing = false;
  bool _isLoading = true;

  final _nameController = TextEditingController();
  final _emailController = TextEditingController(); // 읽기 전용
  final _birthDateController = TextEditingController();
  final _allergiesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _birthDateController.dispose();
    _allergiesController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    final uid = UserStore.userId.value;
    if (uid == null) {
      setState(() => _isLoading = false);
      return;
    }
    try {
      final res = await http.get(Uri.parse('$_apiBase/api/user/me?user_id=$uid'));
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        _nameController.text = data['name'] ?? '';
        _emailController.text = data['email'] ?? '';
        _birthDateController.text = data['birth_date'] ?? '';
        _allergiesController.text = data['allergies'] ?? '';
      }
    } catch (_) {
      // 무시 (네트워크 오류)
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _saveProfile() async {
    final uid = UserStore.userId.value;
    if (uid == null) return;
    try {
      final res = await http.patch(
        Uri.parse('$_apiBase/api/user/me'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': uid,
          'name': _nameController.text,
          'birth_date': _birthDateController.text,
          'allergies': _allergiesController.text,
        }),
      );
      if (!mounted) return;
      if (res.statusCode == 200) {
        setState(() => _isEditing = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('프로필이 저장됐습니다')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('저장 실패: HTTP ${res.statusCode}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('서버 연결 실패: $e')),
        );
      }
    }
  }

  Future<void> _confirmLogout() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('로그아웃'),
        content: const Text('로그아웃 하시겠습니까?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.danger,
              foregroundColor: AppColors.textOnPrimary,
            ),
            child: const Text('로그아웃'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    await UserStore.logout();
    MyPillsStore.clear();
    if (mounted) {
      Navigator.pushNamedAndRemoveUntil(context, '/login', (_) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // ==== 프로필 카드 ====
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Column(
                        children: [
                          Row(
                            children: [
                              Container(
                                width: 72,
                                height: 72,
                                decoration: const BoxDecoration(
                                  color: AppColors.accent,
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(Icons.person,
                                    color: AppColors.textOnPrimary, size: 36),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _nameController.text.isEmpty
                                          ? '이름 없음'
                                          : _nameController.text,
                                      style: const TextStyle(
                                          fontSize: 18,
                                          fontWeight: FontWeight.w600),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      _emailController.text,
                                      style: const TextStyle(
                                          color: AppColors.textSecondary),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 24),

                          _buildField('이름', _nameController, Icons.person,
                              editable: true),
                          const SizedBox(height: 16),
                          _buildField('이메일', _emailController, Icons.email,
                              editable: false),
                          const SizedBox(height: 16),
                          _buildField('생년월일', _birthDateController,
                              Icons.calendar_today,
                              editable: true),
                          const SizedBox(height: 16),
                          _buildField('알레르기', _allergiesController,
                              Icons.health_and_safety,
                              editable: true),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),

                    // ==== 액션 버튼 (수정 / 로그아웃) ====
                    if (_isEditing) ...[
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: () {
                                setState(() => _isEditing = false);
                                _loadProfile();
                              },
                              icon: const Icon(Icons.close),
                              label: const Text('취소'),
                              style: OutlinedButton.styleFrom(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 14),
                                foregroundColor: AppColors.textSecondary,
                                side: const BorderSide(color: AppColors.border),
                                shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(14)),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: _saveProfile,
                              icon: const Icon(Icons.save),
                              label: const Text('저장'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.primarySoft,
                                foregroundColor: AppColors.textOnPrimary,
                                padding:
                                    const EdgeInsets.symmetric(vertical: 14),
                                shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(14)),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ] else ...[
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          onPressed: () => setState(() => _isEditing = true),
                          icon: const Icon(Icons.edit),
                          label: const Text('수정'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.primarySoft,
                            foregroundColor: AppColors.textOnPrimary,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14)),
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: _confirmLogout,
                          icon: const Icon(Icons.logout),
                          label: const Text('로그아웃'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: AppColors.danger,
                            side: const BorderSide(color: AppColors.danger),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14)),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
      ),
      bottomNavigationBar: const BottomNavBar(currentIndex: 4),
    );
  }

  Widget _buildField(
    String label,
    TextEditingController controller,
    IconData icon, {
    required bool editable,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 16, color: AppColors.textSecondary),
            const SizedBox(width: 8),
            Text(label,
                style:
                    const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
          ],
        ),
        const SizedBox(height: 8),
        if (_isEditing && editable)
          TextField(
            controller: controller,
            decoration: InputDecoration(
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
          )
        else
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.surfaceMuted,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              controller.text.isEmpty ? '-' : controller.text,
              style: const TextStyle(fontSize: 15),
            ),
          ),
      ],
    );
  }
}
