from __future__ import annotations

import asyncio

from remnawave_client.operations import apply_extend, apply_new_user


class FakeClient:
    def __init__(self) -> None:
        self.created: dict | None = None
        self.updated: dict | None = None

    async def create_user(self, **values):
        self.created = values
        return {"uuid": "created"}

    async def update_user(self, **values):
        self.updated = values
        return {"uuid": values["user_uuid"]}


def test_new_user_passes_complete_delivery_target() -> None:
    client = FakeClient()
    result = asyncio.run(
        apply_new_user(
            username="alice",
            telegram_id=42,
            days=30,
            internal_squad_ids=["squad-a", "squad-b"],
            external_squad_id="external",
            traffic_limit_bytes=50 * 1024**3,
            traffic_limit_strategy="MONTH_ROLLING",
            description="Premium user",
            tag="PREMIUM",
            client=client,
        )
    )
    assert result == {"uuid": "created"}
    assert client.created is not None
    assert client.created["internal_squad_ids"] == ["squad-a", "squad-b"]
    assert client.created["traffic_limit_bytes"] == 50 * 1024**3
    assert client.created["traffic_limit_strategy"] == "MONTH_ROLLING"
    assert client.created["tag"] == "PREMIUM"


def test_extend_does_not_replace_limit_with_legacy_zero() -> None:
    client = FakeClient()
    asyncio.run(
        apply_extend(
            user_uuid="00000000-0000-4000-8000-000000000001",
            username="alice",
            days=30,
            current_days_left=10,
            internal_squad_ids=["squad-a", "squad-b"],
            external_squad_id="external",
            traffic_limit_bytes=0,
            traffic_limit_strategy="NO_RESET",
            tag="PAID",
            client=client,
        )
    )
    assert client.updated is not None
    assert client.updated["days"] == 40
    assert client.updated["limit_gb"] is None
    assert client.updated["traffic_limit_bytes"] == 0
    assert client.updated["traffic_limit_strategy"] == "NO_RESET"
