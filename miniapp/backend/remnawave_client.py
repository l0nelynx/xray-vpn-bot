"""Compatibility shim — miniapp routers still import from `..remnawave_client`.

Reuses the shared `remnawave_client` package; this module only adapts return
types where miniapp expects something different from app/ (HWID devices as a
list of dicts and a separate count helper).
"""

import logging

from remnawave_client import RemnawaveClient, configure

from .config import get_remnawave_token, get_remnawave_url, get_rw_free_id

logger = logging.getLogger(__name__)


def _client() -> RemnawaveClient:
    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id=get_rw_free_id(),
    )


def _normalize_device(device) -> dict:
    return {
        "hwid": device.hwid,
        "platform": getattr(device, "platform", None),
        "os_version": getattr(device, "os_version", None),
        "device_model": getattr(device, "device_model", None),
        "user_agent": getattr(device, "user_agent", None),
        "created_at": (
            device.created_at.isoformat()
            if getattr(device, "created_at", None) else None
        ),
        "updated_at": (
            device.updated_at.isoformat()
            if getattr(device, "updated_at", None) else None
        ),
    }


async def get_user_from_username(username: str) -> dict | None:
    return await _client().get_user_by_username(username)


async def create_user(
    username: str,
    days: int = 30,
    limit_gb: int = 0,
    descr: str = "created by miniapp",
    email: str | None = None,
    telegram_id: int | None = None,
    tag: str | None = None,
    squad_id: str | None = None,
    external_squad_id: str | None = None,
) -> dict | None:
    if email is None:
        email = f"{username}@miniapp.xyz"
    return await _client().create_user(
        username=username,
        days=days,
        limit_gb=limit_gb,
        descr=descr,
        email=email,
        telegram_id=telegram_id,
        tag=tag,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
    )


async def update_user(
    user_uuid: str,
    username: str | None = None,
    days: int | None = None,
    limit_gb: int | None = None,
    descr: str | None = None,
    email: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    squad_id: str | None = None,
    external_squad_id: str | None = None,
) -> dict | None:
    return await _client().update_user(
        user_uuid=user_uuid,
        username=username,
        days=days,
        limit_gb=limit_gb,
        descr=descr,
        email=email,
        tag=tag,
        status=status,
        squad_id=squad_id,
        external_squad_id=external_squad_id,
    )


async def delete_user(user_uuid: str) -> bool:
    return await _client().delete_user(user_uuid)


async def get_user_hwid_devices(user_uuid: str) -> list[dict]:
    response = await _client().get_user_hwid_devices(user_uuid)
    if not response or not response.devices:
        return []
    return [_normalize_device(d) for d in response.devices]


async def get_user_devices_count(user_uuid: str) -> int:
    response = await _client().get_user_hwid_devices(user_uuid)
    if not response:
        return 0
    return int(response.total) if response.total else len(response.devices or [])


async def delete_user_hwid_device(user_uuid: str, hwid: str) -> bool:
    response = await _client().delete_user_hwid_device(user_uuid, hwid)
    return response is not None
