"""Payment gateway credentials managed from the Dashboard (dual-source)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_db.repo.runtime import (
    list_payment_integrations,
    upsert_payment_integration,
)
from common_db.runtime_config import (
    PAYMENT_PROVIDER_FIELDS,
    PAYMENT_SECRET_FIELDS,
    decrypt_json,
    derive_key,
    invalidate_local,
)

from ..auth import get_current_user
from ..config import get_payments_secrets_key, get_yaml_config
from ..database.session import async_session

router = APIRouter(prefix="/api/settings/payments", tags=["payment-integrations"])

_MASK = "••••••••"


class ProviderFieldMeta(BaseModel):
    name: str
    secret: bool


class PaymentProviderState(BaseModel):
    provider: str
    enabled: bool
    managed: bool
    source: str  # dashboard | yaml | none
    fields: dict[str, Any]
    field_meta: list[ProviderFieldMeta]
    updated_at: str | None = None


class PaymentIntegrationsResponse(BaseModel):
    providers: list[PaymentProviderState]


class PaymentProviderUpdate(BaseModel):
    enabled: bool = True
    fields: dict[str, Any] = Field(default_factory=dict)


def _crypto_key() -> bytes:
    return derive_key(get_payments_secrets_key())


def _yaml_fields(provider: str, yaml_cfg: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in PAYMENT_PROVIDER_FIELDS.get(provider, ()):
        if field in yaml_cfg and yaml_cfg[field] not in (None, ""):
            out[field] = yaml_cfg[field]
    return out


def _mask_fields(fields: dict[str, Any]) -> dict[str, Any]:
    masked = dict(fields)
    for key in list(masked):
        if key in PAYMENT_SECRET_FIELDS and masked[key] not in (None, ""):
            masked[key] = _MASK
    return masked


def _field_meta(provider: str) -> list[ProviderFieldMeta]:
    return [
        ProviderFieldMeta(name=f, secret=f in PAYMENT_SECRET_FIELDS)
        for f in PAYMENT_PROVIDER_FIELDS.get(provider, ())
    ]


@router.get("", response_model=PaymentIntegrationsResponse)
async def list_providers(_: str = Depends(get_current_user)):
    yaml_cfg = get_yaml_config()
    key = _crypto_key()
    async with async_session() as session:
        rows = {r.provider: r for r in await list_payment_integrations(session)}
        await session.commit()

    providers: list[PaymentProviderState] = []
    for provider in PAYMENT_PROVIDER_FIELDS:
        row = rows.get(provider)
        yaml_vals = _yaml_fields(provider, yaml_cfg)
        if row and row.managed:
            try:
                raw = decrypt_json(row.encrypted_config, key) if row.encrypted_config else {}
            except Exception:
                raw = {}
            providers.append(
                PaymentProviderState(
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
                PaymentProviderState(
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
                PaymentProviderState(
                    provider=provider,
                    enabled=False,
                    managed=bool(row and row.managed),
                    source="none",
                    fields={},
                    field_meta=_field_meta(provider),
                    updated_at=row.updated_at if row else None,
                )
            )
    return PaymentIntegrationsResponse(providers=providers)


@router.put("/{provider}", response_model=PaymentProviderState)
async def update_provider(
    provider: str,
    body: PaymentProviderUpdate,
    user: str = Depends(get_current_user),
):
    if provider not in PAYMENT_PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail="unknown provider")
    # Strip masked placeholders so we don't overwrite secrets with bullets.
    clean_fields = {
        k: v
        for k, v in body.fields.items()
        if k in PAYMENT_PROVIDER_FIELDS[provider] and v != _MASK
    }
    key = _crypto_key()
    async with async_session() as session:
        row = await upsert_payment_integration(
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
    return PaymentProviderState(
        provider=provider,
        enabled=bool(row.enabled),
        managed=True,
        source="dashboard",
        fields=_mask_fields(raw),
        field_meta=_field_meta(provider),
        updated_at=row.updated_at,
    )
