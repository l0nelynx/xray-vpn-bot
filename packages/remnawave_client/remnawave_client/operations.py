"""High-level Remnawave operations used during subscription delivery.

These functions wrap RemnawaveClient with the create/extend/update logic that
was previously duplicated between app/handlers/tools.py and miniapp routers.
They are deliberately thin and side-effect-free outside Remnawave: they do
NOT touch any database, do NOT send Telegram messages, and do NOT know about
tariffs, referrals, or localization. Callers handle those concerns.

Each function returns a dict with at least:
    {
        "uuid": str | None,
        "subscription_url": str | None,
        "expire": int | None,           # unix timestamp
        "status": str | None,
    }

If the underlying Remnawave call fails, returns None. (RemnawaveClient already
logs the failure.)
"""

import time
from typing import Optional

from .client import RemnawaveClient, get_default_client


def _client(client: Optional[RemnawaveClient]) -> RemnawaveClient:
    return client or get_default_client()


def _coerce_days(days: int) -> int:
    """Defend against accidental UNIX-timestamps being passed as days."""
    if days > 10000:
        coerced = max(1, round((days - time.time()) / 86400))
        return coerced
    return days


async def apply_new_user(
    *,
    username: str,
    telegram_id: int,
    days: int,
    limit_gb: int = 0,
    email: Optional[str] = None,
    description: str = "Telegram subscription",
    squad_id: Optional[str] = None,
    external_squad_id: Optional[str] = None,
    client: Optional[RemnawaveClient] = None,
) -> dict | None:
    """Create a new Remnawave user."""
    return await _client(client).create_user(
        username=username,
        telegram_id=telegram_id,
        days=_coerce_days(days),
        limit_gb=limit_gb,
        email=email,
        descr=description,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
    )


async def apply_extend(
    *,
    user_uuid: str,
    username: str,
    days: int,
    current_days_left: int,
    squad_id: Optional[str] = None,
    external_squad_id: Optional[str] = None,
    description: Optional[str] = "extended via remnawave_client",
    client: Optional[RemnawaveClient] = None,
) -> dict | None:
    """Extend an existing PAID subscription: new_expire = current_days_left + days,
    no traffic limit, kept on the given squad."""
    new_total = (
        current_days_left + days if isinstance(current_days_left, int) else days
    )
    return await _client(client).update_user(
        user_uuid=user_uuid,
        username=username,
        days=_coerce_days(new_total),
        limit_gb=0,
        descr=description,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
    )


async def apply_update(
    *,
    user_uuid: str,
    username: str,
    days: int,
    limit_gb: int = 0,
    squad_id: Optional[str] = None,
    external_squad_id: Optional[str] = None,
    status: Optional[str] = None,
    description: Optional[str] = "updated via remnawave_client",
    client: Optional[RemnawaveClient] = None,
) -> dict | None:
    """Replace subscription parameters wholesale (used when switching FREE↔PAID
    or refreshing a limited/expired user)."""
    return await _client(client).update_user(
        user_uuid=user_uuid,
        username=username,
        days=_coerce_days(days),
        limit_gb=limit_gb,
        descr=description,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
        status=status,
    )
