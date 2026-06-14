"""OCR 전처리 + 다중 회전 EasyOCR."""

import cv2
import numpy as np


def _isolate(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return cv2.bitwise_and(bgr, bgr, mask=mask)


def preprocess_raw(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    isolated = _isolate(bgr, mask)
    h, w = isolated.shape[:2]
    return cv2.resize(isolated, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


def preprocess_mild(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    isolated = _isolate(bgr, mask)
    gray = cv2.cvtColor(isolated, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(16, 16))
    enhanced = clahe.apply(gray)
    h, w = enhanced.shape
    return cv2.resize(enhanced, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


def preprocess_strong(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
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


def run_ocr_multi_rotation(reader, img: np.ndarray) -> dict:
    """0/90/180/270도 회전 OCR. 평균 신뢰도 최고 결과 반환."""
    best = {"text": "", "conf": 0.0, "rotation": 0}
    for angle in (0, 90, 180, 270):
        rotated = np.rot90(img, k=angle // 90)
        results = reader.readtext(
            rotated, detail=1, paragraph=False,
            text_threshold=0.5, low_text=0.3,
        )
        if not results:
            continue
        avg_conf = sum(c for _, _, c in results) / len(results)
        if avg_conf > best["conf"]:
            best = {
                "text": " ".join(t for _, t, _ in results),
                "conf": avg_conf,
                "rotation": angle,
            }
    return best


def extract_text(reader, bgr: np.ndarray, mask: np.ndarray) -> dict:
    """3가지 전처리 × 4방향 회전 중 최고 신뢰도 결과 반환."""
    best = {"text": "", "conf": 0.0, "rotation": 0, "mode": None}
    for mode, fn in PREPROCESSORS.items():
        ocr_input = fn(bgr, mask)
        result = run_ocr_multi_rotation(reader, ocr_input)
        if result["conf"] > best["conf"]:
            best = {**result, "mode": mode}
    return best
