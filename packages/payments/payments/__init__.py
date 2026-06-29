"""Shared payment-gateway layer used by the seller bot and the miniapp.

Invoice creation goes through provider classes (APay, CrystalPay, CryptoPay,
Platega) behind a small registry; webhook signature verification lives in
``signatures``. Credentials are injected by the host service via
``set_config_provider`` (see ``config``) so this package has no dependency on
``app.settings`` or ``miniapp.backend.config``.
"""
from .base import (
    Invoice,
    InvoiceRequest,
    PaymentError,
    PaymentProvider,
    SupportedCurrencies,
)
from .config import PaymentsConfig, get_config, set_config_provider
from .registry import (
    available_providers,
    create_invoice,
    get_provider,
    register_provider,
)
from . import signatures

__all__ = [
    "Invoice",
    "InvoiceRequest",
    "PaymentError",
    "PaymentProvider",
    "SupportedCurrencies",
    "PaymentsConfig",
    "get_config",
    "set_config_provider",
    "available_providers",
    "create_invoice",
    "get_provider",
    "register_provider",
    "signatures",
]
