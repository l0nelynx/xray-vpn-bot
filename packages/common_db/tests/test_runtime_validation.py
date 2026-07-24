from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import AppIntegration
from common_db.repo.runtime import (
    import_integrations_from_yaml,
    list_app_integrations,
    upsert_app_integration,
)
from common_db.runtime_config import (
    DualSourceConfig,
    android_jwt_secret_error,
    decrypt_json,
    derive_key,
    encrypt_json,
    resolve_android_jwt_secret,
)
from common_db.runtime_config import overlay


def test_android_jwt_secret_rejects_missing_placeholder_and_short_values():
    assert android_jwt_secret_error(None)
    assert android_jwt_secret_error("   ")
    assert android_jwt_secret_error("change-me-android-jwt-secret")
    assert android_jwt_secret_error("x" * 31)


def test_android_jwt_secret_counts_utf8_bytes():
    assert android_jwt_secret_error("я" * 15)
    assert android_jwt_secret_error("я" * 16) is None


def test_android_jwt_secret_accepts_32_byte_value():
    assert android_jwt_secret_error("x" * 32) is None


def test_dashboard_save_repairs_invalid_migrated_secret_from_yaml():
    yaml_secret = "y" * 32
    assert (
        resolve_android_jwt_secret(
            submitted=None,
            existing="too-short",
            yaml_fallback=yaml_secret,
        )
        == yaml_secret
    )
    # Explicit input is never hidden by fallback; the caller will reject it.
    assert (
        resolve_android_jwt_secret(
            submitted="bad-new-value",
            existing="x" * 32,
            yaml_fallback=yaml_secret,
        )
        == "bad-new-value"
    )


def test_yaml_import_then_dashboard_save_keeps_secret():
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        key = derive_key("test-dashboard-key")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                imported = await import_integrations_from_yaml(
                    session,
                    {"android_jwt_secret": "x" * 32},
                    key,
                )
                await session.commit()
                assert imported == 1
                rows = await list_app_integrations(session)
                assert rows[0].managed is False
            async with Session() as session:
                row = await upsert_app_integration(
                    session,
                    provider="android",
                    enabled=True,
                    config={},
                    crypto_key=key,
                )
                assert decrypt_json(row.encrypted_config, key) == {
                    "android_jwt_secret": "x" * 32
                }
        finally:
            await engine.dispose()

    asyncio.run(go())


def test_yaml_import_skips_invalid_android_secret():
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        key = derive_key("test-dashboard-key")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                imported = await import_integrations_from_yaml(
                    session,
                    {"android_jwt_secret": "too-short"},
                    key,
                )
                assert imported == 0
                assert await list_app_integrations(session) == []
        finally:
            await engine.dispose()

    asyncio.run(go())


def test_invalid_managed_android_secret_falls_back_to_yaml(monkeypatch):
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        dashboard_key = "test-dashboard-key"
        key = derive_key(dashboard_key)
        yaml_secret = "y" * 32
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(
                    AppIntegration(
                        provider="android",
                        enabled=True,
                        managed=True,
                        encrypted_config=encrypt_json(
                            {"android_jwt_secret": "too-short"}, key
                        ),
                    )
                )
                await session.commit()
            overlay.set_crypto_secret(dashboard_key)
            async with Session() as session:
                await overlay.refresh_from_session(session, force=True)
            assert (
                DualSourceConfig({"android_jwt_secret": yaml_secret}).get(
                    "android_jwt_secret"
                )
                == yaml_secret
            )
        finally:
            await engine.dispose()

    monkeypatch.setattr(overlay, "_integration_overlay", {})
    monkeypatch.setattr(overlay, "_integration_enabled", {})
    asyncio.run(go())
