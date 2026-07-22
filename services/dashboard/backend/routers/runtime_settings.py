"""Runtime settings API — maintenance, branding/links, free plan (dual-source)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from common_db.repo.runtime import get_runtime_config_dict, save_runtime_config
from common_db.runtime_config import RUNTIME_KEYS, invalidate_local
from common_db.runtime_config.keys import DEFAULT_MAINTENANCE

from ..auth import get_current_user
from ..config import get_yaml_config
from ..database.session import async_session

router = APIRouter(prefix="/api/settings", tags=["settings"])


class MaintenanceBody(BaseModel):
    enabled: bool = False
    title: str = "Технические работы"
    text: str = "Сервис временно недоступен. Попробуйте позже."


class RuntimeSettingsResponse(BaseModel):
    maintenance: MaintenanceBody
    values: dict[str, Any]
    sources: dict[str, str]
    yaml_fallback: dict[str, Any]


class RuntimeSettingsUpdate(BaseModel):
    maintenance: MaintenanceBody | None = None
    values: dict[str, Any] = Field(default_factory=dict)


def _sources_for(config: dict[str, Any], yaml_cfg: dict) -> dict[str, str]:
    sources: dict[str, str] = {"maintenance": "db"}
    for key in RUNTIME_KEYS:
        if key in config:
            sources[key] = "dashboard"
        elif key in yaml_cfg:
            sources[key] = "yaml"
        else:
            sources[key] = "default"
    return sources


@router.get("/runtime", response_model=RuntimeSettingsResponse)
async def get_runtime(_: str = Depends(get_current_user)):
    yaml_cfg = get_yaml_config()
    async with async_session() as session:
        config = await get_runtime_config_dict(session)
        await session.commit()
    maint = config.get("maintenance") or DEFAULT_MAINTENANCE
    values = {k: config[k] for k in RUNTIME_KEYS if k in config}
    # Fill display values from YAML when not yet in DB (UI convenience).
    yaml_fallback = {k: yaml_cfg.get(k) for k in RUNTIME_KEYS if k in yaml_cfg}
    display = dict(yaml_fallback)
    display.update(values)
    return RuntimeSettingsResponse(
        maintenance=MaintenanceBody(
            enabled=bool(maint.get("enabled")),
            title=str(maint.get("title") or DEFAULT_MAINTENANCE["title"]),
            text=str(maint.get("text") or DEFAULT_MAINTENANCE["text"]),
        ),
        values=display,
        sources=_sources_for(config, yaml_cfg),
        yaml_fallback=yaml_fallback,
    )


@router.put("/runtime", response_model=RuntimeSettingsResponse)
async def put_runtime(body: RuntimeSettingsUpdate, user: str = Depends(get_current_user)):
    yaml_cfg = get_yaml_config()
    payload: dict[str, Any] = {}
    if body.maintenance is not None:
        payload["maintenance"] = body.maintenance.model_dump()
    # Only accept known runtime keys.
    clean_values = {k: v for k, v in body.values.items() if k in RUNTIME_KEYS}
    payload.update(clean_values)
    async with async_session() as session:
        config = await save_runtime_config(session, payload, updated_by=user)
        await session.commit()
    invalidate_local()
    maint = config.get("maintenance") or DEFAULT_MAINTENANCE
    values = {k: config[k] for k in RUNTIME_KEYS if k in config}
    yaml_fallback = {k: yaml_cfg.get(k) for k in RUNTIME_KEYS if k in yaml_cfg}
    display = dict(yaml_fallback)
    display.update(values)
    return RuntimeSettingsResponse(
        maintenance=MaintenanceBody(
            enabled=bool(maint.get("enabled")),
            title=str(maint.get("title") or DEFAULT_MAINTENANCE["title"]),
            text=str(maint.get("text") or DEFAULT_MAINTENANCE["text"]),
        ),
        values=display,
        sources=_sources_for(config, yaml_cfg),
        yaml_fallback=yaml_fallback,
    )
