"""Helpers for app_runtime_settings + payment_integrations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.runtime import AppRuntimeSettings, PaymentIntegration
from ..runtime_config.crypto import decrypt_json, encrypt_json
from ..runtime_config.keys import (
    DEFAULT_RUNTIME_CONFIG,
    PAYMENT_PROVIDER_FIELDS,
    RUNTIME_KEYS,
)
from ..runtime_config.overlay import parse_runtime_json
from .system import bump_cache_version, get_or_create_singleton


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def get_runtime_settings(session: AsyncSession) -> AppRuntimeSettings:
    return await get_or_create_singleton(
        session,
        AppRuntimeSettings,
        defaults={
            "config_json": json.dumps(DEFAULT_RUNTIME_CONFIG, ensure_ascii=False),
            "updated_at": _now_iso(),
        },
    )


async def get_runtime_config_dict(session: AsyncSession) -> dict[str, Any]:
    row = await get_runtime_settings(session)
    return parse_runtime_json(row.config_json)


async def save_runtime_config(
    session: AsyncSession,
    config: Mapping[str, Any],
    *,
    updated_by: str | None = None,
) -> dict[str, Any]:
    """Replace the runtime JSON (caller supplies full document)."""
    row = await get_runtime_settings(session)
    # Preserve unknown keys; normalize maintenance + known runtime keys.
    current = parse_runtime_json(row.config_json)
    incoming = dict(config)
    if "maintenance" in incoming and isinstance(incoming["maintenance"], dict):
        maint = dict(DEFAULT_RUNTIME_CONFIG["maintenance"])
        maint.update(incoming["maintenance"])
        current["maintenance"] = maint
    for key in RUNTIME_KEYS:
        if key in incoming:
            current[key] = incoming[key]
    row.config_json = json.dumps(current, ensure_ascii=False)
    row.updated_at = _now_iso()
    row.updated_by = updated_by
    await bump_cache_version(session)
    return current


async def import_runtime_from_yaml(
    session: AsyncSession,
    yaml_config: Mapping[str, Any],
) -> bool:
    """One-shot: if runtime JSON has no operator keys yet, copy from YAML.

    Returns True if an import happened.
    """
    row = await get_runtime_settings(session)
    current = parse_runtime_json(row.config_json)
    # Consider "empty of operator keys" if no RUNTIME_KEYS present.
    if any(k in current for k in RUNTIME_KEYS):
        return False
    imported = False
    for key in RUNTIME_KEYS:
        if key in yaml_config and yaml_config[key] is not None:
            current[key] = yaml_config[key]
            imported = True
    if not imported:
        return False
    row.config_json = json.dumps(current, ensure_ascii=False)
    row.updated_at = _now_iso()
    row.updated_by = "yaml-import"
    await bump_cache_version(session)
    return True


async def list_payment_integrations(session: AsyncSession) -> list[PaymentIntegration]:
    result = await session.execute(select(PaymentIntegration).order_by(PaymentIntegration.provider))
    return list(result.scalars().all())


async def get_payment_integration(
    session: AsyncSession, provider: str
) -> PaymentIntegration | None:
    return await session.scalar(
        select(PaymentIntegration).where(PaymentIntegration.provider == provider)
    )


async def upsert_payment_integration(
    session: AsyncSession,
    *,
    provider: str,
    enabled: bool,
    config: Mapping[str, Any],
    crypto_key: bytes,
    updated_by: str | None = None,
) -> PaymentIntegration:
    if provider not in PAYMENT_PROVIDER_FIELDS:
        raise ValueError(f"unknown payment provider: {provider}")
    allowed = set(PAYMENT_PROVIDER_FIELDS[provider])
    clean = {k: config[k] for k in allowed if k in config}
    row = await get_payment_integration(session, provider)
    if row is None:
        row = PaymentIntegration(provider=provider)
        session.add(row)
    else:
        # Merge with existing secrets when UI sends empty secret fields as "".
        try:
            existing = decrypt_json(row.encrypted_config, crypto_key) if row.encrypted_config else {}
        except Exception:
            existing = {}
        from ..runtime_config.keys import PAYMENT_SECRET_FIELDS

        for field in PAYMENT_SECRET_FIELDS:
            if field in clean and clean[field] in ("", None) and field in existing:
                clean[field] = existing[field]
    row.enabled = enabled
    row.managed = True
    row.encrypted_config = encrypt_json(dict(clean), crypto_key)
    row.updated_at = _now_iso()
    row.updated_by = updated_by
    await bump_cache_version(session)
    await session.flush()
    return row


async def import_payments_from_yaml(
    session: AsyncSession,
    yaml_config: Mapping[str, Any],
    crypto_key: bytes,
) -> int:
    """Create unmanaged placeholder rows from YAML when table is empty.

    Returns number of rows inserted.
    """
    existing = await list_payment_integrations(session)
    if existing:
        return 0
    inserted = 0
    for provider, fields in PAYMENT_PROVIDER_FIELDS.items():
        payload = {}
        has_any = False
        for field in fields:
            if field in yaml_config and yaml_config[field] not in (None, ""):
                payload[field] = yaml_config[field]
                has_any = True
        if not has_any:
            continue
        row = PaymentIntegration(
            provider=provider,
            enabled=True,
            managed=False,
            encrypted_config=encrypt_json(payload, crypto_key),
            updated_at=_now_iso(),
            updated_by="yaml-import",
        )
        session.add(row)
        inserted += 1
    if inserted:
        await bump_cache_version(session)
        await session.flush()
    return inserted
