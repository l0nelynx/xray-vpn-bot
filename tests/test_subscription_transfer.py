"""Remaining-time transfer guarantees for the subscription-page account hub."""
from __future__ import annotations

import asyncio
import importlib
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from common_db.models import User
from common_db.repo import subscriptions
@pytest.fixture
def transfer_db(session_factory, monkeypatch):
    config_path = Path(__file__).resolve().parents[1] / "config-example.yml"
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    import miniapp.backend.config as config

    # CONFIG_PATH is captured at module import time. Keep this harmless test
    # path for later import-smoke tests instead of restoring `/app/config.yml`
    # while the module remains cached in sys.modules.
    config.CONFIG_PATH = str(config_path)
    config._config = None
    sso = importlib.import_module("miniapp.backend.web.subscription_sso_router")
    monkeypatch.setattr(sso, "async_session", session_factory)
    return session_factory, sso


def test_transfer_is_confirmed_single_use_and_idempotent(
    transfer_db, monkeypatch
) -> None:
    session_factory, sso = transfer_db
    calls: list[tuple[int, dict]] = []
    now = int(time.time())
    rem_users = {
        101: {"id": 101, "expire": now + 3 * 86400, "status": "active"},
        202: {"id": 202, "expire": now + 5 * 86400, "status": "active"},
    }

    async def get_user(rw_id: int):
        return rem_users.get(rw_id)

    async def update_user(rw_id: int, **changes):
        calls.append((rw_id, changes))
        if rw_id == 101 and changes.get("status") == "disabled":
            rem_users[rw_id]["status"] = "disabled"
        return rem_users.get(rw_id)

    monkeypatch.setattr(sso.security, "decode_subscription_context", lambda _token: (101, "slug"))
    monkeypatch.setattr(sso, "get_user_from_id", get_user)
    monkeypatch.setattr(sso, "update_user_by_id", update_user)

    async def go() -> None:
        async with session_factory() as session:
            session.add(User(id=1, email="owner@example.com"))
            await session.flush()
            target = await subscriptions.attach(
                session, user_id=1, rw_id=202, source="account"
            )
            await session.commit()

        body = sso.TransferSubscriptionRequest(
            context="x" * 20,
            target_subscription_id=target.id,
            confirmed=True,
        )
        first = await sso.transfer_subscription_time(body, SimpleNamespace(id=1))
        second = await sso.transfer_subscription_time(body, SimpleNamespace(id=1))

        assert first.status == "completed"
        assert first.days_transferred == 3
        assert second == first
        assert calls == [(202, {"days": 8}), (101, {"status": "disabled"})]

        async with session_factory() as session:
            rows = await subscriptions.list_for_user(session, 1)
            assert {row.rw_id for row in rows} == {101, 202}

    asyncio.run(go())


def test_transfer_requires_explicit_confirmation(transfer_db) -> None:
    _, sso = transfer_db
    body = sso.TransferSubscriptionRequest(
        context="x" * 20,
        target_subscription_id=1,
        confirmed=False,
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(sso.transfer_subscription_time(body, SimpleNamespace(id=1)))
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "confirmation_required"}


def test_transfer_rejects_subscription_owned_by_another_account(
    transfer_db, monkeypatch
) -> None:
    session_factory, sso = transfer_db
    monkeypatch.setattr(sso.security, "decode_subscription_context", lambda _token: (101, "slug"))

    async def go() -> None:
        async with session_factory() as session:
            session.add_all([User(id=1), User(id=2)])
            await session.flush()
            target = await subscriptions.attach(
                session, user_id=1, rw_id=202, source="account"
            )
            await subscriptions.attach(
                session, user_id=2, rw_id=101, source="other_account"
            )
            await session.commit()

        body = sso.TransferSubscriptionRequest(
            context="x" * 20,
            target_subscription_id=target.id,
            confirmed=True,
        )
        with pytest.raises(HTTPException) as exc:
            await sso.transfer_subscription_time(body, SimpleNamespace(id=1))
        assert exc.value.status_code == 409
        assert exc.value.detail == {"code": "subscription_already_linked"}

    asyncio.run(go())
