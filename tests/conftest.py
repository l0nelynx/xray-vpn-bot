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
    """In-memory stand-in for app.api.remnawave.api.

    State: a dict {uuid: {"status": str, "data_limit": int | None,
                          "email": str | None, "username": str | None,
                          "subscription_url": str | None}}.
    `update_user(uuid, status=...)` records the call in `disabled_calls`
    when status == "disabled".
    """

    def __init__(self):
        self.by_uuid: dict[str, dict] = {}
        self.by_email: dict[str, str] = {}
        self.by_username: dict[str, str] = {}
        self.disabled_calls: list[str] = []
        self.update_should_raise: Exception | None = None

    def add_user(self, *, uuid: str, status: str = "active",
                 data_limit=None, email: str | None = None,
                 username: str | None = None,
                 subscription_url: str | None = None) -> None:
        rec = {
            "uuid": uuid,
            "status": status,
            "data_limit": data_limit,
            "email": email,
            "username": username,
            "subscription_url": subscription_url,
        }
        self.by_uuid[uuid] = rec
        if email:
            self.by_email[email] = uuid
        if username:
            self.by_username[username] = uuid

    async def get_user_from_email(self, email: str):
        uuid = self.by_email.get(email)
        return self.by_uuid.get(uuid) if uuid else None

    async def get_user_from_username(self, username: str):
        uuid = self.by_username.get(username)
        return self.by_uuid.get(uuid) if uuid else None

    async def get_user_from_uuid(self, uuid: str):
        return self.by_uuid.get(uuid)

    async def update_user(self, *, user_uuid: str, status: str | None = None,
                          **_ignored):
        if self.update_should_raise is not None:
            raise self.update_should_raise
        if status == "disabled":
            self.disabled_calls.append(user_uuid)
        if user_uuid in self.by_uuid and status:
            self.by_uuid[user_uuid]["status"] = status
        return self.by_uuid.get(user_uuid)


@pytest.fixture
def fake_remnawave(monkeypatch) -> FakeRemnawave:
    fake = FakeRemnawave()
    import app.api.remnawave.api as rem
    monkeypatch.setattr(rem, "get_user_from_email", fake.get_user_from_email)
    monkeypatch.setattr(rem, "get_user_from_username", fake.get_user_from_username)
    monkeypatch.setattr(rem, "update_user", fake.update_user)
    # get_user_from_uuid не существует в api shim — добавляем атрибут.
    monkeypatch.setattr(rem, "get_user_from_uuid", fake.get_user_from_uuid,
                        raising=False)
    return fake
