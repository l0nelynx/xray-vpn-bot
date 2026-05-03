"""Compatibility shim that exposes the legacy module-level Remnawave API
on top of the shared `remnawave_client` package.

Existing callers (`import app.api.remnawave.api as rem`) keep working without
changes. New code should import `remnawave_client` directly.
"""

import logging

from remnawave.models import (
    DeleteUserHwidDeviceResponseDto,
    GetUserHwidDevicesResponseDto,
    UsersResponseDto,
)
from remnawave_client import RemnawaveClient, configure

from app.settings import secrets

logger = logging.getLogger(__name__)


def _client() -> RemnawaveClient:
    """Lazy-init the default client from app.settings.secrets on first use."""
    return configure(
        base_url=secrets.get("remnawave_url"),
        token=secrets.get("remnawave_token"),
        free_squad_id=secrets.get("rw_free_id"),
    )


async def get_all_users() -> UsersResponseDto:
    return await _client().get_all_users()


async def get_user_from_username(username: str) -> dict | None:
    return await _client().get_user_by_username(username)


async def get_user_from_email(email: str) -> dict | None:
    return await _client().get_user_by_email(email)


async def create_user(
    username: str,
    days: int = 30,
    limit_gb: int = 0,
    descr: str = "created by backend v2",
    email: str = None,
    telegram_id: int = None,
    tag: str = None,
    squad_id: str = None,
    external_squad_id: str = None,
) -> dict | None:
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
    username: str = None,
    days: int = None,
    limit_gb: int = None,
    descr: str = None,
    email: str = None,
    tag: str = None,
    status: str = None,
    squad_id: str = None,
    external_squad_id: str = None,
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


async def reset_user_traffic(user_uuid: str) -> bool:
    return await _client().reset_user_traffic(user_uuid)


async def delete_user(user_uuid: str) -> bool:
    return await _client().delete_user(user_uuid)


async def get_user_subscription_link(user_uuid: str) -> str | None:
    return await _client().get_subscription_link(user_uuid)


async def get_user_hwid_devices(user_uuid: str) -> GetUserHwidDevicesResponseDto | None:
    return await _client().get_user_hwid_devices(user_uuid)


async def delete_user_hwid_device(
    user_uuid: str, hwid: str
) -> DeleteUserHwidDeviceResponseDto | None:
    return await _client().delete_user_hwid_device(user_uuid, hwid)
