"""System / singleton-row tables: cache version, Telemt free-user params."""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer
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
