"""Tests for common_db.repo.support — lookups, counts, and the N+1 fix.

The big-deal test is ``test_list_user_tickets_with_last_message_is_two_queries``
which uses SQLAlchemy's connection-level event hook to count how many
SELECTs actually go to the DB. We want exactly 2, regardless of how many
tickets the user has.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401  -- register on Base.metadata
from common_db.models import SupportAttachment, SupportMessage, SupportTicket, User
from common_db.repo import support as repo_support


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


async def _seed_user(session, *, user_id: int = 1, tg_id: int = 1001) -> User:
    u = User(id=user_id, tg_id=tg_id, username=f"u{user_id}")
    session.add(u)
    await session.flush()
    return u


async def _seed_ticket(
    session,
    *,
    ticket_id: int,
    user_id: int,
    subject: str = "subj",
    message: str = "body",
    status: str = "open",
    created: datetime,
) -> SupportTicket:
    t = SupportTicket(
        id=ticket_id,
        user_id=user_id,
        subject=subject,
        message=message,
        status=status,
        created_at=_iso(created),
        updated_at=_iso(created),
    )
    session.add(t)
    await session.flush()
    return t


_NEXT_MSG_ID = [1]
_NEXT_ATT_ID = [1]


def _next_attachment_id() -> int:
    """SQLite + BigInteger PK doesn't auto-increment without INTEGER PRIMARY
    KEY semantics (same issue _seed_message works around above); repo_support
    .add_attachment() deliberately has no id param since real Postgres
    auto-generates it, so tests assign one to the returned object before
    commit."""
    val = _NEXT_ATT_ID[0]
    _NEXT_ATT_ID[0] += 1
    return val


async def _seed_message(
    session, *, ticket_id: int, sender: str, text: str, created: datetime,
    message_id: int | None = None,
) -> SupportMessage:
    # SQLite + BigInteger PK doesn't auto-increment without
    # INTEGER PRIMARY KEY semantics; assign ids explicitly so tests
    # don't get IntegrityError. (Postgres uses an identity sequence.)
    if message_id is None:
        message_id = _NEXT_MSG_ID[0]
        _NEXT_MSG_ID[0] += 1
    m = SupportMessage(
        id=message_id,
        ticket_id=ticket_id, sender=sender, text=text, created_at=_iso(created)
    )
    session.add(m)
    await session.flush()
    return m


# --- get_ticket_by_id -----------------------------------------------------


def test_get_ticket_by_id_returns_ticket() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=42, user_id=1, created=now)
                await session.commit()
            async with Session() as session:
                t = await repo_support.get_ticket_by_id(session, 42)
                assert t is not None and t.id == 42
                assert await repo_support.get_ticket_by_id(session, 9999) is None
        finally:
            await engine.dispose()

    _run(go())


# --- list_user_tickets (thin) ---------------------------------------------


def test_list_user_tickets_orders_newest_first() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            base = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1,
                                   subject="oldest", created=base - timedelta(days=3))
                await _seed_ticket(session, ticket_id=2, user_id=1,
                                   subject="middle", created=base - timedelta(days=1))
                await _seed_ticket(session, ticket_id=3, user_id=1,
                                   subject="newest", created=base)
                await session.commit()
            async with Session() as session:
                tickets = await repo_support.list_user_tickets(session, 1)
                assert [t.subject for t in tickets] == ["newest", "middle", "oldest"]
        finally:
            await engine.dispose()

    _run(go())


def test_list_user_tickets_scopes_to_user() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session, user_id=1, tg_id=1001)
                await _seed_user(session, user_id=2, tg_id=1002)
                await _seed_ticket(session, ticket_id=1, user_id=1,
                                   subject="alice's", created=now)
                await _seed_ticket(session, ticket_id=2, user_id=2,
                                   subject="bob's", created=now)
                await session.commit()
            async with Session() as session:
                a = await repo_support.list_user_tickets(session, 1)
                b = await repo_support.list_user_tickets(session, 2)
                assert {t.subject for t in a} == {"alice's"}
                assert {t.subject for t in b} == {"bob's"}
        finally:
            await engine.dispose()

    _run(go())


# --- list_user_tickets_with_last_message ----------------------------------


def test_list_user_tickets_with_last_message_picks_latest_per_ticket() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            base = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1,
                                   subject="t1", created=base - timedelta(days=2))
                await _seed_ticket(session, ticket_id=2, user_id=1,
                                   subject="t2", created=base)
                # ticket 1: 3 messages, latest is "newest-on-1"
                await _seed_message(session, ticket_id=1, sender="user",
                                    text="first", created=base - timedelta(hours=4))
                await _seed_message(session, ticket_id=1, sender="admin",
                                    text="middle", created=base - timedelta(hours=2))
                await _seed_message(session, ticket_id=1, sender="user",
                                    text="newest-on-1", created=base - timedelta(hours=1))
                # ticket 2: 1 message
                await _seed_message(session, ticket_id=2, sender="user",
                                    text="only-on-2", created=base)
                await session.commit()
            async with Session() as session:
                rows = await repo_support.list_user_tickets_with_last_message(
                    session, 1
                )
                assert [r.ticket.subject for r in rows] == ["t2", "t1"]  # newest first
                by_id = {r.ticket.id: r.last_message_text for r in rows}
                assert by_id[1] == "newest-on-1"
                assert by_id[2] == "only-on-2"
        finally:
            await engine.dispose()

    _run(go())


def test_list_user_tickets_with_last_message_none_for_messageless() -> None:
    """A ticket whose messages were somehow purged should still appear
    in the list, with last_message_text=None — caller falls back to
    ticket.message."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1,
                                   subject="orphan", message="body-text",
                                   created=now)
                await session.commit()
            async with Session() as session:
                rows = await repo_support.list_user_tickets_with_last_message(
                    session, 1
                )
                assert len(rows) == 1
                assert rows[0].last_message_text is None
                # Caller-side fallback contract:
                preview = rows[0].last_message_text or rows[0].ticket.message
                assert preview == "body-text"
        finally:
            await engine.dispose()

    _run(go())


