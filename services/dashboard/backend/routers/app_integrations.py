"""Service integrations (SMTP, Android JWT, Telemt, Store, FCM, …) dual-source."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_db.repo.runtime import (
    get_app_integration,
    list_app_integrations,
    upsert_app_integration,
)
from common_db.runtime_config import (
    INTEGRATION_PROVIDER_FIELDS,
    INTEGRATION_SECRET_FIELDS,
    decrypt_json,
    derive_key,
    invalidate_local,
    android_jwt_secret_error,
    resolve_android_jwt_secret,
)

from ..auth import get_current_user
from ..config import get_payments_secrets_key, get_yaml_config
from ..database.session import async_session

router = APIRouter(prefix="/api/settings/integrations", tags=["app-integrations"])

_MASK = "••••••••"


class ProviderFieldMeta(BaseModel):
    name: str
    secret: bool


class IntegrationProviderState(BaseModel):
    provider: str
    enabled: bool
    managed: bool
    source: str  # dashboard | yaml | none
    fields: dict[str, Any]
    field_meta: list[ProviderFieldMeta]
    updated_at: str | None = None


class IntegrationsResponse(BaseModel):
    providers: list[IntegrationProviderState]


class IntegrationProviderUpdate(BaseModel):
    enabled: bool = True
    fields: dict[str, Any] = Field(default_factory=dict)


def _crypto_key() -> bytes:
    return derive_key(get_payments_secrets_key())


def _yaml_fields(provider: str, yaml_cfg: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in INTEGRATION_PROVIDER_FIELDS.get(provider, ()):
        if field in yaml_cfg and yaml_cfg[field] not in (None, ""):
            out[field] = yaml_cfg[field]
    return out


def _mask_fields(fields: dict[str, Any]) -> dict[str, Any]:
    masked = dict(fields)
    for key in list(masked):
        if key in INTEGRATION_SECRET_FIELDS and masked[key] not in (None, ""):
            masked[key] = _MASK
    return masked


def _field_meta(provider: str) -> list[ProviderFieldMeta]:
    return [
        ProviderFieldMeta(name=f, secret=f in INTEGRATION_SECRET_FIELDS)
        for f in INTEGRATION_PROVIDER_FIELDS.get(provider, ())
    ]


@router.get("", response_model=IntegrationsResponse)
async def list_providers(_: str = Depends(get_current_user)):
    yaml_cfg = get_yaml_config()
    key = _crypto_key()
    async with async_session() as session:
        rows = {r.provider: r for r in await list_app_integrations(session)}
        await session.commit()

    providers: list[IntegrationProviderState] = []
    for provider in INTEGRATION_PROVIDER_FIELDS:
        row = rows.get(provider)
        yaml_vals = _yaml_fields(provider, yaml_cfg)
        if row and row.managed:
            try:
                raw = decrypt_json(row.encrypted_config, key) if row.encrypted_config else {}
            except Exception:
                raw = {}
            providers.append(
                IntegrationProviderState(
                    provider=provider,
                    enabled=bool(row.enabled),
                    managed=True,
                    source="dashboard",
                    fields=_mask_fields(raw),
                    field_meta=_field_meta(provider),
                    updated_at=row.updated_at,
                )
            )
        elif yaml_vals:
            providers.append(
                IntegrationProviderState(
                    provider=provider,
                    enabled=True,
                    managed=False,
                    source="yaml",
                    fields=_mask_fields(yaml_vals),
                    field_meta=_field_meta(provider),
                    updated_at=row.updated_at if row else None,
                )
            )
        else:
            providers.append(
                IntegrationProviderState(
                    provider=provider,
                    enabled=False,
                    managed=bool(row and row.managed),
                    source="none",
                    fields={},
                    field_meta=_field_meta(provider),
                    updated_at=row.updated_at if row else None,
                )
            )
    return IntegrationsResponse(providers=providers)


@router.put("/{provider}", response_model=IntegrationProviderState)
async def update_provider(
    provider: str,
    body: IntegrationProviderUpdate,
    user: str = Depends(get_current_user),
):
    if provider not in INTEGRATION_PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail="unknown provider")
    clean_fields = {
        k: v
        for k, v in body.fields.items()
        if k in INTEGRATION_PROVIDER_FIELDS[provider] and v != _MASK
    }
    # Empty secret inputs mean "keep current value"; do not persist an empty
    # override that would hide a valid YAML fallback.
    for field in INTEGRATION_SECRET_FIELDS:
        if clean_fields.get(field) in ("", None):
            clean_fields.pop(field, None)

    key = _crypto_key()
    async with async_session() as session:
        current = await get_app_integration(session, provider)
        existing_fields: dict[str, Any] = {}
        if current and current.encrypted_config:
            try:
                existing_fields = decrypt_json(current.encrypted_config, key)
            except Exception:
                existing_fields = {}

        if provider == "android" and body.enabled:
            # Invalid/corrupt values from the original migration fall back to
            # YAML and are repaired on Save. An explicit new value still wins
            # so the validator can reject it rather than silently hiding it.
            effective_secret = resolve_android_jwt_secret(
                submitted=clean_fields.get("android_jwt_secret"),
                existing=existing_fields.get("android_jwt_secret"),
                yaml_fallback=get_yaml_config().get("android_jwt_secret"),
            )
            validation_error = android_jwt_secret_error(effective_secret)
            if validation_error:
                raise HTTPException(status_code=422, detail=validation_error)
            # Persist the effective value even when the password input was
            # intentionally left blank. This completes the YAML → Dashboard
            # migration instead of leaving a hidden per-field YAML fallback.
            clean_fields["android_jwt_secret"] = effective_secret

        row = await upsert_app_integration(
            session,
            provider=provider,
            enabled=body.enabled,
            config=clean_fields,
            crypto_key=key,
            updated_by=user,
        )
        await session.commit()
        try:
            raw = decrypt_json(row.encrypted_config, key) if row.encrypted_config else {}
        except Exception:
            raw = {}
    invalidate_local()
    return IntegrationProviderState(
        provider=provider,
        enabled=bool(row.enabled),
        managed=True,
        source="dashboard",
        fields=_mask_fields(raw),
        field_meta=_field_meta(provider),
        updated_at=row.updated_at,
    )
