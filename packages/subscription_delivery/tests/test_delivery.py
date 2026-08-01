"""Unit tests for the shared Android delivery, with the Remnawave layer,
DB session and notifier all faked — no network, no real DB.
"""
import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from remnawave_client import RemnawaveOperationError, SubscriptionScenario
import subscription_delivery.delivery as d


@pytest.fixture
def session_factory():
    from common_db import Base
    import common_db.models  # noqa: F401

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    asyncio.run(engine.dispose())


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
    created = False

    async def fake_get_user_from_username(_username, **_kwargs):
        if info is not None:
            return info
        return apply_result if created else None
    monkeypatch.setattr(d.rem, "get_user_from_username", fake_get_user_from_username)
    monkeypatch.setattr(d, "resolve_scenario", lambda *_a, **_k: scenario)

    async def fake_apply_new_user(**_kw):
        nonlocal created
        created = True
        if apply_result is not None:
            apply_result.setdefault("rw_id", 999)
            apply_result.setdefault("username", _kw["username"])
            apply_result.setdefault("description", _kw.get("description"))
        return apply_result
    async def fake_apply_extend(**_kw):
        return apply_result
    async def fake_apply_update(**_kw):
        return apply_result
    monkeypatch.setattr(d, "apply_new_user", fake_apply_new_user)
    monkeypatch.setattr(d, "apply_extend", fake_apply_extend)
    monkeypatch.setattr(d, "apply_update", fake_apply_update)


def _patch_db(monkeypatch, *, user_id=1, owner=None, action="created"):
    async def local(_factory, requested_user_id):
        return {
            "id": requested_user_id,
            "tg_id": None,
            "username": None,
            "email": None,
            "rw_id": None,
            "vless_uuid": None,
            "subscription_count": 0,
        }

    async def get_owner(_factory, _rw_id):
        return owner

    async def attach(*_args, **_kwargs):
        return action, 1

    async def update(*_args, **_kwargs):
        return None

    monkeypatch.setattr(d, "_local_context", local)
    monkeypatch.setattr(d, "_subscription_owner", get_owner)
    monkeypatch.setattr(d, "_attach_subscription", attach)
    monkeypatch.setattr(d, "_update_delivery_status", update)


def test_email_to_username_and_slug_parsing():
    assert d.email_to_username("Foo.Bar@Mail.io") == "foo_bar_at_mail_io"
    assert d._parse_squad_slug("sid:S1:esid:E1") == {"squad_id": "S1", "external_squad_id": "E1"}
    assert d._parse_squad_slug("plain-slug") is None


def test_missing_telegram_username_uses_user_base():
    assert d.build_remnawave_username(None, 1842) == "user_1842"
    assert d.build_remnawave_username(None, 1842, 1) == "user_1842_1"


def test_existing_target_can_be_extended_without_local_email(monkeypatch):
    captured = {}
    _patch_db(monkeypatch, user_id=12, action="existing")

    async def get_by_id(rw_id, **_kwargs):
        assert rw_id == 777
        return {"uuid": "target-uuid", "rw_id": 777, "username": "marketplace_user", "expire": None}

    async def extend(**values):
        captured.update(values)
        return {"uuid": "target-uuid", "subscription_url": "https://sub/target"}

    monkeypatch.setattr(d.rem, "get_user_from_id", get_by_id)
    monkeypatch.setattr(d, "resolve_scenario", lambda *_: SubscriptionScenario.EXTEND)
    monkeypatch.setattr(d, "apply_extend", extend)

    result = asyncio.run(
        d.deliver_android_paid(
            transaction_id="tx-no-email",
            android_user_id=12,
            email=None,
            days=30,
            tariff_slug="sid:S1:esid:E1",
            target_rw_id=777,
            session_factory=_make_session_factory([]),
            notifier=lambda text: _noop(),
        )
    )

    assert result["status"] == "success"
    assert captured["username"] == "marketplace_user"


