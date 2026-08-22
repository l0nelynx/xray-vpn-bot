"""CRM scan orchestration — joins local DB users with Remnawave data."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common_db.models import User
from common_db.repo import crm_segments as seg_repo
from remnawave_client.perks import apply_crm_bonus_days, apply_crm_bonus_traffic
from remnawave_client.segmentation import (
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
    segment_meta,
)
from remnawave_client.torrent_blocker import collect_torrent_user_ids

logger = logging.getLogger(__name__)


def _scan_user_row(user: User, meta: dict | None = None) -> dict:
    return {
        "tg_id": user.tg_id,
        "username": user.username,
        "rw_id": user.rw_id,
        "meta": meta or {},
    }


async def _enrich_device_counts(
    rw_client,
    crm_by_id: dict[int, dict],
    rw_ids: list[int],
) -> None:
    """Fill device_count for users missing it (segment device_limit)."""
    sem = asyncio.Semaphore(20)

    async def _one(rw_id: int) -> None:
        async with sem:
            try:
                resp = await rw_client.get_user_hwid_devices_by_id(rw_id)
                if resp and rw_id in crm_by_id:
                    count = int(resp.total) if resp.total else len(resp.devices or [])
                    crm_by_id[rw_id]["device_count"] = count
            except Exception as exc:
                logger.debug("HWID count failed rw_id=%s: %s", rw_id, exc)

    await asyncio.gather(*[_one(rw_id) for rw_id in rw_ids], return_exceptions=True)


async def scan_segment(
    session: AsyncSession,
    rw_client,
    segment_id: str,
    *,
    days_threshold: int = DEFAULT_DAYS_THRESHOLD,
    traffic_threshold: float = DEFAULT_TRAFFIC_THRESHOLD,
    invoice_max_age_hours: int = DEFAULT_INVOICE_MAX_AGE_HOURS,
    torrent_days: int = DEFAULT_TORRENT_DAYS,
    preview_limit: int | None = PREVIEW_LIMIT,
    user_type: str = seg_repo.USER_TYPE_ALL,
) -> tuple[list[dict], int, str | None]:
    """Return (preview_users, total_count, warning)."""

    if segment_id == SEGMENT_UNPAID_INVOICE:
        users = await seg_repo.users_with_unpaid_invoices(
            session, max_age_hours=invoice_max_age_hours
        )
        users = await seg_repo.filter_users_by_type(session, users, user_type)
        rows = [_scan_user_row(u, {"order_status": "created"}) for u in users]
        preview = rows if preview_limit is None else rows[:preview_limit]
        return preview, len(rows), None

    if segment_id == SEGMENT_ALL_USERS:
        users = await seg_repo.get_broadcast_eligible_users(session)
        users = await seg_repo.filter_users_by_type(session, users, user_type)
        rows = [_scan_user_row(u) for u in users]
        preview = rows if preview_limit is None else rows[:preview_limit]
        return preview, len(rows), None

    local_users = await seg_repo.get_remnawave_broadcast_users(session)
    local_users = await seg_repo.filter_users_by_type(session, local_users, user_type)
    if not local_users:
        return [], 0, None

    by_id = {int(u.rw_id): u for u in local_users if u.rw_id is not None}
    warning: str | None = None

    torrent_rw_ids: set[int] | None = None
    if segment_id == SEGMENT_TORRENT:
        torrent_rw_ids = await collect_torrent_user_ids(rw_client, days=torrent_days)
        if not torrent_rw_ids:
            warning = (
                "Torrent-blocker API returned an empty list — check panel version "
                "or API token permissions."
            )

    try:
        crm_users = await rw_client.get_all_users_for_crm()
    except Exception as exc:
        logger.error("CRM scan: Remnawave bulk fetch failed: %s", exc)
        return [], 0, f"Failed to load Remnawave users: {exc}"

    crm_by_id = {int(u["rw_id"]): u for u in crm_users if u.get("rw_id") is not None}

    if segment_id == SEGMENT_DEVICE_LIMIT:
        missing = [
            rw_id
            for rw_id, cu in crm_by_id.items()
            if rw_id in by_id and cu.get("device_count") is None
        ]
        if missing:
            await _enrich_device_counts(rw_client, crm_by_id, missing)

    matched: list[dict] = []
    for rw_id, db_user in by_id.items():
        crm_user = crm_by_id.get(rw_id)
        if not crm_user:
            continue

        if segment_id == SEGMENT_TORRENT:
            if torrent_rw_ids and rw_id in torrent_rw_ids:
                matched.append(_scan_user_row(db_user, segment_meta(crm_user)))
            continue

        if matches_rw_segment(
            crm_user,
            segment_id,
            days_threshold=days_threshold,
            traffic_threshold=traffic_threshold,
        ):
            matched.append(_scan_user_row(db_user, segment_meta(crm_user)))

    if segment_id == SEGMENT_NEVER_CONNECTED:
        # Warn when panel does not expose firstConnectedAt on any user
        if crm_users and all(u.get("first_connected_at") is None for u in crm_users):
            warning = (
                "firstConnectedAt is missing from the API response — all users "
                "may match this segment. Upgrade the Remnawave panel."
            )

    preview = matched if preview_limit is None else matched[:preview_limit]
    return preview, len(matched), warning


async def apply_campaign_perks(
    rw_client,
    user: User,
    crm_user: dict | None,
    *,
    bonus_days: int | None,
    bonus_traffic_gb: int | None,
) -> tuple[bool, str | None]:
    """Apply CRM perks. Returns (success, error_message)."""
    if user.rw_id is None:
        return False, "no rw_id"
    if not crm_user:
        return False, "remnawave user not found"

    username = user.username or f"user_{user.tg_id}"
    had_perk = bool(bonus_days or bonus_traffic_gb)
    if not had_perk:
        return True, None

    ok = True
    errors: list[str] = []

    if bonus_days and bonus_days > 0:
        if not await apply_crm_bonus_days(
            rw_id=int(user.rw_id),
            username=username,
            bonus_days=bonus_days,
            crm_user=crm_user,
            client=rw_client,
        ):
            ok = False
            errors.append("bonus_days failed")

    if bonus_traffic_gb and bonus_traffic_gb > 0:
        if not await apply_crm_bonus_traffic(
            rw_id=int(user.rw_id),
            username=username,
            bonus_gb=bonus_traffic_gb,
            crm_user=crm_user,
            client=rw_client,
        ):
            ok = False
            errors.append("bonus_traffic failed")

    return ok, "; ".join(errors) if errors else None


def segment_catalog() -> list[dict[str, Any]]:
    user_type_param = {
        "name": "user_type",
        "label": "User type",
        "type": "select",
        "default": seg_repo.USER_TYPE_ALL,
        "options": seg_repo.USER_TYPE_OPTIONS,
    }
    common_filters = [user_type_param]

    def _params(extra: list[dict] | None = None) -> list[dict]:
        return list(extra or []) + common_filters

    return [
        {
            "id": SEGMENT_ALL_USERS,
            "title": "All users",
            "description": "All non-banned users with a tg_id (mass broadcast)",
            "params": _params(),
        },
        {
            "id": SEGMENT_NEVER_CONNECTED,
            "title": "Never connected",
            "description": "Users with a subscription but no firstConnectedAt in Remnawave",
            "params": _params(),
        },
        {
            "id": SEGMENT_EXPIRED,
            "title": "Expired",
            "description": "Subscription status is expired",
            "params": _params(),
        },
        {
            "id": SEGMENT_LIMITED,
            "title": "LIMITED",
            "description": "Subscription status is limited (traffic exhausted)",
            "params": _params(),
        },
        {
            "id": SEGMENT_TRAFFIC_LOW,
            "title": "Traffic running low",
            "description": "Used ≥ threshold of the traffic limit",
            "params": _params([
                {
                    "name": "traffic_threshold",
                    "label": "Usage threshold (0.5–0.95)",
                    "type": "float",
                    "default": DEFAULT_TRAFFIC_THRESHOLD,
                    "min": 0.5,
                    "max": 0.95,
                }
            ]),
        },
        {
            "id": SEGMENT_EXPIRING_SOON,
            "title": "Subscription expiring soon",
            "description": "≤ N days left until expire_at",
            "params": _params([
                {
                    "name": "days_threshold",
                    "label": "Days until expiration",
                    "type": "int",
                    "default": DEFAULT_DAYS_THRESHOLD,
                    "min": 1,
                    "max": 30,
                }
            ]),
        },
        {
            "id": SEGMENT_UNPAID_INVOICE,
            "title": "Unpaid invoice",
            "description": "Transactions with status created",
            "params": _params([
                {
                    "name": "invoice_max_age_hours",
                    "label": "Max invoice age (hours)",
                    "type": "int",
                    "default": DEFAULT_INVOICE_MAX_AGE_HOURS,
                    "min": 1,
                    "max": 168,
                }
            ]),
        },
        {
            "id": SEGMENT_TORRENT,
            "title": "Torrent Reports",
            "description": "Users from torrent-blocker reports",
            "params": _params([
                {
                    "name": "torrent_days",
                    "label": "Period (days)",
                    "type": "int",
                    "default": DEFAULT_TORRENT_DAYS,
                    "min": 1,
                    "max": 90,
                }
            ]),
        },
        {
            "id": SEGMENT_DEVICE_LIMIT,
            "title": "Device limit",
            "description": "Device count ≥ hwidDeviceLimit",
            "params": _params(),
        },
    ]
