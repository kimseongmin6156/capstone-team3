"""
실제 촬영 이미지를 스튜디오 학습 데이터처럼 전처리.

tighten_crop : YOLO의 느슨한 bbox 내에서 밝은 물체(알약)를 찾아 타이트하게 재크롭
to_studio    : CLAHE로 조명 정규화
"""

import cv2
import numpy as np
from PIL import Image


def tighten_crop(crop: Image.Image, padding: float = 0.15, thresh_val: int = 60) -> Image.Image:
    """
    어두운 배경에서 밝은 알약을 찾아 타이트하게 재크롭.
    - thresh_val: 이 밝기 이상인 픽셀을 전경(알약)으로 판단
    - padding: 알약 bbox 주변 여백 비율
    """
    arr = np.array(crop.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

    # 노이즈 제거
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return crop

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    h_img, w_img = arr.shape[:2]
    pad_x = int(w * padding)
    pad_y = int(h * padding)
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w_img, x + w + pad_x)
    y2 = min(h_img, y + h + pad_y)

    return Image.fromarray(arr[y1:y2, x1:x2])


def to_studio(crop: Image.Image) -> Image.Image:
    """YOLO 크롭 → 타이트 재크롭 → CLAHE 조명 정규화."""
    tightened = tighten_crop(crop)
    return _clahe_rgb(tightened)


def _clahe_rgb(img: Image.Image) -> Image.Image:
    """LAB 공간에서 L 채널에 CLAHE 적용 → 조명 편차 완화."""
    arr = np.array(img)
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    return Image.fromarray(out)
