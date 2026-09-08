"""Common ticket actions for Telegram and authenticated web clients."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update, select
from common_db.models import SupportTicket, User
from common_db.support_workflow import can_reopen, now_iso
from .database.session import async_session


class ReadBody(BaseModel):
    message_id: int = Field(ge=0)


class OutcomeBody(BaseModel):
    action: str


def register_actions(router, authenticate, *, telegram: bool, notify):
    async def owner(session, identity):
        if telegram:
            user = await session.scalar(select(User).where(User.tg_id == identity.tg_id))
            if not user:
                raise HTTPException(404, "user not found")
            return user.id
        return identity.id

    @router.post("/tickets/{ticket_id}/read")
    async def mark_read(ticket_id: int, body: ReadBody, identity=Depends(authenticate)):
        async with async_session() as session:
            user_id = await owner(session, identity)
            ticket = await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id))
            if not ticket:
                raise HTTPException(404, "ticket not found")
            cursor = min(body.message_id, ticket.last_admin_message_id)
            await session.execute(update(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_read_id < cursor).values(user_read_id=cursor))
            await session.commit()
        return {"ok": True}

    @router.post("/tickets/{ticket_id}/outcome")
    async def outcome(ticket_id: int, body: OutcomeBody, identity=Depends(authenticate)):
        async with async_session() as session:
            user_id = await owner(session, identity)
            # Serialize against simultaneous replies/status changes.
            ticket = await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id).with_for_update())
            if not ticket:
                raise HTTPException(404, "ticket not found")
            if body.action == "resolved":
                if ticket.status != "closed":
                    ticket.status = "closed"
                    ticket.closed_at = now_iso()
            elif body.action == "reopen":
                if ticket.status == "closed" and not can_reopen(ticket):
                    raise HTTPException(409, "reopen period expired")
                ticket.status = "open"
                ticket.closed_at = None
                ticket.waiting_since = now_iso()
            else:
                raise HTTPException(400, "invalid action")
            ticket.updated_at = now_iso()
            await session.commit()
        if body.action == "reopen":
            await notify(ticket_id, None, "Проблема осталась / Problem remains")
        return {"ok": True}
