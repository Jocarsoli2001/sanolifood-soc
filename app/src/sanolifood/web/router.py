from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sanolifood.database.session import get_db
from sanolifood.models import AuditEvent, Ingredient, ProductionLot, User
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
        {"name": "Producción", "description": "Planificación, recetas y trazabilidad de lotes", "state": "Operativo", "tone": "blue", "url": "/production"},
        {"name": "Calidad", "description": "Controles, límites y disposición de lotes", "state": "Operativo", "tone": "teal", "url": "/quality"},
        {"name": "Inventario", "description": "Ingredientes, proveedores y movimientos", "state": "Operativo", "tone": "orange", "url": "/inventory"},
        {"name": "Auditoría", "description": "Evidencia operativa y de seguridad", "state": "Funcional", "tone": "green", "url": "/audit"},
    ]
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    audit_events = db.scalar(select(func.count()).select_from(AuditEvent)) or 0
    active_lots = db.scalar(
        select(func.count()).select_from(ProductionLot).where(
            ProductionLot.status.in_(["planned", "in_progress", "quality_hold"])
        )
    ) or 0
    quality_holds = db.scalar(
        select(func.count()).select_from(ProductionLot).where(ProductionLot.status == "quality_hold")
    ) or 0
    low_stock = db.scalar(
        select(func.count()).select_from(Ingredient).where(
            Ingredient.is_active.is_(True), Ingredient.current_stock <= Ingredient.reorder_level
        )
    ) or 0
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
            active_lots=active_lots,
            quality_holds=quality_holds,
            low_stock=low_stock,
        ),
    )
