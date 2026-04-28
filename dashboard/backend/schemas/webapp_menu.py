from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

NodeAction = Literal["buttons", "invoice"]


class WebAppMenuNodeBase(BaseModel):
    text: str = Field(..., max_length=200)
    action: NodeAction = "buttons"
    sort_order: int = 0
    is_active: bool = True

    invoice_provider: Optional[str] = None
    invoice_amount: Optional[float] = None
    invoice_currency: Optional[str] = None
    invoice_days: Optional[int] = None
    invoice_tariff_slug: Optional[str] = None


class WebAppMenuNodeCreate(WebAppMenuNodeBase):
    parent_id: Optional[int] = None


class WebAppMenuNodeUpdate(BaseModel):
    text: Optional[str] = None
    action: Optional[NodeAction] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    parent_id: Optional[int] = None
    invoice_provider: Optional[str] = None
    invoice_amount: Optional[float] = None
    invoice_currency: Optional[str] = None
    invoice_days: Optional[int] = None
    invoice_tariff_slug: Optional[str] = None


class WebAppMenuNodeSchema(WebAppMenuNodeBase):
    id: int
    parent_id: Optional[int] = None
    children: list["WebAppMenuNodeSchema"] = []

    class Config:
        from_attributes = True


class ReorderItem(BaseModel):
    id: int
    parent_id: Optional[int] = None
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


WebAppMenuNodeSchema.model_rebuild()
