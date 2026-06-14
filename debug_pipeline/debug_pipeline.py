"""
파이프라인 단계별 디버깅 (YOLO + CNN + OpenCV + OCR).

실행: 프로젝트 루트에서
  python debug_pipeline/debug_pipeline.py <이미지 경로>

저장 (debug_pipeline/<stem>/ 폴더):
  1_yolo_detection.png       : YOLO bbox 시각화
  crop{i}_raw.png            : YOLO 크롭
  crop{i}_cnn_input.png      : CNN 입력 (pad_square + 380 리사이즈)
  crop{i}_opencv.png         : OpenCV 마스크/컨투어 시각화
  crop{i}_ocr_in_{mode}.png  : OCR 전처리 (raw/mild/strong)

출력 (3가지 신호, 합산 로직은 미정):
  - CNN Top-5 분류
  - OpenCV 색/모양/크기
  - OCR 텍스트 (3 전처리 × 4 회전 중 최고)
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision import transforms
from ultralytics import YOLO

sys.path.append(str(Path(__file__).parent.parent))

from config import IMAGE_SIZE, MEAN, STD, DEVICE, CHECKPOINT_DIR
from src.model import PillClassifier

YOLO_CKPT = Path("runs/detect/checkpoints/yolo/weights/best.pt")
CNN_CKPT  = CHECKPOINT_DIR / "cnn_best.pt"
OUT_DIR   = Path(__file__).parent

transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])

HUE_RANGES = [
    (  0,  10, "빨강"),
    ( 10,  25, "주황"),
    ( 25,  35, "노랑"),
    ( 35,  85, "초록"),
    ( 85, 125, "파랑"),
    (125, 145, "보라"),
    (145, 165, "분홍"),
    (165, 180, "빨강"),
]


# ================================================================
# 공통
# ================================================================

def pad_square(img: Image.Image) -> Image.Image:
    """비율 보존을 위해 검정 배경으로 정사각형 패딩."""
    w, h = img.size
    if w == h:
        return img
    size = max(w, h)
    result = Image.new("RGB", (size, size), (0, 0, 0))
    result.paste(img, ((size - w) // 2, (size - h) // 2))
    return result


# ================================================================
# CNN
# ================================================================

def load_cnn(device):
    ckpt = torch.load(CNN_CKPT, map_location=device)
    classes = ckpt["classes"]
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model = PillClassifier(num_classes=len(classes), use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"])
    model.to(device).eval()
    return model, classes


# ================================================================
# OpenCV 색/모양 분석
# ================================================================

def extract_foreground_mask(bgr: np.ndarray):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    h, w = gray.shape
    cy1, cy2 = h // 2 - h // 6, h // 2 + h // 6
    cx1, cx2 = w // 2 - w // 6, w // 2 + w // 6
    if np.mean(thresh[cy1:cy2, cx1:cx2]) < 127:
        thresh = cv2.bitwise_not(thresh)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = h * w
    contours = [c for c in contours if cv2.contourArea(c) < img_area * 0.95]
    if not contours:
        return np.zeros_like(gray), None

    largest = max(contours, key=cv2.contourArea)
    if len(largest) >= 5:
        area = cv2.contourArea(largest)
        peri = cv2.arcLength(largest, True)
        circ = 4 * np.pi * area / (peri ** 2) if peri > 0 else 0
        if circ > 0.65:
            ellipse = cv2.fitEllipse(largest)
            mask = np.zeros_like(gray)
            cv2.ellipse(mask, ellipse, 255, thickness=cv2.FILLED)
            refined, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if refined:
                return mask, max(refined, key=cv2.contourArea)

    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [largest], -1, 255, thickness=cv2.FILLED)
    return mask, largest


def dominant_color(bgr: np.ndarray, mask: np.ndarray):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv[mask == 255]
    if len(pixels) == 0:
        return None, "알 수 없음"

    h_med = int(np.median(pixels[:, 0]))
    s_med = int(np.median(pixels[:, 1]))
    v_med = int(np.median(pixels[:, 2]))

    if v_med > 220 and s_med < 80:
        name = "흰색"
    elif s_med < 60:
        if v_med > 200:
            name = "흰색"
        elif v_med < 60:
            name = "검정"
        else:
            name = "회색"
    else:
        name = next((n for lo, hi, n in HUE_RANGES if lo <= h_med < hi), "알 수 없음")
        if v_med < 70:
            name = f"진한 {name}"
        elif s_med < 100:
            name = f"연한 {name}"

    return (h_med, s_med, v_med), name


def shape_analysis(contour: np.ndarray) -> dict:
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
    rect = cv2.minAreaRect(contour)
    (_, _), (w, h), _ = rect
    long_side, short_side = max(w, h), min(w, h)
    aspect = long_side / short_side if short_side > 0 else 0

    if circularity > 0.85 and aspect < 1.15:
        shape = "원형"
    elif aspect >= 1.8:
        shape = "장방형"
    elif circularity > 0.65 and aspect >= 1.15:
        shape = "타원형"
    elif 0.85 < aspect < 1.15:
        shape = "정사각/마름모"
    else:
        shape = "기타"

    return {
        "shape": shape,
        "aspect_ratio": round(aspect, 3),
        "circularity": round(circularity, 3),
        "long_side": int(long_side),
        "short_side": int(short_side),
        "area": int(area),
    }


# ================================================================
# OCR
# ================================================================

def _isolate(bgr, mask):
    return cv2.bitwise_and(bgr, bgr, mask=mask)


def preprocess_raw(bgr, mask):
    isolated = _isolate(bgr, mask)
    h, w = isolated.shape[:2]
    return cv2.resize(isolated, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


def preprocess_mild(bgr, mask):
    isolated = _isolate(bgr, mask)
    gray = cv2.cvtColor(isolated, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(16, 16))
    enhanced = clahe.apply(gray)
    h, w = enhanced.shape
    return cv2.resize(enhanced, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


def preprocess_strong(bgr, mask):
    isolated = _isolate(bgr, mask)
    gray = cv2.cvtColor(isolated, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blur = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=3)
    sharpened = cv2.addWeighted(enhanced, 1.8, blur, -0.8, 0)
    h, w = sharpened.shape
    return cv2.resize(sharpened, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)


PREPROCESSORS = {
    "raw":    preprocess_raw,
    "mild":   preprocess_mild,
    "strong": preprocess_strong,
}


def run_ocr_multi_rotation(reader, img: np.ndarray):
    best = {"text": "", "conf": 0.0, "rotation": 0, "all": []}
    for angle in (0, 90, 180, 270):
        rotated = np.rot90(img, k=angle // 90)
        results = reader.readtext(
            rotated, detail=1, paragraph=False,
            text_threshold=0.5, low_text=0.3,
        )
        if not results:
            continue
        avg_conf = sum(c for _, _, c in results) / len(results)
        if avg_conf > best["conf"]:
            best = {
                "text": " ".join(t for _, t, _ in results),
                "conf": avg_conf,
                "rotation": angle,
                "all": [(t, round(c, 3)) for _, t, c in results],
            }
    return best


# ================================================================
# 메인
# ================================================================

def main(image_path: str):
    stem = Path(image_path).stem
    save_dir = OUT_DIR / stem
    save_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")

    print(f"[1] YOLO 탐지: {image_path}")
    print(f"    저장 폴더: {save_dir}")
    yolo = YOLO(str(YOLO_CKPT))
    results = yolo(image_path, verbose=False)[0]
    boxes = results.boxes
    print(f"    탐지 수: {len(boxes)}개")

    cv2.imwrite(str(save_dir / "1_yolo_detection.png"), results.plot())

    if len(boxes) == 0:
        return

    print(f"\n[2] CNN 로드")
    cnn, classes = load_cnn(device)

    print(f"[3] EasyOCR 로드 (최초 1회 모델 다운로드)")
    import easyocr
    reader = easyocr.Reader(['en'], gpu=True)

    orig_img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")

    print(f"\n[4] 알약별 분석")
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = box.conf[0].item()
        w, h = x2 - x1, y2 - y1

        print(f"\n  ========== [알약 {i+1}]  YOLO conf={conf:.3f}  bbox=({x1},{y1})-({x2},{y2})  크기={w}x{h} ==========")

        raw_crop = orig_img.crop((x1, y1, x2, y2))
        raw_crop.save(save_dir / f"crop{i+1}_raw.png")
        crop_bgr = cv2.cvtColor(np.array(raw_crop), cv2.COLOR_RGB2BGR)

        # --- CNN ---
        squared = pad_square(raw_crop)
        cnn_input = squared.resize((IMAGE_SIZE, IMAGE_SIZE), Image.LANCZOS)
        cnn_input.save(save_dir / f"crop{i+1}_cnn_input.png")

        tensor = transform(squared).unsqueeze(0).to(device)
        with torch.no_grad():
            probs = F.softmax(cnn(tensor, None), dim=1).squeeze(0)
        topk = probs.topk(20)
        print(f"\n  [CNN] Top-20")
        for prob, idx in zip(topk.values, topk.indices):
            print(f"    {classes[idx.item()]}  {prob.item()*100:.2f}%")

        # --- OpenCV ---
        mask, contour = extract_foreground_mask(crop_bgr)
        if contour is None:
            print(f"\n  [OpenCV] 마스크 추출 실패")
        else:
            hsv_med, color_name = dominant_color(crop_bgr, mask)
            shape_info = shape_analysis(contour)

            vis = crop_bgr.copy()
            cv2.drawContours(vis, [contour], -1, (0, 255, 0), 3)
            overlay = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            combined = np.hstack([crop_bgr, overlay, vis])
            cv2.imwrite(str(save_dir / f"crop{i+1}_opencv.png"), combined)

            print(f"\n  [OpenCV]")
            print(f"    색상: HSV={hsv_med}  → {color_name}")
            print(f"    모양: {shape_info['shape']}  종횡비={shape_info['aspect_ratio']}  원형도={shape_info['circularity']}")
            print(f"    크기: 장변/단변={shape_info['long_side']}/{shape_info['short_side']} px  면적={shape_info['area']} px²")

        # --- OCR ---
        if contour is None:
            print(f"\n  [OCR] 마스크 없어 스킵")
        else:
            print(f"\n  [OCR]")
            best_ocr = {"text": "", "conf": 0.0, "rotation": 0, "all": [], "mode": None}
            for mode, fn in PREPROCESSORS.items():
                ocr_input = fn(crop_bgr, mask)
                cv2.imwrite(str(save_dir / f"crop{i+1}_ocr_in_{mode}.png"), ocr_input)
                result = run_ocr_multi_rotation(reader, ocr_input)
                print(f"    [{mode:>6}]  텍스트=\"{result['text']}\"  rot={result['rotation']}  conf={result['conf']:.3f}")
                if result["conf"] > best_ocr["conf"]:
                    best_ocr = {**result, "mode": mode}
            if best_ocr["all"]:
                print(f"    → 최종: \"{best_ocr['text']}\"  (mode={best_ocr['mode']}, rot={best_ocr['rotation']}, conf={best_ocr['conf']:.3f})")
            else:
                print(f"    → 텍스트 감지 실패")


if __name__ == "__main__":
    main(sys.argv[1])
