"""Backwards-compatible re-export of shared ORM models.

The actual models live in `common_db.models` (packages/common_db).
This module exists so legacy imports such as

    from ..database.models import User, SupportTicket

keep working without rewriting every router. New code should import
directly from `common_db.models`.
"""
from common_db import Base  # noqa: F401  (legacy: dashboard code referenced Base)
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
