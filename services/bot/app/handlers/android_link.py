"""Bot side of the Android Telegram-link flow (Stage 6).

The Android client generates a code via `POST /api/android/link/start`, then
the user opens `https://t.me/<bot>?start=link_<code>`. This module's
`consume_android_link_code` runs from the bot's `/start` handler.

Bot must NOT import `miniapp.backend` (clean dependency direction — the bot
boots as its own service and may run without the FastAPI app loaded), so
this file talks to the shared sqlite via raw SQL on `app.database.models`'s
async_session, mirroring `android_delivery._save_vless_uuid`.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.database.models import async_session
from app.notify_log import esc, notify_log

logger = logging.getLogger(__name__)

_PURPOSE_TG_LINK = "tg_link"
_MAX_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


async def _notify_link_attempt(
    *,
    result: str,
    tg_id: int,
    android_user_id: int | None = None,
    android_email: str | None = None,
    tg_user_id: int | None = None,
    a_rw_uuid: str | None = None,
    t_rw_uuid: str | None = None,
    a_tier: str = "?",
    t_tier: str = "?",
    survivor_id: int | None = None,
    loser_id: int | None = None,
    kept_uuid: str | None = None,
    disabled_uuid: str | None = None,
    error: str | None = None,
) -> None:
    """Send a unified log-channel notification for any link attempt outcome."""
    icon = "❌" if error else "🔗"
    parts = [f"{icon} <b>Android↔TG link: {esc(result)}</b>"]
    if android_user_id is not None:
        parts.append(
            f"android: <code>{android_user_id}</code> "
            f"{esc(android_email or '—')} "
            f"rw=<code>{esc(a_rw_uuid or '—')}</code> "
            f"tier=<code>{esc(a_tier)}</code>"
        )
    parts.append(
        f"tg: <code>{tg_id}</code> "
        f"existing_user=<code>"
        f"{esc(tg_user_id if tg_user_id is not None else '—')}</code> "
        f"rw=<code>{esc(t_rw_uuid or '—')}</code> "
        f"tier=<code>{esc(t_tier)}</code>"
    )
    parts.append(f"result: <code>{esc(result)}</code>")
    if survivor_id is not None:
        parts.append(
            f"survivor=<code>{survivor_id}</code> "
            f"loser=<code>"
            f"{esc(loser_id if loser_id is not None else '—')}</code> "
            f"kept_uuid=<code>{esc(kept_uuid or '—')}</code> "
            f"disabled_uuid=<code>{esc(disabled_uuid or '—')}</code>"
        )
    if error:
        parts.append(f"error: <code>{esc(error[:300])}</code>")
    await notify_log("\n".join(parts))


async def consume_android_link_code(tg_id: int, code: str) -> str:
    """Bind `tg_id` to the Android user that requested `code`.

    Returns:
      "ok"                       — link applied (no conflict OR simple link
                                   where one side had no RW user)
      "merged_pro"               — link applied via merge, PRO kept
      "merged_free"              — link applied via merge, both FREE → TG kept
      "both_pro_support_needed"  — both sides PRO, manual support needed
      "invalid" / "expired" / "exhausted"  — verification failures
      "user_already_linked"      — android user already has tg_id
    """
    code = (code or "").strip()
    if not code:
        await _notify_link_attempt(result="invalid", tg_id=tg_id)
        return "invalid"

    code_hash = _hash_code(code)
    now = _utcnow_iso()

    async with async_session() as s:
        row = (await s.execute(
            text(
                "SELECT id, user_id, expires_at, used_at, attempts "
                "FROM email_verifications "
                "WHERE purpose = :p AND code_hash = :h AND used_at IS NULL "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"p": _PURPOSE_TG_LINK, "h": code_hash},
        )).first()

        if row is None:
            await _notify_link_attempt(result="invalid", tg_id=tg_id)
            return "invalid"

        code_id, user_id, expires_at, used_at, attempts = row
        attempts = int(attempts or 0)

        if attempts >= _MAX_ATTEMPTS:
            await s.execute(
                text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
                {"n": now, "i": code_id},
            )
            await s.commit()
            await _notify_link_attempt(
                result="exhausted", tg_id=tg_id, android_user_id=user_id,
            )
            return "exhausted"

        if expires_at <= now:
            await s.execute(
                text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
                {"n": now, "i": code_id},
            )
            await s.commit()
            await _notify_link_attempt(
                result="expired", tg_id=tg_id, android_user_id=user_id,
            )
            return "expired"

        owner_row = (await s.execute(
            text("SELECT tg_id, email FROM users WHERE id = :i LIMIT 1"),
            {"i": user_id},
        )).first()
        android_email = owner_row[1] if owner_row else None
        if owner_row and owner_row[0] is not None:
            await _notify_link_attempt(
                result="user_already_linked", tg_id=tg_id,
                android_user_id=user_id, android_email=android_email,
            )
            return "user_already_linked"

        existing_row = (await s.execute(
            text("SELECT id FROM users WHERE tg_id = :t LIMIT 1"),
            {"t": tg_id},
        )).first()

        if existing_row and existing_row[0] != user_id:
            # Conflict path — merge the two rows.
            from account_linking import (
                MergeBlocked, merge_android_and_tg,
            )
            try:
                merge = await merge_android_and_tg(
                    s, android_user_id=user_id,
                    tg_user_id=existing_row[0], tg_id=tg_id,
                )
            except MergeBlocked as blocked:
                await s.rollback()
                await _notify_link_attempt(
                    result="both_pro_support_needed", tg_id=tg_id,
                    android_user_id=user_id, android_email=android_email,
                    tg_user_id=existing_row[0],
                    a_rw_uuid=blocked.details.get("a_rw_uuid"),
                    t_rw_uuid=blocked.details.get("t_rw_uuid"),
                    a_tier="pro", t_tier="pro",
                )
                return "both_pro_support_needed"
            except Exception as exc:
                await s.rollback()
                logger.error(
                    "Android link merge failed: %s", exc, exc_info=True,
                )
                await _notify_link_attempt(
                    result="invalid", tg_id=tg_id,
                    android_user_id=user_id, android_email=android_email,
                    tg_user_id=existing_row[0], error=str(exc),
                )
                return "invalid"

            await s.execute(
                text("UPDATE email_verifications SET used_at = :n "
                     "WHERE id = :i"),
                {"n": now, "i": code_id},
            )
            await s.commit()
            logger.info(
                "Android link merged: android=%s tg_user=%s tg_id=%s code=%s",
                user_id, existing_row[0], tg_id, merge["result"],
            )
            await _notify_link_attempt(
                result=merge["result"], tg_id=tg_id,
                android_user_id=user_id, android_email=android_email,
                tg_user_id=existing_row[0],
                a_rw_uuid=merge["a_rw_uuid"], t_rw_uuid=merge["t_rw_uuid"],
                a_tier=merge["a_tier"], t_tier=merge["t_tier"],
                survivor_id=merge["survivor_id"], loser_id=merge["loser_id"],
                kept_uuid=merge.get("chosen_uuid"),
                disabled_uuid=None,
            )
            return merge["result"]

        # No conflict — simple bind.
        await s.execute(
            text("UPDATE users SET tg_id = :t WHERE id = :i"),
            {"t": tg_id, "i": user_id},
        )
        await s.execute(
            text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
            {"n": now, "i": code_id},
        )
        await s.commit()

    logger.info(
        "Android link applied: android_user_id=%s tg_id=%s", user_id, tg_id,
    )
    await _notify_link_attempt(
        result="ok", tg_id=tg_id, android_user_id=user_id,
        android_email=android_email,
    )
    return "ok"
