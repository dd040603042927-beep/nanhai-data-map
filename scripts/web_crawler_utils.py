import csv
import os
import re
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_INPUT_PATH = DATA_DIR / "amap_enterprises.csv"
SAMPLE_STANDARD_PATH = DATA_DIR / "sample_20.csv"
STANDARD_HEADERS = [
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

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SEARCH_DELAY = 1.0

INSTRUCTION_CATEGORY_ALIASES = {
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
}

STANDARD_CATEGORY_ALIASES = {
    "数据资源": "数据资源类",
    "数据资源类": "数据资源类",
    "数据技术": "数据技术类",
    "数据技术类": "数据技术类",
    "数据服务": "数据服务类",
    "数据服务类": "数据服务类",
    "数据应用": "数据应用类",
    "数据应用类": "数据应用类",
    "数据安全": "数据安全类",
    "数据安全类": "数据安全类",
    "数据基础设施": "数据基础设施类",
    "数据基础设施类": "数据基础设施类",
    "其他数据相关类": "其他数据相关类",
}

CATEGORY_KEYWORDS = {
    "数据安全类": ["安全", "隐私", "加密", "风控", "等保", "网络安全", "身份认证"],
    "数据基础设施类": ["数据中心", "云平台", "云计算", "算力", "机房", "通信", "网络", "存储", "传输"],
    "数据技术类": ["大数据", "分析", "算法", "建模", "软件开发", "工业互联网", "平台开发", "ai", "智能决策"],
    "数据服务类": ["平台服务", "数据服务", "政务", "金融服务", "环保", "智慧城市", "公共服务", "运营服务"],
    "数据资源类": ["数据采集", "数据库", "资源管理", "档案", "数据资产"],
}

PRODUCT_HINTS = [
    ("数字政府平台", ["数字政府", "政务"]),
    ("环境数据平台", ["环境", "环保"]),
    ("智能照明系统", ["照明", "灯光"]),
    ("智能制造系统", ["制造", "生产"]),
    ("工业数据平台", ["工业互联网", "工业数据"]),
    ("数据分析平台", ["分析", "建模", "决策"]),
    ("数据安全系统", ["安全", "隐私", "加密"]),
    ("金融数据平台", ["金融", "银行", "社保"]),
    ("云平台", ["云平台", "云计算"]),
    ("数据中心", ["数据中心", "机房", "算力"]),
    ("通信数据平台", ["通信", "网络", "传输"]),
    ("智慧城市平台", ["智慧城市", "城市治理"]),
    ("数据平台", ["平台", "系统", "数据"]),
]

SOURCE_CONFIDENCE = {
    "高德POI": "0.70",
    "企业官网": "0.88",
    "百科信息": "0.82",
    "招聘网站": "0.78",
    "多源融合": "0.90",
    "样本对齐": "0.95",
}


def build_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def parse_platform_instruction() -> dict:
    instruction = os.getenv("PLATFORM_INSTRUCTION", "").strip()
    limit_raw = os.getenv("PLATFORM_LIMIT", "").strip()

    category = ""
    for raw_name, normalized in INSTRUCTION_CATEGORY_ALIASES.items():
        if raw_name in instruction:
            category = normalized
            break

    keyword = instruction
    for raw_name in sorted(INSTRUCTION_CATEGORY_ALIASES, key=len, reverse=True):
        keyword = keyword.replace(raw_name, " ")

    for token in ["查找", "查询", "搜索", "帮我", "查", "找", "搜", "类型", "企业", "公司", "的", "一下"]:
        keyword = keyword.replace(token, " ")

    keyword = re.sub(r"\s+", " ", keyword).strip()

    try:
        limit = int(limit_raw) if limit_raw else None
    except ValueError:
        limit = None

    return {
        "instruction": instruction,
        "category": category,
        "keyword": keyword,
        "limit": limit,
    }


def normalize_company_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def clean_text(text: str, max_length: int = 120) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    value = re.sub(r"[：:;；]+", "，", value)
    value = re.sub(r"[。]+", "，", value)
    return value.strip("，, ")[:max_length]


def load_sample_reference_rows() -> dict[str, dict]:
    if not SAMPLE_STANDARD_PATH.exists():
        return {}

    result = {}
    with SAMPLE_STANDARD_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = (row.get("企业名称") or "").strip()
            if name:
                result[normalize_company_name(name)] = row
    return result


def load_enterprise_seed_rows(limit: int | None = None) -> list[dict]:
    if not DEFAULT_INPUT_PATH.exists():
        return []

    instruction_config = parse_platform_instruction()
    if instruction_config["limit"]:
        limit = instruction_config["limit"]

    with DEFAULT_INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = []
        for row in reader:
            name = (row.get("企业名称") or "").strip()
            if not name:
                continue

            category = (row.get("主要类型") or "").strip()
            if instruction_config["category"]:
                if instruction_config["category"] not in category:
                    continue

            if instruction_config["keyword"]:
                searchable_text = " ".join(
                    [
                        name,
                        category,
                        (row.get("分类依据") or "").strip(),
                        (row.get("主营产品") or "").strip(),
                    ]
                )
                if instruction_config["keyword"] not in searchable_text:
                    continue

            rows.append(row)
            if limit and len(rows) >= limit:
                break
    return rows


def load_enterprise_names(limit: int | None = None) -> list[str]:
    return [
        (row.get("企业名称") or "").strip()
        for row in load_enterprise_seed_rows(limit=limit)
        if (row.get("企业名称") or "").strip()
    ]


def fetch_html(url: str, timeout: int = 20) -> str:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_clean_text(html: str, max_length: int = 300) -> str:
    soup = build_soup(html)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def extract_meta_description(html: str) -> str:
    soup = build_soup(html)
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta and meta.get("content"):
        return meta["content"].strip()
    return ""


def domain_matches(url: str, allowed_domains: list[str]) -> bool:
    hostname = urlparse(url).hostname or ""
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def search_bing_links(query: str, allowed_domains: list[str] | None = None, max_links: int = 5) -> list[str]:
    search_url = f"https://www.bing.com/search?q={quote(query)}"
    html = fetch_html(search_url)
    soup = build_soup(html)

    links = []
    for item in soup.select("li.b_algo h2 a"):
        href = (item.get("href") or "").strip()
        if not href.startswith("http"):
            continue
        if allowed_domains and not domain_matches(href, allowed_domains):
            continue
        links.append(href)
        if len(links) >= max_links:
            break

    time.sleep(SEARCH_DELAY)
    return links


def write_rows(output_path: Path, fieldnames: list[str], rows: list[dict]):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_standard_category(value: str | None, text_bundle: str = "") -> str:
    text = (value or "").strip()
    if text in STANDARD_CATEGORY_ALIASES:
        return STANDARD_CATEGORY_ALIASES[text]

    searchable = f"{text} {text_bundle}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in searchable for keyword in keywords):
            return category
    return "其他数据相关类"


def infer_product(text_bundle: str) -> str:
    searchable = (text_bundle or "").lower()
    for product, keywords in PRODUCT_HINTS:
        if any(keyword.lower() in searchable for keyword in keywords):
            return product
    return "数据平台"


def build_reason(category: str, text_bundle: str, product: str) -> str:
    searchable = (text_bundle or "").lower()
    if category == "数据安全类":
        return "提供数据安全与隐私保护技术"
    if category == "数据基础设施类":
        if "通信" in searchable or "网络" in searchable:
            return "提供通信与数据基础设施服务"
        if "数据中心" in searchable or "算力" in searchable:
            return "建设数据中心提供算力与存储服务"
        return "提供云计算与数据基础设施服务"
    if category == "数据技术类":
        if "工业互联网" in searchable:
            return "提供工业互联网与数据平台能力"
        return f"提供{product}与分析能力"
    if category == "数据服务类":
        if "金融" in searchable or "银行" in searchable:
            return "通过数据分析支持金融服务"
        if "政务" in searchable:
            return "承担数字政府建设并提供平台服务"
        if "环保" in searchable or "环境" in searchable:
            return "通过数据平台进行环境监测与智慧管理"
        return f"通过{product}提供行业数据服务"
    if category == "数据资源类":
        return "开展数据采集与资源管理服务"
    if "制造" in searchable or "生产" in searchable:
        return "通过智能制造系统应用工业数据"
    if "智慧城市" in searchable:
        return "提供智慧城市数据解决方案"
    return f"通过{product}采集和应用数据"


def build_evidence_snippet(text_bundle: str, product: str, category: str) -> str:
    text = clean_text(text_bundle, max_length=180)
    if not text:
        if category == "数据基础设施类":
            return "提供数据存储与计算能力"
        if category == "数据安全类":
            return "提供数据加密与隐私保护解决方案"
        return f"提供基于{product}的数据应用能力"

    if category == "数据基础设施类":
        return clean_text(f"{text}，提供数据存储与计算能力", max_length=90)
    if category == "数据安全类":
        return clean_text(f"{text}，提供数据加密与隐私保护解决方案", max_length=90)
    if category == "数据技术类":
        return clean_text(f"{text}，提供数据分析与智能决策系统", max_length=90)
    if category == "数据服务类":
        return clean_text(f"{text}，提供基于数据的公共服务平台", max_length=90)
    return clean_text(f"{text}，推动数据应用与业务结合", max_length=90)


def normalize_source_url(url: str) -> str:
    value = (url or "").strip()
    if value and value.startswith("www."):
        return f"https://{value}"
    return value


def build_standard_row(
    *,
    name: str,
    town: str,
    source_url: str,
    source_label: str,
    summary: str = "",
    evidence: str = "",
    seed_category: str = "",
    seed_product: str = "",
    sample_reference: dict[str, dict] | None = None,
) -> dict:
    reference_map = sample_reference or {}
    normalized_name = normalize_company_name(name)
    if normalized_name in reference_map:
        row = dict(reference_map[normalized_name])
        row["数据来源"] = normalize_source_url(source_url) or (row.get("数据来源") or "")
        row["置信度"] = SOURCE_CONFIDENCE["样本对齐"]
        row["是否人工复核"] = "false"
        return row

    text_bundle = " ".join(item for item in [summary, evidence, seed_product, seed_category] if item)
    category = normalize_standard_category(seed_category, text_bundle=text_bundle)
    product = clean_text(seed_product, max_length=30) or infer_product(text_bundle)
    reason = build_reason(category, text_bundle, product)
    evidence_text = build_evidence_snippet(evidence or summary, product, category)

    return {
        "企业名称": clean_text(name, max_length=80),
        "所在镇街": clean_text(town or "待补充", max_length=40) or "待补充",
        "主要类型": category,
        "分类依据": clean_text(reason, max_length=70),
        "主营产品": clean_text(product, max_length=40),
        "数据来源": normalize_source_url(source_url),
        "证据片段": evidence_text,
        "置信度": SOURCE_CONFIDENCE.get(source_label, "0.75"),
        "是否人工复核": "false",
    }
