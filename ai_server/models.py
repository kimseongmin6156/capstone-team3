"""YOLO/CNN/Metadata 싱글톤 로더. EasyOCR은 VLM 실패 시 fallback으로 lazy 로드."""

import json
import sys
from pathlib import Path

import torch
from torchvision import transforms
from ultralytics import YOLO

from .config import (
    BASE_DIR, CNN_CKPT, YOLO_CKPT, METADATA_JSON,
    IMAGE_SIZE, MEAN, STD, DEVICE,
)

# 루트 src/model.py 임포트를 위해 path 추가
sys.path.insert(0, str(BASE_DIR))
from src.model import PillClassifier  # noqa: E402


class ModelRegistry:
    """앱 lifespan 동안 단일 인스턴스를 유지하는 모델 묶음."""

    yolo: YOLO
    cnn: PillClassifier
    cnn_classes: list[str]
    metadata: dict           # K-코드 → 메타데이터 (색/모양/각인)
    transform: transforms.Compose
    device: torch.device
    _easyocr_reader: object | None = None  # VLM 실패 시 fallback (lazy)

    @property
    def easyocr_reader(self):
        """첫 호출 시에만 EasyOCR을 로드 (VLM이 모두 성공하면 끝까지 안 불림)."""
        if self._easyocr_reader is None:
            print("[ai_server] EasyOCR fallback 로드 중 ...")
            import easyocr
            self._easyocr_reader = easyocr.Reader(
                ["en"], gpu=(self.device.type == "cuda")
            )
        return self._easyocr_reader

    def load(self):
        self.device = torch.device(DEVICE)

        # YOLO
        self.yolo = YOLO(str(YOLO_CKPT))

        # CNN
        ckpt = torch.load(CNN_CKPT, map_location=self.device, weights_only=False)
        self.cnn_classes = ckpt["classes"]
        use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
        self.cnn = PillClassifier(num_classes=len(self.cnn_classes), use_metadata=use_metadata)
        self.cnn.load_state_dict(ckpt["model"])
        self.cnn.to(self.device).eval()

        # 입력 변환
        self.transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ])

        # Metadata
        if METADATA_JSON.exists():
            with open(METADATA_JSON, encoding="utf-8") as f:
                summary = json.load(f)
            self.metadata = summary.get("drugs", {})
        else:
            self.metadata = {}


registry = ModelRegistry()
