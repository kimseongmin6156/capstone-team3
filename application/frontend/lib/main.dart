import 'package:flutter/material.dart';
import 'screens/signup_page.dart';
import 'screens/login_page.dart';
import 'screens/home_page.dart';
import 'screens/search_page.dart';
import 'screens/scan_page.dart';
import 'screens/analysis_page.dart';
import 'screens/chatbot_page.dart';
import 'screens/profile_page.dart';
import 'screens/my_pills_page.dart';
import 'state/my_pills_store.dart';
import 'state/user_store.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // 저장된 user_id 복원 (페이지 새로고침 후에도 로그인 유지)
  await UserStore.loadFromStorage();
  if (UserStore.userId.value != null) {
    // user_pills도 미리 로드
    await MyPillsStore.refresh();
  }
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loggedIn = UserStore.userId.value != null;
    return MaterialApp(
      title: '이게 머약',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      initialRoute: loggedIn ? '/home' : '/',
      routes: {
        '/': (context) => const SignupPage(),
        '/login': (context) => const LoginPage(),
        '/home': (context) => const HomePage(),
        '/search': (context) => const SearchPage(),
        '/scan': (context) => const ScanPage(),
        '/analysis': (context) => const AnalysisPage(),
        '/chatbot': (context) => const ChatbotPage(),
        '/profile': (context) => const ProfilePage(),
        '/my-pills': (context) => const MyPillsPage(),
      },
    );
  }
}
