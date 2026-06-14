/// API 서버 주소 (전역). 환경에 따라 한 곳만 바꾸세요.
///
/// 로컬 PC에서 개발: 'http://127.0.0.1:8000'
/// 같은 와이파이에서 핸드폰/타 기기로 접속: 'http://<PC_IP>:8000'
///   PC IP는 PowerShell에서 `ipconfig` 실행 → "IPv4 주소" 확인 (예: 192.168.0.42)
/// 배포: 'https://your-domain.com'
///
/// 빌드 시 --dart-define=API_BASE=http://192.168.0.42:8000 로 오버라이드 가능.
class ApiConfig {
  ApiConfig._();

  static const String apiBase = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'http://127.0.0.1:8000',
  );

  /// 외부 이미지 URL을 백엔드 프록시 경유 URL로 변환.
  /// (Flutter Web의 CanvasKit이 CORS 미허용 이미지를 못 그리는 문제 우회)
  static String proxyImage(String? url) {
    if (url == null || url.isEmpty) return '';
    return '$apiBase/api/image-proxy?url=${Uri.encodeQueryComponent(url)}';
  }
}
