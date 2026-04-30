import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from ..config import get_free_days, get_free_traffic, get_news_url, get_rw_free_id
from ..database.models import TelmtFreeParams, User
from ..database.session import async_session
from ..remnawave_client import create_user, get_user_from_username, update_user
from ..telemt_client import create_telemt_user, first_link, get_telemt_user
from ..tg_auth import TgUser, get_tg_user
from ..tg_channel import is_user_subscribed_to_news

router = APIRouter(prefix="/api/free", tags=["free"])
logger = logging.getLogger(__name__)


class SubscribeStateResponse(BaseModel):
    subscribed: bool
    news_url: str


class FreeStatusResponse(BaseModel):
    has_access: bool
    url: str | None = None
    news_url: str = ""


class ClaimResponse(BaseModel):
    ok: bool
    subscription_url: str | None = None
    days: int | None = None
    detail: str | None = None


class TelemtClaimResponse(BaseModel):
    ok: bool
    link: str | None = None
    detail: str | None = None


async def _ensure_user(tg: TgUser) -> User:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")
    if not user.username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "username required")
    return user


@router.get("/check", response_model=SubscribeStateResponse)
async def free_check(tg: TgUser = Depends(get_tg_user)) -> SubscribeStateResponse:
    await _ensure_user(tg)
    subscribed = await is_user_subscribed_to_news(tg.tg_id)
    return SubscribeStateResponse(subscribed=subscribed, news_url=get_news_url())


@router.get("/vpn/status", response_model=FreeStatusResponse)
async def free_vpn_status(tg: TgUser = Depends(get_tg_user)) -> FreeStatusResponse:
    user = await _ensure_user(tg)
    free_squad = get_rw_free_id() or None
    existing = await get_user_from_username(user.username)
    if existing and existing.get("uuid"):
        squads = {s.lower() for s in existing.get("active_squads", [])}
        is_free = bool(free_squad and free_squad.lower() in squads)
        is_active_pro = existing.get("status") == "active" and existing.get("data_limit") is None
        if is_active_pro or is_free:
            return FreeStatusResponse(
                has_access=True,
                url=existing.get("subscription_url"),
                news_url=get_news_url(),
            )
    return FreeStatusResponse(has_access=False, news_url=get_news_url())


@router.get("/telemt/status", response_model=FreeStatusResponse)
async def free_telemt_status(tg: TgUser = Depends(get_tg_user)) -> FreeStatusResponse:
    user = await _ensure_user(tg)
    try:
        existing = await get_telemt_user(user.username)
    except RuntimeError:
        existing = None
    if existing:
        return FreeStatusResponse(
            has_access=True,
            url=first_link(existing.get("links")),
            news_url=get_news_url(),
        )
    return FreeStatusResponse(has_access=False, news_url=get_news_url())


@router.post("/claim", response_model=ClaimResponse)
async def free_claim(tg: TgUser = Depends(get_tg_user)) -> ClaimResponse:
    user = await _ensure_user(tg)

    subscribed = await is_user_subscribed_to_news(tg.tg_id)
    if not subscribed:
        return ClaimResponse(ok=False, detail="not subscribed")

    days = get_free_days()
    limit_gb = get_free_traffic()
    free_squad = get_rw_free_id() or None

    existing = await get_user_from_username(user.username)
    if existing and existing.get("uuid"):
        squads = {s.lower() for s in existing.get("active_squads", [])}
        is_free = bool(free_squad and free_squad.lower() in squads)
        is_active_pro = existing.get("status") == "active" and existing.get("data_limit") is None
        if is_active_pro or is_free:
            return ClaimResponse(
                ok=True,
                subscription_url=existing.get("subscription_url"),
                days=existing.get("expire") and _days_left(existing.get("expire")),
                detail="already_active",
            )
        # Inactive / limited / expired free user — refresh
        updated = await update_user(
            existing["uuid"],
            days=days,
            limit_gb=limit_gb,
            squad_id=free_squad,
            status="active",
        )
        if not updated:
            return ClaimResponse(ok=False, detail="update_failed")
        return ClaimResponse(
            ok=True,
            subscription_url=updated.get("subscription_url"),
            days=days,
        )

    created = await create_user(
        username=user.username,
        days=days,
        limit_gb=limit_gb,
        descr="Free trial via miniapp",
        telegram_id=tg.tg_id,
        squad_id=free_squad,
    )
    if not created:
        return ClaimResponse(ok=False, detail="create_failed")
    return ClaimResponse(
        ok=True,
        subscription_url=created.get("subscription_url"),
        days=days,
    )


@router.post("/telemt", response_model=TelemtClaimResponse)
async def telemt_claim(tg: TgUser = Depends(get_tg_user)) -> TelemtClaimResponse:
    user = await _ensure_user(tg)

    subscribed = await is_user_subscribed_to_news(tg.tg_id)
    if not subscribed:
        return TelemtClaimResponse(ok=False, detail="not subscribed")

    existing = await get_telemt_user(user.username)
    if existing:
        link = first_link(existing.get("links"))
        return TelemtClaimResponse(ok=True, link=link, detail="already_active")

    async with async_session() as session:
        params = await session.scalar(select(TelmtFreeParams).where(TelmtFreeParams.id == 1))

    expire_days = params.expire_days if params and params.expire_days else 30
    max_tcp = params.max_tcp_conns if params else None
    max_ips = params.max_unique_ips if params else None
    quota = params.data_quota_bytes if params else None

    try:
        created = await create_telemt_user(
            username=user.username,
            expire_days=expire_days,
            max_tcp_conns=max_tcp,
            max_unique_ips=max_ips,
            data_quota_bytes=quota,
        )
    except RuntimeError as e:
        return TelemtClaimResponse(ok=False, detail=str(e))

    if not created:
        return TelemtClaimResponse(ok=False, detail="create_failed")

    return TelemtClaimResponse(ok=True, link=first_link(created.get("links")))


def _days_left(expire_ts: int | None) -> int:
    import time
    if expire_ts is None:
        return 0
    diff = round((expire_ts - time.time()) / 86400)
    return max(0, diff)
