"""企业相关接口。

当前提供两个基础能力：
1. 新增企业记录
2. 查询企业列表，并支持按分类筛选
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.database import get_db

router = APIRouter(prefix="/enterprises", tags=["enterprises"])


@router.post("/", response_model=schemas.EnterpriseResponse)
def create_enterprise(enterprise: schemas.EnterpriseCreate, db: Session = Depends(get_db)):
    """创建一条新的企业记录。"""
    db_enterprise = models.Enterprise(**enterprise.model_dump())
    db.add(db_enterprise)
    db.commit()
    # 刷新对象，确保能够拿到数据库生成的最新值，例如主键 id。
    db.refresh(db_enterprise)
    return db_enterprise


@router.get("/", response_model=list[schemas.EnterpriseResponse])
def list_enterprises(
    category: str | None = Query(default=None, description="按分类筛选"),
    db: Session = Depends(get_db)
):
    """查询企业列表。

    如果提供了 category 参数，则只返回对应分类下的企业。
    """
    query = db.query(models.Enterprise)
    if category:
        query = query.filter(models.Enterprise.category == category)
    return query.all()
