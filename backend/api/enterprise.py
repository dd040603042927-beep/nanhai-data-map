from fastapi import APIRouter, Depends, Query
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

router = APIRouter(prefix="/enterprises", tags=["enterprises"])


def serialize_enterprise(item: models.Enterprise) -> dict:
    return {
        "id": item.id,
        "name": (item.name or "").strip(),
        "town": normalize_town(item.town),
        "category": normalize_category(item.category),
        "category_reason": (item.category_reason or "").strip() or "待补充",
        "products": (item.products or "").strip() or "待补充",
    }


def apply_filters(
    query,
    category: str | None,
    town: str | None,
    keyword: str | None,
):
    if category and category != "全部":
        accepted_categories = [
            raw_name
            for raw_name, normalized in CATEGORY_ALIASES.items()
            if normalized == category
        ]
        query = query.filter(models.Enterprise.category.in_(accepted_categories))

    if town and town != "全部":
        query = query.filter(models.Enterprise.town.contains(town))

    if keyword:
        clean_keyword = keyword.strip()
        if clean_keyword:
            query = query.filter(models.Enterprise.name.contains(clean_keyword))

    return query


def parse_query_text(text: str) -> dict:
    clean_text = text.strip()
    parsed_category = None
    parsed_town = None

    for category in OFFICIAL_CATEGORIES:
        if category in clean_text:
            parsed_category = category
            break

    for town in OFFICIAL_TOWNS:
        if town in clean_text:
            parsed_town = town
            break

    keyword = clean_text
    for value in OFFICIAL_CATEGORIES + OFFICIAL_TOWNS + ["企业", "公司", "查询", "查找", "搜索", "帮我", "一下"]:
        keyword = keyword.replace(value, " ")

    keyword = " ".join(keyword.split())

    return {
        "category": parsed_category,
        "town": parsed_town,
        "keyword": keyword,
    }


@router.get("/")
def list_enterprises(
    category: str | None = Query(default=None),
    town: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(models.Enterprise)
    query = apply_filters(query, category, town, keyword)

    total = query.count()
    items = (
        query.order_by(models.Enterprise.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_enterprise(item) for item in items],
    }


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

    return {
        "total": len(items),
        "target": 1000,
        "category_stats": category_stats,
        "town_stats": town_stats,
    }


@router.get("/query")
def query_enterprises(
    text: str = Query(..., min_length=1, description="文本或语音识别结果"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    parsed = parse_query_text(text)

    query = db.query(models.Enterprise)
    query = apply_filters(
        query,
        parsed["category"],
        parsed["town"],
        parsed["keyword"],
    )

    total = query.count()
    items = (
        query.order_by(models.Enterprise.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "input": text,
        "parsed": parsed,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_enterprise(item) for item in items],
    }
