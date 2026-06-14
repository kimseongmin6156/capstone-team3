"""계약 응답 형식 Pydantic 스키마."""

from typing import Literal

from pydantic import BaseModel


class Candidate(BaseModel):
    drug_code: str
    confidence: float


class PillResult(BaseModel):
    drug_code: str | None
    confidence: float | None
    status: Literal["confident", "candidates", "unknown"]
    candidates: list[Candidate]


class PredictResponse(BaseModel):
    count: int
    results: list[PillResult]
