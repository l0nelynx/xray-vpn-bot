"""Store the concrete winning ticket for giveaway results.

Revision ID: 0040_giveaway_winning_ticket
Revises: 0039_subscription_onboarding
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_giveaway_winning_ticket"
down_revision: Union[str, None] = "0039_subscription_onboarding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("giveaway_winners") as batch:
        batch.add_column(sa.Column("winning_ticket_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_giveaway_winners_winning_ticket_id",
            "giveaway_tickets",
            ["winning_ticket_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_giveaway_winners_winning_ticket_id",
            ["winning_ticket_id"],
        )

    bind = op.get_bind()
    winners = sa.table(
        "giveaway_winners",
        sa.column("id", sa.BigInteger()),
        sa.column("giveaway_id", sa.BigInteger()),
        sa.column("tg_id", sa.BigInteger()),
        sa.column("winning_ticket_id", sa.BigInteger()),
    )
    tickets = sa.table(
        "giveaway_tickets",
        sa.column("id", sa.BigInteger()),
        sa.column("giveaway_id", sa.BigInteger()),
        sa.column("participant_tg_id", sa.BigInteger()),
        sa.column("created_at", sa.String()),
    )
    rows = bind.execute(sa.select(winners.c.id, winners.c.giveaway_id, winners.c.tg_id)).all()
    for winner_id, giveaway_id, tg_id in rows:
        ticket_id = bind.execute(
            sa.select(tickets.c.id)
            .where(
                tickets.c.giveaway_id == giveaway_id,
                tickets.c.participant_tg_id == tg_id,
            )
            .order_by(tickets.c.created_at, tickets.c.id)
            .limit(1)
        ).scalar_one_or_none()
        if ticket_id is not None:
            bind.execute(
                winners.update()
                .where(winners.c.id == winner_id)
                .values(winning_ticket_id=ticket_id)
            )


def downgrade() -> None:
    with op.batch_alter_table("giveaway_winners") as batch:
        batch.drop_index("ix_giveaway_winners_winning_ticket_id")
        batch.drop_constraint("fk_giveaway_winners_winning_ticket_id", type_="foreignkey")
        batch.drop_column("winning_ticket_id")
