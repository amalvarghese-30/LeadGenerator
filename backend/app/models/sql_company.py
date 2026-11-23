"""SQLAlchemy ORM model — Company (MySQL)."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dedup_key: Mapped[Optional[str]] = mapped_column(String(512), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    public_contact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    social_profiles: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        "Contact", back_populates="company"
    )
    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        "Lead", back_populates="company"
    )
    client_references: Mapped[list["ProviderClientReference"]] = relationship(  # noqa: F821
        "ProviderClientReference", back_populates="company"
    )
