"""CNN Top-K 후보를 OpenCV(색·모양) + OCR(각인) 신호로 재랭킹.

CNN 확률은 점수에 사용하지 않는다. CNN은 후보 추출기로만 쓰고,
실제 선택은 OpenCV + OCR로 한다.
"""

from rapidfuzz.distance import Levenshtein

# OpenCV가 추정한 색 이름 → 메타데이터 color_class1 후보 키워드 매핑
COLOR_ALIAS = {
    "빨강":   ["빨강", "적색", "분홍"],
    "주황":   ["주황", "황색", "노랑"],
    "노랑":   ["노랑", "황색", "주황"],
    "초록":   ["초록", "녹색", "연두", "청록"],
    "파랑":   ["파랑", "청색", "남색", "청록", "투명"],
    "보라":   ["보라", "자주", "남색"],
    "분홍":   ["분홍", "연빨강", "연주황"],
    "흰색":   ["흰색", "하양", "백색", "투명"],
    "회색":   ["회색"],
    "검정":   ["검정", "흑색", "까망"],
}

SHAPE_ALIAS = {
    "원형":           ["원형"],
    "타원형":         ["타원형", "장방형"],
    "장방형":         ["장방형", "타원형"],
    "정사각/마름모":  ["사각형", "마름모형"],
    "기타":           [],
}


def _normalize(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum())


def color_match(opencv_color: str | None, meta_colors: dict | list | None) -> float:
    """OpenCV 추정 색이 메타데이터 색 라벨에 포함되면 1.0."""
    if not opencv_color or not meta_colors:
        return 0.0

    # "진한 파랑" / "연한 파랑" → "파랑"
    base = opencv_color.replace("진한 ", "").replace("연한 ", "").strip()
    aliases = COLOR_ALIAS.get(base, [base])

    meta_keys = meta_colors.keys() if isinstance(meta_colors, dict) else meta_colors
    for k in meta_keys:
        for alias in aliases:
            if alias in k:
                return 1.0
    return 0.0


def shape_match(opencv_shape: str | None, meta_shapes: dict | list | None) -> float:
    """OpenCV 추정 모양이 메타데이터 모양에 매칭되면 1.0."""
    if not opencv_shape or not meta_shapes:
        return 0.0

    aliases = SHAPE_ALIAS.get(opencv_shape, [opencv_shape])
    meta_keys = meta_shapes.keys() if isinstance(meta_shapes, dict) else meta_shapes
    for k in meta_keys:
        for alias in aliases:
            if alias in k:
                return 1.0
    return 0.0


def ocr_match(ocr_text: str, meta_prints: list[str]) -> float:
    """OCR 텍스트와 메타데이터 print_front들과의 fuzzy 유사도."""
    if not ocr_text or not meta_prints:
        return 0.0

    ocr_norm = _normalize(ocr_text)
    if not ocr_norm:
        return 0.0

    best = 0.0
    for p in meta_prints:
        if not p:
            continue
        p_norm = _normalize(p)
        if not p_norm:
            continue
        dist = Levenshtein.distance(ocr_norm, p_norm)
        max_len = max(len(ocr_norm), len(p_norm))
        sim = 1.0 - dist / max_len if max_len > 0 else 0.0
        best = max(best, sim)
    return best


# 가중치: OCR > 색 > 모양
W_OCR   = 0.5
W_COLOR = 0.3
W_SHAPE = 0.2


def score_candidate(
    drug_code: str,
    meta: dict,
    opencv_color: str | None,
    opencv_shape: str | None,
    ocr_text: str,
) -> dict:
    """단일 후보에 대해 OpenCV·OCR 점수 합산."""
    if not meta:
        return {"drug_code": drug_code, "score": 0.0, "color": 0.0, "shape": 0.0, "ocr": 0.0}

    c = color_match(opencv_color, meta.get("color_class1"))
    s = shape_match(opencv_shape, meta.get("drug_shape"))
    o = ocr_match(ocr_text, meta.get("print_front", []))

    score = W_OCR * o + W_COLOR * c + W_SHAPE * s
    return {"drug_code": drug_code, "score": score, "color": c, "shape": s, "ocr": o}


def rerank_candidates(
    cnn_top_codes: list[str],
    metadata: dict,
    opencv_color: str | None,
    opencv_shape: str | None,
    ocr_text: str,
) -> list[dict]:
    """CNN Top-K를 OpenCV/OCR 점수로 재정렬해 반환."""
    scored = [
        score_candidate(code, metadata.get(code, {}), opencv_color, opencv_shape, ocr_text)
        for code in cnn_top_codes
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