def test_bad_slug_without_resolver_returns_error(monkeypatch):
    _patch_db(monkeypatch)
    res = asyncio.run(d.deliver_android_paid(
        transaction_id="tx1", android_user_id=1, email="a@b.io", days=30,
        tariff_slug="plain-slug",  # not sid:..:esid:.. and no resolver
        session_factory=_make_session_factory([]),
        notifier=lambda t: _noop(),
    ))
    assert res["status"] == "pending"
    assert "bad tariff_slug" in res["message"]


def test_new_user_success_updates_delivery_and_notifies(monkeypatch):
    _patch_db(monkeypatch, user_id=42)
    _patch_remnawave(
        monkeypatch,
        scenario=SubscriptionScenario.NEW_USER,
        info=None,
        apply_result={"uuid": "rw-uuid", "rw_id": 999, "subscription_url": "https://sub/x"},
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
    assert notes and "delivered" in notes[-1]
    assert "Subscription delivered (android)" in notes[-1]


def test_squad_resolver_used_for_plain_slug(monkeypatch):
    _patch_db(monkeypatch, user_id=7)
    _patch_remnawave(
        monkeypatch,
        scenario=SubscriptionScenario.NEW_USER,
        info=None,
        apply_result={"uuid": "u", "rw_id": 999, "subscription_url": "s"},
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
    _patch_db(monkeypatch, user_id=8, action="existing")

    async def fake_get_user_from_id(_rw_id, **_kwargs):
        return {"uuid": "rw-existing", "rw_id": 888, "username": "user_8", "expire": None}

    async def fake_apply_extend(**values):
        captured.update(values)
        return {"uuid": "rw-existing", "subscription_url": "https://sub/existing"}

    monkeypatch.setattr(d.rem, "get_user_from_id", fake_get_user_from_id)
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
                target_rw_id=888,
            session_factory=_make_session_factory([]),
            notifier=lambda text: _noop(),
        )
    )
    assert result["status"] == "success"
    assert captured["internal_squad_ids"] == ["S1", "S2"]
    assert captured["traffic_limit_bytes"] == 25 * 1024**3
    assert captured["traffic_limit_strategy"] == "MONTH"
    assert captured["description"] == "delivery:tx-target"
    assert captured["tag"] == "PAID"


def test_username_policy_sanitizes_suffixes_and_truncates_only_display_part():
    assert d.build_remnawave_username("User.01!", 42) == "user01_42"
    assert d.build_remnawave_username("User.01!", 42, 1) == "user01_42_1"
    assert d.build_remnawave_username("User.01!", 42, 2) == "user01_42_2"
    long_name = d.build_remnawave_username("A" * 80, 123456789, 12)
    assert len(long_name) == 36
    assert long_name.endswith("_123456789_12")


def test_target_owned_by_another_user_is_pending_without_rw_mutation(monkeypatch):
    _patch_db(monkeypatch, user_id=42, owner=77)
    called = False

    async def get_by_id(_rw_id, **_kwargs):
        nonlocal called
        called = True
        return {"uuid": "foreign", "rw_id": 900}

    monkeypatch.setattr(d.rem, "get_user_from_id", get_by_id)
    result = asyncio.run(d.deliver_android_paid(
        transaction_id="tx-conflict", android_user_id=42, email=None, days=30,
        tariff_slug="sid:S1:esid:E1", target_rw_id=900,
        session_factory=_make_session_factory([]), notifier=lambda t: _noop(),
    ))
    assert result == {"status": "pending", "message": "target_owner_conflict"}
    assert called is False


