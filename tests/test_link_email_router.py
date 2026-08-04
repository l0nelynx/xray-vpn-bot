"""Router-level tests for POST /api/link/email (miniapp email→TG link)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_db.models import User


@dataclass
class _FakeTg:
    tg_id: int = 55
    username: str | None = "bob"


@dataclass
class _FakeEmailUser:
    id: int = 100
    email: str = "a@x.io"
    password_hash: str = "hash"
    tg_id: int | None = None
    is_banned: bool = False


@pytest.fixture
def link_email_app(with_app_db, fake_remnawave, monkeypatch):
    import miniapp.backend.database.session as mdb
    import miniapp.backend.notify_log as nl
    import miniapp.backend.routers.link_email as le
    import miniapp.backend.tg_auth as tg_auth

    monkeypatch.setattr(mdb, "async_session", with_app_db)
    monkeypatch.setattr(le, "async_session", with_app_db)

    notify_calls: list[str] = []

    async def fake_notify(text, *, parse_mode="HTML"):
        notify_calls.append(text)

    monkeypatch.setattr(nl, "notify_log", fake_notify)
    monkeypatch.setattr(le, "notify_log", fake_notify)

    app = FastAPI()
    app.include_router(le.router)
    app.state.notify_calls = notify_calls
    app.state.fake_tg = _FakeTg()
    app.state.email_user = _FakeEmailUser()
    app.state.password_ok = True

    async def override_tg():
        return app.state.fake_tg

    async def fake_find_user_by_email(email: str):
        u = app.state.email_user
        if u is None or u.email != email:
            return None
        return u

    async def fake_verify_password(password_hash, password):
        if not app.state.password_ok:
            return False
        return password_hash is not None

    monkeypatch.setattr(le.repo, "find_user_by_email", fake_find_user_by_email)
    monkeypatch.setattr(le.security, "verify_password", fake_verify_password)

    app.dependency_overrides[tg_auth.get_tg_user] = override_tg
    # Also override the Depends binding imported into the router module.
    app.dependency_overrides[le.get_tg_user] = override_tg

    app.state.limiter = le.limiter
    le.limiter.reset()
    return app


@pytest.fixture
def client(link_email_app):
    return TestClient(link_email_app)


class TestLinkEmailEndpoint:
    def test_invalid_credentials(self, link_email_app, client):
        link_email_app.state.password_ok = False
        resp = client.post(
            "/api/link/email",
            json={"email": "a@x.io", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "invalid_credentials"

    def test_telegram_conflict(self, link_email_app, client):
        link_email_app.state.email_user = _FakeEmailUser(tg_id=999)
        resp = client.post(
            "/api/link/email",
            json={"email": "a@x.io", "password": "ok"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "telegram_conflict"
        assert any("telegram_conflict" in m for m in link_email_app.state.notify_calls)

    def test_already_linked(self, link_email_app, client):
        link_email_app.state.email_user = _FakeEmailUser(tg_id=55)
        resp = client.post(
            "/api/link/email",
            json={"email": "a@x.io", "password": "ok"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == "already_linked"
        assert body["survivor_id"] == 100

    def test_merge_email_survivor(self, link_email_app, client, with_app_db, fake_remnawave):
        fake_remnawave.add_user(
            uuid="a-uuid", email="a@x.io", status="active",
            data_limit=None, rw_id=1,
        )
        fake_remnawave.add_user(
            uuid="t-uuid", username="bob", status="active",
            data_limit=10 * 1024 ** 3, rw_id=2, telegram_id=55,
        )

        async def seed():
            async with with_app_db() as s:
                s.add(User(
                    id=100, email="a@x.io", password_hash="ph", rw_id=1,
                    email_verified_at="2026-05-19T00:00:00",
                ))
                s.add(User(
                    id=200, tg_id=55, username="bob",
                    vless_uuid="t-uuid", rw_id=2,
                ))
                await s.commit()

        asyncio.run(seed())

        resp = client.post(
            "/api/link/email",
            json={"email": "a@x.io", "password": "ok"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["survivor_id"] == 100
        assert body["result"] in ("ok", "merged_pro", "merged_free")

        async def verify():
            async with with_app_db() as s:
                survivor = await s.get(User, 100)
                loser = await s.get(User, 200)
                return survivor, loser

        survivor, loser = asyncio.run(verify())
        assert loser is None
        assert survivor is not None
        assert survivor.tg_id == 55
        assert survivor.email == "a@x.io"
