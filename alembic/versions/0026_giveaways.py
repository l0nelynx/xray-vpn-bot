"""0026: Giveaway / raffle tables."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_giveaways"
down_revision: Union[str, None] = "0025_crm_webhook_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "giveaways"):
        op.create_table(
            "giveaways",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False, server_default=""),
            sa.Column("channel_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("winner_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("starts_at", sa.String(30), nullable=True),
            sa.Column("ends_at", sa.String(30), nullable=True),
            sa.Column("drawn_at", sa.String(30), nullable=True),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("created_by", sa.String(100), nullable=False, server_default=""),
        )
        op.create_index("ix_giveaways_status", "giveaways", ["status"])
        op.create_index("ix_giveaways_created_at", "giveaways", ["created_at"])

    if not _has_table(bind, "giveaway_participants"):
        op.create_table(
            "giveaway_participants",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "giveaway_id",
                sa.BigInteger(),
                sa.ForeignKey("giveaways.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("joined_at", sa.String(30), nullable=False),
            sa.UniqueConstraint("giveaway_id", "tg_id", name="uq_giveaway_participant"),
        )
        op.create_index(
            "ix_giveaway_participants_giveaway_id",
            "giveaway_participants",
            ["giveaway_id"],
        )
        op.create_index(
            "ix_giveaway_participants_tg_id",
            "giveaway_participants",
            ["tg_id"],
        )

    if not _has_table(bind, "giveaway_tickets"):
        op.create_table(
            "giveaway_tickets",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "giveaway_id",
                sa.BigInteger(),
                sa.ForeignKey("giveaways.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("participant_tg_id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("source_tg_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.UniqueConstraint(
                "giveaway_id",
                "participant_tg_id",
                "source",
                "source_tg_id",
                name="uq_giveaway_ticket",
            ),
        )
        op.create_index(
            "ix_giveaway_tickets_giveaway_id",
            "giveaway_tickets",
            ["giveaway_id"],
        )
        op.create_index(
            "ix_giveaway_tickets_participant",
            "giveaway_tickets",
            ["giveaway_id", "participant_tg_id"],
        )

    if not _has_table(bind, "giveaway_winners"):
        op.create_table(
            "giveaway_winners",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "giveaway_id",
                sa.BigInteger(),
                sa.ForeignKey("giveaways.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("tickets", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("giveaway_id", "rank", name="uq_giveaway_winner_rank"),
        )
        op.create_index(
            "ix_giveaway_winners_giveaway_id",
            "giveaway_winners",
            ["giveaway_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "giveaway_winners",
        "giveaway_tickets",
        "giveaway_participants",
        "giveaways",
    ):
        if _has_table(bind, table):
            op.drop_table(table)
