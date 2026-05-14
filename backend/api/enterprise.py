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
ENSCAN_PATH = PROJECT_ROOT / "enscan.exe"

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
        "数据资源": "数据资源", "数据资源类": "数据资源", "数据资源企业": "数据资源",
        "数据技术": "数据技术", "数据技术类": "数据技术", "数据技术企业": "数据技术",
        "数据服务": "数据服务", "数据服务类": "数据服务", "数据服务企业": "数据服务",
        "数据应用": "数据应用", "数据应用类": "数据应用", "数据应用企业": "数据应用",
        "数据安全": "数据安全", "数据安全类": "数据安全", "数据安全企业": "数据安全",
        "数据基础设施": "数据基础设施", "数据基础设施类": "数据基础设施", "数据基础设施企业": "数据基础设施",
    }
    for key, val in sorted(cat_map.items(), key=lambda item: len(item[0]), reverse=True):
        if key in clean_text:
            category = val
            break

    # 提取关键词
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

    return {"town": town, "category": category, "keyword": keyword}


def generate_batch_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"batch_{timestamp}_{short_uuid}"


def normalize_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def existing_enterprise_keys(db: Session) -> set:
    return {normalize_name(row[0]) for row in db.query(models.Enterprise.name).all() if row[0]}


def smart_classify_enterprise(name: str, business_scope: str = "") -> dict:
    """根据企业名称和经营范围智能分类"""
    text = f"{name} {business_scope}".lower()

    if any(x in text for x in ["数据安全", "网络安全", "信息安全", "加密", "隐私"]):
        return {"category": "数据安全", "confidence": 0.85, "reason": f"涉及数据安全相关业务"}
    if any(x in text for x in ["数据中心", "云计算", "云平台", "通信", "算力", "存储"]):
        return {"category": "数据基础设施", "confidence": 0.85, "reason": f"提供数据基础设施服务"}
    if any(x in text for x in ["大数据", "人工智能", "算法", "软件开发", "数据分析"]):
        return {"category": "数据技术", "confidence": 0.80, "reason": f"从事数据技术研发"}
    if any(x in text for x in ["数据服务", "智慧城市", "数字政府", "信息服务", "数据运营"]):
        return {"category": "数据服务", "confidence": 0.80, "reason": f"提供行业数据服务"}
    if any(x in text for x in ["数据资源", "数据采集", "数据资产", "数据库"]):
        return {"category": "数据资源", "confidence": 0.75, "reason": f"开展数据资源管理业务"}
    if "数据" in text:
        return {"category": "数据技术", "confidence": 0.60, "reason": f"建议归类为数据技术企业，请人工复核"}
    return {"category": "数据技术", "confidence": 0.50, "reason": f"建议归类为数据技术企业，请人工复核"}


