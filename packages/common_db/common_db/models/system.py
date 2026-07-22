"""System / singleton-row tables: cache version, Telemt free-user params, feature flags."""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class CacheVersion(Base):
    __tablename__ = "cache_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class TelmtFreeParams(Base):
    """Single-row settings table for Telemt free user parameters."""

    __tablename__ = "telemt_free_params"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_tcp_conns: Mapped[int] = mapped_column(Integer, nullable=True)
    max_unique_ips: Mapped[int] = mapped_column(Integer, nullable=True)
    data_quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    expire_days: Mapped[int] = mapped_column(Integer, default=30)
    rate_limit_up_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rate_limit_down_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BotFeatureFlags(Base):
    """Single-row feature-flag table (id=1).

    legacy_bot_constructor: when True, the in-bot tariff menus and inline
    payment flow (app/bot_constructor/) are registered on the aiogram dispatcher
    at bot startup. Requires a bot restart to take effect after toggling.
    """

    __tablename__ = "bot_feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legacy_bot_constructor: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
