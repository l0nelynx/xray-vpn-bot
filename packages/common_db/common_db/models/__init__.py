"""Shared ORM models.

Single source of truth for the schema used by app/, dashboard/ and miniapp/.
All classes are registered on common_db.base.Base.metadata.

Import any class you need from here:
    from common_db.models import User, SupportTicket, SupportMessage
"""
from .auth import EmailVerification, RefreshToken, TelegramLinkCode
from .credit_ledger import CreditLedger
from .crm import (
    CrmCampaign,
    CrmCampaignDelivery,
    CrmEvent,
    CrmEventDelivery,
    CrmWebhookDelivery,
    CrmWebhookRule,
)
from .fcm import AndroidFcmToken
from .google_play import GooglePlayPurchase, GooglePlaySku
from .push import PushCampaign, PushCampaignDelivery
from .giveaways import (
    Giveaway,
    GiveawayParticipant,
    GiveawayTicket,
    GiveawayWinner,
)
from .menus import MenuButton, MenuScreen, WebAppMenuNode
from .promo_redemptions import PromoRedemption
from .promos import Promo, PromoSettings
from .support import SupportAttachment, SupportMessage, SupportTicket
from .runtime import AppRuntimeSettings, AppIntegration, PaymentIntegration
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
    # crm
    "CrmCampaign",
    "CrmCampaignDelivery",
    "CrmEvent",
    "CrmEventDelivery",
    "CrmWebhookRule",
    "CrmWebhookDelivery",
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
    # giveaways
    "Giveaway",
    "GiveawayParticipant",
    "GiveawayTicket",
    "GiveawayWinner",
    # menus
    "MenuScreen",
    "MenuButton",
    "WebAppMenuNode",
    # auth
    "RefreshToken",
    "EmailVerification",
    "TelegramLinkCode",
    # credits
    "CreditLedger",
    # google play
    "GooglePlayPurchase",
    "GooglePlaySku",
    # fcm / push
    "AndroidFcmToken",
    "PushCampaign",
    "PushCampaignDelivery",
    # system
    "BotFeatureFlags",
    "CacheVersion",
    "TelmtFreeParams",
    # runtime
    "AppRuntimeSettings",
    "AppIntegration",
    "PaymentIntegration",
]
