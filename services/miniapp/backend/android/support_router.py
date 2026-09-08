"""Support-ticket endpoints for JWT-authenticated web/android clients.

Mirrors miniapp/backend/routers/support.py but uses Bearer-JWT auth
(deps.get_current_user) instead of Telegram init-data auth.
User lookup is by user.id directly — no tg_id needed.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from common_db.support_delivery import send_notification, ticket_keyboard
from common_db.support_workflow import metadata, record_message
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..config import get_config, get_admin_bot_token, get_admin_id, get_support_uploads_dir
from ..database.models import SupportMessage, SupportTicket, User
from sqlalchemy import select
from ..database.session import async_session
from ..schemas.support import AttachmentOut, MessageItem, TicketCreate, TicketDetail, TicketSummary
from . import deps
from . import repo as android_repo
from common_db.repo import support as _repo_support
from support_attachments import AttachmentValidationError, validate_and_save_attachments

router = APIRouter(prefix="/api/android/support", tags=["android-support"])
logger = logging.getLogger(__name__)

MAX_OPEN_TICKETS = 5
NOTIFY_TIMEOUT = 5.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _notify_admin(ticket_id: int, display_name: str | None, subject: str) -> None:
    token = get_admin_bot_token()
    admin_id = get_admin_id()
    if not token or not admin_id:
        return
    text = (
        f"🆘 New support ticket #{ticket_id}\n"
        f"From: {display_name or '—'}\n"
        f"Subject: {subject}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=NOTIFY_TIMEOUT) as client:
            await send_notification(client, url, {"chat_id": admin_id, "text": text, **ticket_keyboard(get_config(), ticket_id, admin=True)})
    except Exception as e:
        logger.warning("admin notification failed for ticket %s: %s", ticket_id, e)


async def _notify_admin_reply(
    ticket_id: int, display_name: str | None, text: str, image_count: int = 0
) -> None:
    token = get_admin_bot_token()
    admin_id = get_admin_id()
    if not token or not admin_id:
        return
    preview = text if len(text) <= 300 else text[:297] + "..."
    if not preview and image_count:
        preview = "(no text)"
    body = (
        f"💬 New reply on ticket #{ticket_id}\n"
        f"From: {display_name or '—'}\n\n"
        f"{preview}"
    )
    if image_count:
        body += f"\n📷 {image_count} photo(s) attached"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=NOTIFY_TIMEOUT) as client:
            await send_notification(client, url, {"chat_id": admin_id, "text": body, **ticket_keyboard(get_config(), ticket_id, admin=True)})
    except Exception as e:
        logger.warning("admin reply notification failed for ticket %s: %s", ticket_id, e)


@router.get("/tickets", response_model=list[TicketSummary])
async def list_tickets(
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> list[TicketSummary]:
    async with async_session() as session:
        rows = await _repo_support.list_user_tickets_with_last_message(session, user.id)
        return [
            TicketSummary(
                **metadata(row.ticket),
                id=row.ticket.id,
                subject=row.ticket.subject,
                status=row.ticket.status,
                created_at=row.ticket.created_at,
                updated_at=row.ticket.updated_at,
                last_message_preview=(row.ticket.message if row.last_message_text is None else row.last_message_text or "📷")[:120],
            )
            for row in rows
        ]


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: int,
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> TicketDetail:
    async with async_session() as session:
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id, for_update=True)
        if not ticket or ticket.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        msgs = await _repo_support.list_messages_for_ticket(session, ticket.id)
        messages = [
            MessageItem(
                id=m.id, sender=m.sender, text=m.text, created_at=m.created_at,
                attachments=[
                    AttachmentOut(
                        id=a.id, filename=a.original_filename, mime_type=a.mime_type,
                        size_bytes=a.size_bytes,
                        url=f"/android/support/tickets/{ticket_id}/attachments/{a.id}",
                    )
                    for a in m.attachments
                ],
            )
            for m in msgs
        ]
        return TicketDetail(
            **metadata(ticket),
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
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> TicketDetail:
    now = _now_iso()
    display_name = user.email
    async with async_session() as session:
        await session.execute(select(User.id).where(User.id == user.id).with_for_update())
        open_count = await _repo_support.count_open_tickets_for_user(session, user.id)
        if open_count >= MAX_OPEN_TICKETS:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many open tickets")

        ticket = SupportTicket(
            user_id=user.id,
            username=display_name,
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
        await session.flush()
        record_message(ticket, first_message)
        await session.flush()

        ticket_id = ticket.id
        subject = ticket.subject
        msg_id = first_message.id
        await session.commit()

    asyncio.create_task(_notify_admin(ticket_id, display_name, subject))

    return TicketDetail(
        id=ticket_id,
        subject=subject,
        status="open",
        created_at=now,
        updated_at=now,
        messages=[
            MessageItem(id=msg_id, sender="user", text=body.message.strip(), created_at=now)
        ],
    )


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=MessageItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_user_message(
    ticket_id: int,
    text: str = Form(default=""),
    images: list[UploadFile] = File(default=[]),
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> MessageItem:
    text = text.strip()
    if len(text) > 4000:
        raise HTTPException(400, "message too long")
    if not text and not images:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty message")
    now = _now_iso()
    async with async_session() as session:
        ticket = await _repo_support.get_ticket_by_id(session, ticket_id, for_update=True)
        if not ticket or ticket.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        if ticket.status == "closed":
            raise HTTPException(status.HTTP_409_CONFLICT, "ticket is closed")

        try:
            saved = await validate_and_save_attachments(
                images, uploads_dir=get_support_uploads_dir(), ticket_id=ticket_id
            )
        except AttachmentValidationError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

        msg = SupportMessage(
            ticket_id=ticket.id,
            sender="user",
            text=text,
            created_at=now,
        )
        session.add(msg)
        await session.flush()

        att_rows = [
            await _repo_support.add_attachment(
                session,
                message_id=msg.id,
                original_filename=s.original_filename,
                stored_path=s.stored_path,
                mime_type=s.mime_type,
                size_bytes=s.size_bytes,
                created_at=now,
            )
            for s in saved
        ]
        await session.flush()

        record_message(ticket, msg)
        msg_id = msg.id
        await session.commit()
        attachments_out = [
            AttachmentOut(
                id=a.id, filename=a.original_filename, mime_type=a.mime_type,
                size_bytes=a.size_bytes,
                url=f"/android/support/tickets/{ticket_id}/attachments/{a.id}",
            )
            for a in att_rows
        ]

    asyncio.create_task(_notify_admin_reply(ticket_id, user.email, text, len(saved)))
    return MessageItem(
        id=msg_id, sender="user", text=text, created_at=now, attachments=attachments_out
    )


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}")
async def get_attachment(
    ticket_id: int,
    attachment_id: int,
    user: android_repo.UserRow = Depends(deps.get_current_user),
):
    async with async_session() as session:
        row = await _repo_support.get_attachment_with_ticket(session, attachment_id)
        if not row or row.message_sender == "note" or row.ticket_id != ticket_id or row.ticket_user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    full_path = Path(get_support_uploads_dir()) / row.attachment.stored_path
    if not full_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    return FileResponse(full_path, media_type=row.attachment.mime_type)


from ..support_actions import register_actions
register_actions(router, deps.get_current_user, telegram=False, notify=_notify_admin_reply)

from ..support_create import register_creation
register_creation(router, deps.get_current_user, telegram=False, notify=_notify_admin)
