import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from config import IMAGE_SIZE, MEAN, STD, THRESHOLD_CONFIDENT, THRESHOLD_CANDIDATE, DEVICE
from src.model import PillClassifier


def load_model(checkpoint_path: str):
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    classes = ckpt["classes"]
    num_classes = len(classes)
    # head.0.weight shape: (512, 1792) → no metadata, (512, 1817) → with metadata
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model = PillClassifier(num_classes=num_classes, use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, classes, use_metadata


transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])


def predict(model, image_path: str, classes: list, device: torch.device, use_metadata: bool = False, meta: list = None):
    image = Image.open(image_path).convert("RGB")
    image = transform(image).unsqueeze(0).to(device)

    if use_metadata:
        meta_vec = meta if meta is not None else [0.0] * 25
        meta_t = torch.tensor(meta_vec, dtype=torch.float32).unsqueeze(0).to(device)
    else:
        meta_t = None

    with torch.no_grad():
        logits = model(image, meta_t)
        probs  = F.softmax(logits, dim=1).squeeze(0)

    top_prob, top_idx = probs.max(0)
    top_prob = top_prob.item()

    # 확정 출력
    if top_prob >= THRESHOLD_CONFIDENT:
        return {
            "status": "confident",
            "prediction": classes[top_idx],
            "probability": round(top_prob, 4),
            "candidates": [],
        }

    # 후보 출력 (0.3 이상인 클래스 모두)
    candidates = [
        {"class": classes[i], "probability": round(probs[i].item(), 4)}
        for i in range(len(classes))
        if probs[i].item() >= THRESHOLD_CANDIDATE
    ]
    candidates.sort(key=lambda x: x["probability"], reverse=True)

    if candidates:
        return {
            "status": "candidates",
            "prediction": None,
            "probability": None,
            "candidates": candidates,
        }

    return {
        "status": "unknown",
        "prediction": None,
        "probability": None,
        "candidates": [],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="알약 이미지 경로")
    parser.add_argument("--checkpoint", default="checkpoints/best.pt")
    args = parser.parse_args()

    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")
    model, classes, use_metadata = load_model(args.checkpoint)
    model = model.to(device)

    result = predict(model, args.image, classes, device, use_metadata)

    if result["status"] == "confident":
        print(f"[확정] {result['prediction']}  ({result['probability']*100:.1f}%)")
    elif result["status"] == "candidates":
        print("[후보]")
        for c in result["candidates"]:
            print(f"  {c['class']}  ({c['probability']*100:.1f}%)")
    else:
        print("[미확인] 신뢰도 30% 이상인 후보 없음")
