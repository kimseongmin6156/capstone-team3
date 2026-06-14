"""OpenCV로 알약 마스크 추출 및 색/모양 분석."""

import cv2
import numpy as np

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
    """가장 큰 컨투어를 전경(알약)으로 마스크 추출. 타원형이면 타원 피팅 적용."""
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
        return np.zeros_like(gray), None

    largest = max(contours, key=cv2.contourArea)
    if len(largest) >= 5:
        area = cv2.contourArea(largest)
        peri = cv2.arcLength(largest, True)
        circ = 4 * np.pi * area / (peri ** 2) if peri > 0 else 0
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


def dominant_color(bgr: np.ndarray, mask: np.ndarray) -> tuple[tuple[int, int, int] | None, str]:
    """마스크 영역의 HSV 중앙값으로 대표 색상 추정."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv[mask == 255]
    if len(pixels) == 0:
        return None, "알 수 없음"

    h_med = int(np.median(pixels[:, 0]))
    s_med = int(np.median(pixels[:, 1]))
    v_med = int(np.median(pixels[:, 2]))

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
    }


def analyze_pill(bgr: np.ndarray) -> dict:
    """알약 크롭에서 색·모양 추출. 마스크도 함께 반환(OCR에서 재사용)."""
    mask, contour = extract_foreground_mask(bgr)
    if contour is None:
        return {"mask": None, "color_name": None, "shape": None, "hsv": None}

    hsv, color_name = dominant_color(bgr, mask)
    shape = shape_analysis(contour)
    return {
        "mask":       mask,
        "color_name": color_name,
        "shape":      shape["shape"],
        "hsv":        hsv,
    }
