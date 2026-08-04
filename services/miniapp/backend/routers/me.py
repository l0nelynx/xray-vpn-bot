import time

from fastapi import APIRouter, Depends, HTTPException

from ..config import (
    get_agreement_url,
    get_bot_url,
    get_branding_name,
    get_news_url,
    get_policy_url,
    get_rw_free_id,
    get_rw_pro_id,
    get_support_bot_link,
)
from ..database.session import async_session

from common_db.repo import users as _repo_users
from common_db.repo import subscriptions as _repo_subscriptions
from remnawave_client.api import get_user_devices_count_by_id, resolve_remnawave_user
from ..android.managed_subscriptions_router import _serialize
from ..schemas.me import LanguageUpdate, LinksInfo, MeResponse, SubscriptionInfo, UserInfo
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api", tags=["me"])


def _links() -> LinksInfo:
    return LinksInfo(
        bot_url=get_bot_url(),
        policy_url=get_policy_url(),
        agreement_url=get_agreement_url(),
        news_url=get_news_url(),
        branding_name=get_branding_name(),
        support_bot_link=get_support_bot_link(),
    )


def _resolve_tariff(active_squads: list[str]) -> str:
    pro_id = get_rw_pro_id()
    free_id = get_rw_free_id()
    squads_lower = {s.lower() for s in active_squads}
    if pro_id and pro_id.lower() in squads_lower:
        return "Premium"
    if free_id and free_id.lower() in squads_lower:
        return "Free"
    return "—"


def _days_left(expire_ts: int | None) -> int:
    if expire_ts is None:
        return 0
    diff = round((expire_ts - time.time()) / 86400)
    return max(0, diff)


def _expire_iso(expire_ts: int | None) -> str | None:
    if expire_ts is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(expire_ts, tz=timezone.utc).isoformat()


@router.get("/me", response_model=MeResponse)
async def get_me(tg: TgUser = Depends(get_tg_user)) -> MeResponse:
    links = _links()

    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        subscription_rows = (
            await _repo_subscriptions.list_for_user(session, user.id) if user else []
        )

    if not user:
        return MeResponse(registered=False, links=links)

    user_info = UserInfo(
        tg_id=user.tg_id,
        username=user.username,
        language=user.language,
        has_email=bool(user.email),
    )

    if user.is_banned:
        return MeResponse(registered=True, user=user_info, links=links)

    primary_row = next((row for row in subscription_rows if row.is_primary), None)
    if primary_row is not None:
        managed = await _serialize(primary_row)
        subscription = SubscriptionInfo(
            subscription_id=managed.id,
            label=managed.label,
            tariff=managed.tariff,
            status=managed.status,
            days_left=managed.days_left,
            expire_iso=managed.expire_iso,
            data_limit_gb=managed.data_limit_gb,
            traffic_used_gb=managed.traffic_used_gb,
            devices_count=managed.devices_count,
            subscription_url=managed.subscription_url,
        )
        return MeResponse(
            registered=True,
            user=user_info,
            subscription=subscription,
            subscriptions_count=len(subscription_rows),
            links=links,
        )

    # Legacy fallback until every users.rw_id row has been backfilled into
    # user_subscriptions. Pass the trusted Telegram id so a username-only match
    # is accepted only when the panel account is actually owned by this user —
    # otherwise a coincidental @username collision would expose a foreign
    # subscription_url.
    rem_user = await resolve_remnawave_user(
        rw_id=user.rw_id,
        email=user.email,
        username=user.username,
        expected_telegram_id=tg.tg_id,
    )

    if not rem_user:
        return MeResponse(
            registered=True,
            user=user_info,
            subscriptions_count=len(subscription_rows),
            links=links,
        )

    resolved_rw_id = rem_user.get("rw_id")
    devices_count = (
        await get_user_devices_count_by_id(resolved_rw_id)
        if resolved_rw_id is not None else 0
    )

    subscription = SubscriptionInfo(
        subscription_id=None,
        label=None,
        tariff=_resolve_tariff(rem_user.get("active_squads", [])),
        status=rem_user.get("status"),
        days_left=_days_left(rem_user.get("expire")),
        expire_iso=_expire_iso(rem_user.get("expire")),
        data_limit_gb=rem_user.get("data_limit"),
        traffic_used_gb=rem_user.get("traffic_used", 0),
        devices_count=devices_count,
        subscription_url=rem_user.get("subscription_url"),
    )

    return MeResponse(
        registered=True,
        user=user_info,
        subscription=subscription,
        subscriptions_count=len(subscription_rows),
        links=links,
    )


@router.patch("/me/language", response_model=UserInfo)
async def patch_language(
    body: LanguageUpdate,
    tg: TgUser = Depends(get_tg_user),
) -> UserInfo:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.language = body.language
        await session.commit()
        await session.refresh(user)
        return UserInfo(
            tg_id=user.tg_id,
            username=user.username,
            language=user.language,
            has_email=bool(user.email),
        )
