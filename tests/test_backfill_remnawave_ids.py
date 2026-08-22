from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Transaction, User, UserSubscription
from scripts.backfill_remnawave_ids import (
    _BACKFILL_SUBSCRIPTION_SOURCES,
    _DEFAULT_BACKFILL_SUBSCRIPTION_SOURCE,
    _api_base_url,
    _page,
    _primary_repair,
    build_panel_index,
    run_backfill,
)

LEGACY_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
LEGACY_B = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
LEGACY_PRIMARY = "cccccccc-dddd-eeee-ffff-000000000000"
LEGACY_C = "dddddddd-eeee-ffff-0000-111111111111"
PROTOCOL_A = "11111111-2222-3333-4444-555555555555"
PROTOCOL_B = "22222222-3333-4444-5555-666666666666"
PROTOCOL_C = "33333333-4444-5555-6666-777777777777"


def test_backfill_subscription_sources_fit_database_column() -> None:
    sources = [
        _DEFAULT_BACKFILL_SUBSCRIPTION_SOURCE,
        *_BACKFILL_SUBSCRIPTION_SOURCES.values(),
    ]
    assert all(len(source) <= 30 for source in sources)


def _run(coro):
    return asyncio.run(coro)


def _panel(*items):
    return build_panel_index(list(items))


def test_panel_index_detects_ambiguous_legacy_uuid() -> None:
    panel = _panel(
        {"id": 11, "uuid": LEGACY_A.upper()},
        {"id": 22, "uuid": LEGACY_A},
        {"id": 33, "uuid": LEGACY_B},
    )
    assert panel.by_legacy_uuid == {LEGACY_B: 33}
    assert panel.duplicate_legacy_uuids == {LEGACY_A: (11, 22)}


def test_panel_index_maps_and_deduplicates_protocol_vless_uuid() -> None:
    panel = _panel(
        {"id": 11, "uuid": LEGACY_A, "vlessUuid": PROTOCOL_A.upper()},
        {"id": 22, "uuid": LEGACY_B, "vlessUuid": PROTOCOL_B},
        {"id": 33, "uuid": LEGACY_PRIMARY, "vlessUuid": PROTOCOL_B},
    )
    assert panel.by_protocol_vless_uuid == {PROTOCOL_A: 11}
    assert panel.duplicate_protocol_vless_uuids == {PROTOCOL_B: (22, 33)}


def test_page_unwraps_remnawave_envelope() -> None:
    items, total = _page({
        "response": {"users": [{"id": 1, "uuid": "a"}], "total": 3}
    })
    assert items == [{"id": 1, "uuid": "a"}]
    assert total == 3


def test_api_base_url_matches_sdk_convention() -> None:
    assert _api_base_url("https://panel.example") == "https://panel.example/api"
    assert _api_base_url("https://panel.example/api/") == "https://panel.example/api"


def test_primary_repair_argument_parses_explicit_ids() -> None:
    assert _primary_repair("2001:1184") == (2001, 1184)


def test_dry_run_then_apply_resolves_and_attaches() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=101, vless_uuid=LEGACY_A),
                    User(id=2, tg_id=202, rw_id=22, vless_uuid=LEGACY_B),
                ])
                await session.commit()

            panel = _panel(
                {"id": 11, "uuid": LEGACY_A},
                {"id": 22, "uuid": LEGACY_B},
            )
            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=False
            )
            assert code == 0
            assert report["ready"] is False
            assert report["planned"] == {
                "resolve_legacy": 1,
                "resolve_protocol_vless": 0,
                "resolve_email": 0,
                "attach_existing": 1,
                "sync_primary_projection": 0,
            }
            async with Session() as session:
                assert await session.scalar(select(UserSubscription)) is None
                assert (await session.get(User, 1)).rw_id is None

            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=True
            )
            assert code == 0
            assert report["ready"] is True
            assert report["applied"] == 2
            async with Session() as session:
                users = list((await session.scalars(select(User).order_by(User.id))).all())
                links = list(
                    (await session.scalars(
                        select(UserSubscription).order_by(UserSubscription.user_id)
                    )).all()
                )
                assert [user.rw_id for user in users] == [11, 22]
                assert [(link.user_id, link.rw_id, link.is_primary) for link in links] == [
                    (1, 11, True),
                    (2, 22, True),
                ]
        finally:
            await engine.dispose()

    _run(go())