def test_foreign_candidate_advances_to_next_subscription_number(monkeypatch):
    _patch_db(monkeypatch, user_id=42)
    created = None

    async def lookup(username, **_kwargs):
        nonlocal created
        if username == "user01_42":
            return {"uuid": "foreign", "rw_id": 1, "description": "other"}
        return created

    async def create(**values):
        nonlocal created
        created = {
            "uuid": "ours", "rw_id": 2, "username": values["username"],
            "description": values["description"], "subscription_url": "s",
        }
        return created

    monkeypatch.setattr(d.rem, "get_user_from_username", lookup)
    monkeypatch.setattr(d, "apply_new_user", create)
    result = asyncio.run(d.deliver_android_paid(
        transaction_id="tx-next", android_user_id=42, email=None, days=30,
        tariff_slug="sid:S1:esid:E1", session_factory=_make_session_factory([]),
        notifier=lambda text: _noop(), tg_username="User01",
    ))
    assert result["status"] == "success"
    assert result["username"] == "user01_42_1"


def test_create_error_recovers_same_marker_without_second_create(monkeypatch):
    _patch_db(monkeypatch, user_id=42, action="recovered")
    calls = 0
    appeared = False

    async def lookup(username, **_kwargs):
        if not appeared:
            return None
        return {
            "uuid": "ours", "rw_id": 5, "username": username,
            "description": "provisioning:tx-retry; db_user_id:42",
            "subscription_url": "s",
        }

    async def create(**_values):
        nonlocal calls, appeared
        calls += 1
        appeared = True
        raise TimeoutError("response lost")

    monkeypatch.setattr(d.rem, "get_user_from_username", lookup)
    monkeypatch.setattr(d, "apply_new_user", create)
    result = asyncio.run(d.deliver_android_paid(
        transaction_id="tx-retry", android_user_id=42, email=None, days=30,
        tariff_slug="sid:S1:esid:E1", session_factory=_make_session_factory([]),
        notifier=lambda text: _noop(), tg_username="User01",
    ))
    assert result["status"] == "success"
    assert result["action"] == "recovered"
    assert calls == 1


def test_target_lookup_outage_is_retryable_and_never_creates(monkeypatch):
    _patch_db(monkeypatch, user_id=42)
    create_called = False

    async def unavailable(_rw_id, **_kwargs):
        raise RemnawaveOperationError(
            "get_user_by_id", httpx.ReadTimeout("panel unavailable"),
        )

    async def forbidden_create(**_kwargs):
        nonlocal create_called
        create_called = True
        raise AssertionError("read outage must not be treated as missing user")

    monkeypatch.setattr(d.rem, "get_user_from_id", unavailable)
    monkeypatch.setattr(d, "apply_new_user", forbidden_create)

    result = asyncio.run(d.deliver_android_paid(
        transaction_id="tx-outage", android_user_id=42, email=None, days=30,
        tariff_slug="sid:S1:esid:E1", target_rw_id=901,
        session_factory=_make_session_factory([]),
        notifier=lambda text: _noop(), purchase_source="miniapp",
    ))

    assert result["status"] == "pending"
    assert result["retryable"] is True
    assert "ReadTimeout" in result["message"]
    assert create_called is False


def test_lost_extend_response_recovers_marker_without_double_extension(
    monkeypatch,
):
    _patch_db(monkeypatch, user_id=42, action="existing")
    state = {
        "uuid": "existing-uuid", "rw_id": 901, "username": "user01_42",
        "expire": None, "description": "old description",
        "subscription_url": "https://sub/existing",
    }
    update_calls = 0

    async def get_by_id(_rw_id, **_kwargs):
        return dict(state)

    async def extend(**values):
        nonlocal update_calls
        update_calls += 1
        state["description"] = values["description"]
        raise RemnawaveOperationError(
            "update_user", httpx.ReadTimeout("response lost"),
        )

    monkeypatch.setattr(d.rem, "get_user_from_id", get_by_id)
    monkeypatch.setattr(d, "resolve_scenario", lambda *_: SubscriptionScenario.EXTEND)
    monkeypatch.setattr(d, "apply_extend", extend)

    async def deliver():
        return await d.deliver_android_paid(
            transaction_id="tx-marker", android_user_id=42, email=None,
            days=30, tariff_slug="sid:S1:esid:E1", target_rw_id=901,
            session_factory=_make_session_factory([]),
            notifier=lambda text: _noop(), purchase_source="miniapp",
        )

    first = asyncio.run(deliver())
    second = asyncio.run(deliver())

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert state["description"].startswith("delivery:tx-marker")
    assert update_calls == 1


