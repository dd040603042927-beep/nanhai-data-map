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

URL = "https://restapi.amap.com/v3/place/text"


def parse_instruction_keywords() -> list[str]:
    instruction = os.getenv("PLATFORM_INSTRUCTION", "").strip()
    if not instruction:
        return KEYWORDS

    candidates = []
    for keyword in KEYWORDS:
        if keyword in instruction:
            candidates.append(keyword)

    if "数据服务" in instruction:
        candidates.append("数据服务")
    if "数据安全" in instruction:
        candidates.append("数据安全")
    if "数据技术" in instruction:
        candidates.extend(["大数据", "软件开发"])
    if "数据基础设施" in instruction:
        candidates.extend(["数据中心", "云平台"])

    if candidates:
        seen = set()
        ordered = []
        for item in candidates:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    return [instruction]


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
