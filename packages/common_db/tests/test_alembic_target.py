"""Step 5: keep common_db.Base.metadata aligned with alembic's HEAD.

Alembic's autogenerate target is `app.database.models.Base.metadata`,
which after Step 5 *is* `common_db.Base.metadata`. If the two diverge —
a new model added without a migration, or a migration adding a column to
a table that has no model property — autogenerate will silently propose
to drop/recreate the column on the next dev who runs `alembic revision`.

This test pins the set of tables that should live in common_db. It does
NOT validate types/columns column-by-column — that's what test_canon.py
is for; here we only assert *which tables* belong.

Update procedure when adding a new model:
  1. Add the model class in packages/common_db/common_db/models/.
  2. Add the alembic migration creating its table.
  3. Add the table name to CANONICAL_TABLES below.
"""
from __future__ import annotations

import common_db
import common_db.models  # noqa: F401  -- side-effect: populate metadata


CANONICAL_TABLES = frozenset({
    "cache_version",
    "disabled_users",
    "email_verifications",
    "google_play_purchases",
    "google_play_skus",
    "menu_buttons",
    "menu_screens",
    "promo_settings",
    "promos",
    "refresh_tokens",
    "squad_profiles",
    "support_messages",
    "support_tickets",
    "tariff_plans",
    "tariff_prices",
    "telegram_link_codes",
    "telemt_free_params",
    "transactions",
    "users",
    "webapp_menu_nodes",
})

# Tables created by alembic but intentionally NOT modelled in common_db.
# Adding entries here is rare — it's an explicit acknowledgement that
# the table exists in production but the unified codebase does not access
# it. Currently only `support_users` qualifies: it belongs to the legacy
# standalone support bot which lives outside the unified DB.
VESTIGIAL_TABLES = frozenset({"support_users"})


def test_common_db_metadata_exact_table_set() -> None:
    actual = set(common_db.Base.metadata.tables.keys())
    missing = CANONICAL_TABLES - actual
    extra = actual - CANONICAL_TABLES
    assert not missing, (
        f"common_db.Base.metadata is missing tables: {sorted(missing)}. "
        "Did you forget to import the model module in common_db/models/__init__.py?"
    )
    assert not extra, (
        f"common_db.Base.metadata has unexpected tables: {sorted(extra)}. "
        "Either add them to CANONICAL_TABLES (and write an alembic migration) "
        "or remove the model class."
    )


def test_no_vestigial_tables_leaked_into_metadata() -> None:
    """Vestigial tables (e.g. support_users) belong to legacy isolated
    services and must NOT appear in the unified metadata. If they do,
    alembic autogenerate would propose changes against tables the
    unified codebase has no business touching."""
    actual = set(common_db.Base.metadata.tables.keys())
    overlap = VESTIGIAL_TABLES & actual
    assert not overlap, (
        f"Vestigial tables leaked into common_db.Base.metadata: {sorted(overlap)}. "
        "Remove the model class — these tables are managed by a separate service."
    )


def test_canonical_and_vestigial_sets_are_disjoint() -> None:
    """Sanity check on the two table-set constants in this test file."""
    overlap = CANONICAL_TABLES & VESTIGIAL_TABLES
    assert not overlap, f"set overlap (fix the constants): {sorted(overlap)}"
