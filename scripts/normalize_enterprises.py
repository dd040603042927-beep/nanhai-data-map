import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "enterprise.db"
BACKUP_PATH = BASE_DIR / "enterprise_backup_before_normalize.db"

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


def backup_database():
    if DB_PATH.exists() and not BACKUP_PATH.exists():
        BACKUP_PATH.write_bytes(DB_PATH.read_bytes())
        print(f"已备份数据库到: {BACKUP_PATH}")


def normalize_town(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "待补充"

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
    text = (value or "").strip()
    if not text:
        return "待分类"

    return CATEGORY_ALIASES.get(text, text)


def main():
    if not DB_PATH.exists():
        print(f"未找到数据库文件: {DB_PATH}")
        return

    backup_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, town, category
        FROM enterprises
        """
    )
    rows = cursor.fetchall()

    for enterprise_id, town, category in rows:
        cursor.execute(
            """
            UPDATE enterprises
            SET town = ?, category = ?
            WHERE id = ?
            """,
            (normalize_town(town), normalize_category(category), enterprise_id),
        )

    conn.commit()
    conn.close()

    print(f"清洗完成，共更新 {len(rows)} 条记录")
    print("处理内容：")
    print("1. 所在镇街统一为南海区七个官方镇街")
    print("2. 主要类型统一为比赛使用的六大类")


if __name__ == "__main__":
    main()
