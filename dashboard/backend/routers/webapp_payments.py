"""Provider catalog mirror for the tariff constructor.

The miniapp owns the actual `PaymentProvider` implementations. The dashboard
constructor only needs the static metadata (name, payment_method, supported
currencies) to populate dropdowns. Keep this list in sync with
`miniapp/backend/payments/*.py`.
"""

from fastapi import APIRouter, Depends

from ..auth import get_current_user

router = APIRouter(prefix="/api/webapp-menu", tags=["webapp-menu"])


_PROVIDER_CATALOG = [
    {
        "name": "apay",
        "payment_method": "SBP_APAY",
        "currencies": ["RUB"],
    },
    {
        "name": "crystal",
        "payment_method": "CRYSTAL_PAY",
        "currencies": ["RUB", "USD", "EUR"],
    },
    {
        "name": "crypto",
        "payment_method": "CRYPTOPAY",
        "currencies": ["USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC"],
    },
]


@router.get("/providers")
async def list_providers(_: str = Depends(get_current_user)):
    return {"providers": _PROVIDER_CATALOG}
