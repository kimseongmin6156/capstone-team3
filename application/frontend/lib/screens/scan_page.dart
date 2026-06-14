import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import '../config/api_config.dart';
import '../theme/app_colors.dart';
import '../widgets/bottom_nav_bar.dart';

class ScanPage extends StatefulWidget {
  const ScanPage({Key? key}) : super(key: key);

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> {
  static const String _apiBase = ApiConfig.apiBase;

  Uint8List? _selectedBytes;
  bool _isProcessing = false;

  Future<void> _capture() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.camera);
    if (picked != null) await _handlePicked(picked);
  }

  Future<void> _upload() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.gallery);
    if (picked != null) await _handlePicked(picked);
  }

  Future<void> _handlePicked(XFile picked) async {
    final bytes = await picked.readAsBytes();
    setState(() {
      _selectedBytes = bytes;
      _isProcessing = true;
    });
    await _sendToBackend(bytes, picked.name);
  }

  Future<void> _sendToBackend(Uint8List bytes, String filename) async {
    try {
      final req = http.MultipartRequest(
        'POST',
        Uri.parse('$_apiBase/api/scan'),
      );
      req.files.add(http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: filename,
      ));
      final streamed = await req.send();
      final res = await http.Response.fromStream(streamed);

      if (!mounted) return;
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        final results = (data['results'] as List?) ?? [];
        if (results.isEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('알약을 인식하지 못했습니다.')),
          );
        } else {
          Navigator.pushNamed(
            context,
            '/analysis',
            arguments: {
              'scan': data,
              'imageBytes': bytes,
            },
          );
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('스캔 실패: HTTP ${res.statusCode}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('서버 연결 실패: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.primary,
      body: Column(
        children: [
          // ==== 상단 헤더 ====
          SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 8),
                    child: Text(
                      '약품 스캔',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textOnPrimary,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close, color: AppColors.textOnPrimary),
                  ),
                ],
              ),
            ),
          ),

          // ==== 카메라 영역 + 하단 버튼 (Stack) ====
          Expanded(
            child: Stack(
              children: [
                // 카메라 / 선택된 이미지
                Positioned.fill(
                  child: _selectedBytes != null
                      ? Image.memory(_selectedBytes!, fit: BoxFit.cover)
                      : Container(
                          color: AppColors.primary,
                          child: const Center(
                            child: Icon(Icons.camera_alt,
                                size: 100, color: AppColors.primarySoft),
                          ),
                        ),
                ),

                // 처리 중 인디케이터
                if (_isProcessing)
                  const Center(
                    child: CircularProgressIndicator(
                      valueColor:
                          AlwaysStoppedAnimation(AppColors.textOnPrimary),
                    ),
                  ),

                // 하단 버튼 (업로드 + 촬영)
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 24,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _CircleButton(
                        icon: Icons.photo_library_outlined,
                        size: 56,
                        iconSize: 26,
                        background:
                            AppColors.textOnPrimary.withValues(alpha: 0.25),
                        onTap: _isProcessing ? null : _upload,
                      ),
                      const SizedBox(width: 32),
                      _CircleButton(
                        icon: Icons.camera_alt,
                        size: 80,
                        iconSize: 38,
                        background: AppColors.textOnPrimary,
                        iconColor: AppColors.primary,
                        border: true,
                        onTap: _isProcessing ? null : _capture,
                      ),
                      const SizedBox(width: 32),
                      const SizedBox(width: 56), // 좌우 대칭용 빈 공간
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: const BottomNavBar(currentIndex: 2),
    );
  }
}

class _CircleButton extends StatelessWidget {
  final IconData icon;
  final double size;
  final double iconSize;
  final Color background;
  final Color iconColor;
  final bool border;
  final VoidCallback? onTap;

  const _CircleButton({
    required this.icon,
    required this.size,
    required this.iconSize,
    required this.background,
    this.iconColor = AppColors.textOnPrimary,
    this.border = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: background,
          shape: BoxShape.circle,
          border: border
              ? Border.all(color: AppColors.textOnPrimary, width: 4)
              : null,
        ),
        child: Icon(icon, size: iconSize, color: iconColor),
      ),
    );
  }
}
