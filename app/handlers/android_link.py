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


async def consume_android_link_code(tg_id: int, code: str) -> str:
    """Bind `tg_id` to the Android user that requested `code`.

    Returns:
      "ok"               — link applied
      "invalid"          — no matching active code (or hash mismatch)
      "expired"          — code found but past expires_at
      "exhausted"        — too many failed attempts on this code
      "tg_already_linked" — *the bot's* tg_id is already bound to another
                            android user → refuse to silently move it
      "user_already_linked" — the android user that owns this code already
                              has a tg_id (raced with another link)
    """
    code = (code or "").strip()
    if not code:
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
            return "invalid"

        code_id, user_id, expires_at, used_at, attempts = row
        attempts = int(attempts or 0)

        if attempts >= _MAX_ATTEMPTS:
            await s.execute(
                text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
                {"n": now, "i": code_id},
            )
            await s.commit()
            return "exhausted"

        if expires_at <= now:
            await s.execute(
                text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
                {"n": now, "i": code_id},
            )
            await s.commit()
            return "expired"

        # Refuse to overwrite either side of the binding silently.
        owner_row = (await s.execute(
            text("SELECT tg_id FROM users WHERE id = :i LIMIT 1"),
            {"i": user_id},
        )).first()
        if owner_row and owner_row[0] is not None:
            return "user_already_linked"

        existing_row = (await s.execute(
            text("SELECT id FROM users WHERE tg_id = :t LIMIT 1"),
            {"t": tg_id},
        )).first()
        if existing_row and existing_row[0] != user_id:
            return "tg_already_linked"

        await s.execute(
            text("UPDATE users SET tg_id = :t WHERE id = :i"),
            {"t": tg_id, "i": user_id},
        )
        await s.execute(
            text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
            {"n": now, "i": code_id},
        )
        # Read email for the notification (best-effort; bind already happened
        # in the same transaction so we want it in the same DB session).
        email_row = (await s.execute(
            text("SELECT email FROM users WHERE id = :i LIMIT 1"),
            {"i": user_id},
        )).first()
        await s.commit()

    user_email = email_row[0] if email_row else None
    logger.info("Android link applied: android_user_id=%s tg_id=%s", user_id, tg_id)
    await notify_log(
        f"🔗 <b>Telegram linked to Android account</b>\n"
        f"android user: <code>{user_id}</code> {esc(user_email or '—')}\n"
        f"tg_id: <code>{tg_id}</code>"
    )
    return "ok"
