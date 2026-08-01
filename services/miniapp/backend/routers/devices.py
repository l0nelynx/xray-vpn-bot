import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ..database.models import User
from ..database.session import async_session

from common_db.repo import users as _repo_users
from remnawave_client.api import (
    delete_user_hwid_device_by_id,
    list_user_hwid_devices_by_id,
    resolve_remnawave_user,
)
from ..schemas.devices import DeviceItem, DevicesResponse
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/devices", tags=["devices"])
logger = logging.getLogger(__name__)


async def _resolve_user_rw_id(tg: TgUser) -> int:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")
    if user.rw_id is None and not (user.email or user.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no identifier")

    rem_user = await resolve_remnawave_user(
        rw_id=user.rw_id,
        email=user.email,
        username=user.username,
        expected_telegram_id=tg.tg_id,
    )
    if not rem_user or rem_user.get("rw_id") is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return int(rem_user["rw_id"])


@router.get("", response_model=DevicesResponse)
async def list_devices(tg: TgUser = Depends(get_tg_user)) -> DevicesResponse:
    rw_id = await _resolve_user_rw_id(tg)
    devices = await list_user_hwid_devices_by_id(rw_id)
    items = [DeviceItem(**d) for d in devices]
    return DevicesResponse(total=len(items), devices=items)


@router.delete("/{hwid}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(hwid: str, tg: TgUser = Depends(get_tg_user)) -> None:
    rw_id = await _resolve_user_rw_id(tg)
    ok = await delete_user_hwid_device_by_id(rw_id, hwid)
    if not ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "failed to delete device")
    return None
