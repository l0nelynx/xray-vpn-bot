"""Application-level API health and request telemetry models."""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class _ApiMetricMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket_start: Mapped[str] = mapped_column(String(30), nullable=False)
    service: Mapped[str] = mapped_column(String(24), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    duration_sum_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_max_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    response_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    histogram_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    dropped_events: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class ApiMetricMinute(_ApiMetricMixin, Base):
    __tablename__ = "api_metric_minutes"
    __table_args__ = (
        UniqueConstraint("bucket_start", "service", "method", "route", "status_code", name="ux_api_metric_minute_key"),
        Index("ix_api_metric_minutes_bucket", "bucket_start"),
        Index("ix_api_metric_minutes_service_bucket", "service", "bucket_start"),
    )


class ApiMetricHour(_ApiMetricMixin, Base):
    __tablename__ = "api_metric_hours"
    __table_args__ = (
        UniqueConstraint("bucket_start", "service", "method", "route", "status_code", name="ux_api_metric_hour_key"),
        Index("ix_api_metric_hours_bucket", "bucket_start"),
        Index("ix_api_metric_hours_service_bucket", "service", "bucket_start"),
    )


class ApiErrorEvent(Base):
    __tablename__ = "api_error_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[str] = mapped_column(String(30), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    service: Mapped[str] = mapped_column(String(24), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_channel: Mapped[str | None] = mapped_column(String(24), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    response_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    exception_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_api_errors_occurred", "occurred_at"),
        Index("ix_api_errors_service_occurred", "service", "occurred_at"),
        Index("ix_api_errors_route_occurred", "route", "occurred_at"),
        Index("ix_api_errors_status_occurred", "status_code", "occurred_at"),
        Index("ix_api_errors_user", "user_id"),
        Index("ix_api_errors_tg", "tg_id"),
        Index("ix_api_errors_ip", "client_ip"),
        Index("ix_api_errors_fingerprint", "error_fingerprint"),
    )


class ApiServiceStatus(Base):
    __tablename__ = "api_service_status"

    service: Mapped[str] = mapped_column(String(24), primary_key=True)
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checked_at: Mapped[str] = mapped_column(String(30), nullable=False)
    last_ok_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class ApiAlertState(Base):
    __tablename__ = "api_alert_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_sent_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False)
