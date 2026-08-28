import hmac
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sanolifood.soar import SOAR_SCHEMA_VERSION
from sanolifood.soar.catalog import get_catalog
from sanolifood.soar.config import get_soar_settings
from sanolifood.soar.database import SoarBase, get_soar_db, soar_engine
from sanolifood.soar.models import Incident, OrchestrationError, SoarAudit
from sanolifood.soar.schemas import DecisionRequest, NormalizedAlert, OrchestrationErrorRequest
from sanolifood.soar.service import SoarService, isoformat


settings = get_soar_settings()
catalog = get_catalog()


@asynccontextmanager
async def lifespan(_: FastAPI):
    SoarBase.metadata.create_all(soar_engine)
    yield
    soar_engine.dispose()


app = FastAPI(
    title="SanoliFood SOAR Controller",
    version="0.7.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)


def require_internal_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.soar_internal_token.get_secret_value()
    supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SOAR controller authentication failed",
        )


def service(db: Session) -> SoarService:
    return SoarService(db, catalog, settings)


@app.get("/healthz", tags=["platform"])
def health(db: Session = Depends(get_soar_db)) -> dict[str, Any]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ready",
        "service": "sanolifood-soar-controller",
        "version": "0.7.0",
        "schema_version": SOAR_SCHEMA_VERSION,
        "catalog_version": catalog.catalog_version,
        "response_mode": settings.response_mode,
    }


@app.get("/api/v1/capabilities", dependencies=[Depends(require_internal_token)])
def capabilities() -> dict[str, Any]:
    return {
        "schema_version": SOAR_SCHEMA_VERSION,
        "catalog_version": catalog.catalog_version,
        "response_mode": settings.response_mode,
        "routed_rule_ids": catalog.routed_rule_ids,
        "playbooks": [
            {
                "id": playbook.id,
                "name": playbook.name,
                "priority": playbook.priority,
                "rule_ids": playbook.rule_ids,
                "actions": [action.model_dump() for action in playbook.actions],
            }
            for playbook in catalog.playbooks
        ],
    }


@app.post("/api/v1/incidents", status_code=202, dependencies=[Depends(require_internal_token)])
def create_incident(
    payload: NormalizedAlert,
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    active_service = service(db)
    try:
        incident, created = active_service.create_incident(payload)
        db.commit()
        incident = active_service.get_incident(incident.id)
    except IntegrityError as exc:
        db.rollback()
        incident = active_service.get_incident_by_dedup(payload.dedup_key)
        if incident is None:
            raise HTTPException(status_code=409, detail="Concurrent incident creation failed") from exc
        created = False
    except (KeyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"created": created, "incident": active_service.serialize_incident(incident)}


@app.get("/api/v1/incidents", dependencies=[Depends(require_internal_token)])
def list_incidents(
    incident_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    active_service = service(db)
    incidents = active_service.list_incidents(status=incident_status, limit=limit)
    return {"count": len(incidents), "items": [active_service.serialize_incident(item) for item in incidents]}


@app.get("/api/v1/incidents/{incident_id}", dependencies=[Depends(require_internal_token)])
def get_incident(incident_id: str, db: Session = Depends(get_soar_db)) -> dict[str, Any]:
    active_service = service(db)
    try:
        incident = active_service.get_incident(incident_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"incident": active_service.serialize_incident(incident)}


@app.post("/api/v1/incidents/{incident_id}/decision", dependencies=[Depends(require_internal_token)])
def decide_incident(
    incident_id: str,
    payload: DecisionRequest,
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    active_service = service(db)
    try:
        incident = active_service.decide(incident_id, payload)
        db.commit()
        incident = active_service.get_incident(incident.id)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"incident": active_service.serialize_incident(incident)}


@app.post("/api/v1/incidents/{incident_id}/dispatch", dependencies=[Depends(require_internal_token)])
def dispatch_incident(
    incident_id: str,
    scope: str = Query(pattern="^(automatic|approved)$"),
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    active_service = service(db)
    try:
        incident = active_service.dispatch(incident_id, scope)
        db.commit()
        incident = active_service.get_incident(incident.id)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"incident": active_service.serialize_incident(incident), "dispatch_scope": scope}


@app.post("/api/v1/actions/{action_id}/rollback", dependencies=[Depends(require_internal_token)])
def rollback_action(
    action_id: str,
    actor: str = Query(min_length=3, max_length=128),
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    active_service = service(db)
    try:
        action = active_service.rollback_action(action_id, actor=actor)
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"action": active_service.serialize_action(action)}


@app.post("/api/v1/actions/{action_id}/retry", dependencies=[Depends(require_internal_token)])
def retry_action(
    action_id: str,
    actor: str = Query(min_length=3, max_length=128),
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    active_service = service(db)
    try:
        action = active_service.retry_action(action_id, actor=actor)
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"action": active_service.serialize_action(action)}


@app.post("/api/v1/maintenance/expire", dependencies=[Depends(require_internal_token)])
def expire_actions(db: Session = Depends(get_soar_db)) -> dict[str, Any]:
    active_service = service(db)
    actions = active_service.expire_actions()
    db.commit()
    return {"rolled_back_count": len(actions), "action_ids": [action.id for action in actions]}


@app.get("/api/v1/metrics/summary", dependencies=[Depends(require_internal_token)])
def metrics(db: Session = Depends(get_soar_db)) -> dict[str, Any]:
    return service(db).metrics()


@app.post("/api/v1/orchestration-errors", dependencies=[Depends(require_internal_token)])
def orchestration_error(
    payload: OrchestrationErrorRequest,
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    error = service(db).record_orchestration_error(payload)
    db.commit()
    return {"recorded": True, "error_id": error.id}


@app.get("/api/v1/audit", dependencies=[Depends(require_internal_token)])
def audit_log(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    entries = db.scalars(select(SoarAudit).order_by(SoarAudit.occurred_at.desc()).limit(limit)).all()
    return {
        "count": len(entries),
        "items": [
            {
                "id": entry.id,
                "occurred_at": isoformat(entry.occurred_at),
                "event_type": entry.event_type,
                "actor_type": entry.actor_type,
                "actor": entry.actor,
                "incident_id": entry.incident_id,
                "action_id": entry.action_id,
                "details": entry.details,
            }
            for entry in entries
        ],
    }


@app.get("/api/v1/orchestration-errors", dependencies=[Depends(require_internal_token)])
def list_orchestration_errors(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_soar_db),
) -> dict[str, Any]:
    errors = db.scalars(
        select(OrchestrationError).order_by(OrchestrationError.occurred_at.desc()).limit(limit)
    ).all()
    return {
        "count": len(errors),
        "items": [
            {
                "id": item.id,
                "occurred_at": isoformat(item.occurred_at),
                "workflow_id": item.workflow_id,
                "workflow_name": item.workflow_name,
                "execution_id": item.execution_id,
                "error_message": item.error_message,
                "details": item.details,
            }
            for item in errors
        ],
    }


@app.get("/api/v1/schema", dependencies=[Depends(require_internal_token)])
def schema_state(db: Session = Depends(get_soar_db)) -> dict[str, Any]:
    return {
        "schema_version": SOAR_SCHEMA_VERSION,
        "incidents": int(db.scalar(select(func.count()).select_from(Incident)) or 0),
    }
