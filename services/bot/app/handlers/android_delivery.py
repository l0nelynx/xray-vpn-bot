"""Android paid-subscription delivery — seller-bot binding.

The delivery logic now lives in the shared ``subscription_delivery`` package so
the miniapp's Google Play IAP path can reuse it without importing from the bot.
This module is a thin adapter that wires the seller bot's own DB session, admin
notifier and tariff-slug resolver into the shared entry point.

Used by ``app/api/handlers.py`` for the fiat payment webhook delivery path.
"""
from __future__ import annotations

from typing import Optional

from subscription_delivery import deliver_android_paid as _deliver

from app.database.models import async_session
from app.notify_log import notify_log


async def deliver_android_paid(
    *,
    transaction_id: str,
    android_user_id: int,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
    delivery_target: Optional[dict] = None,
) -> dict:
    return await _deliver(
        transaction_id=transaction_id,
        android_user_id=android_user_id,
        email=email,
        days=days,
        tariff_slug=tariff_slug,
        delivery_target=delivery_target,
        session_factory=async_session,
        notifier=notify_log,
        squad_resolver=None,
    )
