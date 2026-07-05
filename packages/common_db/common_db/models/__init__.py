"""Shared ORM models.

Single source of truth for the schema used by app/, dashboard/ and miniapp/.
All classes are registered on common_db.base.Base.metadata.

Import any class you need from here:
    from common_db.models import User, SupportTicket, SupportMessage
"""
from .auth import EmailVerification, RefreshToken, TelegramLinkCode
from .google_play import GooglePlayPurchase, GooglePlaySku
from .menus import MenuButton, MenuScreen, WebAppMenuNode
from .promo_redemptions import PromoRedemption
from .promos import Promo, PromoSettings
from .support import SupportAttachment, SupportMessage, SupportTicket
from .system import BotFeatureFlags, CacheVersion, TelmtFreeParams
from .tariffs import SquadProfile, TariffPlan, TariffPrice
from .transactions import Transaction
from .users import DisabledUser, User

__all__ = [
    # users
    "User",
    "DisabledUser",
    # promos
    "Promo",
    "PromoSettings",
    "PromoRedemption",
    # transactions
    "Transaction",
    # support
    "SupportTicket",
    "SupportMessage",
    "SupportAttachment",
    # tariffs
    "SquadProfile",
    "TariffPlan",
    "TariffPrice",
    # menus
    "MenuScreen",
    "MenuButton",
    "WebAppMenuNode",
    # auth
    "RefreshToken",
    "EmailVerification",
    "TelegramLinkCode",
    # google play
    "GooglePlayPurchase",
    "GooglePlaySku",
    # system
    "BotFeatureFlags",
    "CacheVersion",
    "TelmtFreeParams",
]
