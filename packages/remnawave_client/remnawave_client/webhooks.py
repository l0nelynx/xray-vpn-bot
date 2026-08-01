"""Remnawave panel webhook parsing and signature verification.

Inbound webhooks are signed with HMAC-SHA256 over the raw request body using
the panel's ``WEBHOOK_SECRET_HEADER`` value (configured as
``remnawave_webhook_secret`` in config.yml).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Scopes supported by CRM webhook rules (subset of Remnawave panel scopes).
SCOPE_USER = "user"
SCOPE_TORRENT_BLOCKER = "torrent_blocker"
SCOPE_USER_HWID_DEVICES = "user_hwid_devices"

WEBHOOK_EVENT_CATALOG: list[dict[str, Any]] = [
    {
        "scope": SCOPE_USER,
        "label": "User",
        "events": [
            {"value": "user.created", "label": "User created"},
            {"value": "user.modified", "label": "User modified"},
            {"value": "user.deleted", "label": "User deleted"},
            {"value": "user.revoked", "label": "User revoked"},
            {"value": "user.disabled", "label": "User disabled"},
            {"value": "user.enabled", "label": "User enabled"},
            {"value": "user.limited", "label": "User limited"},
            {"value": "user.expired", "label": "User expired"},
            {"value": "user.traffic_reset", "label": "User traffic reset"},
            {"value": "user.first_connected", "label": "User first connected"},
            {
                "value": "user.bandwidth_usage_threshold_reached",
                "label": "Bandwidth threshold reached",
            },
            {"value": "user.not_connected", "label": "User not connected"},
            {"value": "user.expiration", "label": "User expiration"},
        ],
    },
    {
        "scope": SCOPE_TORRENT_BLOCKER,
        "label": "Torrent Blocker",
        "events": [
            {"value": "torrent_blocker.report", "label": "Torrent blocker report"},
        ],
    },
    {
        "scope": SCOPE_USER_HWID_DEVICES,
        "label": "HWID Devices",
        "events": [
            {"value": "user_hwid_devices.added", "label": "Device added"},
            {"value": "user_hwid_devices.deleted", "label": "Device deleted"},
        ],
    },
]


def webhook_event_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in WEBHOOK_EVENT_CATALOG]


def is_known_webhook_pair(scope: str, event: str) -> bool:
    for group in WEBHOOK_EVENT_CATALOG:
        if group["scope"] != scope:
            continue
        return any(e["value"] == event for e in group["events"])
    return False


class RemnawaveWebhookUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    telegram_id: int | None = Field(None, alias="telegramId")
    username: str | None = None


class TorrentBlockerActionReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    blocked: bool = False
    ip: str | None = None
    block_duration: int | None = Field(None, alias="blockDuration")
    will_unblock_at: str | None = Field(None, alias="willUnblockAt")
    user_id: int | None = Field(None, alias="userId")
    processed_at: str | None = Field(None, alias="processedAt")


class TorrentBlockerXrayReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str | None = None
    protocol: str | None = None
    network: str | None = None
    source: str | None = None
    destination: str | None = None


class TorrentBlockerReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action_report: TorrentBlockerActionReport | None = Field(
        None, alias="actionReport"
    )
    xray_report: TorrentBlockerXrayReport | None = Field(None, alias="xrayReport")


class TorrentBlockerData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    node: dict[str, Any] | None = None
    user: RemnawaveWebhookUser | None = None
    report: TorrentBlockerReport | None = None


class RemnawaveWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scope: str
    event: str
    timestamp: str
    data: dict[str, Any] | TorrentBlockerData | None = None


def verify_webhook_signature(
    raw_body: bytes, signature: str, secret: str
) -> bool:
    """Verify ``X-Remnawave-Signature`` against the raw request body."""
    if not secret or not signature:
        return False
    computed = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def parse_webhook(raw_body: bytes) -> RemnawaveWebhookPayload:
    """Parse and validate a Remnawave webhook JSON body."""
    data = json.loads(raw_body)
    return RemnawaveWebhookPayload.model_validate(data)


def _data_dict(payload: RemnawaveWebhookPayload) -> dict[str, Any]:
    if payload.data is None:
        return {}
    if isinstance(payload.data, TorrentBlockerData):
        return payload.data.model_dump(by_alias=True)
    if isinstance(payload.data, dict):
        return payload.data
    return {}


def _as_torrent_data(
    payload: RemnawaveWebhookPayload,
) -> TorrentBlockerData | None:
    if payload.scope != SCOPE_TORRENT_BLOCKER:
        return None
    if isinstance(payload.data, TorrentBlockerData):
        return payload.data
    if isinstance(payload.data, dict):
        return TorrentBlockerData.model_validate(payload.data)
    return None


def _find_user_dict(data: dict[str, Any]) -> dict[str, Any] | None:
    user = data.get("user")
    if isinstance(user, dict):
        return user
    # Some HWID events nest user under hwidUser / device payload.
    for key in ("hwidUser", "hwid_user"):
        nested = data.get(key)
        if isinstance(nested, dict) and (
            "id" in nested or "userId" in nested
            or "telegramId" in nested or "telegram_id" in nested
        ):
            return nested
    return None


def extract_rw_id(payload: RemnawaveWebhookPayload) -> int | None:
    """Return the numeric Remnawave user ID from a v3 webhook."""
    if payload.scope == SCOPE_TORRENT_BLOCKER:
        tb = _as_torrent_data(payload)
        if tb and tb.report and tb.report.action_report:
            if tb.report.action_report.user_id is not None:
                return int(tb.report.action_report.user_id)
        if tb and tb.user and tb.user.id is not None:
            return int(tb.user.id)
    data = _data_dict(payload)
    if payload.scope == SCOPE_USER:
        value = data.get("id")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    user = _find_user_dict(data)
    if user:
        value = user.get("id") or user.get("userId") or user.get("user_id")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def extract_telegram_id(payload: RemnawaveWebhookPayload) -> int | None:
    """Return telegramId from webhook user data, if present."""
    if payload.scope == SCOPE_TORRENT_BLOCKER:
        tb = _as_torrent_data(payload)
        if tb and tb.user and tb.user.telegram_id is not None:
            return int(tb.user.telegram_id)
    data = _data_dict(payload)
    if payload.scope == SCOPE_USER:
        tg = data.get("telegramId", data.get("telegram_id"))
        if tg is not None:
            try:
                return int(tg)
            except (TypeError, ValueError):
                return None
    user = _find_user_dict(data)
    if user:
        tg = user.get("telegramId", user.get("telegram_id"))
        if tg is not None:
            try:
                return int(tg)
            except (TypeError, ValueError):
                return None
    return None


def extract_not_connected_after_hours(
    payload: RemnawaveWebhookPayload,
) -> int | None:
    """Hours offline from ``meta.notConnectedAfterHours`` (user.not_connected)."""
    data = _data_dict(payload)
    meta = data.get("meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("notConnectedAfterHours", meta.get("not_connected_after_hours"))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_device_dict(data: dict[str, Any]) -> dict[str, Any] | None:
    for key in (
        "hwidUserDevice",
        "hwid_user_device",
        "hwidDevice",
        "hwid_device",
        "device",
        "userHwidDevice",
        "user_hwid_device",
    ):
        device = data.get(key)
        if isinstance(device, dict):
            return device
    # Payload may be the device itself
    if any(
        k in data
        for k in (
            "deviceModel",
            "device_model",
            "platform",
            "osVersion",
            "os_version",
            "hwid",
        )
    ):
        return data
    return None


def _device_str_field(
    payload: RemnawaveWebhookPayload, *keys: str
) -> str | None:
    data = _data_dict(payload)
    device = _find_device_dict(data)
    if not device:
        return None
    for key in keys:
        value = device.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def extract_device_model(payload: RemnawaveWebhookPayload) -> str | None:
    """Device model from HWID device webhook payloads."""
    return _device_str_field(payload, "deviceModel", "device_model")


def extract_device_platform(payload: RemnawaveWebhookPayload) -> str | None:
    """Platform from HWID device webhook payloads (e.g. ios, android)."""
    return _device_str_field(payload, "platform")


def extract_device_os_version(payload: RemnawaveWebhookPayload) -> str | None:
    """OS version from HWID device webhook payloads."""
    return _device_str_field(payload, "osVersion", "os_version")


def is_torrent_block_report(payload: RemnawaveWebhookPayload) -> bool:
    """True when this is a torrent blocker report with an active block."""
    if payload.scope != SCOPE_TORRENT_BLOCKER:
        return False
    if payload.event != "torrent_blocker.report":
        return False
    tb = _as_torrent_data(payload)
    if not tb or not tb.report or not tb.report.action_report:
        return False
    return tb.report.action_report.blocked is True


def torrent_block_minutes(payload: RemnawaveWebhookPayload) -> int:
    """Block duration in whole minutes (minimum 1)."""
    tb = _as_torrent_data(payload)
    if not tb or not tb.report or not tb.report.action_report:
        return 1
    duration = tb.report.action_report.block_duration
    if duration is None or duration <= 0:
        return 1
    return max(1, round(duration / 60))


def torrent_block_ip(payload: RemnawaveWebhookPayload) -> str | None:
    """Offending IP from the action report, if present."""
    tb = _as_torrent_data(payload)
    if not tb or not tb.report or not tb.report.action_report:
        return None
    return tb.report.action_report.ip