def test_protocol_vless_uuid_recovers_android_bugged_user() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(
                    id=1,
                    email="android@example.com",
                    vless_uuid=PROTOCOL_A,
                ))
                await session.commit()

            panel = _panel({
                "id": 11,
                "uuid": LEGACY_A,
                "vlessUuid": PROTOCOL_A,
            })
            code, dry = await run_backfill(
                panel=panel, session_factory=Session, apply=False
            )
            assert code == 0
            assert dry["planned"]["resolve_legacy"] == 0
            assert dry["planned"]["resolve_protocol_vless"] == 1

            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=True
            )
            assert code == 0 and report["ready"] is True
            async with Session() as session:
                user = await session.get(User, 1)
                link = await session.scalar(select(UserSubscription))
                assert user is not None and user.rw_id == 11
                assert link is not None
                assert link.rw_id == 11 and link.is_primary is True
                assert link.source == "protocol_uuid_backfill_2_8"
        finally:
            await engine.dispose()

    _run(go())


def test_cross_panel_and_protocol_uuid_collision_blocks_writes() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, vless_uuid=PROTOCOL_A))
                await session.commit()

            panel = _panel(
                {"id": 11, "uuid": LEGACY_A, "vlessUuid": PROTOCOL_A},
                {"id": 22, "uuid": PROTOCOL_A, "vlessUuid": PROTOCOL_B},
            )
            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=True
            )
            assert code == 2
            assert report["blocker_counts"]["cross_identifier_collisions"] == 1
            assert report["blocker_counts"]["ambiguous_local_identifiers"] == 1
            async with Session() as session:
                assert (await session.get(User, 1)).rw_id is None
                assert await session.scalar(select(UserSubscription)) is None
        finally:
            await engine.dispose()

    _run(go())


def test_conflicting_owner_blocks_all_writes() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=101, vless_uuid=LEGACY_A),
                    User(id=2, tg_id=202, rw_id=11),
                ])
                await session.commit()

            code, report = await run_backfill(
                panel=_panel({"id": 11, "uuid": LEGACY_A}),
                session_factory=Session,
                apply=True,
            )
            assert code == 2
            assert report["blocker_counts"]["ownership_conflicts"] == 1
            async with Session() as session:
                assert (await session.get(User, 1)).rw_id is None
                assert await session.scalar(select(UserSubscription)) is None
        finally:
            await engine.dispose()

    _run(go())


def test_existing_primary_is_preserved_when_legacy_profile_is_additional() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=101, vless_uuid=LEGACY_A))
                session.add(UserSubscription(
                    user_id=1,
                    rw_id=30,
                    source="existing",
                    is_primary=True,
                    created_at="2026-01-01T00:00:00",
                    updated_at="2026-01-01T00:00:00",
                ))
                await session.commit()

            code, report = await run_backfill(
                panel=_panel(
                    {"id": 11, "uuid": LEGACY_A},
                    {"id": 30, "uuid": LEGACY_PRIMARY},
                ),
                session_factory=Session,
                apply=True,
            )
            assert code == 0 and report["ready"] is True
            async with Session() as session:
                user = await session.get(User, 1)
                links = list(
                    (await session.scalars(
                        select(UserSubscription).order_by(UserSubscription.rw_id)
                    )).all()
                )
                assert user.rw_id == 30
                assert [(link.rw_id, link.is_primary) for link in links] == [
                    (11, False),
                    (30, True),
                ]
        finally:
            await engine.dispose()

    _run(go())


