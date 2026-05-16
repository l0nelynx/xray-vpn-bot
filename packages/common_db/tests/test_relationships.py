"""Relationship wiring tests.

These resolve every ORM relationship configured in the package. A typo
in a `back_populates` or a missing import in models/__init__.py surfaces
here at import time rather than at first query in production.
"""
from __future__ import annotations

from sqlalchemy.orm import configure_mappers

from common_db.models import (
    MenuButton,
    MenuScreen,
    SquadProfile,
    SupportMessage,
    SupportTicket,
    TariffPlan,
    TariffPrice,
    Transaction,
    User,
    WebAppMenuNode,
)


def test_configure_mappers_succeeds() -> None:
    # Forces SQLAlchemy to resolve every relationship string. Any unresolved
    # ref or back_populates typo raises here.
    configure_mappers()


class TestUserTransactions:
    def test_user_has_transactions(self) -> None:
        rel = User.__mapper__.relationships["transactions"]
        assert rel.mapper.class_ is Transaction
        assert rel.back_populates == "user"

    def test_transaction_has_user(self) -> None:
        rel = Transaction.__mapper__.relationships["user"]
        assert rel.mapper.class_ is User
        assert rel.back_populates == "transactions"


class TestSupportThread:
    def test_ticket_has_messages_cascade(self) -> None:
        rel = SupportTicket.__mapper__.relationships["messages"]
        assert rel.mapper.class_ is SupportMessage
        assert rel.back_populates == "ticket"
        # delete-orphan ensures orphaned messages are deleted with the ticket.
        assert "delete-orphan" in rel.cascade

    def test_message_has_ticket(self) -> None:
        rel = SupportMessage.__mapper__.relationships["ticket"]
        assert rel.mapper.class_ is SupportTicket
        assert rel.back_populates == "messages"


class TestTariffGraph:
    def test_squad_to_tariffs(self) -> None:
        rel = SquadProfile.__mapper__.relationships["tariffs"]
        assert rel.mapper.class_ is TariffPlan
        assert rel.back_populates == "squad_profile"

    def test_tariff_to_squad(self) -> None:
        rel = TariffPlan.__mapper__.relationships["squad_profile"]
        assert rel.mapper.class_ is SquadProfile
        assert rel.back_populates == "tariffs"

    def test_tariff_has_prices_cascade(self) -> None:
        rel = TariffPlan.__mapper__.relationships["prices"]
        assert rel.mapper.class_ is TariffPrice
        assert "delete-orphan" in rel.cascade

    def test_price_has_tariff(self) -> None:
        rel = TariffPrice.__mapper__.relationships["tariff"]
        assert rel.mapper.class_ is TariffPlan


class TestMenuGraph:
    def test_screen_to_buttons_cascade(self) -> None:
        rel = MenuScreen.__mapper__.relationships["buttons"]
        assert rel.mapper.class_ is MenuButton
        assert "delete-orphan" in rel.cascade

    def test_button_to_screen(self) -> None:
        rel = MenuButton.__mapper__.relationships["screen"]
        assert rel.mapper.class_ is MenuScreen


class TestWebAppMenuNodeSelfRef:
    def test_node_has_parent_and_children(self) -> None:
        parent_rel = WebAppMenuNode.__mapper__.relationships["parent"]
        children_rel = WebAppMenuNode.__mapper__.relationships["children"]
        assert parent_rel.mapper.class_ is WebAppMenuNode
        assert children_rel.mapper.class_ is WebAppMenuNode
        assert parent_rel.back_populates == "children"
        assert children_rel.back_populates == "parent"
        assert "delete-orphan" in children_rel.cascade
