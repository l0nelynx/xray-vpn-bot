"""Live, short-TTL access to the Telegram menu feature flag."""
from __future__ import annotations

import logging
import time

from app.database.models import async_session
from common_db.repo.system import get_bot_feature_flags, get_cache_version

_value = False
_checked_at = 0.0
_known_version = -1
_TTL = 5.0
logger = logging.getLogger(__name__)


async def is_enabled() -> bool:
    global _value, _checked_at, _known_version
    now = time.monotonic()
    if now - _checked_at < _TTL:
        return _value
    try:
        async with async_session() as session:
            version = await get_cache_version(session)
            if version != _known_version:
                flags = await get_bot_feature_flags(session)
                _value = bool(flags.legacy_bot_constructor)
                _known_version = version
            await session.commit()
    except Exception:
        logger.exception("Feature flag read failed; using cached runtime mode")
    _checked_at = now
    return _value


def invalidate() -> None:
    global _checked_at, _known_version
    _checked_at = 0.0
    _known_version = -1
