import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.miniapp.backend.routers import payments


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return False


def _session_factory():
    return _SessionContext()


def test_explicit_subscription_must_belong_to_account(monkeypatch):
    async def missing(_session, *, user_id, subscription_id):
        assert (user_id, subscription_id) == (10, 99)
        return None

    monkeypatch.setattr(payments, "async_session", _session_factory)
    monkeypatch.setattr(payments._repo_subscriptions, "get_for_user", missing)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            payments._purchase_target_rw_id(user_id=10, subscription_id=99)
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "subscription_not_found"}


def test_explicit_subscription_resolves_exact_rw_id(monkeypatch):
    async def owned(_session, *, user_id, subscription_id):
        assert (user_id, subscription_id) == (10, 5)
        return SimpleNamespace(rw_id=2048)

    monkeypatch.setattr(payments, "async_session", _session_factory)
    monkeypatch.setattr(payments._repo_subscriptions, "get_for_user", owned)

    assert (
        asyncio.run(payments._purchase_target_rw_id(user_id=10, subscription_id=5))
        == 2048
    )


def test_omitted_subscription_uses_primary(monkeypatch):
    async def primary(_session, user_id):
        assert user_id == 10
        return SimpleNamespace(rw_id=1031)

    monkeypatch.setattr(payments, "async_session", _session_factory)
    monkeypatch.setattr(payments._repo_subscriptions, "get_primary", primary)

    assert (
        asyncio.run(
            payments._purchase_target_rw_id(user_id=10, subscription_id=None)
        )
        == 1031
    )
