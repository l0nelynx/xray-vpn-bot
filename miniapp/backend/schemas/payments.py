from pydantic import BaseModel, Field


class InvoiceCreateRequest(BaseModel):
    provider: str = Field(..., description="apay | crystal | crypto")
    amount: float = Field(..., gt=0)
    currency: str = Field(..., description="RUB | USD | EUR | USDT | TON | ...")
    days: int = Field(..., gt=0)
    tariff_slug: str | None = None
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
