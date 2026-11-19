import asyncio

import pytest
from fastapi import HTTPException
from common_db.runtime_config import overlay, derive_key, decrypt_json
from common_db.repo.runtime import get_app_integration, import_integrations_from_yaml
from miniapp.backend.web import analytics


@pytest.fixture(autouse=True)
def isolated_overlay(monkeypatch):
    for name, value in (("_integration_overlay", {}), ("_integration_enabled", {}),
                        ("_payment_overlay", {}), ("_payment_enabled", {}), ("_overlay", {}),
                        ("_known_version", -1), ("_last_refresh", 0), ("_crypto_key", derive_key("test-key"))):
        monkeypatch.setattr(overlay, name, value)


def test_dashboard_roundtrip_masking_disable_and_rotation(session_factory, monkeypatch):
    from dashboard.backend.routers import app_integrations as router
    monkeypatch.setattr(router, "async_session", session_factory)
    monkeypatch.setattr(router, "get_payments_secrets_key", lambda: "test-key")
    monkeypatch.setattr(router, "get_yaml_config", lambda: {"ga4_measurement_id": "G-YAML", "ga4_api_secret": "yaml-secret"})
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-ENV")
    monkeypatch.setenv("GA4_API_SECRET", "env-secret")

    async def refresh():
        async with session_factory() as session:
            await overlay.refresh_from_session(session, force=True)

    async def save(enabled, fields):
        return await router.update_provider("ga4", router.IntegrationProviderUpdate(enabled=enabled, fields=fields), "admin")

    async def run():
        assert analytics.settings() == ("", "")
        states = await router.list_providers("admin")
        state = next(p for p in states.providers if p.provider == "ga4")
        assert state.source == "none" and not state.enabled
        await save(False, {})  # Optional, unconfigured save is valid.
        with pytest.raises(HTTPException) as exc:
            await save(True, {"ga4_measurement_id": "invalid", "ga4_api_secret": "secret"})
        assert exc.value.status_code == 422
        with pytest.raises(HTTPException):
            await save(True, {"ga4_measurement_id": "G-TEST123"})
        state = await save(True, {"ga4_measurement_id": "G-TEST123", "ga4_api_secret": "first-secret"})
        assert state.fields["ga4_api_secret"] == "••••••••"
        async with session_factory() as session:
            row = await get_app_integration(session, "ga4")
            assert "first-secret" not in str(row.encrypted_config)
            assert decrypt_json(row.encrypted_config, derive_key("test-key"))["ga4_api_secret"] == "first-secret"
        await refresh()
        assert analytics.settings() == ("G-TEST123", "first-secret")
        await save(True, {"ga4_api_secret": ""})
        await save(True, {"ga4_api_secret": "  "})
        await refresh()
        assert analytics.settings() == ("G-TEST123", "first-secret")
        await save(False, {})
        await refresh()
        assert analytics.settings() == ("", "")
        await save(True, {"ga4_api_secret": "rotated-secret"})
        await refresh()
        assert analytics.settings() == ("G-TEST123", "rotated-secret")
    asyncio.run(run())


def test_integrations_api_requires_admin_and_never_echoes_secret(session_factory, monkeypatch):
    import httpx
    from dashboard.backend import auth, main
    from dashboard.backend.routers import app_integrations as router

    monkeypatch.setattr(router, "async_session", session_factory)
    url = f"{main.BASE_PATH}/api/settings/integrations"
    secret = "private-test-value"
    fields = {"ga4_measurement_id": "G-TEST123", "ga4_api_secret": secret}

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as client:
            for headers, expected in [
                ({}, 401),
                ({"Authorization": f"Bearer {auth.create_access_token('portal-user')}"}, 403),
            ]:
                assert (await client.get(url, headers=headers)).status_code == expected
                denied = await client.put(url + "/ga4", headers=headers, json={"fields": fields})
                assert denied.status_code == expected and secret not in denied.text
            client.headers["Authorization"] = f"Bearer {auth.create_access_token(router.get_dashboard_login())}"
            saved = await client.put(url + "/ga4", json={"enabled": True, "fields": fields})
            assert saved.status_code == 200 and secret not in saved.text
            listed = await client.get(url)
            assert listed.status_code == 200 and secret not in listed.text
            invalid = await client.put(url + "/ga4", json={"fields": [fields]})
            assert invalid.status_code == 422 and secret not in invalid.text
    asyncio.run(run())


def test_yaml_not_imported(session_factory):
    async def run():
        async with session_factory() as session:
            await import_integrations_from_yaml(session, {"ga4_measurement_id": "G-YAML", "ga4_api_secret": "secret"}, derive_key("test-key"))
            assert await get_app_integration(session, "ga4") is None
    asyncio.run(run())


def test_worker_can_start_disabled_then_enable_without_restart(monkeypatch):
    current = ["", ""]
    monkeypatch.setattr(analytics, "settings", lambda: tuple(current))
    sent = []
    sleeps = 0

    async def send(*args):
        sent.append(args[-2:])
    async def sleep(_):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 1:
            current[:] = ["G-TEST123", "first"]
        elif sleeps == 2:
            current[:] = ["", ""]
        elif sleeps == 3:
            current[:] = ["G-TEST123", "rotated"]
        else:
            raise asyncio.CancelledError
    monkeypatch.setattr(analytics, "send_batch", send)
    monkeypatch.setattr(analytics.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(analytics.delivery_loop(None))
    assert sent == [("G-TEST123", "first"), ("G-TEST123", "rotated")]


def test_corrupt_config_and_missing_settings_do_not_block_checkout(monkeypatch):
    async def run():
        # None session deliberately proves the disabled path performs no DB work.
        await analytics.enqueue(None, analytics.AnalyticsContext(client_id="123.456", session_id="123"), "tx", "platega")
    asyncio.run(run())
    monkeypatch.setattr(overlay, "_integration_overlay", {"ga4": {"ga4_measurement_id": 123, "ga4_api_secret": []}})
    monkeypatch.setattr(overlay, "_integration_enabled", {"ga4": True})
    assert analytics.settings() == ("", "")
    asyncio.run(run())
