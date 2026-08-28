from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sanolifood.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SoarControl(Base):
    """A reversible business-application control requested by the SOAR plane."""

    __tablename__ = "soar_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    incident_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    control_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    target: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
