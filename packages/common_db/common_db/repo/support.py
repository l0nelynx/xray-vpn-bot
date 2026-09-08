"""Support-ticket lookups and the N+1 fix for the list_tickets endpoint.

The miniapp's "my tickets" screen had a textbook N+1: after fetching N
tickets it issued one sub-query per ticket for the last-message preview
(``select(SupportMessage.text).where(ticket_id=...).limit(1)`` inside the
for-loop). For a user with 20 tickets that's 21 round-trips.

``list_user_tickets_with_last_message`` collapses it into 2 queries
total: the tickets, plus one window-function pass over the messages to
pick the latest per ticket_id. SQLite 3.25+ and Postgres both support
ROW_NUMBER OVER (PARTITION BY ...).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import SupportAttachment, SupportMessage, SupportTicket


# --- single-row lookups ---------------------------------------------------


async def get_ticket_by_id(
    session: AsyncSession, ticket_id: int
) -> SupportTicket | None:
    """Get a ticket by its primary key, or None."""
    return await session.scalar(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )


# --- list_user_tickets (the N+1 fix) --------------------------------------


@dataclass(frozen=True, slots=True)
class TicketWithLastMessage:
    """A ticket plus the text of its most recent message (or None if none
    exist yet, which shouldn't happen in practice but we don't crash)."""

    ticket: SupportTicket
    last_message_text: str | None


async def list_user_tickets(
    session: AsyncSession, user_id: int
) -> list[SupportTicket]:
    """All tickets owned by ``user_id``, most recently created first.

    Use ``list_user_tickets_with_last_message`` if you need previews;
    this thin variant is for callers that don't.
    """
    result = await session.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.status == "closed", desc(SupportTicket.updated_at), desc(SupportTicket.id))
    )
    return list(result)


async def list_user_tickets_with_last_message(
    session: AsyncSession, user_id: int
) -> list[TicketWithLastMessage]:
    """Tickets + last-message preview in 2 queries instead of 1+N.

    Strategy:
      1. fetch tickets for user, ordered newest first
      2. one batch query: ``SELECT ticket_id, MAX(created_at), text``
         grouped per ticket_id (correlated lookup via ROW_NUMBER).

    Returns ``TicketWithLastMessage`` rows in the same order as the
    ticket query. If a ticket has no messages, ``last_message_text`` is
    None — callers typically fall back to ``ticket.message`` (the
    original subject body) for the preview.
    """
    tickets = await list_user_tickets(session, user_id)
    if not tickets:
        return []

    ticket_ids = [t.id for t in tickets]

    # Subquery: rank each message within its ticket by created_at desc
    # so rn=1 is the most recent. Then SELECT where rn=1.
    ranked = (
        select(
            SupportMessage.ticket_id,
            SupportMessage.text,
            func.row_number()
            .over(
                partition_by=SupportMessage.ticket_id,
                order_by=(desc(SupportMessage.created_at), desc(SupportMessage.id)),
            )
            .label("rn"),
        )
        .where(SupportMessage.ticket_id.in_(ticket_ids))
        .subquery()
    )
    rows = await session.execute(
        select(ranked.c.ticket_id, ranked.c.text).where(ranked.c.rn == 1)
    )
    last_by_ticket: dict[int, str] = {tid: txt for tid, txt in rows.all()}

    return [
        TicketWithLastMessage(
            ticket=t, last_message_text=last_by_ticket.get(t.id)
        )
        for t in tickets
    ]


# --- per-ticket messages --------------------------------------------------


async def list_messages_for_ticket(
    session: AsyncSession, ticket_id: int
) -> list[SupportMessage]:
    """All messages on a ticket, oldest first (chat-log order), with
    attachments eager-loaded (avoids 1+N when the caller renders images)."""
    result = await session.scalars(
        select(SupportMessage)
        .where(SupportMessage.ticket_id == ticket_id)
        .options(selectinload(SupportMessage.attachments))
        .order_by(SupportMessage.created_at, SupportMessage.id)
    )
    return list(result)


# --- counts ---------------------------------------------------------------


async def count_open_tickets_for_user(
    session: AsyncSession, user_id: int
) -> int:
    """Count open tickets owned by ``user_id``. Used by the rate-limiter
    in miniapp's ``create_ticket`` (``MAX_OPEN_TICKETS`` check)."""
    n = await session.scalar(
        select(func.count())
        .select_from(SupportTicket)
        .where(
            SupportTicket.user_id == user_id,
            SupportTicket.status.in_(("open", "in_progress", "waiting_user")),
        )
    )
    return n or 0


