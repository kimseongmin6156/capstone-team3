"""
YOLO 탐지 결과 시각화.

실행: python debug_yolo.py <이미지 경로>
"""

import sys
from pathlib import Path
from ultralytics import YOLO

YOLO_CKPT = Path("runs/detect/checkpoints/yolo/weights/best.pt")


def main(image_path: str):
    yolo = YOLO(str(YOLO_CKPT))
    results = yolo(image_path, verbose=False)[0]
    boxes = results.boxes

    print(f"탐지 수: {len(boxes)}개")
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = box.conf[0].item()
        w, h = x2 - x1, y2 - y1
        print(f"  [{i+1}] conf={conf:.3f}  bbox=({x1},{y1})-({x2},{y2})  크기={w}x{h}")

    out_path = Path(image_path).stem + "_yolo_result.jpg"
    annotated = results.plot()
    import cv2
    cv2.imwrite(out_path, annotated)
    print(f"\n시각화 저장: {out_path}")


if __name__ == "__main__":
    main(sys.argv[1])
