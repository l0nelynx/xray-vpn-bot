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
    a_rw_id: int | None,
    t_rw_id: int | None,
    email: str | None,
    username: str | None,
    expected_telegram_id: int | None = None,
) -> tuple[dict | None, dict | None]:
    """Concurrently look up Android-side and TG-side in Remnawave.

    Numeric IDs are authoritative. Email is the Android fallback; username
    is accepted for Telegram only when the panel ``telegram_id`` matches.

    Returns (a_info, t_info) where each is the dict from the client or None
    only on a genuine miss. Upstream errors propagate: an outage must never
    be interpreted as an absent identity during account merge.
    """
    import asyncio
    from remnawave_client import api as rem

    a_task = rem.get_user_from_id(a_rw_id, strict=True) if a_rw_id else (
        rem.get_user_from_email(email) if email else _none()
    )
    async def lookup_t():
        if t_rw_id:
            return await rem.get_user_from_id(t_rw_id, strict=True)
        if not username:
            return None
        match = await rem.get_user_from_username(username, strict=True)
        if match and expected_telegram_id is not None:
            owner = match.get("telegram_id")
            if owner is None or int(owner) != int(expected_telegram_id):
                return None
        return match

    t_task = lookup_t() if (t_rw_id or username) else _none()

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
    rw_id: int | None,
    email: str | None,
) -> dict | None:
    """Look up the current user (A-side) in Remnawave.

    Tries the numeric Remnawave ID first, then falls back to exact email.
    Returns the Remnawave dict or None on a genuine miss. Mirrors the A-side
    branch of `_lookup_rw` but without the TG-side concurrent fetch — the
    by_url flow already has B-side loaded via short_uuid.
    """
    from remnawave_client import api as rem

    if rw_id:
        info = await rem.get_user_from_id(rw_id, strict=True)
        if info:
            return info
    if email:
        return await rem.get_user_from_email(email)
    return None


class MergeBlocked(Exception):
    """Legacy compatibility exception; safe multi-profile merge no longer raises it."""

    def __init__(self, details: dict[str, Any]):
        super().__init__("both_pro_support_needed")
        self.details = details


def _decide(
    *,
    a_tier: str,
    t_tier: str,
    a_rw_id: int | None,
    t_rw_id: int | None,
    android_id: int,
    tg_user_id: int,
) -> tuple[int, int, str | None, str]:
    """Apply the resolution matrix.

    Returns (survivor_id, loser_id, chosen_rw_id, result_code).
    The Telegram row is always the survivor. Both PRO profiles are preserved.
    """
    if a_tier == "pro" and t_tier == "pro":
        return tg_user_id, android_id, t_rw_id or a_rw_id, "merged_pro"

    # PRO vs FREE — real merge: PRO wins, code = merged_pro
    if a_tier == "pro" and t_tier == "free":
        return tg_user_id, android_id, a_rw_id, "merged_pro"
    if t_tier == "pro" and a_tier == "free":
        return tg_user_id, android_id, t_rw_id, "merged_pro"

    # Both FREE — real merge: TG wins (with Android ID fallback)
    if a_tier == "free" and t_tier == "free":
        chosen = t_rw_id or a_rw_id
        return tg_user_id, android_id, chosen, "merged_free"

    # One side has an RW user (pro or free), the other is "none" → simple
    # link, survivor = the side with the RW user, code = ok
    if a_tier in ("pro", "free") and t_tier == "none":
        return tg_user_id, android_id, a_rw_id, "ok"
    if t_tier in ("pro", "free") and a_tier == "none":
        return tg_user_id, android_id, t_rw_id, "ok"

    # Both "none"
    return tg_user_id, android_id, None, "ok"


_FK_TABLES_USER_ID = (
    "transactions",
    "email_verifications",
    "refresh_tokens",
    "telegram_link_codes",
    "support_tickets",
    "google_play_purchases",
    "web_authorization_codes",
    "subscription_transfers",
    "android_fcm_tokens",
    "push_campaign_deliveries",
    "credit_ledger",
)


def _all_user_owned_tables() -> tuple[str, ...]:
    """Return every modeled users.id FK plus intentionally FK-less ledgers."""
    from common_db import Base

    tables = set(_FK_TABLES_USER_ID)
    for table in Base.metadata.tables.values():
        if "user_id" not in table.c:
            continue
        if any(
            fk.target_fullname == "users.id"
            for fk in table.c.user_id.foreign_keys
        ):
            tables.add(table.name)
    tables.discard("user_subscriptions")  # handled with primary invariants
    return tuple(sorted(tables))


