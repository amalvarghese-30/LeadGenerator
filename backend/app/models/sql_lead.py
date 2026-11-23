"""SQLAlchemy ORM model — Lead (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dedup_key: Mapped[Optional[str]] = mapped_column(String(512), unique=True, nullable=True)
    contact_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    crm_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    lead_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    lead_priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    qualification_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="unqualified")
    outreach_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lead_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    follow_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    contact: Mapped[Optional["Contact"]] = relationship(  # noqa: F821
        "Contact", back_populates="leads"
    )
    company: Mapped[Optional["Company"]] = relationship(  # noqa: F821
        "Company", back_populates="leads"
    )
