"""User lookups and "is paid" predicates.

Every service that has a tg_id wants the same things:
- "give me the User row for this tg_id"
- "is this user currently paid?"

The five sites doing the second query (app/requests.py ×3,
dashboard/users.py, dashboard/stats.py) use the *exact same predicate*:

    Transaction.order_status IN ('confirmed', 'delivered')
    AND Transaction.expire_date > now()

If that definition ever needs to change (e.g. add a 'refunded' status,
or move expire_date to a separate table), this is the one file to edit.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, User

# The canonical set of order_status values that mean "this transaction
# actually delivered VPN time to the user". `created` and `cancelled`
# are not paid; `confirmed` is the post-payment-pre-delivery state and
# `delivered` is the terminal success state. Keep this list in lockstep
# with app/database/requests.py — the migration runner relies on the
# same set in alembic/versions/0002_align_with_models.py.
PAID_ORDER_STATUSES: tuple[str, ...] = ("confirmed", "delivered")


def _now_iso(now: datetime | None) -> str:
    """Return an ISO timestamp suitable for comparing against
    Transaction.expire_date (which is stored as a string)."""
    if now is None:
        now = datetime.now()
    return now.isoformat(timespec="seconds")


# --- single-row lookups ---------------------------------------------------


async def get_user_by_tg_id(
    session: AsyncSession, tg_id: int
) -> User | None:
    """The single most common query in this codebase. ~17 inline copies
    collapse into one call."""
    return await session.scalar(select(User).where(User.tg_id == tg_id))


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Internal PK lookup. Prefer ``session.get(User, user_id)`` when in
    a router that already has the session — this helper exists for
    consistency with the other lookups."""
    return await session.scalar(select(User).where(User.id == user_id))


async def get_user_by_email(
    session: AsyncSession, email: str
) -> User | None:
    """Lookup by email. Unique-among-non-null by way of
    `ix_users_email_unique`. Case-sensitive — callers wanting
    case-insensitive should pass an already-lowercased value (matches
    historical behaviour in app/database/requests.py)."""
    if not email:
        return None
    return await session.scalar(select(User).where(User.email == email))


async def get_user_by_username(
    session: AsyncSession, username: str
) -> User | None:
    """Lookup by Telegram @username. Not unique in the schema (alembic
    revision 0009 dropped the UNIQUE constraint), so multiple rows may
    technically match; we return whichever the DB picks first. The
    paginated admin-side lookup belongs in app/requests.py instead."""
    if not username:
        return None
    return await session.scalar(select(User).where(User.username == username))


async def get_user_by_vless_uuid(
    session: AsyncSession, vless_uuid: str
) -> User | None:
    """Reverse lookup: Remnawave user UUID → local User row."""
    if not vless_uuid:
        return None
    return await session.scalar(
        select(User).where(User.vless_uuid == vless_uuid)
    )


# --- "is paid" predicates -------------------------------------------------


async def user_has_active_paid_transaction(
    session: AsyncSession, tg_id: int, *, now: datetime | None = None
) -> bool:
    """True if the user identified by ``tg_id`` currently holds a paid
    subscription that has not yet expired.

    This is the canonical predicate. ``user_has_transactions`` in
    app/database/requests.py is a *different* predicate (ever had any
    transaction) and is not what callers usually mean.
    """
    now_iso = _now_iso(now)
    stmt = select(
        exists(
            select(Transaction.user_id)
            .join(User, User.id == Transaction.user_id)
            .where(
                User.tg_id == tg_id,
                Transaction.order_status.in_(PAID_ORDER_STATUSES),
                Transaction.expire_date > now_iso,
            )
        )
    )
    return bool(await session.scalar(stmt))


async def user_has_any_transaction(
    session: AsyncSession, tg_id: int
) -> bool:
    """True if the user has *ever* had any transaction (paid, expired,
    cancelled — anything). This is the "is this a brand-new user?" predicate
    used to gate referral promo codes to first-time users.

    Distinct from ``user_has_active_paid_transaction`` (currently-active
    paid only). Mirrors app/database/requests.py::user_has_transactions but
    lives here so miniapp can share it.
    """
    stmt = select(
        exists(
            select(Transaction.transaction_id)
            .join(User, User.id == Transaction.user_id)
            .where(User.tg_id == tg_id)
        )
    )
    return bool(await session.scalar(stmt))


async def count_paid_users(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    """Distinct users with a currently-active paid transaction.

    Replaces the duplicated COUNT(DISTINCT) in:
    - app/database/requests.py::get_paid_users_count
    - dashboard/backend/routers/users.py (paid count in users_count)
    - dashboard/backend/routers/stats.py (paid count in overview)
    """
    now_iso = _now_iso(now)
    stmt = (
        select(func.count(func.distinct(Transaction.user_id)))
        .select_from(Transaction)
        .where(
            Transaction.order_status.in_(PAID_ORDER_STATUSES),
            Transaction.expire_date > now_iso,
        )
    )
    return (await session.scalar(stmt)) or 0


async def count_users(session: AsyncSession) -> int:
    """Total user count. Tiny but duplicated 3+ times across services."""
    return (await session.scalar(select(func.count()).select_from(User))) or 0


def active_paid_user_ids_subquery(now: datetime | None = None):
    """Reusable correlated subquery yielding user_ids that are currently
    paid. Used by dashboard's users-pagination ``is_paid`` flag and
    ``filter=paid|free`` switch — and by app's pagination doing the
    same thing.

    Returns a Core ``select`` object, not a coroutine. Wrap with
    ``.subquery()`` or use ``.in_()`` / ``.exists()`` against it.
    """
    now_iso = _now_iso(now)
    return select(Transaction.user_id).where(
        Transaction.order_status.in_(PAID_ORDER_STATUSES),
        Transaction.expire_date > now_iso,
    ).distinct()


# --- bulk reads -----------------------------------------------------------


async def get_all_tg_ids(session: AsyncSession) -> list[int]:
    """Flat list of every user's Telegram ID. Used by the bot's
    broadcast/announce loop. Wraps `session.scalars(select(User.tg_id))`."""
    result = await session.scalars(select(User.tg_id))
    return [tid for tid in result if tid is not None]


async def get_users_by_tg_ids(
    session: AsyncSession, tg_ids: Iterable[int]
) -> list[User]:
    """Batch fetch for a known set of tg_ids. Order is not guaranteed."""
    tg_ids = list(tg_ids)
    if not tg_ids:
        return []
    result = await session.scalars(select(User).where(User.tg_id.in_(tg_ids)))
    return list(result)


async def persist_remnawave_uuid(
    session: AsyncSession,
    *,
    tg_id: int,
    vless_uuid: str,
    username: str | None = None,
    rw_id: int | None = None,
) -> bool:
    """Write Remnawave uuid (and optional panel id) onto the local user row."""
    if not vless_uuid:
        return False
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return False
    user.vless_uuid = str(vless_uuid)
    user.api_provider = "remnawave"
    if rw_id is not None:
        user.rw_id = rw_id
    if username:
        user.username = username
    await session.flush()
    return True


__all__ = [
    "PAID_ORDER_STATUSES",
    "active_paid_user_ids_subquery",
    "count_paid_users",
    "count_users",
    "get_all_tg_ids",
    "get_user_by_email",
    "get_user_by_id",
    "get_user_by_tg_id",
    "get_user_by_username",
    "get_users_by_tg_ids",
    "persist_remnawave_uuid",
    "user_has_active_paid_transaction",
    "user_has_any_transaction",
]
