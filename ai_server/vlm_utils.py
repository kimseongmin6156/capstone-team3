"""Together AI VLM 기반 OCR (EasyOCR 대체).

YOLO로 잘라낸 알약 이미지를 Together AI 비전 모델에 보내 각인 텍스트를 추출.
"""

import base64

import cv2
import numpy as np
import requests

from .config import (
    TOGETHER_API_KEY,
    TOGETHER_API_URL,
    TOGETHER_VLM_MODEL,
    VLM_OCR_PROMPT,
)


def _bgr_to_png_b64(bgr: np.ndarray) -> str:
    """OpenCV BGR ndarray → PNG base64 문자열."""
    success, encoded = cv2.imencode(".png", bgr)
    if not success:
        raise RuntimeError("PNG 인코딩 실패")
    return base64.b64encode(encoded.tobytes()).decode("utf-8")


def _apply_mask(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """알약 마스크 적용 — 배경을 검정으로 채워 VLM이 알약에만 집중하도록."""
    return cv2.bitwise_and(bgr, bgr, mask=mask)


def vlm_extract_text(bgr: np.ndarray, mask: np.ndarray | None = None) -> dict:
    """알약 크롭에서 VLM으로 각인 텍스트 추출.

    Returns:
        {"text": str, "conf": float, "mode": str}
        - 텍스트 인식 성공: conf=1.0
        - 텍스트 없음(NONE): conf=0.0
        - 호출 실패/API 키 없음: conf=0.0, mode에 에러 표시
    """
    if not TOGETHER_API_KEY:
        return {"text": "", "conf": 0.0, "mode": "vlm-no-api-key"}

    img = _apply_mask(bgr, mask) if mask is not None else bgr
    b64 = _bgr_to_png_b64(img)

    try:
        resp = requests.post(
            TOGETHER_API_URL,
            headers={
                "Authorization": f"Bearer {TOGETHER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TOGETHER_VLM_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VLM_OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()

        # "NONE" 응답이면 텍스트 없음으로 처리
        if text.upper().strip() in ("NONE", "NONE.", "'NONE'"):
            return {"text": "", "conf": 0.0, "mode": "vlm"}
        return {"text": text, "conf": 1.0, "mode": "vlm"}
    except requests.exceptions.RequestException as e:
        return {"text": "", "conf": 0.0, "mode": f"vlm-error: {e}"}
    except (KeyError, IndexError) as e:
        return {"text": "", "conf": 0.0, "mode": f"vlm-parse-error: {e}"}
