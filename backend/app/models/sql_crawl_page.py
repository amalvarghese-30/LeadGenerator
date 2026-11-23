"""SQLAlchemy ORM model — CrawlPage (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CrawlPage(Base):
    __tablename__ = "crawl_pages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    canonical_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="httpx")
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped[Optional["CrawlJob"]] = relationship(  # noqa: F821
        "CrawlJob", back_populates="pages"
    )
    provider: Mapped[Optional["Provider"]] = relationship(  # noqa: F821
        "Provider", back_populates="crawl_pages"
    )
