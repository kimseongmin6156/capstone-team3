import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 로그인된 사용자 정보. SharedPreferences로 영속화 (웹에선 localStorage).
class UserStore {
  UserStore._();

  static const _kUserId = 'user_id';
  static const _kToken  = 'access_token';

  static final ValueNotifier<String?> userId = ValueNotifier<String?>(null);
  static String? accessToken;

  /// 앱 시작 시 한 번 호출 — 저장된 user_id를 메모리로 복원.
  static Future<void> loadFromStorage() async {
    final prefs = await SharedPreferences.getInstance();
    userId.value = prefs.getString(_kUserId);
    accessToken  = prefs.getString(_kToken);
  }

  static Future<void> setUser({required String id, String? token}) async {
    userId.value = id;
    accessToken  = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kUserId, id);
    if (token != null) await prefs.setString(_kToken, token);
  }

  static Future<void> logout() async {
    userId.value = null;
    accessToken  = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kUserId);
    await prefs.remove(_kToken);
  }
}
