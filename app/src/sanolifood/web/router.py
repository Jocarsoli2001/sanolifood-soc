from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sanolifood.database.session import get_db
from sanolifood.models import AuditEvent, User
from sanolifood.web.dependencies import get_current_user
from sanolifood.web.templates import templates, view_context


router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    modules = [
        {"name": "Producción", "description": "Planificación y trazabilidad de lotes", "state": "Siguiente incremento", "tone": "blue"},
        {"name": "Calidad", "description": "Controles, límites y liberación", "state": "Siguiente incremento", "tone": "teal"},
        {"name": "Inventario", "description": "Ingredientes y movimientos", "state": "Siguiente incremento", "tone": "orange"},
        {"name": "Auditoría", "description": "Evidencia operativa y de seguridad", "state": "Funcional", "tone": "green", "url": "/audit"},
    ]
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    audit_events = db.scalar(select(func.count()).select_from(AuditEvent)) or 0
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=view_context(
            request,
            page_title="Centro de operaciones",
            current_user=current_user,
            nav_active="dashboard",
            modules=modules,
            active_users=active_users,
            audit_events=audit_events,
        ),
    )
