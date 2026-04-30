import time

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..config import (
    get_agreement_url,
    get_bot_url,
    get_news_url,
    get_policy_url,
    get_rw_free_id,
    get_rw_pro_id,
)
from ..database.models import User
from ..database.session import async_session
from ..remnawave_client import get_user_devices_count, get_user_from_username
from ..schemas.me import LinksInfo, MeResponse, SubscriptionInfo, UserInfo
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api", tags=["me"])


def _links() -> LinksInfo:
    return LinksInfo(
        bot_url=get_bot_url(),
        policy_url=get_policy_url(),
        agreement_url=get_agreement_url(),
        news_url=get_news_url(),
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
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))

    if not user:
        return MeResponse(registered=False, links=links)

    user_info = UserInfo(
        tg_id=user.tg_id,
        username=user.username,
        language=user.language,
    )

    if user.is_banned:
        return MeResponse(registered=True, user=user_info, links=links)

    rem_user = await get_user_from_username(user.username) if user.username else None

    if not rem_user:
        return MeResponse(registered=True, user=user_info, links=links)

    devices_count = (
        await get_user_devices_count(rem_user["uuid"]) if rem_user.get("uuid") else 0
    )

    subscription = SubscriptionInfo(
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
        links=links,
    )
