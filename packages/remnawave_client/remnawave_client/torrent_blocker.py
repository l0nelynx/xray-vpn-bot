"""Remnawave panel torrent-blocker reports API (node-plugins).

Uses the SDK's authenticated httpx client directly — same pattern as the
HWID compatibility shim in client.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .client import _unwrap_response_envelope

logger = logging.getLogger(__name__)

_TORRENT_REPORTS_PATH = "/node-plugins/torrent-blocker"


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _extract_user_id(record: dict) -> int | None:
    """Extract the numeric Remnawave user id from a v3 report row."""
    user = record.get("user")
    if isinstance(user, dict):
        value = user.get("id") or user.get("userId") or user.get("user_id")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

    xray = record.get("xrayReport") or record.get("xray_report")
    if isinstance(xray, dict):
        email = xray.get("email")
        if email and "@" in str(email):
            # email-only rows — caller joins by email if needed
            return None

    action = record.get("actionReport") or record.get("action_report")
    if isinstance(action, dict):
        value = action.get("userId") or action.get("user_id")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

    return None


def _record_timestamp(record: dict) -> datetime | None:
    action = record.get("actionReport") or record.get("action_report") or {}
    for key in ("processedAt", "processed_at"):
        ts = _parse_dt(action.get(key))
        if ts:
            return ts
    for key in ("createdAt", "created_at", "timestamp"):
        ts = _parse_dt(record.get(key))
        if ts:
            return ts
    return None


async def fetch_torrent_blocker_reports(
    client,
    *,
    start: int = 0,
    size: int = 100,
) -> tuple[list[dict], int]:
    """Fetch one page of torrent-blocker reports.

    ``client`` is a RemnawaveClient instance.
    Returns (records, total_count).
    """
    try:
        http = client.sdk.users.client
        response = await http.get(
            _TORRENT_REPORTS_PATH,
            params={"start": start, "size": size},
        )
        response.raise_for_status()
        data = _unwrap_response_envelope(response.json())
    except Exception as exc:
        logger.error("torrent-blocker reports fetch failed: %s", exc)
        return [], 0

    if isinstance(data, dict):
        records = data.get("records") or data.get("items") or data.get("data") or []
        total = int(data.get("total") or data.get("count") or len(records))
        return list(records), total
    if isinstance(data, list):
        return data, len(data)
    return [], 0


async def collect_torrent_user_ids(
    client,
    *,
    days: int = 7,
    page_size: int = 100,
) -> set[int]:
    """Distinct numeric user IDs with reports in the last ``days``."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    user_ids: set[int] = set()
    start = 0

    while True:
        records, total = await fetch_torrent_blocker_reports(
            client, start=start, size=page_size
        )
        if not records:
            break

        for record in records:
            if not isinstance(record, dict):
                continue
            ts = _record_timestamp(record)
            if ts and ts < cutoff:
                continue
            rw_id = _extract_user_id(record)
            if rw_id is not None:
                user_ids.add(rw_id)

        start += len(records)
        if start >= total or len(records) < page_size:
            break

    return user_ids
