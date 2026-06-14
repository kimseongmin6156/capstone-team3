"""
입력 이미지를 YOLO로 크롭한 뒤 OpenCV로 색/모양/크기 특징 추출.

실행: 프로젝트 루트에서
  python debug_opencv/debug_opencv.py <이미지 경로>

출력 (debug_opencv/ 폴더):
  - dominant color (HSV → 색 이름)
  - shape: 원형/타원/캡슐/장방형
  - aspect ratio, circularity
  - <stem>_crop{i}.png         : YOLO 크롭
  - <stem>_crop{i}_opencv.png  : 원본 | 마스크 | 컨투어
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from ultralytics import YOLO

sys.path.append(str(Path(__file__).parent.parent))

YOLO_CKPT = Path("runs/detect/checkpoints/yolo/weights/best.pt")
OUT_DIR   = Path(__file__).parent


# HSV Hue 범위 → 색 이름 (S, V로 무채색 분기는 별도)
HUE_RANGES = [
    (  0,  10, "빨강"),
    ( 10,  25, "주황"),
    ( 25,  35, "노랑"),
    ( 35,  85, "초록"),
    ( 85, 125, "파랑"),
    (125, 145, "보라"),
    (145, 165, "분홍"),
    (165, 180, "빨강"),
]


def extract_foreground_mask(bgr: np.ndarray):
    """이미지에서 알약 마스크 추출. 중앙 = 알약이라는 가정 사용."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 중앙 영역이 검정이면 알약이 어두운 쪽 → 반전
    h, w = gray.shape
    cy1, cy2 = h // 2 - h // 6, h // 2 + h // 6
    cx1, cx2 = w // 2 - w // 6, w // 2 + w // 6
    if np.mean(thresh[cy1:cy2, cx1:cx2]) < 127:
        thresh = cv2.bitwise_not(thresh)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # 이미지 경계 전체를 잡는 컨투어 제외 (면적이 전체의 95% 이상)
    img_area = h * w
    contours = [c for c in contours if cv2.contourArea(c) < img_area * 0.95]
    if not contours:
        return np.zeros_like(gray), None

    largest = max(contours, key=cv2.contourArea)

    # 타원 피팅: 그림자/반사로 인한 비대칭 돌출 제거
    if len(largest) >= 5:
        area = cv2.contourArea(largest)
        peri = cv2.arcLength(largest, True)
        circ = 4 * np.pi * area / (peri ** 2) if peri > 0 else 0
        # 원/타원/장방형 등 둥근 계열일 때만 적용 (사각형은 제외)
        if circ > 0.65:
            ellipse = cv2.fitEllipse(largest)
            mask = np.zeros_like(gray)
            cv2.ellipse(mask, ellipse, 255, thickness=cv2.FILLED)
            refined, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if refined:
                return mask, max(refined, key=cv2.contourArea)

    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [largest], -1, 255, thickness=cv2.FILLED)
    return mask, largest


def dominant_color(bgr: np.ndarray, mask: np.ndarray) -> tuple:
    """마스크 영역의 HSV 중앙값으로 대표 색상 추정."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv[mask == 255]
    if len(pixels) == 0:
        return None, "알 수 없음"

    h_med = int(np.median(pixels[:, 0]))
    s_med = int(np.median(pixels[:, 1]))
    v_med = int(np.median(pixels[:, 2]))

    # 밝기 우선: 매우 밝고 채도가 적당히 낮으면 흰색 (크림빛 오프화이트 포함)
    if v_med > 220 and s_med < 80:
        name = "흰색"
    elif s_med < 60:
        if v_med > 200:
            name = "흰색"
        elif v_med < 60:
            name = "검정"
        else:
            name = "회색"
    else:
        name = next((n for lo, hi, n in HUE_RANGES if lo <= h_med < hi), "알 수 없음")
        if v_med < 70:
            name = f"진한 {name}"
        elif s_med < 100:
            name = f"연한 {name}"

    return (h_med, s_med, v_med), name


def shape_analysis(contour: np.ndarray) -> dict:
    """컨투어로 모양 분류."""
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0

    rect = cv2.minAreaRect(contour)
    (_, _), (w, h), _ = rect
    long_side, short_side = max(w, h), min(w, h)
    aspect = long_side / short_side if short_side > 0 else 0

    if circularity > 0.85 and aspect < 1.15:
        shape = "원형"
    elif aspect >= 1.8:
        shape = "장방형"
    elif circularity > 0.65 and aspect >= 1.15:
        shape = "타원형"
    elif 0.85 < aspect < 1.15:
        shape = "정사각/마름모"
    else:
        shape = "기타"

    return {
        "shape": shape,
        "aspect_ratio": round(aspect, 3),
        "circularity": round(circularity, 3),
        "long_side": int(long_side),
        "short_side": int(short_side),
        "area": int(area),
    }


def analyze_crop(bgr_crop: np.ndarray, stem: str, idx: int):
    """단일 크롭에 대해 OpenCV 분석 + 시각화 저장."""
    mask, contour = extract_foreground_mask(bgr_crop)
    if contour is None:
        print("  알약 컨투어를 찾지 못했습니다.")
        return

    hsv_med, color_name = dominant_color(bgr_crop, mask)
    shape_info = shape_analysis(contour)

    print(f"  [색상]  HSV 중앙값={hsv_med}  추정={color_name}")
    print(f"  [모양]  {shape_info['shape']}  "
          f"종횡비={shape_info['aspect_ratio']}  원형도={shape_info['circularity']}")
    print(f"  [크기]  장변/단변={shape_info['long_side']}/{shape_info['short_side']} px  "
          f"면적={shape_info['area']} px²")

    vis = bgr_crop.copy()
    cv2.drawContours(vis, [contour], -1, (0, 255, 0), 3)
    overlay = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    combined = np.hstack([bgr_crop, overlay, vis])
    out_path = OUT_DIR / f"{stem}_crop{idx}_opencv.png"
    cv2.imwrite(str(out_path), combined)
    print(f"  시각화: {out_path.name}")


def main(image_path: str):
    stem = Path(image_path).stem

    print(f"[1] YOLO 탐지: {image_path}")
    yolo = YOLO(str(YOLO_CKPT))
    results = yolo(image_path, verbose=False)[0]
    boxes = results.boxes
    print(f"    탐지 수: {len(boxes)}개")

    if len(boxes) == 0:
        return

    # EXIF 회전 적용해서 PIL로 로드 (YOLO와 좌표계 일치)
    orig_img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")

    print(f"\n[2] OpenCV 분석")
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = box.conf[0].item()

        crop_pil = orig_img.crop((x1, y1, x2, y2))
        crop_bgr = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)

        crop_path = OUT_DIR / f"{stem}_crop{i+1}.png"
        cv2.imwrite(str(crop_path), crop_bgr)

        print(f"\n  [알약 {i+1}]  YOLO conf={conf:.3f}  bbox=({x1},{y1})-({x2},{y2})")
        print(f"  크롭 저장: {crop_path.name}")
        analyze_crop(crop_bgr, stem, i + 1)


if __name__ == "__main__":
    main(sys.argv[1])
