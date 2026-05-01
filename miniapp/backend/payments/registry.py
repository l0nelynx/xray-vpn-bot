from typing import Iterable

from .apay import APayProvider
from .base import Invoice, InvoiceRequest, PaymentError, PaymentProvider
from .crypto import CryptoPayProvider
from .crystal import CrystalPayProvider
from .platega import PlategaProvider

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


async def create_invoice(provider_name: str, request: InvoiceRequest) -> Invoice:
    provider = get_provider(provider_name)
    if not provider.supports(request.currency):
        raise PaymentError(
            f"Provider '{provider.name}' does not support currency '{request.currency}'"
        )
    return await provider.create_invoice(request)


# Default registrations — additional providers can register themselves at startup.
for _provider_cls in (APayProvider, CrystalPayProvider, CryptoPayProvider, PlategaProvider):
    register_provider(_provider_cls())
