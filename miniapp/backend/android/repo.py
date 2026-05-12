"""DB access for the Android API auth flow.

Uses raw SQL on the shared aiosqlite engine — the rest of miniapp/backend
already follows that pattern (see routers/me.py etc.) and avoids dragging
SQLAlchemy ORM mappings into a service that needs to stay light.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from ..database.session import async_session
from . import security


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _expiry_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


@dataclass
class UserRow:
    id: int
    email: str | None
    password_hash: str | None
    email_verified_at: str | None
    tg_id: int | None
    is_banned: bool
    language: str | None
    vless_uuid: str | None


def _row_to_user(row) -> UserRow | None:
    if row is None:
        return None
    return UserRow(
        id=row[0],
        email=row[1],
        password_hash=row[2],
        email_verified_at=row[3],
        tg_id=row[4],
        is_banned=bool(row[5]) if row[5] is not None else False,
        language=row[6],
        vless_uuid=row[7],
    )


_USER_COLS = "id, email, password_hash, email_verified_at, tg_id, is_banned, language, vless_uuid"


async def find_user_by_email(email: str) -> UserRow | None:
    normalized = email.strip().lower()
    async with async_session() as s:
        row = (await s.execute(
            text(f"SELECT {_USER_COLS} FROM users WHERE LOWER(email) = :e LIMIT 1"),
            {"e": normalized},
        )).first()
    return _row_to_user(row)


async def find_user_by_id(user_id: int) -> UserRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(f"SELECT {_USER_COLS} FROM users WHERE id = :i LIMIT 1"),
            {"i": user_id},
        )).first()
    return _row_to_user(row)


async def find_user_by_vless_uuid(vless_uuid: str) -> UserRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(f"SELECT {_USER_COLS} FROM users WHERE vless_uuid = :u LIMIT 1"),
            {"u": vless_uuid},
        )).first()
    return _row_to_user(row)


async def find_user_by_remnawave_username(username: str) -> UserRow | None:
    """Lookup a user by the deterministic Remnawave username derived from
    their email (see `provisioning.email_to_username`). The DB has no
    dedicated column for it — Telegram users get a numeric username
    instead — so we re-derive it from `email` for every row that has one
    and compare in Python. The user table is small (single-digit thousands
    in practice) so the full scan is fine; if it ever isn't, materialize
    the username into a column."""
    from .provisioning import email_to_username

    async with async_session() as s:
        rows = (await s.execute(
            text(f"SELECT {_USER_COLS} FROM users WHERE email IS NOT NULL")
        )).all()
    for row in rows:
        email = row[1]
        if email and email_to_username(email) == username:
            return _row_to_user(row)
    return None


async def create_user_with_password(email: str, password_hash: str) -> int:
    """Create a Telegram-less user row. Returns the new user id.

    Raises sqlalchemy.exc.IntegrityError on email collision (caught by callers
    to surface a uniform "email taken" / "registered" response).
    """
    normalized = email.strip().lower()
    now = _utcnow_iso()
    async with async_session() as s:
        result = await s.execute(
            text(
                "INSERT INTO users (tg_id, email, password_hash, password_updated_at, "
                "api_provider, is_banned, vip) "
                "VALUES (NULL, :e, :p, :n, 'remnawave', 0, 0)"
            ),
            {"e": normalized, "p": password_hash, "n": now},
        )
        await s.commit()
        return int(result.lastrowid)


async def create_user_with_password_and_vless(
    email: str, password_hash: str, vless_uuid: str
) -> int:
    """Create a new Android-only user pre-bound to an existing Remnawave
    `vless_uuid`. Used by the migration flow when a Remnawave subscription
    exists but no `users` row references it yet.

    Raises sqlalchemy.exc.IntegrityError on email collision (the caller
    should check for collision in advance, since the migrate flow has
    branching logic for "email exists but no password")."""
    normalized = email.strip().lower()
    now = _utcnow_iso()
    async with async_session() as s:
        result = await s.execute(
            text(
                "INSERT INTO users (tg_id, email, password_hash, password_updated_at, "
                "vless_uuid, api_provider, is_banned, vip) "
                "VALUES (NULL, :e, :p, :n, :v, 'remnawave', 0, 0)"
            ),
            {"e": normalized, "p": password_hash, "n": now, "v": vless_uuid},
        )
        await s.commit()
        return int(result.lastrowid)


async def adopt_user_for_migration(
    user_id: int,
    email: str,
    password_hash: str,
    vless_uuid: str,
) -> None:
    """Fill `password_hash`, `email`, and `vless_uuid` on an existing row.
    Used when a user record exists (matched by vless_uuid/username/email)
    but is missing the credentials needed for Android login. Won't touch
    `email_verified_at` — that's still gated through `/email/verify`."""
    normalized = email.strip().lower()
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE users SET email = :e, password_hash = :p, "
                "password_updated_at = :n, vless_uuid = :v "
                "WHERE id = :i"
            ),
            {
                "e": normalized,
                "p": password_hash,
                "n": now,
                "v": vless_uuid,
                "i": user_id,
            },
        )
        await s.commit()


