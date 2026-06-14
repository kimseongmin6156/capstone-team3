import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class BottomNavBar extends StatelessWidget {
  final int currentIndex;

  const BottomNavBar({Key? key, required this.currentIndex}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface.withValues(alpha: 0.95),
        border: Border(
          top: BorderSide(color: AppColors.primary.withValues(alpha: 0.1), width: 0.5),
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildNavItem(context, Icons.home, '홈', 0, '/home'),
              _buildNavItem(context, Icons.search, '검색', 1, '/search'),
              _buildNavItem(context, Icons.camera_alt, '스캔', 2, '/scan'),
              _buildNavItem(context, Icons.medication, '알약', 3, '/my-pills'),
              _buildNavItem(context, Icons.person, 'MY', 4, '/profile'),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(
    BuildContext context,
    IconData icon,
    String label,
    int index,
    String route,
  ) {
    final isActive = currentIndex == index;

    return Expanded(
      child: GestureDetector(
        onTap: () {
          if (!isActive) {
            Navigator.pushReplacementNamed(context, route);
          }
        },
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 26,
              color: isActive ? AppColors.primarySoft : AppColors.textSecondary,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: isActive ? FontWeight.w500 : FontWeight.normal,
                color: isActive ? AppColors.primarySoft : AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
