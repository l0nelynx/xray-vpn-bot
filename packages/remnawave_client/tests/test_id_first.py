"""ID-first Remnawave adapter behavior."""
from __future__ import annotations

import datetime
import importlib.metadata
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from remnawave_client import api
from remnawave_client.client import RemnawaveClient, RemnawaveOperationError


def _dto(*, rw_id: int = 42, email: str = "user@example.com"):
    return SimpleNamespace(
        id=rw_id,
        expire_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        subscription_url="https://example.com/sub/secret",
        status=SimpleNamespace(value="ACTIVE"),
        traffic_limit_bytes=0,
        used_traffic_bytes=0,
        active_internal_squads=None,
        email=email,
        telegram_id=None,
    )


def test_get_user_by_id_uses_sdk_numeric_id_endpoint() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(get_user_by_id=AsyncMock(return_value=_dto()))
        client._sdk = SimpleNamespace(users=users)

        result = await client.get_user_by_id(42)

        users.get_user_by_id.assert_awaited_once_with(42)
        assert result is not None and result["rw_id"] == 42

    asyncio.run(go())


def test_email_lookup_walks_all_cursor_pages_and_matches_exactly() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(get_users_stream=AsyncMock(side_effect=[
            SimpleNamespace(
                users=[_dto(rw_id=1, email="not-user@example.com")],
                has_more=True, next_cursor=101,
            ),
            SimpleNamespace(
                users=[_dto(rw_id=2, email="  USER@EXAMPLE.COM ")],
                has_more=False, next_cursor=None,
            ),
        ]))
        client._sdk = SimpleNamespace(users=users)

        result = await client.get_user_by_email(" user@example.com ")

        assert result is not None and result["rw_id"] == 2
        assert users.get_users_stream.await_count == 2
        assert users.get_users_stream.await_args_list[1].kwargs["cursor"] == 101

    asyncio.run(go())


def test_email_lookup_zero_and_multiple_results_are_distinct() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(get_users_stream=AsyncMock(return_value=SimpleNamespace(
            users=[], has_more=False, next_cursor=None,
        )))
        client._sdk = SimpleNamespace(users=users)
        assert await client.get_user_by_email("missing@example.com") is None

        users.get_users_stream.return_value = SimpleNamespace(
            users=[
                _dto(rw_id=1, email="same@example.com"),
                _dto(rw_id=2, email="SAME@example.com"),
            ],
            has_more=False,
            next_cursor=None,
        )
        with pytest.raises(RemnawaveOperationError) as exc_info:
            await client.get_user_by_email("same@example.com")
        assert exc_info.value.operation == "get_user_by_email_conflict"

    asyncio.run(go())


def test_email_lookup_outage_is_not_converted_to_not_found() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(
            get_users_stream=AsyncMock(side_effect=TimeoutError("panel down"))
        )
        client._sdk = SimpleNamespace(users=users)

        with pytest.raises(RemnawaveOperationError) as exc_info:
            await client.get_user_by_email("user@example.com")
        assert exc_info.value.operation == "get_user_by_email"

    asyncio.run(go())


def test_update_by_id_calls_numeric_sdk_endpoint_directly() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(update_user=AsyncMock(return_value=_dto(rw_id=77)))
        client._sdk = SimpleNamespace(users=users)

        result = await client.update_user_by_id(77, days=30)

        request = users.update_user.await_args.args[0]
        assert request.id == 77
        assert "status" not in request.model_fields_set
        assert result is not None and result["rw_id"] == 77

    asyncio.run(go())


def test_create_user_omits_absent_email_from_v3_dto() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(create_user=AsyncMock(return_value=_dto()))
        client._sdk = SimpleNamespace(users=users)

        result = await client.create_user(
            "smoke_test", days=1, raise_on_error=True
        )

        request = users.create_user.await_args.args[0]
        assert request.email is None
        assert "email" not in request.model_fields_set
        assert result is not None and result["rw_id"] == 42

    asyncio.run(go())


def test_create_user_preserves_explicit_valid_email() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(create_user=AsyncMock(return_value=_dto()))
        client._sdk = SimpleNamespace(users=users)

        await client.create_user(
            "telegram_user",
            email="telegram_user@telegram.user",
            raise_on_error=True,
        )

        request = users.create_user.await_args.args[0]
        assert request.email == "telegram_user@telegram.user"
        assert "email" in request.model_fields_set

    asyncio.run(go())


def test_resolver_does_not_fall_through_after_numeric_lookup_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    by_id = AsyncMock(side_effect=RemnawaveOperationError(
        "get_user_by_id", httpx.ReadTimeout("panel down")
    ))
    by_email = AsyncMock()
    by_username = AsyncMock()
    monkeypatch.setattr(api, "get_user_from_id", by_id)
    monkeypatch.setattr(api, "get_user_from_email", by_email)
    monkeypatch.setattr(api, "get_user_from_username", by_username)

    with pytest.raises(RemnawaveOperationError):
        asyncio.run(api._resolve_remnawave_user_uncached(
            rw_id=77,
            email="user@example.com",
            username="user",
            expected_telegram_id=42,
        ))

    by_id.assert_awaited_once_with(77, strict=True)
    by_email.assert_not_awaited()
    by_username.assert_not_awaited()


def test_short_uuid_lookup_distinguishes_not_found_from_outage() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        request = httpx.Request("GET", "https://panel.example/api/users/by-short-uuid/x")
        not_found = httpx.HTTPStatusError(
            "missing", request=request, response=httpx.Response(404, request=request)
        )
        users = SimpleNamespace(
            get_user_by_short_uuid=AsyncMock(side_effect=not_found)
        )
        client._sdk = SimpleNamespace(users=users)
        assert await client.get_user_by_short_uuid_raw(
            "missing", raise_on_error=True
        ) is None

        users.get_user_by_short_uuid.side_effect = httpx.ReadTimeout(
            "panel down", request=request
        )
        with pytest.raises(RemnawaveOperationError) as exc_info:
            await client.get_user_by_short_uuid_raw("x", raise_on_error=True)
        assert exc_info.value.operation == "get_user_by_short_uuid"

    asyncio.run(go())


def test_only_supported_remnawave_distribution_is_installed() -> None:
    assert importlib.metadata.version("remnawave-api") == "3.0.1"
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        importlib.metadata.version("remnawave")
