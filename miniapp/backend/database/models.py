"""Backwards-compatible re-export of shared ORM models.

The actual models live in `common_db.models` (packages/common_db).
This module exists so legacy imports such as

    from ..database.models import User, SupportTicket

keep working without rewriting every router. New code should import
directly from `common_db.models`.

Note: miniapp historically only used a subset of the full schema, but we
re-export the same set as the dashboard shim so any future code path can
reach for what it needs without re-introducing a local class.
"""
from common_db import Base  # noqa: F401  (legacy: miniapp code may reference Base)
from common_db.models import (  # noqa: F401
    CacheVersion,
    DisabledUser,
    EmailVerification,
    GooglePlayPurchase,
    GooglePlaySku,
    MenuButton,
    MenuScreen,
    Promo,
    PromoSettings,
    RefreshToken,
    SquadProfile,
    SupportMessage,
    SupportTicket,
    TariffPlan,
    TariffPrice,
    TelegramLinkCode,
    TelmtFreeParams,
    Transaction,
    User,
    WebAppMenuNode,
)

__all__ = [
    "Base",
    "CacheVersion",
    "DisabledUser",
    "EmailVerification",
    "GooglePlayPurchase",
    "GooglePlaySku",
    "MenuButton",
    "MenuScreen",
    "Promo",
    "PromoSettings",
    "RefreshToken",
    "SquadProfile",
    "SupportMessage",
    "SupportTicket",
    "TariffPlan",
    "TariffPrice",
    "TelegramLinkCode",
    "TelmtFreeParams",
    "Transaction",
    "User",
    "WebAppMenuNode",
]
