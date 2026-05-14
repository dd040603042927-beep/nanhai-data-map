#!/usr/bin/env python
"""
批量采集南海区企业 - 命令行入口
使用示例:
    python scripts/run_batch_collect.py -i "采集桂城街道的数据技术企业"
    python scripts/run_batch_collect.py -i "帮我找大沥镇的数据服务公司" -l 30
    python scripts/run_batch_collect.py  # 使用默认参数
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.collectors import create_batch_collector


def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量采集南海区企业")
    parser.add_argument("-i", "--instruction",
                        default="采集桂城街道的数据技术企业",
                        help="采集指令，如: 采集桂城街道的数据技术企业")
    parser.add_argument("-l", "--limit", type=int, default=50,
                        help="每个数据源的采集上限")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  🌐 南海区数据产业图谱 - 批量采集系统")
    print("=" * 70)
    print(f"📝 采集指令: {args.instruction}")
    print(f"🔢 采集上限: {args.limit}")
    print("-" * 70)

    collector = create_batch_collector()
    collector.collect_all(instruction=args.instruction, limit=args.limit)

    print("\n💡 下一步操作:")
    print("   1. 运行: python scripts/import_csv.py")
    print("   2. 运行: python scripts/normalize_enterprises.py")
    print("   3. 重启后端: uvicorn backend.main:app --reload")
    print("   4. 刷新前端页面查看数据")


if __name__ == "__main__":
    main()