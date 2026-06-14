from pathlib import Path

BASE_DIR = Path(__file__).parent

DATA_ROOT = BASE_DIR / "166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터/01.데이터/1.Training"
IMAGE_DIR = DATA_ROOT / "원천데이터/단일경구약제_5000종"
LABEL_DIR = DATA_ROOT / "라벨링데이터/단일경구약제_5000종"

CHECKPOINT_DIR = BASE_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

# 이미지
IMAGE_SIZE = 380
MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]

# 학습
BATCH_SIZE = 32
NUM_WORKERS = 0  # Windows 멀티프로세싱 이슈로 0 권장
EPOCHS_FROZEN   = 10   # backbone frozen 단계
EPOCHS_FINETUNE = 10   # backbone unfreeze 단계
LR_FROZEN    = 1e-3
LR_FINETUNE  = 1e-5
DROPOUT      = 0.3
DEVICE = "cuda"  # GPU 없으면 "cpu"로 변경

# 추론 임계값
THRESHOLD_CONFIDENT = 0.85  # 이 이상이면 단일 확정 출력
THRESHOLD_CANDIDATE = 0.30  # 이 이상이면 후보로 출력
