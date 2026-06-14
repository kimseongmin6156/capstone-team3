"""YOLO 크롭 → CNN/OpenCV/VLM(OCR) 통합 추론."""

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps

from .config import CNN_TOPK, THRESHOLD_CONFIDENT, THRESHOLD_CANDIDATE
from .cv_utils import analyze_pill
from .models import registry
from .ocr_utils import extract_text
from .scoring import rerank_candidates
from .vlm_utils import vlm_extract_text


def pad_square(img: Image.Image) -> Image.Image:
    """비율 보존을 위해 검정 배경으로 정사각형 패딩."""
    w, h = img.size
    if w == h:
        return img
    size = max(w, h)
    result = Image.new("RGB", (size, size), (0, 0, 0))
    result.paste(img, ((size - w) // 2, (size - h) // 2))
    return result


def cnn_topk(pil_crop: Image.Image, k: int = CNN_TOPK) -> list[str]:
    """CNN Top-K 후보 K-코드 리스트 반환 (확률은 점수에 사용 안 함)."""
    squared = pad_square(pil_crop)
    tensor = registry.transform(squared).unsqueeze(0).to(registry.device)
    with torch.no_grad():
        probs = F.softmax(registry.cnn(tensor, None), dim=1).squeeze(0)
    topk = probs.topk(k)
    return [registry.cnn_classes[idx.item()] for idx in topk.indices]


def analyze_pill_full(pil_crop: Image.Image) -> dict:
    """단일 알약 크롭에 대해 CNN/OpenCV/OCR 모두 실행 후 통합 점수로 결정."""
    crop_bgr = cv2.cvtColor(np.array(pil_crop), cv2.COLOR_RGB2BGR)

    # 1) CNN Top-K
    candidates = cnn_topk(pil_crop)

    # 2) OpenCV (마스크 + 색 + 모양)
    cv_result = analyze_pill(crop_bgr)
    color_name = cv_result["color_name"]
    shape      = cv_result["shape"]
    mask       = cv_result["mask"]

    # 3) 텍스트 추출: VLM 우선 → 실패 시 EasyOCR fallback
    ocr_text = ""
    if mask is not None and np.sum(mask) > 0:
        vlm = vlm_extract_text(crop_bgr, mask)
        if vlm["mode"] == "vlm":
            ocr_text = vlm["text"]
        else:
            # VLM 실패 (timeout/에러/API 키 없음) → EasyOCR fallback
            ocr = extract_text(registry.easyocr_reader, crop_bgr, mask)
            ocr_text = ocr["text"]

    # 4) 재랭킹
    scored = rerank_candidates(
        candidates, registry.metadata, color_name, shape, ocr_text,
    )

    return {
        "scored":     scored,        # list of {drug_code, score, color, shape, ocr}
        "color":      color_name,
        "shape":      shape,
        "ocr_text":   ocr_text,
        "cnn_topk":   candidates,
    }


def decide_status(scored: list[dict]) -> tuple[str, str | None, float | None, list[dict]]:
    """재랭킹 결과에서 status/drug_code/confidence/candidates 결정."""
    if not scored:
        return "unknown", None, None, []

    top = scored[0]
    top_score = top["score"]

    candidates = [
        {"drug_code": s["drug_code"], "confidence": round(s["score"], 4)}
        for s in scored if s["score"] >= THRESHOLD_CANDIDATE
    ]

    if top_score >= THRESHOLD_CONFIDENT:
        return "confident", top["drug_code"], round(top_score, 4), candidates

    if candidates:
        # 후보가 있으면 최상위 후보를 drug_code로 반환 (백엔드가 활용 가능하도록)
        return "candidates", top["drug_code"], round(top_score, 4), candidates

    return "unknown", None, None, []


def run_inference(image_bytes: bytes) -> dict:
    """전체 파이프라인. 백엔드에서 받은 이미지 바이트를 처리해 계약 형식으로 반환."""
    import io
    pil = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")

    yolo_results = registry.yolo(pil, verbose=False)[0]
    boxes = yolo_results.boxes
    if len(boxes) == 0:
        return {"count": 0, "results": []}

    pill_results = []
    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        crop = pil.crop((x1, y1, x2, y2))

        info = analyze_pill_full(crop)
        status, drug_code, confidence, candidates = decide_status(info["scored"])

        pill_results.append({
            "drug_code":  drug_code,
            "confidence": confidence,
            "status":     status,
            "candidates": candidates,
        })

    return {"count": len(pill_results), "results": pill_results}
