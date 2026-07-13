"""TG Admin router — channel posts, sub-clean, telemt-clean.

All Telegram API calls go directly via httpx (same pattern as support.py).
Remnawave calls use remnawave_client (installed in dashboard/Dockerfile).
"""

import asyncio
import logging
import re
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from common_db.repo.users import PAID_ORDER_STATUSES

from ..auth import get_current_user
from ..config import (
    get_news_id, get_news_url,
    get_remnawave_token, get_remnawave_url,
    get_telemt_header, get_telemt_server,
)
from ..database.models import DisabledUser, Transaction, User
from ..database.session import async_session
from ..telegram import tg_send, tg_url, tg_bot_open_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tg-admin", tags=["tg-admin"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _check_subscribed(tg_id: int, news_id: int, sem: asyncio.Semaphore) -> bool:
    """Return True if user is subscribed to the channel (or on API error — safer)."""
    async with sem:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    tg_url("getChatMember"),
                    params={"chat_id": news_id, "user_id": tg_id},
                )
            if r.status_code != 200:
                return True  # treat error as subscribed
            status = r.json().get("result", {}).get("status", "left")
            return status in ("member", "creator", "administrator")
        except Exception:
            return True


def _telemt_headers() -> dict:
    h = {"Content-Type": "application/json"}
    hdr = get_telemt_header()
    if hdr:
        h["Authorization"] = hdr
    return h


def _rw_client():
    from remnawave_client import configure
    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id="",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Channel post
# ──────────────────────────────────────────────────────────────────────────────

class ChannelPostRequest(BaseModel):
    text: str
    attach_button: bool = False


@router.post("/channel-post")
async def channel_post(body: ChannelPostRequest, _: str = Depends(get_current_user)):
    if not body.text.strip():
        raise HTTPException(400, "Text is required")

    news_id = get_news_id()
    if not news_id:
        raise HTTPException(503, "news_id not configured")

    reply_markup = None
    if body.attach_button:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(tg_url("getMe"))
            if r.status_code == 200:
                username = r.json().get("result", {}).get("username", "")
                if username:
                    reply_markup = {"inline_keyboard": [[
                        {"text": "Открыть бота", "url": tg_bot_open_url(username)}
                    ]]}
        except Exception:
            pass

    ok = await tg_send(int(news_id), body.text, reply_markup)
    if not ok:
        raise HTTPException(502, "Failed to post to channel")
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────────
# FREE users sub-check (sub-clean)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/sub-clean/scan")
async def sub_clean_scan(_: str = Depends(get_current_user)):
    news_id = get_news_id()
    if not news_id:
        raise HTTPException(503, "news_id not configured")

    now = datetime.now().isoformat(timespec="seconds")

    async with async_session() as session:
        paid_sq = (
            select(Transaction.user_id)
            .where(
                Transaction.order_status.in_(list(PAID_ORDER_STATUSES)),
                Transaction.expire_date > now,
            )
            .scalar_subquery()
        )
        result = await session.execute(
            select(User).where(
                User.api_provider == "remnawave",
                User.vless_uuid.is_not(None),
                User.vip == 0,
                User.is_banned != True,
                User.tg_id.is_not(None),
                ~User.id.in_(paid_sq),
            )
        )
        users = [
            {"tg_id": u.tg_id, "username": u.username, "vless_uuid": u.vless_uuid}
            for u in result.scalars().all()
        ]

    sem = asyncio.Semaphore(20)
    checks = await asyncio.gather(
        *[_check_subscribed(u["tg_id"], int(news_id), sem) for u in users],
        return_exceptions=True,
    )

    to_disable = []
    errors = 0
    for user, subscribed in zip(users, checks):
        if isinstance(subscribed, Exception):
            errors += 1
        elif not subscribed:
            to_disable.append(user)

    return {"total_checked": len(users), "to_disable": to_disable, "errors": errors}


class SubCleanExecuteRequest(BaseModel):
    tg_ids: list[int]


@router.post("/sub-clean/execute")
async def sub_clean_execute(body: SubCleanExecuteRequest, _: str = Depends(get_current_user)):
    if not body.tg_ids:
        raise HTTPException(400, "No users to disable")

    news_url = get_news_url()
    rw = _rw_client()

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.tg_id.in_(body.tg_ids))
        )
        users = {u.tg_id: u for u in result.scalars().all()}

    notification_kb = None
    if news_url:
        notification_kb = {"inline_keyboard": [
            [{"text": "Подписаться на канал", "url": news_url}],
            [{"text": "Я подписался!", "callback_data": "subcheck_reactivate"}],
        ]}

    disabled = notified = errors = 0

    for tg_id in body.tg_ids:
        user = users.get(tg_id)
        if not user or not user.vless_uuid:
            errors += 1
            continue
        try:
            rw_user = await rw.get_user_by_uuid(user.vless_uuid)
            current_status = (rw_user or {}).get("status", "active")

            # Disable in RemnaWave first; only write to DB on success
            rw_result = await rw.update_user(user_uuid=user.vless_uuid, status="disabled")
            if not rw_result:
                errors += 1
                continue
            disabled += 1

            async with async_session() as session:
                existing = await session.scalar(
                    select(DisabledUser).where(DisabledUser.tg_id == tg_id)
                )
                if not existing:
                    session.add(DisabledUser(
                        tg_id=tg_id,
                        original_status=current_status,
                        disabled_at=datetime.now().isoformat(timespec="seconds"),
                    ))
                    await session.commit()
        except Exception as e:
            logger.error("sub-clean disable error tg_id=%s: %s", tg_id, e)
            errors += 1
            continue

        ok = await tg_send(
            tg_id,
            (
                "<b>Доступ к VPN приостановлен</b>\n\n"
                "Вы отписались от нашего канала.\n"
                "Подпишитесь снова, чтобы восстановить бесплатный доступ."
            ),
            notification_kb,
        )
        if ok:
            notified += 1

    return {"disabled": disabled, "notified": notified, "errors": errors}


