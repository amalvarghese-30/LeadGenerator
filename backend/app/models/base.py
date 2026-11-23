"""
SQLAlchemy 2.0 declarative base with UUID primary key and timestamp mixin.
Used by the new MySQL ORM models (separate from existing MongoDB Pydantic documents).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base for all SQLAlchemy / MySQL models."""
    pass


class TimestampMixin:
    """Adds created_at / updated_at columns with server-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
