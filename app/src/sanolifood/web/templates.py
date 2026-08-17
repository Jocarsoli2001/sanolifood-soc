from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from sanolifood.core.config import get_settings
from sanolifood.core.security import csrf_token
from sanolifood.models import ROLE_LABELS, User


container_root = Path("/app")
project_dir = container_root if (container_root / "templates").is_dir() else Path(__file__).resolve().parents[3]
templates = Jinja2Templates(directory=str(project_dir / "templates"))


def view_context(
    request: Request,
    *,
    page_title: str,
    current_user: User | None = None,
    nav_active: str = "",
    **extra: Any,
) -> dict[str, Any]:
    settings = get_settings()
    initials = "SF"
    if current_user:
        name_parts = current_user.full_name.split()
        initials = "".join(part[0] for part in name_parts[:2]).upper()
    return {
        "request": request,
        "page_title": page_title,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "app_env": settings.app_env,
        "correlation_id": getattr(request.state, "correlation_id", "n/a"),
        "current_user": current_user,
        "user_initials": initials,
        "csrf_token": csrf_token(request),
        "role_labels": ROLE_LABELS,
        "nav_active": nav_active,
        **extra,
    }
