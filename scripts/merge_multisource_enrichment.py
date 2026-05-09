import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal
from backend.models import Enterprise

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SOURCE_FILES = [
    {
        "path": DATA_DIR / "company_website_enrichment.csv",
        "source_name": "企业官网",
        "url_field": "官网链接",
        "summary_field": "官网摘要",
        "evidence_field": "官网证据",
    },
    {
        "path": DATA_DIR / "baike_enrichment.csv",
        "source_name": "百科信息",
        "url_field": "百科链接",
        "summary_field": "百科摘要",
        "evidence_field": "百科证据",
    },
    {
        "path": DATA_DIR / "job_board_enrichment.csv",
        "source_name": "招聘网站",
        "url_field": "招聘链接",
        "summary_field": "岗位摘要",
        "evidence_field": "岗位证据",
    },
]


def normalize_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def split_items(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []

    separators = ["；", ";", "，", ",", "\n", "|"]
    values = [raw]
    for separator in separators:
        temp = []
        for value in values:
            temp.extend(value.split(separator))
        values = temp

    return [value.strip() for value in values if value.strip()]


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def load_source_rows():
    merged = defaultdict(lambda: {"sources": [], "urls": [], "summaries": [], "evidences": []})

    for config in SOURCE_FILES:
        path = config["path"]
        if not path.exists():
            continue

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                name = (row.get("企业名称") or "").strip()
                if not name:
                    continue

                normalized = normalize_name(name)
                bucket = merged[normalized]

                summary = (row.get(config["summary_field"]) or "").strip()
                evidence = (row.get(config["evidence_field"]) or "").strip()
                url = (row.get(config["url_field"]) or "").strip()

                bucket["sources"].append(config["source_name"])
                if url:
                    bucket["urls"].append(url)
                if summary:
                    bucket["summaries"].append(f"{config['source_name']}：{summary}")
                if evidence:
                    bucket["evidences"].append(f"{config['source_name']}：{evidence}")

    return merged


def merge_into_database():
    merged_rows = load_source_rows()
    if not merged_rows:
        print("未发现可合并的多源增强 CSV")
        return

    db = SessionLocal()

    try:
        enterprises = db.query(Enterprise).all()
        updated = 0

        for enterprise in enterprises:
            normalized = normalize_name(enterprise.name)
            source_data = merged_rows.get(normalized)
            if not source_data:
                continue

            old_sources = split_items(getattr(enterprise, "data_sources", "") or "")
            old_urls = split_items(getattr(enterprise, "source_url", "") or "")
            old_evidence = split_items(getattr(enterprise, "evidence", "") or "")
            old_tags = split_items(getattr(enterprise, "profile_tags", "") or "")

            merged_sources = dedupe_keep_order(old_sources + source_data["sources"])
            merged_urls = dedupe_keep_order(old_urls + source_data["urls"])
            merged_evidence = dedupe_keep_order(old_evidence + source_data["evidences"])
            merged_tags = dedupe_keep_order(old_tags + ["多源融合", f"{len(merged_sources)}源佐证"])

            enterprise.data_sources = "；".join(merged_sources)
            enterprise.source_url = "；".join(merged_urls)
            enterprise.evidence = "；".join(merged_evidence)
            enterprise.evidence_summary = "；".join(dedupe_keep_order(source_data["summaries"]))[:1200]
            enterprise.source_count = len(merged_sources)
            enterprise.profile_tags = "；".join(merged_tags)
            enterprise.crawler_status = "多源增强已合并"

            if enterprise.source_count >= 3:
                enterprise.confidence = max(float(enterprise.confidence or 0), 0.9)
                enterprise.confidence_level = "高"
            elif enterprise.source_count >= 2:
                enterprise.confidence = max(float(enterprise.confidence or 0), 0.75)
                enterprise.confidence_level = "中"
            else:
                enterprise.confidence = max(float(enterprise.confidence or 0), 0.65)

            updated += 1

        db.commit()
        print(f"多源增强合并完成，共更新 {updated} 家企业")

    except Exception as exc:
        db.rollback()
        print("多源增强合并失败：", exc)
    finally:
        db.close()


if __name__ == "__main__":
    merge_into_database()
