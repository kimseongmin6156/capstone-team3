import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// 약품 카테고리 라벨 배지 (예: "해열진통제", "소화제").
class CategoryBadge extends StatelessWidget {
  final String text;
  const CategoryBadge({Key? key, required this.text}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.accent.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.accent.withValues(alpha: 0.3)),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: AppColors.primarySoft,
        ),
      ),
    );
  }
}
