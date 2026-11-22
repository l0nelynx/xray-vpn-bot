"""User-owned operations on the shared ticket store."""
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from common_db.models import SupportMessage, SupportTicket
from common_db.repo import support as repo
from common_db.repo.users import get_user_by_id
from common_db.support_workflow import can_reopen, now_iso, record_message
from support_attachments import validate_and_save_attachments

from app.database.models import async_session
from app.settings import secrets
from .locale import CATEGORIES, label


class TicketError(ValueError):
    """A localized, user-facing error key."""


def uploads_dir():
    return secrets.get("support_uploads_dir") or "/app/support_uploads"


async def owned_ticket(session, owner, ticket_id, *, lock=False):
    ticket = await repo.get_ticket_by_id(session, ticket_id, for_update=lock)
    if ticket is None or ticket.user_id != owner:
        raise TicketError("unavailable")
    return ticket


async def submit(owner, *, ticket_id, category, text, files, lang):
    text = text.strip()
    if len(text) > 4000:
        raise TicketError("text_limit")
    if not text and (ticket_id is None or not files):
        raise TicketError("need_text" if ticket_id is None else "need_reply")

    saved = []
    directory = uploads_dir()
    try:
        async with async_session.begin() as session:
            now = now_iso()
            if ticket_id is None:
                if category not in CATEGORIES:
                    raise TicketError("stale")
                user = await get_user_by_id(session, owner, for_update=True)
                if user is None:
                    raise TicketError("unavailable")
                if await repo.count_open_tickets_for_user(session, owner) >= 5:
                    raise TicketError("limit")
                ticket = SupportTicket(
                    user_id=owner, username=user.username or user.email,
                    subject=label(lang, category), category=category, message=text,
                    context={"language": lang}, created_at=now, updated_at=now,
                )
                session.add(ticket)
                await session.flush()
            else:
                ticket = await owned_ticket(session, owner, ticket_id, lock=True)
                if ticket.status == "closed":
                    raise TicketError("closed")
            ticket.reply_channel = "support_bot"
            saved = await validate_and_save_attachments(files, uploads_dir=directory, ticket_id=ticket.id)
            message = SupportMessage(ticket_id=ticket.id, sender="user", text=text, created_at=now)
            session.add(message)
            await session.flush()
            for image in saved:
                await repo.add_attachment(
                    session, message_id=message.id, original_filename=image.original_filename,
                    stored_path=image.stored_path, mime_type=image.mime_type,
                    size_bytes=image.size_bytes, created_at=now,
                )
            record_message(ticket, message)
            result_id = ticket.id
    except BaseException:
        for image in saved:
            (Path(directory) / image.stored_path).unlink(missing_ok=True)
        raise
    return result_id


async def list_page(owner, offset):
    async with async_session() as session:
        tickets = await session.scalars(
            select(SupportTicket).where(SupportTicket.user_id == owner)
            .order_by(SupportTicket.status == "closed", SupportTicket.updated_at.desc(), SupportTicket.id.desc())
            .offset(offset).limit(9)
        )
        rows = list(tickets)
    return rows[:8], len(rows) > 8


async def conversation(owner, ticket_id, before=None):
    async with async_session() as session:
        ticket = await owned_ticket(session, owner, ticket_id)
        stmt = select(SupportMessage).where(
            SupportMessage.ticket_id == ticket_id, SupportMessage.sender != "note",
        ).options(selectinload(SupportMessage.attachments))
        if before:
            stmt = stmt.where(SupportMessage.id < before)
        messages = list(await session.scalars(stmt.order_by(SupportMessage.id.desc()).limit(5)))
    return ticket, list(reversed(messages[:4])), len(messages) > 4


async def mark_read(owner, ticket_id, cursor):
    async with async_session.begin() as session:
        await session.execute(update(SupportTicket).where(
            SupportTicket.id == ticket_id, SupportTicket.user_id == owner,
            SupportTicket.user_read_id < cursor,
        ).values(user_read_id=cursor))


async def image_file(owner, ticket_id, attachment_id):
    async with async_session() as session:
        row = await repo.get_attachment_with_ticket(session, attachment_id)
        if not row or row.ticket_user_id != owner or row.ticket_id != ticket_id or row.message_sender == "note":
            raise TicketError("unavailable")
        path = Path(uploads_dir()) / row.attachment.stored_path
        if not path.is_file():
            raise TicketError("unavailable")
        return path, row.attachment.original_filename


async def change_status(owner, ticket_id, *, reopen):
    async with async_session.begin() as session:
        # Same lock order as creation to serialize the active-ticket limit.
        await get_user_by_id(session, owner, for_update=True)
        ticket = await owned_ticket(session, owner, ticket_id, lock=True)
        if (reopen and ticket.status != "closed") or (not reopen and ticket.status == "closed"):
            return False
        now = now_iso()
        if reopen:
            if not can_reopen(ticket):
                raise TicketError("expired")
            if await repo.count_open_tickets_for_user(session, owner) >= 5:
                raise TicketError("limit")
            ticket.status = "open"
            ticket.waiting_since = now
            ticket.closed_at = None
            ticket.reply_channel = "support_bot"
        else:
            ticket.status = "closed"
            ticket.closed_at = now
        ticket.updated_at = now
        return True
