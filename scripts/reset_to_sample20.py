import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_PATH = DATA_DIR / "sample_20.csv"
IMPORT_TARGET_PATH = DATA_DIR / "amap_enterprises.csv"
DATABASE_PATH = PROJECT_ROOT / "enterprise.db"

GENERATED_DATA_FILES = [
    DATA_DIR / "amap_enterprises.csv",
    DATA_DIR / "company_website_enrichment.csv",
    DATA_DIR / "baike_enrichment.csv",
    DATA_DIR / "job_board_enrichment.csv",
    DATA_DIR / "company_website_standardized.csv",
    DATA_DIR / "baike_standardized.csv",
    DATA_DIR / "job_board_standardized.csv",
    DATA_DIR / "crawler_standardized_pool.csv",
    DATA_DIR / "multisource_registry.csv",
]


def remove_generated_files():
    removed = []
    for path in GENERATED_DATA_FILES:
        if path.exists():
            path.unlink()
            removed.append(path.name)

    if DATABASE_PATH.exists():
        try:
            DATABASE_PATH.unlink()
            removed.append(DATABASE_PATH.name)
        except PermissionError:
            clear_database_rows()
            removed.append(f"{DATABASE_PATH.name}（已清空数据，文件被占用未删除）")

    return removed


def clear_database_rows():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='enterprises'"
    )
    table_exists = cursor.fetchone()[0] > 0

    if table_exists:
        cursor.execute("DELETE FROM enterprises")
        try:
            cursor.execute(
                "DELETE FROM sqlite_sequence WHERE name='enterprises'"
            )
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def restore_sample_file():
    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(f"找不到标准样本文件：{SAMPLE_PATH}")

    shutil.copyfile(SAMPLE_PATH, IMPORT_TARGET_PATH)


def run_step(script_name: str):
    script_path = PROJECT_ROOT / "scripts" / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{script_name} 执行失败，退出码：{result.returncode}")


def main():
    print("开始重置数据，只保留 sample_20 标准数据。")
    removed = remove_generated_files()

    if removed:
        print("已删除旧数据文件：")
        for name in removed:
            print(f"- {name}")
    else:
        print("没有发现需要删除的旧数据文件。")

    restore_sample_file()
    print(f"已用 {SAMPLE_PATH.name} 覆盖生成新的 {IMPORT_TARGET_PATH.name}")

    run_step("import_csv.py")
    run_step("normalize_enterprises.py")

    print("重置完成。当前数据库只保留 sample_20 导入的数据。")


if __name__ == "__main__":
    main()
