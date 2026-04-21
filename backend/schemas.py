from pydantic import BaseModel


class EnterpriseResponse(BaseModel):
    id: int
    name: str
    town: str
    category: str
    category_reason: str
    products: str

    class Config:
        from_attributes = True
