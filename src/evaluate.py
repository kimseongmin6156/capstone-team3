import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms
from tqdm import tqdm

from config import IMAGE_SIZE, MEAN, STD, THRESHOLD_CONFIDENT, DEVICE, CHECKPOINT_DIR
from src.dataset import PillDataset, SHAPE_CLASSES, COLOR_CLASSES
from src.model import PillClassifier


def extract_opencv_meta(image_path: Path) -> list:
    img_arr = np.fromfile(str(image_path), dtype=np.uint8)
    img_bgr = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return [0.0] * 25

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h = float(cv2.mean(hsv[:, :, 0], mask=mask)[0])
    s = float(cv2.mean(hsv[:, :, 1], mask=mask)[0])
    v = float(cv2.mean(hsv[:, :, 2], mask=mask)[0])

    if s < 40:
        color = "하양" if v > 200 else ("회색" if v > 80 else "검정")
    elif h < 15 or h >= 165:
        color = "빨강"
    elif h < 25:
        color = "주황"
    elif h < 35:
        color = "노랑"
    elif h < 85:
        color = "초록"
    elif h < 100:
        color = "청록"
    elif h < 125:
        color = "파랑"
    elif h < 135:
        color = "남색"
    else:
        color = "보라"

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    shape = "기타"
    if contours:
        cnt = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        area = cv2.contourArea(cnt)
        circ = 4 * np.pi * area / (peri * peri) if peri > 0 else 0
        n = len(approx)

        if circ > 0.85:
            shape = "원형"
        elif circ > 0.65:
            shape = "타원형"
        elif n == 4:
            shape = "장방형"
        elif n == 5:
            shape = "오각형"
        elif n == 6:
            shape = "육각형"
        elif n == 8:
            shape = "팔각형"
        else:
            shape = "기타"

    shape_vec = [0.0] * len(SHAPE_CLASSES)
    shape_vec[SHAPE_CLASSES.index(shape) if shape in SHAPE_CLASSES else -1] = 1.0
    color_vec = [0.0] * len(COLOR_CLASSES)
    color_vec[COLOR_CLASSES.index(color) if color in COLOR_CLASSES else -1] = 1.0
    return shape_vec + color_vec + [0.0, 0.0, 0.0]


def run_eval(model, val_ds, mode: str, use_metadata: bool, device, tf):
    correct = 0
    confident = 0
    total = len(val_ds)

    for idx in tqdm(range(total), desc=f"  {mode:<12}", ncols=80, leave=True):
        img_path, label = val_ds.samples[idx]

        image = Image.open(img_path).convert("RGB")
        image = tf(image).unsqueeze(0).to(device)

        if not use_metadata:
            meta_t = None
        elif mode == "zeros":
            meta_t = torch.zeros(1, 25, dtype=torch.float32).to(device)
        elif mode == "opencv":
            meta_t = torch.tensor(extract_opencv_meta(img_path), dtype=torch.float32).unsqueeze(0).to(device)
        else:
            meta_t = torch.tensor(val_ds._normalize_meta(val_ds.metadata[idx]), dtype=torch.float32).unsqueeze(0).to(device)

        with torch.no_grad():
            probs = F.softmax(model(image, meta_t), dim=1).squeeze(0)

        if probs.argmax().item() == label:
            correct += 1
        if probs.max().item() >= THRESHOLD_CONFIDENT:
            confident += 1

    return correct / total, confident / total


def main():
    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")

    ckpt = torch.load(CHECKPOINT_DIR / "best.pt", map_location=device)
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model = PillClassifier(num_classes=len(ckpt["classes"]), use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"])
    model.to(device).eval()
    print(f"모델 로드 완료  epoch={ckpt['epoch']}  use_metadata={use_metadata}  classes={len(ckpt['classes'])}")

    print("Val 데이터셋 준비 중...")
    val_ds = PillDataset(split="val", use_metadata=use_metadata)
    print(f"Val 샘플 수: {len(val_ds)}\n")

    tf = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])

    if use_metadata:
        modes = ["zeros", "opencv", "gt"]
        label_map = {"zeros": "영벡터", "opencv": "OpenCV 추출", "gt": "실제값 (JSON)"}
    else:
        modes = ["image_only"]
        label_map = {"image_only": "이미지만 (재학습)"}

    results = {}
    for mode in modes:
        acc, conf = run_eval(model, val_ds, mode, use_metadata, device, tf)
        results[mode] = (acc, conf)

    print("\n" + "=" * 52)
    print(f"{'조건':<16} | {'Top-1 Acc':>10} | {'Confident 비율':>13}")
    print("-" * 52)
    for mode, (acc, conf) in results.items():
        print(f"{label_map[mode]:<16} | {acc*100:>9.2f}% | {conf*100:>12.1f}%")
    print("=" * 52)


if __name__ == "__main__":
    main()
