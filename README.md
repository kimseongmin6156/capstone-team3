# 이게 머약 — 알약 식별 AI 캡스톤

스마트폰으로 알약을 촬영하면 종류를 식별하고, 약품 정보·복약 상호작용·증상 기반 상담을 제공하는 통합 알약 관리 앱입니다.

## 주요 기능

- **알약 스캔**: 사진 한 장으로 여러 알약 동시 식별 (YOLO 탐지 → CNN 분류 → OpenCV 색·모양 검증 → VLM OCR)
- **약품 검색**: 약품명 / 주성분 부분 일치 검색
- **나의 알약**: 사용자별 알약 보관, 영구 저장
- **AI 챗봇 상담**: Together AI Llama-3.3-70B 기반, 약품 DB를 도구로 호출하는 에이전트
- **PWA 지원**: 모바일·데스크톱 브라우저에서 설치 가능

## 기술 스택

| 영역 | 기술 |
|---|---|
| **객체 탐지** | YOLO11s 파인튜닝 (mAP50 0.99) |
| **분류** | EfficientNet-B4 파인튜닝 (100 classes) |
| **OCR / VLM** | Together AI Gemma 4 31B-it (EasyOCR 폴백) |
| **챗봇** | Together AI Llama-3.3-70B + Tool Calling |
| **백엔드** | FastAPI + SQLite |
| **AI 서버** | FastAPI (포트 8001) |
| **프론트엔드** | Flutter (Web/iOS/Android/Desktop) |
| **데이터셋** | AIHub 166번 약품식별 데이터 (100종) |

## 시스템 구조

```
Flutter (Web/Mobile)
   │ multipart POST /api/scan
   ▼
백엔드 FastAPI :8000  (application/backend/)
   │ DB 조회 / 챗봇 / 사용자 관리
   │
   ├─ POST :8001/predict ──▶ AI 서버 (ai_server/)
   │                            YOLO 크롭 → CNN + OpenCV + VLM(OCR)
   │
   └─ Together AI ──▶ 챗봇 + VLM
```

## 폴더 구조

```
.
├── application/
│   ├── backend/        # FastAPI 백엔드 (포트 8000)
│   │   ├── main.py
│   │   ├── migrate_*.py
│   │   └── requirements.txt
│   └── frontend/       # Flutter 앱
│       ├── lib/
│       │   ├── screens/
│       │   ├── state/
│       │   ├── theme/
│       │   └── widgets/
│       └── web/
├── ai_server/          # AI 추론 서버 (포트 8001)
│   ├── main.py
│   ├── inference.py
│   ├── vlm_utils.py    # Together AI VLM (OCR 대체)
│   ├── cv_utils.py     # OpenCV 색·모양 분석
│   └── scoring.py      # 후보 재랭킹
├── src/                # 공유 Python 모듈
│   └── model.py        # PillClassifier
├── train_CNN/          # CNN 학습 파이프라인
├── train_YOLO/         # YOLO 학습 파이프라인
├── dataset/            # 메타데이터 (이미지 데이터는 별도)
└── debug_*/            # 단계별 디버깅 스크립트
```

## 실행 방법

### 1. 사전 준비

- Python 3.12+, Flutter SDK, Git
- 학습된 모델 가중치 (별도 공유, 아래 "모델 파일 받기" 참고)
- Together AI API 키 — https://api.together.xyz/settings/api-keys

### 2. 백엔드 (application/backend)

```bash
cd application
python -m venv Capenv
.\Capenv\Scripts\activate          # Windows
# source Capenv/bin/activate       # macOS/Linux
pip install -r backend/requirements.txt
```

`.env` 파일을 `application/backend/`에 생성:
```
TOGETHER_API_KEY=tgp_v1_...
TOGETHER_CHATBOT_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
TOGETHER_VLM_MODEL=google/gemma-3-27b-it
```

DB 초기 구축:
```bash
python backend/migrate_medicines.py    # medicines 테이블 채우기
python backend/migrate_metadata.py     # 메타데이터 컬럼 추가
python backend/categorize_medicines.py # 카테고리 LLM 분류
```

서버 실행:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 3. AI 서버 (ai_server)

프로젝트 루트에 별도 가상환경 (PyTorch 등 무거운 의존성):
```bash
uv sync
.venv\Scripts\python.exe -m uvicorn ai_server.main:app --host 0.0.0.0 --port 8001
```

### 4. 프론트엔드 (application/frontend)

```bash
cd application/frontend
flutter pub get

# 로컬 PC에서 데스크톱 실행
flutter run -d windows

# 웹 빌드 (PWA로 배포 / 통합 서빙)
flutter build web --dart-define=API_BASE=
```

빌드 결과(`build/web/`)는 백엔드가 자동으로 정적 서빙하므로,
브라우저에서 `http://<백엔드 호스트>:8000` 접속.

## 모델 파일 받기

학습된 가중치는 GitHub 용량 제한으로 별도 공유:

| 파일 | 위치 | 설명 |
|---|---|---|
| `cnn_best.pt` | `checkpoints/` | EfficientNet-B4 분류기 (100 클래스) |
| `best.pt` | `runs/detect/checkpoints/yolo/weights/` | YOLO11s 알약 탐지기 |

> **공유 링크**: (제출 시 추가)

또는 직접 학습:
```bash
python train_YOLO/prepare_yolo.py && python train_YOLO/train_yolo.py
python train_CNN/prepare_cnn.py && python train_CNN/train.py
```

## 모델 성능

| 모델 | 지표 | 값 |
|---|---|---|
| YOLO11s | mAP50 | **0.990** |
| YOLO11s | Recall | **0.996** |
| EfficientNet-B4 | Top-1 (test) | (학습 후 측정) |

## 개발 도구 / 디버깅

| 스크립트 | 용도 |
|---|---|
| `debug_yolo.py` | YOLO bbox 시각화 |
| `debug_cnn.py` | CNN 단독 분류 테스트 |
| `debug_opencv/debug_opencv.py` | OpenCV 마스크/색/모양 추출 |
| `debug_ocr/debug_ocr.py` | OCR 다중 전처리 × 회전 |
| `debug_pipeline/debug_pipeline.py` | 전체 파이프라인 단계별 출력 |
| `benchmark.py` | YOLO + CNN 정확도/속도 측정 |
| `ai_server/server_pipeline/run.py` | AI 서버 파이프라인 CLI 디버깅 |

## 데이터셋

- **AIHub 166번**: 약품식별 인공지능 개발을 위한 경구약제 이미지 데이터
- 학습에 사용: 100종 OTC 일반의약품
  - CNN: 21,599장 (train 70 / val 15 / test 15)
  - YOLO: 11,824장 (train 80 / val 20)

## 라이선스

학술/캡스톤 목적의 비공개 프로젝트입니다. AIHub 데이터셋 이용 약관에 따라 원본 이미지는 재배포하지 않습니다.

## 만든 사람

- 김성민 (AI 모델 / 백엔드 / 통합)
- 노은찬 (프론트엔드 UI 디자인)
