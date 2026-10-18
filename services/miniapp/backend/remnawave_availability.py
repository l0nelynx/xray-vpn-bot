"""Hybrid monitoring: periodic authenticated probe plus immediate request failures.

The singleton row serializes transitions/probes across API workers. Notices are
committed with transitions and retried independently of the user's request.
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from common_db.models import RemnawaveAvailability, RemnawaveNotice, RemnawaveRecoverySubscription
from common_db.repo import users
from remnawave_client.api import _client

from .config import get_admin_bot_token, get_admin_id, get_bot_token, get_remnawave_token, get_remnawave_url
from .database.session import async_session
from .tg_auth import TgUser, get_tg_user

logger = logging.getLogger(__name__)
HEALTHY_INTERVAL = 60
OUTAGE_INTERVAL = 15
PROBE_TIMEOUT = 5
_wake: asyncio.Event | None = None
_notice_wake: asyncio.Event | None = None
router = APIRouter(prefix="/api/remnawave", tags=["availability"])


async def _state(session):
    # Seeded by migration, so concurrent initial requests cannot race to insert.
    state = await session.scalar(select(RemnawaveAvailability).where(RemnawaveAvailability.id == 1).with_for_update())
    if state is None:
        raise RuntimeError("Remnawave availability migration has not been applied")
    return state


def _notice(session, key: str, text: str, *, tg_id: int | None = None):
    session.add(RemnawaveNotice(key=key, text=text, admin=tg_id is None, tg_id=tg_id))


def _start_incident(session, state):
    if not state.unavailable:
        state.unavailable = True
        state.incident += 1
        _notice(session, f"outage:{state.incident}",
                f"🔴 Remnawave недоступен. Сбой #{state.incident}.\n"
                "Miniapp показывает сообщение о технических работах. Проверяем восстановление каждые 15 секунд.")


async def record_failure():
    async with async_session() as session:
        state = await _state(session)
        _start_incident(session, state)
        state.next_probe_at = min(state.next_probe_at, time.time() + OUTAGE_INTERVAL)
        await session.commit()
    if _wake is not None:
        _wake.set()
    if _notice_wake is not None:
        _notice_wake.set()


async def probe():
    # Exercises authentication, API and database, using the same SDK as requests.
    # A one-item stream is cheap and also works when there are no panel users.
    await asyncio.wait_for(_client().sdk.users.get_users_stream(size=1), timeout=PROBE_TIMEOUT)


async def check_availability():
    if not get_remnawave_url() or not get_remnawave_token():
        return
    async with async_session() as session:
        state = await _state(session)
        if state.next_probe_at > time.time():
            return
        try:
            await probe()
        except Exception as exc:
            # Do not log SDK exception strings: they can include URLs/credentials.
            logger.warning("Remnawave availability probe failed (%s)", type(exc).__name__)
            _start_incident(session, state)
        else:
            if state.unavailable:
                state.unavailable = False
                _notice(session, f"recovery:{state.incident}", f"🟢 Remnawave снова доступен. Сбой #{state.incident} завершён.")
                # Only an authenticated probe closes an incident; unrelated
                # successful requests cannot prematurely trigger recovery.
                watchers = (await session.scalars(select(RemnawaveRecoverySubscription).where(
                    RemnawaveRecoverySubscription.incident == state.incident))).all()
                for watcher in watchers:
                    text = ("The maintenance is complete. You can use the miniapp again." if watcher.language == "en"
                            else "✅ Технические работы завершены. Miniapp снова работает — можно вернуться к подписке.")
                    _notice(session, f"user:{state.incident}:{watcher.tg_id}", text, tg_id=watcher.tg_id)
                await session.execute(delete(RemnawaveRecoverySubscription).where(
                    RemnawaveRecoverySubscription.incident == state.incident))
        state.next_probe_at = time.time() + (OUTAGE_INTERVAL if state.unavailable else HEALTHY_INTERVAL)
        await session.commit()
    if _notice_wake is not None:
        _notice_wake.set()


async def deliver_notices():
    # Bound each batch and yield between sends. SKIP LOCKED prevents multiple
    # workers from sending the same pending notice concurrently.
    for _ in range(30):
        async with async_session() as session:
            notice = await session.scalar(select(RemnawaveNotice).where(
                RemnawaveNotice.next_attempt_at <= time.time()).order_by(RemnawaveNotice.admin.desc(), RemnawaveNotice.next_attempt_at, RemnawaveNotice.key)
                .limit(1).with_for_update(skip_locked=True))
            if notice is None:
                return
            token = get_admin_bot_token() if notice.admin else get_bot_token()
            chat_id = get_admin_id() if notice.admin else notice.tg_id
            delivered = False
            permanent_failure = False
            if token and chat_id:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        response = await client.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                                     json={"chat_id": chat_id, "text": notice.text})
                    body = response.json()
                    delivered = response.is_success and body.get("ok") is True
                    # A blocked bot/deleted user cannot receive future retries.
                    permanent_failure = not notice.admin and body.get("error_code") in {400, 403}
                except Exception:
                    logger.warning("Remnawave notification delivery failed")
            if delivered or permanent_failure:
                await session.delete(notice)
            else:
                notice.next_attempt_at = time.time() + 30
            await session.commit()


async def _delivery_loop():
    while True:
        _notice_wake.clear()
        try:
            await deliver_notices()
        except Exception:
            logger.exception("Remnawave notice iteration failed")
        try:
            await asyncio.wait_for(_notice_wake.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass


async def monitor_loop():
    global _wake, _notice_wake
    _wake = asyncio.Event()
    _notice_wake = asyncio.Event()
    delivery_task = asyncio.create_task(_delivery_loop())
    try:
        while True:
            _wake.clear()
            try:
                await check_availability()
            except Exception:
                logger.exception("Remnawave monitor iteration failed")
            try:
                await asyncio.wait_for(_wake.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
    finally:
        delivery_task.cancel()
        try:
            await delivery_task
        except asyncio.CancelledError:
            pass
        _wake = None
        _notice_wake = None


class RecoveryRequest(BaseModel):
    language: str = "ru"


@router.get("/availability")
async def availability(tg: TgUser = Depends(get_tg_user)):
    async with async_session() as session:
        state = await session.get(RemnawaveAvailability, 1)
        watcher = await session.get(RemnawaveRecoverySubscription, (state.incident, tg.tg_id)) if state else None
        return {"unavailable": bool(state and state.unavailable), "subscribed": watcher is not None}


@router.post("/recovery-notification")
async def subscribe(body: RecoveryRequest, tg: TgUser = Depends(get_tg_user)):
    if not get_bot_token():
        raise HTTPException(503, detail={"code": "notifications_unavailable"})
    async with async_session() as session:
        user = await users.get_user_by_tg_id(session, tg.tg_id)
        if user is None or user.is_banned:
            raise HTTPException(403, detail={"code": "user_unavailable"})
        state = await _state(session)
        if not state.unavailable:
            return {"unavailable": False, "subscribed": False}
        if await session.get(RemnawaveRecoverySubscription, (state.incident, tg.tg_id)) is None:
            session.add(RemnawaveRecoverySubscription(incident=state.incident, tg_id=tg.tg_id,
                                                     language="en" if body.language == "en" else "ru"))
        await session.commit()
        return {"unavailable": True, "subscribed": True}
