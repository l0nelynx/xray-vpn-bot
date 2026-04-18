"""
Repository for reading tariffs and menu data from DB with version-based cache.
Dashboard bumps cache_version on save; bot checks it before using cache.
"""
import logging
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import async_session, TariffPlan, TariffPrice, MenuScreen, MenuButton, CacheVersion, SquadProfile

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5  # check DB version every 5 seconds (cheap single-row query)

_tariff_cache: dict = {}
_menu_cache: dict = {}
_known_version: int = -1
_last_poll_ts: float = 0


async def _get_db_version() -> int:
    """Read current cache version from DB (single row)."""
    try:
        async with async_session() as session:
            row = await session.get(CacheVersion, 1)
            return row.version if row else 0
    except Exception:
        return 0


async def _check_version():
    """Poll DB version; if changed, clear caches."""
    global _known_version, _last_poll_ts, _tariff_cache, _menu_cache

    now = time.time()
    if (now - _last_poll_ts) < _POLL_INTERVAL:
        return
    _last_poll_ts = now

    db_version = await _get_db_version()
    if db_version != _known_version:
        logger.info("Cache version changed %d -> %d, invalidating", _known_version, db_version)
        _tariff_cache.clear()
        _menu_cache.clear()
        _known_version = db_version


def invalidate_cache():
    global _tariff_cache, _menu_cache, _known_version
    _tariff_cache.clear()
    _menu_cache.clear()
    _known_version = -1
    logger.info("Tariff/menu cache force-invalidated")


async def _ensure_tariff_cache():
    await _check_version()
    if _tariff_cache:
        return
    try:
        async with async_session() as session:
            result = await session.execute(
                select(TariffPlan)
                .options(selectinload(TariffPlan.prices), selectinload(TariffPlan.squad_profile))
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
                    if method not in _tariff_cache:
                        _tariff_cache[method] = []
                    squad = plan.squad_profile
                    _tariff_cache[method].append({
                        "slug": plan.slug,
                        "name_ru": plan.name_ru,
                        "name_en": plan.name_en,
                        "days": plan.days,
                        "discount_percent": plan.discount_percent,
                        "price": price.price,
                        "currency": price.currency,
                        "squad_id": squad.squad_id if squad else None,
                        "external_squad_id": squad.external_squad_id if squad else None,
                    })
            logger.debug("Tariff cache refreshed: %d methods", len(_tariff_cache))
    except Exception as e:
        logger.error("Failed to load tariffs from DB: %s", e)


async def _ensure_menu_cache():
    await _check_version()
    if _menu_cache:
        return
    try:
        async with async_session() as session:
            result = await session.execute(
                select(MenuScreen)
                .options(selectinload(MenuScreen.buttons))
                .where(MenuScreen.is_active == True)
            )
            screens = result.scalars().all()
            _menu_cache.clear()
            for screen in screens:
                buttons = sorted(
                    [b for b in screen.buttons if b.is_active],
                    key=lambda b: (b.row, b.col, b.sort_order)
                )
                _menu_cache[screen.slug] = {
                    "message_text_ru": screen.message_text_ru,
                    "message_text_en": screen.message_text_en,
                    "buttons": [
                        {
                            "text_ru": b.text_ru,
                            "text_en": b.text_en,
                            "callback_data": b.callback_data,
                            "url": b.url,
                            "row": b.row,
                            "col": b.col,
                            "button_type": b.button_type,
                            "visibility_condition": b.visibility_condition,
                        }
                        for b in buttons
                    ]
                }
            logger.debug("Menu cache refreshed: %d screens", len(_menu_cache))
    except Exception as e:
        logger.error("Failed to load menus from DB: %s", e)


async def get_tariffs_for_method(payment_method: str) -> Optional[list[dict]]:
    """Get tariffs with prices for a specific payment method."""
    await _ensure_tariff_cache()
    return _tariff_cache.get(payment_method)


async def get_tariff_slug_by_days(payment_method: str, days: int) -> Optional[str]:
    """Find tariff slug by payment method and days."""
    await _ensure_tariff_cache()
    method_tariffs = _tariff_cache.get(payment_method, [])
    for t in method_tariffs:
        if t["days"] == days:
            return t["slug"]
    return None


async def get_squad_for_tariff_slug(tariff_slug: str) -> Optional[dict]:
    """Get squad_id and external_squad_id for a tariff by its slug. Returns None if not found or no squad assigned."""
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


async def get_screen_buttons(screen_slug: str, lang_code: str = "ru") -> Optional[list[dict]]:
    """Get buttons for a screen, localized."""
    await _ensure_menu_cache()
    screen = _menu_cache.get(screen_slug)
    if not screen:
        return None
    text_key = f"text_{lang_code}" if lang_code in ("ru", "en") else "text_ru"
    return [
        {
            "text": btn[text_key],
            "callback_data": btn["callback_data"],
            "url": btn["url"],
            "row": btn["row"],
            "col": btn["col"],
            "button_type": btn["button_type"],
            "visibility_condition": btn["visibility_condition"],
        }
        for btn in screen["buttons"]
    ]


async def get_screen_text(screen_slug: str, lang_code: str = "ru") -> Optional[str]:
    """Get message text for a screen."""
    await _ensure_menu_cache()
    screen = _menu_cache.get(screen_slug)
    if not screen:
        return None
    if lang_code == "en":
        return screen.get("message_text_en") or screen.get("message_text_ru")
    return screen.get("message_text_ru")
