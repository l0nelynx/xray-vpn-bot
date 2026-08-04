"""Tests for Remnawave client user normalization."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from remnawave_client.client import (
    RemnawaveClient,
    RemnawaveOperationError,
    _extract_rw_id,
    _normalize_user,
)


def test_extract_rw_id_from_dto() -> None:
    user = SimpleNamespace(id=12345)
    assert _extract_rw_id(user) == 12345


def test_extract_rw_id_from_dict() -> None:
    assert _extract_rw_id({"id": 99}) == 99
    assert _extract_rw_id({"id": None}) is None
    assert _extract_rw_id({}) is None


def test_normalize_user_includes_rw_id() -> None:
    import datetime

    user = SimpleNamespace(
        id=777,
        expire_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        subscription_url="https://example.com/sub",
        status=SimpleNamespace(value="ACTIVE"),
        traffic_limit_bytes=0,
        used_traffic_bytes=0,
        active_internal_squads=None,
        email="u@example.com",
        telegram_id=123,
        username="user01_42",
        description="provisioning:tx-1",
        tag="PAID",
    )
    normalized = _normalize_user(user)
    assert "uuid" not in normalized
    assert normalized["rw_id"] == 777
    assert normalized["username"] == "user01_42"
    assert normalized["description"] == "provisioning:tx-1"
    assert normalized["tag"] == "PAID"


def test_strict_lookup_preserves_transient_error() -> None:
    class Users:
        async def get_user_by_id(self, _rw_id):
            raise httpx.ReadTimeout("panel unavailable")

    client = RemnawaveClient("https://panel.invalid", "token")
    client._sdk = SimpleNamespace(users=Users())

    with pytest.raises(RemnawaveOperationError) as exc_info:
        asyncio.run(client.get_user_by_id(42, raise_on_error=True))

    assert exc_info.value.retryable is True
    assert "ReadTimeout" in str(exc_info.value)


def test_strict_lookup_keeps_real_404_as_not_found() -> None:
    request = httpx.Request("GET", "https://panel.invalid/api/users/42")
    response = httpx.Response(404, request=request)

    class Users:
        async def get_user_by_id(self, _rw_id):
            raise httpx.HTTPStatusError(
                "not found", request=request, response=response,
            )

    client = RemnawaveClient("https://panel.invalid", "token")
    client._sdk = SimpleNamespace(users=Users())

    assert asyncio.run(
        client.get_user_by_id(42, raise_on_error=True)
    ) is None


def test_strict_lookup_keeps_remnawave_sdk_not_found_as_none() -> None:
    """remnawave-api raises NotFoundError with status_code on the exception,
    not on .response — new Telegram users without a panel account hit this
    path from GET /me via username fallback."""
    from remnawave.exceptions import NotFoundError
    from remnawave.exceptions.general import ApiErrorResponse

    class Users:
        async def get_user_by_username(self, _username):
            raise NotFoundError(
                404,
                ApiErrorResponse(
                    message="User with specified params not found",
                    code="A063",
                ),
            )

    client = RemnawaveClient("https://panel.invalid", "token")
    client._sdk = SimpleNamespace(users=Users())

    assert asyncio.run(
        client.get_user_by_username("brand_new_user", raise_on_error=True)
    ) is None
