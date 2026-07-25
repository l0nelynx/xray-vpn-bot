"""App-login handoff state and single-use guarantees."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from miniapp.backend.android import auth_router, repo, security


@pytest.fixture
def app_login_db(session_factory, monkeypatch):
    monkeypatch.setattr(repo, "async_session", session_factory)
    return session_factory


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


async def _store(user_id: int, raw: str, *, ttl: int = 90) -> None:
    await repo.store_verification_code(
        user_id=user_id,
        purpose=repo.PURPOSE_APP_LOGIN,
        code_hash=security.hash_email_code(raw),
        payload=repo.APP_LOGIN_PENDING,
        ttl_seconds=ttl,
    )


def _status(raw: str, user_id: int) -> str:
    result = asyncio.run(
        auth_router.app_login_status(
            auth_router.AppLoginExchangeRequest(token=raw),
            _request(),
            SimpleNamespace(id=user_id),
        )
    )
    return result.status


def test_status_moves_from_pending_to_exchanged(app_login_db):
    raw = "pending-token-12345"
    asyncio.run(_store(10, raw))
    assert _status(raw, 10) == "pending"

    row = asyncio.run(repo.consume_app_login_code(security.hash_email_code(raw)))
    assert row is not None
    assert _status(raw, 10) == "pending"
    asyncio.run(repo.mark_app_login_exchanged(row.id))
    assert _status(raw, 10) == "exchanged"


def test_new_handoff_supersedes_previous_one(app_login_db):
    old = "old-handoff-token"
    new = "new-handoff-token"

    async def go() -> None:
        await _store(10, old)
        await repo.supersede_pending_app_login_codes(10)
        await _store(10, new)

    asyncio.run(go())
    assert _status(old, 10) == "superseded"
    assert _status(new, 10) == "pending"


def test_expired_handoff_cannot_be_consumed(app_login_db):
    raw = "expired-token-12345"
    asyncio.run(_store(10, raw, ttl=-1))
    assert _status(raw, 10) == "expired"
    assert (
        asyncio.run(repo.consume_app_login_code(security.hash_email_code(raw)))
        is None
    )


def test_handoff_is_single_use_under_concurrent_exchange(app_login_db):
    raw = "single-use-token-12345"

    async def go():
        await _store(10, raw)
        code_hash = security.hash_email_code(raw)
        return await asyncio.gather(
            repo.consume_app_login_code(code_hash),
            repo.consume_app_login_code(code_hash),
        )

    results = asyncio.run(go())
    assert sum(row is not None for row in results) == 1


def test_status_is_visible_only_to_owner(app_login_db):
    raw = "private-status-token"
    asyncio.run(_store(10, raw))

    with pytest.raises(HTTPException) as exc:
        _status(raw, 11)
    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "bad_app_login_token"}


def test_unknown_token_is_rejected(app_login_db):
    with pytest.raises(HTTPException) as exc:
        _status("unknown-token-12345", 10)
    assert exc.value.status_code == 401

    assert (
        asyncio.run(
            repo.consume_app_login_code(
                security.hash_email_code("unknown-token-12345")
            )
        )
        is None
    )
