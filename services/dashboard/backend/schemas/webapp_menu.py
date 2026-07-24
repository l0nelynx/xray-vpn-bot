from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeAction = Literal["buttons", "invoice"]


class WebAppMenuNodeBase(BaseModel):
    text_ru: str = Field(..., max_length=255)
    text_en: str = Field(..., max_length=255)
    action: NodeAction = "buttons"
    sort_order: int = 0
    is_active: bool = True
    invoice_provider: str | None = None
    invoice_amount: float | None = None
    invoice_currency: str | None = None
    invoice_method: str | None = None
    invoice_days: int | None = None
    invoice_internal_squad_ids: list[str] | None = None
    invoice_external_squad_id: str | None = None
    invoice_traffic_limit_bytes: int | None = None
    invoice_traffic_limit_strategy: str | None = None
    invoice_remnawave_description: str | None = None
    invoice_remnawave_tag: str | None = None


class WebAppMenuNodeCreate(WebAppMenuNodeBase):
    parent_id: int | None = None


class WebAppMenuNodeUpdate(BaseModel):
    text_ru: str | None = Field(default=None, max_length=255)
    text_en: str | None = Field(default=None, max_length=255)
    action: NodeAction | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    parent_id: int | None = None
    invoice_provider: str | None = None
    invoice_amount: float | None = None
    invoice_currency: str | None = None
    invoice_method: str | None = None
    invoice_days: int | None = None
    invoice_internal_squad_ids: list[str] | None = None
    invoice_external_squad_id: str | None = None
    invoice_traffic_limit_bytes: int | None = None
    invoice_traffic_limit_strategy: str | None = None
    invoice_remnawave_description: str | None = None
    invoice_remnawave_tag: str | None = None


class WebAppMenuNodeSchema(WebAppMenuNodeBase):
    id: int
    parent_id: int | None = None
    needs_attention: bool = False
    children: list["WebAppMenuNodeSchema"] = []

    class Config:
        from_attributes = True


class ReorderItem(BaseModel):
    id: int
    parent_id: int | None = None
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


WebAppMenuNodeSchema.model_rebuild()
