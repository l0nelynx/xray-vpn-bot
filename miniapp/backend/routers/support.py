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
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
        if not user:
            return []
        result = await session.execute(
            select(SupportTicket)
            .where(SupportTicket.user_id == user.id)
            .order_by(desc(SupportTicket.created_at))
        )
        tickets = result.scalars().all()
        out: list[TicketSummary] = []
        for t in tickets:
            last = await session.scalar(
                select(SupportMessage.text)
                .where(SupportMessage.ticket_id == t.id)
                .order_by(desc(SupportMessage.created_at))
                .limit(1)
            )
            preview = (last or t.message)[:120]
            out.append(TicketSummary(
                id=t.id, subject=t.subject, status=t.status,
                created_at=t.created_at, updated_at=t.updated_at,
                last_message_preview=preview,
            ))
        return out


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: int,
    tg: TgUser = Depends(get_tg_user),
) -> TicketDetail:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        ticket = await session.scalar(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        if not ticket or ticket.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        result = await session.execute(
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket.id)
            .order_by(SupportMessage.created_at)
        )
        messages = [
            MessageItem(id=m.id, sender=m.sender, text=m.text, created_at=m.created_at)
            for m in result.scalars().all()
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
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")

        open_count = await session.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(SupportTicket.user_id == user.id, SupportTicket.status == "open")
        ) or 0
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
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
        ticket = await session.scalar(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
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
