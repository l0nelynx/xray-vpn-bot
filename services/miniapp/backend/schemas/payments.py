from pydantic import BaseModel, Field


class InvoiceCreateRequest(BaseModel):
    """Client passes only the Tariff Constructor node id — price/days/provider
    are resolved server-side from ``webapp_menu_nodes``."""

    node_id: int = Field(..., ge=1)
    description: str | None = None


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
