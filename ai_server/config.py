"""AI 서버 설정 — 루트 기준 절대경로와 임계값."""

import os
from pathlib import Path

import torch

BASE_DIR = Path(__file__).resolve().parent.parent

# .env 자동 로드 (백엔드와 동일 파일 공유)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / "application" / "backend" / ".env")
except ImportError:
    pass

YOLO_CKPT = BASE_DIR / "runs" / "detect" / "checkpoints" / "yolo" / "weights" / "best.pt"
CNN_CKPT  = BASE_DIR / "checkpoints" / "cnn_best.pt"
METADATA_JSON = BASE_DIR / "dataset" / "metadata_summary.json"

IMAGE_SIZE = 380
MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]

THRESHOLD_CONFIDENT = 0.85
THRESHOLD_CANDIDATE = 0.30

CNN_TOPK = 20  # 재랭킹 대상 후보 수

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ---- Together AI VLM (OCR 대체) ----
TOGETHER_API_KEY   = os.environ.get("TOGETHER_API_KEY", "")
TOGETHER_API_URL   = "https://api.together.xyz/v1/chat/completions"
TOGETHER_VLM_MODEL = os.environ.get(
    "TOGETHER_VLM_MODEL",
    "google/gemma-3-27b-it",  # 추후 .env로 정확한 모델명 지정
)
VLM_OCR_PROMPT = os.environ.get(
    "VLM_OCR_PROMPT",
    "Read any text or characters imprinted on this pill image. "
    "Reply with only the exact characters you can see, no explanation. "
    "If no text is visible, reply exactly: NONE",
)
