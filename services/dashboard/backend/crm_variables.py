"""CRM message variable catalog and template rendering."""

from __future__ import annotations

import html
import math
import re
from typing import Any

_VAR_PATTERN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")

VARIABLE_CATALOG: list[dict[str, str]] = [
    {
        "key": "username",
        "label": "Имя пользователя",
        "description": "Telegram @username",
        "example": "@alice",
    },
    {
        "key": "days_left",
        "label": "Дней до истечения",
        "description": "Оставшиеся дни подписки в Remnawave",
        "example": "3",
    },
    {
        "key": "traffic_left",
        "label": "Остаток трафика",
        "description": "Свободный трафик в ГБ (или — без лимита)",
        "example": "2 ГБ",
    },
    {
        "key": "hwid_devices",
        "label": "Устройства",
        "description": "Число HWID-устройств в Remnawave",
        "example": "2",
    },
    {
        "key": "traffic_percent",
        "label": "Трафик (%)",
        "description": "Процент использованного трафика",
        "example": "85",
    },
    {
        "key": "status",
        "label": "Статус подписки",
        "description": "Статус в Remnawave (active, limited, …)",
        "example": "limited",
    },
]


def variable_catalog() -> list[dict[str, str]]:
    return list(VARIABLE_CATALOG)


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

    return {
        "username": html.escape(display_name),
        "days_left": html.escape(days_str),
        "traffic_left": html.escape(_format_traffic_left(crm_user)),
        "hwid_devices": html.escape(devices_str),
        "traffic_percent": html.escape(traffic_percent_str),
        "status": html.escape(status_str),
    }


def render_crm_message(template: str, ctx: dict[str, str]) -> str:
    """Replace ``{{var}}`` placeholders; unknown keys become empty strings."""

    def repl(match: re.Match[str]) -> str:
        return ctx.get(match.group(1), "")

    return _VAR_PATTERN.sub(repl, template)
