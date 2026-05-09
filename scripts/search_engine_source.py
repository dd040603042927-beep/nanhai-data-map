"""
多源搜索引擎采集器 - 精准版
只采集真正与数据产业相关的企业
"""

import csv
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_PATH = DATA_DIR / "search_enterprises.csv"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SEARCH_DELAY = 1.5

NANHAI_TOWNS = ["桂城", "狮山", "大沥", "里水", "丹灶", "西樵", "九江"]

# 数据企业核心关键词（企业名必须包含其中一个）
DATA_CORE_KEYWORDS = [
    "数据", "信息", "数字", "科技", "软件", "网络", "通信",
    "智能", "云", "互联", "系统", "计算", "电子", "光电",
]

# 排除关键词
EXCLUDE_KEYWORDS = [
    "纸箱", "音响", "玻璃", "机械", "食品", "餐饮", "酒店",
    "房地产", "物业", "建筑", "建材", "装饰", "家具",
    "服装", "纺织", "鞋", "玩具", "五金", "塑料", "化工",
    "资产交易", "资产管理委员会",
    "农业", "养殖", "种植", "畜牧", "水产",
    "汽车维修", "美容", "理发", "洗衣", "快递",
    "洞边", "石碣", "分站", "委员会", "办事处",
]

# 分类关键词
CATEGORY_KEYWORDS = {
    "数据资源": ["数据资源", "数据采集", "数据资产", "大数据服务", "数据库", "数据治理", "档案数字化", "信息资源"],
    "数据技术": ["大数据", "人工智能", "软件开发", "数据分析", "算法", "工业互联网", "信息技术"],
    "数据服务": ["数据服务", "数字化服务", "信息技术服务", "软件服务", "智慧城市", "信息服务"],
    "数据应用": ["数据应用", "数字化", "智能系统", "软件应用", "互联网平台", "信息系统"],
    "数据安全": ["数据安全", "网络安全", "信息安全", "加密", "等保测评"],
    "数据基础设施": ["数据中心", "云计算", "云服务", "通信网络", "算力", "机房"],
}

# 广域搜索关键词（不按分类，泛搜数据相关企业）
BROAD_SEARCH_KEYWORDS = [
    "数据科技", "信息技术", "软件", "网络科技", "数字科技",
    "智能科技", "通信技术", "电子科技", "信息科技",
    "互联网", "系统集成", "计算机", "云计算",
]


def normalize_company_name(name: str) -> str:
    text = re.sub(r"[（(].*?[）)]", "", name)
    text = re.sub(r"\s+", "", text)
    for suffix in ["有限公司", "有限责任公司", "股份有限公司", "集团", "总公司", "分公司"]:
        text = text.replace(suffix, "")
    return text.lower()


def is_data_company(name: str) -> bool:
    """判断企业是否与数据产业相关"""
    # 排除非企业实体和明确不相关的
    for kw in EXCLUDE_KEYWORDS:
        if kw in name:
            return False

    # 必须包含数据核心关键词
    for kw in DATA_CORE_KEYWORDS:
        if kw in name:
            return True

    return False


def guess_category(name: str, snippet: str) -> str:
    """推断分类"""
    text = f"{name} {snippet}"
    scores = {}

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        scores[cat] = score

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return "数据技术"  # 兜底


def parse_instruction() -> dict:
    instruction = os.getenv("PLATFORM_INSTRUCTION", "").strip()

    found_town = ""
    for town in sorted(NANHAI_TOWNS, key=len, reverse=True):
        if town in instruction:
            found_town = town
            break

    found_category = ""
    for cat in CATEGORY_KEYWORDS:
        if cat in instruction:
            found_category = cat
            break

    return {
        "town": found_town,
        "category": found_category,
        "instruction": instruction,
    }


