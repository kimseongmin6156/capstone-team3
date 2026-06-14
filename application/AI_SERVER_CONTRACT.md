# AI 추론 서버 ↔ 백엔드 계약 (Contract)

사진 업로드 알약 식별 흐름에서 **백엔드(:8000)** 와 **AI 추론 서버(:8001)** 가
주고받는 형식 정의. AI 서버는 아직 미구현이며, 이 문서 형식에 맞춰 구현한다.

## 전체 흐름

```
Flutter (파일 업로드)
   │ multipart POST /api/scan  (field: file)
   ▼
백엔드 (Capenv, :8000)  backend/main.py
   │ 이미지를 그대로 AI 서버로 전달
   │ multipart POST http://127.0.0.1:8001/predict  (field: file)
   ▼
AI 서버 (.venv, :8001)  ← 구현 예정
   │ YOLO로 알약들을 크롭 → 각 알약을 CNN + OCR + OpenCV 로 추론·합산
   │ 가장 그럴듯한 결과를 JSON 으로 반환
   ▼
백엔드: 각 drug_code 를 medicines 테이블에서 조회해 약 이름/성분 보강
   ▼
Flutter 에 결과 표시
```

## ① 요청: 백엔드 → AI 서버

```
POST http://127.0.0.1:8001/predict
Content-Type: multipart/form-data
  file = <업로드된 이미지 바이트 그대로>
```

- 백엔드는 프론트에서 받은 이미지를 **가공 없이 그대로** 전달한다.
- AI 서버가 내부에서 YOLO 크롭 + 전처리(OpenCV) + CNN/OCR 추론을 모두 수행한다.

## ② 응답: AI 서버 → 백엔드 (JSON)

```jsonc
{
  "count": 2,                         // 탐지된 알약 수
  "results": [
    {
      "drug_code": "K-001029",        // 최종 식별 코드. 식별 실패 시 null
      "confidence": 0.92,             // 0.0 ~ 1.0 최종 신뢰도. 실패 시 null
      "status": "confident",          // "confident" | "candidates" | "unknown"
      "candidates": [                 // 차순위 후보(설명/디버깅용, 없으면 빈 배열)
        {"drug_code": "K-001029", "confidence": 0.92},
        {"drug_code": "K-002240", "confidence": 0.40}
      ]
    },
    {
      "drug_code": null,
      "confidence": null,
      "status": "unknown",
      "candidates": []
    }
  ]
}
```

### 필드 규칙
- `drug_code`: `medicines.drug_code` 와 동일한 형식(`K-XXXXXX`). **약 이름/성분은 AI 서버가 보내지 않는다** — 백엔드가 DB에서 채운다.
- `status`:
  - `confident` — 단일 확정
  - `candidates` — 확정은 아니지만 후보 존재(`candidates` 채움)
  - `unknown` — 식별 실패(`drug_code`, `confidence` 는 null)
- 알약을 하나도 탐지 못하면 `count: 0`, `results: []`.

## ③ 백엔드가 프론트로 돌려주는 형식 (참고)

백엔드가 `drug_code` 로 `medicines` 테이블을 조회해 보강한 뒤 아래 형태로 반환한다.

```jsonc
{
  "message": "이미지가 성공적으로 처리되었습니다.",
  "filename": "pill.jpg",
  "count": 1,
  "results": [
    {
      "drug_code": "K-001029",
      "confidence": 0.92,
      "status": "confident",
      "candidates": [...],
      "found_in_db": true,            // medicines 테이블에 있었는지
      "name": "와파린정 5mg",          // DB값. 없으면 drug_code 로 대체
      "ingredient": "와파린",          // DB값. 없으면 null
      "efficacy": "혈전 예방(항응고)",
      "usage": "의사 지시에 따라 복용"
    }
  ],
  "ai_result": { ... }                // 첫 결과(구버전 프론트 호환용)
}
```

## 구현 메모

- **AI 서버 위치**: 프로젝트 루트(`pipeline.py`, `config.py`, `checkpoints/` 가 있는 곳). 루트 `.venv` (torch/ultralytics 설치됨)에서 실행.
- **포트**: 8001 (백엔드 8000 과 분리).
- **모델 로딩**: 무거우므로 서버 시작 시 1회만 로드해 전역 캐싱(요청마다 로드 금지).
- 백엔드는 환경변수 `AI_SERVER_URL` 로 주소를 덮어쓸 수 있다(기본 `http://127.0.0.1:8001/predict`).
- 백엔드 `backend/main.py` 의 `MOCK_WHEN_AI_DOWN = True` 는 **AI 서버가 안 떠 있을 때 프론트 테스트용 목업**을 반환한다. AI 서버 구현 완료 후 `False` 로 변경.
