"""FastAPI AI 추론 서버 (포트 8001).

실행 (프로젝트 루트에서):
  .venv\\Scripts\\python.exe -m uvicorn ai_server.main:app --port 8001
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile

from .inference import run_inference
from .models import registry
from .schemas import PredictResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[ai_server] 모델 로딩 시작...")
    registry.load()
    print(f"[ai_server] 모델 로딩 완료 (device={registry.device}, classes={len(registry.cnn_classes)})")
    yield


app = FastAPI(title="Pill AI Server", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 읽기 실패: {e}")

    if not image_bytes:
        raise HTTPException(status_code=400, detail="빈 파일")

    try:
        result = run_inference(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추론 실패: {e}")

    return result
