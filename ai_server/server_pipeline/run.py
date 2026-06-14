"""AI 서버 파이프라인 단독 실행 (FastAPI 없이 CLI로).

ai_server의 모듈을 그대로 재사용하면서 각 단계 결과를 상세 출력.

실행: 프로젝트 루트에서
  python ai_server/server_pipeline/run.py <이미지 경로>

예:
  python ai_server/server_pipeline/run.py test_images/030590_white.jpg
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from ai_server.config import (
    THRESHOLD_CONFIDENT, THRESHOLD_CANDIDATE, CNN_TOPK,
)
from ai_server.cv_utils import analyze_pill
from ai_server.inference import pad_square
from ai_server.models import registry
from ai_server.vlm_utils import vlm_extract_text
from ai_server.scoring import rerank_candidates, W_OCR, W_COLOR, W_SHAPE


def fmt_meta(meta: dict) -> str:
    if not meta:
        return "(메타데이터 없음)"
    parts = []
    colors = list(meta.get("color_class1", {}).keys()) if isinstance(meta.get("color_class1"), dict) else meta.get("color_class1", [])
    shapes = list(meta.get("drug_shape", {}).keys()) if isinstance(meta.get("drug_shape"), dict) else meta.get("drug_shape", [])
    prints = meta.get("print_front", [])
    if colors: parts.append(f"색={colors}")
    if shapes: parts.append(f"모양={shapes}")
    if prints: parts.append(f"각인={prints}")
    return "  ".join(parts) if parts else "(빈 메타데이터)"


def main(image_path: str):
    print("=" * 70)
    print(f"  AI Server Pipeline 단독 실행")
    print("=" * 70)
    print(f"입력 이미지: {image_path}")

    print(f"\n[1] 모델 로딩...")
    registry.load()
    print(f"    device={registry.device}, CNN classes={len(registry.cnn_classes)}, "
          f"metadata 등록 K-코드={len(registry.metadata)}")

    print(f"\n[2] 이미지 디코드 + EXIF 회전")
    pil = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    print(f"    크기: {pil.size}")

    print(f"\n[3] YOLO 탐지")
    yolo_results = registry.yolo(pil, verbose=False)[0]
    boxes = yolo_results.boxes
    print(f"    탐지 수: {len(boxes)}")

    if len(boxes) == 0:
        print("\n결과: {'count': 0, 'results': []}")
        return

    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        yolo_conf = box.conf[0].item()
        w, h = x2 - x1, y2 - y1
        print(f"\n{'=' * 70}")
        print(f"  [알약 {i+1}]  YOLO conf={yolo_conf:.3f}  bbox=({x1},{y1})-({x2},{y2})  크기={w}x{h}")
        print(f"{'=' * 70}")

        crop = pil.crop((x1, y1, x2, y2))
        crop_bgr = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)

        # ---- CNN Top-K ----
        squared = pad_square(crop)
        tensor = registry.transform(squared).unsqueeze(0).to(registry.device)
        with torch.no_grad():
            probs = F.softmax(registry.cnn(tensor, None), dim=1).squeeze(0)
        topk = probs.topk(CNN_TOPK)
        cnn_codes = [registry.cnn_classes[idx.item()] for idx in topk.indices]
        cnn_probs = [p.item() for p in topk.values]

        print(f"\n  [CNN] Top-{CNN_TOPK} (확률은 점수에 미사용)")
        for code, p in zip(cnn_codes, cnn_probs):
            print(f"    {code}  {p*100:6.2f}%")

        # ---- OpenCV ----
        cv_result = analyze_pill(crop_bgr)
        color = cv_result["color_name"]
        shape = cv_result["shape"]
        mask = cv_result["mask"]
        print(f"\n  [OpenCV]")
        print(f"    색상: {color}  HSV={cv_result['hsv']}")
        print(f"    모양: {shape}")

        # ---- VLM OCR (Together AI) ----
        ocr_text = ""
        if mask is not None and np.sum(mask) > 0:
            vlm = vlm_extract_text(crop_bgr, mask)
            ocr_text = vlm["text"]
            print(f"\n  [VLM]  텍스트=\"{ocr_text}\"  conf={vlm['conf']:.3f}  "
                  f"mode={vlm['mode']}")
        else:
            print(f"\n  [VLM]  마스크 없어 스킵")

        # ---- 재랭킹 ----
        scored = rerank_candidates(cnn_codes, registry.metadata, color, shape, ocr_text)

        print(f"\n  [재랭킹]  weights: OCR={W_OCR}, 색={W_COLOR}, 모양={W_SHAPE}")
        print(f"    {'후보':<12} {'점수':>6}  {'색':>4}  {'모양':>4}  {'OCR':>5}   메타")
        for s in scored:
            meta = registry.metadata.get(s["drug_code"], {})
            print(f"    {s['drug_code']:<12} {s['score']:>6.3f}  "
                  f"{s['color']:>4.2f}  {s['shape']:>4.2f}  {s['ocr']:>5.3f}   {fmt_meta(meta)}")

        # ---- 결정 ----
        top = scored[0]
        if top["score"] >= THRESHOLD_CONFIDENT:
            status = "confident"
        elif top["score"] >= THRESHOLD_CANDIDATE:
            status = "candidates"
        else:
            status = "unknown"

        print(f"\n  ▶ 결과: status={status}")
        print(f"    drug_code={top['drug_code']}  score={top['score']:.4f}")
        if status == "unknown":
            print(f"    → 최고 점수가 임계값({THRESHOLD_CANDIDATE}) 미만이라 unknown")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python ai_server/server_pipeline/run.py <이미지 경로>")
        sys.exit(1)
    main(sys.argv[1])
