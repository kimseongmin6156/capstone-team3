# AI 추론 서버 구현 인수인계 (HANDOFF / TODO)

> 이 문서는 다른 폴더(`application/`)에서 백엔드·프론트엔드를 먼저 구현한 Claude 세션이,
> AI 서버를 구현할 새 Claude 세션에게 넘기는 인수인계서다.
> **목표: 이 `ai_server/` 폴더 안에 FastAPI AI 추론 서버(포트 8001)를 구현한다.**

---

## 0. 한 줄 요약

알약 사진을 받아 **YOLO로 알약을 크롭 → 각 알약을 CNN + OCR + OpenCV 로 추론·합산 →
가장 그럴듯한 `drug_code` 를 JSON 으로 반환**하는 FastAPI 서버(`POST /predict`, 포트 8001)를 만든다.
약 이름/성분은 반환하지 않는다(백엔드가 DB에서 채움). `drug_code` 와 신뢰도만 반환.

---

## 1. 전체 시스템 맥락

```
Flutter (파일 업로드)
   │ multipart POST /api/scan (file)
   ▼
백엔드 FastAPI :8000   (application/backend/main.py, venv: application/Capenv)  ← 구현 완료
   │ 이미지를 그대로 AI 서버로 전달
   │ multipart POST http://127.0.0.1:8001/predict (file)
   ▼
★ AI 서버 :8001  (이 폴더에서 구현할 대상, venv: 프로젝트 루트 .venv)
   │ YOLO 크롭 → CNN + OCR + OpenCV 합산
   │ JSON 반환
   ▼
백엔드: drug_code 로 medicines(SQLite) 조회해 약 이름/성분 보강 → Flutter 로 반환
```

- **백엔드와 프론트는 이미 이 계약대로 구현·검증 완료.** AI 서버만 만들면 끝.
- 백엔드는 AI 서버가 안 떠 있으면 목업으로 응답한다(`MOCK_WHEN_AI_DOWN = True`).
  **AI 서버 구현·기동이 끝나면 `application/backend/main.py` 의 `MOCK_WHEN_AI_DOWN` 을 `False` 로 바꿀 것.**

---

## 2. 지켜야 할 계약 (가장 중요)

전체 계약 원문: **`../application/AI_SERVER_CONTRACT.md`** (반드시 읽을 것)

### 요청 (백엔드 → 이 서버)
```
POST http://127.0.0.1:8001/predict
Content-Type: multipart/form-data
  file = <이미지 바이트>
```

### 응답 (이 서버 → 백엔드) — 이 JSON 형식을 정확히 지킬 것
```jsonc
{
  "count": 2,
  "results": [
    {
      "drug_code": "K-001029",     // 최종 식별 코드(K-XXXXXX). 실패 시 null
      "confidence": 0.92,          // 0.0~1.0. 실패 시 null
      "status": "confident",       // "confident" | "candidates" | "unknown"
      "candidates": [              // 차순위 후보(없으면 [])
        {"drug_code": "K-001029", "confidence": 0.92},
        {"drug_code": "K-002240", "confidence": 0.40}
      ]
    }
  ]
}
```
- 알약 미탐지 시 `{"count": 0, "results": []}`.
- **약 이름/성분은 절대 넣지 않는다.** `drug_code` 형식은 `medicines.drug_code` 와 동일(`K-` + 6자리).

---

## 3. 재사용할 기존 자산 (전부 프로젝트 루트에 있음)

