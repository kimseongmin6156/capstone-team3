"""
전구색 → 자연광 White Balance 보정 샘플.

실행: 프로젝트 루트에서
  python sample_wb.py

저장: dataset/wb_sample.png  (원본 | 약하게 보정 | 강하게 보정 | Gray World)
"""

from pathlib import Path

import cv2
import numpy as np

INPUT  = Path("dataset/166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터/01.데이터/1.Training/원천데이터/단일경구약제_5000종/K-011354/K-011354_0_0_0_0_75_020_200.png")
OUTPUT = Path("dataset/wb_sample2.png")


def wb_manual(bgr: np.ndarray, b_gain: float, g_gain: float, r_gain: float) -> np.ndarray:
    """채널별 곱셈 보정 (OpenCV는 BGR 순서)."""
    out = bgr.astype(np.float32)
    out[:, :, 0] *= b_gain
    out[:, :, 1] *= g_gain
    out[:, :, 2] *= r_gain
    return np.clip(out, 0, 255).astype(np.uint8)


def wb_gray_world(bgr: np.ndarray) -> np.ndarray:
    """Gray World: 이미지 평균색이 회색이 되도록 자동 보정."""
    out  = bgr.astype(np.float32)
    mean = out.reshape(-1, 3).mean(axis=0)        # [meanB, meanG, meanR]
    gray = mean.mean()
    gains = gray / mean
    out *= gains
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    arr = np.fromfile(str(INPUT), dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        print(f"이미지 로드 실패: {INPUT}")
        return

    # 약하게: R-15%, B+10%
    mild   = wb_manual(bgr, b_gain=1.10, g_gain=1.00, r_gain=0.85)
    # 강하게: R-25%, B+25%
    strong = wb_manual(bgr, b_gain=1.25, g_gain=1.00, r_gain=0.75)
    # 자동: Gray World
    auto   = wb_gray_world(bgr)

    combined = np.hstack([bgr, mild, strong, auto])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUTPUT), combined)
    print(f"저장: {OUTPUT}")
    print("순서: 원본 | mild | strong | gray_world")


if __name__ == "__main__":
    main()
