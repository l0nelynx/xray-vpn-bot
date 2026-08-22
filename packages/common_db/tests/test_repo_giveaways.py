"""Tests for common_db.repo.giveaways."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Promo, PromoSettings, User
from common_db.models.giveaways import (
    CHANCE_DYNAMIC,
    TICKET_SOURCE_INVITEE_REF,
)
from common_db.models.promos import PROMO_TYPE_REFERRAL
from common_db.repo import giveaways as repo_giveaways
from common_db.repo import promos as repo_promos


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def test_is_in_window_uses_utc() -> None:
    now = datetime(2026, 7, 31, 12, 0, 0)  # UTC noon
    inside = SimpleNamespace(starts_at="2026-07-31T10:00:00", ends_at="2026-07-31T18:00:00")
    before = SimpleNamespace(starts_at="2026-07-31T13:00:00", ends_at=None)
    after = SimpleNamespace(starts_at=None, ends_at="2026-07-31T11:00:00")
    open_ended = SimpleNamespace(starts_at=None, ends_at=None)
    aware = SimpleNamespace(starts_at="2026-07-31T10:00:00+00:00", ends_at=None)

    assert repo_giveaways._is_in_window(inside, now) is True
    assert repo_giveaways._is_in_window(before, now) is False
    assert repo_giveaways._is_in_window(after, now) is False
    assert repo_giveaways._is_in_window(open_ended, now) is True
    assert repo_giveaways._is_in_window(aware, now) is True


def test_join_outside_window() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                future = (
                    datetime.now(timezone.utc).replace(tzinfo=None).replace(year=2099)
                ).isoformat(timespec="seconds")
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Future",
                    channel_text="",
                    config={"chance_mode": "static"},
                    winner_count=1,
                    starts_at=future,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                await session.commit()

                result = await repo_giveaways.join_participant(session, g.id, 1001)
                assert not result.ok
                assert result.reason == "outside_window"
        finally:
            await engine.dispose()

    _run(go())


def test_update_active_schedule_only() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Sched",
                    channel_text="",
                    config={"chance_mode": "static"},
                    winner_count=1,
                    starts_at="2099-01-01T00:00:00",
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                await session.commit()

                await repo_giveaways.update_giveaway(
                    session,
                    g,
                    starts_at="2020-01-01T00:00:00",
                    clear_starts_at=False,
                )
                await session.commit()
                assert g.starts_at == "2020-01-01T00:00:00"

                try:
                    await repo_giveaways.update_giveaway(session, g, title="Nope")
                    raise AssertionError("expected ValueError")
                except ValueError as exc:
                    assert "starts_at/ends_at" in str(exc)
        finally:
            await engine.dispose()

    _run(go())


def test_join_static_giveaway() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Test",
                    channel_text="Hello",
                    config={"chance_mode": "static", "entry_condition": "click_only"},
                    winner_count=1,
                    starts_at=None,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                await session.commit()

                result = await repo_giveaways.join_participant(session, g.id, 1001)
                await session.commit()
                assert result.ok and result.tickets == 1

                again = await repo_giveaways.join_participant(session, g.id, 1001)
                assert again.already_joined and again.tickets == 1
        finally:
            await engine.dispose()

    _run(go())


def test_dynamic_invitee_ref_ticket() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Ref",
                    channel_text="",
                    config={
                        "chance_mode": CHANCE_DYNAMIC,
                        "entry_condition": "click_only",
                        "ticket_sources": [TICKET_SOURCE_INVITEE_REF],
                    },
                    winner_count=1,
                    starts_at=None,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                session.add(PromoSettings(id=1, default_credit_grant=10))
                session.add(Promo(id=1, tg_id=2001, promo_code="OWNER", promo_type=PROMO_TYPE_REFERRAL))
                session.add(User(id=1, tg_id=2001, username="owner"))
                session.add(User(id=2, tg_id=3001, username="inv"))
                await session.commit()

                await repo_giveaways.join_participant(session, g.id, 2001)
                await session.commit()

                await repo_promos.redeem_promo(session, 3001, "OWNER")
                await session.commit()

                tickets = await repo_giveaways.count_tickets(session, g.id, 2001)
                assert tickets == 2  # join + invitee ref
        finally:
            await engine.dispose()

    _run(go())


def test_draw_random_winner() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Draw",
                    channel_text="",
                    config={"chance_mode": "static", "winner_selection": "random"},
                    winner_count=1,
                    starts_at=None,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                await repo_giveaways.join_participant(session, g.id, 1001)
                await repo_giveaways.join_participant(session, g.id, 1002)
                await session.commit()

                winners = await repo_giveaways.draw_winners(session, g)
                await session.commit()
                assert len(winners) == 1
                assert winners[0]["tg_id"] in (1001, 1002)
                assert winners[0]["ticket_number"] in (1, 2)
                assert g.status == "drawn"
        finally:
            await engine.dispose()

    _run(go())


def test_redraw_replaces_and_excludes_previous_winner() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Redraw",
                    channel_text="",
                    config={"chance_mode": "static", "winner_selection": "random"},
                    winner_count=1,
                    starts_at=None,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                for tg_id in (1001, 1002, 1003):
                    await repo_giveaways.join_participant(session, g.id, tg_id)
                await session.commit()

                first = await repo_giveaways.draw_winners(session, g)
                await session.commit()
                second = await repo_giveaways.redraw_winners(session, g)
                await session.commit()

                assert len(second) == 1
                assert second[0]["tg_id"] != first[0]["tg_id"]
                assert second[0]["ticket_number"] in (1, 2, 3)
                persisted = await repo_giveaways.get_winners(session, g.id)
                assert persisted == second
        finally:
            await engine.dispose()

    _run(go())


def test_redraw_keeps_old_result_when_pool_is_too_small() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="No replacements",
                    channel_text="",
                    config={"chance_mode": "static", "winner_selection": "random"},
                    winner_count=2,
                    starts_at=None,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                await repo_giveaways.join_participant(session, g.id, 1001)
                await repo_giveaways.join_participant(session, g.id, 1002)
                await session.commit()
                giveaway_id = g.id

                original = await repo_giveaways.draw_winners(session, g)
                await session.commit()
                try:
                    await repo_giveaways.redraw_winners(session, g)
                    raise AssertionError("expected ValueError")
                except ValueError as exc:
                    assert "not enough eligible participants" in str(exc)
                    await session.rollback()

                assert await repo_giveaways.get_winners(session, giveaway_id) == original
        finally:
            await engine.dispose()

    _run(go())


def test_most_tickets_uses_participants_first_ticket_number() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Most tickets",
                    channel_text="",
                    config={"chance_mode": "dynamic", "winner_selection": "most_tickets"},
                    winner_count=1,
                    starts_at=None,
                    ends_at=None,
                )
                await repo_giveaways.activate_giveaway(session, g)
                await repo_giveaways.join_participant(session, g.id, 1001)
                await repo_giveaways.join_participant(session, g.id, 1002)
                await repo_giveaways._grant_ticket(
                    session,
                    giveaway_id=g.id,
                    participant_tg_id=1002,
                    source="test_bonus",
                    source_tg_id=1,
                )
                await session.commit()

                winners = await repo_giveaways.draw_winners(session, g)
                await session.commit()

                assert winners[0]["tg_id"] == 1002
                assert winners[0]["tickets"] == 2
                assert winners[0]["ticket_number"] == 2
        finally:
            await engine.dispose()

    _run(go())


def test_redraw_rejects_non_drawn_status() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                g = await repo_giveaways.create_giveaway(
                    session,
                    title="Draft",
                    channel_text="",
                    config={"chance_mode": "static"},
                    winner_count=1,
                    starts_at=None,
                    ends_at=None,
                )
                try:
                    await repo_giveaways.redraw_winners(session, g)
                    raise AssertionError("expected ValueError")
                except ValueError as exc:
                    assert "only drawn giveaways" in str(exc)
        finally:
            await engine.dispose()

    _run(go())
