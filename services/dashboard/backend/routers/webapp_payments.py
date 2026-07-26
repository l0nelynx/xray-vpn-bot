"""Provider metadata for Tariff Constructor, sourced from the runtime registry."""
from fastapi import APIRouter, Depends
from payments import available_providers

from ..auth import get_current_user

router = APIRouter(prefix="/api/webapp-menu", tags=["webapp-menu"])


@router.get("/providers")
async def list_providers(_: str = Depends(get_current_user)):
    return {
        "providers": [
            {
                "name": provider.name,
                "payment_method": provider.payment_method,
                "currencies": list(provider.supported_currencies),
                "methods": [
                    {"value": value, "label": label}
                    for value, label in provider.methods
                ],
                "surfaces": sorted(provider.surfaces),
                "webhook_key": provider.webhook_key,
            }
            for provider in available_providers()
        ]
    }
