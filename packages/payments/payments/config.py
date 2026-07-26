"""Credential injection for the shared payments package.

The provider implementations are credential-free: each host service (the seller
bot, the miniapp) registers a provider callable returning a populated
:class:`PaymentsConfig`. This mirrors ``remnawave_client.set_config_provider``
and keeps the package free of any dependency on ``app.settings`` or
``miniapp.backend.config``.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from .base import PaymentError


@dataclass(frozen=True)
class PaymentsConfig:
    # Telegram Bot API (Stars invoice links)
    bot_token: str = ""
    # APay (SBP)
    apay_id: object = ""          # int or str depending on the host config
    apay_secret: str = ""
    apay_api_url: str = ""
    # CryptoBot
    crypto_bot_token: str = ""
    # CrystalPay
    crystal_login: str = ""
    crystal_secret: str = ""
    crystal_salt: str = ""
    crystal_webhook: str = ""
    # Platega
    platega_merchant_id: str = ""
    platega_api_key: str = ""
    platega_url: str = ""
    platega_payment_method: int = 2
    # ParityPay
    paritypay_shop_id: str = ""
    paritypay_secret_1: str = ""   # signs outgoing API requests (X-SIGNATURE)
    paritypay_secret_2: str = ""   # verifies incoming webhooks
    paritypay_url: str = "https://api.paritypay.ru"
    paritypay_webhook: str = ""    # public callback URL; blank → set in cassa
    paritypay_service: str = "sbp"  # default service when node method is unset


_provider: Optional[Callable[[], PaymentsConfig]] = None


def set_config_provider(provider: Callable[[], PaymentsConfig]) -> None:
    """Register a callable returning the current :class:`PaymentsConfig`."""
    global _provider
    _provider = provider


def get_config() -> PaymentsConfig:
    if _provider is None:
        raise PaymentError(
            "payments config provider is not set. Call "
            "payments.set_config_provider(...) at startup."
        )
    return _provider()
