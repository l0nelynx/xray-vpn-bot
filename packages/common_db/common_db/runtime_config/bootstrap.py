"""Boot helpers: import YAML → DB once, refresh overlay, optional poll loop."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common_db.repo.runtime import import_payments_from_yaml, import_runtime_from_yaml
from .crypto import derive_key
from .overlay import refresh_from_session, set_crypto_secret

logger = logging.getLogger(__name__)


async def bootstrap_runtime_overlay(
    session_factory: async_sessionmaker[AsyncSession],
    yaml_config: dict,
    *,
    crypto_secret: str,
) -> None:
    """One-shot import (if empty) + load overlay into memory."""
    set_crypto_secret(crypto_secret)
    key = derive_key(crypto_secret)
    async with session_factory() as session:
        imported_rt = await import_runtime_from_yaml(session, yaml_config)
        imported_pay = await import_payments_from_yaml(session, yaml_config, key)
        await session.commit()
        if imported_rt:
            logger.info("Imported runtime settings keys from config.yml")
        if imported_pay:
            logger.info("Imported %s payment integration placeholder(s) from config.yml", imported_pay)
        await refresh_from_session(session, force=True)


async def runtime_overlay_poll_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval: float = 5.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background poll so Dashboard saves propagate without process restart."""
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        try:
            async with session_factory() as session:
                await refresh_from_session(session)
        except Exception:
            logger.exception("runtime overlay refresh failed")
        try:
            if stop_event is not None:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                return
            await asyncio.sleep(interval)
        except asyncio.TimeoutError:
            continue