def test_allocation_stops_after_one_hundred_foreign_candidates(monkeypatch):
    _patch_db(monkeypatch, user_id=42)
    checked: list[str] = []

    async def occupied(username, **_kwargs):
        checked.append(username)
        return {"uuid": f"foreign-{username}", "rw_id": len(checked), "description": "other"}

    monkeypatch.setattr(d.rem, "get_user_from_username", occupied)
    result = asyncio.run(d.deliver_android_paid(
        transaction_id="tx-full", android_user_id=42, email=None, days=30,
        tariff_slug="sid:S1:esid:E1", session_factory=_make_session_factory([]),
        notifier=lambda text: _noop(), tg_username="User01",
    ))
    assert result == {"status": "pending", "message": "rw_username_allocation_failed"}
    assert len(checked) == 100


# --- tiny async helpers for the notifier callback ---------------------------
async def _append(target, text):
    target.append(text)


async def _noop():
    return None


async def _seed_purchase(session_factory, *, user_id=42, target_rw_id=None):
    from common_db.models import Transaction, User

    async with session_factory() as session:
        session.add(User(id=user_id, tg_id=4200 + user_id, username="User01"))
        session.add(Transaction(
            transaction_id=f"tx-{user_id}", vless_uuid="None",
            username="User01", order_status="confirmed", delivery_status=0,
            days_ordered=30, user_id=user_id, target_rw_id=target_rw_id,
            purchase_source="miniapp",
        ))
        await session.commit()


def test_successful_retry_restores_confirmed_status_and_clears_error(
    session_factory,
):
    from common_db.models import Transaction

    async def run():
        await _seed_purchase(session_factory)
        async with session_factory() as session:
            await session.execute(d.text(
                "UPDATE transactions SET order_status = 'pending', "
                "delivery_error = 'temporary outage' WHERE transaction_id = 'tx-42'"
            ))
            await session.commit()

        await d._update_delivery_status(session_factory, "tx-42", 1)

        async with session_factory() as session:
            tx = await session.get(Transaction, "tx-42")
            return tx.order_status, tx.delivery_status, tx.delivery_error

    assert asyncio.run(run()) == ("confirmed", 1, None)


def test_real_db_target_owner_conflict_becomes_pending(
    monkeypatch, session_factory,
):
    from common_db.models import Transaction, User, UserSubscription

    async def run():
        await _seed_purchase(session_factory, target_rw_id=900)
        async with session_factory() as session:
            session.add(User(id=77, tg_id=7777, username="Other"))
            session.add(UserSubscription(
                user_id=77, rw_id=900, source="test", is_primary=True,
                created_at="2026-01-01", updated_at="2026-01-01",
            ))
            await session.commit()

        async def forbidden(_rw_id, **_kwargs):
            raise AssertionError("foreign Remnawave profile must not be read or changed")

        monkeypatch.setattr(d.rem, "get_user_from_id", forbidden)
        result = await d.deliver_android_paid(
            transaction_id="tx-42", android_user_id=42, email=None, days=30,
            tariff_slug="sid:S1:esid:E1", target_rw_id=900,
            session_factory=session_factory, notifier=lambda text: _noop(),
            purchase_source="miniapp",
        )
        async with session_factory() as session:
            tx = await session.get(Transaction, "tx-42")
            return result, tx.order_status, tx.delivery_status, tx.delivery_error

    result, order_status, delivery_status, error = asyncio.run(run())
    assert result == {"status": "pending", "message": "target_owner_conflict"}
    assert (order_status, delivery_status, error) == (
        "pending", 0, "target_owner_conflict",
    )


