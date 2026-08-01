"""Account-to-Remnawave subscription relationships."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserSubscription


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def list_for_user(
    session: AsyncSession, user_id: int
) -> list[UserSubscription]:
    rows = await session.scalars(
        select(UserSubscription)
        .where(UserSubscription.user_id == user_id)
        .order_by(UserSubscription.is_primary.desc(), UserSubscription.id)
    )
    return list(rows)


async def get_by_rw_id(
    session: AsyncSession, rw_id: int
) -> UserSubscription | None:
    return await session.scalar(
        select(UserSubscription).where(UserSubscription.rw_id == int(rw_id))
    )


async def get_for_user(
    session: AsyncSession, *, user_id: int, subscription_id: int
) -> UserSubscription | None:
    return await session.scalar(
        select(UserSubscription).where(
            UserSubscription.id == subscription_id,
            UserSubscription.user_id == user_id,
        )
    )


async def get_primary(
    session: AsyncSession, user_id: int
) -> UserSubscription | None:
    return await session.scalar(
        select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.is_primary.is_(True),
        )
    )


async def count_for_user(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(UserSubscription)
            .where(UserSubscription.user_id == user_id)
        )
        or 0
    )


async def attach(
    session: AsyncSession,
    *,
    user_id: int,
    rw_id: int,
    source: str,
    product_key: str | None = None,
    label: str | None = None,
    make_primary: bool = False,
) -> UserSubscription:
    """Attach an unowned subscription or refresh its metadata.

    Ownership cannot be silently moved between accounts. A transfer is a
    distinct, audited business operation and must not call this helper.
    """
    existing = await get_by_rw_id(session, rw_id)
    if existing is not None and existing.user_id != user_id:
        raise ValueError("subscription_already_linked")

    current = await list_for_user(session, user_id)
    make_primary = make_primary or not current
    now = _now_iso()

    if make_primary:
        await session.execute(
            update(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.is_primary.is_(True),
            )
            .values(is_primary=False, updated_at=now)
        )

    if existing is None:
        existing = UserSubscription(
            user_id=user_id,
            rw_id=int(rw_id),
            product_key=product_key,
            label=label,
            source=source,
            is_primary=make_primary,
            created_at=now,
            updated_at=now,
        )
        session.add(existing)
    else:
        existing.product_key = product_key or existing.product_key
        existing.label = label or existing.label
        existing.source = source or existing.source
        existing.is_primary = make_primary or existing.is_primary
        existing.updated_at = now

    if existing.is_primary:
        user = await session.get(User, user_id)
        if user is None:
            raise ValueError("user_not_found")
        user.rw_id = int(rw_id)

    await session.flush()
    return existing


async def set_primary(
    session: AsyncSession, *, user_id: int, subscription_id: int
) -> UserSubscription | None:
    target = await session.scalar(
        select(UserSubscription).where(
            UserSubscription.id == subscription_id,
            UserSubscription.user_id == user_id,
        )
    )
    if target is None:
        return None

    now = _now_iso()
    await session.execute(
        update(UserSubscription)
        .where(UserSubscription.user_id == user_id)
        .values(is_primary=False, updated_at=now)
    )
    target.is_primary = True
    target.updated_at = now
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("user_not_found")
    user.rw_id = target.rw_id
    await session.flush()
    return target


async def rename_label(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
    label: str | None,
) -> UserSubscription | None:
    target = await get_for_user(
        session, user_id=user_id, subscription_id=subscription_id
    )
    if target is None:
        return None
    target.label = label
    target.updated_at = _now_iso()
    await session.flush()
    return target


async def detach(
    session: AsyncSession, *, user_id: int, subscription_id: int
) -> UserSubscription | None:
    """Remove only the local ownership link, never the Remnawave user."""
    target = await get_for_user(
        session, user_id=user_id, subscription_id=subscription_id
    )
    if target is None:
        return None

    total = await count_for_user(session, user_id)
    if target.is_primary and total > 1:
        raise ValueError("primary_change_required")

    await session.execute(
        delete(UserSubscription).where(UserSubscription.id == target.id)
    )
    if total == 1:
        user = await session.get(User, user_id)
        if user is None:
            raise ValueError("user_not_found")
        user.rw_id = None
        # users.vless_uuid is the historical Remnawave panel-user UUID. It is
        # no longer an ownership key, but remains immutable audit/rollback data.
    await session.flush()
    return target


__all__ = [
    "attach",
    "count_for_user",
    "detach",
    "get_by_rw_id",
    "get_for_user",
    "get_primary",
    "list_for_user",
    "rename_label",
    "set_primary",
]