def test_list_user_tickets_with_last_message_empty_returns_empty() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                rows = await repo_support.list_user_tickets_with_last_message(
                    session, 1
                )
                assert rows == []
        finally:
            await engine.dispose()

    _run(go())


def test_list_user_tickets_with_last_message_is_two_queries() -> None:
    """The N+1 fix: regardless of ticket count, we do exactly 2 SELECTs
    on support_* tables (tickets + ranked-messages). Counted via
    SQLAlchemy's ``before_cursor_execute`` hook on the *sync* engine
    that backs the async one."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            base = datetime(2026, 5, 18, 12, 0, 0)
            # Seed 10 tickets, each with 3 messages.
            async with Session() as session:
                await _seed_user(session)
                for i in range(10):
                    await _seed_ticket(
                        session, ticket_id=i + 1, user_id=1,
                        subject=f"t{i}", created=base - timedelta(hours=i),
                    )
                    for j in range(3):
                        await _seed_message(
                            session, ticket_id=i + 1, sender="user",
                            text=f"m{i}-{j}",
                            created=base - timedelta(hours=i, minutes=j),
                        )
                await session.commit()

            # Now count queries during the read.
            counts: dict[str, int] = {"ticket": 0, "message": 0}

            def _on_exec(conn, cursor, statement, params, context, executemany):
                s = statement.lower()
                if "from support_tickets" in s:
                    counts["ticket"] += 1
                if "from support_messages" in s:
                    counts["message"] += 1

            # Async engine's underlying sync engine is .sync_engine
            event.listen(engine.sync_engine, "before_cursor_execute", _on_exec)
            try:
                async with Session() as session:
                    rows = await repo_support.list_user_tickets_with_last_message(
                        session, 1
                    )
                    assert len(rows) == 10
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", _on_exec)

            # Exactly one query touching support_tickets, exactly one
            # touching support_messages. Anything higher means the N+1
            # snuck back in.
            assert counts == {"ticket": 1, "message": 1}, (
                f"expected (1, 1), got {counts}"
            )
        finally:
            await engine.dispose()

    _run(go())


# --- list_messages_for_ticket --------------------------------------------


def test_list_messages_for_ticket_chronological() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            base = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=base)
                await _seed_message(session, ticket_id=1, sender="user",
                                    text="c", created=base + timedelta(hours=2))
                await _seed_message(session, ticket_id=1, sender="user",
                                    text="a", created=base)
                await _seed_message(session, ticket_id=1, sender="admin",
                                    text="b", created=base + timedelta(hours=1))
                await session.commit()
            async with Session() as session:
                msgs = await repo_support.list_messages_for_ticket(session, 1)
                assert [m.text for m in msgs] == ["a", "b", "c"]
        finally:
            await engine.dispose()

    _run(go())


# --- count_open_tickets_for_user ------------------------------------------


def test_count_open_tickets_for_user_only_counts_open() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1,
                                   status="open", created=now)
                await _seed_ticket(session, ticket_id=2, user_id=1,
                                   status="open", created=now)
                await _seed_ticket(session, ticket_id=3, user_id=1,
                                   status="closed", created=now)
                await _seed_ticket(session, ticket_id=4, user_id=1,
                                   status="resolved", created=now)
                await session.commit()
            async with Session() as session:
                n = await repo_support.count_open_tickets_for_user(session, 1)
                assert n == 2
        finally:
            await engine.dispose()

    _run(go())


def test_count_open_tickets_for_user_empty() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                assert await repo_support.count_open_tickets_for_user(session, 1) == 0
        finally:
            await engine.dispose()

    _run(go())


# --- count_tickets_by_status ----------------------------------------------


def test_count_tickets_by_status_filtered_and_unfiltered() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1,
                                   status="open", created=now)
                await _seed_ticket(session, ticket_id=2, user_id=1,
                                   status="closed", created=now)
                await _seed_ticket(session, ticket_id=3, user_id=1,
                                   status="closed", created=now)
                await session.commit()
            async with Session() as session:
                # No filter → total
                assert await repo_support.count_tickets_by_status(session) == 3
                # Single status
                assert await repo_support.count_tickets_by_status(
                    session, ["open"]
                ) == 1
                # Multi
                assert await repo_support.count_tickets_by_status(
                    session, ["open", "closed"]
                ) == 3
                # Empty iterable → 0 (we don't return total)
                assert await repo_support.count_tickets_by_status(session, []) == 0
        finally:
            await engine.dispose()

    _run(go())


# --- delete_admin_message -------------------------------------------------


def test_delete_admin_message_removes_admin_row() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=now)
                await _seed_message(
                    session, ticket_id=1, sender="user",
                    text="u-msg", created=now, message_id=100,
                )
                await _seed_message(
                    session, ticket_id=1, sender="admin",
                    text="a-msg", created=now + timedelta(minutes=1),
                    message_id=101,
                )
                await session.commit()
            async with Session() as session:
                result = await repo_support.delete_admin_message(
                    session, ticket_id=1, message_id=101
                )
                await session.commit()
                assert result.deleted is True
                assert result.attachment_paths == []
            async with Session() as session:
                msgs = await repo_support.list_messages_for_ticket(session, 1)
                assert [m.text for m in msgs] == ["u-msg"]
        finally:
            await engine.dispose()

    _run(go())


def test_delete_admin_message_refuses_user_message() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=now)
                await _seed_message(
                    session, ticket_id=1, sender="user",
                    text="u-msg", created=now, message_id=200,
                )
                await _seed_message(
                    session, ticket_id=1, sender="admin",
                    text="a-msg", created=now + timedelta(minutes=1),
                    message_id=201,
                )
                await session.commit()
            async with Session() as session:
                result = await repo_support.delete_admin_message(
                    session, ticket_id=1, message_id=200
                )
                await session.commit()
                assert result.deleted is False
            async with Session() as session:
                msgs = await repo_support.list_messages_for_ticket(session, 1)
                assert {m.text for m in msgs} == {"u-msg", "a-msg"}
        finally:
            await engine.dispose()

    _run(go())


def test_delete_admin_message_refuses_wrong_ticket() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=now)
                await _seed_ticket(session, ticket_id=2, user_id=1, created=now)
                await _seed_message(
                    session, ticket_id=2, sender="admin",
                    text="a-on-2", created=now, message_id=300,
                )
                await session.commit()
            async with Session() as session:
                result = await repo_support.delete_admin_message(
                    session, ticket_id=1, message_id=300
                )
                await session.commit()
                assert result.deleted is False
            async with Session() as session:
                msgs = await repo_support.list_messages_for_ticket(session, 2)
                assert [m.text for m in msgs] == ["a-on-2"]
        finally:
            await engine.dispose()

    _run(go())


def test_delete_admin_message_missing_id_returns_false() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 5, 18, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=now)
                await session.commit()
            async with Session() as session:
                result = await repo_support.delete_admin_message(
                    session, ticket_id=1, message_id=999999
                )
                assert result.deleted is False
        finally:
            await engine.dispose()

    _run(go())


# --- attachments ------------------------------------------------------------


def test_add_attachment_and_list_messages_eager_loads_it() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 7, 5, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=now)
                msg = await _seed_message(
                    session, ticket_id=1, sender="user", text="screenshot", created=now,
                )
                att = await repo_support.add_attachment(
                    session,
                    message_id=msg.id,
                    original_filename="screenshot.png",
                    stored_path=f"1/abc123.png",
                    mime_type="image/png",
                    size_bytes=1234,
                    created_at=_iso(now),
                )
                att.id = _next_attachment_id()
                await session.commit()
            async with Session() as session:
                msgs = await repo_support.list_messages_for_ticket(session, 1)
                assert len(msgs) == 1
                assert len(msgs[0].attachments) == 1
                att = msgs[0].attachments[0]
                assert att.original_filename == "screenshot.png"
                assert att.stored_path == "1/abc123.png"
                assert att.mime_type == "image/png"
                assert att.size_bytes == 1234
        finally:
            await engine.dispose()

    _run(go())


def test_get_attachment_with_ticket_returns_ticket_and_owner() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 7, 5, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session, user_id=7)
                await _seed_ticket(session, ticket_id=42, user_id=7, created=now)
                msg = await _seed_message(
                    session, ticket_id=42, sender="user", text="pic", created=now,
                )
                att = await repo_support.add_attachment(
                    session,
                    message_id=msg.id,
                    original_filename="a.jpg",
                    stored_path="42/xyz.jpg",
                    mime_type="image/jpeg",
                    size_bytes=99,
                    created_at=_iso(now),
                )
                att.id = _next_attachment_id()
                await session.commit()
                att_id = att.id
            async with Session() as session:
                row = await repo_support.get_attachment_with_ticket(session, att_id)
                assert row is not None
                assert row.ticket_id == 42
                assert row.ticket_user_id == 7
                assert row.attachment.stored_path == "42/xyz.jpg"
        finally:
            await engine.dispose()

    _run(go())


def test_get_attachment_with_ticket_missing_id_returns_none() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                row = await repo_support.get_attachment_with_ticket(session, 999999)
                assert row is None
        finally:
            await engine.dispose()

    _run(go())


def test_delete_admin_message_returns_attachment_paths_for_cleanup() -> None:
    async def go() -> None:
        engine = _make_engine()
        # SQLite does not enforce foreign keys (or their ON DELETE actions)
        # unless told to per-connection -- Postgres always enforces them.
        # Enable it here (scoped to this test's own engine) so the
        # ON DELETE CASCADE this test verifies actually fires, matching
        # production behavior.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_fk(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime(2026, 7, 5, 12, 0, 0)
            async with Session() as session:
                await _seed_user(session)
                await _seed_ticket(session, ticket_id=1, user_id=1, created=now)
                msg = await _seed_message(
                    session, ticket_id=1, sender="admin", text="here", created=now,
                    message_id=500,
                )
                att_a = await repo_support.add_attachment(
                    session, message_id=msg.id, original_filename="a.png",
                    stored_path="1/a.png", mime_type="image/png",
                    size_bytes=10, created_at=_iso(now),
                )
                att_a.id = _next_attachment_id()
                att_b = await repo_support.add_attachment(
                    session, message_id=msg.id, original_filename="b.png",
                    stored_path="1/b.png", mime_type="image/png",
                    size_bytes=20, created_at=_iso(now),
                )
                att_b.id = _next_attachment_id()
                await session.commit()
            async with Session() as session:
                result = await repo_support.delete_admin_message(
                    session, ticket_id=1, message_id=500
                )
                await session.commit()
                assert result.deleted is True
                assert sorted(result.attachment_paths) == ["1/a.png", "1/b.png"]
            async with Session() as session:
                # ON DELETE CASCADE removed the attachment rows along with the message.
                remaining = await session.scalar(
                    select(SupportAttachment).where(SupportAttachment.message_id == 500)
                )
                assert remaining is None
        finally:
            await engine.dispose()

    _run(go())

    _run(go())
