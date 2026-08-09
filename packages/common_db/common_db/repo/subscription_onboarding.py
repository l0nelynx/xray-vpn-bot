"""Pending subscription-page registration and first-profile attachment."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PendingSubscriptionOnboarding, User
from . import subscriptions

OnboardingStatus = Literal[
    "attached",
    "awaiting_oauth",
    "already_attached",
    "skipped_nonempty",
    "conflict",
    "none",
]

PENDING_TTL_SECONDS = 24 * 60 * 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _expires_iso() -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=PENDING_TTL_SECONDS)
    ).isoformat(timespec="seconds")


async def create(
    session: AsyncSession, *, user_id: int, rw_id: int | None
) -> PendingSubscriptionOnboarding:
    row = PendingSubscriptionOnboarding(
        user_id=user_id,
        rw_id=int(rw_id) if rw_id is not None else None,
        created_at=_now_iso(),
        expires_at=_expires_iso(),
    )
    session.add(row)
    await session.flush()
    return row


async def get_active(
    session: AsyncSession, user_id: int
) -> PendingSubscriptionOnboarding | None:
    row = await session.get(PendingSubscriptionOnboarding, user_id)
    if row is None:
        return None
    if row.expires_at <= _now_iso():
        await session.delete(row)
        await session.flush()
        return None
    return row


async def clear(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        delete(PendingSubscriptionOnboarding).where(
            PendingSubscriptionOnboarding.user_id == user_id
        )
    )
    await session.flush()


async def finalize_email_verification(
    session: AsyncSession, *, user_id: int
) -> OnboardingStatus:
    """Mark email verified and consume a legacy pending rw_id if available."""
    user = await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if user is None:
        raise ValueError("user_not_found")
    user.email_verified_at = _now_iso()

    pending = await get_active(session, user_id)
    if pending is None:
        await session.flush()
        return "none"

    current = await subscriptions.list_for_user(session, user_id)
    if current:
        status: OnboardingStatus = (
            "already_attached"
            if pending.rw_id is not None
            and any(item.rw_id == pending.rw_id for item in current)
            else "skipped_nonempty"
        )
        await clear(session, user_id)
        return status

    if pending.rw_id is None:
        await session.flush()
        return "awaiting_oauth"

    owner = await subscriptions.get_by_rw_id(session, pending.rw_id)
    if owner is not None and owner.user_id != user_id:
        await clear(session, user_id)
        return "conflict"

    linked = await subscriptions.attach(
        session,
        user_id=user_id,
        rw_id=pending.rw_id,
        source="subscription_page_registration",
        make_primary=True,
    )
    await clear(session, user_id)
    return "already_attached" if owner is not None else "attached"


async def attach_initial(
    session: AsyncSession, *, user_id: int, rw_id: int
) -> tuple[Literal["attached", "already_attached", "skipped_nonempty"], int | None, bool]:
    """Attach ``rw_id`` only when this account still has no subscriptions."""
    user = await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if user is None:
        raise ValueError("user_not_found")

    owner = await subscriptions.get_by_rw_id(session, rw_id)
    if owner is not None:
        if owner.user_id != user_id:
            raise ValueError("subscription_already_linked")
        await clear(session, user_id)
        return "already_attached", owner.id, owner.is_primary

    current = await subscriptions.list_for_user(session, user_id)
    if current:
        await clear(session, user_id)
        return "skipped_nonempty", None, False

    linked = await subscriptions.attach(
        session,
        user_id=user_id,
        rw_id=int(rw_id),
        source="subscription_page_oauth",
        make_primary=True,
    )
    await clear(session, user_id)
    return "attached", linked.id, linked.is_primary
