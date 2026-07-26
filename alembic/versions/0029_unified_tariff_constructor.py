"""0029: make Tariff Constructor the only purchase-menu source."""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_unified_tariff_constructor"
down_revision: Union[str, None] = "0028_app_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table: str) -> set[str]:
    if table not in _tables(bind):
        return set()
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _parse_target(value: str | None) -> tuple[str, str] | None:
    if not value or not value.startswith("sid:"):
        return None
    try:
        _, squad_id, marker, external_id = value.split(":", 3)
    except ValueError:
        return None
    if marker != "esid" or not squad_id or not external_id:
        return None
    return squad_id, external_id


def _valid_invoice(row, target: tuple[str, str] | None) -> bool:
    provider = str(row["invoice_provider"] or "").lower()
    currency = str(row["invoice_currency"] or "").upper()
    method = str(row["invoice_method"] or "default")
    try:
        amount = float(row["invoice_amount"] or 0)
        days = int(row["invoice_days"] or 0)
    except (TypeError, ValueError):
        return False
    capabilities = {
        "apay": ({"RUB"}, {"default"}),
        "crystal": ({"RUB", "USD", "EUR"}, {"default"}),
        "crypto": (
            {"USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC"},
            {"default"},
        ),
        "platega": ({"RUB"}, {"2", "3", "11", "12", "13"}),
        "paritypay": ({"RUB"}, {"sbp", "card"}),
        "stars": ({"XTR"}, {"default"}),
    }
    supported = capabilities.get(provider)
    if (
        target is None
        or supported is None
        or currency not in supported[0]
        or method not in supported[1]
        or amount <= 0
        or days <= 0
    ):
        return False
    return provider != "stars" or amount.is_integer()


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)

    if "webapp_menu_nodes" in tables:
        cols = _columns(bind, "webapp_menu_nodes")
        with op.batch_alter_table("webapp_menu_nodes") as batch:
            if "text_ru" not in cols:
                batch.add_column(
                    sa.Column("text_ru", sa.String(255), nullable=False, server_default="")
                )
            if "text_en" not in cols:
                batch.add_column(
                    sa.Column("text_en", sa.String(255), nullable=False, server_default="")
                )
            if "invoice_squad_id" not in cols:
                batch.add_column(sa.Column("invoice_squad_id", sa.String(100), nullable=True))
            if "invoice_external_squad_id" not in cols:
                batch.add_column(
                    sa.Column("invoice_external_squad_id", sa.String(100), nullable=True)
                )

        cols = _columns(bind, "webapp_menu_nodes")
        if "text" in cols:
            bind.execute(sa.text(
                "UPDATE webapp_menu_nodes SET text_ru = text, text_en = text "
                "WHERE text_ru = '' OR text_en = ''"
            ))

        legacy_targets: dict[str, tuple[str, str]] = {}
        if {"tariff_plans", "squad_profiles"}.issubset(tables):
            rows = bind.execute(sa.text(
                "SELECT t.slug, s.squad_id, s.external_squad_id "
                "FROM tariff_plans t JOIN squad_profiles s ON s.id = t.squad_profile_id"
            )).mappings()
            legacy_targets = {
                str(r["slug"]): (str(r["squad_id"]), str(r["external_squad_id"]))
                for r in rows
                if r["slug"] and r["squad_id"] and r["external_squad_id"]
            }

        node_rows = bind.execute(sa.text(
            "SELECT id, action, invoice_tariff_slug, invoice_squad_id, "
            "invoice_external_squad_id, invoice_provider, invoice_amount, "
            "invoice_currency, invoice_method, invoice_days "
            "FROM webapp_menu_nodes"
        )).mappings()
        for row in node_rows:
            target = None
            if row["invoice_squad_id"] and row["invoice_external_squad_id"]:
                target = (
                    str(row["invoice_squad_id"]),
                    str(row["invoice_external_squad_id"]),
                )
            if target is None:
                raw = row["invoice_tariff_slug"]
                target = _parse_target(raw) or legacy_targets.get(str(raw or ""))
            if target:
                bind.execute(
                    sa.text(
                        "UPDATE webapp_menu_nodes SET invoice_squad_id=:sid, "
                        "invoice_external_squad_id=:esid WHERE id=:id"
                    ),
                    {"sid": target[0], "esid": target[1], "id": row["id"]},
                )
            if row["action"] == "invoice" and not _valid_invoice(row, target):
                bind.execute(
                    sa.text("UPDATE webapp_menu_nodes SET is_active=:inactive WHERE id=:id"),
                    {"inactive": False, "id": row["id"]},
                )

        with op.batch_alter_table("webapp_menu_nodes") as batch:
            cols = _columns(bind, "webapp_menu_nodes")
            if "text" in cols:
                batch.drop_column("text")
            if "invoice_tariff_slug" in cols:
                batch.drop_column("invoice_tariff_slug")

    if "transactions" in tables:
        cols = _columns(bind, "transactions")
        with op.batch_alter_table("transactions") as batch:
            if "squad_id" not in cols:
                batch.add_column(sa.Column("squad_id", sa.String(100), nullable=True))
            if "external_squad_id" not in cols:
                batch.add_column(sa.Column("external_squad_id", sa.String(100), nullable=True))
            if "provider_invoice_id" not in cols:
                batch.add_column(sa.Column("provider_invoice_id", sa.String(100), nullable=True))

        legacy_targets = {}
        plan_candidates: dict[tuple[str, int], tuple[str, str]] = {}
        if {"tariff_plans", "tariff_prices", "squad_profiles"}.issubset(tables):
            rows = bind.execute(sa.text(
                "SELECT t.slug, t.days, p.payment_method, s.squad_id, "
                "s.external_squad_id FROM tariff_plans t "
                "JOIN tariff_prices p ON p.tariff_id=t.id "
                "JOIN squad_profiles s ON s.id=t.squad_profile_id "
                "WHERE t.is_active=:active AND p.is_active=:active "
                "ORDER BY t.sort_order, t.id"
            ), {"active": True}).mappings()
            for row in rows:
                target = (str(row["squad_id"]), str(row["external_squad_id"]))
                legacy_targets[str(row["slug"])] = target
                plan_candidates.setdefault(
                    (str(row["payment_method"]), int(row["days"])), target
                )

        method_map = {
            "TG_STARS": "stars",
            "CRYPTOPAY": "crypto",
            "SBP_APAY": "sbp",
            "CRYSTAL_PAY": "crystal",
            "PLATEGA": "platega",
            "PARITYPAY": "paritypay",
        }
        tx_rows = bind.execute(sa.text(
            "SELECT transaction_id, tariff_slug, payment_method, days_ordered, order_status, "
            "squad_id, external_squad_id FROM transactions"
        )).mappings()
        for row in tx_rows:
            target = None
            if row["squad_id"] and row["external_squad_id"]:
                target = (str(row["squad_id"]), str(row["external_squad_id"]))
            if target is None:
                raw = row["tariff_slug"]
                target = _parse_target(raw) or legacy_targets.get(str(raw or ""))
            if target is None:
                raw_method = str(row["payment_method"] or "")
                legacy_method = method_map.get(raw_method, raw_method.lower())
                if legacy_method and row["days_ordered"]:
                    target = plan_candidates.get((legacy_method, int(row["days_ordered"])))
            old_id = str(row["transaction_id"])
            is_open = str(row["order_status"] or "").lower() in {"created", "pending"}
            local_id = (
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"xray-vpn-bot:legacy:{old_id}"))
                if is_open
                else old_id
            )
            values = {"pid": old_id, "tx": old_id, "local_id": local_id}
            if target:
                values.update({"sid": target[0], "esid": target[1]})
                bind.execute(sa.text(
                    "UPDATE transactions SET transaction_id=:local_id, "
                    "provider_invoice_id=:pid, squad_id=:sid, "
                    "external_squad_id=:esid WHERE transaction_id=:tx"
                ), values)
            else:
                bind.execute(sa.text(
                    "UPDATE transactions SET transaction_id=:local_id, "
                    "provider_invoice_id=:pid "
                    "WHERE transaction_id=:tx"
                ), values)

        with op.batch_alter_table("transactions") as batch:
            if "tariff_slug" in _columns(bind, "transactions"):
                batch.drop_column("tariff_slug")
            batch.create_index(
                "ix_transactions_provider_invoice_id",
                ["provider_invoice_id"],
                unique=False,
            )

    if "menu_buttons" in tables:
        bind.execute(sa.text(
            "UPDATE menu_buttons SET button_type='tariff', callback_data=NULL, url=NULL "
            "WHERE callback_data IN ('Premium', 'Extend_Month')"
        ))
        with op.batch_alter_table("menu_buttons") as batch:
            if "visibility_condition" in _columns(bind, "menu_buttons"):
                batch.drop_column("visibility_condition")

    if "menu_screens" in tables:
        pay_ids = [
            r[0]
            for r in bind.execute(
                sa.text("SELECT id FROM menu_screens WHERE slug='pay_methods'")
            ).all()
        ]
        for screen_id in pay_ids:
            bind.execute(
                sa.text("DELETE FROM menu_buttons WHERE screen_id=:id"),
                {"id": screen_id},
            )
        bind.execute(sa.text("DELETE FROM menu_screens WHERE slug='pay_methods'"))

    for table in ("tariff_prices", "tariff_plans", "squad_profiles"):
        if table in _tables(bind):
            op.drop_table(table)


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)

    if "squad_profiles" not in tables:
        op.create_table(
            "squad_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("squad_id", sa.String(100), nullable=False),
            sa.Column("external_squad_id", sa.String(100), nullable=False),
        )
    if "tariff_plans" not in tables:
        op.create_table(
            "tariff_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(50), unique=True, nullable=False),
            sa.Column("name_ru", sa.String(100), nullable=False),
            sa.Column("name_en", sa.String(100), nullable=False),
            sa.Column("days", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.String(30), nullable=True),
            sa.Column("squad_profile_id", sa.Integer(), sa.ForeignKey("squad_profiles.id")),
        )
    if "tariff_prices" not in tables:
        op.create_table(
            "tariff_prices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tariff_id",
                sa.Integer(),
                sa.ForeignKey("tariff_plans.id", ondelete="CASCADE"),
            ),
            sa.Column("payment_method", sa.String(30), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("tariff_id", "payment_method", name="uq_tariff_payment"),
        )

    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.add_column(sa.Column("text", sa.String(255), nullable=True))
        batch.add_column(sa.Column("invoice_tariff_slug", sa.String(255), nullable=True))
    bind.execute(sa.text(
        "UPDATE webapp_menu_nodes SET text=text_ru, "
        "invoice_tariff_slug='sid:' || invoice_squad_id || ':esid:' || "
        "invoice_external_squad_id"
    ))
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.drop_column("text_ru")
        batch.drop_column("text_en")
        batch.drop_column("invoice_squad_id")
        batch.drop_column("invoice_external_squad_id")

    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("tariff_slug", sa.String(200), nullable=True))
        batch.drop_index("ix_transactions_provider_invoice_id")
        batch.drop_column("provider_invoice_id")
        batch.drop_column("squad_id")
        batch.drop_column("external_squad_id")

    with op.batch_alter_table("menu_buttons") as batch:
        batch.add_column(
            sa.Column(
                "visibility_condition",
                sa.String(50),
                nullable=False,
                server_default="always",
            )
        )
