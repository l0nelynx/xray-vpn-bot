"""Module-level functional facade over the configured default RemnawaveClient.

This is the single source for the thin module-level wrappers that the seller
bot (`app.api.remnawave.api`) and the miniapp (`miniapp.backend.remnawave_client`)
used to each re-implement on top of `RemnawaveClient`. Both now import from here.

Configuration: a host service either calls `configure(...)` at startup, or
registers a lazy provider via `set_config_provider()` so the first call wires
the default client on demand — mirroring the old per-service `_client()` that
read `app.settings` / miniapp config lazily.

Where app/ and miniapp historically diverged:
- HWID device listing: app consumed the raw SDK DTO, miniapp wanted a list of
  plain dicts. Both shapes are exposed: `get_user_hwid_devices` (raw DTO) and
  `list_user_hwid_devices` (normalized list[dict]).
- create_user email default: the underlying client already fills
  `<username>@bot.local` when email is None; the miniapp-specific
  `<username>@miniapp.xyz` is now passed explicitly by its single caller.
"""

import logging
from typing import Callable, Optional

from remnawave.models import (
    DeleteUserHwidDeviceResponseDto,
    GetUserHwidDevicesResponseDto,
    UsersResponseDto,
)

from .client import RemnawaveClient, configure, get_default_client

logger = logging.getLogger(__name__)

_provider: Optional[Callable[[], dict]] = None


def set_config_provider(provider: Callable[[], dict]) -> None:
    """Register a callable returning ``{base_url, token, free_squad_id}``.

    Used to lazily configure the default client on first use, preserving the
    old behaviour where each service configured from its own settings source
    without an explicit startup call.
    """
    global _provider
    _provider = provider


def _client() -> RemnawaveClient:
    try:
        return get_default_client()
    except RuntimeError:
        if _provider is None:
            raise
        return configure(**_provider())


# ---------------------------------------------------------------------------
# User lookups
# ---------------------------------------------------------------------------
async def get_all_users() -> UsersResponseDto:
    return await _client().get_all_users()


async def get_user_from_username(username: str) -> dict | None:
    return await _client().get_user_by_username(username)


async def get_user_from_email(email: str) -> dict | None:
    return await _client().get_user_by_email(email)


async def get_user_from_uuid(user_uuid: str) -> dict | None:
    return await _client().get_user_by_uuid(user_uuid)


async def get_user_by_short_uuid_raw(short_uuid: str) -> dict | None:
    """Return the raw Remnawave SDK DTO for the user owning ``short_uuid``.

    Preserves every field the SDK exposes — the Android subscription-URL import
    flow and account-recovery flows rely on the full payload.
    """
    return await _client().get_user_by_short_uuid_raw(short_uuid)


async def resolve_remnawave_user(
    *,
    vless_uuid: str | None = None,
    email: str | None = None,
    username: str | None = None,
) -> dict | None:
    """Look up a Remnawave user via the strongest identifier available,
    falling back to weaker ones.

    Priority: vless_uuid → email → username. The cached ``vless_uuid`` in our
    local ``users`` row is authoritative — Remnawave can't rename a user's UUID
    — so try it first. Only fall back when it's missing or the upstream record
    was deleted/recreated out of band. Returns the normalized user dict, or
    None when every identifier we were given missed.
    """
    if vless_uuid:
        user = await get_user_from_uuid(vless_uuid)
        if user:
            return user
    if email:
        user = await get_user_from_email(email)
        if user:
            return user
    if username:
        user = await get_user_from_username(username)
        if user:
            return user
    return None


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
async def create_user(
    username: str,
    days: int = 30,
    limit_gb: int = 0,
    descr: str = "created by backend",
    email: str | None = None,
    telegram_id: int | None = None,
    tag: str | None = None,
    squad_id: str | None = None,
    external_squad_id: str | None = None,
) -> dict | None:
    return await _client().create_user(
        username=username,
        days=days,
        limit_gb=limit_gb,
        descr=descr,
        email=email,
        telegram_id=telegram_id,
        tag=tag,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
    )


async def update_user(
    user_uuid: str,
    username: str | None = None,
    days: int | None = None,
    limit_gb: int | None = None,
    descr: str | None = None,
    email: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    squad_id: str | None = None,
    external_squad_id: str | None = None,
) -> dict | None:
    return await _client().update_user(
        user_uuid=user_uuid,
        username=username,
        days=days,
        limit_gb=limit_gb,
        descr=descr,
        email=email,
        tag=tag,
        status=status,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
    )


async def reset_user_traffic(user_uuid: str) -> bool:
    return await _client().reset_user_traffic(user_uuid)


async def delete_user(user_uuid: str) -> bool:
    return await _client().delete_user(user_uuid)


async def get_user_subscription_link(user_uuid: str) -> str | None:
    return await _client().get_subscription_link(user_uuid)


# ---------------------------------------------------------------------------
# HWID devices
# ---------------------------------------------------------------------------
def _normalize_device(device) -> dict:
    return {
        "hwid": device.hwid,
        "platform": getattr(device, "platform", None),
        "os_version": getattr(device, "os_version", None),
        "device_model": getattr(device, "device_model", None),
        "user_agent": getattr(device, "user_agent", None),
        "created_at": (
            device.created_at.isoformat()
            if getattr(device, "created_at", None) else None
        ),
        "updated_at": (
            device.updated_at.isoformat()
            if getattr(device, "updated_at", None) else None
        ),
    }


async def get_user_hwid_devices(user_uuid: str) -> GetUserHwidDevicesResponseDto | None:
    """Raw SDK DTO (used by the seller bot, which reads ``.devices`` directly)."""
    return await _client().get_user_hwid_devices(user_uuid)


async def list_user_hwid_devices(user_uuid: str) -> list[dict]:
    """Normalized list of device dicts (used by the miniapp API responses)."""
    response = await _client().get_user_hwid_devices(user_uuid)
    if not response or not response.devices:
        return []
    return [_normalize_device(d) for d in response.devices]


async def get_user_devices_count(user_uuid: str) -> int:
    response = await _client().get_user_hwid_devices(user_uuid)
    if not response:
        return 0
    return int(response.total) if response.total else len(response.devices or [])


async def delete_user_hwid_device(
    user_uuid: str, hwid: str
) -> DeleteUserHwidDeviceResponseDto | None:
    return await _client().delete_user_hwid_device(user_uuid, hwid)
