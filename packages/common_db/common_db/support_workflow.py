"""Ticket transitions and public metadata. Notes never change the reply queue."""
from datetime import datetime, timezone, timedelta


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_message(ticket, message):
    if message.sender == "note":
        return
    if ticket.last_sender != message.sender or not ticket.waiting_since:
        ticket.waiting_since = message.created_at
    ticket.last_sender = message.sender
    ticket.updated_at = message.created_at
    if message.sender == "admin":
        ticket.last_admin_message_id = message.id
        ticket.status = "waiting_user"
    else:
        ticket.last_user_message_id = message.id
        ticket.status = "open"
    ticket.closed_at = None


def can_reopen(ticket):
    if ticket.status != "closed" or not ticket.closed_at:
        return False
    closed = datetime.fromisoformat(ticket.closed_at.replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - closed.replace(tzinfo=closed.tzinfo or timezone.utc) <= timedelta(days=7)


def metadata(ticket, *, admin=False):
    return {
        "category": ticket.category, "context": ticket.context or {},
        "last_sender": ticket.last_sender, "waiting_since": ticket.waiting_since,
        "unread": (ticket.last_user_message_id > ticket.admin_read_id) if admin else (ticket.last_admin_message_id > ticket.user_read_id),
        "last_message_id": max(ticket.last_user_message_id, ticket.last_admin_message_id),
        "can_reopen": can_reopen(ticket),
        **({"assignee": ticket.assignee} if admin else {}),
    }
