"""Bot menu screens/buttons + dashboard-built webapp menu tree.

WebAppMenuNode lived in dashboard/backend/database/models.py but not in
app/database/models.py — the table itself was created by alembic 0001 and
widened by 0010 (text and invoice_tariff_slug to String(255)). We mirror
the post-0010 widths here so autogenerate stays silent.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class MenuScreen(Base):
    __tablename__ = "menu_screens"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    message_text_ru: Mapped[str] = mapped_column(Text, nullable=True)
    message_text_en: Mapped[str] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    buttons: Mapped[list["MenuButton"]] = relationship(
        back_populates="screen", cascade="all, delete-orphan"
    )


class MenuButton(Base):
    __tablename__ = "menu_buttons"

    id: Mapped[int] = mapped_column(primary_key=True)
    screen_id: Mapped[int] = mapped_column(
        ForeignKey("menu_screens.id", ondelete="CASCADE")
    )
    text_ru: Mapped[str] = mapped_column(String(200))
    text_en: Mapped[str] = mapped_column(String(200))
    callback_data: Mapped[str] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=True)
    row: Mapped[int] = mapped_column(Integer, default=0)
    col: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    button_type: Mapped[str] = mapped_column(String(20), default="callback")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    visibility_condition: Mapped[str] = mapped_column(String(50), default="always")

    screen: Mapped["MenuScreen"] = relationship(back_populates="buttons")


class WebAppMenuNode(Base):
    """Tree of webapp menu nodes built in the dashboard tariff constructor.

    A node is either a `buttons` group (renders a sublist) or an `invoice`
    leaf that triggers payment creation when tapped in the webapp.
    """

    __tablename__ = "webapp_menu_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("webapp_menu_nodes.id", ondelete="CASCADE"), nullable=True
    )
    # Widened to 255 by alembic 0010.
    text: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(20), default="buttons")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    # Invoice action params (NULL when action != "invoice").
    invoice_provider: Mapped[str] = mapped_column(String(30), nullable=True)
    invoice_amount: Mapped[float] = mapped_column(Float, nullable=True)
    invoice_currency: Mapped[str] = mapped_column(String(10), nullable=True)
    invoice_method: Mapped[str] = mapped_column(String(30), nullable=True)
    invoice_days: Mapped[int] = mapped_column(Integer, nullable=True)
    # Widened to 255 by alembic 0010.
    invoice_tariff_slug: Mapped[str] = mapped_column(String(255), nullable=True)

    parent: Mapped["WebAppMenuNode"] = relationship(
        "WebAppMenuNode",
        remote_side="WebAppMenuNode.id",
        back_populates="children",
    )
    children: Mapped[list["WebAppMenuNode"]] = relationship(
        "WebAppMenuNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="WebAppMenuNode.sort_order",
    )

    __table_args__ = (Index("ix_webapp_menu_nodes_parent_id", "parent_id"),)
