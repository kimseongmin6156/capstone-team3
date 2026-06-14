"""
YOLO11s 알약 탐지 모델 학습.

실행: 프로젝트 루트에서
  python train_YOLO/train_yolo.py
"""

from pathlib import Path

from ultralytics import YOLO

YAML_PATH      = Path("dataset/yolo_dataset.yaml")
CHECKPOINT_DIR = Path("checkpoints")


def main():
    print("YOLO11s 학습 시작")
    print(f"데이터셋: {YAML_PATH.resolve()}")

    model = YOLO("yolo11s.pt")

    model.train(
        data=str(YAML_PATH.resolve()),
        epochs=50,
        imgsz=640,
        batch=16,
        device=0,
        workers=0,          # Windows 멀티프로세싱 이슈 방지
        amp=True,
        patience=10,
        project=str(CHECKPOINT_DIR),
        name="yolo",
        exist_ok=True,
        save=True,
        plots=True,
        # 실제 환경 강건성 augmentation
        degrees=180,        # 알약 회전 불변성
        hsv_v=0.6,          # 조명 밝기 편차
        hsv_s=0.7,          # 채도 편차
        scale=0.5,          # 크기 편차
        flipud=0.5,         # 상하 반전
        mixup=0.1,          # 배경 다양성
    )

    best = CHECKPOINT_DIR / "yolo" / "weights" / "best.pt"
    print(f"\n학습 완료. 최종 모델: {best}")


if __name__ == "__main__":
    main()
