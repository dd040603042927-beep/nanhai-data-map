import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run_step(step_name: str, script_path: Path):
    print(f"\n===== 开始执行：{step_name} =====")
    result = subprocess.run(
        [PYTHON, str(script_path)],
        cwd=BASE_DIR,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{step_name} 执行失败，退出码：{result.returncode}")
    print(f"===== 完成：{step_name} =====")


def main():
    parser = argparse.ArgumentParser(description="南海区数据产业图谱一键全流程脚本")
    parser.add_argument(
        "--skip-amap",
        action="store_true",
        help="跳过高德 POI 采集，适合已有 data/amap_enterprises.csv 的情况",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="跳过 LLM 辅助摘要演示脚本",
    )
    args = parser.parse_args()

    pipeline = []
    if not args.skip_amap:
        pipeline.extend(
            [
                ("高德 POI 采集", BASE_DIR / "scripts" / "amap_poi_source.py"),
                ("CSV 导入数据库", BASE_DIR / "scripts" / "import_csv.py"),
                ("基础字段标准化", BASE_DIR / "scripts" / "normalize_enterprises.py"),
            ]
        )

    pipeline.extend(
        [
            ("企业官网采集", BASE_DIR / "scripts" / "company_website_source.py"),
            ("百科信息采集", BASE_DIR / "scripts" / "baike_source.py"),
            ("招聘网站采集", BASE_DIR / "scripts" / "job_board_source.py"),
            ("标准化采集池构建", BASE_DIR / "scripts" / "build_standardized_crawler_pool.py"),
            ("多源增强合并", BASE_DIR / "scripts" / "merge_multisource_enrichment.py"),
            ("采集平台注册表生成", BASE_DIR / "scripts" / "collector_platform.py"),
        ]
    )

    if not args.skip_llm:
        pipeline.append(("LLM 辅助摘要演示", BASE_DIR / "scripts" / "llm_assistant.py"))

    for step_name, script_path in pipeline:
        run_step(step_name, script_path)

    print("\n全部流程执行完成。")
    print("如需查看系统效果，请重启后端并刷新前端页面。")


if __name__ == "__main__":
    main()
