"""Backward-compatibility shim — real implementation moved to app.bot_constructor.keyboards.tools."""
from app.bot_constructor.keyboards.tools import (  # noqa: F401
    PaymentCallbackData,
    TariffKeyboardBuilder,
    OptimizedTariffKeyboard,
    create_tariff_keyboard,
    payment_keyboard,
    get_price_stars,
    get_price_crypto,
    get_price_discount,
    get_sbp_price,
)

__all__ = [
    "PaymentCallbackData",
    "TariffKeyboardBuilder",
    "OptimizedTariffKeyboard",
    "create_tariff_keyboard",
    "payment_keyboard",
    "get_price_stars",
    "get_price_crypto",
    "get_price_discount",
    "get_sbp_price",
]
