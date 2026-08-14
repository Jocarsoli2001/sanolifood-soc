from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sanolifood.core.config import get_settings


router = APIRouter()
project_dir = Path("/app") if Path("/app/templates").is_dir() else Path(__file__).resolve().parents[3]
templates = Jinja2Templates(directory=str(project_dir / "templates"))


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request) -> HTMLResponse:
    settings = get_settings()
    modules = [
        {"name": "Producción", "description": "Planificación y trazabilidad de lotes", "state": "Base preparada", "tone": "blue"},
        {"name": "Calidad", "description": "Controles, límites y liberación", "state": "Base preparada", "tone": "teal"},
        {"name": "Inventario", "description": "Ingredientes y movimientos", "state": "Base preparada", "tone": "orange"},
        {"name": "Auditoría", "description": "Evidencia operativa y de seguridad", "state": "Telemetría activa", "tone": "green"},
    ]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "page_title": "Centro de operaciones",
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "app_env": settings.app_env,
            "correlation_id": getattr(request.state, "correlation_id", "n/a"),
            "modules": modules,
        },
    )
