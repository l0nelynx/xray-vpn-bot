"""Backward-compatibility shim — implementation moved to app.bot_constructor.handlers.menus.

This module is no longer registered on the dispatcher by default.
It is conditionally loaded at startup when bot_feature_flags.legacy_bot_constructor is True.
"""
from app.bot_constructor.handlers.menus import (  # noqa: F401
    router,
    PAYMENT_SCREEN_SLUGS,
    dynamic_screen_handler,
)
