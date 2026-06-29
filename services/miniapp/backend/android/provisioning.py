"""Free Remnawave provisioning for Android-API users.

When an Android user verifies their email we eagerly hand them a FREE
subscription on Remnawave, mirroring the bot's onboarding. This module
contains only the Remnawave side-effects + DB persistence of `vless_uuid`;
caller chooses *when* to invoke it.
"""
from __future__ import annotations

import logging
import re

from remnawave_client import (
    RemnawaveClient,
    SubscriptionScenario,
    SubscriptionType,
    apply_new_user,
    apply_update,
    configure,
    resolve_scenario,
)

from ..config import (
    get_free_days,
    get_free_traffic,
    get_remnawave_token,
    get_remnawave_url,
    get_rw_free_id,
)
from . import repo

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


async def ensure_free_subscription(user_id: int, email: str) -> str | None:
    """Create or refresh a FREE Remnawave subscription for `user_id`.

    Returns the user's vless_uuid (newly created or pre-existing) or None on
    Remnawave failure. Saves vless_uuid to `users.vless_uuid` so subsequent
    calls can short-circuit without another Remnawave round-trip.
    """
    free_squad = get_rw_free_id() or None
    days = get_free_days()
    limit_gb = get_free_traffic()
    username = email_to_username(email)
    client = _rw_client()

    existing_uuid = await repo.get_user_vless_uuid(user_id)
    user_info = None
    if existing_uuid:
        user_info = await client.get_user_by_username(username)

    scenario = resolve_scenario(user_info, SubscriptionType.FREE)

    if scenario == SubscriptionScenario.ALREADY_ACTIVE:
        return existing_uuid

    if scenario == SubscriptionScenario.NEW_USER:
        created = await apply_new_user(
            username=username,
            telegram_id=0,
            days=days,
            limit_gb=limit_gb,
            email=email,
            description="Android free signup",
            squad_id=free_squad,
            client=client,
        )
        if not created or not created.get("uuid"):
            logger.error("Remnawave create_user failed for %s", username)
            return None
        await repo.set_user_vless_uuid(user_id, created["uuid"])
        return created["uuid"]

    # UPDATE / LIMITED / EXTEND-on-FREE: refresh the existing record.
    if not existing_uuid or not user_info:
        logger.error(
            "ensure_free_subscription: scenario=%s but no uuid for user_id=%s",
            scenario, user_id,
        )
        return None
    await apply_update(
        user_uuid=existing_uuid,
        username=username,
        days=days,
        limit_gb=limit_gb,
        squad_id=free_squad,
        status="active",
        description="Android free refresh",
        client=client,
    )
    return existing_uuid


async def rename_remnawave_email(user_id: int, new_email: str) -> None:
    """Update Remnawave's `email` field after the user changes their address.

    Username stays constant (see module docstring). Failures are logged but
    not raised — the email column in our DB is the source of truth.
    """
    vless_uuid = await repo.get_user_vless_uuid(user_id)
    if not vless_uuid:
        return
    try:
        await _rw_client().update_user(
            user_uuid=vless_uuid,
            email=new_email.strip().lower(),
        )
    except Exception as exc:
        logger.warning("Remnawave email rename for %s failed: %s", vless_uuid, exc)
