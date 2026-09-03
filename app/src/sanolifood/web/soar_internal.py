import hmac
from datetime import timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sanolifood.core.config import get_settings
from sanolifood.core.events import record_event
from sanolifood.database.session import get_db
from sanolifood.services.soar_controls import (
    active_control,
    active_control_count,
    apply_control,
    rollback_control,
    validate_control_target,
)


router = APIRouter(prefix="/internal/soar", tags=["soar-internal"])


class ControlRequest(BaseModel):
    action_id: str = Field(min_length=8, max_length=36)
    incident_id: str = Field(min_length=8, max_length=36)
    control_type: str
    target: str = Field(min_length=1, max_length=255)
    ttl_seconds: int
    reason: str = Field(min_length=8, max_length=500)
    details: dict[str, Any] = Field(default_factory=dict)


class EnforcementProbeRequest(BaseModel):
    control_type: str
    target: str = Field(min_length=1, max_length=255)


def require_soar_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    configured = get_settings().soar_internal_token.get_secret_value()
    supplied = ""
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization[7:]
    if not configured or not hmac.compare_digest(configured, supplied):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SOAR service authentication failed",
        )


def serialize_control(control) -> dict[str, Any]:
    return {
        "action_id": control.action_id,
        "incident_id": control.incident_id,
        "control_type": control.control_type,
        "target": control.target,
        "active": control.active,
        "applied_at": control.applied_at.astimezone(timezone.utc).isoformat(),
        "expires_at": control.expires_at.astimezone(timezone.utc).isoformat(),
        "revoked_at": control.revoked_at.astimezone(timezone.utc).isoformat()
        if control.revoked_at
        else None,
    }


@router.get("/status", dependencies=[Depends(require_soar_token)])
def soar_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"status": "ready", "active_controls": active_control_count(db), "schema_version": 1}


@router.post("/enforcement-probe", dependencies=[Depends(require_soar_token)])
def enforcement_probe(
    payload: EnforcementProbeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evaluate the same application guard used by the live control paths.

    The probe is read-only: it confirms whether the application would allow or
    deny the requested operation without creating a login attempt, releasing a
    production lot or changing any business record.
    """
    try:
        target = validate_control_target(
            payload.control_type,
            payload.target,
            get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    control = active_control(db, payload.control_type, target)
    guard_names = {
        "app_ip_block": "http_request",
        "app_account_lock": "authentication",
        "quality_guard": "quality_release",
    }
    return {
        "schema_version": 1,
        "control_type": payload.control_type,
        "target": target,
        "guard": guard_names[payload.control_type],
        "decision": "deny" if control is not None else "allow",
        "enforced": control is not None,
        "action_id": control.action_id if control is not None else None,
        "incident_id": control.incident_id if control is not None else None,
    }


@router.post("/controls", dependencies=[Depends(require_soar_token)])
def create_control(
    payload: ControlRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        control, created = apply_control(
            db,
            action_id=payload.action_id,
            incident_id=payload.incident_id,
            control_type=payload.control_type,
            target=payload.target,
            ttl_seconds=payload.ttl_seconds,
            reason=payload.reason,
            details=payload.details,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if created:
        record_event(
            db,
            request=request,
            event_type="soar.control.applied",
            outcome="success",
            actor_username="soar-controller",
            resource_type="soar_control",
            resource_id=control.action_id,
            details={
                "incident_id": control.incident_id,
                "control_type": control.control_type,
                "target": control.target,
                "expires_at": control.expires_at.isoformat(),
            },
        )
    db.commit()
    return {"created": created, "control": serialize_control(control)}


@router.post("/controls/{action_id}/rollback", dependencies=[Depends(require_soar_token)])
def revoke_control(
    action_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    control, changed = rollback_control(db, action_id)
    if control is None:
        raise HTTPException(status_code=404, detail="SOAR control not found")
    if changed:
        record_event(
            db,
            request=request,
            event_type="soar.control.rolled_back",
            outcome="success",
            actor_username="soar-controller",
            resource_type="soar_control",
            resource_id=control.action_id,
            details={
                "incident_id": control.incident_id,
                "control_type": control.control_type,
                "target": control.target,
            },
        )
    db.commit()
    return {"changed": changed, "control": serialize_control(control)}
