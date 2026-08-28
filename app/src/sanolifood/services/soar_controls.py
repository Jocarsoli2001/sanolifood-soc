import ipaddress
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sanolifood.core.config import Settings, get_settings
from sanolifood.models import SoarControl


CONTROL_TYPES = frozenset({"app_ip_block", "app_account_lock", "quality_guard"})
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,49}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalized_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def validate_control_target(control_type: str, target: str, settings: Settings) -> str:
    normalized = target.strip()
    if control_type not in CONTROL_TYPES:
        raise ValueError("El tipo de control SOAR no está permitido.")

    if control_type == "app_ip_block":
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            raise ValueError("La dirección de contención no es válida.") from None
        if address.version != 4 or address.is_multicast or address.is_unspecified or address.is_loopback:
            raise ValueError("La dirección no es apta para contención.")
        if str(address) in settings.soar_protected_ips_set:
            raise ValueError("La dirección pertenece a un activo protegido.")
        allowed_networks = [ipaddress.ip_network(value, strict=False) for value in settings.soar_allowed_cidrs_list]
        if not any(address in network for network in allowed_networks):
            raise ValueError("La dirección está fuera de los segmentos autorizados del laboratorio.")
        return str(address)

    if control_type == "app_account_lock":
        normalized = normalized.lower()
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("El usuario objetivo no tiene un formato válido.")
        if normalized in settings.soar_protected_users_set:
            raise ValueError("La cuenta pertenece a una identidad protegida.")
        return normalized

    if normalized != "quality-release":
        raise ValueError("El guard de calidad solo admite el objetivo quality-release.")
    return normalized


def apply_control(
    db: Session,
    *,
    action_id: str,
    incident_id: str,
    control_type: str,
    target: str,
    ttl_seconds: int,
    reason: str,
    details: dict | None = None,
    settings: Settings | None = None,
) -> tuple[SoarControl, bool]:
    active_settings = settings or get_settings()
    if not 60 <= ttl_seconds <= active_settings.soar_max_ttl_seconds:
        raise ValueError(
            f"El TTL debe estar entre 60 y {active_settings.soar_max_ttl_seconds} segundos."
        )
    if not 8 <= len(reason.strip()) <= 500:
        raise ValueError("La justificación debe contener entre 8 y 500 caracteres.")
    normalized_target = validate_control_target(control_type, target, active_settings)

    existing = db.scalar(select(SoarControl).where(SoarControl.action_id == action_id))
    if existing is not None:
        same_request = (
            existing.incident_id == incident_id
            and existing.control_type == control_type
            and existing.target == normalized_target
        )
        if not same_request:
            raise ValueError("El identificador de acción ya pertenece a otro control.")
        return existing, False

    now = utcnow()
    control = SoarControl(
        action_id=action_id,
        incident_id=incident_id,
        control_type=control_type,
        target=normalized_target,
        reason=reason.strip(),
        active=True,
        applied_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        details=details or {},
    )
    db.add(control)
    db.flush()
    return control, True


def rollback_control(db: Session, action_id: str) -> tuple[SoarControl | None, bool]:
    control = db.scalar(
        select(SoarControl).where(SoarControl.action_id == action_id).with_for_update()
    )
    if control is None:
        return None, False
    if not control.active:
        return control, False
    control.active = False
    control.revoked_at = utcnow()
    db.flush()
    return control, True


def active_control(
    db: Session,
    control_type: str,
    target: str,
    *,
    at: datetime | None = None,
) -> SoarControl | None:
    current_time = at or utcnow()
    return db.scalar(
        select(SoarControl)
        .where(
            SoarControl.control_type == control_type,
            SoarControl.target == target,
            SoarControl.active.is_(True),
            SoarControl.expires_at > current_time,
        )
        .order_by(SoarControl.expires_at.desc())
    )


def active_control_count(db: Session, *, at: datetime | None = None) -> int:
    current_time = at or utcnow()
    return int(
        db.scalar(
            select(func.count())
            .select_from(SoarControl)
            .where(SoarControl.active.is_(True), SoarControl.expires_at > current_time)
        )
        or 0
    )
