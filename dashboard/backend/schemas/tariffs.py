from pydantic import BaseModel
from typing import Optional


class TariffPriceSchema(BaseModel):
    id: Optional[int] = None
    payment_method: str
    price: float
    currency: str
    is_active: bool = True

    class Config:
        from_attributes = True


class TariffPlanSchema(BaseModel):
    id: int
    slug: str
    name_ru: str
    name_en: str
    days: int
    sort_order: int
    is_active: bool
    discount_percent: int
    created_at: Optional[str] = None
    squad_profile_id: Optional[int] = None
    prices: list[TariffPriceSchema] = []

    class Config:
        from_attributes = True


class TariffPlanCreate(BaseModel):
    slug: str
    name_ru: str
    name_en: str
    days: int
    sort_order: int = 0
    is_active: bool = True
    discount_percent: int = 0
    squad_profile_id: Optional[int] = None
    prices: list[TariffPriceSchema] = []


class TariffPlanUpdate(BaseModel):
    slug: Optional[str] = None
    name_ru: Optional[str] = None
    name_en: Optional[str] = None
    days: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    discount_percent: Optional[int] = None
    squad_profile_id: Optional[int] = None
    prices: Optional[list[TariffPriceSchema]] = None


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]
