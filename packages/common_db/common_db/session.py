"""Async engine + sessionmaker factory.

Each service calls `make_async_session(default_sqlite_path=...)` once at
import time and gets back its own (engine, async_session) pair bound to the
shared common_db.base.Base metadata. The shared models module does not
create any engine on its own — that stays the responsibility of each
service's database/session.py.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from .url import async_db_url


def make_async_session(
    *,
    default_sqlite_path: str | None = None,
    echo: bool = False,
    pool_pre_ping: bool = True,
    expire_on_commit: bool = False,
    connect_args: dict[str, Any] | None = None,
) -> tuple[AsyncEngine, async_sessionmaker]:
    """Build (engine, async_session) for the current service.

    sqlite-specific connect args are applied automatically when the resolved
    URL is sqlite — services don't have to repeat that boilerplate.
    """
    url = async_db_url(default_sqlite_path=default_sqlite_path)

    effective_connect_args: dict[str, Any] = dict(connect_args or {})
    if url.startswith("sqlite") and not effective_connect_args:
        effective_connect_args = {"check_same_thread": False, "timeout": 30}

    engine = create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
        connect_args=effective_connect_args,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=expire_on_commit)
    return engine, session_factory