# ==================== ENScan_GO 采集核心 ====================
def run_enscan_search(keyword: str, limit: int = 30) -> list:
    """执行 ENScan_GO 搜索，返回企业列表"""
    if not ENSCAN_PATH.exists():
        print(f"ENScan_GO 不存在: {ENSCAN_PATH}")
        return []

    try:
        cmd = [str(ENSCAN_PATH), "-n", keyword, "-type", "tyc", "-deep", "1"]
        print(f"执行: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            errors='ignore'
        )

        output = result.stdout
        if not output:
            return []

        # 解析输出，提取企业信息
        enterprises = []
        lines = output.split('\n')

        # ENScan_GO 输出格式示例：
        # 企业名称    法人代表    经营状态    PID
        # 华为技术有限公司    赵明路    存续    24416401

        for line in lines:
            line = line.strip()
            if not line or line.startswith('『') or line.startswith('【'):
                continue

            # 按制表符或空格分割
            parts = re.split(r'\t|\s{2,}', line)
            if parts and parts[0]:
                name = parts[0].strip()
                # 过滤无效名称
                if len(name) >= 4 and not name.startswith(('==', '--', '『', '【')):
                    if '有限公司' in name or '股份有限公司' in name or '集团' in name or '中心' in name:
                        # 提取经营范围（如果有）
                        business_scope = parts[1] if len(parts) > 1 else ""
                        enterprises.append({
                            "name": name,
                            "business_scope": business_scope,
                            "raw_line": line
                        })

        return enterprises[:limit]

    except subprocess.TimeoutExpired:
        print(f"ENScan_GO 超时")
        return []
    except Exception as e:
        print(f"ENScan_GO 执行失败: {e}")
        return []


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

    if category and category != "全部":
        query = query.filter(models.Enterprise.category.contains(category))
    if town and town != "全部":
        query = query.filter(models.Enterprise.town.contains(town))
    if keyword and keyword.strip():
        query = query.filter(models.Enterprise.name.contains(keyword.strip()))

    total = query.count()
    items = query.order_by(models.Enterprise.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 构建返回数据
    result_items = []
    for item in items:
        insight = build_enterprise_insight(item, all_items, enable_llm=False)
        result_items.append({
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
        })

    return {"total": total, "page": page, "page_size": page_size, "items": result_items}


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
    parsed = parse_collect_instruction(text)
    all_items = db.query(models.Enterprise).all()
    query = db.query(models.Enterprise)

    if parsed["category"]:
        query = query.filter(models.Enterprise.category.contains(parsed["category"]))
    if parsed["town"]:
        query = query.filter(models.Enterprise.town.contains(parsed["town"]))
    if parsed["keyword"]:
        query = query.filter(models.Enterprise.name.contains(parsed["keyword"]))

    total = query.count()
    items = query.order_by(models.Enterprise.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result_items = []
    for item in items:
        insight = build_enterprise_insight(item, all_items, enable_llm=False)
        result_items.append({
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
        })

    return {"input": text, "parsed": parsed, "total": total, "page": page, "page_size": page_size, "items": result_items}


@router.get("/{enterprise_id}/insight")
def get_enterprise_insight(enterprise_id: int, enable_llm: bool = Query(default=False), db: Session = Depends(get_db)):
    all_items = db.query(models.Enterprise).all()
    item = next((e for e in all_items if e.id == enterprise_id), None)
    if not item:
        return {"success": False, "message": "企业不存在"}
    return {"success": True, "enterprise": {}, "insight": build_enterprise_insight(item, all_items, enable_llm=enable_llm)}


@router.get("/graph/network")
def get_enterprise_graph(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    return build_graph_payload(items)


@router.get("/platform/overview")
def get_platform_overview(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    return build_platform_overview(items)


# ==================== 智能采集接口（仅 ENScan_GO）====================
@router.post("/collect/smart")
def smart_collect(
    instruction: str = Query(..., min_length=1, description="采集指令，如：采集桂城街道的数据安全企业"),
    db: Session = Depends(get_db),
):
    """智能采集：仅使用 ENScan_GO 采集企业信息"""

    # 1. 解析用户指令
    parsed = parse_collect_instruction(instruction)

    if not parsed["town"] and not parsed["category"] and not parsed["keyword"]:
        return {"success": False, "message": "无法解析采集条件，请提供镇街或关键词", "parsed": parsed}

    batch_id = generate_batch_id()

    # 2. 构建搜索关键词
    search_keywords = []
    if parsed["keyword"]:
        search_keywords.append(parsed["keyword"])
    if parsed["town"]:
        search_keywords.append(parsed["town"])
    if parsed["category"]:
        search_keywords.append(parsed["category"])

    search_keyword = " ".join(search_keywords) if search_keywords else "数据企业"

    print(f"📋 采集指令: {instruction}")
    print(f"🔍 搜索关键词: {search_keyword}")

    # 3. 执行 ENScan_GO 采集
    raw_enterprises = run_enscan_search(search_keyword, limit=50)

    # 4. 处理采集结果
    existing_names = existing_enterprise_keys(db)
    candidates = []

    for raw in raw_enterprises:
        name = raw.get("name", "")
        if not name or normalize_name(name) in existing_names:
            continue

        # 智能分类
        classification = smart_classify_enterprise(name, raw.get("business_scope", ""))

        # 生成候选企业
        candidate_key = f"enscan:{normalize_name(name)}"
        candidates.append({
            "key": candidate_key,
            "batch_id": batch_id,
            "name": name,
            "town": parsed["town"] or "待补充",
            "category": classification["category"],
            "category_reason": classification["reason"],
            "products": raw.get("business_scope", "")[:100] or "待补充",
            "source_url": "ENScan_GO/天眼查",
            "evidence": raw.get("raw_line", "")[:300],
            "confidence": str(classification["confidence"]),
            "reviewed": False,
            "data_source": "enscan"
        })

    print(f"✅ 采集完成: 发现 {len(raw_enterprises)} 条，生成候选 {len(candidates)} 条")

    return {
        "success": len(candidates) > 0,
        "instruction": instruction,
        "parsed": parsed,
        "batch_id": batch_id,
        "search_keyword": search_keyword,
        "collected": len(raw_enterprises),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "source_results": [{
            "source": "enscan",
            "success": len(raw_enterprises) > 0,
            "collected": len(raw_enterprises),
            "message": "执行完成"
        }],
        "message": f"采集完成：发现{len(raw_enterprises)}家，生成候选{len(candidates)}家，请筛选后确认入库" if candidates else "未采集到符合条件的企业，请调整镇街、类型或关键词后重试"
    }


@router.post("/collect/approve")
def approve_collected_candidates(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    """将前端筛选确认的候选企业写入正式企业库"""
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
        if not name or normalize_name(name) in existing_names:
            skipped += 1
            continue

        # 创建企业记录
        enterprise = models.Enterprise(
            name=name,
            town=candidate.get("town") or "待补充",
            category=candidate.get("category") or "数据技术",
            category_reason=candidate.get("category_reason") or "待补充",
            products=candidate.get("products") or "待补充",
            source_url=candidate.get("source_url", ""),
            evidence=candidate.get("evidence", ""),
            confidence=float(candidate.get("confidence", 0.7)),
            reviewed=False,
            collect_batch=batch_id,
            data_sources="ENScan_GO",
            crawler_status="人工确认入库",
        )
        db.add(enterprise)
        db.flush()
        inserted_items.append(enterprise)
        existing_names.add(normalize_name(name))

    db.commit()

    return {
        "success": True,
        "batch_id": batch_id,
        "approved_count": len(inserted_items),
        "skipped_count": skipped,
        "message": f"已确认入库 {len(inserted_items)} 家，跳过 {skipped} 家"
    }