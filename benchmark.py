"""
YOLO + CNN 정확도 및 추론 속도 벤치마크.

실행: 프로젝트 루트에서
  python benchmark.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader
from torchvision import transforms
from ultralytics import YOLO

sys.path.append(str(Path(__file__).parent))

from config import IMAGE_SIZE, MEAN, STD, DEVICE, CHECKPOINT_DIR
from src.model import PillClassifier
from train_CNN.dataset_cnn import PillDataset

YOLO_CKPT = Path("runs/detect/checkpoints/yolo/weights/best.pt")
CNN_CKPT  = CHECKPOINT_DIR / "cnn_best.pt"
YOLO_YAML = Path("dataset/yolo_dataset.yaml")
N_WARMUP  = 5
N_RUNS    = 30


# ============================================================
# YOLO 정확도 + 속도
# ============================================================
def bench_yolo():
    print("=" * 60)
    print(" YOLO 성능")
    print("=" * 60)

    yolo = YOLO(str(YOLO_CKPT))

    # 정확도: test 셋 (yaml에 test: 경로 있으면 사용, 없으면 val 폴백)
    yaml_text = YOLO_YAML.read_text(encoding="utf-8")
    if "test:" in yaml_text:
        split = "test"
        print("\n[YOLO] 테스트셋 평가 중...")
    else:
        split = "val"
        print("\n[YOLO] (test 셋 없음 → val로 폴백)")
    metrics = yolo.val(data=str(YOLO_YAML.resolve()), split=split, verbose=False, plots=False)
    print(f"  Precision   : {metrics.box.mp:.4f}")
    print(f"  Recall      : {metrics.box.mr:.4f}")
    print(f"  mAP50       : {metrics.box.map50:.4f}")
    print(f"  mAP50-95    : {metrics.box.map:.4f}")

    # 속도: 더미 이미지로 측정
    print(f"\n[YOLO] 추론 속도 측정 (warmup {N_WARMUP}회, 측정 {N_RUNS}회)")
    dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

    for _ in range(N_WARMUP):
        yolo(dummy, verbose=False)

    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(N_RUNS):
        yolo(dummy, verbose=False)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    dt = (time.perf_counter() - t0) / N_RUNS * 1000  # ms

    print(f"  이미지당     : {dt:.2f} ms  ({1000/dt:.1f} FPS)")


# ============================================================
# CNN 정확도 + 속도
# ============================================================
def bench_cnn():
    print("\n" + "=" * 60)
    print(" CNN 성능")
    print("=" * 60)

    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")

    # 모델 로드
    ckpt = torch.load(CNN_CKPT, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model = PillClassifier(num_classes=len(classes), use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"])
    model.to(device).eval()

    # 정확도: test 셋
    print(f"\n[CNN] 테스트셋 평가 중 (클래스={len(classes)})...")
    test_ds = PillDataset(split="test")
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False, num_workers=0, pin_memory=True)

    correct = total = top5_correct = 0
    with torch.no_grad():
        for images, labels in test_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images, None)
            preds = outputs.argmax(1)
            correct += (preds == labels).sum().item()

            # Top-5
            _, top5 = outputs.topk(5, dim=1)
            top5_correct += (top5 == labels.unsqueeze(1)).any(dim=1).sum().item()
            total += images.size(0)

    print(f"  Test 샘플 수 : {total}")
    print(f"  Top-1 정확도 : {correct/total:.4f}  ({correct}/{total})")
    print(f"  Top-5 정확도 : {top5_correct/total:.4f}  ({top5_correct}/{total})")

    # 속도: 380×380 더미 텐서
    print(f"\n[CNN] 추론 속도 측정 (warmup {N_WARMUP}회, 측정 {N_RUNS}회)")
    dummy = torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE, device=device)

    with torch.no_grad():
        for _ in range(N_WARMUP):
            model(dummy, None)

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(N_RUNS):
            model(dummy, None)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        dt = (time.perf_counter() - t0) / N_RUNS * 1000

    print(f"  이미지당     : {dt:.2f} ms  ({1000/dt:.1f} FPS)")


# ============================================================
# 메인
# ============================================================
def main():
    print(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    if torch.cuda.is_available():
        print(f"GPU   : {torch.cuda.get_device_name(0)}")

    bench_yolo()
    bench_cnn()

    print("\n" + "=" * 60)
    print(" 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
