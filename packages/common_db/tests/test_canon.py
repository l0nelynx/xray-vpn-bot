"""Schema canon — each assertion mirrors the table from the agreed audit.

When a model in common_db.models is edited, these tests pin the contract.
If you change a model intentionally, update both the model and the
matching assertion (and write an Alembic migration if it affects prod).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, Text

from common_db import Base
from common_db.models import (
    GooglePlayPurchase,
    GooglePlaySku,
    MenuButton,
    Promo,
    PromoSettings,
    SupportMessage,
    SupportTicket,
    TariffPlan,
    Transaction,
    User,
    WebAppMenuNode,
)


# ---------------------------------------------------------------- helpers ----
def _col(model, name):
    return model.__table__.c[name]


def _has_index(model, name) -> bool:
    return any(idx.name == name for idx in model.__table__.indexes)


def _server_default(col):
    """Return server_default literal as a plain string for comparison."""
    if col.server_default is None:
        return None
    arg = col.server_default.arg
    # arg can be a sa.text() clause or a plain string
    return str(getattr(arg, "text", arg))


# ------------------------------------------------------------------- User ----
class TestUserCanon:
    def test_id_is_big_integer_pk(self) -> None:
        col = _col(User, "id")
        assert isinstance(col.type, BigInteger)
        assert col.primary_key is True

    def test_tg_id_is_not_unique(self) -> None:
        # Alembic 0009 dropped the unique constraint; models must reflect this.
        col = _col(User, "tg_id")
        assert col.unique in (None, False), "tg_id must not be unique on prod"
        # Also verify no Unique-constraint object hides in __table_args__.
        from sqlalchemy import UniqueConstraint
        for c in User.__table__.constraints:
            if isinstance(c, UniqueConstraint):
                assert "tg_id" not in c.columns.keys()

    def test_vip_is_big_integer_with_defaults(self) -> None:
        col = _col(User, "vip")
        assert isinstance(col.type, BigInteger)
        assert col.default is not None and col.default.arg == 0
        assert _server_default(col) == "0"
        assert col.nullable is True

    def test_api_provider_python_default_remnawave(self) -> None:
        # Canon: Python-side default flipped to "remnawave"; DB server_default
        # still "marzban" historically — kept until a dedicated migration.
        col = _col(User, "api_provider")
        assert col.default is not None and col.default.arg == "remnawave"
        assert _server_default(col) == "marzban"

    def test_language_default_none_server_default_ru(self) -> None:
        col = _col(User, "language")
        # mapped_column(default=None) does not register a ColumnDefault.
        assert col.default is None
        assert _server_default(col) == "ru"

    def test_is_banned_defaults(self) -> None:
        col = _col(User, "is_banned")
        assert isinstance(col.type, Boolean)
        assert col.default is not None and col.default.arg is False
        assert _server_default(col) == "0"
        assert col.nullable is True

    def test_email_unique_index(self) -> None:
        assert _has_index(User, "ix_users_email_unique")
        idx = next(i for i in User.__table__.indexes if i.name == "ix_users_email_unique")
        assert idx.unique is True

    def test_username_indexed(self) -> None:
        assert _has_index(User, "ix_user_username")


# -------------------------------------------------------- SupportTicket -----
class TestSupportTicketCanon:
    def test_id_is_big_integer_pk(self) -> None:
        col = _col(SupportTicket, "id")
        assert isinstance(col.type, BigInteger)
        assert col.primary_key is True

    def test_user_id_is_big_integer_fk(self) -> None:
        col = _col(SupportTicket, "user_id")
        assert isinstance(col.type, BigInteger)
        assert any(fk.column.name == "id" and fk.column.table.name == "users"
                   for fk in col.foreign_keys)

    def test_status_defaults(self) -> None:
        col = _col(SupportTicket, "status")
        assert col.default is not None and col.default.arg == "open"
        assert _server_default(col) == "open"

    def test_indexes_present(self) -> None:
        assert _has_index(SupportTicket, "ix_support_tickets_user_id")
        assert _has_index(SupportTicket, "ix_support_tickets_status")

    def test_subject_and_message_types(self) -> None:
        assert isinstance(_col(SupportTicket, "subject").type, String)
        assert isinstance(_col(SupportTicket, "message").type, Text)


# ------------------------------------------------------- SupportMessage -----
class TestSupportMessageCanon:
    def test_id_is_big_integer_pk(self) -> None:
        col = _col(SupportMessage, "id")
        assert isinstance(col.type, BigInteger)
        assert col.primary_key is True

    def test_ticket_id_is_big_integer_fk_cascade(self) -> None:
        col = _col(SupportMessage, "ticket_id")
        assert isinstance(col.type, BigInteger)
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"
        assert fk.column.table.name == "support_tickets"

    def test_index_present(self) -> None:
        assert _has_index(SupportMessage, "ix_support_messages_ticket_id")


# --------------------------------------------------------------- Promo ------
class TestPromoCanon:
    def test_used_promo_consumed_defaults(self) -> None:
        col = _col(Promo, "used_promo_consumed")
        assert col.default is not None and col.default.arg is False
        assert _server_default(col) == "0"

    def test_promo_settings_default_discount_percent(self) -> None:
        col = _col(PromoSettings, "default_discount_percent")
        assert col.default is not None and col.default.arg == 20


# ---------------------------------------------------------- Transaction ----
class TestTransactionCanon:
    def test_username_nullable_str50(self) -> None:
        col = _col(Transaction, "username")
        assert isinstance(col.type, String)
        assert col.type.length == 50
        assert col.nullable is True

    def test_tariff_slug_nullable_str200(self) -> None:
        col = _col(Transaction, "tariff_slug")
        assert isinstance(col.type, String)
        assert col.type.length == 200
        assert col.nullable is True

    def test_android_user_id_nullable_integer_indexed(self) -> None:
        col = _col(Transaction, "android_user_id")
        assert isinstance(col.type, Integer)
        assert not isinstance(col.type, BigInteger)
        assert col.nullable is True
        assert _has_index(Transaction, "ix_transactions_android_user_id")

    def test_user_relationship_back_populates(self) -> None:
        rel = Transaction.__mapper__.relationships["user"]
        assert rel.back_populates == "transactions"


# -------------------------------------------------- WebAppMenuNode widths --
class TestWebAppMenuNodeCanon:
    def test_text_widened_to_255(self) -> None:
        # Alembic 0010 widened both columns; Python model must match.
        assert _col(WebAppMenuNode, "text").type.length == 255

    def test_invoice_tariff_slug_widened_to_255(self) -> None:
        assert _col(WebAppMenuNode, "invoice_tariff_slug").type.length == 255

    def test_self_ref_index(self) -> None:
        assert _has_index(WebAppMenuNode, "ix_webapp_menu_nodes_parent_id")


# ----------------------------------------------------------- TariffPlan ----
class TestTariffPlanCanon:
    def test_squad_profile_id_is_big_integer(self) -> None:
        # Alembic 0007 widened the FK column.
        assert isinstance(_col(TariffPlan, "squad_profile_id").type, BigInteger)


# --------------------------------------------------- Google Play canon ----
class TestGooglePlayCanon:
    def test_acknowledged_server_default_zero(self) -> None:
        assert _server_default(_col(GooglePlayPurchase, "acknowledged")) == "0"

    def test_auto_renewing_server_default_zero(self) -> None:
        assert _server_default(_col(GooglePlayPurchase, "auto_renewing")) == "0"

    def test_sku_active_server_default_one(self) -> None:
        assert _server_default(_col(GooglePlaySku, "active")) == "1"


# ------------------------------------------------------- menus canon ------
class TestMenuButtonCanon:
    def test_visibility_condition_default(self) -> None:
        col = _col(MenuButton, "visibility_condition")
        assert col.default is not None and col.default.arg == "always"


# -------------------------------------------------- nullable-or-default ---
class TestNonNullableHaveDefaults:
    """Every NOT NULL column without a Python-time or server-time default
    must be supplied by application code at insert. We don't enforce that
    here; we just confirm that the columns we *do* mark "default available"
    actually have one — guards against silently dropping a default."""

    def test_user_is_banned_has_default(self) -> None:
        col = _col(User, "is_banned")
        assert col.default is not None or col.server_default is not None

    def test_ticket_status_has_default(self) -> None:
        col = _col(SupportTicket, "status")
        assert col.default is not None and col.server_default is not None


# ------------------------------------------------- Base.metadata sanity ---
class TestMetadataSanity:
    def test_expected_tables_present(self) -> None:
        expected = {
            "users",
            "disabled_users",
            "promos",
            "promo_settings",
            "transactions",
            "support_tickets",
            "support_messages",
            "squad_profiles",
            "tariff_plans",
            "tariff_prices",
            "menu_screens",
            "menu_buttons",
            "webapp_menu_nodes",
            "refresh_tokens",
            "email_verifications",
            "telegram_link_codes",
            "google_play_purchases",
            "google_play_skus",
            "cache_version",
            "telemt_free_params",
        }
        assert expected <= set(Base.metadata.tables.keys())