async def set_password(user_id: int, password_hash: str) -> None:
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE users SET password_hash = :p, password_updated_at = :n "
                "WHERE id = :i"
            ),
            {"p": password_hash, "n": now, "i": user_id},
        )
        await s.commit()


async def mark_email_verified(user_id: int) -> None:
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text("UPDATE users SET email_verified_at = :n WHERE id = :i"),
            {"n": now, "i": user_id},
        )
        await s.commit()


# --- Refresh tokens ---


async def store_refresh_token(
    *,
    user_id: int,
    family_id: str,
    token_hash: str,
    user_agent: str | None,
    ip: str | None,
) -> int:
    now = _utcnow_iso()
    expires = _expiry_iso(security.refresh_ttl_seconds())
    async with async_session() as s:
        result = await s.execute(
            text(
                "INSERT INTO refresh_tokens (user_id, family_id, token_hash, "
                "issued_at, expires_at, user_agent, ip) "
                "VALUES (:u, :f, :h, :i, :e, :ua, :ip)"
            ),
            {
                "u": user_id,
                "f": family_id,
                "h": token_hash,
                "i": now,
                "e": expires,
                "ua": (user_agent or "")[:255] or None,
                "ip": (ip or "")[:64] or None,
            },
        )
        await s.commit()
        return int(result.lastrowid)


@dataclass
class RefreshRow:
    id: int
    user_id: int
    family_id: str
    issued_at: str
    expires_at: str
    revoked_at: str | None
    replaced_by_id: int | None


async def find_refresh_by_hash(token_hash: str) -> RefreshRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(
                "SELECT id, user_id, family_id, issued_at, expires_at, "
                "revoked_at, replaced_by_id FROM refresh_tokens "
                "WHERE token_hash = :h LIMIT 1"
            ),
            {"h": token_hash},
        )).first()
    if row is None:
        return None
    return RefreshRow(
        id=row[0],
        user_id=row[1],
        family_id=row[2],
        issued_at=row[3],
        expires_at=row[4],
        revoked_at=row[5],
        replaced_by_id=row[6],
    )


async def rotate_refresh_token(
    *,
    old_id: int,
    user_id: int,
    family_id: str,
    new_token_hash: str,
    user_agent: str | None,
    ip: str | None,
) -> int:
    now = _utcnow_iso()
    expires = _expiry_iso(security.refresh_ttl_seconds())
    async with async_session() as s:
        result = await s.execute(
            text(
                "INSERT INTO refresh_tokens (user_id, family_id, token_hash, "
                "issued_at, expires_at, user_agent, ip) "
                "VALUES (:u, :f, :h, :i, :e, :ua, :ip)"
            ),
            {
                "u": user_id,
                "f": family_id,
                "h": new_token_hash,
                "i": now,
                "e": expires,
                "ua": (user_agent or "")[:255] or None,
                "ip": (ip or "")[:64] or None,
            },
        )
        new_id = int(result.lastrowid)
        await s.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = :n, replaced_by_id = :nid "
                "WHERE id = :oid"
            ),
            {"n": now, "nid": new_id, "oid": old_id},
        )
        await s.commit()
        return new_id


