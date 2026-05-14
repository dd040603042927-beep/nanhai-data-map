import csv
import os
import time
from pathlib import Path

import requests
from web_crawler_utils import build_standard_row, load_sample_reference_rows

BASE_DIR = Path(__file__).resolve().parent.parent


def load_key_from_env_files() -> str:
    for env_path in [BASE_DIR / ".env.local", BASE_DIR / ".env"]:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            if key.strip() == "AMAP_WEB_KEY":
                return value.strip().strip("'\"")
    return ""


def resolve_amap_key() -> str:
    return os.getenv("AMAP_WEB_KEY", "").strip() or load_key_from_env_files()


AMAP_KEY = resolve_amap_key()

# 建议你把这里改成南海区对应的 adcode；官方文档明确建议优先使用 adcode 精确到区县
# 如果你暂时没填 adcode，也可以先用 city + citylimit 的方式测试
TARGET_CITY = "440605"   # 南海区常用 adcode，建议你自己在高德控制台/城市代码表再核对一遍
CITY_LIMIT = "true"

OUTPUT_PATH = Path("data/amap_enterprises.csv")

KEYWORDS = [
    "大数据",
    "数据服务",
    "数据安全",
    "工业互联网",
    "智慧城市",
    "数据中心",
    "云平台",
    "软件开发",
    "信息科技",
    "数字化",
]

TOWN_ALIASES = {
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

CATEGORY_SEARCH_KEYWORDS = {
    "数据资源": ["数据采集", "数据治理", "数据库", "数据资产", "数据标注"],
    "数据技术": ["大数据", "软件开发", "人工智能", "数据分析", "工业互联网"],
    "数据服务": ["数据服务", "智慧城市", "数字政府", "信息服务", "数据运营"],
    "数据应用": ["智慧城市", "工业互联网", "智能制造", "物联网", "数字化"],
    "数据安全": ["数据安全", "网络安全", "信息安全", "隐私保护", "安全服务"],
    "数据基础设施": ["数据中心", "云平台", "云计算", "通信", "算力"],
}

URL = "https://restapi.amap.com/v3/place/text"


def parse_instruction_keywords() -> list[str]:
    instruction = os.getenv("PLATFORM_INSTRUCTION", "").strip()
    if not instruction:
        return KEYWORDS

    town = ""
    for raw_name, short_name in sorted(TOWN_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if raw_name in instruction:
            town = short_name
            break

    candidates = []
    for category, keywords in CATEGORY_SEARCH_KEYWORDS.items():
        if category in instruction:
            candidates.extend(keywords)

    for keyword in KEYWORDS:
        if keyword in instruction:
            candidates.append(keyword)

    keyword_text = instruction
    for raw_name in sorted(list(TOWN_ALIASES) + list(CATEGORY_SEARCH_KEYWORDS), key=len, reverse=True):
        keyword_text = keyword_text.replace(raw_name, " ")
    for token in ["请帮我", "帮我找", "帮我", "帮忙", "查找", "查询", "搜索", "采集", "找", "搜", "查", "一下", "企业", "公司", "单位", "名单", "类型", "类别", "的"]:
        keyword_text = keyword_text.replace(token, " ")
    keyword_text = " ".join(keyword_text.split())
    if keyword_text:
        candidates.insert(0, keyword_text)

    if not candidates:
        candidates = KEYWORDS

    seen = set()
    ordered = []
    for item in candidates:
        value = item.strip()
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)

    if town:
        town_scoped = [f"{town} {keyword}" for keyword in ordered]
        ordered = town_scoped + ordered

    return ordered[:12]


def fetch_poi_by_keyword(keyword: str, max_pages: int = 3, offset: int = 20):
    """
    高德官方文档说明：
    - keywords 为查询关键字
    - city 可传城市中文 / citycode / adcode
    - citylimit=true 可尽量只返回指定区域数据
    - page / offset 支持分页
    - 官方建议 offset 不超过 25
    - 同一请求翻页最多支持获取 200 条
    """
    all_pois = []

    for page in range(1, max_pages + 1):
        params = {
            "key": AMAP_KEY,
            "keywords": keyword,
            "city": TARGET_CITY,
            "citylimit": CITY_LIMIT,
            "page": page,
            "offset": offset,
            "extensions": "base",
        }

        resp = requests.get(URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "1":
            print(f"[错误] keyword={keyword}, page={page}, info={data.get('info')}")
            break

        pois = data.get("pois", [])
        if not pois:
            break

        all_pois.extend(pois)

        # 稍微停一下，避免请求太密
        time.sleep(0.3)

    return all_pois


def guess_category(name: str, type_text: str, keyword: str) -> str:
    text = f"{name} {type_text} {keyword}"

    if any(x in text for x in ["数据安全", "安全"]):
        return "数据安全类"
    if any(x in text for x in ["数据中心", "云平台", "云计算", "机房"]):
        return "数据基础设施类"
    if any(x in text for x in ["工业互联网", "平台", "软件", "分析", "AI", "算法", "建模"]):
        return "数据技术类"
    if any(x in text for x in ["数据服务", "智慧城市", "数字化服务", "信息服务"]):
        return "数据服务类"
    return "其他数据相关类"


def build_rows():
    rows = []
    seen = set()
    active_keywords = parse_instruction_keywords()
    sample_reference = load_sample_reference_rows()
    max_rows = int(os.getenv("PLATFORM_LIMIT", "50") or "50")

    for keyword in active_keywords:
        pois = fetch_poi_by_keyword(keyword)

        for poi in pois:
            name = (poi.get("name") or "").strip()
            address = (poi.get("address") or "").strip()
            type_text = (poi.get("type") or "").strip()
            location = (poi.get("location") or "").strip()

            if not name:
                continue

            # 去重：先按企业名去重
            if name in seen:
                continue
            seen.add(name)

            category = guess_category(name, type_text, keyword)
            row = build_standard_row(
                name=name,
                town=address if address else "待补充",
                seed_category=category,
                seed_product=type_text if type_text else keyword,
                source_url=f"https://restapi.amap.com/v3/place/text?keywords={keyword}&city={TARGET_CITY}",
                source_label="高德POI",
                summary=f"{keyword}；POI类型：{type_text}",
                evidence=f"名称：{name}；地址：{address}；类型：{type_text}；坐标：{location}",
                sample_reference=sample_reference,
            )
            rows.append(row)
            if len(rows) >= max_rows:
                return rows

    return rows


def save_csv(rows):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "企业名称",
        "所在镇街",
        "主要类型",
        "分类依据",
        "主营产品",
        "数据来源",
        "证据片段",
        "置信度",
        "是否人工复核",
    ]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"已写出: {OUTPUT_PATH}")
    print(f"共生成 {len(rows)} 条候选企业数据")


def main():
    if not AMAP_KEY:
        raise RuntimeError(
            "缺少高德 Key。请在启动后端的环境变量中设置 AMAP_WEB_KEY，"
            "或在项目根目录 .env.local / .env 中写入 AMAP_WEB_KEY=你的Key"
        )

    rows = build_rows()
    save_csv(rows)


if __name__ == "__main__":
    main()
