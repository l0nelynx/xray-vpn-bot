import asyncio
from types import SimpleNamespace

import remnawave_client.managed_subscriptions as managed


def _row():
    return SimpleNamespace(
        id=7,
        rw_id=1031,
        label="Marketplace",
        product_key=None,
        source="marketplace",
        is_primary=True,
    )


def test_unavailable_remnawave_link_is_preserved(monkeypatch):
    async def missing(_rw_id):
        return None

    async def failed_devices(_rw_id):
        raise RuntimeError("panel offline")

    monkeypatch.setattr(managed, "get_user_from_id", missing)
    monkeypatch.setattr(managed, "get_user_devices_count_by_id", failed_devices)
    result = asyncio.run(managed.serialize_managed_subscription(_row()))

    assert result["id"] == 7
    assert result["rw_id"] == 1031
    assert result["status"] == "unavailable"
    assert result["subscription_url"] is None


def test_live_remnawave_link_has_tariff_and_devices(monkeypatch):
    async def found(_rw_id):
        return {
            "active_squads": ["pro"],
            "status": "active",
            "expire": None,
            "traffic_used": 1,
            "data_limit": 10,
            "subscription_url": "https://example.test/sub",
        }

    async def devices(_rw_id):
        return 3

    monkeypatch.setattr(managed, "get_user_from_id", found)
    monkeypatch.setattr(managed, "get_user_devices_count_by_id", devices)
    result = asyncio.run(
        managed.serialize_managed_subscription(_row(), pro_squad_id="PRO")
    )

    assert result["tariff"] == "Premium"
    assert result["devices_count"] == 3
    assert result["status"] == "active"
