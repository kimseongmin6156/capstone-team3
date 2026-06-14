import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import 'user_store.dart';

/// 사용자의 "나의 알약" 목록 (백엔드 user_pills 테이블과 동기화).
class MyPillsStore {
  MyPillsStore._();

  static const String _apiBase = ApiConfig.apiBase;

  static final ValueNotifier<List<Map<String, dynamic>>> pills =
      ValueNotifier<List<Map<String, dynamic>>>([]);

  /// 로그인 직후나 화면 진입 시 호출 — 서버에서 목록을 불러와 캐시.
  static Future<void> refresh() async {
    final uid = UserStore.userId.value;
    if (uid == null) {
      pills.value = [];
      return;
    }
    try {
      final uri = Uri.parse('$_apiBase/api/user/pills?user_id=$uid');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        pills.value =
            List<Map<String, dynamic>>.from(data['results'] ?? []);
      }
    } catch (_) {
      // 네트워크 실패 시 기존 캐시 유지
    }
  }

  /// 약품 추가 — 낙관적 업데이트 후 서버 호출. 성공 시 true.
  static Future<bool> add(Map<String, dynamic> pill) async {
    final uid = UserStore.userId.value;
    final code = pill['drug_code'] as String?;
    if (uid == null || code == null) return false;
    if (contains(code)) return false;

    // 낙관적 업데이트
    pills.value = [...pills.value, pill];

    try {
      final res = await http.post(
        Uri.parse('$_apiBase/api/user/pills'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'user_id': uid, 'drug_code': code}),
      );
      if (res.statusCode != 200) {
        _rollbackAdd(code);
        return false;
      }
      return true;
    } catch (_) {
      _rollbackAdd(code);
      return false;
    }
  }

  /// 약품 삭제 — 낙관적 업데이트 후 서버 호출.
  static Future<bool> remove(String drugCode) async {
    final uid = UserStore.userId.value;
    if (uid == null) return false;
    final removed = pills.value.firstWhere(
      (p) => p['drug_code'] == drugCode,
      orElse: () => <String, dynamic>{},
    );
    pills.value =
        pills.value.where((p) => p['drug_code'] != drugCode).toList();

    try {
      final res = await http.delete(
        Uri.parse('$_apiBase/api/user/pills?user_id=$uid&drug_code=$drugCode'),
      );
      if (res.statusCode != 200) {
        if (removed.isNotEmpty) pills.value = [...pills.value, removed];
        return false;
      }
      return true;
    } catch (_) {
      if (removed.isNotEmpty) pills.value = [...pills.value, removed];
      return false;
    }
  }

  static bool contains(String drugCode) =>
      pills.value.any((p) => p['drug_code'] == drugCode);

  static void _rollbackAdd(String code) {
    pills.value =
        pills.value.where((p) => p['drug_code'] != code).toList();
  }

  static void clear() {
    pills.value = [];
  }
}
