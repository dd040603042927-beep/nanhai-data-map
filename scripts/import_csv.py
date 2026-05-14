import csv
import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal
from backend.database import engine, ensure_enterprise_schema
from backend.models import Enterprise
from backend import models

# CSV源文件优先级（按优先级排序）
CSV_SOURCES = [
    Path("data/amap_enterprises.csv"),      # 最高优先级：标准采集结果
    Path("data/enscan_standardized.csv"),   # ENScan_GO 标准化结果
    Path("data/search_enterprises.csv"),    # 搜索引擎结果
    Path("data/enscan_enterprises.csv"),    # ENScan_GO 原始结果
    Path("data/merged_enterprises.csv"),    # 合并文件（兼容旧版）
]

OFFICIAL_TOWNS = [
    "桂城街道", "狮山镇", "大沥镇", "里水镇", "丹灶镇", "西樵镇", "九江镇",
]

CATEGORY_ALIASES = {
    "数据资源": "数据资源", "数据资源类": "数据资源", "数据资源企业": "数据资源",
    "数据技术": "数据技术", "数据技术类": "数据技术", "数据技术企业": "数据技术",
    "数据服务": "数据服务", "数据服务类": "数据服务", "数据服务企业": "数据服务",
    "数据应用": "数据应用", "数据应用类": "数据应用", "数据应用企业": "数据应用",
    "数据安全": "数据安全", "数据安全类": "数据安全", "数据安全企业": "数据安全",
    "数据基础设施": "数据基础设施", "数据基础设施类": "数据基础设施", "数据基础设施企业": "数据基础设施",
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
    if not text or text == "待补充":
        return "待补充"

    for town in OFFICIAL_TOWNS:
        if town in text:
            return town
    short_names = {"桂城": "桂城街道", "狮山": "狮山镇", "大沥": "大沥镇",
                   "里水": "里水镇", "丹灶": "丹灶镇", "西樵": "西樵镇", "九江": "九江镇"}
    for short_name, full_name in short_names.items():
        if short_name in text:
            return full_name
    return "待补充"


def normalize_category(value: str) -> str:
    text = value.strip()
    if not text or text == "待分类":
        return "待分类"
    return CATEGORY_ALIASES.get(text, text)


def find_best_csv() -> Path | None:
    """查找最佳的CSV文件"""
    for path in CSV_SOURCES:
        if path.exists():
            # 统计文件行数
            with path.open("r", encoding="utf-8-sig") as f:
                line_count = sum(1 for _ in f) - 1  # 减去表头
            print(f"📁 发现文件: {path} ({line_count} 条数据)")
            return path
    return None


def validate_csv_format(csv_path: Path) -> bool:
    """验证CSV文件格式是否正确"""
    required_columns = ["企业名称", "所在镇街", "主要类型"]

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            print(f"❌ CSV文件无列名: {csv_path}")
            return False

        missing = [col for col in required_columns if col not in reader.fieldnames]
        if missing:
            print(f"❌ CSV文件缺少必要列: {missing}")
            print(f"   现有列: {reader.fieldnames}")
            return False

        print(f"✅ CSV格式验证通过，列名: {reader.fieldnames}")
        return True


def main():
    csv_path = find_best_csv()
    if not csv_path:
        print("❌ 找不到可导入的CSV文件")
        print(f"   尝试过的路径: {CSV_SOURCES}")
        return

    print(f"📁 导入文件: {csv_path}")

    # 验证CSV格式
    if not validate_csv_format(csv_path):
        return

    models.Base.metadata.create_all(bind=engine)
    ensure_enterprise_schema()

    db = SessionLocal()

    try:
        existing_names = {
            normalize_name(item.name): item.id for item in db.query(Enterprise).all()
        }
        print(f"📊 数据库中已有 {len(existing_names)} 条记录")

        success_count = 0
        skip_count = 0
        error_count = 0

        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            for row_num, row in enumerate(reader, start=2):  # start=2 因为第1行是表头
                name = safe_str(row, "企业名称")
                if not name:
                    print(f"⚠️ 第 {row_num} 行: 企业名称为空，跳过")
                    skip_count += 1
                    continue

                normalized_name = normalize_name(name)
                if normalized_name in existing_names:
                    print(f"⏭️ 跳过（已存在）: {name}")
                    skip_count += 1
                    continue

                try:
                    town_raw = safe_str(row, "所在镇街")
                    category_raw = safe_str(row, "主要类型")

                    enterprise = Enterprise(
                        name=name,
                        town=normalize_town(town_raw),
                        category=normalize_category(category_raw),
                        category_reason=safe_str(row, "分类依据") or f"基于{category_raw}自动归类",
                        products=safe_str(row, "主营产品") or "待补充",
                        source_url=safe_str(row, "数据来源") or "",
                        evidence=safe_str(row, "证据片段") or "",
                        confidence=0.7,
                        reviewed=False,
                        crawler_status="批量采集导入",
                    )
                    db.add(enterprise)
                    db.flush()
                    existing_names[normalized_name] = enterprise.id
                    success_count += 1

                    if success_count <= 10 or success_count % 20 == 0:
                        print(f"✅ 导入: {name} → {enterprise.category} ({enterprise.town})")

                except Exception as e:
                    print(f"❌ 第 {row_num} 行导入失败: {name} - {e}")
                    error_count += 1
                    continue

        db.commit()
        print("\n" + "=" * 40)
        print("📊 导入结果统计")
        print("=" * 40)
        print(f"✅ 成功导入：{success_count} 条")
        print(f"⏭️ 跳过：{skip_count} 条")
        print(f"❌ 错误：{error_count} 条")
        print(f"📦 当前数据库总计：{db.query(Enterprise).count()} 条")
        print("=" * 40)

        if success_count > 0:
            # 显示各类别统计
            from sqlalchemy import func
            stats = db.query(Enterprise.category, func.count(Enterprise.id)).group_by(Enterprise.category).all()
            print("\n📈 分类统计:")
            for cat, count in stats:
                print(f"   {cat}: {count} 家")

    except Exception as exc:
        db.rollback()
        print("❌ 导入失败：", exc)
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()