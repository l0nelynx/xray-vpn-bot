"""Provider catalog mirror for the tariff constructor.

The miniapp owns the actual `PaymentProvider` implementations. The dashboard
constructor only needs the static metadata (name, payment_method, supported
currencies, supported methods) to populate dropdowns. Keep this list in sync
with `miniapp/backend/payments/*.py`.

`methods` is a per-provider list of {value, label} pairs. Providers with a
single fixed method expose `[{"value": "default", "label": "Default"}]` —
the UI then disables the Method dropdown for them.
"""

from fastapi import APIRouter, Depends

from ..auth import get_current_user

router = APIRouter(prefix="/api/webapp-menu", tags=["webapp-menu"])


_DEFAULT_METHODS = [{"value": "default", "label": "Default"}]


_PROVIDER_CATALOG = [
    {
        "name": "apay",
        "payment_method": "SBP_APAY",
        "currencies": ["RUB"],
        "methods": _DEFAULT_METHODS,
    },
    {
        "name": "crystal",
        "payment_method": "CRYSTAL_PAY",
        "currencies": ["RUB", "USD", "EUR"],
        "methods": _DEFAULT_METHODS,
    },
    {
        "name": "crypto",
        "payment_method": "CRYPTOPAY",
        "currencies": ["USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC"],
        "methods": _DEFAULT_METHODS,
    },
    {
        "name": "platega",
        "payment_method": "PLATEGA",
        "currencies": ["RUB"],
        "methods": [
            {"value": "2", "label": "SBP"},
            {"value": "3", "label": "ERIP"},
            {"value": "11", "label": "Card"},
            {"value": "12", "label": "International"},
            {"value": "13", "label": "Crypto"},
        ],
    },
]


@router.get("/providers")
async def list_providers(_: str = Depends(get_current_user)):
    return {"providers": _PROVIDER_CATALOG}
