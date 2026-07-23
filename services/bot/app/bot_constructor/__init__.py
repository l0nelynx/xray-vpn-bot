"""Database-authored Telegram menus and unified tariff-tree payment flow.

The router is always registered. ``legacy_bot_constructor`` is retained as a
compatibility-named live runtime flag: when false, purchase callbacks open the
MiniApp; dynamic Telegram screens remain available.

Handlers are imported lazily so the router can be registered during bot setup
without coupling package import order to payment configuration.
"""

__all__ = ["get_router"]


def get_router():
    """Build and return the bot_constructor aiogram Router.

    Imports are deferred until call time to keep startup import order simple.
    """
    from aiogram import Router
    from .handlers.menus import router as _menus_router
    from .handlers.payments import router as _payments_router

    _router = Router(name="bot_constructor")
    _router.include_router(_menus_router)
    _router.include_router(_payments_router)
    return _router
