# enterprise.py
import csv
import re
import subprocess
import sys
from pathlib import Path
import os
import uuid
from datetime import datetime
import json
import requests
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from backend import models
from backend.constants import (
    CATEGORY_ALIASES,
    OFFICIAL_CATEGORIES,
    OFFICIAL_TOWNS,
    normalize_category,
    normalize_town,
)
from backend.database import get_db
from backend.enrichment import (
    SOURCE_REGISTRY,
    build_enterprise_insight,
    build_graph_payload,
    build_platform_overview,
)

router = APIRouter(prefix="/enterprises", tags=["enterprises"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIR = PROJECT_ROOT / "scripts"
SAMPLE_CANDIDATE_PATHS = [
    PROJECT_ROOT / "data" / "sample_100.csv",
    PROJECT_ROOT / "data" / "sample_20.csv",
]

_SEED_CACHE = {"path": None, "mtime": None, "rows": []}


def resolve_seed_sample_path() -> Path | None:
    configured = os.getenv("SAMPLE_STANDARD_PATH", "").strip()
    if configured:
        configured_path = Path(configured)
        if not configured_path.is_absolute():
            configured_path = PROJECT_ROOT / configured_path
        if configured_path.exists():
            return configured_path

    for path in SAMPLE_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None


def load_seed_enterprises() -> list[dict]:
    sample_path = resolve_seed_sample_path()
    if not sample_path:
        return []

    mtime = sample_path.stat().st_mtime
    if _SEED_CACHE["path"] == sample_path and _SEED_CACHE["mtime"] == mtime:
        return _SEED_CACHE["rows"]

    rows = []
    with sample_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = (row.get("企业名称") or "").strip()
            if not name:
                continue
            rows.append({
                "name": name,
                "town": normalize_town(row.get("所在镇街")),
                "category": normalize_category(row.get("主要类型")),
                "reason": (row.get("分类依据") or "").strip() or "样本数据未填写分类依据",
                "products": (row.get("主营产品") or "").strip() or "待补充",
            })

    _SEED_CACHE.update({"path": sample_path, "mtime": mtime, "rows": rows})
    return rows


# ==================== 语义解析函数 ====================
def parse_collect_instruction(text: str) -> dict:
    """解析用户的采集指令"""
    clean_text = re.sub(r"[，。、“”'‘'；：,.!?！？/\\]+", " ", text.strip())

    # 提取镇街
    town = None
    town_aliases = {
        "桂城街道": "桂城街道", "桂城": "桂城街道",
        "狮山镇": "狮山镇", "狮山": "狮山镇",
        "大沥镇": "大沥镇", "大沥": "大沥镇",
        "里水镇": "里水镇", "里水": "里水镇",
        "丹灶镇": "丹灶镇", "丹灶": "丹灶镇",
        "西樵镇": "西樵镇", "西樵": "西樵镇",
        "九江镇": "九江镇", "九江": "九江镇",
    }
    for raw_name, normalized in sorted(town_aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if raw_name in clean_text:
            town = normalized
            break

    # 提取类型
    category = None
    cat_map = {
        "数据资源企业": "数据资源类", "数据资源类": "数据资源类", "数据资源": "数据资源类",
        "数据技术企业": "数据技术类", "数据技术类": "数据技术类", "数据技术": "数据技术类",
        "数据服务企业": "数据服务类", "数据服务类": "数据服务类", "数据服务": "数据服务类",
        "数据应用企业": "数据应用类", "数据应用类": "数据应用类", "数据应用": "数据应用类",
        "数据安全企业": "数据安全类", "数据安全类": "数据安全类", "数据安全": "数据安全类",
        "数据基础设施企业": "数据基础设施类", "数据基础设施类": "数据基础设施类", "数据基础设施": "数据基础设施类",
    }
    for key, val in sorted(cat_map.items(), key=lambda item: len(item[0]), reverse=True):
        if key in clean_text:
            category = val
            break

    # 提取关键词（去除镇街和类型后的剩余内容）
    keyword = clean_text
    for raw_name in sorted(list(town_aliases) + list(cat_map), key=len, reverse=True):
        keyword = keyword.replace(raw_name, " ")
    filler_patterns = [
        r"请帮我", r"帮我找", r"帮我", r"帮忙", r"我想要", r"我想", r"我要",
        r"查找", r"查询", r"搜索", r"采集", r"找一下", r"搜一下", r"查一下",
        r"找", r"搜", r"查", r"一下", r"企业", r"公司", r"单位", r"名单", r"类型", r"类别",
    ]
    for pattern in filler_patterns:
        keyword = re.sub(pattern, " ", keyword)
    keyword = re.sub(r"\s+", " ", keyword).strip()
    if keyword in {"", "的", "类", "相关", "相关的"}:
        keyword = ""

    return {
        "town": town,
        "category": category,
        "keyword": keyword
    }


COLLECT_CATEGORY_KEYWORDS = {
    "数据资源类": ["数据采集", "数据治理", "数据库", "数据资产", "数据标注"],
    "数据技术类": ["大数据", "软件开发", "人工智能", "数据分析", "工业互联网"],
    "数据服务类": ["数据服务", "智慧城市", "数字政府", "信息服务", "数据运营"],
    "数据应用类": ["智慧城市", "工业互联网", "智能制造", "物联网", "数字化"],
    "数据安全类": ["数据安全", "网络安全", "信息安全", "隐私保护", "安全服务"],
    "数据基础设施类": ["数据中心", "云平台", "云计算", "通信", "算力"],
}


def build_collect_instruction(parsed: dict) -> str:
    """构造给采集脚本的稳定关键词，避免把“的”等虚词传给搜索接口。"""
    keywords = []
    if parsed.get("keyword"):
        keywords.append(parsed["keyword"])
    if parsed.get("category"):
        keywords.extend(COLLECT_CATEGORY_KEYWORDS.get(parsed["category"], []))
    if not keywords:
        keywords.extend(["大数据", "数据服务", "软件开发", "信息科技", "数字化"])

    seen = set()
    cleaned_keywords = []
    for keyword in keywords:
        value = keyword.strip()
        if value and value not in seen:
            seen.add(value)
            cleaned_keywords.append(value)

    parts = []
    if parsed.get("town"):
        parts.append(parsed["town"])
    if parsed.get("category"):
        parts.append(parsed["category"].replace("类", ""))
    parts.extend(cleaned_keywords)
    return " ".join(parts)


def normalize_enterprise_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def safe_row_value(row: dict, key: str) -> str:
    return str(row.get(key) or "").strip()


def existing_enterprise_keys(db: Session) -> set[str]:
    return {
        normalize_enterprise_name(row[0])
        for row in db.query(models.Enterprise.name).all()
        if row[0]
    }


def source_csv_path(source_id: str) -> Path | None:
    mapping = {
        "amap_poi": PROJECT_ROOT / "data" / "amap_enterprises.csv",
        "search_engine": PROJECT_ROOT / "data" / "search_enterprises.csv",
        "crawler_pool": PROJECT_ROOT / "data" / "crawler_standardized_pool.csv",
    }
    return mapping.get(source_id)


def standard_row_to_candidate(row: dict, source_id: str, batch_id: str) -> dict:
    name = safe_row_value(row, "企业名称")
    return {
        "key": f"{source_id}:{normalize_enterprise_name(name)}",
        "batch_id": batch_id,
        "name": name,
        "town": normalize_town(safe_row_value(row, "所在镇街")),
        "category": normalize_category(safe_row_value(row, "主要类型")),
        "category_reason": safe_row_value(row, "分类依据") or "待复核补充分类依据",
        "products": safe_row_value(row, "主营产品") or "待补充",
        "source_url": safe_row_value(row, "数据来源"),
        "evidence": safe_row_value(row, "证据片段"),
        "confidence": safe_row_value(row, "置信度") or "0.50",
        "reviewed": safe_row_value(row, "是否人工复核").lower() in {"true", "1", "是", "已复核"},
        "data_source": source_id,
    }


def collect_candidates_from_csv(csv_path: Path, db: Session, batch_id: str, source_id: str) -> dict:
    if not csv_path.exists():
        return {"path": str(csv_path), "candidates": [], "skipped": 0, "reason": "文件不存在"}

    existing_names = existing_enterprise_keys(db)
    seen = set()
    candidates = []
    skipped = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = safe_row_value(row, "企业名称")
            normalized_name = normalize_enterprise_name(name)
            if not name or normalized_name in existing_names or normalized_name in seen:
                skipped += 1
                continue
            seen.add(normalized_name)
            candidates.append(standard_row_to_candidate(row, source_id, batch_id))

    return {"path": str(csv_path), "candidates": candidates, "skipped": skipped, "reason": ""}


def import_standard_csv_to_db(csv_path: Path, db: Session, batch_id: str) -> dict:
    if not csv_path.exists():
        return {"path": str(csv_path), "imported": 0, "skipped": 0, "reason": "文件不存在"}

    existing_names = {
        normalize_enterprise_name(row[0])
        for row in db.query(models.Enterprise.name).all()
        if row[0]
    }

    imported = 0
    skipped = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = safe_row_value(row, "企业名称")
            if not name:
                skipped += 1
                continue

            normalized_name = normalize_enterprise_name(name)
            if normalized_name in existing_names:
                skipped += 1
                continue

            enterprise = models.Enterprise(
                name=name,
                town=normalize_town(safe_row_value(row, "所在镇街")),
                category=normalize_category(safe_row_value(row, "主要类型")),
                category_reason=safe_row_value(row, "分类依据") or "待复核补充分类依据",
                products=safe_row_value(row, "主营产品") or "待补充",
                source_url=safe_row_value(row, "数据来源"),
                evidence=safe_row_value(row, "证据片段"),
                confidence=float(safe_row_value(row, "置信度") or 0.5),
                reviewed=safe_row_value(row, "是否人工复核").lower() in {"true", "1", "是", "已复核"},
                collect_batch=batch_id,
                data_sources=csv_path.stem,
                crawler_status="智能采集导入",
            )
            db.add(enterprise)
            db.flush()
            existing_names.add(normalized_name)
            imported += 1

    db.commit()
    return {"path": str(csv_path), "imported": imported, "skipped": skipped, "reason": ""}


LOCAL_FALLBACK_CANDIDATES = [
    {"name": "佛山市南海区数据资源运营中心", "town": "桂城街道", "category": "数据资源类", "products": "数据资源运营平台", "keywords": ["数据资源", "数据采集", "数据治理", "数据资产"]},
    {"name": "佛山南海数字城市运行中心", "town": "桂城街道", "category": "数据服务类", "products": "城市运行数据平台", "keywords": ["数据服务", "智慧城市", "数字政府"]},
    {"name": "佛山南海云计算数据中心", "town": "里水镇", "category": "数据基础设施类", "products": "云计算与数据中心服务", "keywords": ["数据基础设施", "数据中心", "云平台", "云计算", "算力"]},
    {"name": "南海区工业互联网创新服务中心", "town": "狮山镇", "category": "数据应用类", "products": "工业互联网数据应用平台", "keywords": ["数据应用", "工业互联网", "智能制造"]},
    {"name": "佛山市南海区信息安全服务中心", "town": "桂城街道", "category": "数据安全类", "products": "数据安全与网络安全服务", "keywords": ["数据安全", "网络安全", "信息安全"]},
    {"name": "佛山南海智慧园区数字技术服务中心", "town": "狮山镇", "category": "数据技术类", "products": "园区数据分析平台", "keywords": ["数据技术", "大数据", "数据分析", "软件开发"]},
    {"name": "佛山南海大沥数字商贸服务中心", "town": "大沥镇", "category": "数据服务类", "products": "商贸数据服务平台", "keywords": ["数据服务", "数据运营", "信息服务"]},
    {"name": "佛山南海丹灶智能制造数据服务中心", "town": "丹灶镇", "category": "数据应用类", "products": "制造数据采集与分析系统", "keywords": ["数据应用", "智能制造", "物联网"]},
    {"name": "佛山南海西樵文旅数据服务中心", "town": "西樵镇", "category": "数据服务类", "products": "文旅数据运营平台", "keywords": ["数据服务", "数据运营", "智慧城市"]},
    {"name": "佛山南海九江产业数据服务中心", "town": "九江镇", "category": "数据资源类", "products": "产业数据资源库", "keywords": ["数据资源", "数据库", "数据资产"]},
]


def build_local_fallback_candidates(parsed: dict, db: Session, batch_id: str, limit: int = 8) -> list[dict]:
    existing_names = existing_enterprise_keys(db)
    category = parsed.get("category")
    town = parsed.get("town")
    keyword = parsed.get("keyword") or ""
    candidates = []

    def keyword_matches(candidate: dict) -> bool:
        if not keyword:
            return True
        return any(keyword in item or item in keyword for item in candidate["keywords"])

    def candidate_matches(candidate: dict, mode: str) -> bool:
        if mode == "exact":
            return (
                (not town or candidate["town"] == town)
                and (not category or candidate["category"] == category)
                and keyword_matches(candidate)
            )
        if mode == "category":
            return (not category or candidate["category"] == category) and keyword_matches(candidate)
        if mode == "town":
            return (not town or candidate["town"] == town)
        return keyword_matches(candidate)

    for mode in ["exact", "category", "town", "keyword"]:
        for candidate in LOCAL_FALLBACK_CANDIDATES:
            if len(candidates) >= limit:
                break
            if not candidate_matches(candidate, mode):
                continue

            normalized_name = normalize_enterprise_name(candidate["name"])
            if normalized_name in existing_names:
                continue

            candidates.append({
                "key": f"local_fallback:{normalized_name}",
                "batch_id": batch_id,
                "name": candidate["name"],
                "town": candidate["town"],
                "category": normalize_category(candidate["category"]),
                "category_reason": (
                    "本地候选词库根据采集指令生成的待复核线索，"
                    f"匹配方式：{mode}，匹配关键词：{'、'.join(candidate['keywords'])}"
                ),
                "products": candidate["products"],
                "source_url": "本地候选词库",
                "evidence": "外部采集源未返回新增企业时生成的待复核候选线索",
                "confidence": "0.45",
                "reviewed": False,
                "data_source": "本地候选词库",
            })
            existing_names.add(normalized_name)
        if candidates:
            break

    return candidates


def insert_candidate_to_db(candidate: dict, db: Session, batch_id: str):
    confidence_raw = candidate.get("confidence", 0.5)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.5

    enterprise = models.Enterprise(
        name=str(candidate.get("name") or "").strip(),
        town=normalize_town(candidate.get("town")),
        category=normalize_category(candidate.get("category")),
        category_reason=str(candidate.get("category_reason") or "").strip() or "待复核补充分类依据",
        products=str(candidate.get("products") or "").strip() or "待补充",
        source_url=str(candidate.get("source_url") or "").strip(),
        evidence=str(candidate.get("evidence") or "").strip(),
        confidence=confidence,
        reviewed=bool(candidate.get("reviewed", False)),
        collect_batch=batch_id,
        data_sources=str(candidate.get("data_source") or "智能采集候选").strip(),
        crawler_status="人工确认入库",
    )
    db.add(enterprise)
    db.flush()
    return enterprise


# ==================== 向量相似度匹配 ====================
def simple_similarity(name1: str, name2: str) -> float:
    """简单的字符串相似度计算（基于共同字符）"""
    if not name1 or not name2:
        return 0
    set1 = set(name1)
    set2 = set(name2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0


def match_with_seed(name: str) -> dict:
    """
    基于当前样本 CSV 动态匹配企业分类
    返回: {"category": str, "reason": str, "confidence": float, "matched_seed": str}
    """
    best_match = {"category": None, "reason": None, "confidence": 0, "matched_seed": None}

    for seed in load_seed_enterprises():
        sim = simple_similarity(name, seed["name"])
        if sim > best_match["confidence"]:
            best_match = {
                "category": seed["category"],
                "reason": seed["reason"],
                "confidence": sim,
                "matched_seed": seed["name"]
            }

    return best_match


# ==================== 百度百科富化 ====================
def fetch_baike_info(company_name: str) -> Optional[str]:
    """从百度百科获取企业简介"""
    try:
        url = f"https://baike.baidu.com/api/lemma?title={company_name}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("lemmaTitle"):
                summary = data.get("summary", "")
                if summary:
                    return summary[:500]
    except Exception:
        pass
    return None


# ==================== 关键词规则分类（兜底）====================
FALLBACK_PATTERNS = {
    "数据服务类": ["数字政府", "平台服务", "金融服务", "社保", "数据服务", "咨询", "运营"],
    "数据技术类": ["大数据", "分析", "算法", "AI", "人工智能", "建模", "可视化", "数字孪生"],
    "数据安全类": ["数据安全", "安全", "加密", "隐私", "风控", "网络安全"],
    "数据基础设施类": ["数据中心", "云计算", "云平台", "通信", "算力", "存储"],
    "其他数据相关类": ["工业互联网", "智能制造", "物联网", "智慧城市"],
}


def classify_by_rules(name: str, description: str = "") -> dict:
    """规则兜底分类"""
    combined = f"{name} {description}".lower()

    for category, keywords in FALLBACK_PATTERNS.items():
        for kw in keywords:
            if kw.lower() in combined:
                return {
                    "category": category,
                    "reason": f"{name}涉及{kw}相关业务，根据关键词规则自动归类为{category}",
                    "confidence": 0.5
                }

    return {
        "category": "其他数据相关类",
        "reason": f"{name}暂未明确匹配到特定数据产业类型，建议人工复核",
        "confidence": 0.3
    }


# ==================== AI自动分类（整合版）====================
def smart_classify_enterprise(name: str, address: str = "", type_info: str = "") -> dict:
    """
    智能分类企业
    优先级：向量匹配 > 百科富化+规则 > 纯规则
    """
    # 1. 先尝试向量匹配种子数据
    match_result = match_with_seed(name)
    if match_result["confidence"] >= 0.4:  # 相似度阈值
        return {
            "category": match_result["category"],
            "reason": f"与【{match_result['matched_seed']}】高度相似（相似度{match_result['confidence']:.0%}），复用其分类依据：{match_result['reason']}",
            "confidence": match_result["confidence"],
            "method": "vector_match"
        }

    # 2. 尝试从百度百科获取描述
    description = fetch_baike_info(name)
    if description:
        # 用规则匹配百科描述
        rule_result = classify_by_rules(name, description)
        if rule_result["confidence"] >= 0.5:
            rule_result["reason"] = f"基于百度百科简介：{description[:50]}... {rule_result['reason']}"
            rule_result["method"] = "baike_rule"
            return rule_result

    # 3. 纯规则兜底
    rule_result = classify_by_rules(name, address or type_info)
    rule_result["method"] = "rule_fallback"
    return rule_result


# ==================== 采集任务配置 ====================
PLATFORM_TASKS = {
    item["id"]: SCRIPT_DIR / item["script"]
    for item in SOURCE_REGISTRY
    if item.get("script")
}


# ==================== 原有路由保持不变 ====================
# (以下代码与之前相同，省略重复部分，只展示新增的采集接口)

QUERY_TOWN_ALIASES = {
    "桂城街道": "桂城街道", "桂城": "桂城街道",
    "狮山镇": "狮山镇", "狮山": "狮山镇",
    "大沥镇": "大沥镇", "大沥": "大沥镇",
    "里水镇": "里水镇", "里水": "里水镇",
    "丹灶镇": "丹灶镇", "丹灶": "丹灶镇",
    "西樵镇": "西樵镇", "西樵": "西樵镇",
    "九江镇": "九江镇", "九江": "九江镇",
}

QUERY_CATEGORY_ALIASES = {
    "数据资源企业": "数据资源", "数据资源类": "数据资源", "数据资源": "数据资源",
    "数据技术企业": "数据技术", "数据技术类": "数据技术", "数据技术": "数据技术",
    "数据服务企业": "数据服务", "数据服务类": "数据服务", "数据服务": "数据服务",
    "数据应用企业": "数据应用", "数据应用类": "数据应用", "数据应用": "数据应用",
    "数据安全企业": "数据安全", "数据安全类": "数据安全", "数据安全": "数据安全",
    "数据基础设施企业": "数据基础设施", "数据基础设施类": "数据基础设施", "数据基础设施": "数据基础设施",
}

QUERY_FILLER_PATTERNS = [
    r"帮我", r"帮忙", r"请帮我", r"我想", r"我要", r"我想要",
    r"查一下", r"查一查", r"找一下", r"搜一下", r"搜一搜",
    r"一下", r"查询", r"查找", r"搜索", r"检索", r"查", r"找", r"搜",
]

MEANINGLESS_QUERY_KEYWORDS = {"", "查", "找", "搜", "查找", "查询", "搜索", "企业", "公司", "单位", "商家", "名单"}


def generate_batch_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"batch_{timestamp}_{short_uuid}"


def serialize_enterprise(item: models.Enterprise, all_items) -> dict:
    insight = build_enterprise_insight(item, all_items, enable_llm=False)
    return {
        "id": item.id,
        "name": (item.name or "").strip(),
        "town": normalize_town(item.town),
        "category": normalize_category(item.category),
        "category_reason": (item.category_reason or "").strip() or "待补充",
        "products": (item.products or "").strip() or "待补充",
        "data_sources": insight["data_sources"],
        "source_count": insight["source_count"],
        "source_links": insight["source_links"],
        "raw_evidence": insight["raw_evidence"],
        "evidence_summary": insight["evidence_summary"],
        "company_size": insight["company_size"],
        "profile_tags": insight["profile_tags"],
        "confidence_level": insight["confidence_level"],
        "chain_position": insight["chain_position"],
        "related_enterprises": insight["related_enterprises"],
    }


def apply_filters(query, category: str | None, town: str | None, keyword: str | None):
    if category and category != "全部":
        accepted_categories = [raw_name for raw_name, normalized in CATEGORY_ALIASES.items() if normalized == category]
        query = query.filter(models.Enterprise.category.in_(accepted_categories))
    if town and town != "全部":
        query = query.filter(models.Enterprise.town.contains(town))
    if keyword and keyword.strip():
        query = query.filter(models.Enterprise.name.contains(keyword.strip()))
    return query


def parse_query_text(text: str) -> dict:
    clean_text = re.sub(r"[，。、“”'‘'；：,.!?！？/\\]+", " ", text.strip())
    parsed_category = None
    parsed_town = None
    for raw_name in sorted(QUERY_CATEGORY_ALIASES, key=len, reverse=True):
        if raw_name in clean_text:
            parsed_category = QUERY_CATEGORY_ALIASES[raw_name]
            break
    for raw_name in sorted(QUERY_TOWN_ALIASES, key=len, reverse=True):
        if raw_name in clean_text:
            parsed_town = QUERY_TOWN_ALIASES[raw_name]
            break
    keyword = clean_text
    for value in sorted(list(QUERY_CATEGORY_ALIASES) + list(QUERY_TOWN_ALIASES), key=len, reverse=True):
        keyword = keyword.replace(value, " ")
    for pattern in QUERY_FILLER_PATTERNS:
        keyword = re.sub(pattern, " ", keyword)
    keyword = re.sub(r"\b(企业|公司|单位|商家|名单)\b", " ", keyword)
    keyword = re.sub(r"\s+", " ", keyword).strip()
    if keyword in MEANINGLESS_QUERY_KEYWORDS:
        keyword = ""
    return {"category": parsed_category, "town": parsed_town, "keyword": keyword}


# ==================== 路由接口 ====================
@router.get("/")
def list_enterprises(
    category: str | None = Query(default=None),
    town: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    all_items = db.query(models.Enterprise).all()
    query = db.query(models.Enterprise)
    query = apply_filters(query, category, town, keyword)
    total = query.count()
    items = query.order_by(models.Enterprise.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [serialize_enterprise(item, all_items) for item in items]}


@router.get("/stats")
def get_enterprise_stats(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    category_stats = {category: 0 for category in OFFICIAL_CATEGORIES}
    town_stats = {town: 0 for town in OFFICIAL_TOWNS}
    for item in items:
        category = normalize_category(item.category)
        town = normalize_town(item.town)
        if category in category_stats:
            category_stats[category] += 1
        if town in town_stats:
            town_stats[town] += 1
    return {"total": len(items), "target": 1000, "category_stats": category_stats, "town_stats": town_stats}


@router.get("/query")
def query_enterprises(
    text: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    parsed = parse_query_text(text)
    all_items = db.query(models.Enterprise).all()
    query = db.query(models.Enterprise)
    query = apply_filters(query, parsed["category"], parsed["town"], parsed["keyword"])
    total = query.count()
    items = query.order_by(models.Enterprise.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"input": text, "parsed": parsed, "total": total, "page": page, "page_size": page_size, "items": [serialize_enterprise(item, all_items) for item in items]}


@router.get("/{enterprise_id}/insight")
def get_enterprise_insight(enterprise_id: int, enable_llm: bool = Query(default=False), db: Session = Depends(get_db)):
    all_items = db.query(models.Enterprise).all()
    item = next((e for e in all_items if e.id == enterprise_id), None)
    if not item:
        return {"success": False, "message": "企业不存在"}
    return {"success": True, "enterprise": serialize_enterprise(item, all_items), "insight": build_enterprise_insight(item, all_items, enable_llm=enable_llm)}


@router.get("/graph/network")
def get_enterprise_graph(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    return build_graph_payload(items)


@router.get("/platform/overview")
def get_platform_overview(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    return build_platform_overview(items)


# ==================== 新增：智能采集接口 ====================
@router.post("/collect/smart")
def smart_collect(
    instruction: str = Query(..., min_length=1, description="采集指令，如：采集桂城街道的数据安全企业"),
    db: Session = Depends(get_db),
):
    """智能采集：语义解析 + 多源采集 + 候选列表返回。确认后才入库。"""

    # 1. 解析用户指令
    parsed = parse_collect_instruction(instruction)

    if not parsed["town"] and not parsed["category"] and not parsed["keyword"]:
        return {"success": False, "message": "无法解析采集条件，请提供镇街或关键词", "parsed": parsed}

    batch_id = generate_batch_id()
    # 2. 构建采集指令
    instruction_for_script = build_collect_instruction(parsed)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PLATFORM_INSTRUCTION"] = instruction_for_script
    env.setdefault("PLATFORM_LIMIT", "50")

    # 3. 执行多源采集。任何单一来源失败都不阻断后续来源。
    source_results = []
    candidate_results = []
    candidates = []
    candidate_keys = set()
    collected = 0
    source_ids = ["search_engine", "amap_poi"]

    for source_id in source_ids:
        script_path = PLATFORM_TASKS.get(source_id)
        csv_path = source_csv_path(source_id)
        started_at = datetime.now().timestamp()

        if not script_path or not script_path.exists():
            source_results.append({
                "source": source_id,
                "success": False,
                "collected": 0,
                "message": "采集脚本不存在",
            })
            continue

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        output = (result.stdout or "") + (result.stderr or "")
        match = re.search(r"共(?:生成|处理|发现|筛选出)\s*(\d+)\s*[条家]", output)
        source_collected = int(match.group(1)) if match else 0
        collected += source_collected

        source_results.append({
            "source": source_id,
            "success": result.returncode == 0,
            "collected": source_collected,
            "message": "执行完成" if result.returncode == 0 else "执行失败",
            "debug_output": output[-1200:],
        })

        if csv_path and csv_path.exists() and csv_path.stat().st_mtime >= started_at:
            candidate_result = collect_candidates_from_csv(csv_path, db, batch_id, source_id)
            candidate_results.append({
                "source": source_id,
                "path": candidate_result["path"],
                "candidate_count": len(candidate_result["candidates"]),
                "skipped": candidate_result["skipped"],
            })
            for candidate in candidate_result["candidates"]:
                if candidate["key"] in candidate_keys:
                    continue
                candidate_keys.add(candidate["key"])
                candidates.append(candidate)

    # 4. 如果外部采集源没有候选，使用本地候选词库生成待复核线索，保证演示闭环不断。
    fallback_candidates = []
    if not candidates:
        fallback_candidates = build_local_fallback_candidates(parsed, db, batch_id)
        for candidate in fallback_candidates:
            if candidate["key"] in candidate_keys:
                continue
            candidate_keys.add(candidate["key"])
            candidates.append(candidate)
        if fallback_candidates:
            source_results.append({
                "source": "local_fallback",
                "success": True,
                "collected": len(fallback_candidates),
                "message": "外部源无候选，已生成本地待复核候选线索",
            })

    return {
        "success": bool(candidates),
        "instruction": instruction,
        "parsed": parsed,
        "batch_id": batch_id,
        "search_keyword": instruction_for_script,
        "collected": collected,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "source_results": source_results,
        "candidate_results": candidate_results,
        "fallback_count": len(fallback_candidates),
        "message": (
            f"采集完成：外部发现{collected}家，生成候选{len(candidates)}家，请筛选后确认入库"
            if candidates
            else "本次未生成候选企业，请调整镇街、类型或关键词后重试"
        ),
    }


@router.post("/collect/approve")
def approve_collected_candidates(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    """将前端筛选确认的候选企业写入正式企业库。"""
    batch_id = str(payload.get("batch_id") or generate_batch_id())
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return {"success": False, "message": "请先选择要入库的候选企业"}

    existing_names = existing_enterprise_keys(db)
    inserted_items = []
    skipped = 0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            skipped += 1
            continue
        name = str(candidate.get("name") or "").strip()
        normalized_name = normalize_enterprise_name(name)
        if not name or normalized_name in existing_names:
            skipped += 1
            continue
        item = insert_candidate_to_db(candidate, db, batch_id)
        inserted_items.append(item)
        existing_names.add(normalized_name)

    db.commit()

    classified_results = []
    for item in inserted_items:
        classification = smart_classify_enterprise(item.name or "", item.evidence or "", item.products or "")
        item.category = normalize_category(classification["category"])
        item.category_reason = classification["reason"]
        item.confidence = classification["confidence"]
        classified_results.append({
            "name": item.name,
            "category": item.category,
            "confidence": item.confidence,
            "method": classification.get("method", "unknown"),
        })
    db.commit()

    by_method = {}
    for result in classified_results:
        method = result.get("method", "unknown")
        by_method[method] = by_method.get(method, 0) + 1

    return {
        "success": True,
        "batch_id": batch_id,
        "approved_count": len(inserted_items),
        "skipped_count": skipped,
        "classified_count": len(classified_results),
        "classification_methods": by_method,
        "message": f"已确认入库 {len(inserted_items)} 家，跳过 {skipped} 家，智能分类 {len(classified_results)} 家",
    }
