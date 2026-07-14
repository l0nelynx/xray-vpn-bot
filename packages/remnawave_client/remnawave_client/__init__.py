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
from .perks import apply_crm_bonus_days, apply_crm_bonus_traffic
from .scenarios import SubscriptionScenario, SubscriptionType, resolve_scenario
from .segmentation import (
    DEFAULT_DAYS_THRESHOLD,
    DEFAULT_INVOICE_MAX_AGE_HOURS,
    DEFAULT_TORRENT_DAYS,
    DEFAULT_TRAFFIC_THRESHOLD,
    PREVIEW_LIMIT,
    SEGMENT_ALL_USERS,
    SEGMENT_DEVICE_LIMIT,
    SEGMENT_EXPIRED,
    SEGMENT_EXPIRING_SOON,
    SEGMENT_LIMITED,
    SEGMENT_NEVER_CONNECTED,
    SEGMENT_TORRENT,
    SEGMENT_TRAFFIC_LOW,
    SEGMENT_UNPAID_INVOICE,
    matches_rw_segment,
    normalize_user_for_crm,
    segment_meta,
)
from .torrent_blocker import collect_torrent_user_uuids, fetch_torrent_blocker_reports
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
    "apply_crm_bonus_days",
    "apply_crm_bonus_traffic",
    "DEFAULT_DAYS_THRESHOLD",
    "DEFAULT_INVOICE_MAX_AGE_HOURS",
    "DEFAULT_TORRENT_DAYS",
    "DEFAULT_TRAFFIC_THRESHOLD",
    "PREVIEW_LIMIT",
    "SEGMENT_ALL_USERS",
    "SEGMENT_DEVICE_LIMIT",
    "SEGMENT_EXPIRED",
    "SEGMENT_EXPIRING_SOON",
    "SEGMENT_LIMITED",
    "SEGMENT_NEVER_CONNECTED",
    "SEGMENT_TORRENT",
    "SEGMENT_TRAFFIC_LOW",
    "SEGMENT_UNPAID_INVOICE",
    "matches_rw_segment",
    "normalize_user_for_crm",
    "segment_meta",
    "collect_torrent_user_uuids",
    "fetch_torrent_blocker_reports",
    "webhooks",
    "RemnawaveWebhookPayload",
    "verify_webhook_signature",
    "parse_webhook",
    "extract_vless_uuid",
    "is_torrent_block_report",
    "torrent_block_minutes",
    "torrent_block_ip",
]
