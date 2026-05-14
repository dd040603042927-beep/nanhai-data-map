import csv
import re
from pathlib import Path

from web_crawler_utils import (
    DATA_DIR,
    SAMPLE_CANDIDATE_PATHS,
    STANDARD_HEADERS,
    normalize_company_name,
    write_rows,
)

SOURCE_PRIORITY = [
    *SAMPLE_CANDIDATE_PATHS,
    DATA_DIR / "company_website_standardized.csv",
    DATA_DIR / "baike_standardized.csv",
    DATA_DIR / "job_board_standardized.csv",
    DATA_DIR / "amap_enterprises.csv",
]

OUTPUT_PATH = DATA_DIR / "crawler_standardized_pool.csv"


def score_row(row: dict) -> tuple[int, int]:
    source = (row.get("数据来源") or "").strip()
    confidence = row.get("置信度") or "0"
    try:
        confidence_score = int(float(confidence) * 100)
    except ValueError:
        confidence_score = 0

    source_score = 0
    if "nfnews" in source or "sample_" in source:
        source_score = 5
    elif "官网" in source or source.startswith("http"):
        source_score = 4
    elif "baike" in source:
        source_score = 3
    elif "zhipin" in source or "liepin" in source or "51job" in source:
        source_score = 2
    elif "高德" in source:
        source_score = 1

    return source_score, confidence_score


def normalize_row(row: dict) -> dict:
    result = {}
    for field in STANDARD_HEADERS:
        result[field] = (row.get(field) or "").strip()

    if not result["置信度"]:
        result["置信度"] = "0.70"
    if not result["是否人工复核"]:
        result["是否人工复核"] = "false"

    result["分类依据"] = re.sub(r"\s+", "", result["分类依据"])
    result["主营产品"] = re.sub(r"\s+", "", result["主营产品"])
    result["证据片段"] = re.sub(r"\s+", "", result["证据片段"])
    return result


def build_pool():
    best_rows = {}

    for path in SOURCE_PRIORITY:
        if not path.exists():
            continue

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for raw_row in reader:
                row = normalize_row(raw_row)
                name = row.get("企业名称", "")
                if not name:
                    continue

                key = normalize_company_name(name)
                current_score = score_row(row)
                existing = best_rows.get(key)

                if not existing or current_score > existing["score"]:
                    best_rows[key] = {
                        "score": current_score,
                        "row": row,
                    }

    return [item["row"] for item in best_rows.values()]


def main():
    rows = build_pool()
    rows.sort(key=lambda item: item["企业名称"])
    write_rows(OUTPUT_PATH, STANDARD_HEADERS, rows)
    print(f"标准化采集池已输出到：{OUTPUT_PATH}")
    print(f"共汇总 {len(rows)} 家企业")


if __name__ == "__main__":
    main()
