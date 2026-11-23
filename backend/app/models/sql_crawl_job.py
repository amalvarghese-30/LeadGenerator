"""SQLAlchemy ORM model — CrawlJob (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CrawlJob(Base, TimestampMixin):
    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    starting_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full_research")
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_analysed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    references_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contacts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    companies_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    errors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    warnings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    lock_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Relationships
    provider: Mapped[Optional["Provider"]] = relationship(  # noqa: F821
        "Provider", back_populates="crawl_jobs"
    )
    events: Mapped[list["JobEvent"]] = relationship(  # noqa: F821
        "JobEvent", back_populates="job", cascade="all, delete-orphan"
    )
    pages: Mapped[list["CrawlPage"]] = relationship(  # noqa: F821
        "CrawlPage", back_populates="job", cascade="all, delete-orphan"
    )
