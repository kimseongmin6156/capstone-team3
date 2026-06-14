"""
assets/logo.png 한 장으로 PWA 아이콘 세트 일괄 생성.

생성 파일 (web/icons/, web/):
  Icon-192.png             — 일반 192x192
  Icon-512.png             — 일반 512x512
  Icon-maskable-192.png    — Android maskable (안전 영역 padding 추가)
  Icon-maskable-512.png    — Android maskable 512
  ../favicon.png           — 브라우저 탭 아이콘 32x32

실행 (application/frontend 폴더에서):
  python generate_pwa_icons.py
"""

from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
SRC  = BASE / "assets" / "logo.png"
ICONS_DIR = BASE / "web" / "icons"
WEB_DIR   = BASE / "web"


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    """logo.png를 size×size 캔버스에 맞춰 생성. maskable이면 80% 안전 영역."""
    src = Image.open(SRC).convert("RGBA")

    # 정사각형으로 패딩 (긴 쪽 기준 흰 배경)
    w, h = src.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 255))
    canvas.paste(src, ((side - w) // 2, (side - h) // 2), src)

    # maskable: 80% 영역에 축소 배치 (Android가 원형 마스킹해도 안 잘림)
    if maskable:
        inner_size = int(size * 0.8)
        resized = canvas.resize((inner_size, inner_size), Image.LANCZOS)
        out = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        off = (size - inner_size) // 2
        out.paste(resized, (off, off), resized)
        return out
    return canvas.resize((size, size), Image.LANCZOS)


def main():
    if not SRC.exists():
        raise FileNotFoundError(f"원본이 없습니다: {SRC}")
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    targets = [
        (ICONS_DIR / "Icon-192.png",          192, False),
        (ICONS_DIR / "Icon-512.png",          512, False),
        (ICONS_DIR / "Icon-maskable-192.png", 192, True),
        (ICONS_DIR / "Icon-maskable-512.png", 512, True),
        (WEB_DIR / "favicon.png",              32, False),
    ]
    for path, size, maskable in targets:
        img = make_icon(size, maskable)
        img.convert("RGB").save(path, "PNG", optimize=True)
        print(f"생성: {path.relative_to(BASE)}  ({size}x{size})")

    print("\n완료 — flutter build web 다시 실행하세요.")


if __name__ == "__main__":
    main()
