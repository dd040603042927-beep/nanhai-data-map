"""ORM 数据模型定义。"""

from sqlalchemy import Boolean, Column, Float, Integer, String, Text

from backend.database import Base


class Enterprise(Base):
    """企业表模型。

    用于保存南海区数据产业企业图谱中的核心企业信息，
    包括名称、所在镇街、分类、证据来源和复核状态等字段。
    """

    __tablename__ = "enterprises"

    # 主键 ID，作为每条企业记录的唯一标识。
    id = Column(Integer, primary_key=True, index=True)
    # 企业名称，通常也是前端展示和搜索的核心字段。
    name = Column(String(255), nullable=False, index=True)
    # 企业所在镇街，便于按区域做筛选和统计。
    town = Column(String(100), nullable=False, index=True)
    # 企业所属主要类型，对应 taxonomy 文档中的分类结果。
    category = Column(String(100), nullable=False, index=True)
    # 记录分类依据，说明为什么把该企业归入当前类别。
    category_reason = Column(Text, nullable=False)
    # 企业主营产品或解决方案简介。
    products = Column(Text, nullable=True)
    # 公开来源链接，便于后续核验数据来源。
    source_url = Column(Text, nullable=True)
    # 从公开资料中摘录的证据片段。
    evidence = Column(Text, nullable=True)
    # 分类或识别置信度，范围通常为 0 到 1。
    confidence = Column(Float, default=0.0)
    # 是否已完成人工复核。
    reviewed = Column(Boolean, default=False)
