"""Pydantic 数据校验模型。

这些模型用于定义接口请求体和响应体的结构，
让 FastAPI 自动完成参数校验和文档生成。
"""

from pydantic import BaseModel, Field


class EnterpriseBase(BaseModel):
    """企业数据的公共字段定义。"""

    name: str = Field(..., description="企业名称")
    town: str = Field(..., description="所在镇街")
    category: str = Field(..., description="主要类型")
    category_reason: str = Field(..., description="分类依据")
    products: str | None = Field(default=None, description="主营产品")
    source_url: str | None = Field(default=None, description="数据来源链接")
    evidence: str | None = Field(default=None, description="证据片段")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reviewed: bool = Field(default=False, description="是否人工复核")


class EnterpriseCreate(EnterpriseBase):
    """创建企业记录时使用的请求模型。"""

    pass


class EnterpriseResponse(EnterpriseBase):
    """返回给前端的企业响应模型，额外包含数据库中的主键 ID。"""

    id: int

    class Config:
        # 允许直接从 SQLAlchemy 模型对象中读取字段并输出。
        from_attributes = True
