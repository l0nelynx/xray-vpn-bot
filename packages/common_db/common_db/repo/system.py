"""Singleton-row helpers.

CacheVersion, PromoSettings and TelmtFreeParams are all "single row at id=1"
configuration tables. Each service that wanted to read them was doing the
same ``select(Model).where(Model.id == 1)`` over and over, and at least one
service forgot to handle the case where the row was never seeded.

This module solves both problems with one primitive — ``get_or_create_singleton``
— and exposes friendly wrappers on top of it.
"""
from __future__ import annotations

from typing import Mapping, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import Base
from ..models import BotFeatureFlags, CacheVersion, PromoSettings, TelmtFreeParams

# All singletons in this codebase live at id == 1. If that ever needs to
# change for a specific table, override via the ``row_id`` parameter.
DEFAULT_ROW_ID = 1


_M = TypeVar("_M", bound=Base)


async def get_or_create_singleton(
    session: AsyncSession,
    model: type[_M],
    *,
    row_id: int = DEFAULT_ROW_ID,
    defaults: Mapping[str, object] | None = None,
) -> _M:
    """Fetch ``model`` row at ``row_id``; insert with ``defaults`` if missing.

    The new row is flushed (but not committed) so the caller gets a real
    autoincrement-assigned object back. The caller still owns the transaction.

    Why flush-but-don't-commit: the bot startup orchestrator (`async_main`)
    seeds these tables inside its own session/commit cycle, and we want
    `repo.system.get_*` calls to *also* be safe when called by routers that
    happen to be the first to ever touch the row (e.g. fresh dev DB).
    """
    existing = await session.scalar(select(model).where(model.id == row_id))
    if existing is not None:
        return existing

    payload: dict[str, object] = {"id": row_id}
    if defaults:
        payload.update(defaults)
    row = model(**payload)
    session.add(row)
    await session.flush()
    return row


# --- PromoSettings -----------------------------------------------------------

# Why 20: matches the seed in app/database/models.py::_seed_promo_settings.
# Keep both in sync — when one changes, change the other.
DEFAULT_PROMO_DISCOUNT_PERCENT = 20
DEFAULT_CREDIT_GRANT = 100
# Reward tunables — bonus points (🪙) for referral owners.
DEFAULT_POINTS_REWARD_PER_30 = 30
DEFAULT_REWARD_CAP_POINTS = 1800


async def get_promo_settings(session: AsyncSession) -> PromoSettings:
    """Return the (only) PromoSettings row, creating it on first call."""
    return await get_or_create_singleton(
        session,
        PromoSettings,
        defaults={
            "default_discount_percent": DEFAULT_PROMO_DISCOUNT_PERCENT,
            "default_credit_grant": DEFAULT_CREDIT_GRANT,
            "points_reward_per_30": DEFAULT_POINTS_REWARD_PER_30,
            "reward_cap_points": DEFAULT_REWARD_CAP_POINTS,
        },
    )


async def get_default_credit_grant(session: AsyncSession) -> int:
    """Default credits a code grants when it has no per-code override."""
    settings = await get_promo_settings(session)
    return settings.default_credit_grant


async def get_default_discount_percent(session: AsyncSession) -> int:
    """Convenience: the integer percent, unwrapped.

    Both app/ and miniapp/ were duplicating the lookup-then-attribute-access
    pattern; this collapses it to one call.
    """
    settings = await get_promo_settings(session)
    return settings.default_discount_percent


async def get_points_reward_per_30(session: AsyncSession) -> int:
    """Bonus points granted to referral owner per 30 invitee-days purchased."""
    settings = await get_promo_settings(session)
    return settings.points_reward_per_30


async def get_reward_cap_points(session: AsyncSession) -> int:
    """Cumulative cap (points) on referral owner rewards for one code."""
    settings = await get_promo_settings(session)
    return settings.reward_cap_points


# --- TelmtFreeParams ---------------------------------------------------------

# Defaults match `_seed_telemt_free_params` in app/database/models.py.
DEFAULT_TELMT_EXPIRE_DAYS = 30


async def get_telmt_free_params(session: AsyncSession) -> TelmtFreeParams:
    """Return the (only) TelmtFreeParams row, creating it on first call."""
    return await get_or_create_singleton(
        session,
        TelmtFreeParams,
        defaults={
            "max_tcp_conns": None,
            "max_unique_ips": None,
            "data_quota_bytes": None,
            "expire_days": DEFAULT_TELMT_EXPIRE_DAYS,
            "rate_limit_up_bps": None,
            "rate_limit_down_bps": None,
        },
    )


# --- CacheVersion ------------------------------------------------------------


async def get_cache_version(session: AsyncSession) -> int:
    """Return the current cache version number (creates row with 0 if missing)."""
    row = await get_or_create_singleton(
        session, CacheVersion, defaults={"version": 0}
    )
    return row.version


async def bump_cache_version(session: AsyncSession) -> int:
    """Atomically increment cache_version.version and return the new value.

    Single-row UPDATE so concurrent callers don't trample each other. The
    caller still needs to commit; the helper does not because dashboard's
    cache-bump can happen inside a larger write (e.g. updating a menu screen
    and bumping the cache in the same transaction).
    """
    # Ensure the row exists before bumping — fresh DBs start with no row.
    await get_or_create_singleton(session, CacheVersion, defaults={"version": 0})
    stmt = (
        update(CacheVersion)
        .where(CacheVersion.id == DEFAULT_ROW_ID)
        .values(version=CacheVersion.version + 1)
        .returning(CacheVersion.version)
    )
    result = await session.execute(stmt)
    new_value = result.scalar_one()
    return new_value


# --- BotFeatureFlags ---------------------------------------------------------


async def get_bot_feature_flags(session: AsyncSession) -> BotFeatureFlags:
    """Return the (only) BotFeatureFlags row, creating it on first call."""
    return await get_or_create_singleton(
        session,
        BotFeatureFlags,
        defaults={"legacy_bot_constructor": False},
    )


__all__ = [
    "DEFAULT_CREDIT_GRANT",
    "DEFAULT_POINTS_REWARD_PER_30",
    "DEFAULT_PROMO_DISCOUNT_PERCENT",
    "DEFAULT_REWARD_CAP_POINTS",
    "DEFAULT_TELMT_EXPIRE_DAYS",
    "bump_cache_version",
    "get_bot_feature_flags",
    "get_cache_version",
    "get_points_reward_per_30",
    "get_default_credit_grant",
    "get_default_discount_percent",
    "get_or_create_singleton",
    "get_promo_settings",
    "get_reward_cap_points",
    "get_telmt_free_params",
]
