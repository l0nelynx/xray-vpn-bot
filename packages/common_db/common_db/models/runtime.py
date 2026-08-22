"""Runtime settings and payment integrations stored in Postgres.

Dual-source period: YAML remains the fallback until an operator saves values
in the Dashboard (``managed=True`` for payments; keys present in the runtime
JSON for overlay settings).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class AppRuntimeSettings(Base):
    """Singleton (id=1) JSON blob for operator-editable runtime config."""

    __tablename__ = "app_runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    updated_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class DashboardBrandingAsset(Base):
    """Validated logo snapshot used by the Dashboard and its public PWA assets."""

    __tablename__ = "dashboard_branding_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, default="", server_default="")
    mime_type: Mapped[str] = mapped_column(String(40))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String(30))
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PaymentIntegration(Base):
    """Per-provider payment credentials managed from the Dashboard.

    When ``managed`` is False the YAML payment block is still the source of
    truth (row may exist only as an import placeholder). After the first
    Dashboard save, ``managed`` becomes True and DB wins.
    """

    __tablename__ = "payment_integrations"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    managed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    encrypted_config: Mapped[str] = mapped_column(Text, default="", server_default="")
    updated_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class AppIntegration(Base):
    """Encrypted service credentials (SMTP, Android JWT, Telemt, Store, FCM, …).

    Same dual-source semantics as :class:`PaymentIntegration`: YAML until
    ``managed=True`` after the first Dashboard save.
    """

    __tablename__ = "app_integrations"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    managed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    encrypted_config: Mapped[str] = mapped_column(Text, default="", server_default="")
    updated_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