async def count_tickets_by_status(
    session: AsyncSession, statuses: Iterable[str] | None = None
) -> int:
    """Total tickets, optionally filtered by status set. Used by
    dashboard's pagination metadata."""
    stmt = select(func.count()).select_from(SupportTicket)
    if statuses is not None:
        statuses = list(statuses)
        if not statuses:
            return 0
        stmt = stmt.where(SupportTicket.status.in_(statuses))
    return (await session.scalar(stmt)) or 0


# --- attachments ------------------------------------------------------------


async def add_attachment(
    session: AsyncSession,
    *,
    message_id: int,
    original_filename: str,
    stored_path: str,
    mime_type: str,
    size_bytes: int,
    created_at: str,
) -> SupportAttachment:
    """Create one attachment row. Caller commits (called inside the same
    transaction as the SupportMessage insert, per router)."""
    att = SupportAttachment(
        message_id=message_id,
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type=mime_type,
        size_bytes=size_bytes,
        created_at=created_at,
    )
    session.add(att)
    return att


@dataclass(frozen=True, slots=True)
class AttachmentWithTicket:
    """An attachment plus its parent ticket's id/owner, for the download
    endpoint's ownership check (miniapp/android: does ticket.user_id match
    the requester? dashboard: any admin may view)."""

    attachment: SupportAttachment
    ticket_id: int
    ticket_user_id: int


async def get_attachment_with_ticket(
    session: AsyncSession, attachment_id: int
) -> AttachmentWithTicket | None:
    """Fetch an attachment plus its parent ticket's id/owner in one query."""
    row = (
        await session.execute(
            select(SupportAttachment, SupportMessage.ticket_id, SupportTicket.user_id)
            .join(SupportMessage, SupportMessage.id == SupportAttachment.message_id)
            .join(SupportTicket, SupportTicket.id == SupportMessage.ticket_id)
            .where(SupportAttachment.id == attachment_id)
        )
    ).first()
    if not row:
        return None
    att, ticket_id, user_id = row
    return AttachmentWithTicket(attachment=att, ticket_id=ticket_id, ticket_user_id=user_id)


# --- mutations ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeletedMessageResult:
    """Result of deleting an admin message: whether a row was actually
    deleted, and the relative stored_path of every attachment that was on
    it (for the caller to unlink from disk after commit)."""

    deleted: bool
    attachment_paths: list[str]


async def delete_admin_message(
    session: AsyncSession, ticket_id: int, message_id: int
) -> DeletedMessageResult:
    """Hard-delete an admin-authored message (+ its attachment rows via
    ON DELETE CASCADE) from a ticket.

    Filters on (id, ticket_id, sender='admin') in a single statement so
    you can't delete a user message, a message that belongs to a
    different ticket, or a non-existent row by guessing ids. Caller
    commits.

    Attachment paths are fetched *before* the delete (the cascade removes
    the rows, not the files) so the caller can best-effort unlink them from
    disk afterward — a stray file leak on disk is not a break-the-request
    problem, the DB delete is authoritative.
    """
    paths = list(
        await session.scalars(
            select(SupportAttachment.stored_path)
            .join(SupportMessage, SupportMessage.id == SupportAttachment.message_id)
            .where(
                SupportMessage.id == message_id,
                SupportMessage.ticket_id == ticket_id,
                SupportMessage.sender == "admin",
            )
        )
    )
    stmt = delete(SupportMessage).where(
        SupportMessage.id == message_id,
        SupportMessage.ticket_id == ticket_id,
        SupportMessage.sender == "admin",
    )
    result = await session.execute(stmt)
    deleted = (result.rowcount or 0) > 0
    return DeletedMessageResult(deleted=deleted, attachment_paths=paths if deleted else [])


__all__ = [
    "AttachmentWithTicket",
    "DeletedMessageResult",
    "TicketWithLastMessage",
    "add_attachment",
    "count_open_tickets_for_user",
    "count_tickets_by_status",
    "delete_admin_message",
    "get_attachment_with_ticket",
    "get_ticket_by_id",
    "list_messages_for_ticket",
    "list_user_tickets",
    "list_user_tickets_with_last_message",
]
