"""Legacy in-bot tariff menus and inline payment flow.

This subpackage is conditionally loaded at bot startup based on the
``bot_feature_flags.legacy_bot_constructor`` DB flag. When the flag is False
(default) none of this code runs and the bot directs users to the MiniApp
for all payment flows.

Toggle via Dashboard → WebApp → Settings.
"""
from aiogram import Router

from .handlers.menus import router as _menus_router
from .handlers.payments import router as _payments_router

router = Router(name="bot_constructor")
router.include_router(_menus_router)
router.include_router(_payments_router)

__all__ = ["router"]