async def revoke_family(family_id: str) -> int:
    now = _utcnow_iso()
    async with async_session() as s:
        result = await s.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = :n "
                "WHERE family_id = :f AND revoked_at IS NULL"
            ),
            {"n": now, "f": family_id},
        )
        await s.commit()
        return int(result.rowcount or 0)


async def revoke_refresh_by_id(token_id: int) -> None:
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = :n "
                "WHERE id = :i AND revoked_at IS NULL"
            ),
            {"n": now, "i": token_id},
        )
        await s.commit()


async def revoke_all_user_tokens(user_id: int) -> int:
    now = _utcnow_iso()
    async with async_session() as s:
        result = await s.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = :n "
                "WHERE user_id = :u AND revoked_at IS NULL"
            ),
            {"n": now, "u": user_id},
        )
        await s.commit()
        return int(result.rowcount or 0)


async def revoke_user_email(user_id: int) -> None:
    """Drop email_verified_at — used after email change initiation if you
    wish to require re-verification of the old address. Currently unused
    in the change flow (we set new email + verified_at atomically) but
    kept for symmetry."""
    async with async_session() as s:
        await s.execute(
            text("UPDATE users SET email_verified_at = NULL WHERE id = :i"),
            {"i": user_id},
        )
        await s.commit()


async def update_user_email(user_id: int, new_email: str) -> None:
    normalized = new_email.strip().lower()
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE users SET email = :e, email_verified_at = :n WHERE id = :i"
            ),
            {"e": normalized, "n": now, "i": user_id},
        )
        await s.commit()


async def get_user_vless_uuid(user_id: int) -> str | None:
    async with async_session() as s:
        row = (await s.execute(
            text("SELECT vless_uuid FROM users WHERE id = :i"),
            {"i": user_id},
        )).first()
    return row[0] if row else None


async def set_user_vless_uuid(user_id: int, uuid: str) -> None:
    async with async_session() as s:
        await s.execute(
            text("UPDATE users SET vless_uuid = :u WHERE id = :i"),
            {"u": uuid, "i": user_id},
        )
        await s.commit()


# --- Email verification codes -----------------------------------------------


PURPOSE_VERIFY = "verify"
PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_EMAIL_CHANGE = "email_change"
PURPOSE_TG_LINK = "tg_link"


async def invalidate_pending_codes(user_id: int, purpose: str) -> None:
    """Mark every still-active code of `purpose` as used so a fresh one is
    the only valid candidate. Cheap protection against parallel requests."""
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE email_verifications SET used_at = :n "
                "WHERE user_id = :u AND purpose = :p AND used_at IS NULL"
            ),
            {"n": now, "u": user_id, "p": purpose},
        )
        await s.commit()


async def store_verification_code(
    *,
    user_id: int,
    purpose: str,
    code_hash: str,
    payload: str | None,
    ttl_seconds: int,
) -> int:
    now = _utcnow_iso()
    expires = _expiry_iso(ttl_seconds)
    async with async_session() as s:
        result = await s.execute(
            text(
                "INSERT INTO email_verifications "
                "(user_id, purpose, code_hash, payload, created_at, expires_at, attempts) "
                "VALUES (:u, :p, :h, :pl, :c, :e, 0)"
            ),
            {
                "u": user_id,
                "p": purpose,
                "h": code_hash,
                "pl": payload,
                "c": now,
                "e": expires,
            },
        )
        await s.commit()
        return int(result.lastrowid)


