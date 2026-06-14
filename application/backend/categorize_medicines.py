"""
medicines 테이블의 각 약품을 LLM으로 짧은 분류명(category)으로 요약 저장.

예: "이 약은 두통, 치통, ... 발열시의 해열에 사용합니다."  → "해열진통제"

실행 (프로젝트 루트에서):
  python application/backend/categorize_medicines.py

옵션:
  --overwrite   이미 채워진 category도 다시 생성
"""

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DB_PATH  = BASE_DIR / "app.db"
load_dotenv(BASE_DIR / ".env")

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY", "")
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"
MODEL = os.environ.get(
    "TOGETHER_CHATBOT_MODEL",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
)

SYSTEM_PROMPT = (
    "당신은 약품 분류 전문가입니다. 약품 효능 텍스트를 보고 "
    "짧은 한국어 분류명을 답합니다. 다른 설명 없이 분류명만 출력하세요."
)

USER_PROMPT_TEMPLATE = """약품명: {name}
효능: {indications}

위 약품을 한국어 분류명으로 답해주세요.
- 최대 8자 이내, 명사형
- 예: 해열진통제, 소화제, 감기약, 위장약, 변비약, 알러지약, 진해거담제, 종합비타민, 혈압약, 항생제

분류명만 한 줄로 답하세요."""


def categorize(name: str, indications: str) -> str:
    """Together AI로 한 약품을 분류 → 짧은 문자열 반환."""
    if not indications:
        return ""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    name=name, indications=indications[:1500]
                ),
            },
        ],
        "max_tokens": 30,
        "temperature": 0.2,
    }
    resp = requests.post(
        TOGETHER_API_URL,
        headers={
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()
    # 따옴표/마침표 제거, 첫 줄만
    text = text.splitlines()[0].strip().strip("'\"`. ")
    return text[:20]  # 길어도 20자 컷


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true",
                        help="이미 category가 있어도 다시 생성")
    args = parser.parse_args()

    if not TOGETHER_API_KEY:
        print("TOGETHER_API_KEY가 .env에 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 컬럼 추가 (이미 있으면 무시)
    cur.execute("PRAGMA table_info(medicines)")
    if "category" not in {r[1] for r in cur.fetchall()}:
        cur.execute("ALTER TABLE medicines ADD COLUMN category TEXT")
        print("category 컬럼 추가됨")

    # 대상 행 조회
    if args.overwrite:
        rows = cur.execute(
            "SELECT drug_code, medicine_name, indications FROM medicines"
        ).fetchall()
    else:
        rows = cur.execute(
            """SELECT drug_code, medicine_name, indications
                 FROM medicines
                WHERE category IS NULL OR category = ''"""
        ).fetchall()

    print(f"\n대상: {len(rows)}건")
    if not rows:
        return

    success = 0
    failed = 0
    for i, (code, name, ind) in enumerate(rows, 1):
        try:
            category = categorize(name, ind or "")
            if category:
                cur.execute(
                    "UPDATE medicines SET category = ? WHERE drug_code = ?",
                    (category, code),
                )
                conn.commit()
                success += 1
                print(f"  [{i:>3}/{len(rows)}] {code}  {name[:25]:<25} → {category}")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"  [{i:>3}/{len(rows)}] {code}  실패: {e}")
        time.sleep(0.3)  # rate limit 안전 여유

    print(f"\n=== 완료: 성공 {success} / 실패 {failed} ===")
    conn.close()


if __name__ == "__main__":
    main()
