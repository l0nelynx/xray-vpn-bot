"""Backward-compatibility shim — implementation moved to app.bot_constructor.handlers.payments.

This module is no longer registered on the dispatcher by default.
It is conditionally loaded at startup when bot_feature_flags.legacy_bot_constructor is True.
"""
from app.bot_constructor.handlers.payments import (  # noqa: F401
    router,
    PaymentState,
    PAYMENT_METHOD_NAMES,
    payment_handler,
    pre_checkout_handler,
    success_stars_payment_handler,
    stars_plan,
    premium,
    premium_extend,
    invoice_handler,
    enter_promo,
    process_promo_input,
)
