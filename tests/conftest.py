"""Shared fixtures for top-level integration-style tests.

Uses in-memory aiosqlite, mirrors the pattern from
`packages/common_db/tests/test_repo_users.py` (asyncio.run + per-test engine)
but adds pytest fixtures so this module's tests can be parameterized cleanly.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common_db import Base
import common_db.models  # noqa: F401  — registers all tables on Base.metadata


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    asyncio.run(_create_all(eng))
    yield eng
    asyncio.run(eng.dispose())


async def _create_all(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class FakeRemnawave:
    """In-memory stand-in for the numeric-ID Remnawave facade.

    ``uuid`` is accepted only as a convenient fixture label. Application
    lookups and mutations use ``rw_id``; short-UUID wire responses expose
    the v3 ``id`` field.
    """

    def __init__(self):
        self.by_uuid: dict[str, dict] = {}
        self.by_email: dict[str, str] = {}
        self.by_username: dict[str, str] = {}
        self.by_short_uuid: dict[str, str] = {}
        self.disabled_calls: list[int] = []
        self.update_should_raise: Exception | None = None

    def add_user(self, *, uuid: str, status: str = "active",
                 data_limit=None, email: str | None = None,
                 username: str | None = None,
                 subscription_url: str | None = None,
                 short_uuid: str | None = None,
                 rw_id: int | None = None,
                 telegram_id: int | None = None,
                 description: str | None = None,
                 tag: str | None = None) -> None:
        rw_id = rw_id if rw_id is not None else len(self.by_uuid) + 1
        rec = {
            "uuid": uuid,
            "id": rw_id,
            "rw_id": rw_id,
            "status": status,
            "data_limit": data_limit,
            "email": email,
            "username": username,
            "subscription_url": subscription_url,
            "short_uuid": short_uuid,
            "telegram_id": telegram_id,
            "description": description,
            "tag": tag,
        }
        self.by_uuid[uuid] = rec
        if email:
            self.by_email[email] = uuid
        if username:
            self.by_username[username] = uuid
        if short_uuid:
            self.by_short_uuid[short_uuid] = uuid

    async def get_user_from_email(self, email: str):
        uuid = self.by_email.get(email)
        return self.by_uuid.get(uuid) if uuid else None

    async def get_user_from_username(
        self, username: str, *, strict: bool = False,
    ):
        uuid = self.by_username.get(username)
        return self.by_uuid.get(uuid) if uuid else None

    async def get_user_from_id(self, rw_id: int, *, strict: bool = False):
        return next(
            (record for record in self.by_uuid.values() if record.get("rw_id") == rw_id),
            None,
        )

    async def get_user_by_short_uuid_raw(
        self, short_uuid: str, *, strict: bool = True,
    ):
        uuid = self.by_short_uuid.get(short_uuid)
        return self.by_uuid.get(uuid) if uuid else None

    async def update_user(self, *, rw_id: int, status: str | None = None,
                          **_ignored):
        if self.update_should_raise is not None:
            raise self.update_should_raise
        record = await self.get_user_from_id(rw_id)
        if status == "disabled":
            self.disabled_calls.append(rw_id)
        if record is not None and status:
            record["status"] = status
        return record


@pytest.fixture
def fake_remnawave(monkeypatch) -> FakeRemnawave:
    fake = FakeRemnawave()
    # Both the seller bot and the miniapp now go through the single shared
    # facade `remnawave_client.api`; patching it covers every caller that uses
    # attribute access (`rem.get_user_from_email(...)`), including the
    # module-level `resolve_remnawave_user`. Callers that bound the functions by
    # name at import time patch their own module reference too (see
    # test_link_by_url_router.py).
    import remnawave_client.api as rem
    monkeypatch.setattr(rem, "get_user_from_email", fake.get_user_from_email)
    monkeypatch.setattr(rem, "get_user_from_username", fake.get_user_from_username)
    monkeypatch.setattr(rem, "get_user_from_id", fake.get_user_from_id)
    monkeypatch.setattr(rem, "get_user_by_short_uuid_raw",
                        fake.get_user_by_short_uuid_raw)
    return fake


@pytest.fixture
def with_app_db(engine, monkeypatch):
    """Redirect app.database.models.async_session to the in-memory engine.

    `consume_android_link_code` opens its own session via the module-level
    `async_session` import in `app.handlers.android_link`, so we patch BOTH
    the source and the alias copy.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    import app.database.models as models
    monkeypatch.setattr(models, "async_session", sm)
    import app.handlers.android_link as al
    monkeypatch.setattr(al, "async_session", sm)
    return sm


@pytest.fixture
def notify_spy(monkeypatch):
    """Capture every `notify_log` call as plain text in a list."""
    calls: list[str] = []

    async def fake_notify(text, *, parse_mode="HTML"):
        calls.append(text)

    import app.notify_log as nl
    monkeypatch.setattr(nl, "notify_log", fake_notify)
    import app.handlers.android_link as al
    monkeypatch.setattr(al, "notify_log", fake_notify)
    return calls
