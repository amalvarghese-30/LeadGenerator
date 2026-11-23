"""SQLAlchemy ORM model — Provider (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    services: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    discovery_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="pending")
    verification_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="unverified")
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="manual")
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True), nullable=True
    )
    crawl_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", back_populates="providers", foreign_keys=[created_by]
    )
    client_references: Mapped[list["ProviderClientReference"]] = relationship(  # noqa: F821
        "ProviderClientReference", back_populates="provider"
    )
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(  # noqa: F821
        "CrawlJob", back_populates="provider"
    )
    crawl_pages: Mapped[list["CrawlPage"]] = relationship(  # noqa: F821
        "CrawlPage", back_populates="provider"
    )
