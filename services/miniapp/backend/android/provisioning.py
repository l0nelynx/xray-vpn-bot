"""Free Remnawave provisioning for Android-API users.

When an Android user verifies their email we eagerly hand them a FREE
subscription on Remnawave, mirroring the bot's onboarding. This module
contains only the Remnawave side-effects + DB persistence of `rw_id`;
caller chooses *when* to invoke it.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import text

from remnawave_client import (
    RemnawaveClient,
    SubscriptionScenario,
    SubscriptionType,
    apply_new_user,
    apply_update,
    configure,
    resolve_scenario,
)
from remnawave_client import api as rem
from subscription_delivery import build_remnawave_username
from common_db.repo import subscriptions as subscription_repo

from ..config import (
    get_free_days,
    get_free_traffic,
    get_remnawave_token,
    get_remnawave_url,
    get_rw_free_id,
)
from . import repo
from ..database.session import async_session
from ..notify_log import notify_log

logger = logging.getLogger(__name__)


_USERNAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def _rw_client() -> RemnawaveClient:
    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id=get_rw_free_id(),
    )


def email_to_username(email: str) -> str:
    """`lynx@example.com` -> `lynx_at_example_com`.

    Remnawave usernames must match its character class; we keep them stable
    across the lifetime of the account (renames go via the email field, not
    the username) so support tickets can correlate.
    """
    local, _, domain = email.strip().lower().partition("@")
    raw = f"{local}_at_{domain}" if domain else local
    sanitized = _USERNAME_RE.sub("_", raw).strip("_")
    return sanitized or "user"


async def ensure_free_subscription(user_id: int, email: str) -> int | None:
    """Create or refresh a FREE Remnawave subscription for `user_id`.

    Returns the user's rw_id (newly created or pre-existing) or None on
    Remnawave failure. Saves rw_id so subsequent
    calls can short-circuit without another Remnawave round-trip.
    """
    free_squad = get_rw_free_id() or None
    days = get_free_days()
    limit_gb = get_free_traffic()
    client = _rw_client()
    user = await repo.find_user_by_id(user_id)
    if user is None:
        logger.error("ensure_free_subscription: local user %s not found", user_id)
        return None
    async with async_session() as session:
        primary = await subscription_repo.get_primary(session, user_id)
        start = await subscription_repo.count_for_user(session, user_id)

    user_info = await rem.resolve_remnawave_user(
        rw_id=primary.rw_id if primary else user.rw_id,
        email=email,
        username=user.username,
        expected_telegram_id=user.tg_id,
    )
    if user_info is None and user.username:
        legacy = await client.get_user_by_username(
            user.username, raise_on_error=True,
        )
        if legacy:
            await notify_log(
                "⚠️ <b>legacy_username_collision</b>\n"
                f"DB user: <code>{user_id}</code>\n"
                f"TG: <code>{user.tg_id or '—'}</code> @{user.username}\n"
                f"matched rw_id: <code>{legacy.get('rw_id') or '—'}</code>"
            )
    existing_rw_id = int(user_info["rw_id"]) if user_info and user_info.get("rw_id") is not None else user.rw_id
    if existing_rw_id is not None:
        async with async_session() as session:
            await subscription_repo.attach(
                session, user_id=user_id, rw_id=int(existing_rw_id),
                source="android_free_resolve",
            )
            await session.commit()

    scenario = resolve_scenario(user_info, SubscriptionType.FREE)

    if scenario == SubscriptionScenario.ALREADY_ACTIVE:
        return existing_rw_id

    if scenario == SubscriptionScenario.NEW_USER:
        marker = f"provisioning:android-free:{user_id}"
        created = None
        for ordinal in range(start, start + 100):
            candidate = build_remnawave_username(user.username, user_id, ordinal)
            occupied = await client.get_user_by_username(
                candidate, raise_on_error=True,
            )
            if occupied:
                if marker in str(occupied.get("description") or ""):
                    created = occupied
                    break
                continue
            description = (
                f"{marker}; db_user_id:{user_id}; "
                f"tg_id:{user.tg_id if user.tg_id is not None else 'none'}; "
                f"source:android; tg_username:{user.username or 'none'}; "
                "Android free signup"
            )
            created = await apply_new_user(
                username=candidate,
                telegram_id=user.tg_id or 0,
                days=days,
                limit_gb=limit_gb,
                email=email,
                description=description,
                squad_id=free_squad,
                client=client,
                strict=True,
            )
            appeared = await client.get_user_by_username(
                candidate, raise_on_error=True,
            )
            if appeared and marker in str(appeared.get("description") or ""):
                created = appeared
            elif appeared:
                created = None
                continue
            elif not created:
                logger.error("Remnawave create_user failed for %s", candidate)
                return None
            break
        if not created or created.get("rw_id") is None:
            logger.error("Remnawave username allocation failed for user %s", user_id)
            return None
        created_rw_id = int(created["rw_id"])
        async with async_session() as session:
            link = await subscription_repo.attach(
                session, user_id=user_id, rw_id=created_rw_id,
                source="android_free_created",
            )
            if link.is_primary:
                await session.execute(
                    text("UPDATE users SET rw_id = :r WHERE id = :u"),
                    {"r": created_rw_id, "u": user_id},
                )
            await session.commit()
        return created_rw_id

    # UPDATE / LIMITED / EXTEND-on-FREE: refresh the existing record.
    if existing_rw_id is None or not user_info:
        logger.error(
            "ensure_free_subscription: scenario=%s but no rw_id for user_id=%s",
            scenario, user_id,
        )
        return None
    await apply_update(
        rw_id=int(existing_rw_id),
        username=user_info.get("username") or build_remnawave_username(
            user.username, user_id, 0
        ),
        days=days,
        limit_gb=limit_gb,
        squad_id=free_squad,
        status="active",
        description="Android free refresh",
        client=client,
        strict=True,
    )
    return int(existing_rw_id)


async def rename_remnawave_email(user_id: int, new_email: str) -> None:
    """Update Remnawave's `email` field after the user changes their address.

    Username stays constant (see module docstring). Failures are logged but
    not raised — the email column in our DB is the source of truth.
    """
    user = await repo.find_user_by_id(user_id)
    if user is None or user.rw_id is None:
        return
    try:
        await _rw_client().update_user_by_id(
            rw_id=int(user.rw_id),
            email=new_email.strip().lower(),
        )
    except Exception as exc:
        logger.warning("Remnawave email rename for rw_id=%s failed: %s", user.rw_id, exc)
