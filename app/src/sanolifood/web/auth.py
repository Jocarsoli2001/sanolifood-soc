from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sanolifood.core.config import get_settings
from sanolifood.core.events import record_event
from sanolifood.core.security import (
    DUMMY_PASSWORD_HASH,
    csrf_is_valid,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from sanolifood.database.session import get_db
from sanolifood.models import User
from sanolifood.services.soar_controls import active_control
from sanolifood.web.dependencies import PermissionDenied, get_current_user
from sanolifood.web.templates import templates, view_context


router = APIRouter(prefix="/auth", tags=["identity"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalized_datetime(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def login_response(request: Request, *, error: str | None = None, username: str = "", status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context=view_context(request, page_title="Acceso seguro", error=error, username=username),
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request) -> Response:
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return login_response(request)


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> Response:
    normalized_username = username.strip().lower()
    if not csrf_is_valid(request, csrf_token):
        record_event(
            db,
            request=request,
            event_type="auth.csrf.rejected",
            outcome="failure",
            actor_username=normalized_username,
            details={"endpoint": "/auth/login"},
        )
        db.commit()
        raise PermissionDenied("La solicitud de acceso no superó la validación de seguridad.")

    user = db.scalar(select(User).where(func.lower(User.username) == normalized_username))
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        record_event(
            db,
            request=request,
            event_type="auth.login.failed",
            outcome="failure",
            actor_username=normalized_username,
            details={"reason": "invalid_credentials"},
        )
        db.commit()
        return login_response(
            request,
            error="No fue posible iniciar sesión con las credenciales proporcionadas.",
            username=normalized_username,
            status_code=401,
        )

    now = utcnow()
    soar_lock = active_control(db, "app_account_lock", normalized_username, at=now)
    if soar_lock is not None:
        record_event(
            db,
            request=request,
            event_type="auth.login.blocked",
            outcome="blocked",
            actor=user,
            details={"reason": "soar_temporary_control", "incident_id": soar_lock.incident_id},
        )
        db.commit()
        return login_response(
            request,
            error="La cuenta está temporalmente bloqueada. Intenta nuevamente más tarde.",
            username=normalized_username,
            status_code=423,
        )
    locked_until = normalized_datetime(user.locked_until)
    if locked_until and locked_until > now:
        record_event(
            db,
            request=request,
            event_type="auth.login.blocked",
            outcome="blocked",
            actor=user,
            details={"reason": "temporary_lockout"},
        )
        db.commit()
        return login_response(
            request,
            error="La cuenta está temporalmente bloqueada. Intenta nuevamente más tarde.",
            username=normalized_username,
            status_code=423,
        )

    if not user.is_active or not verify_password(password, user.password_hash):
        settings = get_settings()
        user.failed_login_attempts += 1
        event_type = "auth.login.failed"
        outcome = "failure"
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(seconds=settings.login_lockout_seconds)
            event_type = "auth.account.locked"
            outcome = "blocked"
        record_event(
            db,
            request=request,
            event_type=event_type,
            outcome=outcome,
            actor=user,
            details={"reason": "inactive_or_invalid_credentials", "attempts": user.failed_login_attempts},
        )
        db.commit()
        return login_response(
            request,
            error="No fue posible iniciar sesión con las credenciales proporcionadas.",
            username=normalized_username,
            status_code=401,
        )

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    request.session.clear()
    request.session.update({"user_id": user.id, "username": user.username, "role": user.role})
    record_event(
        db,
        request=request,
        event_type="auth.login.succeeded",
        outcome="success",
        actor=user,
        details={"role": user.role},
    )
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout", include_in_schema=False)
def logout(
    request: Request,
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La solicitud de cierre de sesión no superó la validación de seguridad.")
    record_event(db, request=request, event_type="auth.logout", outcome="success", actor=current_user)
    db.commit()
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=303)
