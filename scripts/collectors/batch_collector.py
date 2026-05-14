"""批量采集调度器"""
import os
import time
from pathlib import Path

from .search_collector import SearchCollector
from .enscan_collector import EnscanCollector

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


class BatchCollector:
    """批量采集调度器"""

    def __init__(self):
        self.collectors = []
        self.results_summary = {}

    def register_collector(self, name: str, collector):
        self.collectors.append({"name": name, "collector": collector})

    def collect_all(self, instruction: str = None, limit: int = 50):
        if instruction:
            os.environ["PLATFORM_INSTRUCTION"] = instruction
        os.environ["PLATFORM_LIMIT"] = str(limit)

        print("=" * 60)
        print("🚀 批量采集启动")
        print(f"📋 采集指令: {instruction or '使用默认'}")
        print(f"📊 采集上限: {limit}")
        print("=" * 60)

        for item in self.collectors:
            print(f"\n▶ 开始采集: {item['name']}")
            start_time = time.time()

            try:
                results = item["collector"].collect()
                elapsed = time.time() - start_time
                self.results_summary[item["name"]] = {
                    "count": len(results),
                    "time": f"{elapsed:.1f}s",
                    "status": "success"
                }
                print(f"✅ {item['name']} 完成: {len(results)} 条, 耗时 {elapsed:.1f}s")
            except Exception as e:
                self.results_summary[item["name"]] = {
                    "count": 0,
                    "time": "0s",
                    "status": f"failed: {e}"
                }
                print(f"❌ {item['name']} 失败: {e}")

        self._print_summary()
        self._merge_results()

    def _print_summary(self):
        print("\n" + "=" * 60)
        print("📊 采集汇总")
        print("=" * 60)

        total = 0
        for name, summary in self.results_summary.items():
            print(f"  {name}: {summary['count']} 条 ({summary['time']})")
            total += summary["count"]

        print(f"\n📈 总计采集: {total} 条")

    def _merge_results(self):
        """合并所有采集结果"""
        all_results = []
        seen = set()

        source_files = [
            DATA_DIR / "enscan_enterprises.csv",
            DATA_DIR / "search_enterprises.csv",
        ]

        for file_path in source_files:
            if not file_path.exists():
                continue

            import csv
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("企业名称", "")
                    if name and name not in seen:
                        seen.add(name)
                        all_results.append(row)

        if all_results:
            merged_path = DATA_DIR / "merged_enterprises.csv"
            fieldnames = ["企业名称", "所在镇街", "主要类型", "分类依据", "主营产品", "数据来源", "证据片段", "置信度", "是否人工复核"]

            with open(merged_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_results)

            print(f"\n📁 合并结果已保存: {merged_path} ({len(all_results)} 条)")


def create_batch_collector() -> BatchCollector:
    collector = BatchCollector()
    collector.register_collector("ENScan_GO", EnscanCollector())
    collector.register_collector("搜索引擎", SearchCollector())
    return collector


def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量采集南海区企业")
    parser.add_argument("-i", "--instruction", help="采集指令，如: 采集桂城街道的数据技术企业")
    parser.add_argument("-l", "--limit", type=int, default=50, help="采集上限")
    args = parser.parse_args()

    collector = create_batch_collector()
    collector.collect_all(instruction=args.instruction, limit=args.limit)


if __name__ == "__main__":
    main()