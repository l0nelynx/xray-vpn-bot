"""CRM message variable catalog and template rendering."""

from __future__ import annotations

import html
import math
import re
from typing import Any

from remnawave_client.webhooks import (
    RemnawaveWebhookPayload,
    extract_device_model,
    extract_not_connected_after_hours,
    torrent_block_ip,
    torrent_block_minutes,
)

# Allow snake_case and camelCase placeholders (webhook vars use camelCase).
_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}")

VARIABLE_CATALOG: list[dict[str, str]] = [
    {
        "key": "username",
        "label": "Username",
        "description": "Telegram @username",
        "example": "@alice",
    },
    {
        "key": "days_left",
        "label": "Days until expiration",
        "description": "Remaining subscription days in Remnawave",
        "example": "3",
    },
    {
        "key": "traffic_left",
        "label": "Traffic remaining",
        "description": "Free traffic in GB (or — if unlimited)",
        "example": "2 GB",
    },
    {
        "key": "hwid_devices",
        "label": "Devices",
        "description": "Number of HWID devices in Remnawave",
        "example": "2",
    },
    {
        "key": "traffic_percent",
        "label": "Traffic (%)",
        "description": "Percentage of traffic used",
        "example": "85",
    },
    {
        "key": "status",
        "label": "Subscription status",
        "description": "Status in Remnawave (active, limited, …)",
        "example": "limited",
    },
]

WEBHOOK_VARIABLE_CATALOG: list[dict[str, str]] = [
    {
        "key": "notConnectedAfterHours",
        "label": "Not connected (hours)",
        "description": "Hours offline from user.not_connected meta",
        "example": "24",
    },
    {
        "key": "deviceModel",
        "label": "Device model",
        "description": "HWID device model from user_hwid_devices events",
        "example": "iPhone 15",
    },
    {
        "key": "ip",
        "label": "Blocked IP",
        "description": "IP from torrent_blocker.report",
        "example": "203.0.113.42",
    },
    {
        "key": "blockMinutes",
        "label": "Block minutes",
        "description": "Torrent block duration in minutes",
        "example": "30",
    },
]


def variable_catalog(*, context: str | None = None) -> list[dict[str, str]]:
    if context == "webhook":
        return list(VARIABLE_CATALOG) + list(WEBHOOK_VARIABLE_CATALOG)
    return list(VARIABLE_CATALOG)


def webhook_variable_catalog() -> list[dict[str, str]]:
    return list(WEBHOOK_VARIABLE_CATALOG)


def _format_traffic_left(crm_user: dict | None) -> str:
    if not crm_user:
        return "—"
    limit = int(crm_user.get("traffic_limit_bytes") or 0)
    if limit <= 0:
        return "—"
    used = int(crm_user.get("used_traffic_bytes") or 0)
    left_bytes = max(0, limit - used)
    left_gb = max(0, math.ceil(left_bytes / (1024 ** 3)))
    return f"{left_gb} ГБ"


def _format_traffic_percent(crm_user: dict | None) -> str:
    if not crm_user:
        return "—"
    ratio = crm_user.get("traffic_ratio")
    if ratio is None:
        return "—"
    return str(round(float(ratio) * 100))


def build_message_context(
    *,
    username: str | None,
    crm_user: dict | None,
    meta: dict | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build substitution map for one recipient."""
    meta = meta or {}
    uname = (username or "").strip()
    display_name = f"@{uname}" if uname else "—"

    days_left = meta.get("days_left")
    if days_left is None and crm_user is not None:
        days_left = crm_user.get("days_left")
    days_str = str(days_left) if days_left is not None else "—"

    devices = meta.get("devices")
    if devices is None and crm_user is not None:
        devices = crm_user.get("device_count")
    devices_str = str(devices) if devices is not None else "—"

    status = meta.get("status")
    if status is None and crm_user is not None:
        status = crm_user.get("status")
    status_str = str(status) if status else "—"

    traffic_pct = meta.get("traffic_percent")
    if traffic_pct is not None:
        traffic_percent_str = str(traffic_pct)
    else:
        traffic_percent_str = _format_traffic_percent(crm_user)

    ctx = {
        "username": html.escape(display_name),
        "days_left": html.escape(days_str),
        "traffic_left": html.escape(_format_traffic_left(crm_user)),
        "hwid_devices": html.escape(devices_str),
        "traffic_percent": html.escape(traffic_percent_str),
        "status": html.escape(status_str),
    }
    if extra:
        for key, value in extra.items():
            ctx[key] = html.escape(str(value)) if value is not None else ""
    return ctx


def build_webhook_extra_vars(payload: RemnawaveWebhookPayload) -> dict[str, str]:
    """Webhook-only placeholders; missing fields become empty strings."""
    hours = extract_not_connected_after_hours(payload)
    model = extract_device_model(payload)
    ip = torrent_block_ip(payload)
    minutes = torrent_block_minutes(payload) if payload.scope == "torrent_blocker" else None
    return {
        "notConnectedAfterHours": "" if hours is None else str(hours),
        "deviceModel": model or "",
        "ip": ip or "",
        "blockMinutes": "" if minutes is None else str(minutes),
    }


def build_webhook_message_context(
    *,
    username: str | None,
    crm_user: dict | None,
    payload: RemnawaveWebhookPayload,
    meta: dict | None = None,
) -> dict[str, str]:
    return build_message_context(
        username=username,
        crm_user=crm_user,
        meta=meta,
        extra=build_webhook_extra_vars(payload),
    )


def render_crm_message(template: str, ctx: dict[str, str]) -> str:
    """Replace ``{{var}}`` placeholders; unknown keys become empty strings."""

    def repl(match: re.Match[str]) -> str:
        return ctx.get(match.group(1), "")

    return _VAR_PATTERN.sub(repl, template)
