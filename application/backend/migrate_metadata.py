"""
medicines 테이블에 메타데이터 컬럼 8개 추가 + drug_interactions 테이블 재구축.

데이터 소스:
  - dataset/medicines_metadata.csv  → medicines 확장 컬럼
  - dataset/drug_interactions.csv   → drug_interactions 테이블

실행: 프로젝트 루트에서
  python application/backend/migrate_metadata.py
"""

import csv
import sqlite3
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent
DB_PATH     = BASE_DIR / "app.db"
PROJECT     = BASE_DIR.parent.parent
DATASET     = PROJECT / "dataset"
MEDS_CSV    = DATASET / "medicines_metadata.csv"
INTER_CSV   = DATASET / "drug_interactions.csv"

# CSV 한글 컬럼 → DB 영문 컬럼
COL_MAP = {
    "업체명":       "manufacturer_name",
    "효능":         "indications",
    "사용법":       "dosage_and_administration",
    "주의사항경고": "warnings",
    "주의사항":     "precautions",
    "상호작용":     "drug_interactions",
    "부작용":       "adverse_reactions",
    "보관법":       "storage_instructions",
}
NEW_COLS = list(COL_MAP.values())


def _strip_bom(s: str) -> str:
    """CSV 첫 컬럼 헤더에 붙는 BOM 제거."""
    return s.lstrip("﻿").strip()


def add_columns_if_missing(conn: sqlite3.Connection):
    """medicines에 신규 컬럼이 없으면 ALTER TABLE로 추가."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(medicines)")
    existing = {r[1] for r in cur.fetchall()}
    for col in NEW_COLS:
        if col not in existing:
            cur.execute(f"ALTER TABLE medicines ADD COLUMN {col} TEXT")
            print(f"  컬럼 추가: {col}")
        else:
            print(f"  이미 있음: {col}")


def fill_medicines_metadata(conn: sqlite3.Connection):
    """medicines_metadata.csv 읽어서 medicines 행에 update."""
    with open(MEDS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # 헤더의 BOM/공백 제거
        reader.fieldnames = [_strip_bom(h) for h in reader.fieldnames or []]
        rows = list(reader)

    cur = conn.cursor()
    set_clause = ", ".join(f"{c} = ?" for c in NEW_COLS)
    sql = f"UPDATE medicines SET {set_clause} WHERE drug_code = ?"

    updated = missing = 0
    for row in rows:
        code = row.get("K코드", "").strip()
        if not code:
            continue
        # medicines에 해당 K-코드가 있는지 확인
        exists = cur.execute(
            "SELECT 1 FROM medicines WHERE drug_code = ?", (code,)
        ).fetchone()
        if not exists:
            missing += 1
            continue
        values = [row.get(kor, "") for kor in COL_MAP.keys()]
        values.append(code)
        cur.execute(sql, values)
        updated += 1

    print(f"  업데이트: {updated}건")
    if missing:
        print(f"  medicines에 없는 K-코드: {missing}건 (스킵됨)")


def rebuild_drug_interactions(conn: sqlite3.Connection):
    """drug_interactions 테이블 전체 비우고 CSV로 다시 채움."""
    cur = conn.cursor()
    cur.execute("DELETE FROM drug_interactions")

    with open(INTER_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [_strip_bom(h) for h in reader.fieldnames or []]
        rows = list(reader)

    inserted = 0
    for row in rows:
        cur.execute(
            "INSERT INTO drug_interactions (ingredient_a, ingredient_b, risk_level, interaction_effect) VALUES (?, ?, ?, ?)",
            (
                row.get("ingredient_a", "").strip(),
                row.get("ingredient_b", "").strip(),
                row.get("risk_level", "").strip(),
                row.get("interaction_effect", "").strip(),
            ),
        )
        inserted += 1
    print(f"  삽입: {inserted}건")


def main():
    print(f"DB: {DB_PATH}")
    print(f"medicines_metadata.csv:  {MEDS_CSV}")
    print(f"drug_interactions.csv:   {INTER_CSV}\n")

    conn = sqlite3.connect(DB_PATH)
    try:
        print("[1] medicines 컬럼 추가")
        add_columns_if_missing(conn)

        print("\n[2] medicines 메타데이터 채우기")
        fill_medicines_metadata(conn)

        print("\n[3] drug_interactions 재구축")
        rebuild_drug_interactions(conn)

        conn.commit()
        print("\n=== 완료 ===")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
