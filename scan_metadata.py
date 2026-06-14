"""
단일경구약제_5000종 JSON 라벨 메타데이터 스캔.

추출:
  - 전체 light_color 분포
  - K-코드별 light_color/color_class1/shape 분포
  - 투명 알약 + light_color 조합

실행: python scan_metadata.py
저장: dataset/metadata_summary.json
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

LABEL_BASE = Path("dataset/166.약품식별_인공지능_개발을_위한_경구약제_이미지_데이터/01.데이터/1.Training/라벨링데이터/단일경구약제_5000종")
OUT_PATH   = Path("dataset/metadata_summary.json")


def extract_fields(json_path: Path) -> dict | None:
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    img = (data.get("images") or [{}])[0]
    # color_class1은 "파랑, 투명" 같은 콤마 구분 문자열
    colors1 = [c.strip() for c in (img.get("color_class1") or "").split(",") if c.strip()]
    colors2 = [c.strip() for c in (img.get("color_class2") or "").split(",") if c.strip()]
    return {
        "light_color":  img.get("light_color"),
        "color_class1": colors1,
        "color_class2": colors2,
        "drug_shape":   img.get("drug_shape"),
        "print_front":  img.get("print_front") or "",
        "print_back":   img.get("print_back") or "",
        "dl_name_en":   img.get("dl_name_en") or "",
        "custom_shape": img.get("dl_custom_shape") or "",
    }


def main():
    drug_dirs = sorted(d for d in LABEL_BASE.iterdir() if d.is_dir())
    print(f"폴더 수: {len(drug_dirs)}")

    light_overall = Counter()
    drugs = {}

    for drug_dir in drug_dirs:
        code = drug_dir.name.replace("_json", "")
        light_per_drug   = Counter()
        color1_per_drug  = Counter()
        color2_per_drug  = Counter()
        shape_per_drug   = Counter()
        prints_front     = set()
        prints_back      = set()
        dl_name_en       = ""
        custom_shape     = ""

        for json_path in drug_dir.glob("*.json"):
            fields = extract_fields(json_path)
            if fields is None:
                continue
            if fields["light_color"]:
                light_per_drug[fields["light_color"]] += 1
                light_overall[fields["light_color"]] += 1
            for c in fields["color_class1"]:
                color1_per_drug[c] += 1
            for c in fields["color_class2"]:
                color2_per_drug[c] += 1
            if fields["drug_shape"]:
                shape_per_drug[fields["drug_shape"]] += 1
            if fields["print_front"]:
                prints_front.add(fields["print_front"])
            if fields["print_back"]:
                prints_back.add(fields["print_back"])
            dl_name_en   = dl_name_en   or fields["dl_name_en"]
            custom_shape = custom_shape or fields["custom_shape"]

        drugs[code] = {
            "dl_name_en":   dl_name_en,
            "custom_shape": custom_shape,
            "light_color":  dict(light_per_drug),
            "color_class1": dict(color1_per_drug),
            "color_class2": dict(color2_per_drug),
            "drug_shape":   dict(shape_per_drug),
            "print_front":  sorted(prints_front),
            "print_back":   sorted(prints_back),
            "json_count":   sum(light_per_drug.values()) or sum(color1_per_drug.values()),
        }

    transparent_codes = sorted(
        code for code, d in drugs.items()
        if "투명" in d["color_class1"]
    )

    summary = {
        "total_drugs":              len(drugs),
        "light_color_overall":      dict(light_overall.most_common()),
        "transparent_drug_count":   len(transparent_codes),
        "transparent_drugs":        transparent_codes,
        "drugs":                    drugs,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== 전체 light_color 분포 ===")
    for color, count in light_overall.most_common():
        print(f"  {color}:  {count}")

    print(f"\n=== 투명 알약 K-코드 ({len(transparent_codes)}개) ===")
    for code in transparent_codes[:20]:
        d = drugs[code]
        lights = ", ".join(f"{k}={v}" for k, v in d["light_color"].items())
        colors = ", ".join(d["color_class1"].keys())
        print(f"  {code}  color={colors}  lights=[{lights}]")
    if len(transparent_codes) > 20:
        print(f"  ... 외 {len(transparent_codes) - 20}개")

    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
