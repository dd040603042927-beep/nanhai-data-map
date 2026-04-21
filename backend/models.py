from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from backend.database import Base


class Enterprise(Base):
    __tablename__ = "enterprises"

    id = Column(Integer, primary_key=True, index=True)

    # 比赛要求核心字段
    name = Column(String(255), nullable=False, index=True)          # 企业名
    town = Column(String(100), nullable=True, index=True)           # 所在镇街
    category = Column(String(100), nullable=True, index=True)       # 主要类型（六大类）
    category_reason = Column(Text, nullable=True)                   # 分类依据
    products = Column(Text, nullable=True)                          # 主营产品

    # 补充字段（可保留，不影响比赛要求）
    source_url = Column(Text, nullable=True)                        # 企业网站/来源链接
    evidence = Column(Text, nullable=True)                          # 证据片段
    confidence = Column(Float, default=0.0)                         # 置信度
    reviewed = Column(Boolean, default=False)                       # 复核标记