"""SQLAlchemy ORM model — ProviderClientReference (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProviderClientReference(Base, TimestampMixin):
    __tablename__ = "provider_client_references"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dedup_key: Mapped[Optional[str]] = mapped_column(String(512), unique=True, nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    person_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    evidence_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relationship_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="client")
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verification_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="unverified")
    verified_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    provider: Mapped[Optional["Provider"]] = relationship(  # noqa: F821
        "Provider", back_populates="client_references"
    )
    company: Mapped[Optional["Company"]] = relationship(  # noqa: F821
        "Company", back_populates="client_references"
    )