# ──────────────────────────────────────────────────────────────────────────────
# Telemt clean
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/telemt-clean/scan")
async def telemt_clean_scan(_: str = Depends(get_current_user)):
    news_id = get_news_id()
    if not news_id:
        raise HTTPException(503, "news_id not configured")

    base = get_telemt_server()
    if not base:
        raise HTTPException(503, "telemt_server not configured")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{base.rstrip('/')}/v1/users", headers=_telemt_headers())
    if r.status_code != 200:
        raise HTTPException(502, "Failed to fetch Telemt users")

    raw = r.json()
    # Telemt returns {ok, data: {users: [...]}} or {ok, data: [...]}
    data = raw.get("data", {})
    telemt_users: list[dict] = data.get("users", data) if isinstance(data, dict) else data
    if not isinstance(telemt_users, list):
        telemt_users = []

    usernames = [u.get("username") for u in telemt_users if u.get("username")]
    if not usernames:
        return {"total_checked": 0, "to_delete": [], "errors": 0}

    now = datetime.now().isoformat(timespec="seconds")

    async with async_session() as session:
        result = await session.execute(select(User).where(User.username.in_(usernames)))
        db_users: dict[str, User] = {u.username: u for u in result.scalars().all()}

        paid_result = await session.execute(
            select(Transaction.user_id).where(
                Transaction.user_id.in_([u.id for u in db_users.values()]),
                Transaction.order_status.in_(list(PAID_ORDER_STATUSES)),
                Transaction.expire_date > now,
            )
        )
        paid_ids = {r[0] for r in paid_result.fetchall()}

    to_check = []
    for username in usernames:
        db_user = db_users.get(username)
        if not db_user or not db_user.tg_id:
            continue
        if db_user.vip and db_user.vip > 0:
            continue
        if db_user.id in paid_ids:
            continue
        to_check.append({"tg_id": db_user.tg_id, "username": username})

    sem = asyncio.Semaphore(20)
    checks = await asyncio.gather(
        *[_check_subscribed(u["tg_id"], int(news_id), sem) for u in to_check],
        return_exceptions=True,
    )

    to_delete = []
    errors = 0
    for user, subscribed in zip(to_check, checks):
        if isinstance(subscribed, Exception):
            errors += 1
        elif not subscribed:
            to_delete.append(user)

    return {"total_checked": len(to_check), "to_delete": to_delete, "errors": errors}


class TelmtCleanExecuteRequest(BaseModel):
    usernames: list[str]


@router.post("/telemt-clean/execute")
async def telemt_clean_execute(body: TelmtCleanExecuteRequest, _: str = Depends(get_current_user)):
    if not body.usernames:
        raise HTTPException(400, "No users to delete")

    base = get_telemt_server()
    if not base:
        raise HTTPException(503, "telemt_server not configured")

    news_url = get_news_url()

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username.in_(body.usernames))
        )
        db_users = {u.username: u for u in result.scalars().all()}

    notification_kb = None
    if news_url:
        notification_kb = {"inline_keyboard": [
            [{"text": "Подписаться на канал", "url": news_url}],
            [{"text": "Получить доступ", "callback_data": "Telemt_Free"}],
        ]}

    deleted = notified = errors = 0

    for username in body.usernames:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.delete(
                    f"{base.rstrip('/')}/v1/users/{username}",
                    headers=_telemt_headers(),
                )
            if r.status_code in (200, 204):
                deleted += 1
            else:
                errors += 1
                continue
        except Exception as e:
            logger.error("telemt-clean delete error %s: %s", username, e)
            errors += 1
            continue

        db_user = db_users.get(username)
        if db_user and db_user.tg_id:
            ok = await tg_send(
                db_user.tg_id,
                (
                    "<b>Доступ к Telemt удалён</b>\n\n"
                    "Вы отписались от нашего канала.\n"
                    "Подпишитесь снова, чтобы получить доступ."
                ),
                notification_kb,
            )
            if ok:
                notified += 1

    return {"deleted": deleted, "notified": notified, "errors": errors}
