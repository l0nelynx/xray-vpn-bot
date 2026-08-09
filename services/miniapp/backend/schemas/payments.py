from typing import Literal

from pydantic import BaseModel, Field


class InvoiceCreateRequest(BaseModel):
    """Client passes only the Tariff Constructor node id — price/days/provider
    are resolved server-side from ``webapp_menu_nodes``."""

    node_id: int = Field(..., ge=1)
    description: str | None = None
    subscription_id: int | None = Field(default=None, ge=1)


class PayCreditsRequest(BaseModel):
    node_id: int = Field(..., ge=1)
    subscription_id: int | None = Field(default=None, ge=1)


class PayCreditsResponse(BaseModel):
    ok: bool
    transaction_id: str | None = None
    points_spent: int | None = None
    points_cost: int | None = None
    credits_spent: int | None = None
    balance_after: int | None = None
    subscription_url: str | None = None
    message: str | None = None


class InvoiceResponse(BaseModel):
    provider: str
    invoice_id: str
    url: str
    amount: float
    currency: str
    transaction_id: str
    payment_method: str


class ProviderInfo(BaseModel):
    name: str
    payment_method: str
    currencies: list[str]


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]


class TransactionStatusResponse(BaseModel):
    transaction_id: str
    state: Literal["awaiting_payment", "processing", "succeeded", "failed"]
    delivery_status: int
