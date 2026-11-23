"""SQLAlchemy ORM models — Rate Limit entities (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DomainRateProfile(Base, TimestampMixin):
    __tablename__ = "domain_rate_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    recommended_delay_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    last_request_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_in_cooldown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_429_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_403_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RateLimitRequestLog(Base):
    __tablename__ = "rate_limit_request_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cf_ray: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
