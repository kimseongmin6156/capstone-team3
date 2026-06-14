"""
YOLO → CNN 전체 파이프라인 추론.

실행: 프로젝트 루트에서
  python pipeline.py dataset/test_data.jpg          # 전처리 적용 (기본)
  python pipeline.py dataset/test_data.jpg --raw    # 전처리 없이 원본 크롭
"""

import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision import transforms
from ultralytics import YOLO

from config import (
    IMAGE_SIZE, MEAN, STD,
    THRESHOLD_CONFIDENT, THRESHOLD_CANDIDATE,
    DEVICE, CHECKPOINT_DIR,
)
from src.model import PillClassifier
from src.preprocess import to_studio

YOLO_CKPT = Path("runs/detect/checkpoints/yolo/weights/best.pt")
CNN_CKPT  = CHECKPOINT_DIR / "cnn_best.pt"

transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])


def pad_square(img: Image.Image) -> Image.Image:
    """비율 보존을 위해 검정 배경으로 정사각형 패딩."""
    w, h = img.size
    if w == h:
        return img
    size = max(w, h)
    result = Image.new("RGB", (size, size), (0, 0, 0))
    result.paste(img, ((size - w) // 2, (size - h) // 2))
    return result


def load_cnn(checkpoint_path: Path, device):
    ckpt        = torch.load(checkpoint_path, map_location=device)
    classes     = ckpt["classes"]
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model       = PillClassifier(num_classes=len(classes), use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"])
    model.to(device).eval()
    return model, classes


def classify(model, crop: Image.Image, classes: list, device):
    img    = transform(crop).unsqueeze(0).to(device)
    with torch.no_grad():
        probs = F.softmax(model(img, None), dim=1).squeeze(0)

    top_prob = probs.max().item()
    top_idx  = probs.argmax().item()

    if top_prob >= THRESHOLD_CONFIDENT:
        return {"status": "confident", "prediction": classes[top_idx], "probability": round(top_prob, 4), "candidates": []}

    candidates = [
        {"class": classes[i], "probability": round(probs[i].item(), 4)}
        for i in range(len(classes)) if probs[i].item() >= THRESHOLD_CANDIDATE
    ]
    candidates.sort(key=lambda x: x["probability"], reverse=True)

    if candidates:
        return {"status": "candidates", "prediction": None, "probability": None, "candidates": candidates}

    return {"status": "unknown", "prediction": None, "probability": None, "candidates": []}


def run(image_path: str, preprocess: bool = False, debug: bool = False):
    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")

    print(f"YOLO 모델 로드: {YOLO_CKPT}")
    yolo = YOLO(str(YOLO_CKPT))

    print(f"CNN 모델 로드: {CNN_CKPT}")
    cnn, classes = load_cnn(CNN_CKPT, device)

    mode = "스튜디오 전처리" if preprocess else "원본 크롭"
    print(f"\n이미지 분석: {image_path}  [{mode}]\n")
    results = yolo(image_path, verbose=False)[0]
    boxes   = results.boxes

    if len(boxes) == 0:
        print("알약을 탐지하지 못했습니다.")
        return

    print(f"탐지된 알약 수: {len(boxes)}개\n")
    orig_img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")

    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = box.conf[0].item()

        crop = orig_img.crop((x1, y1, x2, y2))
        crop = pad_square(crop)

        if debug:
            raw_path = Path(image_path).stem + f"_crop{i+1}_raw.png"
            crop.save(raw_path)
            print(f"  [DEBUG] 원본 크롭 저장: {raw_path}")

        if preprocess:
            crop = to_studio(crop)

        if debug:
            debug_path = Path(image_path).stem + f"_crop{i+1}_preprocessed.png"
            crop.save(debug_path)
            print(f"  [DEBUG] 전처리 크롭 저장: {debug_path}")

        result = classify(cnn, crop, classes, device)

        print(f"[알약 {i+1}]  YOLO 신뢰도: {conf:.3f}  bbox: ({x1},{y1})-({x2},{y2})")
        if result["status"] == "confident":
            print(f"  → [확정] {result['prediction']}  ({result['probability']*100:.1f}%)")
        elif result["status"] == "candidates":
            print(f"  → [후보]")
            for c in result["candidates"]:
                print(f"       {c['class']}  ({c['probability']*100:.1f}%)")
        else:
            print(f"  → [미확인] 신뢰도 30% 이상 후보 없음")
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="알약 사진 경로")
    parser.add_argument("--preprocess", action="store_true", help="스튜디오 전처리 적용 (tighten_crop + CLAHE)")
    parser.add_argument("--debug",      action="store_true", help="크롭 이미지 저장")
    args = parser.parse_args()
    run(args.image, preprocess=args.preprocess, debug=args.debug)
