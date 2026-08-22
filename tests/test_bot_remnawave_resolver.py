from __future__ import annotations

import asyncio
from types import SimpleNamespace


def test_resolver_does_not_read_subscription_after_commit(monkeypatch) -> None:
    import app.handlers.tools as tools

    class ExpiringLink:
        expired = False

        @property
        def is_primary(self) -> bool:
            if self.expired:
                raise RuntimeError("detached ORM attribute was accessed")
            return True

    link = ExpiringLink()

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self) -> None:
            link.expired = True

        async def rollback(self) -> None:
            return None

    async def get_user_by_tg_id(_session, _tg_id):
        return SimpleNamespace(id=42, rw_id=1184, email="user@example.com")

    async def get_primary(_session, _user_id):
        return None

    async def resolve_user(**_kwargs):
        return {
            "rw_id": 1184,
            "status": "active",
            "subscription_url": "https://example.com/sub",
        }

    async def attach(_session, **_kwargs):
        return link

    persisted: list[int] = []

    async def persist(**kwargs):
        persisted.append(int(kwargs["rw_id"]))

    monkeypatch.setattr(tools, "async_session", lambda: FakeSession())
    monkeypatch.setattr(tools._repo_users, "get_user_by_tg_id", get_user_by_tg_id)
    monkeypatch.setattr(tools._repo_subscriptions, "get_primary", get_primary)
    monkeypatch.setattr(tools._repo_subscriptions, "attach", attach)
    monkeypatch.setattr(tools.rem, "resolve_remnawave_user", resolve_user)
    monkeypatch.setattr(tools.rq, "update_user_api_info", persist)

    rw_id, info = asyncio.run(tools.resolve_remnawave_account(777, "user"))

    assert rw_id == 1184
    assert info is not None and info["rw_id"] == 1184
    assert persisted == [1184]
