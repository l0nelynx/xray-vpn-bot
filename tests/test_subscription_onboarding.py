"""Subscription-page registration and initial attachment guarantees."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from common_db.models import PendingSubscriptionOnboarding, User
from common_db.repo import subscription_onboarding, subscriptions


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def test_web_registration_creates_pending_without_subscription(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from miniapp.backend.android import repo as android_repo
    from miniapp.backend.android.schemas import TokenPair
    from miniapp.backend.web import web_router

    monkeypatch.setattr(web_router, "async_session", session_factory)
    monkeypatch.setattr(android_repo, "async_session", session_factory)
    monkeypatch.setattr(
        web_router,
        "User",
        lambda **kwargs: User(id=1001, **kwargs),
    )
    monkeypatch.setattr(
        web_router.android_security, "hash_password", lambda _password: asyncio.sleep(0, result="hash")
    )
    monkeypatch.setattr(web_router.brute_force, "check", lambda _ip: None)
    monkeypatch.setattr(web_router.brute_force, "clear", lambda _ip: None)
    monkeypatch.setattr(web_router.register_ip_guard, "check", lambda _ip: None)
    monkeypatch.setattr(web_router.register_ip_guard, "record", lambda _ip: None)
    monkeypatch.setattr(web_router.email_policy, "assert_email_allowed", lambda _email: None)
    monkeypatch.setattr(
        web_router,
        "_issue_pair",
        lambda *_args, **_kwargs: asyncio.sleep(
            0,
            result=TokenPair(
                access_token="access",
                refresh_token="refresh-token",
                expires_in=900,
            ),
        ),
    )
    monkeypatch.setattr(web_router, "notify_log", lambda *_args, **_kwargs: asyncio.sleep(0))

    async def go() -> None:
        response = await web_router.web_register(
            web_router.WebRegisterRequest(
                email="new@example.com",
                password="correct-horse",
                subscription_flow=True,
            ),
            _request(),
        )
        async with session_factory() as session:
            pending = await session.get(PendingSubscriptionOnboarding, response.user.id)
            assert pending is not None and pending.rw_id is None
            assert await subscriptions.list_for_user(session, response.user.id) == []
            assert (await session.get(User, response.user.id)).rw_id is None

    asyncio.run(go())


def test_email_verification_finalizes_legacy_pending_as_primary(session_factory) -> None:
    async def go() -> None:
        async with session_factory() as session:
            session.add(User(id=1, email="owner@example.com"))
            await session.flush()
            await subscription_onboarding.create(session, user_id=1, rw_id=1031)
            await session.commit()

        async with session_factory() as session:
            result = await subscription_onboarding.finalize_email_verification(
                session, user_id=1
            )
            await session.commit()
            assert result == "attached"
            rows = await subscriptions.list_for_user(session, 1)
            assert len(rows) == 1
            assert rows[0].rw_id == 1031 and rows[0].is_primary is True
            user = await session.get(User, 1)
            assert user is not None and user.email_verified_at is not None
            assert user.rw_id == 1031
            assert await session.get(PendingSubscriptionOnboarding, 1) is None

    asyncio.run(go())


def test_contextless_pending_waits_for_oauth_without_creating_profile(session_factory) -> None:
    async def go() -> None:
        async with session_factory() as session:
            session.add(User(id=1, email="owner@example.com"))
            await session.flush()
            await subscription_onboarding.create(session, user_id=1, rw_id=None)
            await session.commit()

        async with session_factory() as session:
            result = await subscription_onboarding.finalize_email_verification(
                session, user_id=1
            )
            await session.commit()
            assert result == "awaiting_oauth"
            assert await subscriptions.list_for_user(session, 1) == []
            assert await session.get(PendingSubscriptionOnboarding, 1) is not None

    asyncio.run(go())


def test_email_verification_keeps_identity_verified_on_legacy_owner_conflict(
    session_factory,
) -> None:
    async def go() -> None:
        async with session_factory() as session:
            session.add_all(
                [
                    User(id=1, email="new@example.com"),
                    User(id=2, email="existing@example.com"),
                ]
            )
            await session.flush()
            await subscriptions.attach(
                session, user_id=2, rw_id=1031, source="existing"
            )
            await subscription_onboarding.create(session, user_id=1, rw_id=1031)
            await session.commit()

        async with session_factory() as session:
            result = await subscription_onboarding.finalize_email_verification(
                session, user_id=1
            )
            await session.commit()
            assert result == "conflict"
            user = await session.get(User, 1)
            assert user is not None and user.email_verified_at is not None
            assert await subscriptions.list_for_user(session, 1) == []
            assert await session.get(PendingSubscriptionOnboarding, 1) is None

    asyncio.run(go())


def test_email_verify_does_not_provision_free_while_oauth_is_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from miniapp.backend.android import email_router

    async def no_op(*_args, **_kwargs):
        return None

    async def awaiting(_user_id: int) -> str:
        return "awaiting_oauth"

    async def must_not_provision(*_args, **_kwargs):
        raise AssertionError("FREE provisioning must wait for OAuth callback")

    monkeypatch.setattr(email_router, "_consume_code", no_op)
    monkeypatch.setattr(email_router, "_finalize_subscription_onboarding", awaiting)
    monkeypatch.setattr(email_router, "notify_log", no_op)
    monkeypatch.setattr(
        email_router.provisioning,
        "ensure_free_subscription",
        must_not_provision,
    )

    user = SimpleNamespace(
        id=1,
        email="owner@example.com",
        email_verified_at=None,
        rw_id=None,
    )
    result = asyncio.run(
        email_router.email_verify(
            email_router.EmailVerifyConfirmRequest(code="123456"),
            _request(),
            user,
        )
    )
    assert result.subscription_status == "awaiting_oauth"


def test_initial_attach_is_empty_only_and_idempotent(session_factory) -> None:
    async def go() -> None:
        async with session_factory() as session:
            session.add_all([User(id=1), User(id=2), User(id=3)])
            await session.flush()
            await subscriptions.attach(session, user_id=2, rw_id=2002, source="existing")
            await subscriptions.attach(session, user_id=3, rw_id=3003, source="other")
            await session.commit()

        async with session_factory() as session:
            first = await subscription_onboarding.attach_initial(
                session, user_id=1, rw_id=1001
            )
            await session.commit()
            assert first[0] == "attached"

        async with session_factory() as session:
            repeated = await subscription_onboarding.attach_initial(
                session, user_id=1, rw_id=1001
            )
            skipped = await subscription_onboarding.attach_initial(
                session, user_id=2, rw_id=2004
            )
            assert repeated[0] == "already_attached"
            assert skipped[0] == "skipped_nonempty"
            with pytest.raises(ValueError, match="subscription_already_linked"):
                await subscription_onboarding.attach_initial(
                    session, user_id=1, rw_id=3003
                )

    asyncio.run(go())


def test_oauth_requires_verified_email_or_telegram() -> None:
    from miniapp.backend.web import subscription_sso_router as sso

    with pytest.raises(HTTPException) as exc_info:
        sso._require_verified_identity(
            SimpleNamespace(email_verified_at=None, tg_id=None)
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {"code": "email_not_verified"}

    sso._require_verified_identity(
        SimpleNamespace(email_verified_at="2026-08-09T12:00:00+00:00", tg_id=None)
    )
    sso._require_verified_identity(
        SimpleNamespace(email_verified_at=None, tg_id=123456)
    )
