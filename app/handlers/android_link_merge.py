"""Merge logic for the Android↔Telegram link conflict path.

Called from `android_link.consume_android_link_code` when an Android-side
`users` row and a Telegram-side `users` row both exist and need to be
collapsed into a single row. See
`docs/superpowers/specs/2026-05-19-android-link-conflict-design.md`.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _classify(info: Any) -> str:
    """Return "pro" | "free" | "none" for a Remnawave user dict.

    Matches the project-wide rule used in
    `remnawave_client.scenarios.resolve_scenario` and
    `app/handlers/tools.py:377`: PRO iff status == "active" and data_limit
    is None. 404 sentinel and None map to "none".
    """
    if info is None or info == 404:
        return "none"
    status = info.get("status")
    data_limit = info.get("data_limit")
    if status == "active" and data_limit is None:
        return "pro"
    return "free"


async def _lookup_rw(
    *,
    email: str | None,
    vless_uuid: str | None,
    username: str | None,
) -> tuple[dict | None, dict | None]:
    """Concurrently look up Android-side (by email) and TG-side
    (by uuid → fallback username) in Remnawave.

    Returns (a_info, t_info) where each is the dict from the client or None
    on miss/error. Errors are logged at WARNING and swallowed — the merge
    must continue even if Remnawave is temporarily down.
    """
    import asyncio
    import app.api.remnawave.api as rem

    async def safe(coro):
        try:
            return await coro
        except Exception as exc:
            logger.warning("Remnawave lookup failed: %s", exc)
            return None

    a_task = safe(rem.get_user_from_email(email)) if email else _none()
    if vless_uuid:
        t_task = safe(rem.get_user_from_uuid(vless_uuid))
    elif username:
        t_task = safe(rem.get_user_from_username(username))
    else:
        t_task = _none()

    a_info, t_info = await asyncio.gather(a_task, t_task)
    return a_info, t_info


async def _none():
    return None


class LookupNotFound(Exception):
    """Raised when get_user_by_short_uuid_raw returns None — the imported
    subscription URL pointed at a non-existent Remnawave user. The router
    maps this to HTTP 404 with code=rw_not_found.
    """

    def __init__(self, short_uuid: str):
        super().__init__(f"rw_not_found: {short_uuid}")
        self.short_uuid = short_uuid


async def _lookup_a_side_rw(
    *,
    vless_uuid: str | None,
    email: str | None,
) -> dict | None:
    """Look up the current user (A-side) in Remnawave.

    Tries vless_uuid first (authoritative when set), falls back to email.
    Returns the Remnawave dict or None on miss/error. Mirrors the A-side
    branch of `_lookup_rw` but without the TG-side concurrent fetch — the
    by_url flow already has B-side loaded via short_uuid.
    """
    import app.api.remnawave.api as rem

    if vless_uuid:
        try:
            info = await rem.get_user_from_uuid(vless_uuid)
        except Exception as exc:
            logger.warning("Remnawave A-side uuid lookup failed: %s", exc)
            info = None
        if info:
            return info
    if email:
        try:
            return await rem.get_user_from_email(email)
        except Exception as exc:
            logger.warning("Remnawave A-side email lookup failed: %s", exc)
            return None
    return None


class MergeBlocked(Exception):
    """Raised when both sides hold an active PRO subscription — automatic
    resolution would discard a paid subscription, so the caller must surface
    a "contact support" message instead."""

    def __init__(self, details: dict[str, Any]):
        super().__init__("both_pro_support_needed")
        self.details = details


def _decide(
    *,
    a_tier: str,
    t_tier: str,
    a_rw_uuid: str | None,
    t_rw_uuid: str | None,
    android_id: int,
    tg_user_id: int,
) -> tuple[int, int, str | None, str]:
    """Apply the resolution matrix.

    Returns (survivor_id, loser_id, chosen_uuid, result_code).
    Raises MergeBlocked when both sides are PRO.
    """
    if a_tier == "pro" and t_tier == "pro":
        raise MergeBlocked({
            "a_tier": "pro", "t_tier": "pro",
            "a_rw_uuid": a_rw_uuid, "t_rw_uuid": t_rw_uuid,
        })

    # PRO vs FREE — real merge: PRO wins, code = merged_pro
    if a_tier == "pro" and t_tier == "free":
        return android_id, tg_user_id, a_rw_uuid, "merged_pro"
    if t_tier == "pro" and a_tier == "free":
        return tg_user_id, android_id, t_rw_uuid, "merged_pro"

    # Both FREE — real merge: TG wins (with android UUID fallback)
    if a_tier == "free" and t_tier == "free":
        chosen = t_rw_uuid or a_rw_uuid
        return tg_user_id, android_id, chosen, "merged_free"

    # One side has an RW user (pro or free), the other is "none" → simple
    # link, survivor = the side with the RW user, code = ok
    if a_tier in ("pro", "free") and t_tier == "none":
        return android_id, tg_user_id, a_rw_uuid, "ok"
    if t_tier in ("pro", "free") and a_tier == "none":
        return tg_user_id, android_id, t_rw_uuid, "ok"

    # Both "none"
    return tg_user_id, android_id, None, "ok"


_FK_TABLES_USER_ID = (
    "transactions",
    "email_verifications",
    "refresh_tokens",
    "telegram_link_codes",
    "support_tickets",
    "google_play_purchases",
)


async def _apply_merge_db(
    *,
    session,
    survivor_id: int,
    loser_id: int,
    tg_id: int,
    chosen_uuid: str | None,
) -> None:
    """Copy loser fields onto survivor, reparent FK rows, then DELETE loser.

    Caller controls commit/rollback. Idempotent against the case where
    survivor already holds tg_id.
    """
    from common_db.models import User

    survivor = await session.get(User, survivor_id)
    loser = await session.get(User, loser_id)

    # Clear loser.email BEFORE mutating survivor so autoflush doesn't trip
    # the users.email unique index while both rows hold the same value.
    loser_email = loser.email
    if loser_email:
        loser.email = None
        await session.flush()
    if survivor.email in (None, "") and loser_email:
        survivor.email = loser_email

    _copy_if_empty(survivor, loser, "password_hash")
    _copy_if_empty(survivor, loser, "password_updated_at")
    _copy_if_empty(survivor, loser, "email_verified_at")
    _copy_if_empty(survivor, loser, "username")
    _copy_if_empty(survivor, loser, "language")
    _copy_if_empty(survivor, loser, "api_provider")

    survivor.vip = max(survivor.vip or 0, loser.vip or 0)

    survivor.tg_id = tg_id
    if chosen_uuid is not None:
        survivor.vless_uuid = chosen_uuid

    for table in _FK_TABLES_USER_ID:
        await session.execute(
            text(f"UPDATE {table} SET user_id = :s WHERE user_id = :l"),
            {"s": survivor_id, "l": loser_id},
        )
    await session.execute(
        text("UPDATE transactions SET android_user_id = :s "
             "WHERE android_user_id = :l"),
        {"s": survivor_id, "l": loser_id},
    )

    await session.delete(loser)
    await session.flush()


def _copy_if_empty(survivor, loser, field: str) -> None:
    if getattr(survivor, field, None) in (None, ""):
        loser_val = getattr(loser, field, None)
        if loser_val not in (None, ""):
            setattr(survivor, field, loser_val)


async def merge_android_and_tg(
    session,
    android_user_id: int,
    tg_user_id: int,
    tg_id: int,
) -> dict[str, Any]:
    """Collapse the Android-side and Telegram-side ``users`` rows into one.

    Caller owns the transaction — this function does NOT commit. On
    :class:`MergeBlocked`, no DB writes have been made.
    """
    from common_db.models import User

    a = await session.get(User, android_user_id)
    t = await session.get(User, tg_user_id)
    if a is None or t is None:
        raise RuntimeError(
            f"merge: rows not found android={android_user_id} "
            f"tg={tg_user_id}"
        )

    a_info, t_info = await _lookup_rw(
        email=a.email, vless_uuid=t.vless_uuid, username=t.username,
    )
    a_tier = _classify(a_info)
    t_tier = _classify(t_info)
    a_rw_uuid = (a_info or {}).get("uuid")
    t_rw_uuid = (t_info or {}).get("uuid")

    survivor_id, loser_id, chosen_uuid, result_code = _decide(
        a_tier=a_tier, t_tier=t_tier,
        a_rw_uuid=a_rw_uuid, t_rw_uuid=t_rw_uuid,
        android_id=android_user_id, tg_user_id=tg_user_id,
    )

    # Loser's RW uuid is the one NOT chosen — caller deactivates it.
    # None when we kept the loser-side uuid (FREE+FREE with T.uuid missing).
    if survivor_id == android_user_id:
        loser_rw_uuid = t_rw_uuid if chosen_uuid != t_rw_uuid else None
    else:
        loser_rw_uuid = a_rw_uuid if chosen_uuid != a_rw_uuid else None

    await _apply_merge_db(
        session=session,
        survivor_id=survivor_id,
        loser_id=loser_id,
        tg_id=tg_id,
        chosen_uuid=chosen_uuid,
    )

    logger.info(
        "merge_android_and_tg: survivor=%s loser=%s code=%s "
        "a_tier=%s t_tier=%s",
        survivor_id, loser_id, result_code, a_tier, t_tier,
    )

    return {
        "result": result_code,
        "survivor_id": survivor_id,
        "loser_id": loser_id,
        "loser_rw_uuid": loser_rw_uuid,
        "a_tier": a_tier,
        "t_tier": t_tier,
        "a_rw_uuid": a_rw_uuid,
        "t_rw_uuid": t_rw_uuid,
    }