def search_bing(query: str, max_results: int = 8) -> list[dict]:
    try:
        search_url = f"https://www.bing.com/search?q={quote(query)}&count={max_results}"
        response = requests.get(search_url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for item in soup.select("li.b_algo"):
            title_elem = item.select_one("h2 a")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            link = title_elem.get("href", "")
            snippet_elem = item.select_one(".b_caption p") or item.select_one(".b_lineclamp2")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            results.append({"title": title, "link": link, "snippet": snippet})

        return results
    except Exception as e:
        print(f"  搜索失败: {e}")
        return []


def extract_company_names(text: str) -> list[str]:
    patterns = [
        r'([\u4e00-\u9fa5（）()\w]+?(?:有限公司|有限责任公司|股份有限公司|集团))',
    ]

    companies = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            name = match.strip()
            if 6 <= len(name) <= 40:
                if not any(s in name for s in ["http", "www", "搜索", "查看", "百度", "天眼查"]):
                    companies.append(name)

    return companies


def collect() -> list[dict]:
    parsed = parse_instruction()
    town = parsed["town"] or "南海"
    target_category = parsed["category"]

    print(f"指令解析：镇街={town}, 目标分类={target_category or '未指定'}")
    print(f"采集策略：广域搜索所有数据/信息/科技相关企业")
    print()

    all_results = []
    seen_companies = set()

    # 使用广域关键词搜索
    for keyword in BROAD_SEARCH_KEYWORDS[:8]:
        if len(all_results) >= 30:
            break

        queries = [
            f"佛山 {town} {keyword} 有限公司",
            f"site:tianyancha.com 佛山 {town} {keyword}",
        ]

        for query in queries:
            if len(all_results) >= 30:
                break

            print(f"搜索: {query[:60]}...")
            results = search_bing(query)

            for result in results:
                companies = extract_company_names(result["title"] + " " + result["snippet"])

                for company in companies:
                    normalized = normalize_company_name(company)
                    if normalized in seen_companies:
                        continue
                    seen_companies.add(normalized)

                    # 过滤：必须是数据相关企业
                    if not is_data_company(company):
                        continue

                    # 推断分类
                    category = guess_category(company, result["snippet"])

                    print(f"  ✓ {company} → {category}")

                    all_results.append({
                        "name": company,
                        "source": "搜索引擎",
                        "snippet": result["snippet"][:200],
                        "link": result["link"],
                        "category": category,
                    })

                    if len(all_results) >= 30:
                        break

            time.sleep(SEARCH_DELAY)

    print(f"\n{'='*50}")
    print(f"采集完成，共筛选出 {len(all_results)} 家数据相关企业")
    return all_results


def save_to_csv(results: list[dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    parsed = parse_instruction()
    town = parsed["town"] if parsed["town"] else "待补充"

    fieldnames = [
        "企业名称", "所在镇街", "主要类型", "分类依据",
        "主营产品", "数据来源", "证据片段", "置信度", "是否人工复核",
    ]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            cat_label = result["category"] + "类" if not result["category"].endswith("类") else result["category"]

            writer.writerow({
                "企业名称": result["name"],
                "所在镇街": town,
                "主要类型": cat_label,
                "分类依据": f"该企业涉及{result['category']}相关业务",
                "主营产品": "待补充",
                "数据来源": result["link"],
                "证据片段": result["snippet"][:300],
                "置信度": "0.70",
                "是否人工复核": "false",
            })

    print(f"已写出: {OUTPUT_PATH}")
    print(f"共生成 {len(results)} 条")


def main():
    print("=" * 60)
    print("  多源搜索引擎采集器 - 广域搜索模式")
    print("  搜索所有数据/信息/科技/软件相关企业")
    print("=" * 60)
    print()

    try:
        results = collect()
        if results:
            save_to_csv(results)
            print(f"\n✅ 采集成功！")
        else:
            print("\n⚠️ 未采集到数据企业，建议：")
            print("  1. 确认该镇街是否有科技园区/产业园区")
            print("  2. 尝试搜索其他镇街（如桂城街道）")
            print("  3. 尝试其他数据分类（如数据技术、数据服务）")
    except Exception as e:
        print(f"\n❌ 采集失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()