async def _apply_merge_db(
    *,
    session,
    survivor_id: int,
    loser_id: int,
    tg_id: int,
    chosen_rw_id: int | None,
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
    loser_legacy_panel_uuid = loser.vless_uuid
    if loser_email:
        loser.email = None
    # users.rw_id is unique. Ownership is preserved in user_subscriptions,
    # so release the loser's legacy projection before assigning the survivor.
    loser.rw_id = None
    loser.vless_uuid = None
    await session.flush()
    if survivor.email in (None, "") and loser_email:
        survivor.email = loser_email
    if survivor.vless_uuid in (None, "") and loser_legacy_panel_uuid:
        survivor.vless_uuid = loser_legacy_panel_uuid

    _copy_if_empty(survivor, loser, "password_hash")
    _copy_if_empty(survivor, loser, "password_updated_at")
    _copy_if_empty(survivor, loser, "email_verified_at")
    _copy_if_empty(survivor, loser, "username")
    _copy_if_empty(survivor, loser, "language")
    _copy_if_empty(survivor, loser, "api_provider")

    survivor.vip = max(survivor.vip or 0, loser.vip or 0)
    survivor.bonus_credits = int(survivor.bonus_credits or 0) + int(
        loser.bonus_credits or 0
    )

    survivor.tg_id = tg_id
    # Preserve all Remnawave profiles. Primary preference is survivor's
    # existing primary, then loser's, then the oldest link.
    subscriptions = (
        await session.execute(
            text(
                "SELECT id, user_id, rw_id, is_primary, created_at "
                "FROM user_subscriptions WHERE user_id IN (:s, :l) ORDER BY id"
            ),
            {"s": survivor_id, "l": loser_id},
        )
    ).mappings().all()
    survivor_primary = next(
        (row for row in subscriptions if row["user_id"] == survivor_id and row["is_primary"]),
        None,
    )
    loser_primary = next(
        (row for row in subscriptions if row["user_id"] == loser_id and row["is_primary"]),
        None,
    )
    primary = survivor_primary or loser_primary or (subscriptions[0] if subscriptions else None)
    if subscriptions:
        await session.execute(
            text(
                "UPDATE user_subscriptions SET is_primary = false "
                "WHERE user_id IN (:s, :l)"
            ),
            {"s": survivor_id, "l": loser_id},
        )
        await session.execute(
            text("UPDATE user_subscriptions SET user_id = :s WHERE user_id = :l"),
            {"s": survivor_id, "l": loser_id},
        )
        await session.execute(
            text("UPDATE user_subscriptions SET is_primary = true WHERE id = :i"),
            {"i": primary["id"]},
        )
        survivor.rw_id = int(primary["rw_id"])
    elif chosen_rw_id is not None:
        survivor.rw_id = chosen_rw_id

    for table in _all_user_owned_tables():
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

    Caller owns the transaction — this function does NOT commit.
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
        a_rw_id=a.rw_id, t_rw_id=t.rw_id, email=a.email,
        username=t.username, expected_telegram_id=tg_id,
    )
    a_tier = _classify(a_info)
    t_tier = _classify(t_info)
    a_rw_id = (a_info or {}).get("rw_id")
    t_rw_id = (t_info or {}).get("rw_id")

    # Backfill legacy single-profile ownership before collapsing the rows.
    from common_db.repo import subscriptions as repo_subscriptions
    for owner_id, info in ((android_user_id, a_info), (tg_user_id, t_info)):
        rw_id = (info or {}).get("rw_id")
        if rw_id is None:
            continue
        try:
            await repo_subscriptions.attach(
                session,
                user_id=owner_id,
                rw_id=int(rw_id),
                source="account_merge_backfill",
            )
        except ValueError:
            logger.warning(
                "Merge backfill skipped rw_id=%s: already linked", rw_id
            )

    survivor_id, loser_id, chosen_rw_id, result_code = _decide(
        a_tier=a_tier, t_tier=t_tier,
        a_rw_id=a_rw_id, t_rw_id=t_rw_id,
        android_id=android_user_id, tg_user_id=tg_user_id,
    )

    await _apply_merge_db(
        session=session,
        survivor_id=survivor_id,
        loser_id=loser_id,
        tg_id=tg_id,
        chosen_rw_id=chosen_rw_id,
    )
    survivor = await session.get(User, survivor_id)
    primary_rw_id = survivor.rw_id if survivor is not None else chosen_rw_id

    logger.info(
        "merge_android_and_tg: survivor=%s loser=%s code=%s "
        "a_tier=%s t_tier=%s",
        survivor_id, loser_id, result_code, a_tier, t_tier,
    )

    return {
        "result": result_code,
        "survivor_id": survivor_id,
        "loser_id": loser_id,
        "loser_rw_id": None,
        "a_tier": a_tier,
        "t_tier": t_tier,
        "a_rw_id": a_rw_id,
        "t_rw_id": t_rw_id,
        "chosen_rw_id": primary_rw_id,
    }


