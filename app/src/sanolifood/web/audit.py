from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from sanolifood.database.session import get_db
from sanolifood.models import AuditEvent, User, UserRole
from sanolifood.web.dependencies import require_roles
from sanolifood.web.templates import templates, view_context


router = APIRouter(prefix="/audit", tags=["audit"])
audit_required = require_roles(UserRole.ADMIN, UserRole.AUDITOR)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def audit_events(
    request: Request,
    current_user: User = Depends(audit_required),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    event_type = request.query_params.get("event_type", "").strip()
    outcome = request.query_params.get("outcome", "").strip()
    statement = select(AuditEvent)
    if event_type:
        statement = statement.where(AuditEvent.event_type.contains(event_type))
    if outcome in {"success", "failure", "blocked"}:
        statement = statement.where(AuditEvent.outcome == outcome)
    events = db.scalars(statement.order_by(AuditEvent.occurred_at.desc()).limit(200)).all()
    return templates.TemplateResponse(
        request=request,
        name="audit/list.html",
        context=view_context(
            request,
            page_title="Auditoría de seguridad",
            current_user=current_user,
            nav_active="audit",
            events=events,
            event_type_filter=event_type,
            outcome_filter=outcome,
        ),
    )
