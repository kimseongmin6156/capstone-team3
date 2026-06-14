import 'package:flutter/material.dart';

/// 앱 전체에서 쓰이는 색상 상수.
/// UI 코드에서는 항상 이 상수를 통해 색을 참조 (하드코드 금지).
///
/// 테마: White + Beige + Green (4단계 그린 포인트)
class AppColors {
  AppColors._();

  // === Brand / Primary (4단계 그린: 진한 → 연한) ===
  static const Color primary       = Color(0xFF2F5D37); // 1순위 진한 그린 (메인 포인트)
  static const Color primaryDark   = Color(0xFF1E3F23); // primary보다 진하게 (호버/누름 상태)
  static const Color primarySoft   = Color(0xFF436949); // 2순위 그린 (보조 강조)
  static const Color accent        = Color(0xFF517A58); // 3순위 그린 (강조/링크)
  static const Color accentLight   = Color(0xFF739B79); // 4순위 연한 그린 (서브 강조)

  // === Surface / Background ===
  static const Color background    = Color(0xFFEEEEEE); // 화면 배경 (베이지빛 회색)
  static const Color surface       = Color(0xFFFFFFFF); // 카드/표면 (배경과 대비되는 흰색)
  static const Color surfaceMuted  = Color(0xFFE0E0E0); // 박스 배경 (살짝 진하게)

  // === Borders / Dividers (베이지 톤) ===
  static const Color border        = Color(0xFFE6E0D2); // 입력창/카드 테두리 (베이지)
  static const Color borderStrong  = Color(0xFFD0C6B0); // 강조 테두리

  // === Text ===
  static const Color textPrimary   = Color(0xFF1F2421); // 본문 (거의 검정, 미세 그린 톤)
  static const Color textSecondary = Color(0xFF6B7280); // 보조 텍스트
  static const Color textMuted     = Color(0xFF9CA3AF); // 흐릿한 텍스트
  static const Color textOnPrimary = Color(0xFFFFFFFF); // 그린 배경 위 흰 글자

  // === Accent / Status ===
  static const Color success       = Color(0xFF16A34A); // 밝은 순수 그린 (브랜드와 구별)
  static const Color warning       = Color(0xFFD97706); // 호박색 (베이지와 조화)
  static const Color danger        = Color(0xFFB91C1C); // 차분한 빨강
}
