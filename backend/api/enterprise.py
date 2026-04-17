from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend import models, schemas
from backend.database import get_db

router = APIRouter(prefix="/enterprises", tags=["enterprises"])


@router.post("/", response_model=schemas.EnterpriseResponse)
def create_enterprise(enterprise: schemas.EnterpriseCreate, db: Session = Depends(get_db)):
    db_enterprise = models.Enterprise(**enterprise.model_dump())
    db.add(db_enterprise)
    db.commit()
    db.refresh(db_enterprise)
    return db_enterprise


@router.get("/")
def list_enterprises(
    category: str | None = Query(default=None, description="按分类筛选"),
    town: str | None = Query(default=None, description="按镇街筛选"),
    keyword: str | None = Query(default=None, description="按企业名称搜索"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    query = db.query(models.Enterprise)

    if category:
        query = query.filter(models.Enterprise.category == category)

    if town:
        query = query.filter(models.Enterprise.town == town)

    if keyword:
        query = query.filter(models.Enterprise.name.contains(keyword))

    total = query.count()

    items = (
        query.order_by(desc(models.Enterprise.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "town": item.town,
                "category": item.category,
                "category_reason": item.category_reason,
                "products": item.products,
                "source_url": item.source_url,
                "evidence": item.evidence,
                "confidence": item.confidence,
                "reviewed": item.reviewed,
            }
            for item in items
        ],
    }

@router.get("/stats")
def get_enterprise_stats(db: Session = Depends(get_db)):
    total = db.query(models.Enterprise).count()

    service = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据服务类"
    ).count()

    tech = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据技术类"
    ).count()

    security = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据安全类"
    ).count()

    infrastructure = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据基础设施类"
    ).count()

    other = db.query(models.Enterprise).filter(
        models.Enterprise.category == "其他数据相关类"
    ).count()

    return {
        "total": total,
        "service": service,
        "tech": tech,
        "security": security,
        "infrastructure": infrastructure,
        "other": other,
    }