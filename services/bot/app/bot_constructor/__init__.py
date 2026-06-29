"""Legacy in-bot tariff menus and inline payment flow.

This subpackage is conditionally loaded at bot startup based on the
``bot_feature_flags.legacy_bot_constructor`` DB flag. When the flag is False
(default) none of this code runs and the bot directs users to the MiniApp
for all payment flows.

Toggle via Dashboard → WebApp → Settings.

NOTE: handler imports are deferred inside get_router() to avoid circular imports.
      The keyboards/tools.py shim imports from this package at module level,
      which triggers __init__.py. If handlers were imported here eagerly,
      they would try to import app.api.a_pay which is not yet fully initialized.
"""

__all__ = ["get_router"]


def get_router():
    """Build and return the bot_constructor aiogram Router.

    Imports are deferred until call time so that module-level imports of
    app.bot_constructor.keyboards.tools (via the keyboards shim) do not
    trigger a circular dependency through the payment handlers.
    """
    from aiogram import Router
    from .handlers.menus import router as _menus_router
    from .handlers.payments import router as _payments_router

    _router = Router(name="bot_constructor")
    _router.include_router(_menus_router)
    _router.include_router(_payments_router)
    return _router
