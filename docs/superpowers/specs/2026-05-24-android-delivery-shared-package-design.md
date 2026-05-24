# Android delivery shared package — design

**Date:** 2026-05-24
**Scope:** new `packages/android_delivery/` shared package; migrations in `app/handlers/android_delivery.py`, `app/handlers/subscription_service.py`, `app/database/requests.py`, `app/database/tariff_repository.py`, `miniapp/backend/android/provisioning.py`, `miniapp/backend/android/iap_router.py`; boot wiring in `app/__main__.py` and `miniapp/backend/main.py`; new tests under `packages/android_delivery/tests/`.

## Problem

`app/` (bot container) and `miniapp/` (HTTP API container) are deployed as **separate Docker images**. The two are wired through the shared DB and the shared `packages/remnawave_client` + `packages/common_db`, but neither container ships the other's source tree.

Android subscription delivery currently lives in `app/handlers/android_delivery.py`. Both containers need to invoke it:

- **app/** (paid bot flow) — already wired correctly via direct import.
- **miniapp/** (Google Play IAP webhook → delivery) — does a hard `from app.handlers.android_delivery import deliver_android_paid` lazy import inside `iap_router.py:149`. In production this raises `ModuleNotFoundError: No module named 'app'` because the `app/` package is not installed in the miniapp image — IAP delivery silently fails.

The same problem hit `link_router.py` last week; it was fixed by copying the merge module into miniapp/ and rewriting imports. That solution doesn't scale — Android delivery references DB, notify_log, tariff cache, and Remnawave operations, and we don't want to maintain two parallel copies.

We solve this by **extracting all Android delivery logic into a shared package** `packages/android_delivery`, which both containers install via `pip install -e`. This mirrors the existing `packages/common_db` + `packages/remnawave_client` pattern.

## Design overview

The shared package owns: PAID delivery (`deliver_android_paid`), FREE provisioning (`ensure_free_subscription`, `rename_remnawave_email`), and the helpers they need (tariff cache, persistence, notify formatting, username derivation).

Three dependencies are injected at container boot, all via module-level setters (self-configuring style):

- **Remnawave client** — NOT registered separately. The package calls `remnawave_client.get_default_client()` directly; both containers already call `remnawave_client.configure(...)` at startup, and `configure()` is singleton-keyed by `(base_url, token)` so the HTTP pool is naturally reused.
- **DB session factory** — `android_delivery.set_session_factory(async_session)` once per container at boot. Each container's `async_session` comes from its own `make_async_session(...)` call.
- **Notify function** — `android_delivery.set_notify(notify_log)` once per container at boot. Container picks whether to use `app.notify_log.notify_log` or `miniapp.backend.notify_log.notify_log`.

Calling delivery without configuring raises `RuntimeError` — fail-fast at first call.

## Package structure

```
packages/android_delivery/
├── pyproject.toml
├── android_delivery/
│   ├── __init__.py        # public API exports
│   ├── config.py          # set_notify, set_session_factory, _require_*
│   ├── username.py        # email_to_username
│   ├── tariffs.py         # _tariff_cache, get_squad_for_tariff_slug
│   ├── persistence.py     # update_delivery_status, save_vless_uuid
│   ├── notify.py          # notify_android_delivery, _esc
│   ├── free.py            # ensure_free_subscription, rename_remnawave_email
│   └── paid.py            # deliver_android_paid, _parse_squad_slug,
│                          #   _days_left_from_info
└── tests/
    ├── conftest.py
    ├── test_paid.py
    ├── test_free.py
    ├── test_tariffs.py
    └── test_config.py
```

### Public API (`android_delivery/__init__.py`)

```python
from .config import set_notify, set_session_factory
from .paid import deliver_android_paid
from .free import ensure_free_subscription, rename_remnawave_email
from .username import email_to_username

__all__ = [
    "set_notify",
    "set_session_factory",
    "deliver_android_paid",
    "ensure_free_subscription",
    "rename_remnawave_email",
    "email_to_username",
]
```

## Component details

### `config.py`

```python
from typing import Callable, Awaitable
from sqlalchemy.ext.asyncio import async_sessionmaker

NotifyFn = Callable[[str], Awaitable[None]]

_notify: NotifyFn | None = None
_session_factory: async_sessionmaker | None = None


def set_notify(fn: NotifyFn) -> None:
    global _notify
    _notify = fn


def set_session_factory(factory: async_sessionmaker) -> None:
    global _session_factory
    _session_factory = factory


def _require_notify() -> NotifyFn:
    if _notify is None:
        raise RuntimeError(
            "android_delivery: notify not configured. "
            "Call set_notify(fn) at startup."
        )
    return _notify


def _require_session_factory() -> async_sessionmaker:
    if _session_factory is None:
        raise RuntimeError(
            "android_delivery: session_factory not configured. "
            "Call set_session_factory(async_session) at startup."
        )
    return _session_factory
```

### `username.py`

Direct port of the `_email_to_username` helper duplicated in both containers today:

```python
import re

_USERNAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def email_to_username(email: str) -> str:
    """`lynx@example.com` -> `lynx_at_example_com`."""
    local, _, domain = email.strip().lower().partition("@")
    raw = f"{local}_at_{domain}" if domain else local
    sanitized = _USERNAME_RE.sub("_", raw).strip("_")
    return sanitized or "user"
```

### `tariffs.py`

Port of `app/database/tariff_repository.py:153` (`get_squad_for_tariff_slug`) + its supporting cache. The bot's `app/database/tariff_repository.py` keeps its menu helpers (UI-only) but loses `get_squad_for_tariff_slug` (becomes a re-export). The cache is process-local on purpose — each container has its own copy and polls `cache_version` independently every 5 seconds.

```python
import logging
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from common_db.models import TariffPlan, CacheVersion
from .config import _require_session_factory

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5
_tariff_cache: dict = {}
_known_version: int = -1
_last_poll_ts: float = 0


async def _get_db_version() -> int:
    try:
        async with _require_session_factory()() as session:
            row = await session.get(CacheVersion, 1)
            return row.version if row else 0
    except Exception:
        return 0


async def _check_version() -> None:
    global _known_version, _last_poll_ts, _tariff_cache
    now = time.time()
    if (now - _last_poll_ts) < _POLL_INTERVAL:
        return
    _last_poll_ts = now
    db_version = await _get_db_version()
    if db_version != _known_version:
        _tariff_cache.clear()
        _known_version = db_version


async def _ensure_tariff_cache() -> None:
    await _check_version()
    if _tariff_cache:
        return
    try:
        async with _require_session_factory()() as session:
            result = await session.execute(
                select(TariffPlan)
                .options(
                    selectinload(TariffPlan.prices),
                    selectinload(TariffPlan.squad_profile),
                )
                .where(TariffPlan.is_active == True)
                .order_by(TariffPlan.sort_order)
            )
            plans = result.scalars().all()
            _tariff_cache.clear()
            for plan in plans:
                for price in plan.prices:
                    if not price.is_active:
                        continue
                    method = price.payment_method
                    bucket = _tariff_cache.setdefault(method, [])
                    squad = plan.squad_profile
                    bucket.append({
                        "slug": plan.slug,
                        "days": plan.days,
                        "squad_id": squad.squad_id if squad else None,
                        "external_squad_id": squad.external_squad_id if squad else None,
                    })
    except Exception as e:
        logger.error("Failed to load tariffs from DB: %s", e)


async def get_squad_for_tariff_slug(tariff_slug: str) -> Optional[dict]:
    await _ensure_tariff_cache()
    for method_tariffs in _tariff_cache.values():
        for t in method_tariffs:
            if t["slug"] == tariff_slug:
                sid = t.get("squad_id")
                esid = t.get("external_squad_id")
                if sid and esid:
                    return {"squad_id": sid, "external_squad_id": esid}
                return None
    return None
```

### `persistence.py`

```python
import logging

from sqlalchemy import update, text

from common_db.models import Transaction
from .config import _require_session_factory

logger = logging.getLogger(__name__)


async def update_delivery_status(transaction_id: str, new_status: int) -> bool:
    """Flip transactions.delivery_status by transaction_id. Returns True
    on update, False if no row matched."""
    async with _require_session_factory()() as s:
        result = await s.execute(
            update(Transaction)
            .where(Transaction.transaction_id == transaction_id)
            .values(delivery_status=new_status)
        )
        await s.commit()
        return result.rowcount > 0


async def save_vless_uuid(user_id: int, vless_uuid: str) -> None:
    async with _require_session_factory()() as s:
        await s.execute(
            text("UPDATE users SET vless_uuid = :u WHERE id = :i"),
            {"u": vless_uuid, "i": user_id},
        )
        await s.commit()
```

### `notify.py`

```python
import html
from typing import Optional

from .config import _require_notify


def _esc(value: object) -> str:
    """Standalone copy of app.notify_log.esc / miniapp.backend.notify_log.esc.
    Both implementations are identical (`html.escape(str(v), quote=False)`)
    — duplicating one line is cheaper than another shared dependency."""
    return html.escape(str(value), quote=False)


async def notify_android_delivery(
    *,
    ok: bool,
    transaction_id: str,
    android_user_id: int,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
    reason: Optional[str] = None,
) -> None:
    icon = "📦" if ok else "❌"
    title = "Android subscription delivered" if ok else "Android delivery FAILED"
    extra = f"\nerror: <code>{_esc(reason[:300])}</code>" if (not ok and reason) else ""
    await _require_notify()(
        f"{icon} <b>{title}</b>\n"
        f"user: <code>{android_user_id}</code> {_esc(email or '—')}\n"
        f"days: <code>{days}</code>\n"
        f"slug: <code>{_esc(tariff_slug or '—')}</code>\n"
        f"tx: <code>{_esc(transaction_id)}</code>"
        f"{extra}"
    )
```

### `paid.py`

Direct port of `app/handlers/android_delivery.py:80-214`. Same signature, same return shape, same side-effects ordering. Differences from the original:

- Uses `remnawave_client.get_default_client()` instead of `app.api.remnawave.api.get_user_from_username`.
- Uses `get_squad_for_tariff_slug` from `.tariffs` instead of `app.database.tariff_repository`.
- Uses `update_delivery_status` / `save_vless_uuid` from `.persistence` instead of `app.database.requests`.
- Uses `_days_left_from_info` — an inlined sync copy of `app.handlers.tools.get_user_days` — preserving the `expire is None → 999999` semantics and `round()` rounding.
- Uses `notify_android_delivery` from `.notify` instead of `_notify_android_delivery`.

```python
import logging
import time
from typing import Optional

from remnawave_client import (
    SubscriptionScenario,
    SubscriptionType,
    apply_extend,
    apply_new_user,
    apply_update,
    get_default_client,
    resolve_scenario,
)

from .notify import notify_android_delivery
from .persistence import save_vless_uuid, update_delivery_status
from .tariffs import get_squad_for_tariff_slug
from .username import email_to_username

logger = logging.getLogger(__name__)


def _parse_squad_slug(slug: Optional[str]) -> Optional[dict]:
    """Parse 'sid:<squad_id>:esid:<external_squad_id>' (legacy format
    written by the Android invoice router into transactions.tariff_slug)."""
    if not slug or not slug.startswith("sid:"):
        return None
    try:
        _, sid, marker, esid = slug.split(":", 3)
    except ValueError:
        return None
    if marker != "esid" or not sid or not esid:
        return None
    return {"squad_id": sid, "external_squad_id": esid}


def _days_left_from_info(info: dict) -> int:
    """Inlined copy of app.handlers.tools.get_user_days. Sync — the
    original is async but never awaits. Returns 999999 for None expire
    (infinite), round()ed days otherwise, never negative."""
    expire = (info or {}).get("expire")
    if expire is None:
        return 999999
    try:
        days_left = round((expire - time.time()) / 86400)
        return max(0, days_left)
    except (TypeError, ValueError):
        logger.error("Bad expire value: %r", expire)
        return 0


async def deliver_android_paid(
    *,
    transaction_id: str,
    android_user_id: int,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
) -> dict:
    """Provision/extend a PAID Remnawave subscription for an Android user.

    Returns:
        {"status": "success", "scenario": ..., "uuid": ..., "subscription_url": ...}
        or {"status": "error", "message": ...} on failure.
    """
    if not email:
        await notify_android_delivery(
            ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email,
            days=days, tariff_slug=tariff_slug,
            reason="android_user_missing_email",
        )
        return {"status": "error", "message": "android_user_missing_email"}

    squad = _parse_squad_slug(tariff_slug)
    if not squad and tariff_slug:
        squad = await get_squad_for_tariff_slug(tariff_slug)
    if not squad:
        await notify_android_delivery(
            ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email,
            days=days, tariff_slug=tariff_slug,
            reason=f"bad tariff_slug: {tariff_slug!r}",
        )
        return {"status": "error", "message": f"bad tariff_slug: {tariff_slug!r}"}

    username = email_to_username(email)
    rw = get_default_client()
    info = await rw.get_user_by_username(username)
    scenario = resolve_scenario(info, SubscriptionType.PAID)

    try:
        if scenario == SubscriptionScenario.NEW_USER:
            result = await apply_new_user(
                username=username, telegram_id=0, days=days, limit_gb=0,
                email=email, description="Android paid subscription",
                squad_id=squad["squad_id"],
                external_squad_id=squad["external_squad_id"],
            )
        elif scenario == SubscriptionScenario.EXTEND:
            uuid = (info or {}).get("uuid")
            if not uuid:
                await notify_android_delivery(
                    ok=False, transaction_id=transaction_id,
                    android_user_id=android_user_id, email=email,
                    days=days, tariff_slug=tariff_slug,
                    reason="extend without uuid",
                )
                return {"status": "error", "message": "extend without uuid"}
            current_days = _days_left_from_info(info)
            result = await apply_extend(
                user_uuid=uuid, username=username, days=days,
                current_days_left=current_days,
                squad_id=squad["squad_id"],
                external_squad_id=squad["external_squad_id"],
                description="Android paid extend",
            )
        else:
            uuid = (info or {}).get("uuid")
            if not uuid:
                await notify_android_delivery(
                    ok=False, transaction_id=transaction_id,
                    android_user_id=android_user_id, email=email,
                    days=days, tariff_slug=tariff_slug,
                    reason=f"{scenario.value} without uuid",
                )
                return {"status": "error", "message": f"{scenario.value} without uuid"}
            result = await apply_update(
                user_uuid=uuid, username=username, days=days, limit_gb=0,
                squad_id=squad["squad_id"],
                external_squad_id=squad["external_squad_id"],
                status="active",
                description="Android paid update",
            )
    except Exception as exc:
        logger.error("android delivery for tx=%s failed: %s", transaction_id, exc)
        await notify_android_delivery(
            ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email,
            days=days, tariff_slug=tariff_slug, reason=str(exc),
        )
        return {"status": "error", "message": str(exc)}

    if not result:
        await notify_android_delivery(
            ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email,
            days=days, tariff_slug=tariff_slug,
            reason="remnawave_apply_returned_none",
        )
        return {"status": "error", "message": "remnawave_apply_returned_none"}

    rw_uuid = result.get("uuid") or (info or {}).get("uuid")
    if rw_uuid:
        try:
            await save_vless_uuid(android_user_id, rw_uuid)
        except Exception as exc:
            logger.warning("Failed to save vless_uuid for user %s: %s",
                           android_user_id, exc)

    await update_delivery_status(transaction_id, 1)
    await notify_android_delivery(
        ok=True, transaction_id=transaction_id,
        android_user_id=android_user_id, email=email,
        days=days, tariff_slug=tariff_slug,
    )
    return {
        "status": "success",
        "scenario": scenario.value,
        "uuid": rw_uuid,
        "subscription_url": result.get("subscription_url"),
    }
```

### `free.py`

Port of `miniapp/backend/android/provisioning.ensure_free_subscription` + `rename_remnawave_email`. The package can't depend on `miniapp.backend.config`, so policy values (`free_days`, `free_traffic_gb`, `free_squad_id`) become explicit parameters. Each container's existing wrapper passes its own config.

```python
import logging
from typing import Optional

from sqlalchemy import select
from remnawave_client import (
    SubscriptionScenario,
    SubscriptionType,
    apply_new_user,
    apply_update,
    get_default_client,
    resolve_scenario,
)

from common_db.models import User
from .config import _require_session_factory
from .persistence import save_vless_uuid
from .username import email_to_username

logger = logging.getLogger(__name__)


async def _get_user_vless_uuid(user_id: int) -> Optional[str]:
    async with _require_session_factory()() as s:
        user = await s.get(User, user_id)
        return user.vless_uuid if user else None


async def ensure_free_subscription(
    user_id: int,
    email: str,
    *,
    free_days: int,
    free_traffic_gb: int,
    free_squad_id: Optional[str],
) -> Optional[str]:
    """Create or refresh a FREE Remnawave subscription for `user_id`.

    Policy values are explicit parameters — bot and miniapp may differ.
    Returns vless_uuid (newly created or pre-existing) or None on RW failure.
    """
    username = email_to_username(email)
    client = get_default_client()

    existing_uuid = await _get_user_vless_uuid(user_id)
    user_info = None
    if existing_uuid:
        user_info = await client.get_user_by_username(username)

    scenario = resolve_scenario(user_info, SubscriptionType.FREE)
    if scenario == SubscriptionScenario.ALREADY_ACTIVE:
        return existing_uuid

    if scenario == SubscriptionScenario.NEW_USER:
        created = await apply_new_user(
            username=username, telegram_id=0,
            days=free_days, limit_gb=free_traffic_gb,
            email=email, description="Android free signup",
            squad_id=free_squad_id,
        )
        if not created or not created.get("uuid"):
            logger.error("Remnawave create_user failed for %s", username)
            return None
        await save_vless_uuid(user_id, created["uuid"])
        return created["uuid"]

    if not existing_uuid or not user_info:
        logger.error(
            "ensure_free_subscription: scenario=%s but no uuid for user_id=%s",
            scenario, user_id,
        )
        return None
    await apply_update(
        user_uuid=existing_uuid, username=username,
        days=free_days, limit_gb=free_traffic_gb,
        squad_id=free_squad_id, status="active",
        description="Android free refresh",
    )
    return existing_uuid


async def rename_remnawave_email(user_id: int, new_email: str) -> None:
    """Update Remnawave's email field after the user changes theirs.
    Best-effort; failures are logged, not raised — the DB column is the
    source of truth."""
    vless_uuid = await _get_user_vless_uuid(user_id)
    if not vless_uuid:
        return
    try:
        await get_default_client().update_user(
            user_uuid=vless_uuid,
            email=new_email.strip().lower(),
        )
    except Exception as exc:
        logger.warning("Remnawave email rename for %s failed: %s",
                       vless_uuid, exc)
```

## Boot wiring

**Critical:** neither container calls `remnawave_client.configure(...)` at startup today — both use lazy `_client()` / `_rw_client()` factories that call `configure(...)` on every request. Because `RemnawaveClient.get(base_url, token)` is interned, this is essentially free. After this refactor, `paid.py` and `free.py` call `get_default_client()` directly, which raises `RuntimeError` until `configure()` has been called at least once. **Boot wiring must do an explicit eager `rw_configure(...)` first.**

### Bot entrypoint — `main.py` (repo root), inside `if __name__ == "__main__":` block

```python
# main.py — extend the existing `if __name__ == "__main__":` block
if __name__ == "__main__":
    logging.basicConfig(...)
    from app.log_buffer import init_error_log_handler
    from app.settings import secrets
    init_error_log_handler(maxlen=secrets.get('admin_logs_length', 20))

    # --- new wiring ---
    from remnawave_client import configure as rw_configure
    from android_delivery import set_notify, set_session_factory
    from app.database.models import async_session
    from app.notify_log import notify_log

    rw_configure(
        base_url=secrets.get("remnawave_url"),
        token=secrets.get("remnawave_token"),
        free_squad_id=secrets.get("rw_free_id"),
    )
    set_session_factory(async_session)
    set_notify(notify_log)
    # --- /new wiring ---

    asyncio.run(main())
```

### Miniapp entrypoint — `miniapp/backend/main.py`, module top-level (FastAPI app builds at import time)

```python
# miniapp/backend/main.py — after logging.basicConfig(...), BEFORE the
# `from .android import ...` router imports.
from remnawave_client import configure as rw_configure
from android_delivery import set_notify, set_session_factory
from .config import get_remnawave_url, get_remnawave_token, get_rw_free_id
from .database.session import async_session
from .notify_log import notify_log

rw_configure(
    base_url=get_remnawave_url(),
    token=get_remnawave_token(),
    free_squad_id=get_rw_free_id(),
)
set_session_factory(async_session)
set_notify(notify_log)
```

Setters must run **before** router imports / handler registration — the routers import modules that may call `_require_session_factory()` at request time, and the first request after deploy must not hit an unconfigured package.

## Call-site migration

| File | Change |
|---|---|
| `app/handlers/android_delivery.py` | Reduce to `from android_delivery import deliver_android_paid` (one-line re-export). Old body removed. |
| `app/api/handlers.py:185` | Replace lazy `from app.handlers.android_delivery import deliver_android_paid` with `from android_delivery import deliver_android_paid` (still lazy or hoisted — caller's choice). |
| `app/database/requests.py:406` | Replace function body with `from android_delivery.persistence import update_delivery_status` re-export so existing bot callers (`subscription_service.py:249`) keep working without changes. |
| `app/database/tariff_repository.py:153` | Replace function body with re-export from `android_delivery.tariffs.get_squad_for_tariff_slug`. Existing lazy callers in `subscription_service.py:147` keep working. The menu cache and UI helpers stay in this file. |
| `miniapp/backend/android/iap_router.py:149` | Replace lazy `from app.handlers.android_delivery import deliver_android_paid` with module-level `from android_delivery import deliver_android_paid`. **This fixes the production `ModuleNotFoundError`.** |
| `miniapp/backend/android/provisioning.py` | Replace body with thin wrapper that pulls policy from `miniapp.backend.config` and calls `android_delivery.ensure_free_subscription(...)`. Same for `rename_remnawave_email`. |
| `main.py` (repo root) | Add `rw_configure(...)` + `set_session_factory(async_session)` + `set_notify(notify_log)` inside the existing `if __name__ == "__main__":` block. See Boot wiring. |
| `miniapp/backend/main.py` | Add the same three calls at module top-level, BEFORE the `from .android import ...` router imports. |
| `Dockerfile` | Add `RUN pip install -e packages/android_delivery` next to the existing `packages/common_db` + `packages/remnawave_client` installs. |
| `miniapp/Dockerfile` | Same. |

### Wrapper example — `miniapp/backend/android/provisioning.py` after migration

```python
"""Thin wrappers over android_delivery for FREE provisioning.

Kept in place so call sites in email_router.py don't need to know about
miniapp-local config (free_days / free_traffic / free_squad_id)."""
from android_delivery import (
    ensure_free_subscription as _ensure,
    rename_remnawave_email as _rename,
)
from ..config import get_free_days, get_free_traffic, get_rw_free_id


async def ensure_free_subscription(user_id: int, email: str) -> str | None:
    return await _ensure(
        user_id, email,
        free_days=get_free_days(),
        free_traffic_gb=get_free_traffic(),
        free_squad_id=get_rw_free_id() or None,
    )


async def rename_remnawave_email(user_id: int, new_email: str) -> None:
    await _rename(user_id, new_email)
```

## Testing

### `packages/android_delivery/tests/conftest.py`

Provides:
- `with_app_db` fixture — `async_sessionmaker` bound to in-memory aiosqlite with `common_db.models` `Base.metadata.create_all(...)`.
- `fake_remnawave` fixture — monkeypatches `remnawave_client.get_default_client()` to return a fake client that records calls and lets tests stage `get_user_by_username`/`apply_*` responses.
- `notify_calls` fixture — registers a list-appending `set_notify(...)` and yields the list.
- `configured` fixture (autouse) — wires both `set_session_factory` and `set_notify`.

### `test_paid.py` (≈8 cases)

1. **NEW_USER** — RW returns None for the username → `apply_new_user` called with the squad/days → `delivery_status=1` set, vless_uuid saved, ok notify.
2. **EXTEND** — RW returns active subscription with expire in future → `apply_extend` called with computed `current_days_left` (covers the `_days_left_from_info` math).
3. **UPDATE-fallback (LIMITED/UPDATE branch)** — `apply_update` called with squad/days.
4. **Missing email** — early-return error, no RW calls, FAILED notify with `android_user_missing_email`.
5. **Bad tariff_slug** — no `sid:` prefix and not in tariff cache → early-return error.
6. **Legacy `sid:..:esid:..` slug** — `_parse_squad_slug` parses correctly, no DB tariff lookup needed.
7. **Apply raises** — try-block catches, FAILED notify with exception message, no `delivery_status` update.
8. **Apply returns None** — error path, no `delivery_status` update.
9. **`_days_left_from_info` semantics** — table-driven test: `None → 999999`, future timestamp → positive days, past timestamp → 0, garbage → 0.

### `test_free.py` (≈5 cases)

1. **ALREADY_ACTIVE** — existing uuid, RW reports active → returns same uuid, no apply calls.
2. **NEW_USER** — no uuid → `apply_new_user`, `save_vless_uuid` called.
3. **UPDATE branch** — uuid exists but scenario is LIMITED/EXTEND-on-FREE → `apply_update`.
4. **`apply_new_user` returns None** — function returns None, no DB write.
5. **`rename_remnawave_email`** — calls `update_user(email=...)` with lowercased trimmed value; failure logged, doesn't raise.

### `test_tariffs.py` (≈3 cases)

1. **Cache miss → fetch** — empty cache, `_ensure_tariff_cache` reads `TariffPlan` rows and populates per-method buckets.
2. **Version bump invalidates** — set `_known_version=0`, bump `CacheVersion.version` in DB, wait past 5s poll window (or monkeypatch `_last_poll_ts`) → next call sees fresh data.
3. **`get_squad_for_tariff_slug` miss** — unknown slug returns None; slug present but `squad_id` None returns None.

### `test_config.py` (≈2 cases)

1. **`deliver_android_paid` without `set_session_factory`** → `RuntimeError("session_factory not configured")`.
2. **`deliver_android_paid` without `set_notify`** → `RuntimeError("notify not configured")`.

### Existing tests to migrate

`tests/test_android_delivery.py` (if it exists at the top level — verify during plan) — most cases collapse into `packages/android_delivery/tests/test_paid.py`. The bot-side smoke test (does `app.handlers.android_delivery` still expose `deliver_android_paid`?) stays in `tests/` as a tiny import check.

### Verification

```bash
python -m pytest packages/android_delivery/tests/ -v
python -m pytest packages/common_db/tests/ packages/remnawave_client/tests/ -v
python -m pytest tests/ -v          # full bot suite — must stay green
```

The cross-directory collision documented in the android-link spec applies here too: run `tests/` and `packages/*/tests/` separately, not jointly.

## `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "android_delivery"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "remnawave_client",
    "common_db",
    "sqlalchemy[asyncio]>=2.0",
]

