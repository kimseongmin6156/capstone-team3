"""
단일경구약제_5000종 이미지를 JSON bbox로 크롭 후 380x380으로 저장.
CNN 학습용 전처리 스크립트.

투명 알약(color_class1에 "투명" 포함)은 Gray World로 white balance 보정 후 저장.

실행: 프로젝트 루트에서
  python train_CNN/prepare_cnn.py
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

IMAGE_BASE = Path("dataset/166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터/01.데이터/1.Training/원천데이터/단일경구약제_5000종")
LABEL_BASE = Path("dataset/166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터/01.데이터/1.Training/라벨링데이터/단일경구약제_5000종")
OUT_BASE   = Path("dataset/cropped")
IMG_SIZE   = 380


def get_metadata(json_path: Path):
    """bbox와 투명 여부 추출."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    bbox = None
    for ann in data.get("annotations", []):
        b = ann.get("bbox", [])
        if len(b) == 4 and all(v >= 0 for v in b) and b[2] > 0 and b[3] > 0:
            bbox = b
            break
    if bbox is None:
        return None

    img_meta = (data.get("images") or [{}])[0]
    colors = [c.strip() for c in (img_meta.get("color_class1") or "").split(",") if c.strip()]
    return {"bbox": bbox, "is_transparent": "투명" in colors}


def gray_world(pil_img: Image.Image) -> Image.Image:
    """이미지 평균색이 회색이 되도록 채널 보정."""
    arr   = np.array(pil_img).astype(np.float32)   # RGB
    mean  = arr.reshape(-1, 3).mean(axis=0)
    gray  = mean.mean()
    arr  *= gray / mean
    arr   = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def pad_square(img: Image.Image) -> Image.Image:
    """비율 보존을 위해 검정 배경으로 정사각형 패딩."""
    w, h = img.size
    if w == h:
        return img
    size = max(w, h)
    result = Image.new("RGB", (size, size), (0, 0, 0))
    result.paste(img, ((size - w) // 2, (size - h) // 2))
    return result


def main():
    drug_dirs = sorted([d for d in IMAGE_BASE.iterdir() if d.is_dir()])
    print(f"K-코드 폴더 수: {len(drug_dirs)}")

    total = success = skip = wb_applied = 0

    for drug_dir in tqdm(drug_dirs, desc="크롭 중", ncols=80):
        code     = drug_dir.name
        json_dir = LABEL_BASE / f"{code}_json"
        out_dir  = OUT_BASE / code

        for img_path in sorted(drug_dir.glob("*.png")):
            total += 1
            json_path = json_dir / f"{img_path.stem}.json"

            if not json_path.exists():
                skip += 1
                continue

            meta = get_metadata(json_path)
            if meta is None:
                skip += 1
                continue

            try:
                x, y, w, h = meta["bbox"]
                img = Image.open(img_path).convert("RGB")

                if meta["is_transparent"]:
                    img = gray_world(img)
                    wb_applied += 1

                cropped = img.crop((x, y, x + w, y + h))
                squared = pad_square(cropped)
                resized = squared.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
                out_dir.mkdir(parents=True, exist_ok=True)
                resized.save(out_dir / img_path.name)
                success += 1
            except Exception:
                skip += 1

    print(f"\n=== 결과 ===")
    print(f"전체:       {total:>6}장")
    print(f"성공:       {success:>6}장  ({success/total*100:.1f}%)")
    print(f"스킵:       {skip:>6}장  ({skip/total*100:.1f}%)")
    print(f"WB 보정:    {wb_applied:>6}장  (투명 알약)")
    print(f"저장:       {OUT_BASE.resolve()}")


if __name__ == "__main__":
    main()
