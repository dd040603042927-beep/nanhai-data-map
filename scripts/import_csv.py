import csv
import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal
from backend.models import Enterprise

CSV_PATH = Path("data/amap_enterprises.csv")

OFFICIAL_TOWNS = [
    "桂城街道",
    "狮山镇",
    "大沥镇",
    "里水镇",
    "丹灶镇",
    "西樵镇",
    "九江镇",
]

CATEGORY_ALIASES = {
    "数据资源": "数据资源",
    "数据资源类": "数据资源",
    "数据资源企业": "数据资源",
    "数据技术": "数据技术",
    "数据技术类": "数据技术",
    "数据技术企业": "数据技术",
    "数据服务": "数据服务",
    "数据服务类": "数据服务",
    "数据服务企业": "数据服务",
    "数据应用": "数据应用",
    "数据应用类": "数据应用",
    "数据应用企业": "数据应用",
    "数据安全": "数据安全",
    "数据安全类": "数据安全",
    "数据安全企业": "数据安全",
    "数据基础设施": "数据基础设施",
    "数据基础设施类": "数据基础设施",
    "数据基础设施企业": "数据基础设施",
    "其他数据相关类": "数据应用",
}


def safe_str(row, key):
    return str(row.get(key) or "").strip()


def normalize_name(name: str) -> str:
    text = name.strip()
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def normalize_town(value: str) -> str:
    text = value.strip()
    for town in OFFICIAL_TOWNS:
        if town in text:
            return town

    short_names = {
        "桂城": "桂城街道",
        "狮山": "狮山镇",
        "大沥": "大沥镇",
        "里水": "里水镇",
        "丹灶": "丹灶镇",
        "西樵": "西樵镇",
        "九江": "九江镇",
    }

    for short_name, full_name in short_names.items():
        if short_name in text:
            return full_name

    return "待补充"


def normalize_category(value: str) -> str:
    text = value.strip()
    return CATEGORY_ALIASES.get(text, "待分类")


def main():
    if not CSV_PATH.exists():
        print(f"找不到文件: {CSV_PATH}")
        return

    db = SessionLocal()

    try:
        existing_names = {
            normalize_name(item.name): item.id for item in db.query(Enterprise).all()
        }

        success_count = 0
        skip_count = 0

        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            for row in reader:
                name = safe_str(row, "企业名称")
                if not name:
                    skip_count += 1
                    continue

                normalized_name = normalize_name(name)
                if normalized_name in existing_names:
                    skip_count += 1
                    continue

                enterprise = Enterprise(
                    name=name,
                    town=normalize_town(safe_str(row, "所在镇街")),
                    category=normalize_category(safe_str(row, "主要类型")),
                    category_reason=safe_str(row, "分类依据") or "待补充",
                    products=safe_str(row, "主营产品") or "待补充",
                    source_url=safe_str(row, "数据来源"),
                    evidence=safe_str(row, "证据片段"),
                    confidence=0.0,
                    reviewed=False,
                )

                db.add(enterprise)
                db.flush()
                existing_names[normalized_name] = enterprise.id
                success_count += 1

        db.commit()
        print("====== 导入结果 ======")
        print(f"成功导入：{success_count} 条")
        print(f"跳过：{skip_count} 条")

    except Exception as exc:
        db.rollback()
        print("导入失败：", exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
