import logging
from datetime import datetime, timezone
from html import escape
from common_db.support_delivery import send_notification, ticket_keyboard
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_, cast, String, case, update
from common_db.support_workflow import metadata, record_message
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..config import get_config, get_bot_token, get_support_uploads_dir
from ..database.models import SupportTicket, SupportMessage, User
from ..database.session import async_session

from common_db.repo import support as _repo_support
from common_db.repo import users as _repo_users
from support_attachments import AttachmentValidationError, validate_and_save_attachments

router = APIRouter(prefix="/api/support", tags=["support"])
logger = logging.getLogger(__name__)

VALID_STATUSES = {"open", "in_progress", "waiting_user", "closed"}


class StatusBody(BaseModel):
    status: str


class ReadBody(BaseModel):
    message_id: int = Field(ge=0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_TICKET_SORT_COLUMNS = {
    "id": SupportTicket.id,
    "subject": SupportTicket.subject,
    "username": SupportTicket.username,
    "status": SupportTicket.status,
    "created_at": SupportTicket.created_at,
    "updated_at": SupportTicket.updated_at,
}


@router.get("/tickets")
async def list_tickets(
    status: str = Query("all"),
    queue: str = Query("all"),
    search: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("updated_at"),
    order: str = Query("desc"),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        stmt = select(SupportTicket, User.tg_id).join(User, User.id == SupportTicket.user_id)
        counts = dict((await session.execute(select(SupportTicket.status, func.count()).group_by(SupportTicket.status))).all())
        counters = {"needs_reply": counts.get("open", 0) + counts.get("in_progress", 0), "waiting_user": counts.get("waiting_user", 0), "closed": counts.get("closed", 0)}
        counters["active"] = counters["needs_reply"] + counters["waiting_user"]
        queue_filter = {"needs_reply": SupportTicket.status.in_(("open", "in_progress")), "waiting_user": SupportTicket.status == "waiting_user", "active": SupportTicket.status != "closed", "closed": SupportTicket.status == "closed", "all": True}.get(queue)
        if queue_filter is None:
            raise HTTPException(400, "invalid queue")
        stmt = stmt.where(queue_filter)
        count_stmt = select(func.count()).select_from(SupportTicket).join(User, User.id == SupportTicket.user_id).where(queue_filter)
        if status != "all":
            if status not in VALID_STATUSES:
                raise HTTPException(400, "invalid status")
            stmt = stmt.where(SupportTicket.status == status)
            count_stmt = count_stmt.where(SupportTicket.status == status)
        if search:
            like = f"%{search}%"
            search_filter = or_(SupportTicket.subject.ilike(like), SupportTicket.username.ilike(like), cast(SupportTicket.id, String) == search.lstrip("#"), cast(User.tg_id, String) == search)
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)
        total = await session.scalar(count_stmt) or 0
        sort_col = _TICKET_SORT_COLUMNS.get(sort, SupportTicket.updated_at)
        sort_clause = sort_col.asc() if order == "asc" else sort_col.desc()
        stmt = stmt.order_by(SupportTicket.waiting_since.asc() if queue == "needs_reply" else sort_clause, SupportTicket.id.desc()).offset((page - 1) * per_page).limit(per_page)
        rows = (await session.execute(stmt)).all()
        ids = [t.id for t, _ in rows]
        ranked = select(SupportMessage.ticket_id, SupportMessage.text, func.row_number().over(partition_by=SupportMessage.ticket_id, order_by=SupportMessage.id.desc()).label("rn")).where(SupportMessage.ticket_id.in_(ids), SupportMessage.sender != "note").subquery()
        previews = dict((await session.execute(select(ranked.c.ticket_id, ranked.c.text).where(ranked.c.rn == 1))).all()) if ids else {}
        items = [
            {
                **metadata(t, admin=True),
                "last_message_preview": (previews.get(t.id) or "📷")[:120],
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
    return {"items": items, "total": total, "page": page, "per_page": per_page, "counts": counters}


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .options(
                selectinload(SupportTicket.messages).selectinload(SupportMessage.attachments)
            )
        )
        ticket = await session.scalar(stmt)
        if not ticket:
            raise HTTPException(404, "ticket not found")
        user = await _repo_users.get_user_by_id(session, ticket.user_id)
        messages = sorted(ticket.messages, key=lambda m: m.id)
        return {
            **metadata(ticket, admin=True),
            "id": ticket.id,
            "user_id": ticket.user_id,
            "tg_id": user.tg_id if user else None,
            "username": ticket.username,
            "subject": ticket.subject,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "author": m.author,
                    "text": m.text,
                    "created_at": m.created_at,
                    "attachments": [
                        {
                            "id": a.id,
                            "filename": a.original_filename,
                            "mime_type": a.mime_type,
                            "size_bytes": a.size_bytes,
                            "url": f"/support/tickets/{ticket_id}/attachments/{a.id}",
                        }
                        for a in m.attachments
                    ],
                }
                for m in messages
            ],
        }


