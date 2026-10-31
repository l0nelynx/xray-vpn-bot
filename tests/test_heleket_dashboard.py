from __future__ import annotations

import asyncio

import pytest

from common_db.repo.runtime import get_payment_integration
from common_db.runtime_config import DualSourceConfig, decrypt_json, derive_key, overlay
from payments.config import PaymentsConfig


@pytest.fixture(autouse=True)
def isolated_overlay(monkeypatch):
    for name, value in (
        ("_payment_overlay", {}), ("_payment_enabled", {}),
        ("_integration_overlay", {}), ("_integration_enabled", {}),
        ("_overlay", {}), ("_known_version", -1), ("_last_refresh", 0),
        ("_crypto_key", derive_key("test-key")),
    ):
        monkeypatch.setattr(overlay, name, value)


def test_dashboard_encrypts_masks_and_applies_settings_without_restart(session_factory, monkeypatch):
    from dashboard.backend.routers import payment_integrations as router

    monkeypatch.setattr(router, "async_session", session_factory)
    monkeypatch.setattr(router, "get_payments_secrets_key", lambda: "test-key")
    monkeypatch.setattr(router, "get_yaml_config", lambda: {})
    config = DualSourceConfig({})
    fields = {
        "heleket_merchant_id": "merchant", "heleket_api_key": "first-secret",
        "heleket_webhook": "https://vpn.example/bot/heleket_webhook",
    }

    async def save(enabled, values):
        return await router.update_provider(
            "heleket", router.PaymentProviderUpdate(enabled=enabled, fields=values), "admin",
        )

    async def refresh():
        async with session_factory() as session:
            await overlay.refresh_from_session(session, force=True)

    def current():
        return PaymentsConfig(**overlay.payments_config_kwargs(config))

    async def run():
        assert current().heleket_api_key == ""
        states = await router.list_providers("admin")
        state = next(p for p in states.providers if p.provider == "heleket")
        assert state.source == "none" and not state.enabled
        assert {f.name: f.secret for f in state.field_meta} == {
            "heleket_merchant_id": False, "heleket_api_key": True, "heleket_webhook": False,
        }
        await save(False, {})  # Valid without any credentials.
        state = await save(True, fields)
        assert state.fields["heleket_api_key"] == "••••••••"
        async with session_factory() as session:
            row = await get_payment_integration(session, "heleket")
            assert "first-secret" not in row.encrypted_config
            assert decrypt_json(row.encrypted_config, derive_key("test-key")) == fields
        await refresh()
        assert current().heleket_api_key == "first-secret"
        assert config.get("heleket_merchant_id") == "merchant"
        # The API strips masked placeholders; saving those must keep the key.
        await save(True, state.fields)
        await refresh()
        assert current().heleket_api_key == "first-secret"
        await save(True, {**fields, "heleket_api_key": ""})
        await refresh()
        assert current().heleket_api_key == "first-secret"
        await save(True, {**fields, "heleket_api_key": "rotated-secret"})
        await refresh()
        assert current().heleket_api_key == "rotated-secret"
        await save(False, {**fields, "heleket_api_key": ""})
        await refresh()
        assert current().heleket_api_key == ""
        assert config.get("heleket_api_key") == ""

    asyncio.run(run())


def test_tariff_constructor_catalog_and_revenue_currency():
    from dashboard.backend.routers.webapp_payments import list_providers
    from dashboard.backend.currency import convert_to_rub

    catalog = asyncio.run(list_providers("admin"))
    heleket = next(p for p in catalog["providers"] if p["name"] == "heleket")
    assert heleket == {
        "name": "heleket", "payment_method": "HELEKET", "currencies": ["USD"],
        "methods": [{"value": "default", "label": "Crypto"}],
        "surfaces": ["android", "bot", "miniapp", "web"], "webhook_key": "merchant",
    }
    assert convert_to_rub(12.34, "HELEKET", {"USD": 100}) == 1234
