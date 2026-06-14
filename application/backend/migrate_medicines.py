"""
medicines 테이블 재구축 + food_interactions 테이블 삭제.

데이터 소스:
  - drug_code, medicine_name : dataset/medicines_name.txt
  - main_ingredient          : dataset/166.../K-XXXXXX_json/*.json → images[0].dl_material
  - image                    : dataset/drug_image.csv (4번째 컬럼)

실행: 프로젝트 루트 또는 application/backend/ 에서
  python application/backend/migrate_medicines.py
"""

import json
import sqlite3
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent
DB_PATH     = BASE_DIR / "app.db"
PROJECT     = BASE_DIR.parent.parent
DATASET     = PROJECT / "dataset"
NAMES_TXT   = DATASET / "medicines_name.txt"
JSON_BASE   = DATASET / "166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터" / "01.데이터" / "1.Training" / "라벨링데이터" / "단일경구약제_5000종"
CSV_PATH    = DATASET / "drug_image.csv"


def parse_names() -> dict[str, str]:
    """medicines_name.txt: 'K-XXXXXX  medicine_name' → {code: name}"""
    result = {}
    for line in NAMES_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result


def get_main_ingredient(drug_code: str) -> str | None:
    """해당 K-코드 폴더의 첫 JSON 파일에서 images[0].dl_material 추출."""
    json_dir = JSON_BASE / f"{drug_code}_json"
    if not json_dir.exists():
        return None
    json_files = sorted(json_dir.glob("*.json"))
    if not json_files:
        return None
    try:
        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)
        img_meta = (data.get("images") or [{}])[0]
        return img_meta.get("dl_material")
    except Exception:
        return None


def parse_csv() -> dict[str, str]:
    """drug_image.csv: K-XXXXXX,name,code,url → {code: url} (인코딩 자동 시도)."""
    text = None
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            text = CSV_PATH.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise RuntimeError(f"drug_image.csv 인코딩 판독 실패: {CSV_PATH}")

    result = {}
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) >= 4 and parts[0].startswith("K-"):
            result[parts[0].strip()] = parts[3].strip()
    return result


def main():
    print(f"DB: {DB_PATH}")
    print(f"names: {NAMES_TXT}")
    print(f"json:  {JSON_BASE}")
    print(f"csv:   {CSV_PATH}\n")

    names = parse_names()
    print(f"medicines_name.txt 로드: {len(names)}건")

    images = parse_csv()
    print(f"drug_image.csv 로드:     {len(images)}건")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # food_interactions 삭제
    cur.execute("DROP TABLE IF EXISTS food_interactions")
    print("food_interactions 테이블 삭제 완료")

    # medicines 재생성 (efficacy/usage 제거, image 추가)
    cur.execute("DROP TABLE IF EXISTS medicines")
    cur.execute("""
        CREATE TABLE medicines (
            drug_code       TEXT PRIMARY KEY,
            medicine_name   TEXT,
            main_ingredient TEXT,
            image           TEXT
        )
    """)
    print("medicines 테이블 재생성 완료")

    inserted = 0
    miss_ingredient = 0
    miss_image = 0

    for code, name in names.items():
        ingredient = get_main_ingredient(code)
        image_url  = images.get(code)
        if ingredient is None:
            miss_ingredient += 1
        if image_url is None:
            miss_image += 1
        cur.execute(
            "INSERT INTO medicines (drug_code, medicine_name, main_ingredient, image) VALUES (?, ?, ?, ?)",
            (code, name, ingredient, image_url),
        )
        inserted += 1

    conn.commit()
    conn.close()

    print(f"\n=== 결과 ===")
    print(f"삽입:                 {inserted}건")
    print(f"main_ingredient 누락: {miss_ingredient}건")
    print(f"image 누락:           {miss_image}건")


if __name__ == "__main__":
    main()
