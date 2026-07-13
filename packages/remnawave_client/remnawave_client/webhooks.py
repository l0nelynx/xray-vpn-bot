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


class RemnawaveWebhookUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    uuid: str | None = None
    telegram_id: int | None = Field(None, alias="telegramId")
    username: str | None = None


class TorrentBlockerActionReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    blocked: bool = False
    ip: str | None = None
    block_duration: int | None = Field(None, alias="blockDuration")
    will_unblock_at: str | None = Field(None, alias="willUnblockAt")
    user_id: str | None = Field(None, alias="userId")
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


def _as_torrent_data(
    payload: RemnawaveWebhookPayload,
) -> TorrentBlockerData | None:
    if payload.scope != "torrent_blocker" or not isinstance(payload.data, dict):
        if isinstance(payload.data, TorrentBlockerData):
            return payload.data
        return None
    return TorrentBlockerData.model_validate(payload.data)


def extract_vless_uuid(payload: RemnawaveWebhookPayload) -> str | None:
    """Return the Remnawave user UUID from webhook data, if present."""
    if payload.scope == "torrent_blocker":
        tb = _as_torrent_data(payload)
        if tb and tb.user and tb.user.uuid:
            return tb.user.uuid
    if isinstance(payload.data, dict):
        user = payload.data.get("user")
        if isinstance(user, dict):
            uuid = user.get("uuid")
            if uuid:
                return str(uuid)
    return None


def is_torrent_block_report(payload: RemnawaveWebhookPayload) -> bool:
    """True when this is a torrent blocker report with an active block."""
    if payload.scope != "torrent_blocker":
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
