"""Exercise the real SDK serializer/controllers against a v3 HTTP contract.

Mock only the network: replacing controllers with AsyncMock cannot detect SDK
changes to URL parameters, JSON aliases, response envelopes, or exception types.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from remnawave import RemnawaveSDK

from remnawave_client.client import RemnawaveClient, RemnawaveOperationError

SQUAD = "11111111-2222-4333-8444-555555555555"


def user_payload(**overrides):
    return {
        "id": 42, "shortUuid": "test-short", "username": "test_user",
        "expireAt": "2027-01-01T00:00:00Z", "status": "ACTIVE",
        "trafficLimitBytes": 10 * 1024**3, "trafficLimitStrategy": "MONTH",
        "telegramId": 123, "email": "user@example.com", "tag": "PAID",
        "trojanPassword": "test-password", "vlessUuid": SQUAD,
        "ssPassword": "test-password", "description": "payment:test",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "subscriptionUrl": "https://subscription.invalid/test-short",
        "activeInternalSquads": [{"uuid": SQUAD, "name": "Paid"}],
        "userTraffic": {
            "usedTrafficBytes": 2 * 1024**3, "lifetimeUsedTrafficBytes": 3 * 1024**3,
            "firstConnectedAt": "2026-01-02T00:00:00Z",
        },
        **overrides,
    }


@asynccontextmanager
async def real_client(handler):
    async with httpx.AsyncClient(
        base_url="https://panel.invalid/api/",
        transport=httpx.MockTransport(handler),
    ) as http:
        client = RemnawaveClient("https://panel.invalid", "test-token")
        client._sdk = RemnawaveSDK(client=http)
        yield client


def test_sdk_reads_numeric_id_and_unwraps_nested_traffic():
    def handler(request):
        assert request.method == "GET" and request.url.path == "/api/users/42"
        return httpx.Response(200, json={"response": user_payload()})

    async def run():
        async with real_client(handler) as client:
            result = await client.get_user_by_id(42, raise_on_error=True)
            assert result["rw_id"] == 42
            assert result["traffic_used"] == 2
            assert result["data_limit"] == 10
            assert result["active_squads"] == [SQUAD]
            assert result["first_connected_at"].startswith("2026-01-02")

    asyncio.run(run())


def test_sdk_stream_serializes_filters_and_walks_cursor_pages():
    calls = []

    def handler(request):
        assert request.url.path == "/api/users/stream"
        assert request.url.params["size"] == "500"
        assert request.url.params["email"] == "USER@example.com"
        calls.append(dict(request.url.params))
        more = len(calls) == 1
        assert ("cursor" not in request.url.params) if more else request.url.params["cursor"] == "42"
        return httpx.Response(200, json={"response": {
            "users": [user_payload(email="other@example.com" if more else "user@example.com")],
            "hasMore": more, "nextCursor": 42 if more else None,
        }})

    async def run():
        async with real_client(handler) as client:
            result = await client.get_user_by_email(" USER@example.com ")
            assert result["rw_id"] == 42 and len(calls) == 2

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["create", "update"])
def test_sdk_writes_camel_case_body_and_preserves_numeric_id(operation):
    def handler(request):
        assert request.url.path == "/api/users"
        assert request.method == ("POST" if operation == "create" else "PATCH")
        body = json.loads(request.content)
        assert isinstance(body, dict)  # rapid-api-client must not double-encode JSON
        assert body["trafficLimitBytes"] == 10 * 1024**3
        assert body["trafficLimitStrategy"] == "MONTH"
        assert body["activeInternalSquads"] == [SQUAD]
        assert body["externalSquadUuid"] == SQUAD
        assert body["email"] == "user@example.com"
        assert "active_internal_squads" not in body
        if operation == "update":
            assert body["id"] == 42
        else:
            assert body["username"] == "test_user" and "expireAt" in body
        return httpx.Response(200, json={"response": user_payload()})

    async def run():
        async with real_client(handler) as client:
            kwargs = dict(limit_gb=10, email="user@example.com", internal_squad_ids=[SQUAD],
                          external_squad_id=SQUAD, raise_on_error=True)
            result = (
                await client.create_user("test_user", **kwargs) if operation == "create"
                else await client.update_user_by_id(42, **kwargs)
            )
            assert result["rw_id"] == 42

    asyncio.run(run())


def test_sdk_hwid_delete_and_no_content_user_delete():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/users/42":
            assert request.method == "DELETE"
            return httpx.Response(204)
        assert request.url.path == "/api/hwid/devices/delete"
        assert json.loads(request.content) == {"userId": 42, "hwid": "test-hwid"}
        return httpx.Response(200, json={"response": {"total": 0, "devices": []}})

    async def run():
        async with real_client(handler) as client:
            result = await client.delete_user_hwid_device_by_id(42, "test-hwid")
            assert result is not None and result.total == 0
            assert await client.delete_user_by_id(42) is True
            assert len(calls) == 2

    asyncio.run(run())


@pytest.mark.parametrize("status", [404, 503])
def test_sdk_distinguishes_missing_user_from_panel_outage(status):
    def handler(request):
        return httpx.Response(status, json={"message": "panel error", "code": "A063"})

    async def run():
        async with real_client(handler) as client:
            if status == 404:
                assert await client.get_user_by_id(42, raise_on_error=True) is None
            else:
                with pytest.raises(RemnawaveOperationError) as error:
                    await client.get_user_by_id(42, raise_on_error=True)
                assert error.value.status_code == 503 and error.value.retryable

    asyncio.run(run())
