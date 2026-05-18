import asyncio
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select

from ..config import get_admin_bot_token, get_admin_id
from ..database.models import SupportMessage, SupportTicket, User
from ..database.session import async_session
from ..schemas.support import (
    MessageItem,
    TicketCreate,
    TicketDetail,
    TicketReply,
    TicketSummary,
)
from ..tg_auth import TgUser, get_tg_user

# common_db helpers fix the 1+N round-trips on /tickets and centralise the
# user-by-tg_id / ticket-by-id lookups.
from common_db.repo import support as _repo_support
from common_db.repo import users as _repo_users

router = APIRouter(prefix="/api/support", tags=["support"])
logger = logging.getLogger(__name__)

MAX_OPEN_TICKETS = 5
NOTIFY_TIMEOUT = 5.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _notify_admin(ticket_id: int, username: str | None, subject: str) -> None:
    token = get_admin_bot_token()
    admin_id = get_admin_id()
    if not token or not admin_id:
        return
    text = (
        f"🆘 New support ticket #{ticket_id}\n"
        f"From: @{username or '—'}\n"
        f"Subject: {subject}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=NOTIFY_TIMEOUT) as client:
            await client.post(url, json={"chat_id": admin_id, "text": text})
    except Exception as e:
        logger.warning("admin notification failed for ticket %s: %s", ticket_id, e)


@router.get("/tickets", response_model=list[TicketSummary])
async def list_tickets(tg: TgUser = Depends(get_tg_user)) -> list[TicketSummary]:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            return []
        # 2 queries instead of 1+N: the helper batches the
        # last-message-per-ticket lookup via ROW_NUMBER PARTITION BY.
        rows = await _repo_support.list_user_tickets_with_last_message(
            session, user.id
        )
        return [
            TicketSummary(
                id=row.ticket.id,
                subject=row.ticket.subject,
                status=row.ticket.status,
                created_at=row.ticket.created_at,
                updated_at=row.ticket.updated_at,
                last_message_preview=((row.last_message_text or row.ticket.message)[:120]),
            )
            for row in rows
        ]


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: int,
    tg: TgUser = Depends(get_tg_user),
) -> TicketDetail:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id)
        if not ticket or ticket.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        msgs = await _repo_support.list_messages_for_ticket(session, ticket.id)
        messages = [
            MessageItem(id=m.id, sender=m.sender, text=m.text, created_at=m.created_at)
            for m in msgs
        ]
        return TicketDetail(
            id=ticket.id,
            subject=ticket.subject,
            status=ticket.status,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            messages=messages,
        )


@router.post("/tickets", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    tg: TgUser = Depends(get_tg_user),
) -> TicketDetail:
    now = _now_iso()
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")

        open_count = await _repo_support.count_open_tickets_for_user(
            session, user.id
        )
        if open_count >= MAX_OPEN_TICKETS:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many open tickets")

        ticket = SupportTicket(
            user_id=user.id,
            username=tg.username,
            subject=body.subject.strip(),
            message=body.message.strip(),
            status="open",
            created_at=now,
            updated_at=now,
        )
        session.add(ticket)
        await session.flush()

        first_message = SupportMessage(
            ticket_id=ticket.id,
            sender="user",
            text=body.message.strip(),
            created_at=now,
        )
        session.add(first_message)
        await session.commit()

        ticket_id = ticket.id
        subject = ticket.subject

    asyncio.create_task(_notify_admin(ticket_id, tg.username, subject))

    return TicketDetail(
        id=ticket_id,
        subject=subject,
        status="open",
        created_at=now,
        updated_at=now,
        messages=[
            MessageItem(id=first_message.id, sender="user", text=body.message.strip(), created_at=now)
        ],
    )


async def _notify_admin_reply(ticket_id: int, username: str | None, text: str) -> None:
    token = get_admin_bot_token()
    admin_id = get_admin_id()
    if not token or not admin_id:
        return
    preview = text if len(text) <= 300 else text[:297] + "..."
    body = (
        f"💬 New reply on ticket #{ticket_id}\n"
        f"From: @{username or '—'}\n\n"
        f"{preview}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=NOTIFY_TIMEOUT) as client:
            await client.post(url, json={"chat_id": admin_id, "text": body})
    except Exception as e:
        logger.warning("admin reply notification failed for ticket %s: %s", ticket_id, e)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=MessageItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_user_message(
    ticket_id: int,
    body: TicketReply,
    tg: TgUser = Depends(get_tg_user),
) -> MessageItem:
    text = body.text.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty message")
    now = _now_iso()
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id)
        if not ticket or ticket.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        if ticket.status == "closed":
            raise HTTPException(status.HTTP_409_CONFLICT, "ticket is closed")

        msg = SupportMessage(
            ticket_id=ticket.id,
            sender="user",
            text=text,
            created_at=now,
        )
        session.add(msg)
        ticket.updated_at = now
        await session.commit()
        msg_id = msg.id

    asyncio.create_task(_notify_admin_reply(ticket_id, tg.username, text))

    return MessageItem(id=msg_id, sender="user", text=text, created_at=now)
