from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..config import get_bot_token
from ..database.models import SupportTicket, SupportMessage, User
from ..database.session import async_session

router = APIRouter(prefix="/api/support", tags=["support"])

VALID_STATUSES = {"open", "in_progress", "closed"}


class ReplyBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class StatusBody(BaseModel):
    status: str


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@router.get("/tickets")
async def list_tickets(
    status: str = Query("all"),
    search: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        stmt = select(SupportTicket, User.tg_id).join(User, User.id == SupportTicket.user_id)
        count_stmt = select(func.count()).select_from(SupportTicket)
        if status != "all":
            if status not in VALID_STATUSES:
                raise HTTPException(400, "invalid status")
            stmt = stmt.where(SupportTicket.status == status)
            count_stmt = count_stmt.where(SupportTicket.status == status)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(SupportTicket.subject.ilike(like))
            count_stmt = count_stmt.where(SupportTicket.subject.ilike(like))
        total = await session.scalar(count_stmt) or 0
        stmt = stmt.order_by(desc(SupportTicket.updated_at)).offset((page - 1) * per_page).limit(per_page)
        rows = (await session.execute(stmt)).all()
        items = [
            {
                "id": t.id,
                "user_id": t.user_id,
                "tg_id": tg_id,
                "username": t.username,
                "subject": t.subject,
                "status": t.status,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t, tg_id in rows
        ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .options(selectinload(SupportTicket.messages))
        )
        ticket = await session.scalar(stmt)
        if not ticket:
            raise HTTPException(404, "ticket not found")
        user = await session.scalar(select(User).where(User.id == ticket.user_id))
        messages = sorted(ticket.messages, key=lambda m: m.id)
        return {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "tg_id": user.tg_id if user else None,
            "username": ticket.username,
            "subject": ticket.subject,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "messages": [
                {"id": m.id, "sender": m.sender, "text": m.text, "created_at": m.created_at}
                for m in messages
            ],
        }


@router.post("/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: int, body: ReplyBody, _: str = Depends(get_current_user)):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "empty text")
    async with async_session() as session:
        ticket = await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id))
        if not ticket:
            raise HTTPException(404, "ticket not found")
        user = await session.scalar(select(User).where(User.id == ticket.user_id))
        now = _now_iso()
        msg = SupportMessage(ticket_id=ticket.id, sender="admin", text=text, created_at=now)
        session.add(msg)
        ticket.updated_at = now
        if ticket.status == "open":
            ticket.status = "in_progress"
        await session.commit()
        tg_id = user.tg_id if user else None

    if tg_id:
        token = get_bot_token()
        if token:
            notify = (
                f"💬 Ответ по обращению #{ticket_id}: <b>{ticket.subject}</b>\n\n{text}"
            )
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": tg_id, "text": notify, "parse_mode": "HTML"},
                    )
            except Exception:
                pass
    return {"ok": True}


@router.patch("/tickets/{ticket_id}")
async def update_status(ticket_id: int, body: StatusBody, _: str = Depends(get_current_user)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, "invalid status")
    async with async_session() as session:
        ticket = await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id))
        if not ticket:
            raise HTTPException(404, "ticket not found")
        ticket.status = body.status
        ticket.updated_at = _now_iso()
        await session.commit()
    return {"ok": True}
