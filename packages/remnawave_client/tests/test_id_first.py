"""ID-first Remnawave adapter behavior."""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from remnawave_client.client import RemnawaveClient


def _dto(*, rw_id: int = 42, uuid: str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"):
    return SimpleNamespace(
        id=rw_id,
        uuid=uuid,
        expire_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        subscription_url="https://example.com/sub/secret",
        status=SimpleNamespace(value="ACTIVE"),
        traffic_limit_bytes=0,
        used_traffic_bytes=0,
        active_internal_squads=None,
        email="user@example.com",
        telegram_id=None,
    )


def test_get_user_by_id_uses_sdk_numeric_id_endpoint() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        users = SimpleNamespace(get_user_by_id=AsyncMock(return_value=_dto()))
        client._sdk = SimpleNamespace(users=users)

        result = await client.get_user_by_id(42)

        users.get_user_by_id.assert_awaited_once_with("42")
        assert result is not None and result["rw_id"] == 42

    asyncio.run(go())


def test_update_by_id_resolves_uuid_only_inside_adapter() -> None:
    import asyncio

    async def go() -> None:
        client = RemnawaveClient("https://panel.example", "token")
        client.get_user_by_id = AsyncMock(return_value={"uuid": "panel-user-uuid"})
        client.update_user = AsyncMock(return_value={"rw_id": 77})

        result = await client.update_user_by_id(77, days=30)

        client.get_user_by_id.assert_awaited_once_with(77)
        client.update_user.assert_awaited_once_with("panel-user-uuid", days=30)
        assert result == {"rw_id": 77}

    asyncio.run(go())
