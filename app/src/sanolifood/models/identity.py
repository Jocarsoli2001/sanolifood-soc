from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sanolifood.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(StrEnum):
    ADMIN = "admin"
    PRODUCTION = "production"
    QUALITY = "quality"
    WAREHOUSE = "warehouse"
    AUDITOR = "auditor"


ROLE_LABELS: dict[str, str] = {
    UserRole.ADMIN: "Administrador",
    UserRole.PRODUCTION: "Producción",
    UserRole.QUALITY: "Calidad",
    UserRole.WAREHOUSE: "Almacén",
    UserRole.AUDITOR: "Auditor",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default=UserRole.AUDITOR)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