@pytest.mark.parametrize("legacy_projection", [False, True])
def test_real_db_unowned_external_target_is_recovered(
    monkeypatch, session_factory, legacy_projection,
):
    from common_db.models import Transaction, User, UserSubscription

    async def get_by_id(rw_id, **_kwargs):
        assert rw_id == 901
        return {
            "uuid": "external-uuid", "rw_id": 901, "username": "legacy_profile",
            "expire": None, "status": "active", "data_limit": None,
        }

    async def extend(**_values):
        return {"uuid": "external-uuid", "subscription_url": "https://sub/recovered"}

    monkeypatch.setattr(d.rem, "get_user_from_id", get_by_id)
    monkeypatch.setattr(d, "resolve_scenario", lambda *_: SubscriptionScenario.EXTEND)
    monkeypatch.setattr(d, "apply_extend", extend)

    async def run():
        await _seed_purchase(session_factory, target_rw_id=901)
        if legacy_projection:
            async with session_factory() as session:
                await session.execute(
                    d.text("UPDATE users SET rw_id = 901 WHERE id = 42")
                )
                await session.commit()
        result = await d.deliver_android_paid(
            transaction_id="tx-42", android_user_id=42, email=None, days=30,
            tariff_slug="sid:S1:esid:E1", target_rw_id=901,
            session_factory=session_factory, notifier=lambda text: _noop(),
            purchase_source="miniapp",
        )
        async with session_factory() as session:
            tx = await session.get(Transaction, "tx-42")
            user = await session.get(User, 42)
            link = await session.scalar(
                d.text("SELECT id FROM user_subscriptions WHERE user_id = 42 AND rw_id = 901")
            )
            return result, tx, user, link

    result, tx, user, link = asyncio.run(run())
    assert result["action"] == "recovered"
    assert link is not None
    assert tx.delivery_status == 1 and tx.delivery_error is None
    assert user.rw_id == 901 and user.vless_uuid == "external-uuid"


@pytest.mark.parametrize("original_target", [None, 902])
def test_real_db_null_or_missing_target_creates_and_replaces_target(
    monkeypatch, session_factory, original_target,
):
    from common_db.models import Transaction, UserSubscription

    created: dict = {}

    async def get_by_id(rw_id, **_kwargs):
        assert rw_id == 902
        return None

    async def get_by_username(username, **_kwargs):
        return created.get(username)

    async def create(**values):
        created[values["username"]] = {
            "uuid": "new-uuid", "rw_id": 903, "username": values["username"],
            "description": values["description"], "subscription_url": "https://sub/new",
            "status": "active", "data_limit": None,
        }
        return created[values["username"]]

    monkeypatch.setattr(d.rem, "get_user_from_id", get_by_id)
    monkeypatch.setattr(d.rem, "get_user_from_username", get_by_username)
    monkeypatch.setattr(d, "apply_new_user", create)

    async def run():
        await _seed_purchase(session_factory, target_rw_id=original_target)
        result = await d.deliver_android_paid(
            transaction_id="tx-42", android_user_id=42, email=None, days=30,
            tariff_slug="sid:S1:esid:E1", target_rw_id=original_target,
            session_factory=session_factory, notifier=lambda text: _noop(),
            purchase_source="miniapp",
        )
        async with session_factory() as session:
            tx = await session.get(Transaction, "tx-42")
            link = await session.scalar(
                d.text("SELECT rw_id FROM user_subscriptions WHERE user_id = 42")
            )
            return result, tx.target_rw_id, link

    result, target, link = asyncio.run(run())
    assert result["status"] == "success" and result["action"] == "created"
    assert result["username"] == "user01_42"
    assert target == 903 and link == 903
    assert "provisioning:tx-42" in created["user01_42"]["description"]