@dataclass
class VerificationRow:
    id: int
    user_id: int
    purpose: str
    code_hash: str
    payload: str | None
    expires_at: str
    used_at: str | None
    attempts: int


async def find_active_code(user_id: int, purpose: str) -> VerificationRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(
                "SELECT id, user_id, purpose, code_hash, payload, expires_at, "
                "used_at, attempts FROM email_verifications "
                "WHERE user_id = :u AND purpose = :p AND used_at IS NULL "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"u": user_id, "p": purpose},
        )).first()
    if row is None:
        return None
    return VerificationRow(
        id=row[0],
        user_id=row[1],
        purpose=row[2],
        code_hash=row[3],
        payload=row[4],
        expires_at=row[5],
        used_at=row[6],
        attempts=row[7] or 0,
    )


async def increment_code_attempts(code_id: int) -> int:
    async with async_session() as s:
        await s.execute(
            text(
                "UPDATE email_verifications SET attempts = attempts + 1 "
                "WHERE id = :i"
            ),
            {"i": code_id},
        )
        row = (await s.execute(
            text("SELECT attempts FROM email_verifications WHERE id = :i"),
            {"i": code_id},
        )).first()
        await s.commit()
    return int(row[0]) if row else 0


async def mark_code_used(code_id: int) -> None:
    now = _utcnow_iso()
    async with async_session() as s:
        await s.execute(
            text("UPDATE email_verifications SET used_at = :n WHERE id = :i"),
            {"n": now, "i": code_id},
        )
        await s.commit()


async def find_active_code_by_purpose_and_hash(
    purpose: str, code_hash: str
) -> VerificationRow | None:
    """Bot-side lookup: the Telegram side knows the code (hashed) and purpose
    but not which user_id it belongs to. Constant-time comparison happens at
    the SQL layer via exact match on the hash column."""
    async with async_session() as s:
        row = (await s.execute(
            text(
                "SELECT id, user_id, purpose, code_hash, payload, expires_at, "
                "used_at, attempts FROM email_verifications "
                "WHERE purpose = :p AND code_hash = :h AND used_at IS NULL "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"p": purpose, "h": code_hash},
        )).first()
    if row is None:
        return None
    return VerificationRow(
        id=row[0],
        user_id=row[1],
        purpose=row[2],
        code_hash=row[3],
        payload=row[4],
        expires_at=row[5],
        used_at=row[6],
        attempts=row[7] or 0,
    )


async def find_user_by_tg_id(tg_id: int) -> UserRow | None:
    async with async_session() as s:
        row = (await s.execute(
            text(f"SELECT {_USER_COLS} FROM users WHERE tg_id = :t LIMIT 1"),
            {"t": tg_id},
        )).first()
    return _row_to_user(row)


async def set_user_tg_id(user_id: int, tg_id: int) -> None:
    async with async_session() as s:
        await s.execute(
            text("UPDATE users SET tg_id = :t WHERE id = :i"),
            {"t": tg_id, "i": user_id},
        )
        await s.commit()


async def clear_user_tg_id(user_id: int) -> None:
    async with async_session() as s:
        await s.execute(
            text("UPDATE users SET tg_id = NULL WHERE id = :i"),
            {"i": user_id},
        )
        await s.commit()


async def list_active_sessions(user_id: int) -> list[dict[str, Any]]:
    async with async_session() as s:
        rows = (await s.execute(
            text(
                "SELECT id, family_id, issued_at, expires_at, user_agent, ip "
                "FROM refresh_tokens "
                "WHERE user_id = :u AND revoked_at IS NULL "
                "AND expires_at > :now "
                "ORDER BY issued_at DESC"
            ),
            {"u": user_id, "now": _utcnow_iso()},
        )).all()
    return [
        {
            "id": r[0],
            "family_id": r[1],
            "issued_at": r[2],
            "expires_at": r[3],
            "user_agent": r[4],
            "ip": r[5],
        }
        for r in rows
    ]
