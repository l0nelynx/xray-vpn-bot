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

from ..models import SupportMessage, SupportTicket


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
        .order_by(desc(SupportTicket.created_at))
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
                order_by=desc(SupportMessage.created_at),
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
    """All messages on a ticket, oldest first (chat-log order)."""
    result = await session.scalars(
        select(SupportMessage)
        .where(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.created_at)
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
            SupportTicket.status == "open",
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


# --- mutations ------------------------------------------------------------


async def delete_admin_message(
    session: AsyncSession, ticket_id: int, message_id: int
) -> bool:
    """Hard-delete an admin-authored message from a ticket.

    Filters on (id, ticket_id, sender='admin') in a single statement so
    you can't delete a user message, a message that belongs to a
    different ticket, or a non-existent row by guessing ids. Caller
    commits.

    Returns True iff exactly one row was deleted.
    """
    stmt = delete(SupportMessage).where(
        SupportMessage.id == message_id,
        SupportMessage.ticket_id == ticket_id,
        SupportMessage.sender == "admin",
    )
    result = await session.execute(stmt)
    return (result.rowcount or 0) > 0


__all__ = [
    "TicketWithLastMessage",
    "count_open_tickets_for_user",
    "count_tickets_by_status",
    "delete_admin_message",
    "get_ticket_by_id",
    "list_messages_for_ticket",
    "list_user_tickets",
    "list_user_tickets_with_last_message",
]
