"""Tests for crm_webhooks repository."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.repo import crm_webhooks as webhooks_repo


def _run(coro):
    return asyncio.run(coro)


def test_create_list_matching_and_cooldown() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                rule = await webhooks_repo.create_rule(
                    session,
                    name="torrent",
                    scope="torrent_blocker",
                    event="torrent_blocker.report",
                    actions=[{"type": "send_message", "enabled": True, "text": "hi"}],
                    created_by="admin",
                    cooldown_hours=24,
                )
                await session.flush()

                matched = await webhooks_repo.list_enabled_matching(
                    session,
                    scope="torrent_blocker",
                    event="torrent_blocker.report",
                )
                assert len(matched) == 1
                assert matched[0].id == rule.id

                none = await webhooks_repo.list_enabled_matching(
                    session, scope="user", event="user.expired"
                )
                assert none == []

                assert not await webhooks_repo.has_recent_delivery(
                    session, rule_id=rule.id, tg_id=1, cooldown_hours=24
                )
                await webhooks_repo.record_delivery(
                    session, rule_id=rule.id, tg_id=1
                )
                assert await webhooks_repo.has_recent_delivery(
                    session, rule_id=rule.id, tg_id=1, cooldown_hours=24
                )

                await webhooks_repo.bump_stats(
                    session,
                    rule,
                    webhooks_received=2,
                    messages_sent=1,
                    messages_failed=1,
                )
                assert rule.webhooks_received == 2
                assert rule.messages_sent == 1
                assert rule.messages_failed == 1
        finally:
            await engine.dispose()

    _run(go())
