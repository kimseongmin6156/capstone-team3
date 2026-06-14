"""
알약 각인 OCR 디버깅.

YOLO 크롭 → OpenCV 마스크 → 강한 전처리 → EasyOCR (4방향 회전)

실행: 프로젝트 루트에서
  python debug_ocr/debug_ocr.py <이미지 경로>

저장 (debug_ocr/ 폴더):
  <stem>_crop{i}.png        : YOLO 크롭
  <stem>_crop{i}_ocr_in.png : OCR에 실제로 들어간 전처리 이미지
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


# ------------------------------------------------------------------
# OpenCV 전경 마스크 (debug_opencv.py와 동일 로직)
# ------------------------------------------------------------------
def extract_foreground_mask(bgr: np.ndarray):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    h, w = gray.shape
    cy1, cy2 = h // 2 - h // 6, h // 2 + h // 6
    cx1, cx2 = w // 2 - w // 6, w // 2 + w // 6
    if np.mean(thresh[cy1:cy2, cx1:cx2]) < 127:
        thresh = cv2.bitwise_not(thresh)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = h * w
    contours = [c for c in contours if cv2.contourArea(c) < img_area * 0.95]
    if not contours:
        return np.zeros_like(gray)

    largest = max(contours, key=cv2.contourArea)
    if len(largest) >= 5:
        area = cv2.contourArea(largest)
        peri = cv2.arcLength(largest, True)
        circ = 4 * np.pi * area / (peri ** 2) if peri > 0 else 0
        if circ > 0.65:
            ellipse = cv2.fitEllipse(largest)
            mask = np.zeros_like(gray)
            cv2.ellipse(mask, ellipse, 255, thickness=cv2.FILLED)
            return mask

    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [largest], -1, 255, thickness=cv2.FILLED)
    return mask


# ------------------------------------------------------------------
# OCR 전처리 (3가지 강도)
# ------------------------------------------------------------------
def _isolate(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return cv2.bitwise_and(bgr, bgr, mask=mask)


def preprocess_raw(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """원본 + 마스크만 적용 + 업스케일."""
    isolated = _isolate(bgr, mask)
    h, w = isolated.shape[:2]
    return cv2.resize(isolated, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


def preprocess_mild(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """약한 CLAHE만 적용 (반사가 강한 연질 캡슐용)."""
    isolated = _isolate(bgr, mask)
    gray = cv2.cvtColor(isolated, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(16, 16))
    enhanced = clahe.apply(gray)
    h, w = enhanced.shape
    return cv2.resize(enhanced, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


def preprocess_strong(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """강한 CLAHE + 샤프닝 (저대비 음각 정제용)."""
    isolated = _isolate(bgr, mask)
    gray = cv2.cvtColor(isolated, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blur = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=3)
    sharpened = cv2.addWeighted(enhanced, 1.8, blur, -0.8, 0)
    h, w = sharpened.shape
    return cv2.resize(sharpened, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


PREPROCESSORS = {
    "raw":    preprocess_raw,
    "mild":   preprocess_mild,
    "strong": preprocess_strong,
}


def run_ocr_multi_rotation(reader, img: np.ndarray):
    """0/90/180/270도 회전 OCR. 임계값 완화. 신뢰도 최고 결과 반환."""
    best = {"text": "", "conf": 0.0, "rotation": 0, "all": []}
    for angle in (0, 90, 180, 270):
        rotated = np.rot90(img, k=angle // 90)
        results = reader.readtext(
            rotated, detail=1, paragraph=False,
            text_threshold=0.5, low_text=0.3,
        )
        if not results:
            continue
        avg_conf = sum(c for _, _, c in results) / len(results)
        texts = [t for _, t, _ in results]
        if avg_conf > best["conf"]:
            best = {
                "text": " ".join(texts),
                "conf": avg_conf,
                "rotation": angle,
                "all": [(t, round(c, 3)) for _, t, c in results],
            }
    return best


# ------------------------------------------------------------------
# 메인
# ------------------------------------------------------------------
def main(image_path: str):
    stem = Path(image_path).stem
    save_dir = OUT_DIR / stem
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1] YOLO 탐지: {image_path}")
    print(f"    저장 폴더: {save_dir}")
    yolo = YOLO(str(YOLO_CKPT))
    results = yolo(image_path, verbose=False)[0]
    boxes = results.boxes
    print(f"    탐지 수: {len(boxes)}개")

    if len(boxes) == 0:
        return

    orig_img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")

    print(f"\n[2] EasyOCR 로드 (최초 1회 모델 다운로드)")
    import easyocr
    reader = easyocr.Reader(['en'], gpu=True)

    print(f"\n[3] 각인 OCR")
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = box.conf[0].item()

        crop_pil = orig_img.crop((x1, y1, x2, y2))
        crop_bgr = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(save_dir / f"crop{i+1}.png"), crop_bgr)

        mask = extract_foreground_mask(crop_bgr)
        if np.sum(mask) == 0:
            print(f"\n  [알약 {i+1}] 마스크 추출 실패")
            continue

        print(f"\n  [알약 {i+1}]  YOLO conf={conf:.3f}  bbox=({x1},{y1})-({x2},{y2})")

        # 3가지 전처리 × 4방향 회전 → 신뢰도 최고 채택
        best_overall = {"text": "", "conf": 0.0, "rotation": 0, "all": [], "mode": None}
        for mode, fn in PREPROCESSORS.items():
            ocr_input = fn(crop_bgr, mask)
            cv2.imwrite(str(save_dir / f"crop{i+1}_ocr_in_{mode}.png"), ocr_input)
            result = run_ocr_multi_rotation(reader, ocr_input)
            print(f"    [{mode:>6}]  텍스트=\"{result['text']}\"  rot={result['rotation']}  conf={result['conf']:.3f}")
            if result["conf"] > best_overall["conf"]:
                best_overall = {**result, "mode": mode}

        if not best_overall["all"]:
            print(f"    → 텍스트 감지 실패")
            continue
        print(f"    → 최종: \"{best_overall['text']}\"  (mode={best_overall['mode']}, rot={best_overall['rotation']}, conf={best_overall['conf']:.3f})")
        result = best_overall
        print(f"    개별 항목:")
        for text, c in result["all"]:
            print(f"      \"{text}\"  ({c})")


if __name__ == "__main__":
    main(sys.argv[1])
