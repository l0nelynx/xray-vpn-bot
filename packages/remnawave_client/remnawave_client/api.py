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

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Hashable, Optional

from remnawave.models import UsersResponseDto

from .client import HwidDevicesCompat, RemnawaveClient, configure, get_default_client

logger = logging.getLogger(__name__)

_provider: Optional[Callable[[], dict]] = None


class _TTLCache:
    """Minimal in-process TTL cache for coalescing repeated Remnawave lookups
    within a short window — e.g. an Android client re-fetching /me on every
    foreground-resume, or a web session refreshing the dashboard tab.

    Not shared across processes; each single-worker container gets its own
    cache, which matches the current in-process-state architecture (see the
    single-worker note in docs/deployment.md). Values (including a genuine
    "not found") are cached — a short staleness window on subscription/device
    display is harmless, and it also avoids re-hammering Remnawave for a user
    it just told us doesn't exist.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._inflight: dict[Hashable, asyncio.Future] = {}

    def get(self, key: Hashable) -> tuple[bool, Any]:
        entry = self._store.get(key)
        if entry is None:
            return False, None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del self._store[key]
            return False, None
        return True, value

    def set(self, key: Hashable, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)

    async def get_or_compute(
        self, key: Hashable, compute: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Cache lookup with single-flight de-duplication.

        Under load-test observation (loadtest/README.md), many concurrent
        callers for the *same* key would all miss the cache in the same
        instant right when the TTL expired, and each independently re-hit
        Remnawave — a "cache stampede". Here, only the first caller to miss
        actually runs `compute()`; concurrent callers for the same key await
        that same in-flight call instead of duplicating it.

        The check-then-register step below contains no `await`, so it is
        atomic with respect to other coroutines on this event loop — two
        callers can't both become "the leader" for the same key.
        """
        hit, cached = self.get(key)
        if hit:
            return cached

        future = self._inflight.get(key)
        if future is not None:
            return await future

        future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            result = await compute()
            self.set(key, result)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            if self._inflight.get(key) is future:
                del self._inflight[key]


# Short enough that support/troubleshooting still feels "live", long enough to
# absorb bursty repeat reads (app foreground-resume, tab refresh) without a
# live round-trip to Remnawave on every single one.
_REMNAWAVE_USER_CACHE_TTL = 15.0
_DEVICES_COUNT_CACHE_TTL = 15.0

_user_cache = _TTLCache(_REMNAWAVE_USER_CACHE_TTL)
_devices_count_cache = _TTLCache(_DEVICES_COUNT_CACHE_TTL)


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
    expected_telegram_id: int | None = None,
) -> dict | None:
    """Look up a Remnawave user via the strongest identifier available,
    falling back to weaker ones.

    Priority: vless_uuid → email → username. The cached ``vless_uuid`` in our
    local ``users`` row is authoritative — Remnawave can't rename a user's UUID
    — so try it first. Only fall back when it's missing or the upstream record
    was deleted/recreated out of band. Returns the normalized user dict, or
    None when every identifier we were given missed.

    ``username`` is the weakest match: a Telegram @username can coincide with a
    *different* person's panel account, which would leak their subscription URL.
    When ``expected_telegram_id`` is given, a username match is only trusted if
    the panel account is owned by that Telegram id (its ``telegram_id`` matches).
    Accounts found by ``vless_uuid``/``email`` come from our own cached row and
    are not re-checked; accounts whose panel ``telegram_id`` is unset are treated
    as unverifiable and rejected on the username path.

    Result is cached for _REMNAWAVE_USER_CACHE_TTL seconds (per identifier
    combination), with single-flight de-duplication — this is the single
    hottest Remnawave lookup (every Android/web /me and /devices call goes
    through it), so coalescing repeat/concurrent reads within a short window
    meaningfully cuts load on the panel.
    """
    cache_key = (vless_uuid, email, username, expected_telegram_id)
    return await _user_cache.get_or_compute(
        cache_key,
        lambda: _resolve_remnawave_user_uncached(
            vless_uuid=vless_uuid,
            email=email,
            username=username,
            expected_telegram_id=expected_telegram_id,
        ),
    )


async def _resolve_remnawave_user_uncached(
    *,
    vless_uuid: str | None,
    email: str | None,
    username: str | None,
    expected_telegram_id: int | None,
) -> dict | None:
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
            if expected_telegram_id is not None:
                owner = user.get("telegram_id")
                try:
                    if owner is None or int(owner) != int(expected_telegram_id):
                        return None
                except (TypeError, ValueError):
                    return None
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


async def get_user_hwid_devices(user_uuid: str) -> HwidDevicesCompat | None:
    """Device list DTO (used by the seller bot, which reads ``.devices`` directly)."""
    return await _client().get_user_hwid_devices(user_uuid)


async def list_user_hwid_devices(user_uuid: str) -> list[dict]:
    """Normalized list of device dicts (used by the miniapp API responses)."""
    response = await _client().get_user_hwid_devices(user_uuid)
    if not response or not response.devices:
        return []
    return [_normalize_device(d) for d in response.devices]


async def get_user_devices_count(user_uuid: str) -> int:
    """Cached for _DEVICES_COUNT_CACHE_TTL seconds, with single-flight
    de-duplication — this is display-only data (used in /me summaries),
    never a limit-enforcement check: HWID device add/remove is enforced by
    Remnawave itself, and add/remove endpoints here (list_user_hwid_devices,
    delete_user_hwid_device) bypass this cache entirely, so they always see
    live data."""

    async def _fetch() -> int:
        response = await _client().get_user_hwid_devices(user_uuid)
        if not response:
            return 0
        return int(response.total) if response.total else len(response.devices or [])

    return await _devices_count_cache.get_or_compute(user_uuid, _fetch)


async def delete_user_hwid_device(
    user_uuid: str, hwid: str
) -> HwidDevicesCompat | None:
    return await _client().delete_user_hwid_device(user_uuid, hwid)
