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

    # 增强字段：多源证据、企业画像、关系图谱、LLM 辅助、采集平台
    data_sources = Column(Text, nullable=True)                      # 多源数据平台列表
    evidence_summary = Column(Text, nullable=True)                  # 证据摘要
    source_count = Column(Integer, default=0)                       # 来源数量
    company_size = Column(String(50), nullable=True)                # 企业规模画像
    profile_tags = Column(Text, nullable=True)                      # 企业画像标签
    confidence_level = Column(String(50), nullable=True)            # 可信度等级
    chain_position = Column(String(50), nullable=True)              # 产业链位置
    upstream_enterprises = Column(Text, nullable=True)              # 上游企业
    downstream_enterprises = Column(Text, nullable=True)            # 下游企业
    related_enterprises = Column(Text, nullable=True)               # 关联企业
    llm_summary = Column(Text, nullable=True)                       # LLM 摘要
    llm_label_suggestion = Column(String(100), nullable=True)       # LLM 建议分类
    llm_provider = Column(String(100), nullable=True)               # LLM 提供方
    crawler_status = Column(String(50), nullable=True)              # 采集平台状态
