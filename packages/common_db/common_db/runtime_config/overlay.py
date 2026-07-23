"""In-memory dual-source overlay: DB values win over YAML for RUNTIME_KEYS.

Services call :func:`refresh_from_session` on startup and on a short poll
(or after Dashboard bumps ``cache_version``). Sync readers use
:func:`get_overlay` / :func:`merge_config`.
"""
from __future__ import annotations

import json
import logging
import time
from copy import deepcopy
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.runtime import AppIntegration, AppRuntimeSettings, PaymentIntegration
from .crypto import decrypt_json, derive_key
from .keys import (
    DEFAULT_MAINTENANCE,
    DEFAULT_RUNTIME_CONFIG,
    INTEGRATION_EMPTY_DEFAULTS,
    INTEGRATION_PROVIDER_FIELDS,
    PAYMENT_PROVIDER_FIELDS,
    RUNTIME_KEYS,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5.0

# Flat overlay for RUNTIME_KEYS (+ nested maintenance under "maintenance").
_overlay: dict[str, Any] = {}
# provider -> decrypted field dict when managed; None means unmanaged / YAML.
_payment_overlay: dict[str, dict[str, Any] | None] = {}
_payment_enabled: dict[str, bool] = {}
_integration_overlay: dict[str, dict[str, Any] | None] = {}
_integration_enabled: dict[str, bool] = {}
_known_version: int = -1
_last_refresh: float = 0.0
_crypto_key: bytes | None = None


def set_crypto_secret(secret: str) -> None:
    global _crypto_key
    _crypto_key = derive_key(secret)


def _ensure_key() -> bytes:
    global _crypto_key
    if _crypto_key is None:
        _crypto_key = derive_key("")
    return _crypto_key


def get_overlay() -> dict[str, Any]:
    return dict(_overlay)


def get_maintenance() -> dict[str, Any]:
    maint = _overlay.get("maintenance")
    if isinstance(maint, dict):
        return dict(maint)
    return dict(DEFAULT_RUNTIME_CONFIG["maintenance"])


def is_maintenance_enabled() -> bool:
    return bool(get_maintenance().get("enabled"))


def merge_config(yaml_config: Mapping[str, Any]) -> dict[str, Any]:
    """Return YAML dict with runtime overlay keys applied."""
    merged = dict(yaml_config)
    for key, value in _overlay.items():
        if key == "maintenance":
            continue
        if key in RUNTIME_KEYS:
            merged[key] = value
    return merged


def apply_payments_to_mapping(target: dict[str, Any]) -> dict[str, Any]:
    """Overlay managed payment fields onto a flat config mapping."""
    out = dict(target)
    for provider, fields in PAYMENT_PROVIDER_FIELDS.items():
        payload = _payment_overlay.get(provider)
        if payload is None:
            continue
        if not _payment_enabled.get(provider, False):
            # Managed but disabled → clear credentials so providers refuse.
            for field in fields:
                out[field] = "" if field != "platega_payment_method" else 2
            continue
        for field in fields:
            if field in payload:
                out[field] = payload[field]
    return out


def apply_integrations_to_mapping(target: dict[str, Any]) -> dict[str, Any]:
    """Overlay managed app_integrations secrets onto a flat config mapping."""
    out = dict(target)
    for provider, fields in INTEGRATION_PROVIDER_FIELDS.items():
        payload = _integration_overlay.get(provider)
        if payload is None:
            continue
        if not _integration_enabled.get(provider, False):
            for field in fields:
                out[field] = INTEGRATION_EMPTY_DEFAULTS.get(field, "")
            continue
        for field in fields:
            if field in payload:
                out[field] = payload[field]
    return out


def payments_config_kwargs(yaml_config: Mapping[str, Any]) -> dict[str, Any]:
    """Build kwargs for ``payments.PaymentsConfig`` with dual-source precedence."""
    base = {
        "bot_token": yaml_config.get("token", "") or "",
        "apay_id": yaml_config.get("apay_id", ""),
        "apay_secret": yaml_config.get("apay_secret", "") or "",
        "apay_api_url": yaml_config.get("apay_api_url", "") or "",
        "crypto_bot_token": yaml_config.get("crypto_bot_token", "") or "",
        "crystal_login": yaml_config.get("crystal_login", "") or "",
        "crystal_secret": yaml_config.get("crystal_secret", "") or "",
        "crystal_salt": yaml_config.get("crystal_salt", "") or "",
        "crystal_webhook": yaml_config.get("crystal_webhook", "") or "",
        "platega_merchant_id": yaml_config.get("platega_merchant_id", "") or "",
        "platega_api_key": yaml_config.get("platega_api_key", "") or "",
        "platega_url": (yaml_config.get("platega_url") or "https://app.platega.io"),
        "platega_payment_method": yaml_config.get("platega_payment_method", 2),
        "paritypay_shop_id": yaml_config.get("paritypay_shop_id", "") or "",
        "paritypay_secret_1": yaml_config.get("paritypay_secret_1", "") or "",
        "paritypay_secret_2": yaml_config.get("paritypay_secret_2", "") or "",
        "paritypay_url": (yaml_config.get("paritypay_url") or "https://api.paritypay.ru"),
        "paritypay_webhook": yaml_config.get("paritypay_webhook", "") or "",
        "paritypay_service": yaml_config.get("paritypay_service", "sbp") or "sbp",
    }
    merged = apply_payments_to_mapping(base)
    try:
        merged["platega_payment_method"] = int(merged.get("platega_payment_method", 2))
    except (TypeError, ValueError):
        merged["platega_payment_method"] = 2
    return merged


def parse_runtime_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return deepcopy(DEFAULT_RUNTIME_CONFIG)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("app_runtime_settings.config_json is invalid JSON; using defaults")
        return deepcopy(DEFAULT_RUNTIME_CONFIG)
    if not isinstance(data, dict):
        return deepcopy(DEFAULT_RUNTIME_CONFIG)
    # Ensure maintenance block exists.
    if "maintenance" not in data or not isinstance(data.get("maintenance"), dict):
        data["maintenance"] = dict(DEFAULT_MAINTENANCE)
    else:
        maint = dict(DEFAULT_RUNTIME_CONFIG["maintenance"])
        maint.update(data["maintenance"])
        data["maintenance"] = maint
    return data


async def refresh_from_session(session: AsyncSession, *, force: bool = False) -> None:
    """Reload overlay from DB. Optionally skip if cache_version unchanged."""
    global _overlay, _payment_overlay, _payment_enabled
    global _integration_overlay, _integration_enabled, _known_version, _last_refresh

    now = time.monotonic()
    if not force and (now - _last_refresh) < _POLL_INTERVAL and _known_version >= 0:
        return

    from ..repo.system import get_cache_version

    version = await get_cache_version(session)
    if not force and version == _known_version and _known_version >= 0:
        _last_refresh = now
        return

    row = await session.scalar(
        select(AppRuntimeSettings).where(AppRuntimeSettings.id == 1)
    )
    config = parse_runtime_json(row.config_json if row else None)
    flat: dict[str, Any] = {"maintenance": config.get("maintenance", DEFAULT_MAINTENANCE)}
    for key in RUNTIME_KEYS:
        if key in config:
            flat[key] = config[key]

    key = _ensure_key()

    pay_map: dict[str, dict[str, Any] | None] = {}
    pay_en: dict[str, bool] = {}
    result = await session.execute(select(PaymentIntegration))
    for integ in result.scalars().all():
        if not integ.managed:
            pay_map[integ.provider] = None
            continue
        pay_en[integ.provider] = bool(integ.enabled)
        try:
            pay_map[integ.provider] = decrypt_json(integ.encrypted_config, key)
        except Exception as exc:
            logger.error(
                "Failed to decrypt payment_integrations[%s]: %s",
                integ.provider,
                exc,
            )
            pay_map[integ.provider] = {}

    int_map: dict[str, dict[str, Any] | None] = {}
    int_en: dict[str, bool] = {}
    result = await session.execute(select(AppIntegration))
    for integ in result.scalars().all():
        if not integ.managed:
            int_map[integ.provider] = None
            continue
        int_en[integ.provider] = bool(integ.enabled)
        try:
            int_map[integ.provider] = decrypt_json(integ.encrypted_config, key)
        except Exception as exc:
            logger.error(
                "Failed to decrypt app_integrations[%s]: %s",
                integ.provider,
                exc,
            )
            int_map[integ.provider] = {}

    _overlay = flat
    _payment_overlay = pay_map
    _payment_enabled = pay_en
    _integration_overlay = int_map
    _integration_enabled = int_en
    _known_version = version
    _last_refresh = now


def invalidate_local() -> None:
    """Force next refresh_from_session to reload (same process)."""
    global _known_version
    _known_version = -1
