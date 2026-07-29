import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from ..config import get_free_days, get_free_traffic, get_news_url, get_rw_free_id
from ..database.models import TelmtFreeParams, User
from ..database.session import async_session

from common_db.repo import system as _repo_system
from common_db.repo import subscriptions as _repo_subscriptions
from common_db.repo import users as _repo_users
from remnawave_client.api import (
    create_user,
    get_user_from_username,
    resolve_remnawave_user,
    update_user,
)
from subscription_delivery import build_remnawave_username
from ..notify_log import notify_log
from ..telemt_client import create_telemt_user, first_link, get_telemt_user
from ..tg_auth import TgUser, get_tg_user
from ..tg_channel import is_user_subscribed_to_news

router = APIRouter(prefix="/api/free", tags=["free"])
logger = logging.getLogger(__name__)


async def _persist_rw_uuid(user: User, rw_user: dict | None) -> None:
    if not rw_user or not rw_user.get("uuid") or rw_user.get("rw_id") is None:
        return
    async with async_session() as session:
        try:
            link = await _repo_subscriptions.attach(
                session, user_id=user.id, rw_id=int(rw_user["rw_id"]), source="miniapp_free"
            )
        except ValueError as exc:
            await session.rollback()
            await notify_log(
                "🚨 <b>FREE delivery ownership conflict</b>\n"
                f"DB user: <code>{user.id}</code>\n"
                f"rw_id: <code>{rw_user.get('rw_id')}</code>"
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT, "target_owner_conflict"
            ) from exc
        if link.is_primary:
            await _repo_users.persist_remnawave_uuid(
                session,
                tg_id=user.tg_id,
                vless_uuid=str(rw_user["uuid"]),
                username=user.username,
                rw_id=rw_user.get("rw_id"),
            )
        await session.commit()


async def _resolve_existing(user: User, tg: TgUser) -> dict | None:
    async with async_session() as session:
        primary = await _repo_subscriptions.get_primary(session, user.id)
    existing = await resolve_remnawave_user(
        rw_id=primary.rw_id if primary else user.rw_id,
        vless_uuid=user.vless_uuid,
        email=user.email,
        username=user.username,
        expected_telegram_id=tg.tg_id,
    )
    if existing is None and user.username:
        collision = await get_user_from_username(user.username)
        if collision:
            await notify_log(
                "⚠️ <b>legacy_username_collision</b>\n"
                f"DB user: <code>{user.id}</code>\n"
                f"TG: <code>{tg.tg_id}</code> @{user.username}\n"
                f"matched rw_id: <code>{collision.get('rw_id') or '—'}</code>"
            )
    return existing


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
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")
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
    existing = await _resolve_existing(user, tg)
    if existing and existing.get("uuid"):
        await _persist_rw_uuid(user, existing)
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
        existing = await get_telemt_user(user.username or f"user_{user.id}")
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

    existing = await _resolve_existing(user, tg)
    if existing and existing.get("uuid"):
        squads = {s.lower() for s in existing.get("active_squads", [])}
        is_free = bool(free_squad and free_squad.lower() in squads)
        is_active_pro = existing.get("status") == "active" and existing.get("data_limit") is None
        if is_active_pro or is_free:
            await _persist_rw_uuid(user, existing)
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
        await _persist_rw_uuid(user, updated)
        return ClaimResponse(
            ok=True,
            subscription_url=updated.get("subscription_url"),
            days=days,
        )

    async with async_session() as session:
        start = await _repo_subscriptions.count_for_user(session, user.id)
    marker = f"provisioning:free:{user.id}"
    created = None
    for ordinal in range(start, start + 100):
        candidate = build_remnawave_username(user.username, user.id, ordinal)
        occupied = await get_user_from_username(candidate)
        if occupied:
            if marker in str(occupied.get("description") or ""):
                created = occupied
                break
            continue
        try:
            created = await create_user(
                username=candidate,
                days=days,
                limit_gb=limit_gb,
                descr=(
                    f"{marker}; db_user_id:{user.id}; tg_id:{tg.tg_id}; "
                    f"source:miniapp; tg_username:{user.username or 'none'}; "
                    "Free trial via miniapp"
                ),
                email=f"{candidate}@miniapp.xyz",
                telegram_id=tg.tg_id,
                squad_id=free_squad,
            )
        except Exception:
            appeared = await get_user_from_username(candidate)
            if appeared and marker in str(appeared.get("description") or ""):
                created = appeared
            elif appeared:
                continue
            else:
                raise
        appeared = await get_user_from_username(candidate)
        if appeared:
            if marker in str(appeared.get("description") or ""):
                created = appeared
                break
            created = None
            continue
        if not created:
            return ClaimResponse(ok=False, detail="create_failed")
        break
    if not created:
        return ClaimResponse(ok=False, detail="rw_username_allocation_failed")
    await _persist_rw_uuid(user, created)
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

    telemt_username = user.username or f"user_{user.id}"
    existing = await get_telemt_user(telemt_username)
    if existing:
        link = first_link(existing.get("links"))
        return TelemtClaimResponse(ok=True, link=link, detail="already_active")

    # Singleton auto-seed: get_telmt_free_params creates the row on a
    # fresh DB so we always have the canonical defaults.
    async with async_session() as session:
        params = await _repo_system.get_telmt_free_params(session)
        await session.commit()

    expire_days = params.expire_days or 30
    max_tcp = params.max_tcp_conns
    max_ips = params.max_unique_ips
    quota = params.data_quota_bytes
    rate_up = params.rate_limit_up_bps
    rate_down = params.rate_limit_down_bps

    try:
        created = await create_telemt_user(
            username=telemt_username,
            expire_days=expire_days,
            max_tcp_conns=max_tcp,
            max_unique_ips=max_ips,
            data_quota_bytes=quota,
            rate_limit_up_bps=rate_up,
            rate_limit_down_bps=rate_down,
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
