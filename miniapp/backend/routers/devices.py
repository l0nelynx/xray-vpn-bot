import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ..database.models import User
from ..database.session import async_session
from ..remnawave_client import (
    delete_user_hwid_device,
    get_user_from_username,
    get_user_hwid_devices,
)
from ..schemas.devices import DeviceItem, DevicesResponse
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/devices", tags=["devices"])
logger = logging.getLogger(__name__)


async def _resolve_user_uuid(tg: TgUser) -> str:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")
    if not user.username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "username required")

    rem_user = await get_user_from_username(user.username)
    if not rem_user or not rem_user.get("uuid"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return rem_user["uuid"]


@router.get("", response_model=DevicesResponse)
async def list_devices(tg: TgUser = Depends(get_tg_user)) -> DevicesResponse:
    user_uuid = await _resolve_user_uuid(tg)
    devices = await get_user_hwid_devices(user_uuid)
    items = [DeviceItem(**d) for d in devices]
    return DevicesResponse(total=len(items), devices=items)


@router.delete("/{hwid}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(hwid: str, tg: TgUser = Depends(get_tg_user)) -> None:
    user_uuid = await _resolve_user_uuid(tg)
    ok = await delete_user_hwid_device(user_uuid, hwid)
    if not ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "failed to delete device")
    return None