@router.post("/tickets/{ticket_id}/reply")
async def reply_ticket(
    ticket_id: int,
    text: str = Form(default=""),
    images: list[UploadFile] = File(default=[]),
    close: bool = Form(False),
    internal: bool = Form(False),
    actor: str = Depends(get_current_user),
):
    text = text.strip()
    if len(text) > 4000:
        raise HTTPException(400, "message too long")
    if not text and not images:
        raise HTTPException(400, "empty text")
    async with async_session() as session:
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id, for_update=True)
        if not ticket:
            raise HTTPException(404, "ticket not found")
        if ticket.status == "closed" and not internal:
            raise HTTPException(409, "Reopen the ticket before replying")
        user = await _repo_users.get_user_by_id(session, ticket.user_id)

        try:
            saved = await validate_and_save_attachments(
                images, uploads_dir=get_support_uploads_dir(), ticket_id=ticket_id
            )
        except AttachmentValidationError as exc:
            raise HTTPException(400, str(exc)) from exc

        now = _now_iso()
        msg = SupportMessage(ticket_id=ticket.id, sender="note" if internal else "admin", author=actor, text=text, created_at=now)
        session.add(msg)
        await session.flush()
        for s in saved:
            await _repo_support.add_attachment(
                session,
                message_id=msg.id,
                original_filename=s.original_filename,
                stored_path=s.stored_path,
                mime_type=s.mime_type,
                size_bytes=s.size_bytes,
                created_at=now,
            )
        record_message(ticket, msg)
        if close and not internal:
            ticket.status = "closed"
            ticket.closed_at = now
        await session.commit()
        tg_id = user.tg_id if user else None
        subject = ticket.subject

    if tg_id and not internal:
        token = get_bot_token()
        if token:
            preview = text or ("(no text)" if saved else "")
            notify = f"💬 Ответ по обращению #{ticket_id}: <b>{escape(subject)}</b>\n\n{escape(preview[:3000])}"
            if saved:
                notify += f"\n📷 {len(saved)} фото прикреплено"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await send_notification(client,
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        {"chat_id": tg_id, "text": notify, "parse_mode": "HTML", **ticket_keyboard(get_config(), ticket_id)},
                    )
            except Exception:
                logger.warning("support notification could not be sent for ticket %s", ticket_id)
    return {"ok": True}


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}")
async def get_attachment(
    ticket_id: int,
    attachment_id: int,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        row = await _repo_support.get_attachment_with_ticket(session, attachment_id)
        if not row or row.ticket_id != ticket_id:
            raise HTTPException(404, "attachment not found")
    full_path = Path(get_support_uploads_dir()) / row.attachment.stored_path
    if not full_path.is_file():
        raise HTTPException(404, "file missing")
    return FileResponse(full_path, media_type=row.attachment.mime_type)


@router.patch("/tickets/{ticket_id}")
async def update_status(ticket_id: int, body: StatusBody, _: str = Depends(get_current_user)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, "invalid status")
    async with async_session() as session:
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id, for_update=True)
        if not ticket:
            raise HTTPException(404, "ticket not found")
        ticket.status = body.status
        ticket.closed_at = _now_iso() if body.status == "closed" else None
        if body.status == "open":
            ticket.waiting_since = _now_iso()
        ticket.updated_at = _now_iso()
        await session.commit()
    return {"ok": True}


@router.delete("/tickets/{ticket_id}/messages/{message_id}")
async def delete_admin_message(
    ticket_id: int,
    message_id: int,
    _: str = Depends(get_current_user),
):
    """Delete an admin-authored reply from a ticket.

    Only messages with sender='admin' can be removed. The repo helper
    enforces this at the SQL level; the endpoint translates "nothing
    deleted" into a 404 (covers: wrong message_id, wrong ticket_id,
    or a user-authored message).
    """
    async with async_session() as session:
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id, for_update=True)
        if not ticket:
            raise HTTPException(404, "ticket not found")
        result = await _repo_support.delete_admin_message(
            session, ticket_id=ticket_id, message_id=message_id
        )
        if not result.deleted:
            raise HTTPException(404, "message not found")
        remaining = await _repo_support.list_messages_for_ticket(session, ticket_id)
        ticket.last_admin_message_id = max((m.id for m in remaining if m.sender == "admin"), default=0)
        ticket.last_user_message_id = max((m.id for m in remaining if m.sender == "user"), default=0)
        if remaining:
            latest = remaining[-1]
            ticket.last_sender = latest.sender
            if ticket.status != "closed":
                ticket.status = "waiting_user" if latest.sender == "admin" else "open"
                ticket.waiting_since = latest.created_at
        ticket.updated_at = _now_iso()
        await session.commit()

    uploads_dir = Path(get_support_uploads_dir())
    for rel_path in result.attachment_paths:
        try:
            (uploads_dir / rel_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("failed to unlink attachment %s: %s", rel_path, exc)
    return {"ok": True}


@router.post("/tickets/{ticket_id}/read")
async def mark_read(ticket_id: int, body: ReadBody, _: str = Depends(get_current_user)):
    async with async_session() as session:
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id, for_update=True)
        if not ticket:
            raise HTTPException(404, "ticket not found")
        cursor = min(body.message_id, ticket.last_user_message_id)
        await session.execute(update(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.admin_read_id < cursor).values(admin_read_id=cursor))
        await session.commit()
    return {"ok": True}


@router.post("/tickets/{ticket_id}/claim")
async def claim(ticket_id: int, actor: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(update(SupportTicket).where(SupportTicket.id == ticket_id, or_(SupportTicket.assignee.is_(None), SupportTicket.assignee == actor)).values(assignee=actor))
        if not result.rowcount:
            raise HTTPException(409, "Ticket already assigned or not found")
        await session.commit()
    return {"ok": True}


@router.delete("/tickets/{ticket_id}/claim")
async def release(ticket_id: int, actor: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(update(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.assignee == actor).values(assignee=None))
        if not result.rowcount:
            raise HTTPException(409, "Only the assigned administrator can release this ticket")
        await session.commit()
    return {"ok": True}
