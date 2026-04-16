import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import csv
import re
from pathlib import Path

import re

from backend.database import SessionLocal
from backend.models import Enterprise

CSV_PATH = Path("data/sample_20.csv")


def safe_str(row, key):
    value = row.get(key)
    if value is None:
        return ""
    return str(value).strip()


def parse_bool(value: str) -> bool:
    return safe_lower(value) in {"true", "1", "yes", "是"}


def safe_lower(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_name(name: str) -> str:
    if not name:
        return ""

    name = name.strip()

    # 去掉括号内容
    name = re.sub(r"[（(].*?[）)]", "", name)

    # 去掉空格
    name = re.sub(r"\s+", "", name)

    return name.lower()


def main():
    if not CSV_PATH.exists():
        print(f"找不到文件: {CSV_PATH}")
        return

    db = SessionLocal()

    try:
        existing_names = {
            normalize_name(item.name): item.id
            for item in db.query(Enterprise).all()
        }

        success_count = 0
        skip_count = 0

        with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                name = safe_str(row, "企业名称")
                town = safe_str(row, "所在镇街")
                category = safe_str(row, "主要类型")
                category_reason = safe_str(row, "分类依据")
                products = safe_str(row, "主营产品")
                source_url = safe_str(row, "数据来源")
                evidence = safe_str(row, "证据片段")
                confidence_raw = safe_str(row, "置信度")
                reviewed_raw = safe_str(row, "是否人工复核")

                if not name:
                    print("跳过：企业名称为空")
                    skip_count += 1
                    continue

                normalized = normalize_name(name)
                if normalized in existing_names:
                    print(f"跳过重复企业：{name}")
                    skip_count += 1
                    continue

                try:
                    confidence = float(confidence_raw) if confidence_raw else 0.0
                except ValueError:
                    print(f"跳过：置信度格式错误 -> {name}")
                    skip_count += 1
                    continue

                reviewed = parse_bool(reviewed_raw)

                normalized_name = normalize_name(row["企业名称"])
                existing = db.query(Enterprise).all()
                is_duplicate = False

                for item in existing:
                    if normalize_name(item.name) == normalized_name:
                        is_duplicate = True
                        break

                if is_duplicate:
                    skip_count += 1
                    continue

                enterprise = Enterprise(
                    name=name,
                    town=town,
                    category=category,
                    category_reason=category_reason,
                    products=products,
                    source_url=source_url,
                    evidence=evidence,
                    confidence=confidence,
                    reviewed=reviewed,
                )

                db.add(enterprise)
                db.flush()

                existing_names[normalized] = enterprise.id
                success_count += 1

        db.commit()
        print("====== 导入结果 ======")
        print(f"成功导入：{success_count} 条")
        print(f"跳过：{skip_count} 条")

    except Exception as e:
        db.rollback()
        print("导入失败：", e)

    finally:
        db.close()


if __name__ == "__main__":
    main()