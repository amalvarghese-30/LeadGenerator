"""SQLAlchemy ORM model — ResearchReport (MySQL)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ResearchReport(Base, TimestampMixin):
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, default="provider_research")
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
