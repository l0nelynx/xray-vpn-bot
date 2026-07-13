"""Shared Remnawave client and subscription operations.

Public API:
    RemnawaveClient — singleton-per-(base_url, token) wrapper over RemnawaveSDK.
    configure(base_url, token, free_squad_id=None) — set defaults for module-level helpers.
    get_default_client() — get the configured default client.

    SubscriptionScenario, resolve_scenario — pure scenario resolver.

    apply_new_user, apply_extend, apply_update — high-level operations against Remnawave
    that take pre-resolved squad ids and return normalized dicts. They do NOT touch any
    database, send Telegram messages, or know about referral logic — orchestration stays
    in the calling service.
"""

from . import api
from .api import set_config_provider
from .client import RemnawaveClient, configure, get_default_client
from .operations import apply_extend, apply_new_user, apply_update
from .scenarios import SubscriptionScenario, SubscriptionType, resolve_scenario
from . import webhooks
from .webhooks import (
    RemnawaveWebhookPayload,
    extract_vless_uuid,
    is_torrent_block_report,
    parse_webhook,
    torrent_block_ip,
    torrent_block_minutes,
    verify_webhook_signature,
)

__all__ = [
    "RemnawaveClient",
    "configure",
    "get_default_client",
    "api",
    "set_config_provider",
    "SubscriptionScenario",
    "SubscriptionType",
    "resolve_scenario",
    "apply_new_user",
    "apply_extend",
    "apply_update",
    "webhooks",
    "RemnawaveWebhookPayload",
    "verify_webhook_signature",
    "parse_webhook",
    "extract_vless_uuid",
    "is_torrent_block_report",
    "torrent_block_minutes",
    "torrent_block_ip",
]