def test_existing_projection_without_primary_is_repaired() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=101, rw_id=11, vless_uuid=LEGACY_A))
                session.add(UserSubscription(
                    user_id=1,
                    rw_id=11,
                    source="broken_legacy",
                    is_primary=False,
                    created_at="2026-01-01T00:00:00",
                    updated_at="2026-01-01T00:00:00",
                ))
                await session.commit()

            panel = _panel({"id": 11, "uuid": LEGACY_A})
            code, dry = await run_backfill(
                panel=panel, session_factory=Session, apply=False
            )
            assert code == 0
            assert dry["planned"]["attach_existing"] == 1

            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=True
            )
            assert code == 0 and report["ready"] is True
            async with Session() as session:
                link = await session.scalar(select(UserSubscription))
                assert link is not None and link.is_primary is True
        finally:
            await engine.dispose()

    _run(go())


def test_non_uuid_legacy_sentinels_are_reported_but_do_not_block() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=101, vless_uuid="None"),
                    User(id=2, tg_id=202, vless_uuid="null"),
                    User(id=3, tg_id=303, vless_uuid="not-a-panel-uuid"),
                ])
                await session.commit()

            code, report = await run_backfill(
                panel=_panel({"id": 11, "uuid": LEGACY_A}),
                session_factory=Session,
                apply=False,
            )
            assert code == 0
            assert report["ready"] is True
            assert report["blocker_counts"]["unresolved_user_ids"] == 0
            assert report["ignored_counts"]["non_uuid_legacy_values"] == 3
            assert [
                item["user_id"]
                for item in report["ignored_samples"]["non_uuid_legacy_values"]
            ] == [1, 2, 3]
        finally:
            await engine.dispose()

    _run(go())


def test_missing_legacy_profile_blocks_only_for_active_paid_user() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=999, tg_id=999, vless_uuid=LEGACY_A),
                    User(id=2000, tg_id=2000, vless_uuid=LEGACY_B),
                    Transaction(
                        transaction_id="active-tx",
                        vless_uuid=LEGACY_A,
                        order_status="delivered",
                        delivery_status=1,
                        days_ordered=30,
                        expire_date="2099-01-01T00:00:00",
                        user_id=999,
                        target_rw_id=11,
                    ),
                    Transaction(
                        transaction_id="expired-tx",
                        vless_uuid=LEGACY_B,
                        order_status="delivered",
                        delivery_status=1,
                        days_ordered=30,
                        expire_date="2020-01-01T00:00:00",
                        user_id=2000,
                        target_rw_id=22,
                    ),
                ])
                await session.commit()

            code, report = await run_backfill(
                panel=_panel({"id": 30, "uuid": LEGACY_PRIMARY}),
                session_factory=Session,
                apply=False,
            )
            assert code == 2
            assert report["policy"] == {
                "missing_panel_profile": (
                    "try_exact_unique_email_then_block_only_with_active_paid_transaction"
                ),
                "active_paid_order_statuses": ["confirmed", "delivered"],
            }
            assert report["blocker_samples"]["unresolved_user_ids"] == [999]
            assert report["ignored_counts"][
                "missing_panel_profiles_without_active_paid_transaction"
            ] == 1
            assert report["ignored_samples"][
                "missing_panel_profiles_without_active_paid_transaction"
            ] == [2000]
            assert report["unresolved_active_paid_details"] == [{
                "user_id": 999,
                "transactions": [{
                    "transaction_id": "active-tx",
                    "order_status": "delivered",
                    "delivery_status": 1,
                    "expire_date": "2099-01-01T00:00:00",
                    "target_rw_id": 11,
                }],
            }]
        finally:
            await engine.dispose()

    _run(go())


def test_missing_legacy_profile_is_recovered_by_exact_email() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(
                    id=2000,
                    email=" Migrated@Example.COM ",
                    vless_uuid=LEGACY_A,
                ))
                await session.commit()

            panel = _panel({
                "id": 30,
                "uuid": LEGACY_PRIMARY,
                "vlessUuid": PROTOCOL_A,
                "email": "migrated@example.com",
            })
            code, dry = await run_backfill(
                panel=panel, session_factory=Session, apply=False
            )
            assert code == 0 and dry["ready"] is False
            assert dry["planned"]["resolve_email"] == 1
            assert dry["ignored_counts"][
                "missing_panel_profiles_without_active_paid_transaction"
            ] == 0

            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=True
            )
            assert code == 0 and report["ready"] is True
            async with Session() as session:
                user = await session.get(User, 2000)
                link = await session.scalar(select(UserSubscription))
                assert user is not None and user.rw_id == 30
                assert link is not None and link.rw_id == 30
                assert link.source == "exact_email_backfill_2_8"
        finally:
            await engine.dispose()

    _run(go())


