"""
경구약제조합_5000종 데이터를 YOLO 포맷으로 변환.

출력:
  - 각 이미지 옆에 동명의 .txt 라벨 파일 생성
  - dataset/yolo_train.txt, dataset/yolo_val.txt (이미지 경로 목록)
  - dataset/yolo_dataset.yaml
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent.parent))

BASE       = Path("dataset/166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터/01.데이터/1.Training")
IMAGE_BASE = BASE / "원천데이터/경구약제조합_5000종"
LABEL_BASE = BASE / "라벨링데이터/경구약제조합_5000종"
OUT_DIR    = Path("dataset")


def coco_to_yolo(bbox, img_w, img_h):
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    return cx, cy, w / img_w, h / img_h


def main():
    combo_dirs = sorted([d for d in IMAGE_BASE.iterdir() if d.is_dir()])
    print(f"조합 폴더 수: {len(combo_dirs)}")

    all_img_paths = []
    total_images      = 0
    skip_no_json_dir  = 0
    skip_invalid_bbox = 0

    for combo_dir in combo_dirs:
        name     = combo_dir.name
        json_dir = LABEL_BASE / f"{name}_json"

        if not json_dir.exists():
            skip_no_json_dir += 1
            continue

        drug_subs = [d for d in json_dir.iterdir() if d.is_dir()]
        images    = sorted([f for f in combo_dir.glob("*.png") if "index" not in f.name])

        for img_path in images:
            total_images += 1
            stem      = img_path.stem
            yolo_rows = []
            invalid   = False

            for drug_sub in drug_subs:
                json_path = drug_sub / f"{stem}.json"
                if not json_path.exists():
                    invalid = True
                    break

                try:
                    with open(json_path, encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    invalid = True
                    break

                img_info = data["images"][0]
                w, h     = img_info["width"], img_info["height"]

                anns = [a for a in data["annotations"] if len(a.get("bbox", [])) == 4]
                if not anns:
                    invalid = True
                    break

                for ann in anns:
                    cx, cy, bw, bh = coco_to_yolo(ann["bbox"], w, h)
                    yolo_rows.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            if invalid or not yolo_rows:
                skip_invalid_bbox += 1
                continue

            (img_path.parent / f"{stem}.txt").write_text(
                "\n".join(yolo_rows), encoding="utf-8"
            )
            all_img_paths.append(str(img_path.resolve()))

    print(f"\n=== 데이터 통계 ===")
    print(f"전체 이미지 수:          {total_images:>6}장")
    print(f"라벨 폴더 없어 스킵:     {skip_no_json_dir:>6}개 폴더")
    print(f"bbox 오류로 스킵:        {skip_invalid_bbox:>6}장  ({skip_invalid_bbox/total_images*100:.1f}%)")
    print(f"정상 라벨 생성:          {len(all_img_paths):>6}장  ({len(all_img_paths)/total_images*100:.1f}%)")
    print(f"====================")

    # 80/20 train/val 분할
    rng     = np.random.default_rng(42)
    indices = rng.permutation(len(all_img_paths))
    split   = int(len(all_img_paths) * 0.8)
    train   = [all_img_paths[i] for i in indices[:split]]
    val     = [all_img_paths[i] for i in indices[split:]]

    (OUT_DIR / "yolo_train.txt").write_text("\n".join(train), encoding="utf-8")
    (OUT_DIR / "yolo_val.txt").write_text("\n".join(val),   encoding="utf-8")
    print(f"Train: {len(train)}장  Val: {len(val)}장")

    # dataset.yaml
    train_txt = (OUT_DIR / "yolo_train.txt").resolve()
    val_txt   = (OUT_DIR / "yolo_val.txt").resolve()
    yaml = (
        f"train: {train_txt}\n"
        f"val:   {val_txt}\n\n"
        f"nc: 1\n"
        f"names: ['pill']\n"
    )
    (OUT_DIR / "yolo_dataset.yaml").write_text(yaml, encoding="utf-8")
    print("dataset/yolo_dataset.yaml 생성 완료")


if __name__ == "__main__":
    main()
