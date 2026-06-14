"""
CNN 단독 분류 테스트.

실행: python debug_cnn.py <이미지 경로>
"""

import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from config import IMAGE_SIZE, MEAN, STD, DEVICE, CHECKPOINT_DIR
from src.model import PillClassifier
from src.preprocess import to_studio

CNN_CKPT = CHECKPOINT_DIR / "cnn_best.pt"

transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])


def main(image_path: str):
    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")

    ckpt = torch.load(CNN_CKPT, map_location=device)
    classes = ckpt["classes"]
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model = PillClassifier(num_classes=len(classes), use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"])
    model.to(device).eval()

    img_raw = Image.open(image_path).convert("RGB")
    img_processed = to_studio(img_raw)
    img_processed.save(Path(image_path).stem + "_cnn_input.png")

    for label, img in [("원본", img_raw), ("전처리", img_processed)]:
        tensor = transform(img).unsqueeze(0).to(device)
        with torch.no_grad():
            probs = F.softmax(model(tensor, None), dim=1).squeeze(0)

        top5 = probs.topk(5)
        print(f"\n[{label}] Top-5:")
        for prob, idx in zip(top5.values, top5.indices):
            print(f"  {classes[idx.item()]}  {prob.item()*100:.1f}%")


if __name__ == "__main__":
    main(sys.argv[1])