[tool.setuptools.packages.find]
include = ["android_delivery*"]
```

Both Dockerfiles already copy `packages/` and install the shared packages as editable; we add `packages/android_delivery` to those lines.

## Files touched

| Path | Change |
|---|---|
| `packages/android_delivery/pyproject.toml` | **new** |
| `packages/android_delivery/android_delivery/__init__.py` | **new** — public API |
| `packages/android_delivery/android_delivery/config.py` | **new** — setters + `_require_*` |
| `packages/android_delivery/android_delivery/username.py` | **new** — `email_to_username` |
| `packages/android_delivery/android_delivery/tariffs.py` | **new** — cache + `get_squad_for_tariff_slug` |
| `packages/android_delivery/android_delivery/persistence.py` | **new** — `update_delivery_status`, `save_vless_uuid` |
| `packages/android_delivery/android_delivery/notify.py` | **new** — `notify_android_delivery`, `_esc` |
| `packages/android_delivery/android_delivery/paid.py` | **new** — `deliver_android_paid` + helpers |
| `packages/android_delivery/android_delivery/free.py` | **new** — `ensure_free_subscription`, `rename_remnawave_email` |
| `packages/android_delivery/tests/conftest.py` | **new** |
| `packages/android_delivery/tests/test_paid.py` | **new** |
| `packages/android_delivery/tests/test_free.py` | **new** |
| `packages/android_delivery/tests/test_tariffs.py` | **new** |
| `packages/android_delivery/tests/test_config.py` | **new** |
| `app/handlers/android_delivery.py` | shrink to one-line re-export |
| `app/handlers/subscription_service.py` | switch import path |
| `app/database/requests.py` | `update_delivery_status` becomes a re-export |
| `app/database/tariff_repository.py` | `get_squad_for_tariff_slug` becomes a re-export |
| `miniapp/backend/android/iap_router.py` | switch import path; **fixes ModuleNotFoundError** |
| `miniapp/backend/android/provisioning.py` | thin wrappers over `android_delivery` |
| `app/__main__.py` (or current configure call site) | add two setter calls |
| `miniapp/backend/main.py` | add two setter calls |
| `Dockerfile` | install `packages/android_delivery` |
| `miniapp/Dockerfile` | install `packages/android_delivery` |

## Out of scope

- Unifying `notify_log` itself across containers — `app/notify_log.py` and `miniapp/backend/notify_log.py` keep independent chat IDs / formatters. Only the formatted text for delivery messages moves.
- Refactoring `app.api.remnawave.api` — it remains a legacy shim. New code goes through `remnawave_client` directly; this spec doesn't add new callers to the shim.
- Menu cache (`_menu_cache`, `get_screen_buttons`, `get_tariffs_for_method`, `get_tariff_slug_by_days`) — bot-only UI helpers, stay in `app/database/tariff_repository.py`.
- Reversing a delivery / undo / refund flow.
- Extracting `subscription_service.deliver_subscription` (Telegram-side bot flow) — separate concern; it touches `bot.send_message` and localization which are bot-only.

## Risks (non-blocking)

1. **Boot-order races.** A handler that fires before setters are wired raises `RuntimeError`. Both containers currently rely on lazy `_client()` factories that internally call `configure(...)` on every request, so the eager `rw_configure(...)` at boot is a new contract. Mitigation: do all three setup calls (`rw_configure`, `set_session_factory`, `set_notify`) at the very top of the app entrypoint, before any router/handler registration or `asyncio.run(main())`. Verified locations in the repo today: `main.py` line 121 (`asyncio.run(main())`) — wiring goes right above this. `miniapp/backend/main.py` — wiring goes right after `logging.basicConfig(...)` (lines 11-14 in current head), before the `from .android import auth_router as android_auth_router` block.
2. **Two tariff caches per process** (in app/: `app.database.tariff_repository._tariff_cache` + `android_delivery.tariffs._tariff_cache`). They're independent, each polls `cache_version` every 5s. Memory cost: a few KB. Could be unified later by making `app.database.tariff_repository.get_squad_for_tariff_slug` literally call into the shared cache (the re-export already does this) — the duplicated cache is the `app` menu cache, which is a different beast.
3. **Drift of `_days_left_from_info` from `app.handlers.tools.get_user_days`.** Test pinning the semantics covers this; if `get_user_days` ever changes, the test fails and forces a sync.
4. **`apply_*` returning unexpected shapes** — already handled by the original code (`result.get("uuid")`, `result.get("subscription_url")`). No change to robustness.