경로는 모두 프로젝트 루트(`C:\Users\user\ForStudy\Class\26_1\capstone\Capstone_Design\`) 기준.

| 파일 | 내용 | 재사용 포인트 |
|---|---|---|
| `pipeline.py` | YOLO→CNN 추론(현재는 결과를 print만 함) | `load_cnn()`, `classify()`, `pad_square()`, `transform`, 임계값 사용법. **CNN 분류 로직의 정답 소스** |
| `debug_ocr/debug_ocr.py` | YOLO 크롭 → OpenCV 마스크 → 강전처리 → **EasyOCR 4방향 회전** | OCR 파이프라인 전체. 각인(글자) 인식 로직 |
| `debug_opencv/` | OpenCV 전경 마스크 결과 이미지들 | `extract_foreground_mask()` 로직 참고(debug_ocr.py 안에 동일 함수 있음) |
| `src/model.py` | `PillClassifier` 모델 정의 | CNN 모델 클래스 |
| `src/preprocess.py` | `to_studio()`, `tighten_crop()`, `_clahe_rgb()` | 크롭 전처리(CLAHE 등) |
| `config.py` | `IMAGE_SIZE=380`, `MEAN/STD`, `DEVICE`, `THRESHOLD_CONFIDENT=0.85`, `THRESHOLD_CANDIDATE=0.30`, `CHECKPOINT_DIR` | 모든 설정값 |

### CNN 분류의 핵심 코드 (pipeline.py 발췌)
```python
YOLO_CKPT = Path("runs/detect/checkpoints/yolo/weights/best.pt")
CNN_CKPT  = CHECKPOINT_DIR / "cnn_best.pt"     # checkpoints/cnn_best.pt

def load_cnn(checkpoint_path, device):         # ckpt["classes"] = 클래스 라벨 리스트
    ckpt = torch.load(checkpoint_path, map_location=device)
    classes = ckpt["classes"]
    use_metadata = ckpt["model"]["head.0.weight"].shape[1] == 1817
    model = PillClassifier(num_classes=len(classes), use_metadata=use_metadata)
    model.load_state_dict(ckpt["model"]); model.to(device).eval()
    return model, classes

# classify(model, crop, classes, device) → {"status", "prediction", "probability", "candidates"}
#   status: "confident"(>=0.85) / "candidates"(>=0.30) / "unknown"
```

---

## 4. 모델 체크포인트 (이미 존재)

| 모델 | 경로 | 비고 |
|---|---|---|
| YOLO (알약 탐지) | `runs/detect/checkpoints/yolo/weights/best.pt` | ultralytics YOLO |
| CNN (분류) | `checkpoints/cnn_best.pt` | **클래스 100종**, 라벨이 `K-XXXXXX` 형식 (= drug_code). `use_metadata=False` |

CNN 클래스 예시: `['K-000112', 'K-000121', 'K-000250', 'K-000573', 'K-001029', 'K-002240', ...]` (총 100개)

---

## 5. 실행 환경 (venv)

**프로젝트 루트의 `.venv` 를 사용한다** (`C:\...\Capstone_Design\.venv`).
- 이미 설치됨: `torch`, `torchvision(cu124)`, `ultralytics`, `cv2(opencv)`, `easyocr`, `PIL`
- **추가 설치 필요**: `fastapi`, `uvicorn`, `python-multipart`
  ```powershell
  C:\Users\user\ForStudy\Class\26_1\capstone\Capstone_Design\.venv\Scripts\python.exe -m pip install fastapi uvicorn python-multipart
  ```
- 참고: 백엔드(application/Capenv)와는 **다른 venv**다. AI 서버는 무거운 ML 의존성 때문에 루트 .venv 사용.

---

## 6. ⚠️ 경로(작업 디렉터리) 주의

`pipeline.py` / `config.py` / `debug_ocr.py` 의 체크포인트 경로가 **상대경로**(`runs/...`, `checkpoints/...`)다.
이 `ai_server/` 폴더에서 그냥 실행하면 상대경로가 안 맞는다. 둘 중 하나로 해결:
- (권장) AI 서버를 **프로젝트 루트에서 실행**하거나, 코드에서 `BASE_DIR = Path(__file__).parent.parent` 식으로 루트를 잡아 절대경로로 체크포인트를 로드한다.
- 또는 `sys.path.append(<루트>)` 후 루트 기준으로 경로를 절대화한다(`debug_ocr.py` 가 `sys.path.append(parent.parent)` 하는 방식 참고).

---

## 7. 구현 TODO

- [ ] **1. 루트 `.venv` 에 `fastapi uvicorn python-multipart` 설치** (위 5번)
- [ ] **2. 모델 1회 로딩(전역 캐싱)** — 서버 startup 시 YOLO + CNN(+ EasyOCR Reader) 한 번만 로드. 요청마다 로드 금지(느림).
- [ ] **3. `/predict` 엔드포인트** — `UploadFile` 로 이미지 받기 → PIL 로 디코드.
- [ ] **4. YOLO 크롭** — `pipeline.py` 처럼 박스별로 crop + `pad_square`. 박스 0개면 `{"count":0,"results":[]}`.
- [ ] **5. 알약별 추론(핵심)** — 각 크롭에 대해:
  - CNN 분류 (`classify()` 재사용) → 후보 + 확률
  - OpenCV 마스크 + 전처리 (`debug_ocr.py`/`preprocess.py` 재사용)
  - EasyOCR 로 각인 텍스트 인식 (`debug_ocr.py` 의 4방향 회전 로직)
  - **세 결과(CNN 확률 / OCR 각인 매칭 / OpenCV 형상·색)를 합산해 "가장 그럴듯한" drug_code 1개 결정** ← 합산 가중치 설계가 이 작업의 핵심. 어떻게 합칠지 사용자와 상의해서 정할 것.
- [ ] **6. 계약 JSON 형식으로 응답** (2번 섹션) — `status`/`confidence`/`candidates` 채우기.
- [ ] **7. 단독 테스트** — `test_images/` 또는 `dataset/` 이미지로 검증:
  ```powershell
  # 서버 기동 (루트에서)
  .venv\Scripts\python.exe -m uvicorn ai_server.main:app --port 8001 --reload
  # 다른 터미널에서 호출
  curl.exe -F "file=@test_images/<어떤이미지>.jpg" http://127.0.0.1:8001/predict
  ```
- [ ] **8. 통합 테스트** — 백엔드(:8000)도 함께 띄우고 Flutter 에서 파일 업로드 → 결과 확인.
- [ ] **9. `application/backend/main.py` 의 `MOCK_WHEN_AI_DOWN = False` 로 변경** (AI 서버 정상 동작 확인 후).

---

## 8. 참고: OCR 파이프라인 (debug_ocr/debug_ocr.py 요약)

> YOLO 크롭 → `extract_foreground_mask()`(OpenCV: Otsu 임계 + 모폴로지 + 타원 피팅) →
> 강한 전처리 → EasyOCR 로 4방향(0/90/180/270°) 회전하며 각인 텍스트 추출.

각인 텍스트를 약 DB의 각인 정보와 매칭하면 CNN 만으로 헷갈리는 알약을 구분하는 데 쓸 수 있다.
(단, 각인↔drug_code 매핑 테이블이 필요. 현재 백엔드 `medicines` 테이블엔 각인 컬럼이 없으니,
필요하면 별도 매핑 데이터/컬럼 추가를 사용자와 논의.)

---

## 9. 현재까지 완료된 것 (참고)

- 백엔드를 Supabase → **SQLite**(`application/backend/app.db`)로 교체 완료.
- `medicines` 테이블 스키마: `drug_code, medicine_name, main_ingredient, efficacy, usage` (현재 샘플 2건만: K-004378, K-001029).
- 백엔드 `/api/scan`: 이미지를 AI 서버로 forward → 응답의 drug_code 를 medicines 에서 조회해 보강하는 로직 **구현·검증 완료**.
- 프론트 "파일 업로드" 버튼 → 갤러리 선택 → /api/scan 호출 → 결과 다이얼로그 **구현 완료**.
- 따라서 **AI 서버 `/predict` 만 계약대로 만들면 전체 사진 스캔 기능이 끝난다.**

> 다음 작업(향후): AI 챗봇 기능. 이번 범위 아님.