def test_duplicate_panel_email_blocks_automatic_recovery() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(
                    id=2000,
                    email="duplicate@example.com",
                    vless_uuid=LEGACY_A,
                ))
                await session.commit()

            panel = _panel(
                {
                    "id": 30,
                    "uuid": LEGACY_PRIMARY,
                    "vlessUuid": PROTOCOL_A,
                    "email": "duplicate@example.com",
                },
                {
                    "id": 31,
                    "uuid": LEGACY_C,
                    "vlessUuid": PROTOCOL_C,
                    "email": "DUPLICATE@example.com",
                },
            )
            code, report = await run_backfill(
                panel=panel, session_factory=Session, apply=True
            )
            assert code == 2
            assert report["blocker_counts"]["ambiguous_email_matches"] == 1
            assert report["blocker_samples"]["ambiguous_email_matches"] == [{
                "user_id": 2000,
                "email": "duplicate@example.com",
                "rw_ids": [30, 31],
            }]
            async with Session() as session:
                assert (await session.get(User, 2000)).rw_id is None
                assert await session.scalar(select(UserSubscription)) is None
        finally:
            await engine.dispose()

    _run(go())


def test_primary_mismatch_report_contains_both_numeric_ids() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=101, rw_id=11, vless_uuid=LEGACY_A))
                session.add(UserSubscription(
                    user_id=1,
                    rw_id=22,
                    source="primary",
                    is_primary=True,
                    created_at="2026-01-02T00:00:00",
                    updated_at="2026-01-02T00:00:00",
                ))
                await session.commit()

            panel = _panel(
                {"id": 11, "uuid": LEGACY_A},
                {"id": 22, "uuid": LEGACY_B},
            )
            code, report = await run_backfill(
                panel=panel,
                session_factory=Session,
                apply=False,
            )
            assert code == 2
            assert report["blocker_samples"]["primary_mismatch_user_ids"] == [1]
            assert report["primary_mismatch_details"] == [{
                "user_id": 1,
                "users_rw_id": 11,
                "primary_rw_id": 22,
            }]

            code, report = await run_backfill(
                panel=panel,
                session_factory=Session,
                apply=False,
                primary_projection_repairs={1: 999},
            )
            assert code == 2
            assert report["planned"]["sync_primary_projection"] == 0
            assert report["blocker_counts"]["invalid_primary_repair_requests"] == 1

            code, report = await run_backfill(
                panel=panel,
                session_factory=Session,
                apply=False,
                primary_projection_repairs={1: 22},
            )
            assert code == 0
            assert report["ready"] is False
            assert report["planned"]["attach_existing"] == 1
            assert report["planned"]["sync_primary_projection"] == 1
            assert report["blocker_counts"]["primary_mismatch_user_ids"] == 0
            assert report["confirmed_primary_projection_repairs"] == [{
                "user_id": 1,
                "primary_rw_id": 22,
            }]

            code, report = await run_backfill(
                panel=panel,
                session_factory=Session,
                apply=True,
                primary_projection_repairs={1: 22},
            )
            assert code == 0 and report["ready"] is True
            assert report["applied"] == 2
            async with Session() as session:
                user = await session.get(User, 1)
                links = list(
                    (await session.scalars(
                        select(UserSubscription).order_by(UserSubscription.rw_id)
                    )).all()
                )
                assert user.rw_id == 22
                assert [(link.rw_id, link.is_primary) for link in links] == [
                    (11, False),
                    (22, True),
                ]
        finally:
            await engine.dispose()

    _run(go())
