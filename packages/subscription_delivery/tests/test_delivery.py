"""Unit tests for the shared Android delivery, with the Remnawave layer,
DB session and notifier all faked — no network, no real DB.
"""
import asyncio
from contextlib import asynccontextmanager

import pytest

from remnawave_client import SubscriptionScenario
import subscription_delivery.delivery as d


class _FakeSession:
    def __init__(self, sink):
        self.sink = sink

    async def execute(self, stmt, params=None):
        self.sink.append(params)

    async def commit(self):
        pass


def _make_session_factory(sink):
    @asynccontextmanager
    async def factory():
        yield _FakeSession(sink)
    return factory


def _patch_remnawave(monkeypatch, *, scenario, info=None, apply_result=None):
    async def fake_get_user_from_username(_username):
        return info
    monkeypatch.setattr(d.rem, "get_user_from_username", fake_get_user_from_username)
    monkeypatch.setattr(d, "resolve_scenario", lambda *_a, **_k: scenario)

    async def fake_apply_new_user(**_kw):
        return apply_result
    async def fake_apply_extend(**_kw):
        return apply_result
    async def fake_apply_update(**_kw):
        return apply_result
    monkeypatch.setattr(d, "apply_new_user", fake_apply_new_user)
    monkeypatch.setattr(d, "apply_extend", fake_apply_extend)
    monkeypatch.setattr(d, "apply_update", fake_apply_update)


def test_email_to_username_and_slug_parsing():
    assert d.email_to_username("Foo.Bar@Mail.io") == "foo_bar_at_mail_io"
    assert d._parse_squad_slug("sid:S1:esid:E1") == {"squad_id": "S1", "external_squad_id": "E1"}
    assert d._parse_squad_slug("plain-slug") is None


def test_missing_email_returns_error(monkeypatch):
    notes = []
    res = asyncio.run(d.deliver_android_paid(
        transaction_id="tx1", android_user_id=1, email=None, days=30,
        tariff_slug="sid:S1:esid:E1",
        session_factory=_make_session_factory([]),
        notifier=lambda t: _append(notes, t),
    ))
    assert res["status"] == "error"
    assert res["message"] == "android_user_missing_email"


def test_bad_slug_without_resolver_returns_error(monkeypatch):
    res = asyncio.run(d.deliver_android_paid(
        transaction_id="tx1", android_user_id=1, email="a@b.io", days=30,
        tariff_slug="plain-slug",  # not sid:..:esid:.. and no resolver
        session_factory=_make_session_factory([]),
        notifier=lambda t: _noop(),
    ))
    assert res["status"] == "error"
    assert "bad tariff_slug" in res["message"]


def test_new_user_success_updates_delivery_and_notifies(monkeypatch):
    _patch_remnawave(
        monkeypatch,
        scenario=SubscriptionScenario.NEW_USER,
        info=None,
        apply_result={"uuid": "rw-uuid", "subscription_url": "https://sub/x"},
    )
    sink: list = []
    notes: list = []
    res = asyncio.run(d.deliver_android_paid(
        transaction_id="tx-ok", android_user_id=42, email="a@b.io", days=30,
        tariff_slug="sid:S1:esid:E1",
        session_factory=_make_session_factory(sink),
        notifier=lambda t: _append(notes, t),
    ))
    assert res["status"] == "success"
    assert res["uuid"] == "rw-uuid"
    assert res["subscription_url"] == "https://sub/x"
    # delivery_status update + vless_uuid save both ran against the session.
    assert any(p and p.get("t") == "tx-ok" for p in sink)
    assert any(p and p.get("u") == "rw-uuid" for p in sink)
    assert notes and "delivered" in notes[-1]


def test_squad_resolver_used_for_plain_slug(monkeypatch):
    _patch_remnawave(
        monkeypatch,
        scenario=SubscriptionScenario.NEW_USER,
        info=None,
        apply_result={"uuid": "u", "subscription_url": "s"},
    )

    async def resolver(slug):
        assert slug == "webapp-tariff"
        return {"squad_id": "S9", "external_squad_id": "E9"}

    res = asyncio.run(d.deliver_android_paid(
        transaction_id="tx2", android_user_id=7, email="a@b.io", days=30,
        tariff_slug="webapp-tariff",
        session_factory=_make_session_factory([]),
        notifier=lambda t: _noop(),
        squad_resolver=resolver,
    ))
    assert res["status"] == "success"


def test_existing_user_receives_full_target_without_overwriting_blank_description(
    monkeypatch,
):
    captured = {}

    async def fake_get_user_from_username(_username):
        return {"uuid": "rw-existing", "expire": None}

    async def fake_apply_extend(**values):
        captured.update(values)
        return {"uuid": "rw-existing", "subscription_url": "https://sub/existing"}

    monkeypatch.setattr(d.rem, "get_user_from_username", fake_get_user_from_username)
    monkeypatch.setattr(
        d,
        "resolve_scenario",
        lambda *_a, **_k: SubscriptionScenario.EXTEND,
    )
    monkeypatch.setattr(d, "apply_extend", fake_apply_extend)

    result = asyncio.run(
        d.deliver_android_paid(
            transaction_id="tx-target",
            android_user_id=8,
            email="a@b.io",
            days=30,
            tariff_slug="sid:S1:esid:E1",
            delivery_target={
                "internal_squad_ids": ["S1", "S2"],
                "external_squad_id": "E1",
                "traffic_limit_bytes": 25 * 1024**3,
                "traffic_limit_strategy": "MONTH",
                "remnawave_description": None,
                "remnawave_tag": "PAID",
            },
            session_factory=_make_session_factory([]),
            notifier=lambda text: _noop(),
        )
    )
    assert result["status"] == "success"
    assert captured["internal_squad_ids"] == ["S1", "S2"]
    assert captured["traffic_limit_bytes"] == 25 * 1024**3
    assert captured["traffic_limit_strategy"] == "MONTH"
    assert captured["description"] is None
    assert captured["tag"] == "PAID"


# --- tiny async helpers for the notifier callback ---------------------------
async def _append(target, text):
    target.append(text)


async def _noop():
    return None