async def import_subscription_by_uuid(
    session,
    *,
    current_user_id: int,
    b_rw_short_uuid: str,
    claimed_email: str,
) -> dict[str, Any]:
    """Import a Remnawave subscription URL into the current user's account.

    A = current user (must exist in DB).
    B = subscription owner identified by Remnawave short_uuid (may not exist
        in our DB — only RW is consulted for B).

    `claimed_email` is the email the requester claims belongs to B. It is
    compared case- and whitespace-insensitively to B's RW-side email
    immediately after the RW lookup; a mismatch (or an empty RW email)
    raises `LookupNotFound` — the same opaque failure used when the
    short_uuid resolves to nothing. See
    docs/superpowers/specs/2026-05-21-android-link-by-url-email-design.md.

    Reuses the PRO/FREE matrix from `_decide` by mapping
    A → "android-side" and B → "tg-side". `survivor_id`/`loser_id` outputs
    of `_decide` are ignored here (only one DB row exists).

    Returns:
      {
        "result": "merged_pro" | "merged_free" | "ok" | "already_owned",
        "a_tier": "pro" | "free" | "none",
        "b_tier": "pro" | "free",
        "a_rw_id": int | None,
        "b_rw_id": int,
        "chosen_rw_id": int,
        "loser_rw_id": int | None,
      }

    Raises:
      LookupNotFound  — RW returned no user for the short_uuid.

    The caller commits the session. No Remnawave profile is disabled.
    """
    from remnawave_client import api as rem
    from common_db.models import User
    from common_db.repo import subscriptions as repo_subscriptions

    a = await session.get(User, current_user_id)
    if a is None:
        raise RuntimeError(f"a_user_not_found: {current_user_id}")

    b_info = await rem.get_user_by_short_uuid_raw(b_rw_short_uuid)
    if b_info is None:
        raise LookupNotFound(b_rw_short_uuid)

    # Email confirmation gate — wire response is uniform with "short_uuid
    # not found" so the endpoint cannot be used as an oracle.
    rw_email = (b_info.get("email") or "").strip().lower()
    claimed = claimed_email.strip().lower()
    if not rw_email or rw_email != claimed:
        logger.info(
            "import_subscription_by_uuid: email_mismatch user=%s short=%s "
            "rw_email=%s claimed=%s",
            current_user_id, b_rw_short_uuid,
            rw_email or "<none>", claimed_email,
        )
        raise LookupNotFound(b_rw_short_uuid)

    b_rw_id = int(b_info["id"])

    # Self-import: pasted own URL → no-op.
    if a.rw_id is not None and int(a.rw_id) == b_rw_id:
        await repo_subscriptions.attach(
            session, user_id=current_user_id, rw_id=b_rw_id,
            source="import_self_backfill",
        )
        tier = _classify(b_info)
        return {
            "result": "already_owned",
            "a_tier": tier,
            "b_tier": tier,
            "a_rw_id": b_rw_id,
            "b_rw_id": b_rw_id,
            "chosen_rw_id": b_rw_id,
            "loser_rw_id": None,
        }

    a_info = await _lookup_a_side_rw(
        rw_id=a.rw_id, email=a.email,
    )
    a_tier = _classify(a_info)
    b_tier = _classify(b_info)
    a_rw_id = (a_info or {}).get("rw_id")

    # Preserve both subscriptions locally. Existing primary stays primary;
    # when there is none, the first successfully attached profile becomes it.
    for info, source in ((a_info, "import_existing"), (b_info, "import_by_url")):
        rw_id = (info or {}).get("rw_id", (info or {}).get("id"))
        if rw_id is None:
            continue
        await repo_subscriptions.attach(
            session,
            user_id=current_user_id,
            rw_id=int(rw_id),
            source=source,
        )

    # Map A → android-side, B → tg-side. survivor/loser ids are
    # meaningless (only one DB row); we use the caller's id for both
    # slots so _decide doesn't see None and stays consistent.
    _survivor, _loser, chosen_rw_id, result_code = _decide(
        a_tier=a_tier, t_tier=b_tier,
        a_rw_id=a_rw_id, t_rw_id=b_rw_id,
        android_id=current_user_id, tg_user_id=current_user_id,
    )

    primary = await repo_subscriptions.get_primary(session, current_user_id)
    if primary is not None:
        a.rw_id = primary.rw_id
        chosen_rw_id = primary.rw_id
    elif chosen_rw_id is not None:
        a.rw_id = chosen_rw_id
    await session.flush()

    logger.info(
        "import_subscription_by_uuid: user=%s a_tier=%s b_tier=%s "
        "chosen=%s code=%s",
        current_user_id, a_tier, b_tier, chosen_rw_id,
        result_code,
    )

    return {
        "result": result_code,
        "a_tier": a_tier,
        "b_tier": b_tier,
        "a_rw_id": a_rw_id,
        "b_rw_id": b_rw_id,
        "chosen_rw_id": chosen_rw_id,
        "loser_rw_id": None,
    }
