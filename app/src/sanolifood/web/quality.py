from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from sanolifood.core.events import record_event
from sanolifood.core.security import csrf_is_valid
from sanolifood.database.session import get_db
from sanolifood.models import ProductionLot, QualityCheck, User, UserRole
from sanolifood.services.operations import decimal_value, register_quality_check, transition_lot
from sanolifood.web.dependencies import PermissionDenied, get_current_user, require_roles
from sanolifood.web.templates import templates, view_context


router = APIRouter(prefix="/quality", tags=["quality"])
quality_write_required = require_roles(UserRole.ADMIN, UserRole.QUALITY)


def quality_response(
    request: Request,
    db: Session,
    current_user: User,
    *,
    errors: list[str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    lots = db.scalars(
        select(ProductionLot).order_by(ProductionLot.scheduled_at.desc()).limit(80)
    ).unique().all()
    inspectable_lots = [lot for lot in lots if lot.status in {"in_progress", "quality_hold"}]
    checks = db.scalars(
        select(QualityCheck).order_by(QualityCheck.inspected_at.desc()).limit(100)
    ).unique().all()
    return templates.TemplateResponse(
        request=request,
        name="quality/list.html",
        context=view_context(
            request,
            page_title="Calidad e inocuidad",
            current_user=current_user,
            nav_active="quality",
            lots=lots,
            inspectable_lots=inspectable_lots,
            checks=checks,
            can_write=current_user.role in {UserRole.ADMIN, UserRole.QUALITY},
            hold_count=sum(1 for lot in lots if lot.status == "quality_hold"),
            errors=errors or [],
            created=request.query_params.get("created", ""),
        ),
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def quality_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return quality_response(request, db, current_user)


@router.post("/checks", include_in_schema=False)
def create_quality_check(
    request: Request,
    lot_id: Annotated[int, Form()],
    check_type: Annotated[str, Form()],
    measured_value: Annotated[str, Form()],
    unit: Annotated[str, Form()],
    min_value: Annotated[str, Form()],
    max_value: Annotated[str, Form()],
    notes: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(quality_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("El control de calidad no superó la validación de seguridad.")
    errors: list[str] = []
    parsed_values: list[Decimal] = []
    for raw in (measured_value, min_value, max_value):
        try:
            parsed_values.append(decimal_value(raw))
        except ValueError as exc:
            errors.append(str(exc))
            parsed_values.append(Decimal("0"))
    if len(check_type.strip()) < 2 or not unit.strip():
        errors.append("El tipo de control y la unidad son obligatorios.")
    if errors:
        return quality_response(request, db, current_user, errors=errors, status_code=422)
    try:
        check, result = register_quality_check(
            db,
            lot_id=lot_id,
            check_type=check_type,
            measured_value=parsed_values[0],
            unit=unit,
            min_value=parsed_values[1],
            max_value=parsed_values[2],
            notes=notes,
            actor=current_user,
        )
    except ValueError as exc:
        db.rollback()
        return quality_response(request, db, current_user, errors=[str(exc)], status_code=422)
    event_type = "quality.check.passed" if result == "pass" else "quality.check.failed"
    record_event(db, request=request, event_type=event_type, outcome="success" if result == "pass" else "failure", actor=current_user, resource_type="quality_check", resource_id=str(check.id), details={"lot_code": check.production_lot.lot_code, "check_type": check.check_type, "measured_value": str(check.measured_value), "min_value": str(check.min_value), "max_value": str(check.max_value), "result": result})
    db.commit()
    return RedirectResponse(url=f"/quality?created=check_{result}", status_code=303)


@router.post("/lots/{lot_id}/decision", include_in_schema=False)
def decide_lot(
    lot_id: int,
    request: Request,
    decision: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(quality_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La decisión de calidad no superó la validación de seguridad.")
    if decision not in {"released", "rejected"}:
        return quality_response(request, db, current_user, errors=["La decisión no es válida."], status_code=422)
    try:
        lot, previous_status, _ = transition_lot(
            db, lot_id=lot_id, target_status=decision, actor=current_user
        )
    except ValueError as exc:
        db.rollback()
        return quality_response(request, db, current_user, errors=[str(exc)], status_code=422)
    record_event(db, request=request, event_type=f"quality.lot.{decision}", outcome="success", actor=current_user, resource_type="production_lot", resource_id=str(lot.id), details={"lot_code": lot.lot_code, "previous_status": previous_status, "decision": decision})
    db.commit()
    return RedirectResponse(url=f"/quality?created={decision}", status_code=303)
