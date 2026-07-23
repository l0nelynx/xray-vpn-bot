from typing import Iterable

from .apay import APayProvider
from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider
from .crypto import CryptoPayProvider
from .crystal import CrystalPayProvider
from .paritypay import ParityPayProvider
from .platega import PlategaProvider
from .stars import TelegramStarsProvider

_REGISTRY: dict[str, PaymentProvider] = {}


def register_provider(provider: PaymentProvider) -> None:
    _REGISTRY[provider.name] = provider


def get_provider(name: str) -> PaymentProvider:
    provider = _REGISTRY.get(name.lower())
    if not provider:
        raise PaymentError(f"Unknown payment provider: {name}")
    return provider


def available_providers() -> Iterable[PaymentProvider]:
    return _REGISTRY.values()


def validate_provider_invoice(
    provider_name: str,
    *,
    currency: str,
    method: str | None,
    surface: str,
) -> PaymentProvider:
    """Validate a constructor invoice against live provider capabilities."""
    provider = get_provider(provider_name)
    if surface not in provider.surfaces:
        raise PaymentError(
            f"Provider '{provider.name}' is not available on surface '{surface}'"
        )
    if not provider.supports(currency):
        raise PaymentError(
            f"Provider '{provider.name}' does not support currency '{currency}'"
        )
    supported_methods = {value for value, _ in provider.methods}
    if (method or "default") not in supported_methods:
        raise PaymentError(
            f"Provider '{provider.name}' does not support method '{method}'"
        )
    return provider


async def create_invoice(provider_name: str, request: InvoiceRequest) -> Invoice:
    provider = get_provider(provider_name)
    if not provider.supports(request.currency):
        raise PaymentError(
            f"Provider '{provider.name}' does not support currency '{request.currency}'"
        )
    return await provider.create_invoice(request)


# Default registrations — additional providers can register themselves at startup.
for _provider_cls in (
    APayProvider,
    CrystalPayProvider,
    CryptoPayProvider,
    PlategaProvider,
    ParityPayProvider,
    TelegramStarsProvider,
):
    register_provider(_provider_cls())
