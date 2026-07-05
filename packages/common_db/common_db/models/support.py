"""Support ticket schema (used by miniapp + dashboard).

Schema canon (after alembic 0007 BigInteger pass):
- support_tickets.id        : BigInteger PK
- support_tickets.user_id   : BigInteger FK -> users.id
- support_tickets.status    : default="open", server_default="open"
- support_tickets indexes   : (user_id), (status)
- support_messages.id       : BigInteger PK
- support_messages.ticket_id: BigInteger FK -> support_tickets.id  ON DELETE CASCADE
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="open", server_default="open"
    )
    created_at: Mapped[str] = mapped_column(String(30))
    updated_at: Mapped[str] = mapped_column(String(30))

    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_support_tickets_user_id", "user_id"),
        Index("ix_support_tickets_status", "status"),
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("support_tickets.id", ondelete="CASCADE")
    )
    sender: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(30))

    ticket: Mapped["SupportTicket"] = relationship(back_populates="messages")
    attachments: Mapped[list["SupportAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_support_messages_ticket_id", "ticket_id"),)


class SupportAttachment(Base):
    """Image attached to a support-ticket reply (up to 3 per message).

    The actual file lives on disk under a shared bind-mounted directory (see
    `get_support_uploads_dir()` in the miniapp/dashboard configs) — this row
    only tracks metadata + a path relative to that uploads root. `stored_path`
    is deliberately relative (never an absolute host path) so it stays
    portable across containers and never leaks filesystem layout in an API
    response.
    """
    __tablename__ = "support_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("support_messages.id", ondelete="CASCADE")
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[str] = mapped_column(String(30))

    message: Mapped["SupportMessage"] = relationship(back_populates="attachments")

    __table_args__ = (Index("ix_support_attachments_message_id", "message_id"),)
