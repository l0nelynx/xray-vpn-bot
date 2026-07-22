"""FCM token CRUD (Android push registration)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AndroidFcmToken


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def upsert_token(
    session: AsyncSession,
    *,
    user_id: int,
    token: str,
    platform: str = "android",
    app_version: str | None = None,
) -> AndroidFcmToken:
    """Bind ``token`` to ``user_id``. Reassigns if the token belonged to another user."""
    now = _now_iso()
    existing = await session.scalar(
        select(AndroidFcmToken).where(AndroidFcmToken.token == token)
    )
    if existing is not None:
        existing.user_id = user_id
        existing.platform = platform or "android"
        existing.app_version = app_version
        existing.updated_at = now
        await session.flush()
        return existing

    row = AndroidFcmToken(
        user_id=user_id,
        token=token,
        platform=platform or "android",
        app_version=app_version,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def delete_token(
    session: AsyncSession, *, user_id: int, token: str
) -> bool:
    result = await session.execute(
        delete(AndroidFcmToken).where(
            AndroidFcmToken.user_id == user_id,
            AndroidFcmToken.token == token,
        )
    )
    await session.flush()
    return (result.rowcount or 0) > 0


async def delete_token_by_value(session: AsyncSession, token: str) -> bool:
    """Remove a dead/unregistered FCM token regardless of owner."""
    result = await session.execute(
        delete(AndroidFcmToken).where(AndroidFcmToken.token == token)
    )
    await session.flush()
    return (result.rowcount or 0) > 0


async def count_tokens(session: AsyncSession) -> int:
    return int(
        await session.scalar(select(func.count()).select_from(AndroidFcmToken)) or 0
    )


async def list_tokens_all(session: AsyncSession) -> list[AndroidFcmToken]:
    result = await session.scalars(select(AndroidFcmToken))
    return list(result)


async def list_tokens_for_users(
    session: AsyncSession, user_ids: list[int]
) -> list[AndroidFcmToken]:
    if not user_ids:
        return []
    result = await session.scalars(
        select(AndroidFcmToken).where(AndroidFcmToken.user_id.in_(user_ids))
    )
    return list(result)
