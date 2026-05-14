"""
ENScan_GO 企业信息采集脚本
通过调用 ENScan_GO 命令行工具，从爱企查/天眼查/企查查获取企业信息
"""

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.web_crawler_utils import (
    DATA_DIR,
    STANDARD_HEADERS,
    build_standard_row,
    load_sample_reference_rows,
    write_rows,
)

OUTPUT_PATH = DATA_DIR / "enscan_enterprises.csv"
STANDARD_OUTPUT_PATH = DATA_DIR / "enscan_standardized.csv"


def check_enscan_installed() -> bool:
    """检查 ENScan_GO 是否已安装"""
    try:
        result = subprocess.run(
            ["enscan", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def parse_instruction_keywords() -> dict:
    """解析采集指令，提取关键词和搜索参数"""
    instruction = os.getenv("PLATFORM_INSTRUCTION", "").strip()
    limit = int(os.getenv("PLATFORM_LIMIT", "30"))

    # 镇街映射
    town_aliases = {
        "桂城街道": "桂城",
        "桂城": "桂城",
        "狮山镇": "狮山",
        "狮山": "狮山",
        "大沥镇": "大沥",
        "大沥": "大沥",
        "里水镇": "里水",
        "里水": "里水",
        "丹灶镇": "丹灶",
        "丹灶": "丹灶",
        "西樵镇": "西樵",
        "西樵": "西樵",
        "九江镇": "九江",
        "九江": "九江",
    }

    # 类型关键词映射
    category_keywords = {
        "数据资源": ["数据资源", "数据采集", "数据资产", "数据库"],
        "数据技术": ["大数据", "人工智能", "数据技术", "软件开发", "AI"],
        "数据服务": ["数据服务", "数据运营", "数据咨询", "数字化转型"],
        "数据应用": ["数据应用", "智慧城市", "工业互联网", "智能制造"],
        "数据安全": ["数据安全", "网络安全", "信息安全", "隐私计算"],
        "数据基础设施": ["数据中心", "云计算", "云服务", "算力", "基础设施"],
    }

    parsed_town = ""
    for raw_name, short_name in town_aliases.items():
        if raw_name in instruction:
            parsed_town = short_name
            break

    parsed_category = ""
    search_keywords = []
    for cat, keywords in category_keywords.items():
        if cat in instruction:
            parsed_category = cat
            search_keywords.extend(keywords)
            break

    # 如果没有匹配到类型，使用默认关键词
    if not search_keywords:
        search_keywords = ["数据", "信息", "科技", "软件", "网络"]

    # 如果有镇街，添加到搜索关键词中
    if parsed_town:
        search_keywords = [f"{parsed_town} {kw}" for kw in search_keywords]

    return {
        "instruction": instruction,
        "town": parsed_town,
        "category": parsed_category,
        "keywords": search_keywords[:5],  # 最多5个关键词
        "limit": limit,
    }


def run_enscan_search(keyword: str, limit: int = 30) -> Optional[list]:
    """
    执行 ENScan_GO 搜索
    返回: 企业信息列表
    """
    if not check_enscan_installed():
        print("[错误] ENScan_GO 未安装，请先安装：")
        print("  go install github.com/enscan/enscan@latest")
        return None

    try:
        # 使用 ENScan_GO 搜索企业
        # 命令示例: enscan search --keyword "大数据" --output json --limit 30
        cmd = [
            "enscan", "search",
            "--keyword", keyword,
            "--output", "json",
            "--limit", str(limit),
        ]

        print(f"[执行] {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"[错误] ENScan_GO 执行失败: {result.stderr}")
            return None

        # 解析 JSON 输出
        output = result.stdout.strip()
        if not output:
            return []

        # ENScan_GO 输出可能是多行 JSON 或单行数组
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "data" in data:
                return data["data"]
            else:
                return [data] if data else []
        except json.JSONDecodeError:
            # 尝试按行解析
            lines = output.strip().split("\n")
            results = []
            for line in lines:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            return results

    except subprocess.TimeoutExpired:
        print("[错误] ENScan_GO 执行超时")
        return None
    except Exception as e:
        print(f"[错误] ENScan_GO 执行异常: {e}")
        return None


def extract_company_info(raw_data: dict, source_keyword: str) -> dict:
    """
    从 ENScan_GO 返回的原始数据中提取企业信息
    """
    name = raw_data.get("name") or raw_data.get("entname") or ""
    if not name:
        name = raw_data.get("title", "")

    # 提取地址信息
    address = raw_data.get("address") or raw_data.get("regaddress") or ""
    # 提取统一社会信用代码
    credit_code = raw_data.get("creditCode") or raw_data.get("uscc", "")
    # 提取注册资本
    reg_capital = raw_data.get("regCapital") or raw_data.get("regcap", "")
    # 提取成立日期
    est_date = raw_data.get("estDate") or raw_data.get("startdate", "")
    # 提取经营范围
    business_scope = raw_data.get("businessScope") or raw_data.get("scope", "")
    # 提取来源链接
    source_url = raw_data.get("source_url") or f"enscan:keyword={source_keyword}"

    return {
        "name": name.strip(),
        "address": address.strip(),
        "credit_code": credit_code.strip(),
        "reg_capital": reg_capital,
        "est_date": est_date,
        "business_scope": business_scope[:500] if business_scope else "",
        "source_url": source_url,
        "raw_data": raw_data,
    }


def infer_town_from_address(address: str) -> str:
    """从地址推断镇街"""
    if not address:
        return "待补充"

    town_patterns = {
        "桂城": "桂城街道",
        "狮山": "狮山镇",
        "大沥": "大沥镇",
        "里水": "里水镇",
        "丹灶": "丹灶镇",
        "西樵": "西樵镇",
        "九江": "九江镇",
    }

    for pattern, town in town_patterns.items():
        if pattern in address:
            return town

    return "待补充"


def infer_category_from_name_and_scope(name: str, business_scope: str) -> str:
    """根据企业名称和经营范围推断分类"""
    text = f"{name} {business_scope}".lower()

    category_rules = [
        ("数据资源", ["数据采集", "数据标注", "数据交易", "数据资产", "数据库"]),
        ("数据技术", ["大数据", "人工智能", "数据技术", "算法", "ai", "软件开发", "数据平台"]),
        ("数据服务", ["数据服务", "数据运营", "数据咨询", "数字化转型", "信息服务"]),
        ("数据应用", ["智慧城市", "工业互联网", "智能制造", "物联网", "数据应用"]),
        ("数据安全", ["数据安全", "网络安全", "信息安全", "隐私计算", "加密"]),
        ("数据基础设施", ["数据中心", "云计算", "云服务", "算力", "idc"]),
    ]

    for category, keywords in category_rules:
        for kw in keywords:
            if kw in text:
                return f"{category}类"

    return "数据技术类"  # 默认


def build_rows(limit: int | None = None) -> tuple[list, list]:
    """
    执行 ENScan_GO 采集并构建标准化行
    返回: (原始行列表, 标准化行列表)
    """
    params = parse_instruction_keywords()
    max_rows = params["limit"] if limit is None else min(limit, params["limit"])

    if not params["keywords"]:
        print("[错误] 未提取到有效的搜索关键词")
        return [], []

    if not check_enscan_installed():
        print("[错误] ENScan_GO 未安装")
        print("请安装: go install github.com/enscan/enscan@latest")
        return [], []

    sample_reference = load_sample_reference_rows()
    all_results = []
    standard_rows = []
    seen_names = set()

    for keyword in params["keywords"]:
        if len(all_results) >= max_rows:
            break

        print(f"[采集] 搜索关键词: {keyword}")
        raw_results = run_enscan_search(keyword, limit=max_rows - len(all_results))

        if not raw_results:
            continue

        for raw in raw_results:
            if len(all_results) >= max_rows:
                break

            info = extract_company_info(raw, keyword)
            name = info["name"]

            if not name or name in seen_names:
                continue
            seen_names.add(name)

            # 推断镇街和分类
            town = infer_town_from_address(info["address"])
            category = infer_category_from_name_and_scope(name, info["business_scope"])

            # 构建证据片段
            evidence_parts = []
            if info["credit_code"]:
                evidence_parts.append(f"统一社会信用代码：{info['credit_code']}")
            if info["reg_capital"]:
                evidence_parts.append(f"注册资本：{info['reg_capital']}")
            if info["est_date"]:
                evidence_parts.append(f"成立日期：{info['est_date']}")
            if info["business_scope"]:
                evidence_parts.append(f"经营范围：{info['business_scope'][:200]}")

            evidence = "；".join(evidence_parts) if evidence_parts else "ENScan_GO 企业信息采集"

            # 构建分类依据
            reason = f"基于企业名称「{name}」及经营范围自动归入{category}"

            # 原始行
            all_results.append({
                "企业名称": name,
                "所在镇街": town,
                "主要类型": category,
                "分类依据": reason,
                "主营产品": info["business_scope"][:100] if info["business_scope"] else "待补充",
                "数据来源": info["source_url"],
                "证据片段": evidence[:500],
                "置信度": "0.75",
                "是否人工复核": "false",
                "统一社会信用代码": info["credit_code"],
                "注册资本": info["reg_capital"],
                "成立日期": info["est_date"],
            })

            # 标准化行
            standard_rows.append(
                build_standard_row(
                    name=name,
                    town=town,
                    seed_category=category,
                    seed_product=info["business_scope"][:100] if info["business_scope"] else "数据服务",
                    source_url=info["source_url"],
                    source_label="ENScan_GO",
                    summary=evidence[:300],
                    evidence=evidence,
                    sample_reference=sample_reference,
                )
            )

            print(f"  ✓ 发现: {name} → {category}")

    return all_results, standard_rows


def main():
    print("=" * 60)
    print("  ENScan_GO 企业信息采集器")
    print("  数据源：爱企查 / 天眼查 / 企查查")
    print("=" * 60)

    rows, standard_rows = build_rows()

    if rows:
        # 写入原始数据
        write_rows(
            OUTPUT_PATH,
            ["企业名称", "所在镇街", "主要类型", "分类依据", "主营产品",
             "数据来源", "证据片段", "置信度", "是否人工复核",
             "统一社会信用代码", "注册资本", "成立日期"],
            rows,
        )

        # 写入标准化数据
        write_rows(STANDARD_OUTPUT_PATH, STANDARD_HEADERS, standard_rows)

        print(f"\n✅ 采集完成！")
        print(f"   原始数据: {OUTPUT_PATH}")
        print(f"   标准化数据: {STANDARD_OUTPUT_PATH}")
        print(f"   共采集 {len(rows)} 家企业")
    else:
        print("\n⚠️ 未采集到企业数据")
        print("   请检查：")
        print("   1. ENScan_GO 是否正确安装")
        print("   2. 网络连接是否正常")
        print("   3. 采集指令是否包含有效关键词")


if __name__ == "__main__":
    main()