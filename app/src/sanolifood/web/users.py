from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from sanolifood.core.events import record_event
from sanolifood.core.security import csrf_is_valid, hash_password, password_validation_errors
from sanolifood.database.session import get_db
from sanolifood.models import ROLE_LABELS, User, UserRole
from sanolifood.web.dependencies import PermissionDenied, require_roles
from sanolifood.web.templates import templates, view_context


router = APIRouter(prefix="/users", tags=["identity"])
admin_required = require_roles(UserRole.ADMIN)


def users_response(
    request: Request,
    db: Session,
    current_user: User,
    *,
    errors: list[str] | None = None,
    form_data: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return templates.TemplateResponse(
        request=request,
        name="users/list.html",
        context=view_context(
            request,
            page_title="Usuarios y accesos",
            current_user=current_user,
            nav_active="users",
            users=users,
            role_options=[(role.value, ROLE_LABELS[role]) for role in UserRole],
            errors=errors or [],
            form_data=form_data or {},
            created=request.query_params.get("created") == "1",
            changed=request.query_params.get("changed") == "1",
        ),
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def list_users(
    request: Request,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return users_response(request, db, current_user)


@router.post("", response_class=HTMLResponse, include_in_schema=False)
def create_user(
    request: Request,
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    full_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La creación del usuario no superó la validación de seguridad.")

    normalized_username = username.strip().lower()
    normalized_email = email.strip().lower()
    normalized_name = full_name.strip()
    form_data = {"username": normalized_username, "email": normalized_email, "full_name": normalized_name, "role": role}
    errors = password_validation_errors(password)
    if len(normalized_username) < 3:
        errors.append("El nombre de usuario debe contener al menos 3 caracteres.")
    if "@" not in normalized_email:
        errors.append("Ingresa un correo electrónico válido.")
    if len(normalized_name) < 3:
        errors.append("Ingresa el nombre completo del usuario.")
    allowed_roles = {item.value for item in UserRole}
    if role not in allowed_roles:
        errors.append("El rol seleccionado no es válido.")
    duplicate = db.scalar(select(User).where(or_(User.username == normalized_username, User.email == normalized_email)))
    if duplicate:
        errors.append("Ya existe un usuario con ese nombre o correo.")
    if errors:
        return users_response(request, db, current_user, errors=errors, form_data=form_data, status_code=422)

    new_user = User(
        username=normalized_username,
        email=normalized_email,
        full_name=normalized_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    record_event(
        db,
        request=request,
        event_type="identity.user.created",
        outcome="success",
        actor=current_user,
        resource_type="user",
        resource_id=str(new_user.id),
        details={"created_username": new_user.username, "assigned_role": new_user.role},
    )
    db.commit()
    return RedirectResponse(url="/users?created=1", status_code=303)


@router.post("/{user_id}/toggle", include_in_schema=False)
def toggle_user(
    user_id: int,
    request: Request,
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La actualización del usuario no superó la validación de seguridad.")
    target = db.get(User, user_id)
    if target is None:
        raise PermissionDenied("El usuario solicitado no existe.")
    if target.id == current_user.id:
        raise PermissionDenied("No puedes desactivar tu propia cuenta administrativa.")
    target.is_active = not target.is_active
    record_event(
        db,
        request=request,
        event_type="identity.user.status_changed",
        outcome="success",
        actor=current_user,
        resource_type="user",
        resource_id=str(target.id),
        details={"target_username": target.username, "is_active": target.is_active},
    )
    db.commit()
    return RedirectResponse(url="/users?changed=1", status_code=303)
