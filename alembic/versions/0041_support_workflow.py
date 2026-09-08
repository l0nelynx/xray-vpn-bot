"""Support queue, read cursors, context and ownership."""
from datetime import datetime, timezone
import os
from zoneinfo import ZoneInfo
from alembic import op
import sqlalchemy as sa

revision = "0041_support_workflow"
down_revision = "0040_giveaway_winning_ticket"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("support_tickets") as batch:
        for name, default, size in [("category", "other", 30), ("last_sender", "user", 20)]:
            batch.add_column(sa.Column(name, sa.String(size), nullable=False, server_default=default))
        for name in ("waiting_since", "closed_at"):
            batch.add_column(sa.Column(name, sa.String(30), nullable=True))
        batch.add_column(sa.Column("assignee", sa.String(100), nullable=True))
        batch.add_column(sa.Column("context", sa.JSON(), nullable=True))
        for name in ("admin_read_id", "user_read_id", "last_user_message_id", "last_admin_message_id"):
            batch.add_column(sa.Column(name, sa.BigInteger(), nullable=False, server_default="0"))
        batch.create_index("ix_support_queue", ["status", "waiting_since"])
    with op.batch_alter_table("support_messages") as batch:
        batch.add_column(sa.Column("author", sa.String(100), nullable=True))
    bind = op.get_bind()
    # Old dashboard dates had no offset. Docker defaults to UTC; deployments
    # that used another TZ can supply SUPPORT_LEGACY_TIMEZONE during migration.
    legacy_tz = ZoneInfo(os.environ.get("SUPPORT_LEGACY_TIMEZONE", "UTC"))
    for table in ("support_tickets", "support_messages", "support_attachments"):
        columns = ("created_at", "updated_at") if table == "support_tickets" else ("created_at",)
        for column in columns:
            for row in bind.execute(sa.text(f"SELECT id, {column} FROM {table}" )).all():
                if not row[1]:
                    continue
                value = datetime.fromisoformat(row[1].replace("Z", "+00:00"))
                if value.tzinfo is None:
                    value = value.replace(tzinfo=legacy_tz)
                bind.execute(sa.text(f"UPDATE {table} SET {column}=:value WHERE id=:id"),
                             {"id": row[0], "value": value.astimezone(timezone.utc).isoformat(timespec="seconds")})
    for ticket in bind.execute(sa.text("SELECT id, status, created_at, updated_at FROM support_tickets")).all():
        messages = bind.execute(sa.text("SELECT id, sender, created_at FROM support_messages WHERE ticket_id=:id ORDER BY created_at, id"), {"id": ticket.id}).all()
        last = messages[-1] if messages else None
        sender = last.sender if last else "user"
        status = "waiting_user" if ticket.status != "closed" and sender == "admin" else ticket.status
        bind.execute(sa.text("UPDATE support_tickets SET last_sender=:sender, status=:status, waiting_since=:waiting, closed_at=:closed, last_user_message_id=:uid, last_admin_message_id=:aid WHERE id=:id"), {
            "id": ticket.id, "sender": sender, "status": status,
            "waiting": last.created_at if last else ticket.created_at,
            "closed": ticket.updated_at if status == "closed" else None,
            "uid": max((m.id for m in messages if m.sender == "user"), default=0),
            "aid": max((m.id for m in messages if m.sender == "admin"), default=0),
        })


def downgrade():
    op.execute("UPDATE support_tickets SET status='in_progress' WHERE status='waiting_user'")
    with op.batch_alter_table("support_messages") as batch:
        batch.drop_column("author")
    with op.batch_alter_table("support_tickets") as batch:
        batch.drop_index("ix_support_queue")
        for name in ("category", "context", "assignee", "last_sender", "waiting_since", "closed_at", "admin_read_id", "user_read_id", "last_user_message_id", "last_admin_message_id"):
            batch.drop_column(name)
