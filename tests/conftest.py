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
