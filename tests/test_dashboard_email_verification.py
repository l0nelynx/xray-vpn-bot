import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from common_db.models import User
from dashboard.backend.routers import users


def test_manual_email_verification_tracks_the_saved_address(session_factory, monkeypatch):
    monkeypatch.setattr(users, "async_session", session_factory)
    panel = AsyncMock()
    panel.get_user_by_email.return_value = None
    monkeypatch.setattr("remnawave_client.configure", lambda **kwargs: panel)
    address = "first@example.com"

    async def check():
        async with session_factory() as session:
            session.add(User(id=1, email=address))
            await session.commit()

        request = users.UpdateEmailVerificationRequest(email=address, verified=True)
        assert await users.update_email_verification(1, request) == {"email_verified": True}
        assert (await users.get_user(1))["email_verified"] is True
        panel.get_user_by_email.assert_not_called()

        # A retry must preserve the original verification time.
        async with session_factory() as session:
            user = await session.get(User, 1)
            assert user.email_verified_at
            user.email_verified_at = "2020-01-01T00:00:00+00:00"
            await session.commit()
        await users.update_email_verification(1, request)
        await users.update_email(1, users.UpdateEmailRequest(email=address.upper()))
        async with session_factory() as session:
            assert (await session.get(User, 1)).email_verified_at == "2020-01-01T00:00:00+00:00"

        await users.update_email_verification(
            1, users.UpdateEmailVerificationRequest(email=address, verified=False)
        )
        assert (await users.get_user(1))["email_verified"] is False
        await users.update_email_verification(1, request)
        await users.update_email(1, users.UpdateEmailRequest(email="second@example.com"))
        with pytest.raises(HTTPException) as stale:
            await users.update_email_verification(1, request)
        assert stale.value.status_code == 409
        assert (await users.get_user(1))["email_verified"] is False

    asyncio.run(check())


def test_verification_requires_a_user_with_an_email(session_factory, monkeypatch):
    monkeypatch.setattr(users, "async_session", session_factory)

    async def check():
        async with session_factory() as session:
            session.add(User(id=1))
            await session.commit()
        request = users.UpdateEmailVerificationRequest(email="absent@example.com", verified=True)
        for user_id, expected_status in [(1, 409), (2, 404)]:
            with pytest.raises(HTTPException) as error:
                await users.update_email_verification(user_id, request)
            assert error.value.status_code == expected_status
        assert (await users.get_user(1))["email_verified"] is False

    asyncio.run(check())
